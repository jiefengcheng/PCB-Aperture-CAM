#!/usr/bin/env python3
"""Execute one predeclared, source-bound square-neighbor mechanism experiment."""
from __future__ import annotations

import hashlib
import argparse
import html
import json
import math
import platform
import re
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path

import sexpdata
import shapely
from shapely import STRtree, from_wkb, to_wkb
from shapely.geometry import Point, box
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.crop_square_neighbor_experiment import Settings, construct, geometry_hash, verify_addition
from src.native_inventory import inventory
from src.native_reference import one

OUT = ROOT / "out/crop_dynamic_tasks/square_neighbor_mechanism_20261024"
POLICY_SHA = "7d8f55ca645a2bc33a8dabbf1f0afb88f8bdf622ed42f4d203d2fc4ec61d588c"
REQUIRED_EXECUTION_CHECKS = frozenset({
    "later_source_core_preserved", "earlier_source_core_preserved",
    "assembled_actual_copper_constraints", "both_control_geometries_pass_constraints",
    "earlier_addition_changes_later_copper", "square_rule_changes_later_copper",
    "square_has_no_effect_when_earlier_addition_is_absent", "square_consumed_by_construction",
    "no_square_recess_without_actual_conflict", "square_vertices_on_enlarged_circle",
    "deterministic_replay", "sealed_source_unchanged",
})
REQUIRED_GEOMETRIES = frozenset({
    "a_core", "b_core", "a_accepted", "b_accepted", "a_envelope", "b_envelope",
    "b_square", "b_without_a_addition", "b_without_square",
    "b_without_a_addition_and_square", "b_square_removed_optional", "b_live_conflict",
})


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def source_scene(source, policy):
    inv = inventory(source)
    rows = [row for row in inv["objects"] if "F.Cu" in row["layers"]]
    unsupported = [row["id"] for row in rows if not row["geometry_sha256"]]
    if unsupported:
        raise ValueError("UNSUPPORTED_FCU_GEOMETRY:" + str(unsupported))
    shapes = [from_wkb(inv["payloads"][row["geometry_sha256"]]) for row in rows]
    tree = STRtree(shapes)
    occurrences = defaultdict(list)
    viewport = box(*policy["viewport_mm"])
    for index, (row, geometry) in enumerate(zip(rows, shapes)):
        if row["kind"] != "gr_circle" or not geometry.intersects(viewport):
            continue
        node = sexpdata.loads(source[slice(*row["source_span"])].decode())
        if str(one(node, "fill", ["none"])[0]) not in ("yes", "solid"):
            continue
        occurrences[row["geometry_sha256"]].append(index)
    sites = []
    for geometry_sha, indexes in occurrences.items():
        core = shapes[indexes[0]]
        center = [core.centroid.x, core.centroid.y]
        radius = (core.bounds[2]-core.bounds[0]+core.bounds[3]-core.bounds[1])/4
        sites.append({"source_id": min(rows[i]["id"] for i in indexes),
                      "aliases": sorted(rows[i]["id"] for i in indexes),
                      "core": core, "center": center, "radius": radius,
                      "geometry_sha256": geometry_sha, "indexes": indexes})
    sites.sort(key=lambda site: (site["center"][1], site["center"][0], site["source_id"]))
    assert len(sites) == 51
    # Fresh whole-source same-layer physical contact groups, not electrical nets.
    group_by_index = {}
    for site in sites:
        seed = site["indexes"][0]
        if seed not in group_by_index:
            seen = {seed}
            todo = [seed]
            while todo:
                current = todo.pop()
                for item in tree.query(shapes[current], predicate="intersects"):
                    index = int(item)
                    if index not in seen:
                        seen.add(index)
                        todo.append(index)
            members = sorted(rows[i]["id"] for i in seen)
            group_id = hashlib.sha256("\n".join(members).encode()).hexdigest()
            for index in seen:
                group_by_index[index] = group_id
        site["physical_contact_group"] = group_by_index[seed]
        site["enlarged_radius"] = policy["radius_multiplier"] * site["radius"]
    return inv, rows, shapes, tree, sites


