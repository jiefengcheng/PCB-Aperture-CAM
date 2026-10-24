#!/usr/bin/env python3
"""Freeze T01-R1 scope, execute its ORG-only crop, and publish local evidence."""
from __future__ import annotations

import copy
import hashlib
import html
import json
import math
import platform
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from shapely import from_wkb, geos_version_string, to_wkb
from shapely.geometry import Point, Polygon, box
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.crop_dynamic_t01_r1 import (  # noqa: E402
    CONSTRUCTION_BUFFER_MM,
    ERROR_MM,
    GAP_TOLERANCE_MM,
    HARD_GAP_MM,
    MAX_GROWTH_REACH_MM,
    PORT_EXTENSION_MM,
    PORT_LATERAL_MARGIN_MM,
    QUAD_SEGS,
    ROUND_OUTLINE_TOLERANCE_MM,
    V_BOUNDS,
    _filled_circle,
    _prior_disposition,
    run,
)
from src.native_inventory import inventory  # noqa: E402


ORG_REL = Path("dataset/szu-comm_3020301113B_intake_ready_20261021_v2/raw/ORG/top.kicad_pcb")
EXPECTED_ORG_SHA = "850c4c74d55717a721d4bbed7ec876ee086f475efd97f69bb5b5164ef77533a0"
EXPECTED_BASELINE_COMMIT = "ee619a01be1f6b8d4088380b5234f06f7d33fefa"
EXPECTED_FROZEN_T01_SHA = "e8685dfa1a315c0c25ec60c3e0431415e120ccff8819752bf9d7976a46eeab70"
EVIDENCE = ROOT / "out/crop_dynamic_tasks/t01_r1"
INPUTS = EVIDENCE / "input_references"
OLD_EVIDENCE = ROOT / "out/crop_dynamic_tasks/t01"
ZIP_SHA = "70c320a1e3f59a0422faa2ce0e11677da599effd4340f8744940f139ffc115de"
REFERENCE_SHAS = {
    "01_missed_candidates.png": "707c3aa1ae3273b0aeb24657c9cad59bcff0638fde2fb4a0e5ef93fcf07c7a0a",
    "02_growth_and_available_space.png": "834972dde38cd1ce0cdc2bc1213266a7db3b73a907ab394e3e8af90848d25502",
    "03_priority_round_shapes.png": "ff416145af53458e3e65c1c884a34f1936484b4f1aa3898bc46928eeafacfde8",
    "EDIT_owner_crop.png": "ee6711f5157d6782cce1f3fbe59a11b180b47fcb005254266a6b3787e72f8d67",
    "original_scope_ORG_EDIT.png": "cefaa35b2f5ffc13a791c4b3b79b46bae10264572eea40168dea4e3fec851b21",
}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def current_commit() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def old_manifest_audit() -> dict:
    manifest = OLD_EVIDENCE / "SHA256SUMS"
    checks = []
    for line in manifest.read_text().splitlines():
        if not line.strip():
            continue
        expected, rel = line.split("  ", 1)
        path = OLD_EVIDENCE / rel
        observed = sha(path.read_bytes()) if path.is_file() else None
        checks.append({"path": rel, "expected_sha256": expected,
                       "observed_sha256": observed,
                       "status": "PASS" if observed == expected else "MISMATCH_OR_MISSING"})
    return {"manifest_path": str(manifest.relative_to(ROOT)),
            "manifest_sha256": sha(manifest.read_bytes()),
            "checks": checks,
            "status": "PASS" if all(item["status"] == "PASS" for item in checks) else "PRESERVED_BASELINE_HAS_EXISTING_MISMATCH",
            "mismatch_paths": [item["path"] for item in checks if item["status"] != "PASS"]}


