"""Actual-geometry T02 owner review: full crop, marked close-ups and latent circles."""
from collections import Counter
import hashlib
import html
import json
import math
from pathlib import Path

from shapely import STRtree, wkb
from shapely.geometry import Point, box
from shapely.ops import nearest_points, unary_union

from src.org_edit_target_map import _inventory_side, _row_geometry, _svg_path
from tools.finalize_crop_rect_t02 import target_details_html

ROOT = Path(__file__).resolve().parents[1]
PALETTE = ["#ffb454", "#48c9b0", "#dba4ff", "#82baff", "#f97884", "#d6db70", "#ffa2d4"]

# Pixel frame of the owner screenshot's full-crop image, measured from the
# screenshot stored beside this run. Image Y is top-down; scene Y is upward.
OWNER_SCREENSHOT_IMAGE_FRAME_PX = (20.0, 139.0, 1158.0, 977.0)


def screenshot_pixel_to_scene(px, py, scene_bounds,
                              image_frame=OWNER_SCREENSHOT_IMAGE_FRAME_PX):
    """Map an approximate owner screenshot pixel into native crop coordinates.

    This locator is visualization-only: it never participates in geometry
    construction or acceptance. The Y transform is inverted because raster
    screenshot pixels increase downward while the scene coordinate frame does
    not.
    """
    x0, y0, x1, y1 = scene_bounds
    left, top, right, bottom = image_frame
    if right <= left or bottom <= top:
        raise ValueError("INVALID_OWNER_SCREENSHOT_FRAME")
    x = x0 + (float(px) - left) / (right - left) * (x1 - x0)
    y = y1 - (float(py) - top) / (bottom - top) * (y1 - y0)
    return x, y


def sha(data):
    return hashlib.sha256(data).hexdigest()


def review_relative_link(run, target):
    """Return a local page-relative path to a review artifact."""
    import os
    return Path(os.path.relpath(target, run)).as_posix()


def marked_location_issue_html(locations, issues, rect_ids):
    """Cross-reference approximate owner windows to source-bound review points."""
    rows = []
    for location in locations:
        x0, y0, x1, y1 = location["bounds_mm"]
        inside = [issue for issue in issues
                  if issue.get("review_point_mm")
                  and x0 <= issue["review_point_mm"][0] <= x1
                  and y0 <= issue["review_point_mm"][1] <= y1]
        if inside:
            for issue in inside:
                gap = issue.get("final_surface_gap_mm")
                gap_text = "not measured" if gap is None else f"{gap:.6f}"
                rows.append(
                    f'<tr><td>{html.escape(location["id"])}</td>'
                    f'<td>{html.escape(issue["review_id"])}</td>'
                    f'<td>{rect_ids[issue["rectangle_source_id"]]}</td>'
                    f'<td>{html.escape(issue["issue_type"])}</td>'
                    f'<td>{gap_text}</td><td>Open · point inside approximate window</td></tr>')
            continue

        def distance_to_window(issue):
            px, py = issue["review_point_mm"]
            dx = max(x0 - px, 0.0, px - x1)
            dy = max(y0 - py, 0.0, py - y1)
            return math.hypot(dx, dy)

        nearest = min((issue for issue in issues if issue.get("review_point_mm")),
                      key=distance_to_window, default=None)
        if nearest is None:
            rows.append(f'<tr><td>{html.escape(location["id"])}</td><td colspan="5">No source-bound review point found.</td></tr>')
        else:
            gap = nearest.get("final_surface_gap_mm")
            gap_text = "not measured" if gap is None else f"{gap:.6f}"
            rows.append(
                f'<tr><td>{html.escape(location["id"])}</td>'
                f'<td>{html.escape(nearest["review_id"])}</td>'
                f'<td>{rect_ids[nearest["rectangle_source_id"]]}</td>'
                f'<td>{html.escape(nearest["issue_type"])}</td>'
                f'<td>{gap_text}</td>'
                f'<td>No point inside; nearest is {distance_to_window(nearest):.3f} mm outside window</td></tr>')
    return ('<p class="small">Locator cross-reference: ledger points inside each approximate screenshot window are listed below. '
            'Attachment-extension records describe pre-existing contacts, not side-gap passes. A locator match is not a construction input.</p>'
            '<div class="scroll"><table><tr><th>Mark</th><th>Issue</th><th>Rectangle</th><th>Ledger classification</th>'
            '<th>Final surface gap mm</th><th>Locator relationship</th></tr>' + ''.join(rows) + '</table></div>')