def obstacles_for(site, rows, shapes, tree, source, settings, accepted=None):
    envelope = Point(*site["center"]).buffer(site["enlarged_radius"],
                                             quad_segs=settings.quad_segs)
    influence = envelope.buffer(settings.construction_gap_mm + 0.00002,
                                quad_segs=settings.quad_segs)
    result = []
    # Current accepted geometry is within its envelope, so extend search with
    # the live shape explicitly even when its source bounds miss the query.
    indexes = {int(i) for i in tree.query(influence)}
    if accepted:
        indexes.update(accepted["indexes"])
    for index in sorted(indexes):
        row, geometry = rows[index], shapes[index]
        if row["id"] in site["aliases"]:
            continue
        source_id = row["id"]
        if accepted and index in accepted["indexes"]:
            geometry = accepted["candidate"]
            source_id = accepted["source_id"]
        port = None
        if row["kind"] in ("segment", "arc") and geometry.intersects(
                site["core"].buffer(1e-7, quad_segs=settings.quad_segs)):
            raw = source[slice(*row["source_span"])].decode()
            width = re.search(r"\(\s*width\s+([0-9.]+)\s*\)", raw)
            if not width:
                raise ValueError("SOURCE_ATTACHMENT_WIDTH_UNAVAILABLE:" + row["id"])
            lateral = max(0.005, float(width.group(1))/2 + 0.005)
            port = geometry.buffer(lateral, quad_segs=settings.quad_segs).intersection(
                site["core"].buffer(site["enlarged_radius"]-site["radius"],
                                     quad_segs=settings.quad_segs))
        result.append({"source_id": source_id, "geometry": geometry,
                       "kind": row["kind"], "port_zone": port})
    return result


def site_record(site):
    return {key: site[key] for key in ("source_id", "aliases", "center", "radius",
                                       "enlarged_radius", "geometry_sha256",
                                       "physical_contact_group")}


def obstacle_records(obstacles):
    return [{"source_id": row["source_id"], "kind": row["kind"],
             "geometry_sha256": geometry_hash(row["geometry"]),
             "port_zone_wkb": to_wkb(row["port_zone"], byte_order=1).hex()
             if row["port_zone"] is not None else None}
            for row in obstacles]


def path_for(geometry):
    if geometry.is_empty:
        return ""
    if geometry.geom_type in ("MultiPolygon", "GeometryCollection"):
        return " ".join(path_for(part) for part in geometry.geoms)
    if geometry.geom_type != "Polygon":
        return ""
    def ring(coords):
        return "M " + " L ".join(f"{x:.9f} {y:.9f}" for x, y, *_ in coords) + " Z"
    return " ".join([ring(geometry.exterior.coords),
                     *(ring(part.coords) for part in geometry.interiors)])


def shape(geometry, fill, stroke="none", width=.002, opacity=1, dash=""):
    return (f'<path d="{path_for(geometry)}" fill="{fill}" stroke="{stroke}" '
            f'stroke-width="{width}" opacity="{opacity}" fill-rule="evenodd" '
            f'stroke-dasharray="{dash}"/>')


def positive_gallery_issues(report):
    """Check report eligibility for a positive page, not geometry independently."""
    issues = []
    if report.get("status") != "MECHANISM_DEMONSTRATION_SIZE_NOT_QUALIFIED":
        issues.append("The current execution did not establish the mechanism.")
    checks = report.get("checks")
    if not isinstance(checks, dict) or set(checks) != REQUIRED_EXECUTION_CHECKS:
        issues.append("The complete required execution checks are missing.")
    elif any(value is not True for value in checks.values()):
        issues.append("One or more required execution checks did not pass.")
    if type(report.get("causal_actual_source_events")) is not int or report["causal_actual_source_events"] != 1:
        issues.append("Exactly one evidenced actual-source mechanism event is required.")
    return issues