def frozen_scope(source: bytes) -> tuple[dict, dict]:
    inv = inventory(source)
    viewport = box(*V_BOUNDS)
    groups = defaultdict(list)
    geometries = {}
    for row in inv["objects"]:
        if "F.Cu" not in row["layers"] or not row["geometry_sha256"] or not _filled_circle(source, row):
            continue
        geometry = from_wkb(inv["payloads"][row["geometry_sha256"]])
        if geometry.intersects(viewport):
            groups[row["geometry_sha256"]].append((row, geometry))
            geometries[row["geometry_sha256"]] = geometry
    occurrences = []
    sites = []
    for geometry_sha, rows in sorted(groups.items(), key=lambda item: min(r[0]["id"] for r in item[1])):
        aliases = sorted(row["id"] for row, _ in rows)
        primary = aliases[0]
        geometry = geometries[geometry_sha]
        diameter = (geometry.bounds[2] - geometry.bounds[0] +
                    geometry.bounds[3] - geometry.bounds[1]) / 2
        sites.append({"site_id": primary, "source_ids": aliases,
                      "geometry_sha256": geometry_sha,
                      "center_mm": [geometry.centroid.x, geometry.centroid.y],
                      "diameter_mm": diameter,
                      "intersects_fixed_viewport": True,
                      "full_geometry_bounds_mm": list(geometry.bounds)})
        for row, _ in sorted(rows, key=lambda pair: pair[0]["id"]):
            occurrences.append({"source_id": row["id"], "source_span": row["source_span"],
                "source_revision_sha256": inv["source_sha256"],
                "geometry_sha256": row["geometry_sha256"],
                "prior_disposition": _prior_disposition(row["id"], geometry)})
    return inv, {"target_occurrence_count": len(occurrences),
                 "unique_geometry_site_count": len(sites),
                 "target_occurrences": occurrences,
                 "target_sites": sites,
                 "viewport_mm": list(V_BOUNDS),
                 "selection_rule": "all supported filled F.Cu gr_circle source geometries intersecting fixed viewport V; no minimum diameter threshold and no inset write window"}


def source_copper(inv: dict, view):
    shapes = []
    for row in inv["objects"]:
        if "F.Cu" not in row["layers"] or not row["geometry_sha256"]:
            continue
        geometry = from_wkb(inv["payloads"][row["geometry_sha256"]])
        if geometry.intersects(view):
            shapes.append(geometry.intersection(view))
    return unary_union(shapes) if shapes else view.difference(view)


def polygon_path(geometry, bounds, scale):
    minx, miny, _, _ = bounds
    if geometry.is_empty:
        return ""
    if geometry.geom_type == "Polygon":
        polygons = [geometry]
    elif geometry.geom_type in ("MultiPolygon", "GeometryCollection"):
        polygons = [part for part in geometry.geoms if part.geom_type == "Polygon"]
    else:
        return ""
    commands = []
    for polygon in polygons:
        for ring in [polygon.exterior, *polygon.interiors]:
            coords = list(ring.coords)
            if not coords:
                continue
            commands.append(f"M {(coords[0][0]-minx)*scale:.3f} {(coords[0][1]-miny)*scale:.3f}")
            commands.extend(f"L {(x-minx)*scale:.3f} {(y-miny)*scale:.3f}" for x, y, *_ in coords[1:])
            commands.append("Z")
    return " ".join(commands)


def svg_header(bounds, scale, title):
    minx, miny, maxx, maxy = bounds
    width, height = (maxx-minx)*scale, (maxy-miny)*scale
    return [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}" height="{height:.0f}" viewBox="0 0 {width:.3f} {height:.3f}">',
        '<rect width="100%" height="100%" fill="#101820"/>']


def svg_title(parts, bounds, scale, title):
    width = (bounds[2] - bounds[0]) * scale
    safe_title = html.escape(title)
    parts.extend([f'<rect x="0" y="0" width="{width:.3f}" height="34" fill="#101820" opacity="0.96"/>',
        f'<text x="10" y="23" fill="white" font-family="sans-serif" font-size="13">{safe_title}</text>'])


def svg_source_only(inv, view, out_path: Path, title: str, scale=500):
    bounds = list(view.bounds)
    parts = svg_header(bounds, scale, title)
    copper = source_copper(inv, view)
    path = polygon_path(copper, bounds, scale)
    if path:
        parts.append(f'<path d="{path}" fill="#d62537" fill-rule="evenodd"/>')
    svg_title(parts, bounds, scale, title)
    parts.append("</svg>")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(parts) + "\n")