def marked_surface_findings_html(locations, decisions, rows, geometries, candidates,
                                 trace_geometries, rect_ids, audit_dir, policy):
    """Show direct copper gaps beside each marked window, separate from corner minima."""
    checks = json.loads((audit_dir / "side_gap_checks.json").read_bytes()) if audit_dir else []
    check_by_pair = {(x["rectangle_source_id"], x["trace_source_id"]): x for x in checks}
    decisions_by_id = {x["source_id"]: x for x in decisions}
    tree_ids = sorted(trace_geometries)
    tree = STRtree([trace_geometries[sid] for sid in tree_ids]) if tree_ids else None
    tolerance = float(policy["geometry_tolerance_mm"])
    construction = float(policy["construction_gap_mm"])
    out = []
    for location in locations:
        window = box(*location["bounds_mm"])
        selected = []
        for rect_id, candidate in candidates.items():
            if not candidate.intersects(window):
                continue
            core = geometries[rect_id]
            decision = decisions_by_id[rect_id]
            reservations = {x["source_id"]: x for x in decision.get("trace_gap_reservations", [])}
            issue_by_trace = {x["trace_source_id"]: x for x in decision.get("future_trace_clearance_work_items", [])}
            query = candidate.buffer(construction + tolerance)
            if tree is None:
                continue
            for index in tree.query(query):
                trace_id = tree_ids[int(index)]
                trace = trace_geometries[trace_id]
                final_gap = candidate.distance(trace)
                if final_gap > construction + tolerance:
                    continue
                original_gap = core.distance(trace)
                # Existing source attachments are listed in the separate
                # attachment ledger and are not presented as clearance passes.
                if original_gap <= 1e-10:
                    continue
                reservation = reservations.get(trace_id, {})
                side_check = check_by_pair.get((rect_id, trace_id), {})
                issue = issue_by_trace.get(trace_id, {})
                basis = reservation.get("constraint_basis", "UNCLASSIFIED_CLOSE_PAIR")
                if basis == "SIDE_SURFACE_GAP":
                    state = ("SIDE GAP MEETS 0.020020 mm" if
                             float(side_check.get("new_growth_gap_mm") or final_gap) + 1e-12 >= construction
                             else "SIDE GAP DEFECT · OPEN")
                elif issue:
                    state = "OPEN · " + issue["issue_type"]
                else:
                    state = "OPEN · CORNER / ENDPOINT REVIEW"
                side_gap = side_check.get("final_surface_gap_mm")
                selected.append({
                    "rectangle_id": rect_ids[rect_id],
                    "rectangle_span": rows[rect_id]["source_span"],
                    "trace_span": rows[trace_id]["source_span"],
                    "trace_kind": rows[trace_id]["kind"],
                    "original_gap": original_gap,
                    "final_gap": final_gap,
                    "side_gap": side_gap,
                    "side_labels": reservation.get("side_labels", side_check.get("side_labels", [])),
                    "basis": basis,
                    "state": state,
                })
        selected.sort(key=lambda x: (x["final_gap"], x["rectangle_span"], x["trace_span"]))
        if selected:
            body_rows = []
            for x in selected:
                side_gap_text = ("not side-classified" if x["side_gap"] is None
                                 else f'{x["side_gap"]:.6f} mm')
                body_rows.append(
                    f'<tr><td>{x["rectangle_id"]} · {x["rectangle_span"][0]}–{x["rectangle_span"][1]}</td>'
                    f'<td>{x["trace_kind"]} · {x["trace_span"][0]}–{x["trace_span"][1]}</td>'
                    f'<td>{x["original_gap"]:.6f} → {x["final_gap"]:.6f}</td>'
                    f'<td>{html.escape(x["basis"])} · {html.escape(", ".join(x["side_labels"]) or "no side")}</td>'
                    f'<td>{side_gap_text}</td><td>{html.escape(x["state"])}</td></tr>')
            body = "".join(body_rows)
        else:
            body = '<tr><td colspan="6">No disconnected trace pair within the construction target in this marked window.</td></tr>'
        out.append(f'<h3>{html.escape(location["id"])} · source-bound close pairs</h3>'
                   '<div class="scroll"><table><tr><th>Rectangle source span</th><th>Trace source span</th>'
                   '<th>Original → final copper gap mm</th><th>Constraint basis</th><th>Side-region gap mm</th>'
                   f'<th>Finding</th></tr>{body}</table></div>')
    return ('<p class="small">These rows measure actual copper-to-copper distance. A small nearest-corner gap is shown separately from a side-region gap; corner findings remain OPEN and cannot waive a side requirement. Original attachments are reported in the attachment ledger.</p>' + ''.join(out))