def positive_gallery_bindings(report, a, b, live, no_add, no_square):
    """Bind the displayed scene to its saved receipt, source, policy and WKB."""
    issues = []
    try:
        policy_path = OUT/"policy.json"
        if sha(policy_path) != POLICY_SHA or report.get("policy_sha256") != POLICY_SHA:
            return ["The policy binding does not match the frozen experiment."]
        policy = json.loads(policy_path.read_bytes())
        if sha(OUT/"owner_handoff.md") != policy["owner_handoff_sha256"]:
            issues.append("The owner handoff binding does not match the frozen policy.")
        if sha(ROOT/policy["source"]) != report.get("source_sha256") or report.get("source_sha256") != policy["source_sha256"]:
            issues.append("The source binding does not match this execution.")
        receipt_path = OUT/"report.json"
        if json.loads(receipt_path.read_bytes()) != report:
            issues.append("The displayed execution differs from the saved receipt.")
        for filename, binding in (("selection.json", "selection_sha256"),
                                  ("obstacle_bindings.json", "obstacle_bindings_sha256")):
            if sha(OUT/filename) != report[binding]:
                issues.append("A linked execution artifact does not match its receipt.")
        if set(report["geometry_sha256"]) != REQUIRED_GEOMETRIES:
            return issues + ["The complete required geometry artifacts are missing."]
        for name, expected in report["geometry_sha256"].items():
            if sha(OUT/(name+".wkb")) != expected:
                issues.append("A saved geometry artifact does not match its receipt.")
        if issues:
            return issues
        displayed = {"a_core": a["core"], "b_core": b["core"],
                     "a_accepted": a["candidate"], "b_accepted": live["candidate"],
                     "a_envelope": a["result"]["envelope"], "b_envelope": live["envelope"],
                     "b_square": live["square"], "b_without_a_addition": no_add["candidate"],
                     "b_without_square": no_square["candidate"],
                     "b_square_removed_optional": live["square_removed_optional"],
                     "b_live_conflict": live["neighbor_conflict"]}
        if any(geometry_hash(geometry) != report["geometry_sha256"].get(name)
               for name, geometry in displayed.items()):
            issues.append("The displayed geometry differs from the bound artifacts.")
        if a["source_id"] != report["a"]["source_id"] or b["source_id"] != report["b"]["source_id"]:
            issues.append("The displayed source identities differ from the receipt.")
        for filename, binding in (("local_full_inventory_audit.json", "report_sha256"),
                                  ("chatgpt_desk_audit.json", "audited_report_sha256")):
            audit = OUT/filename
            if audit.exists() and json.loads(audit.read_bytes()).get(binding) != sha(receipt_path):
                issues.append("A linked audit belongs to another execution receipt.")
    except (OSError, KeyError, TypeError, ValueError):
        issues.append("Required source, receipt or geometry evidence is unavailable.")
    return issues


def write_landing_page(page):
    """Publish a complete page through a same-directory atomic replacement."""
    pending = OUT/".index.html.next"
    pending.write_text(page)
    pending.replace(OUT/"index.html")


def write_unestablished_page(report, issues):
    """Replace any stale positive landing page with the current failure state."""
    reasons = "".join(f"<li>{html.escape(issue)}</li>" for issue in issues)
    status = html.escape(str(report.get("status", "NOT_ESTABLISHED")))
    write_landing_page(
        '<!doctype html><html lang="en"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>Square-neighbor mechanism not established</title>'
        '<main style="font:18px/1.5 system-ui;max-width:800px;margin:40px auto;padding:20px">'
        '<h1>Mechanism not established for this run</h1>'
        f'<p><strong>{status}</strong></p><ul>{reasons}</ul>'
        '<p><a href="report.json">Inspect the recorded execution report</a></p>'
        '</main></html>')