def svg_effective(inv, view, candidates: dict, out_path: Path, title: str, scale=500):
    bounds = list(view.bounds)
    parts = svg_header(bounds, scale, title)
    base = source_copper(inv, view)
    final_parts = [base] + [geom.intersection(view) for geom in candidates.values() if geom.intersects(view)]
    effective = unary_union(final_parts)
    path = polygon_path(effective, bounds, scale)
    if path:
        parts.append(f'<path d="{path}" fill="#d62537" fill-rule="evenodd"/>')
    svg_title(parts, bounds, scale, title)
    parts.append("</svg>")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(parts) + "\n")


def svg_overlay(inv, view, candidates: dict, cores: dict, out_path: Path, title: str,
                priorities: dict | None = None, scale=500):
    bounds = list(view.bounds)
    parts = svg_header(bounds, scale, title)
    base = source_copper(inv, view)
    path = polygon_path(base, bounds, scale)
    if path:
        parts.append(f'<path d="{path}" fill="#b62435" fill-rule="evenodd" opacity="0.92"/>')
    additions = [geom.difference(cores[key]).intersection(view)
                 for key, geom in candidates.items() if key in cores and geom.intersects(view)]
    add_union = unary_union([g for g in additions if not g.is_empty]) if any(not g.is_empty for g in additions) else view.difference(view)
    path = polygon_path(add_union, bounds, scale)
    if path:
        parts.append(f'<path d="{path}" fill="#36d993" fill-rule="evenodd" opacity="0.95"/>')
    if priorities:
        for source_id in priorities.values():
            core = cores[source_id]
            if not core.intersects(view):
                continue
            minx, miny, _, _ = bounds
            x = (core.centroid.x - minx) * scale
            y = (core.centroid.y - miny) * scale
            radius = (core.bounds[2] - core.bounds[0]) * scale / 2
            parts.append(f'<circle cx="{x:.3f}" cy="{y:.3f}" r="{radius:.3f}" fill="none" stroke="#ffd166" stroke-width="3"/>')
    svg_title(parts, bounds, scale, title)
    parts.append("</svg>")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(parts) + "\n")


def rasterize_svg(svg_path: Path, requested_size=2048):
    """Rasterize with sips so the SVG's declared aspect ratio is preserved."""
    png_path = svg_path.with_suffix(".png")
    command = ["/usr/bin/sips", "-s", "format", "png", str(svg_path), "--out", str(png_path)]
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    if completed.returncode != 0 or not png_path.is_file():
        raise RuntimeError(f"SVG_RASTERIZATION_FAILED:{svg_path}:{completed.stderr}:{completed.stdout}")
    return {"renderer": "/usr/bin/sips", "command": command,
            "png_path": str(png_path.relative_to(ROOT)),
            "png_sha256": sha(png_path.read_bytes())}