def future_trace_width_reservation_html(doc):
    """Render an owner-marked width-reservation issue without inventing a target."""
    if doc.get("status") != "OPEN_UNQUALIFIED_FUTURE_TRACE_WIDTH_RESERVATION":
        raise ValueError("T02_FUTURE_TRACE_WIDTH_RESERVATION_NOT_OPEN")
    gap = float(doc["final_surface_gap_mm"])
    hard = float(doc["hard_experimental_gap_mm"])
    width = float(doc["trace_width_mm"])
    fixed_route = float(doc["maximum_symmetric_trace_width_increase_with_route_fixed_from_this_side_only_mm"])
    if doc.get("trace_width_must_not_shrink") is not True or doc.get("future_trace_width_target_mm") is not None:
        raise ValueError("T02_FUTURE_TRACE_WIDTH_TARGET_OR_NO_SHRINK_CONTRACT_MISMATCH")
    return (f'<aside class="notice"><b>{html.escape(doc["rectangle_review_id"])} · future trace-width reservation OPEN</b>'
            f'<p>Saved rectangle-to-trace copper gap: {gap:.12f} mm; hard minimum: {hard:.6f} mm '
            f'(margin {gap-hard:.12f} mm). The adjacent trace is {width:.6f} mm wide. '
            f'With the current route fixed, this side allows only {fixed_route:.9f} mm of symmetric width increase '
            f'before reaching the hard floor.</p>'
            f'<p>This planning note is separate from the 135 clearance/attachment ledger items; R67 currently '
            f'meets the stated hard floor and is not classified here as a sub-minimum gap. The trace must not '
            f'shrink, and no future width target is specified. The opposite-side cross-section calculation is '
            f'only a local geometric bound; it does not establish a feasible connected reroute. Any later route '
            f'change must preserve original connectivity and attachments and verify clearance along the full route. '
            f'This remains an OPEN planning item, not a clearance or route-feasibility pass.</p>'
            f'<p><a href="M1_gap_measured.svg">Measured gap view</a> · '
            f'<a href="M1_gap_and_local_corridor.svg">Local corridor view</a> · '
            f'<a href="future_trace_width_reservation.json">Source-bound reservation record</a></p></aside>')