def gallery(a, b, live, no_add, no_square, context, report):
    issues = positive_gallery_issues(report)
    if not issues:
        issues = positive_gallery_bindings(report, a, b, live, no_add, no_square)
    if issues:
        write_unestablished_page(report, issues)
        return False
    pair = unary_union([a["result"]["envelope"], live["envelope"]])
    x0, y0, x1, y1 = pair.bounds
    pad = .06
    bounds = (x0-pad, y0-pad, x1+pad, y1+pad)
    common = shape(context, "#697686", opacity=.45)
    cores = shape(a["core"], "#ef6a60") + shape(b["core"], "#ef6a60")
    core_lines = shape(a["core"], "none", "#ff8179", .002) + shape(b["core"], "none", "#ff8179", .002)
    a_live = shape(a["candidate"], "#38bfc5", opacity=.8)
    envelope_lines = (shape(a["result"]["envelope"], "none", "#69aafa", .0025, dash=".008 .005")
                      + shape(live["envelope"], "none", "#69aafa", .0025, dash=".008 .005"))
    squares = (shape(a["result"]["square"], "none", "#ffd166", .0025)
               + shape(live["square"], "none", "#ffd166", .0025))
    delta_a = live["candidate"].symmetric_difference(no_add["candidate"])
    delta_s = live["candidate"].symmetric_difference(no_square["candidate"])
    scenes = [
        ("1 · ORG source pair", "Red cores and grey surrounding copper are unchanged source geometry.", common+cores),
        ("2 · Proposed envelopes → actual conflict", "Blue: fixed 1.5× circular envelopes. Gold: derived squares. Magenta: B’s optional envelope conflicts with A’s accepted copper exclusion.",
         common+a_live+shape(b["core"], "#ef6a60")+envelope_lines+squares+shape(live["neighbor_conflict"], "#fa65c0", opacity=.8)+core_lines),
        ("3 · Square side consumes optional copper", f"B’s {live['square_side']} square supporting line determines the facing lobe. Gold is removed optional copper; green is B after all constraints.",
         common+a_live+shape(live["square_removed_optional"], "#ffd166", opacity=.6)+shape(live["candidate"], "#38d6a0")+envelope_lines+squares+core_lines),
        ("4 · Check A: remove only A’s addition", f"Purple: B recomputed with A restored to ORG. Green: live B. Pink: changed copper ({report['check_a_symmetric_difference_mm2']:.6f} mm²). Radius and all other settings are fixed.",
         common+shape(a["core"], "#ef6a60")+shape(no_add["candidate"], "#a68bfa", opacity=.7)+shape(live["candidate"], "#38d6a0", opacity=.8)+shape(delta_a, "#fa65c0")+core_lines),
        ("5 · Check B: disable square rule", f"Purple: ordinary clearance clipping. Green: square-aware B. Gold: changed copper ({report['check_b_symmetric_difference_mm2']:.6f} mm²). Same live A and radius.",
         common+a_live+shape(no_square["candidate"], "#a68bfa", opacity=.8)+shape(live["candidate"], "#38d6a0", opacity=.8)+shape(delta_s, "#ffd166")+core_lines),
        ("6 · Assembled experimental copper", "Teal: A accepted first. Green: B accepted after square recession. Red outlines: both original cores. Complete applicable surroundings were checked.",
         common+a_live+shape(live["candidate"], "#38d6a0")+shape(a["core"], "none", "#ff8179", .002)+shape(b["core"], "none", "#ff8179", .002)),
    ]
    cards = []
    for index, (title, text, content) in enumerate(scenes, 1):
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{bounds[0]} {-bounds[3]} '
               f'{bounds[2]-bounds[0]} {bounds[3]-bounds[1]}" role="img" aria-label="{html.escape(title)}">'
               f'<rect x="{bounds[0]}" y="{-bounds[3]}" width="{bounds[2]-bounds[0]}" '
               f'height="{bounds[3]-bounds[1]}" fill="#111923"/><g transform="scale(1,-1)">{content}</g></svg>')
        (OUT/f"step_{index}.svg").write_text(svg)
        cards.append(f'<article><h2>{title}</h2>{svg}<p>{text}</p></article>')
    page = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Square-guided neighbor recession · one source pair</title><style>