def render_main_bundle(source_inv, run_result, receipt, output_dir):
    view = box(*V_BOUNDS)
    source_copper_geom = source_copper(source_inv, view)
    old_receipt = json.loads((OLD_EVIDENCE / "t01_run.json").read_text())
    old_shapes = {}
    old_cores = {}
    all_source_rows = {row["id"]: row for row in source_inv["objects"]}
    for decision in old_receipt["run"]["decisions"]:
        data = (ROOT / decision["geometry_artifact"]).read_bytes()
        if sha(data) != decision["geometry_sha256"]:
            raise ValueError(f"OLD_T01_GEOMETRY_HASH_MISMATCH:{decision['source_id']}")
        old_shapes[decision["source_id"]] = from_wkb(data)
        row = all_source_rows[decision["source_id"]]
        old_cores[decision["source_id"]] = from_wkb(source_inv["payloads"][row["geometry_sha256"]])

    new_shapes = {}
    new_cores = {}
    for decision in run_result["decisions"]:
        new_shapes[decision["source_id"]] = from_wkb(receipt["geometry_payloads"][decision["source_id"]])
        source_row = all_source_rows[decision["source_id"]]
        new_cores[decision["source_id"]] = from_wkb(source_inv["payloads"][source_row["geometry_sha256"]])
    paths = []
    for name, title, candidates in (
        ("01_org_effective_copper.svg", "ORG source copper · effective copper · fixed viewport V", {}),
        ("02_frozen_t01_effective_copper.svg", "Frozen original T01 · effective copper · fixed viewport V", old_shapes),
        ("03_t01_r1_effective_copper.svg", "T01-R1 · effective copper · fixed viewport V", new_shapes),
    ):
        path = output_dir / "full_crop" / name
        if not candidates:
            svg_source_only(source_inv, view, path, title)
        else:
            svg_effective(source_inv, view, candidates, path, title)
        paths.append(rasterize_svg(path))

    overlay_path = output_dir / "full_crop" / "t01_r1_added_copper_overlay.svg"
    svg_overlay(source_inv, view, new_shapes, new_cores, overlay_path,
                "T01-R1 · ORG effective copper red · accepted additions green · priority outline gold",
                run_result["priority_sites_by_component"])
    paths.append(rasterize_svg(overlay_path))

    # Owner issue 1: the full-crop census is the superset of every marked site;
    # every circle occurrence is source-bound in the adjacent candidate ledger.
    coverage_path = output_dir / "owner_issues" / "01_coverage_candidates.svg"
    coverage_path.parent.mkdir(parents=True, exist_ok=True)
    parts = svg_header(list(view.bounds), 500, "All source-bound circular candidates intersecting V · no size/edge exclusion")
    base_path = polygon_path(source_copper_geom, list(view.bounds), 500)
    parts.append(f'<path d="{base_path}" fill="#b62435" fill-rule="evenodd" opacity="0.85"/>')
    from src.crop_dynamic_t01_r1 import _circle_metrics
    for site in run_result["eligible_site_ids"]:
        decision = next(row for row in run_result["decisions"] if row["source_id"] == site)
        x = (decision["center_mm"][0] - V_BOUNDS[0]) * 500
        y = (decision["center_mm"][1] - V_BOUNDS[1]) * 500
        parts.append(f'<circle cx="{x:.3f}" cy="{y:.3f}" r="6" fill="none" stroke="#5ddcff" stroke-width="2"/>')
    svg_title(parts, list(view.bounds), 500,
              "Full supported circular candidate set · cyan = source-bound sites")
    parts.append("</svg>")
    coverage_path.write_text("\n".join(parts) + "\n")
    paths.append(rasterize_svg(coverage_path))

    # Owner issue 2: choose the actual crop event with largest directional
    # spread in radial reach, excluding round priorities and zero-growth sites.
    focus_growth = _choose_space_demo_site(run_result)
    issue2 = output_dir / "owner_issues" / "02_space_responsive_growth.svg"
    bounds = focus_growth["bounds_mm"]
    focus_view = box(*bounds)
    focus_candidates = {focus_growth["source_id"]: new_shapes[focus_growth["source_id"]]}
    focus_cores = {focus_growth["source_id"]: new_cores[focus_growth["source_id"]]}
    svg_overlay(source_inv, focus_view, focus_candidates, focus_cores, issue2,
        f"Space response · added={focus_growth['added_area_mm2']:.3f} mm² · limits={len(focus_growth['limiting_source_ids'])}")
    paths.append(rasterize_svg(issue2))

    # Owner issue 3: show one actual component with a preserved priority and
    # at least one companion where available.
    focus_component = _choose_priority_component(run_result)
    component_id = focus_component["component_id"]
    component_decisions = [row for row in run_result["decisions"]
                           if row["physical_component_id"] == component_id]
    focused_ids = {row["source_id"] for row in component_decisions}
    focused_shapes = {sid: new_shapes[sid] for sid in focused_ids}
    focused_cores = {sid: new_cores[sid] for sid in focused_ids}
    component_bounds = unary_union([new_shapes[sid] for sid in focused_ids]).bounds
    pad = 0.12
    focus_view3 = box(component_bounds[0]-pad, component_bounds[1]-pad,
                      component_bounds[2]+pad, component_bounds[3]+pad)
    issue3 = output_dir / "owner_issues" / "03_component_priority_round_shape.svg"
    svg_overlay(source_inv, focus_view3, focused_shapes, focused_cores, issue3,
        "Priority outline · gold = round anchor · green = companions",
        {component_id: focus_component["source_id"]})
    paths.append(rasterize_svg(issue3))

    write_domain = from_wkb(bytes.fromhex(run_result["write_domain_wkb"]))
    full_write_view = box(*write_domain.bounds)
    edge_path = output_dir / "outside_viewport" / "full_local_write_domain.svg"
    svg_overlay(source_inv, full_write_view, new_shapes, new_cores, edge_path,
        "Full local write envelopes · viewport edge is shown separately in policy metadata",
        run_result["priority_sites_by_component"])
    paths.append(rasterize_svg(edge_path))
    return {"images": paths,
            "space_focus": focus_growth,
            "priority_focus": {"component_id": component_id,
                "priority_source_id": focus_component["source_id"],
                "member_sites": sorted(focused_ids)},
            "source_copper_area_in_view_mm2": source_copper_geom.area}