def render_review(run, audit):
    result = json.loads((run / "t02_result.json").read_bytes())
    decisions_doc = json.loads((run / "t02_decisions.json").read_bytes())
    decisions = decisions_doc["decisions"]
    policy = json.loads((run / "t02_policy.json").read_bytes())
    embedded = json.loads((run / "embedded_covered_circles.json").read_bytes())
    ledger = json.loads((run / "future_trace_work_items.json").read_bytes())
    width_reservation_path = run / "future_trace_width_reservation.json"
    width_reservation_doc = (json.loads(width_reservation_path.read_bytes())
                             if width_reservation_path.exists() else None)
    rule_mode = policy.get("trace_interactions", {}).get("rule_mode", "unknown")
    width_reservation_html = (future_trace_width_reservation_html(width_reservation_doc)
                              if width_reservation_doc and rule_mode != "surface_side_priority_v15" else "")
    audit_doc = json.loads((audit / "audit.json").read_bytes()) if audit else {}
    if rule_mode != "surface_side_priority_v15":
        raise ValueError("T02_REVIEW_RENDER_REQUIRES_SURFACE_GAP_POLICY_V15")
    raw = (ROOT / policy["source"]).read_bytes()
    inv = _inventory_side(raw, sha(raw))
    rows = {r["id"]: r for r in inv["rows"] if "F.Cu" in r.get("layers", [])}
    geometries = {sid: _row_geometry(r, inv["payloads"]) for sid, r in rows.items()}
    full_bounds = result["crop_bounds_mm"]
    crop = box(*full_bounds)
    org = unary_union([g.intersection(crop) for g in geometries.values() if g.intersects(crop)])
    combined = wkb.loads((run / "t01_accepted_plus_t02.wkb").read_bytes())
    add = wkb.loads((run / "t02_additions.wkb").read_bytes())
    old = wkb.loads((ROOT / "out/crop_dynamic_tasks/t02_rectangles_crop_20261025_v31/t01_accepted_plus_t02.wkb").read_bytes())
    candidates = {d["source_id"]: wkb.loads((run / "t02_candidates" / (sha(d["source_id"].encode()) + ".wkb")).read_bytes()) for d in decisions}
    trace_geometries = {sid: geometries[sid] for sid, row in rows.items()
                        if row.get("kind") in policy.get("trace_interactions", {}).get("trace_source_kinds", [])}
    rect_ids = {d["source_id"]: f"R{i:02d}" for i, d in enumerate(decisions, 1)}
    circle_ids = {d["source_id"]: f"C{i:02d}" for i, d in enumerate(embedded["records"], 1)}

    def svg(name, bounds, layers, circles=(), markers=(), labels=()):
        x0, y0, x1, y1 = bounds
        factor = 300
        bits = []
        for geometry, fill, stroke, width, opacity in layers:
            bits.append(f'<path d="{_svg_path(geometry, x0, y0, factor)}" fill="{fill}" stroke="{stroke}" stroke-width="{width}" opacity="{opacity}" fill-rule="evenodd"/>')
        for geometry, color, dash in circles:
            bits.append(f'<path d="{_svg_path(geometry, x0, y0, factor)}" fill="none" stroke="{color}" stroke-width="1.5" stroke-dasharray="{dash}"/>')
        for point, label, color in markers:
            x, y = (point[0]-x0)*factor, (point[1]-y0)*factor
            bits.append(f'<circle cx="{x}" cy="{y}" r="8" fill="{color}" stroke="#071522" stroke-width="2"/><text x="{x+10}" y="{y-8}" fill="white" stroke="#071522" stroke-width="3" paint-order="stroke" font-family="system-ui" font-size="15">{html.escape(label)}</text>')
        for point, label in labels:
            x, y = (point[0]-x0)*factor, (point[1]-y0)*factor
            bits.append(f'<text x="{x}" y="{y}" text-anchor="middle" fill="white" stroke="#071522" stroke-width="3" paint-order="stroke" font-size="16" font-family="system-ui">{html.escape(label)}</text>')
        width, height = (x1-x0)*factor, (y1-y0)*factor
        (run / name).write_text(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" style="overflow:hidden;background:#071522"><defs><clipPath id="frame"><rect width="{width}" height="{height}"/></clipPath></defs><rect width="{width}" height="{height}" fill="#071522"/><g clip-path="url(#frame)">{"".join(bits)}</g></svg>')

    red = (combined, "#e9485b", "none", 0, 1)
    svg("rejected_v31.svg", full_bounds, [(old, "#e9485b", "none", 0, 1)])
    svg("growth_overlay.svg", full_bounds, [(combined, "#e9485b", "none", 0, .5), (add, "#35d4b7", "none", 0, 1)])
    svg("target_ids.svg", full_bounds, [red], labels=[(candidates[sid].centroid.coords[0], rid) for sid, rid in rect_ids.items()])
    circle_outlines = []
    for row in embedded["records"]:
        sid = row["source_id"]
        selected = wkb.loads((run / "t02_embedded_circles" / (sha(sid.encode()) + ".wkb")).read_bytes())
        circle_outlines.append((selected, "#ffd166", ""))
    svg("covered_overlay.svg", full_bounds, [red], circles=circle_outlines,
        labels=[(row["center_mm"], circle_ids[row["source_id"]]) for row in embedded["records"]])

    issues = []
    for i, issue in enumerate(sorted(ledger["clearance_issues"], key=lambda x: (x["issue_type"], x["rectangle_source_id"], x["trace_source_id"])), 1):
        candidate = candidates[issue["rectangle_source_id"]]
        pa, pb = nearest_points(candidate, geometries[issue["trace_source_id"]])
        point = ((pa.x+pb.x)/2, (pa.y+pb.y)/2)
        issues.append({**issue, "review_id": f"I{i:03d}", "review_point_mm": point})
    action_issues = [x for x in issues if x["issue_type"] != "EXISTING_ATTACHMENT_EXTENSION_REVIEW"]
    svg("issues_overlay.svg", full_bounds, [red], markers=[(x["review_point_mm"], x["review_id"], "#ffbb33") for x in action_issues])
    if audit and (audit / "attachment_port_witnesses.json").exists():
        ports = json.loads((audit / "attachment_port_witnesses.json").read_bytes())
        port_regions = [wkb.loads((audit / p["exemption_geometry_file"]).read_bytes()) for p in ports]
        protected_regions = [wkb.loads((audit / p["protected_side_geometry_file"]).read_bytes()) for p in ports]
        svg("attachment_ports.svg", full_bounds, [red,
            (unary_union(port_regions), "#ffd166", "none", 0, .4),
            (unary_union(protected_regions), "#65b5ff", "none", 0, .95)])
    membership = json.loads((run / "physical_component_membership.json").read_bytes())
    comp_parts = []
    for i, (cid, member_ids) in enumerate(sorted(membership["component_members"].items())):
        region = unary_union([geometries[s] for s in member_ids if geometries[s].intersects(crop)] +
                             [candidates[s] for s in member_ids if s in candidates])
        if not region.is_empty:
            comp_parts.append((region, PALETTE[i % len(PALETTE)], "none", 0, 1))
    svg("physical_components.svg", full_bounds, comp_parts)

    # Screenshot coordinates locate review panels only. They never feed the
    # constructor or provide dimensions/feature targets.
    screen_locations = [("M1", "Left side corridor", 110, 680),
                        ("M2", "Lower left side corridor", 110, 757),
                        ("M3", "Bottom left corner", 103, 925),
                        ("M4", "Right upper corner", 782, 557),
                        ("M5", "Right lower corner", 782, 741)]
    locations = []
    for rid, name, px, py in screen_locations:
        cx, cy = screenshot_pixel_to_scene(px, py, full_bounds)
        bounds = [max(full_bounds[0], cx-.65), max(full_bounds[1], cy-.5),
                  min(full_bounds[2], cx+.65), min(full_bounds[3], cy+.5)]
        locations.append({"id": rid, "label": name, "screenshot_pixel": [px, py],
                          "center_mm": [cx, cy], "bounds_mm": bounds})
        for suffix, geometry in [("org", org), ("rejected", old), ("corrected", combined)]:
            svg(f"{rid}_{suffix}.svg", bounds, [(geometry, "#e9485b", "none", 0, 1)],
                markers=[((cx, cy), rid, "#ffdd00")])
    (run / "owner_marked_locations.json").write_text(json.dumps({
        "basis": "owner screenshot locator only; approximate, not construction data",
        "coordinate_mapping": "affine full-crop image frame; raster Y inverted into scene Y",
        "image_frame_px": list(OWNER_SCREENSHOT_IMAGE_FRAME_PX),
        "locations": locations,
    }, indent=2) + "\n")
    (run / "review_issue_ids.json").write_text(json.dumps(issues, indent=2, sort_keys=True) + "\n")

    circle_rows = []
    for row in embedded["records"]:
        sid, cid = row["source_id"], circle_ids[row["source_id"]]
        selected = wkb.loads((run / "t02_embedded_circles" / (sha(sid.encode()) + ".wkb")).read_bytes())
        parent = candidates.get(row["parent_source_id"], geometries[row["parent_source_id"]])
        cx, cy = row["center_mm"]
        radius = max(row["source_radius_mm"] * 2.2, .22)
        bounds = [cx-radius, cy-radius, cx+radius, cy+radius]
        svg(f"{cid}.svg", bounds, [(combined, "#e9485b", "none", 0, .4), (parent, "#e9485b", "#ffffff", 1, 1)],
            circles=[(geometries[sid], "#65b5ff", "4 3"), (selected, "#ffd166", "")])
        parent_label = rect_ids.get(row["parent_source_id"], "protected source")
        circle_rows.append(f'<tr><td><button onclick="showCircle(\'{cid}\')">{cid}</button></td><td>{row["source_radius_mm"]*2:.6f}</td><td>{row["selected_diameter_mm"]:.6f}</td><td>{parent_label}</td><td>{row["decision"]}</td></tr>')
    closeups = "".join(f'<section id="{r["id"]}"><h3>{r["id"]} · {r["label"]}</h3><div class="three">' +
        "".join(f'<figure><figcaption>{label}</figcaption><img src="{r["id"]}_{suffix}.svg" alt="{r["id"]} {label}"></figure>'
                for suffix, label in [("org", "ORG"), ("rejected", "Rejected v31"), ("corrected", "Corrected")]) + '</div></section>' for r in locations)
    marked_issue_html = marked_location_issue_html(locations, issues, rect_ids)
    marked_surface_html = marked_surface_findings_html(
        locations, decisions, rows, geometries, candidates, trace_geometries, rect_ids, audit, policy)

    def issue_table(items):
        return '<div class="scroll"><table><tr><th>Review ID</th><th>Rectangle</th><th>Issue</th><th>Source → final surface gap mm</th><th>Status</th></tr>' + "".join(
            f'<tr><td>{x["review_id"]}</td><td>{rect_ids[x["rectangle_source_id"]]}</td><td>{x["issue_type"]}</td><td>{x["original_surface_gap_mm"]:.6f} → {x["final_surface_gap_mm"]:.6f}</td><td>Open · future trace review</td></tr>' for x in items) + '</table></div>'
    kept = result["decision_counts"].get("KEEP", 0)
    circles_count, grown_circles = embedded["count"], embedded["grown_count"]
    baseline_count = len(audit_doc.get("baseline_side_gap_issues", []))
    surface_shortfall_count = audit_doc.get("surface_gap_diagnostic_count_below_hard_floor", baseline_count)
    side_check_count = audit_doc.get("owner_side_surface_check_count", audit_doc.get("side_copper_checks", 0))
    minimum_surface_gap = audit_doc.get("minimum_owner_side_surface_gap_mm")
    side_gap_rows = (json.loads((audit / "side_gap_checks.json").read_bytes()) if audit else [])
    growth_gaps = [x["new_growth_gap_mm"] for x in side_gap_rows if x.get("new_growth_gap_mm") is not None]
    minimum_growth_gap = min(growth_gaps) if growth_gaps else None
    corner_only_count = audit_doc.get("corner_only_open_pairs", 0)
    side_safe_corner_count = audit_doc.get("side_safe_corner_open_pairs", 0)
    corner_pair_count = audit_doc.get("corner_or_endpoint_open_pairs", corner_only_count)
    corner_summary = (f"{corner_pair_count} corner/endpoint near-gap pairs remain OPEN: "
                      f"{corner_only_count} have no classified side section, and {side_safe_corner_count} "
                      "meet the side-region gap separately but have a closer corner/endpoint gap. "
                      if corner_pair_count else "")
    surface_summary = (f"The {side_check_count} classified side checks have a minimum candidate-to-trace-copper gap of "
                       f"{minimum_surface_gap:.6f} mm against the {policy['construction_gap_mm']:.6f} mm construction target. "
                       f"This includes {surface_shortfall_count} unchanged ORG gaps below the hard floor, which remain OPEN. "
                       f"Across {len(growth_gaps)} checks involving new growth, the smallest added-copper side gap is "
                       f"{minimum_growth_gap:.9f} mm; those checks meet the construction target. "
                       if minimum_surface_gap is not None else "")
    trace_rule_summary = surface_summary
    measurement_summary = ("Side copper-surface construction target: 0.020020 mm · copper-surface hard floor: 0.020000 mm · comparison tolerance: 0.000010 mm (not a waiver).")
    audit_href = review_relative_link(run, audit / "audit.json") if audit else None
    audit_link = f'<a href="{html.escape(audit_href)}">Fresh saved-output audit</a>' if audit_href else 'Fresh audit pending'
    buttons = [("t01_plus_t02.svg", "Corrected copper"), ("rejected_v31.svg", "Rejected v31"),
               ("growth_overlay.svg", "Added copper"), ("target_ids.svg", "Rectangle IDs"),
               ("covered_overlay.svg", "Covered circles"), ("issues_overlay.svg", "Open trace issues"),
               ("physical_components.svg", "Physical components"), ("org_crop.svg", "ORG")]
    if (run / "attachment_ports.svg").exists():
        buttons.insert(-1, ("attachment_ports.svg", "Attachment ports"))
    button_html = "".join(f'<button onclick="showView(\'{src}\',this)">{label}</button>' for src, label in buttons)
    page = f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>T02 · Reopened owner review</title>
<style>body{{margin:0;background:#edf2f6;color:#17283a;font:16px/1.5 system-ui}}main{{max-width:1500px;margin:auto;padding:24px}}article,header{{background:white;border:1px solid #cbd5df;border-radius:14px;padding:22px;margin-bottom:20px}}h1{{font-size:30px;margin:0}}h2{{margin-top:0}}nav, .controls{{display:flex;gap:10px;flex-wrap:wrap;margin:16px 0}}button,a{{color:#085fa6}}button{{font:inherit;background:#f7fafc;border:1px solid #aebfcd;border-radius:7px;padding:8px 12px;cursor:pointer}}button.active{{background:#183b55;color:white}}img{{display:block;width:100%;background:#071522;border-radius:8px}}.notice{{background:#fff3d2;padding:14px;border-left:4px solid #d59100}}.stats{{display:flex;gap:16px;flex-wrap:wrap;margin:16px 0}}.stats b{{font-size:24px}}.stats>div{{padding:10px;background:#f0f5f8;border-radius:8px}}.three{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}}figure{{margin:0}}figcaption{{font-weight:650;margin:8px 0}}section{{margin:24px 0}}.scroll{{overflow:auto;max-height:520px}}table{{border-collapse:collapse;width:100%;font-size:14px}}td,th{{border:1px solid #cbd5df;padding:7px;text-align:left}}th{{background:#edf2f6;position:sticky;top:0}}a{{text-decoration:none}}.small{{font-size:14px;color:#455b6b}}.circle-view{{max-width:650px;margin:16px auto}}@media(max-width:800px){{main{{padding:10px}}header,article{{padding:14px}}.three{{grid-template-columns:1fr}}}}</style>
<main><header><h1>T02 · Reopened owner review</h1><p>Side-by-side spacing is measured from the actual finite-width trace-copper boundary and has priority over corner growth. The corrected run preserves source centers, intact rectangles, the 1.25× rectangle ceiling, original physical components and original local contact pairs.</p><nav><a href="#whole-crop">Whole crop</a><a href="#marked-closeups">Your marked locations</a><a href="#covered-circles">Covered circles</a><a href="#trace-issues">Future trace issues</a><a href="../t02_owner_reopening_evidence_20261025/owner_annotation_1.png">Your annotation</a></nav>
<div class="stats"><div><b>{result['target_set_count']-kept}</b> rectangles grow · {kept} held</div><div><b>{audit_doc.get('original_source_component_count','?')}</b> original physical components</div><div><b>{audit_doc.get('source_contributions_preserved','?')}</b> source contributions preserved</div><div><b>{audit_doc.get('original_source_contacts_retained','?')}</b> original contact pairs retained</div><div><b>0</b> new component joins or source contacts</div><div><b>{grown_circles}/{circles_count}</b> covered circles grow internally</div><div><b>{result['added_area_mm2']:.4f}</b> mm² added</div></div>
<p class="notice">Owner review remains pending. {trace_rule_summary} {surface_shortfall_count} unchanged ORG side gaps below the 0.020000 mm hard floor remain OPEN diagnostics. {corner_summary} Attachment extensions also remain OPEN; no trace repair is applied. The future trace step must preserve or increase ORG trace width.</p><p class="small">{measurement_summary} A separate finite-width copper-contact guard preserves the original component/contact partition. The component audit measures physical source contacts, not electrical nets. Same native parser and Shapely; these are bounded geometric checks, not independent electrical or manufacturing acceptance.</p></header>
<article id="whole-crop"><h2 id="view-title">Corrected copper · full crop</h2><div class="controls">{button_html}</div><img id="whole-result" src="t01_plus_t02.svg" alt="Corrected T01 plus T02 full crop, available for annotation"><p>Use Rectangle IDs or Open trace issues to identify feedback precisely. The rejected view is retained for direct comparison. Component colors represent physical source copper membership, separate from T01 envelope groups.</p></article>
<article id="marked-closeups"><h2>Your marked locations · same scale comparisons</h2><p class="small">Yellow dots mark the approximate screenshot selections. Their pixel positions are mapped through the displayed crop image frame (x={OWNER_SCREENSHOT_IMAGE_FRAME_PX[0]:g}–{OWNER_SCREENSHOT_IMAGE_FRAME_PX[2]:g}, y={OWNER_SCREENSHOT_IMAGE_FRAME_PX[1]:g}–{OWNER_SCREENSHOT_IMAGE_FRAME_PX[3]:g}); screenshot Y is inverted into scene coordinates. The locator affects review windows only; construction uses native ORG geometry. Each window compares original copper, rejected v31 and the corrected saved result.</p>{closeups}{marked_surface_html}{marked_issue_html}</article>
<article id="covered-circles"><h2>Embedded covered-circle pass · {grown_circles} grown of {circles_count}</h2><p>Gold is the selected round contour; dashed blue is its ORG core. White outlines its same source-bound parent's final shape. Each circle selects the largest shared diameter class that fits wholly inside that parent, with its center fixed and its own 1.5× ceiling. These promotions add zero incremental composed-copper area within the declared geometric tolerance because each selected circle remains fully covered by its parent; the overlay shows this latent round geometry.</p><div class="circle-view"><h3 id="circle-title">C01</h3><img id="covered-focus" src="C01.svg" alt="Covered circle and containing parent"></div><details><summary>Choose a covered circle · all {circles_count} records</summary><div class="scroll"><table><tr><th>ID</th><th>ORG diameter mm</th><th>Selected diameter mm</th><th>Parent</th><th>Decision</th></tr>{''.join(circle_rows)}</table></div></details></article>
<article id="trace-issues"><h2>Open work for the future trace session</h2><p>{len(action_issues)} side/corner clearance issues and {len(issues)-len(action_issues)} original-attachment extensions are recorded with source IDs, spans, hashes and measured gaps. No width reduction is authorized: any later trace edit must retain at least its ORG width throughout the changed route. The ledger does not select repairs.</p>{issue_table(action_issues)}<details><summary>Original-attachment extension contexts · {len(issues)-len(action_issues)}</summary>{issue_table([x for x in issues if x not in action_issues])}</details><p><a href="future_trace_work_items.json">Complete future trace handoff</a> · <a href="review_issue_ids.json">Review IDs and source bindings</a></p>{width_reservation_html}</article>
<article><h2>Decisions and saved evidence</h2><p>{audit_link} · <a href="component_preservation.json">Component/contact audit</a> · <a href="rejected_v31_component_negative_control.json">Rejected v31 failure control</a> · <a href="embedded_covered_circles.json">Covered-circle decisions</a> · <a href="determinism_receipt.json">Byte-identical replay</a> · <a href="SHA256SUMS.txt">Bundle hashes</a></p>{target_details_html(decisions_doc,1.25)}<p class="small">Accepted T01 scene: {result['accepted_T01_scene_sha256']}. T02 source and policy are bound in the run receipt. The accepted scene remains frozen. Architecture/ABI consolidation follows owner acceptance; T03 is not started.</p></article></main>
<script>function showView(src,button){{document.getElementById('whole-result').src=src;document.getElementById('view-title').textContent=button.textContent+' · full crop';document.querySelectorAll('.controls button').forEach(b=>b.classList.remove('active'));button.classList.add('active')}}function showCircle(id){{document.getElementById('covered-focus').src=id+'.svg';document.getElementById('circle-title').textContent=id;document.getElementById('covered-circles').scrollIntoView({{behavior:'smooth'}})}}</script></html>'''
    (run / "index.html").write_text(page)