body{font:16px/1.5 system-ui;background:#eaf0f5;color:#152b40;margin:0}main{max-width:1500px;margin:auto;padding:24px}h1{font-size:30px;margin-bottom:6px}.status{padding:12px 18px;background:#fff0cc;border-left:5px solid #d99a15}section{display:grid;grid-template-columns:1fr 1fr;gap:18px}article{background:white;border-radius:12px;padding:18px;border:1px solid #d0dae3}h2{font-size:21px;margin:0 0 12px}svg{width:100%;height:350px;border-radius:8px;overflow:hidden;background:#111923}article p{min-height:72px}.legend{display:flex;gap:20px;flex-wrap:wrap}code{font-size:13px;overflow-wrap:anywhere}table{border-collapse:collapse;width:100%;background:white;margin:20px 0}td,th{padding:9px;border:1px solid #cdd8e0;text-align:left}details{background:white;padding:16px;margin:16px 0}a{color:#086f80}@media(max-width:850px){section{grid-template-columns:1fr}main{padding:12px}} </style><main>
<h1>The square now changes the neighbor-facing copper</h1>
<p>One actual ORG pair · A grows first, then B responds to A’s accepted addition.</p>
<p class="status"><strong>MECHANISM_DEMONSTRATION — SIZE_NOT_QUALIFIED</strong><br>Provisional axis-aligned lobe-recession operator. No EDIT construction input. This is not owner acceptance or the three-event T01 objective.</p>
<p class="legend"><span style="color:#2870b5">Blue: enlarged envelopes</span><span style="color:#987115">Gold: squares / removed lobe</span><span style="color:#168c69">Green: later B</span><span style="color:#197b80">Teal: earlier A</span></p>'''
    page += '<section>' + ''.join(cards) + '</section>'
    page += '<h2>Does the square respond specifically to A’s addition?</h2>'
    page += '<table><tr><th>A geometry supplied to B</th><th>Square on versus off: changed B copper</th></tr>'
    page += f'<tr><td>Accepted A, including its addition</td><td>{report["four_condition_control"]["square_effect_with_a_addition_mm2"]:.6f} mm²</td></tr>'
    page += '<tr><td>A restored to ORG; its addition removed</td><td>0.000000 mm² — same B with square on or off</td></tr></table>'
    page += '<p>The earlier addition creates a clearance conflict. The square changes B’s response to that conflict. The untrimmed disks need not physically overlap.</p>'
    page += '<table><tr><th>Verification</th><th>Result</th></tr>'
    for key, value in report["checks"].items():
        page += f'<tr><td>{html.escape(key.replace("_", " "))}</td><td>{"PASS" if value else "FAIL"}</td></tr>'
    page += '</table><details><summary>Exact sources, operator and recorded evidence</summary>'
    page += f'<p>A source ID: <code>{a["source_id"]}</code><br>B source ID: <code>{b["source_id"]}</code></p>'
    page += '<p>Geometry consumer: <code>square_facing_lobe</code> uses the square side; <code>construct</code> removes that lobe before ordinary constraints and acceptance.</p>'
    page += '<p>Source-existing attached trace ports permit new land copper to join that same trace only inside a fixed source-derived local zone. All other copper remains checked within that zone; original traces and core-to-trace contacts are preserved. This is geometric contact, not verified net intent.</p>'
    page += '<p><a href="report.json">Measurements and four conditions</a> · <a href="selection.json">Frozen pair selection</a> · <a href="policy.json">Predeclared policy</a> · <a href="owner_handoff.md">Owner handoff</a> · <a href="SHA256SUMS">Checksums</a></p>'
    for filename, label in (("local_full_inventory_audit.json", "Full source and port audit"),
                            ("chatgpt_desk_audit.json", "ChatGPT desk audit")):
        page += (f'<p><a href="{filename}">{label}: recorded separately</a></p>'
                 if (OUT/filename).exists() else f'<p>{label}: NOT_RUN at page generation.</p>')
    page += '</details></main></html>'
    write_landing_page(page)
    return True


def main(output_dir=None):
    global OUT
    if output_dir is not None:
        destination = Path(output_dir).resolve()
        if not destination.is_relative_to(ROOT/"out"):
            raise ValueError("RUN_OUTPUT_MUST_BE_UNDER_PROJECT_OUT")
        if destination.exists() and any(destination.iterdir()):
            raise SystemExit("EXISTING_EVIDENCE_RETAINED: choose a fresh --output directory")
        seed = ROOT/"out/crop_dynamic_tasks/square_neighbor_mechanism_20261024"
        destination.mkdir(parents=True, exist_ok=True)
        for name in ("policy.json", "owner_handoff.md"):
            shutil.copy2(seed/name, destination/name)
        OUT = destination
    elif (OUT/"report.json").exists():
        raise SystemExit("EXISTING_EVIDENCE_RETAINED: supply --output with a fresh directory")
    assert sha(OUT/"policy.json") == POLICY_SHA
    policy = json.loads((OUT/"policy.json").read_bytes())
    source_path = ROOT/policy["source"]
    assert sha(source_path) == policy["source_sha256"]
    source = source_path.read_bytes()
    settings = Settings()
    inv, rows, shapes, tree, sites = source_scene(source, policy)
    class_counts = Counter(round(site["radius"], 5) for site in sites)
    common_classes = [item[0] for item in sorted(class_counts.items(), key=lambda item: (-item[1], item[0]))[:2]]
    eligible = [site for site in sites if round(site["radius"], 5) in common_classes]
    potential = []
    for a in eligible:
        for b in eligible:
            if a["physical_contact_group"] == b["physical_contact_group"]:
                continue
            gap = math.dist(a["center"], b["center"])-a["radius"]-b["radius"]
            ra = a["enlarged_radius"]-a["radius"]
            rb = b["enlarged_radius"]-b["radius"]
            if rb+settings.construction_gap_mm+2e-5 < gap < ra+rb+settings.construction_gap_mm-2e-5:
                potential.append((a, b, gap))
    potential.sort(key=lambda pair: (pair[0]["center"][1], pair[0]["center"][0],
                                     pair[0]["source_id"], pair[1]["center"][1],
                                     pair[1]["center"][0], pair[1]["source_id"]))
    attempts = []
    selected = None
    for a, b, gap in potential:
        obs_a = obstacles_for(a, rows, shapes, tree, source, settings)
        result_a = construct(a["core"], a["center"], a["enlarged_radius"], obs_a,
                             square_enabled=False, settings=settings)
        verification_a = verify_addition(a["core"], result_a["candidate"], result_a["envelope"],
                                         obs_a, settings=settings)
        live_a = {**a, "candidate": result_a["candidate"], "result": result_a}
        obs_b = obstacles_for(b, rows, shapes, tree, source, settings, live_a)
        b_optional = Point(*b["center"]).buffer(b["enlarged_radius"],
                                               quad_segs=settings.quad_segs).difference(b["core"])
        actual_conflict = b_optional.intersection(result_a["candidate"].buffer(
            settings.construction_gap_mm, quad_segs=settings.quad_segs)).area
        added_a = result_a["candidate"].difference(a["core"]).area
        attempts.append({"a": a["source_id"], "b": b["source_id"],
                         "org_analytic_gap_mm": gap, "a_added_area_mm2": added_a,
                         "b_envelope_live_conflict_mm2": actual_conflict,
                         "a_constraints_pass": verification_a["passed"]})
        if (added_a > settings.event_epsilon_mm2 and actual_conflict > settings.event_epsilon_mm2
                and verification_a["passed"]):
            selected = (live_a, b, obs_a, obs_b)
            break
    selection = {"policy_sha256": POLICY_SHA, "source_sha256": inv["source_sha256"],
                 "all_circle_sites": len(sites), "source_radius_class_counts": dict(class_counts),
                 "eligible_common_class_sites": len(eligible), "potential_directed_pairs": len(potential),
                 "attempts_before_later_square_execution": attempts,
                 "selected_pair": [site_record(selected[0]), site_record(selected[1])] if selected else None}
    # Persist before the square operation or either causal control is evaluated.
    dump(OUT/"selection.json", selection)
    if not selected:
        unavailable = {"status": "NO_QUALIFYING_SQUARE_AWARE_INTERACTION_WITHIN_DECLARED_RANGE",
                       "selection_sha256": sha(OUT/"selection.json")}
        dump(OUT/"report.json", unavailable)
        write_unestablished_page(unavailable, ["No qualifying pair was found within the frozen policy."])
        print("No qualifying pair within frozen policy")
        raise SystemExit(1)
    a, b, obs_a, obs_b = selected
    kwargs = {"earlier_neighbor_id": a["source_id"],
              "earlier_neighbor_center": a["center"], "settings": settings}
    live = construct(b["core"], b["center"], b["enlarged_radius"], obs_b, **kwargs)
    original_obs_b = obstacles_for(b, rows, shapes, tree, source, settings)
    # Normalize A aliases for the same neighbor ID even in source-only control.
    for row in original_obs_b:
        if row["source_id"] in a["aliases"]:
            row["source_id"] = a["source_id"]
    no_add = construct(b["core"], b["center"], b["enlarged_radius"], original_obs_b, **kwargs)
    no_square = construct(b["core"], b["center"], b["enlarged_radius"], obs_b,
                          square_enabled=False, **kwargs)
    neither = construct(b["core"], b["center"], b["enlarged_radius"], original_obs_b,
                        square_enabled=False, **kwargs)
    replay = construct(b["core"], b["center"], b["enlarged_radius"], obs_b, **kwargs)
    verify_b = verify_addition(b["core"], live["candidate"], live["envelope"], obs_b, settings=settings)
    final_b = {**b, "candidate": live["candidate"]}
    final_obs_a = obstacles_for(a, rows, shapes, tree, source, settings, final_b)
    final_verify_a = verify_addition(a["core"], a["candidate"], a["result"]["envelope"], final_obs_a,
                                    settings=settings)
    verify_no_add = verify_addition(b["core"], no_add["candidate"], no_add["envelope"], original_obs_b,
                                    settings=settings)
    verify_no_square = verify_addition(b["core"], no_square["candidate"], no_square["envelope"], obs_b,
                                       settings=settings)
    dump(OUT/"obstacle_bindings.json", {
        "a_source_scene": obstacle_records(obs_a),
        "b_live_scene": obstacle_records(obs_b),
        "b_source_scene": obstacle_records(original_obs_b),
        "a_assembled_scene": obstacle_records(final_obs_a)})
    da = live["candidate"].symmetric_difference(no_add["candidate"]).area
    ds = live["candidate"].symmetric_difference(no_square["candidate"]).area
    ds_without_addition = no_add["candidate"].symmetric_difference(neither["candidate"]).area
    vertex_error = max(abs(math.dist(b["center"], vertex)-b["enlarged_radius"])
                       for vertex in list(live["square"].exterior.coords)[:4])
    checks = {"later_source_core_preserved": verify_b["checks"]["source_core_preserved"],
              "earlier_source_core_preserved": final_verify_a["checks"]["source_core_preserved"],
              "assembled_actual_copper_constraints": verify_b["passed"] and final_verify_a["passed"],
              "both_control_geometries_pass_constraints": verify_no_add["passed"] and verify_no_square["passed"],
              "earlier_addition_changes_later_copper": da > settings.event_epsilon_mm2,
              "square_rule_changes_later_copper": ds > settings.event_epsilon_mm2,
              "square_has_no_effect_when_earlier_addition_is_absent": ds_without_addition <= settings.event_epsilon_mm2,
              "square_consumed_by_construction": live["square_consumed"],
              "no_square_recess_without_actual_conflict": not no_add["square_consumed"],
              "square_vertices_on_enlarged_circle": vertex_error <= 1e-12,
              "deterministic_replay": geometry_hash(replay["candidate"]) == geometry_hash(live["candidate"]),
              "sealed_source_unchanged": sha(source_path) == policy["source_sha256"]}
    geometries = {"a_core": a["core"], "b_core": b["core"], "a_accepted": a["candidate"],
                  "b_accepted": live["candidate"], "b_without_a_addition": no_add["candidate"],
                  "b_without_square": no_square["candidate"], "b_square": live["square"],
                  "b_without_a_addition_and_square": neither["candidate"],
                  "b_envelope": live["envelope"], "a_envelope": a["result"]["envelope"],
                  "b_square_removed_optional": live["square_removed_optional"],
                  "b_live_conflict": live["neighbor_conflict"]}
    hashes = {}
    for name, geometry in geometries.items():
        path = OUT/(name+".wkb")
        path.write_bytes(to_wkb(geometry, byte_order=1))
        hashes[name] = sha(path)
    report = {"schema": "square-neighbor-mechanism-result/1",
              "status": "MECHANISM_DEMONSTRATION_SIZE_NOT_QUALIFIED" if all(checks.values()) else "MECHANISM_NOT_ESTABLISHED",
              "checks": checks, "source_sha256": inv["source_sha256"], "policy_sha256": POLICY_SHA,
              "selection_sha256": sha(OUT/"selection.json"),
              "obstacle_bindings_sha256": sha(OUT/"obstacle_bindings.json"),
              "implementation_sha256": sha(ROOT/"src/crop_square_neighbor_experiment.py"),
              "runner_sha256": sha(Path(__file__)), "inventory_sha256": sha(ROOT/"src/native_inventory.py"),
              "runtime": {"python": platform.python_version(), "shapely": shapely.__version__,
                          "geos": shapely.geos_version_string, "inventory": inv["version"]},
              "source_fcu_objects": len(rows), "unsupported_fcu_objects": 0,
              "a": site_record(a), "b": site_record(b),
              "a_applicable_obstacles": len(obs_a), "b_applicable_obstacles": len(obs_b),
              "a_attachment_source_ids": [row["source_id"] for row in obs_a if row["port_zone"] is not None],
              "b_attachment_source_ids": [row["source_id"] for row in obs_b if row["port_zone"] is not None],
              "check_a_symmetric_difference_mm2": da, "check_b_symmetric_difference_mm2": ds,
              "four_condition_control": {
                  "live_square_enabled": "b_accepted.wkb",
                  "live_square_disabled": "b_without_square.wkb",
                  "source_only_square_enabled": "b_without_a_addition.wkb",
                  "source_only_square_disabled": "b_without_a_addition_and_square.wkb",
                  "square_effect_with_a_addition_mm2": ds,
                  "square_effect_without_a_addition_mm2": ds_without_addition,
                  "ordinary_clipping_effect_of_a_addition_mm2": no_square["candidate"].symmetric_difference(neither["candidate"]).area},
              "square_side": live["square_side"], "square_vertex_max_error_mm": vertex_error,
              "square_supporting_line": {
                  "square_source": "analytic pre-clipping B enlarged circle",
                  "b_source_id": b["source_id"], "earlier_source_id": a["source_id"],
                  "side": live["square_side"],
                  "square_bounds_mm": list(live["square"].bounds),
                  "perpendicular_center_distance_mm": b["enlarged_radius"]/math.sqrt(2),
                  "removal_mask": "b_square_removed_optional.wkb"},
              "a_added_area_mm2": a["candidate"].difference(a["core"]).area,
              "b_added_area_mm2": live["candidate"].difference(b["core"]).area,
              "b_square_removed_optional_area_mm2": live["square_removed_optional"].area,
              "a_b_final_copper_gap_mm": a["candidate"].distance(live["candidate"]),
              "verification_a_assembled": final_verify_a, "verification_b": verify_b,
              "control_verification_no_addition": verify_no_add,
              "control_verification_no_square": verify_no_square,
              "geometry_sha256": hashes, "source_unselected_objects": "unchanged source geometries, never rewritten",
              "square_geometry_consumers": ["inscribed_square", "square_facing_lobe", "construct"],
              "causal_actual_source_events": 1 if all(checks.values()) else 0,
              "t01_acceptance_event_credit": 0, "owner_acceptance": "PENDING_USER",
              "cursor_review": "NOT_RUN: CHANNEL_UNAVAILABLE", "chatgpt_desk_audit": "NOT_RUN",
              "limitations": ["Provisional 1.5x radius ceiling and axis-aligned lobe removal, not qualified sizing or an EDIT recipe.",
                              "Selected pair is growth-eligible only in this isolated experiment; frozen T01 round-priority policy is not qualified by it.",
                              "Native parsed geometry only; no KiCad/Gerber export, electrical net or manufacturing qualification.",
                              "One pair does not satisfy the unchanged three-event T01 objective."]}
    dump(OUT/"report.json", report)
    context = unary_union([row["geometry"] for row in obs_b
                           if row["source_id"] != a["source_id"]])
    published = gallery(a, b, live, no_add, no_square, context, report)
    for relative in ("src/crop_square_neighbor_experiment.py", "src/native_inventory.py",
                     "tools/run_crop_square_neighbor_experiment.py",
                     "tools/audit_crop_square_neighbor_experiment.py"):
        snapshot = OUT/"review_source"/relative
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT/relative, snapshot)
    files = sorted(path for path in OUT.rglob("*") if path.is_file() and path.name != "SHA256SUMS")
    (OUT/"SHA256SUMS").write_text("".join(f"{sha(path)}  {path.relative_to(ROOT)}\n" for path in files))
    print(json.dumps({"status": report["status"], "checks": checks,
                      "publication_status": "PUBLISHED" if published else "NOT_ESTABLISHED",
                      "check_a_mm2": da, "check_b_mm2": ds,
                      "final_pair_gap_mm": report["a_b_final_copper_gap_mm"],
                      "selected_a": a["center"], "selected_b": b["center"]}, indent=2))
    if not published:
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="A fresh directory under out/; the original review bundle is retained.")
    main(parser.parse_args().output)