def _choose_space_demo_site(run_result):
    decisions = [row for row in run_result["decisions"]
                 if row["decision"] == "GROW" and row["added_area_mm2"] > 1e-5]
    if not decisions:
        raise ValueError("NO_REAL_CROP_SPACE_RESPONSIVE_GROWTH_TO_DISPLAY")
    def score(row):
        limits = len(row["limiting_source_ids"])
        return (row["added_area_mm2"], limits, not row["growth_cap_touched"], row["source_id"])
    chosen = max(decisions, key=score)
    center = chosen["center_mm"]
    return {**chosen, "bounds_mm": [center[0]-0.40, center[1]-0.40,
                                     center[0]+0.40, center[1]+0.40]}


def _choose_priority_component(run_result):
    priorities = run_result["priority_sites_by_component"]
    candidates = []
    for component_id, priority_id in priorities.items():
        members = [row for row in run_result["decisions"]
                   if row["physical_component_id"] == component_id]
        companions = [row for row in members if row["source_id"] != priority_id]
        score = max((row["added_area_mm2"] for row in companions), default=0.0)
        candidates.append((score, len(companions), component_id, priority_id))
    if not candidates:
        raise ValueError("NO_COMPONENT_PRIORITY_TO_DISPLAY")
    _, _, component_id, priority_id = max(candidates)
    return {"component_id": component_id, "source_id": priority_id}


def main() -> None:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    source_path = ROOT / ORG_REL
    source = source_path.read_bytes()
    source_sha = sha(source)
    if source_sha != EXPECTED_ORG_SHA:
        raise SystemExit(f"ORG_SOURCE_HASH_MISMATCH:{source_sha}")
    commit = current_commit()
    if commit != EXPECTED_BASELINE_COMMIT:
        raise SystemExit(f"REPORTED_BASELINE_CHANGED:{commit}")
    old_receipt_bytes = (OLD_EVIDENCE / "t01_run.json").read_bytes()
    if sha(old_receipt_bytes) != EXPECTED_FROZEN_T01_SHA:
        raise SystemExit("FROZEN_T01_RECEIPT_HASH_MISMATCH")
    refs = {name: sha((INPUTS / name).read_bytes()) for name in REFERENCE_SHAS}
    if refs != REFERENCE_SHAS:
        raise SystemExit(f"OWNER_REFERENCE_HASH_MISMATCH:{refs}")
    inv, scope = frozen_scope(source)
    if scope["target_occurrence_count"] != 53 or scope["unique_geometry_site_count"] != 51:
        raise SystemExit(f"UNEXPECTED_PRE_RUN_DENOMINATOR:{scope['target_occurrence_count']}:{scope['unique_geometry_site_count']}")
    manifest_audit = old_manifest_audit()
    manifest_paths = manifest_audit["mismatch_paths"]
    if manifest_paths != ["t01_full_crop.png"]:
        raise SystemExit(f"UNEXPECTED_FROZEN_T01_MANIFEST_STATE:{manifest_paths}")

    policy = {
        "schema": "crop-dynamic-t01-r1-policy/1",
        "source_sha256": source_sha,
        "historical_baseline_commit": EXPECTED_BASELINE_COMMIT,
        "historical_frozen_t01_receipt_sha256": EXPECTED_FROZEN_T01_SHA,
        "viewport_mm": list(V_BOUNDS),
        "target_scope": scope,
        "parameters": {"maximum_growth_reach_mm": MAX_GROWTH_REACH_MM,
            "hard_experimental_separation_mm": HARD_GAP_MM,
            "gap_tolerance_mm": GAP_TOLERANCE_MM,
            "construction_buffer_mm": CONSTRUCTION_BUFFER_MM,
            "port_extension_mm": PORT_EXTENSION_MM,
            "port_lateral_margin_mm": PORT_LATERAL_MARGIN_MM,
            "round_outline_tolerance_mm": ROUND_OUTLINE_TOLERANCE_MM,
            "inventory_precision_mm": ERROR_MM,
            "curve_quad_segs": QUAD_SEGS,
            "nominal_construction_buffer_is_not_final_clearance": True,
            "EDIT_used_for_construction": False,
            "smoothing": "none"},
        "implementation_sha256": sha((ROOT / "src/crop_dynamic_t01_r1.py").read_bytes()),
        "handoff_sha256": sha((ROOT / "docs/crop_dynamic_tasks/amendments/T01_R1_20261024/T01_R1_AMENDMENT_HANDOFF.md").read_bytes()),
        "owner_package_sha256": ZIP_SHA,
        "owner_reference_sha256": refs,
        "old_t01_artifact_manifest_audit": manifest_audit,
        "runtime_versions": {"python": platform.python_version(),
            "shapely": __import__("shapely").__version__,
            "geos": geos_version_string},
        "status": "FROZEN_BEFORE_MAIN_RUN",
    }
    policy_path = EVIDENCE / "frozen_policy.json"
    write_json(policy_path, policy)
    policy_sha = sha(policy_path.read_bytes())

    # Main run begins only after the exact target census and shared policy are
    # persisted and hash-bound.
    result = run(source)
    geometry_dir = EVIDENCE / "geometry"
    geometry_dir.mkdir(exist_ok=True)
    geometry_payloads = {}
    for decision in result["decisions"]:
        payload = bytes.fromhex(decision.pop("candidate_wkb"))
        artifact = geometry_dir / f"dynamic_{sha(decision['source_id'].encode())[:20]}.wkb"
        artifact.write_bytes(payload)
        decision["geometry_artifact"] = str(artifact.relative_to(ROOT))
        decision["geometry_artifact_sha256"] = sha(payload)
        geometry_payloads[decision["source_id"]] = payload
    for decision in result["static_baseline"]["decisions"]:
        payload = bytes.fromhex(decision.pop("candidate_wkb"))
        artifact = geometry_dir / f"static_{sha(decision['source_id'].encode())[:20]}.wkb"
        artifact.write_bytes(payload)
        decision["geometry_artifact"] = str(artifact.relative_to(ROOT))
        decision["geometry_artifact_sha256"] = sha(payload)
    # Replace generic owner-locator notes with a complete source-bound superset
    # assertion: all marked sites in the fixed viewport are in the candidate set.
    for row in result["target_occurrences"]:
        row["owner_locator_regions"] = ["01_missed_candidates: fixed-viewport full-circle superset"]
        row["note"] = "Candidate identity comes from pinned ORG source revision and full geometry intersection with V; screenshot pixels were used only to define the fixed review viewport."
    result["contract_sha256"] = policy_sha
    result["geometry_payloads"] = {key: value.hex() for key, value in geometry_payloads.items()}
    result["created_utc"] = datetime.now(timezone.utc).isoformat()
    receipt = {"schema": "crop-dynamic-t01-r1-receipt/1",
        "policy_path": str(policy_path.relative_to(ROOT)),
        "policy_sha256": policy_sha,
        "source_path": str(ORG_REL),
        "source_sha256": source_sha,
        "run": result,
        "status": {"task_execution": "COMPLETE", "technical_checks": "PENDING"}}
    # Do not carry WKB hex in the durable receipt; the files have explicit hashes.
    result["geometry_payloads"] = {key: sha(value) for key, value in geometry_payloads.items()}
    write_json(EVIDENCE / "t01_r1_run.json", receipt)

    source_inv = inventory(source)
    render = render_main_bundle(source_inv, result, {"geometry_payloads": {k: v.hex() for k, v in geometry_payloads.items()}}, EVIDENCE)
    write_json(EVIDENCE / "render_receipt.json", render)

    # Machine-readable candidate map with every source occurrence and all
    # disposition reasons, including exact prior 39/7/7 categories.
    write_json(EVIDENCE / "selection_and_priority_map.json", {
        "schema": "crop-dynamic-t01-r1-selection-map/1",
        "source_sha256": source_sha,
        "policy_sha256": policy_sha,
        "target_occurrences": result["target_occurrences"],
        "priority_sites_by_component": result["priority_sites_by_component"],
        "priority_exceptions": result["priority_exceptions"],
        "decisions": [{key: value for key, value in decision.items() if key not in ("component_source_member_ids",)}
                      for decision in result["decisions"]],
        "mapping_rule": "source spans and geometry hashes bind every ORG occurrence; exact co-located geometry aliases share one constructed site; this is physical geometry evidence, not pad/net identity"})

    report = build_report(result, policy_sha, render, manifest_audit)
    (EVIDENCE / "t01_r1_report.md").write_text(report)
    write_json(EVIDENCE / "owner_issue_site_details.json",
        build_owner_site_details(result, geometry_payloads, source_inv))
    create_results_manifest()
    print(json.dumps({"status": "RUN_COMPLETE_TECHNICAL_CHECKS_PENDING",
        "policy_sha256": policy_sha,
        "occurrences": result["target_occurrence_count"], "sites": result["target_site_count"],
        "components": len(result["priority_sites_by_component"]),
        "dynamic_events": result["dynamic_adaptation_event_count"],
        "space_control": result["same_seed_space_control"],
        "size_order": result["smaller_roomier_vs_larger_crowded"],
        "dynamic_gap_violations": len(result["dynamic_hard_gap_violations"]),
        "priority_failures": sum(row["status"] != "ROUND_OUTLINE_PRESERVED" for row in result["priority_outline_checks"]),
        "evidence_dir": str(EVIDENCE)}, indent=2))


def build_report(result, policy_sha, render, manifest_audit):
    count_by_disposition = Counter(row["prior_disposition"] for row in result["target_occurrences"])
    count_by_decision = Counter(row["decision"] for row in result["decisions"])
    return "\n".join([
        "# T01-R1 crop run",
        "",
        f"- Status: `RUN COMPLETE; TECHNICAL VERIFICATION PENDING`",
        f"- ORG SHA-256: `{result['source_sha256']}`",
        f"- Frozen policy SHA-256: `{policy_sha}` (persisted before the main run)",
        f"- Viewport V remains fixed at `{tuple(result['viewport_mm'])}` mm.",
        f"- Full source-bound target scope: {result['target_occurrence_count']} circular occurrences, {result['target_site_count']} unique geometries; {len(result['priority_sites_by_component'])} complete ORG physical components receive a round priority.",
        f"- Previous dispositions in the new denominator: `{dict(count_by_disposition)}`.",
        f"- New decisions: `{dict(count_by_decision)}`; no target is excluded solely by diameter or display-edge crossing.",
        f"- W' is the union of each complete source circle's 0.20 mm local growth envelope; H' extends each by 0.025 mm construction allowance plus 0.00001 mm inventory precision. No viewport-clipped writing.",
        f"- Construction buffer: 0.025 mm; experimental hard separation remains 0.020 mm with 0.00001 mm tolerance. The buffer is not a final-clearance claim.",
        f"- Dynamic neighbor adaptations: {result['dynamic_adaptation_event_count']}; controlled single-neighbor counterfactuals: {len(result['controlled_counterfactuals'])}.",
        f"- Same-seed open/crowded control: `{result['same_seed_space_control']['status']}`.",
        f"- Smaller-roomier/larger-crowded real-crop relation: `{result['smaller_roomier_vs_larger_crowded']['status']}`.",
        f"- Minimum raw dynamic optional gap: `{result['minimum_dynamic_optional_gap_mm']}` mm, pair `{result['minimum_dynamic_gap_pair_source_ids']}`; violations: {len(result['dynamic_hard_gap_violations'])}.",
        f"- Explicit source-existing attachment-port contact violations outside the bounded port zones: {len(result['attached_trace_port_violations'])}.",
        f"- Growth touched the shared reach cap at {sum(row['growth_cap_touched'] for row in result['decisions'])} sites; was limited by the cap alone at {sum(row['growth_cap_only_limiter'] for row in result['decisions'])} sites.",
        f"- Priority outline failures: {sum(row['status'] != 'ROUND_OUTLINE_PRESERVED' for row in result['priority_outline_checks'])}; exceptions: {len(result['priority_exceptions'])}.",
        f"- Fair static comparison uses the same source sites, priorities, ports, gap buffers, reach, schedule and geometry kernel; only evolving-neighbor updates are disabled.",
        f"- Existing T01 geometry/WKB manifest: {sum(r['status']=='PASS' for r in manifest_audit['checks'])}/{len(manifest_audit['checks'])} entries match; preserved mismatch: `{manifest_audit['mismatch_paths']}`. This run rebuilds frozen T01 from its verified source geometry artifacts, not the mismatched PNG.",
        f"- Shared source parser/kernel: `{result['shared_parser_and_kernel_qualification']}`",
        "- No electrical net intent, engineering/manufacturing approval, expert-equivalence, or T02–T07 work is claimed.",
        "",
        "## Evidence artifacts",
        "",
        *[f"- `{image['png_path']}` (SHA-256 `{image['png_sha256']}`)" for image in render["images"]],
        "- `selection_and_priority_map.json` binds every occurrence, decision, component, priority and limitation.",
        "- `owner_issue_site_details.json` reports every occurrence/site, added area, radius, directional added area, actual limiting source objects and attachment ports.",
        "- `t01_r1_run.json` and source-keyed WKB artifacts bind the evolving and fair static scenes.",
        "",
    ])


def build_owner_site_details(result, geometry_payloads, source_inv):
    """Describe every source-bound circle, including eight-way local growth."""
    rows = []
    for index, decision in enumerate(result["decisions"], start=1):
        candidate = from_wkb(geometry_payloads[decision["source_id"]])
        # Recover the immutable source core from its run-bound source payload.
        source_row = next(row for row in source_inv["objects"]
                          if row["id"] == decision["source_id"])
        core = from_wkb(source_inv["payloads"][source_row["geometry_sha256"]])
        growth = candidate.difference(core)
        cx, cy = decision["center_mm"]
        reach = MAX_GROWTH_REACH_MM + decision["original_radius_mm"] + CONSTRUCTION_BUFFER_MM
        directional = []
        for sector in range(8):
            start = sector * 45.0
            points = [(cx, cy)] + [(cx + reach * math.cos(math.radians(start + j * 45 / 24)),
                                     cy + reach * math.sin(math.radians(start + j * 45 / 24)))
                                    for j in range(25)]
            wedge = Polygon(points)
            directional.append({"sector_start_degrees": start,
                                "added_area_mm2": growth.intersection(wedge).area})
        rows.append({"review_label": f"C{index:02d}",
            "source_id": decision["source_id"],
            "source_occurrence_ids": decision["source_occurrence_ids"],
            "source_span_by_id": decision["source_span_by_id"],
            "source_sha256": decision["source_sha256"],
            "geometry_sha256": decision["geometry_sha256"],
            "physical_component_id": decision["physical_component_id"],
            "component_member_count": decision["component_member_count"],
            "priority_site_id": decision["priority_site_id"],
            "center_mm": decision["center_mm"],
            "original_radius_mm": decision["original_radius_mm"],
            "original_area_mm2": decision["original_area_mm2"],
            "final_effective_area_mm2": decision["final_effective_area_mm2"],
            "added_area_mm2": decision["added_area_mm2"],
            "candidate_radius_max_mm": decision["candidate_radius_max_mm"],
            "maximum_growth_reach_mm": decision["maximum_growth_reach_mm"],
            "growth_cap_touched": decision["growth_cap_touched"],
            "growth_cap_only_limiter": decision["growth_cap_only_limiter"],
            "limiting_obstacles": decision["limiting_obstacles"],
            "attachment_port_trace_ids": decision["attachment_port_trace_ids"],
            "directional_added_area": directional,
            "decision": decision["decision"]})
    return {"schema": "crop-dynamic-t01-r1-owner-site-details/1",
            "source_sha256": result["source_sha256"],
            "viewport_mm": result["viewport_mm"],
            "site_count": len(rows), "occurrence_count": result["target_occurrence_count"],
            "direction_bins": "8 equal 45-degree sectors from ORG +X, positive Y-down coordinates",
            "sites": rows}


def create_results_manifest():
    files = sorted(path for path in EVIDENCE.rglob("*") if path.is_file()
                   and path.name != "SHA256SUMS")
    (EVIDENCE / "SHA256SUMS").write_text("".join(
        f"{sha(path.read_bytes())}  {path.relative_to(EVIDENCE).as_posix()}\n" for path in files))


if __name__ == "__main__":
    main()
