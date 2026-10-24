#!/usr/bin/env python3
"""Run and render the bounded ORG-only T01 crop experiment."""
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape

from shapely import from_wkb
from shapely.geometry import box

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.crop_dynamic_t01 import CROP_EDGE_GUARD_MM, V_BOUNDS, run
from src.native_inventory import inventory

DATA = ROOT / "dataset/szu-comm_3020301113B_intake_ready_20261021_v2/raw/ORG/top.kicad_pcb"
EXPECTED_ORG = "850c4c74d55717a721d4bbed7ec876ee086f475efd97f69bb5b5164ef77533a0"
EVIDENCE = ROOT / "out/crop_dynamic_tasks/t01"


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def polygon_path(geom, sx, sy, scale):
    if geom.geom_type == "Polygon":
        polys = [geom]
    elif geom.geom_type == "MultiPolygon":
        polys = list(geom.geoms)
    elif geom.geom_type == "GeometryCollection":
        polys = [p for p in geom.geoms if p.geom_type == "Polygon"]
    else:
        return ""
    commands = []
    for p in polys:
        for ring in [p.exterior, *p.interiors]:
            pts = list(ring.coords)
            if not pts:
                continue
            commands.append(f"M {(pts[0][0]-sx)*scale:.2f} {(pts[0][1]-sy)*scale:.2f}")
            commands.extend(f"L {(x-sx)*scale:.2f} {(y-sy)*scale:.2f}" for x,y in pts[1:])
            commands.append("Z")
    return " ".join(commands)


def render(source, result, path):
    inv = inventory(source)
    view = box(*V_BOUNDS)
    minx, miny, maxx, maxy = V_BOUNDS
    scale = 420
    width, height = (maxx-minx)*scale, (maxy-miny)*scale
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}" height="{height:.0f}" viewBox="0 0 {width:.2f} {height:.2f}">',
             '<rect width="100%" height="100%" fill="#101820"/>',
             '<g fill="#d62537" fill-rule="evenodd" opacity=".93">']
    for obj in inv["objects"]:
        if "F.Cu" not in obj["layers"] or not obj["geometry_sha256"]:
            continue
        geom = from_wkb(inv["payloads"][obj["geometry_sha256"]])
        if geom.intersects(view):
            cropped = geom.intersection(view)
            d = polygon_path(cropped, minx, miny, scale)
            if d:
                parts.append(f'<path d="{d}"/>')
    parts.append('</g><g fill="#38d886" fill-rule="evenodd" opacity=".82">')
    for decision in result["decisions"]:
        g = from_wkb(bytes.fromhex(decision["candidate_wkb"]))
        core = next(from_wkb(inv["payloads"][o["geometry_sha256"]]) for o in inv["objects"]
                    if o["id"] == decision["source_id"])
        added = g.difference(core).intersection(view)
        d = polygon_path(added, minx, miny, scale)
        if d:
            parts.append(f'<path d="{d}"/>')
    parts.extend(['</g>',
        f'<text x="12" y="24" fill="white" font-family="sans-serif" font-size="16">ORG base red · accepted circle-stage addition green · {result["eligible_target_count"]} eligible</text>',
        '</svg>'])
    path.write_text("\n".join(parts) + "\n")


def main():
    source = DATA.read_bytes()
    sha = hashlib.sha256(source).hexdigest()
    if sha != EXPECTED_ORG:
        raise SystemExit(f"ORG_SOURCE_HASH_MISMATCH:{sha}")
    result = run(source)
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    profile_path = ROOT / "dataset/szu-comm_3020301113B_intake_ready_20261021_v2/metadata/profile.json"
    profile = json.loads(profile_path.read_text())
    geometry_dir = EVIDENCE / "geometry"
    geometry_dir.mkdir(exist_ok=True)
    contract = {
        "schema": "crop-dynamic-t00-contract/1",
        "authorization": "T00 prerequisites + T01 only; stop before T02",
        "source": {"path": str(DATA.relative_to(ROOT)), "sha256": sha, "revision": "ORG"},
        "preserved_intake_profile": {"path": str(profile_path.relative_to(ROOT)),
            "sha256": hashlib.sha256(profile_path.read_bytes()).hexdigest(),
            "intake_status": profile["intake"]["status"], "preservation": profile["intake"]["preservation"],
            "qualification": profile["intake"]["qualification"], "native_extraction": profile["intake"]["native_extraction"],
            "note": "This task reads the pinned ORG native board; it does not reseal or upgrade the intake profile."},
        "edit_source_available_to_constructor": False,
        "mapping": {"prior_evidence": "out/ingestion/audits/20261024_org_and_screenshot_mapping_v1/evidence/summary.json",
            "status": "CONDITIONAL_PASS_LOCAL_CROP_MATCHING; exact semantic identity and board-wide uniqueness unproven",
            "viewport_mm": list(V_BOUNDS), "frame": "native KiCad X right, Y down, millimetres",
            "ORG_mask_iou": 0.851804256439209, "EDIT_mask_iou": 0.9152336120605469,
            "ORG_mapping_basis": {"evidence": "out/ingestion/audits/20261024_org_and_screenshot_mapping_v1/evidence/g18_predeclared_holdout_v1.json",
                "conditional_G16_orientation": [2, True], "conditional_G16_scale": 0.6,
                "conditional_G16_top_left_source_px": [107, 3933],
                "local_training_search_reused": True,
                "interpretation": "conditional local candidate mapping, not screenshot authenticity or board-wide uniqueness"},
            "owner_composite_reference": {"path": "docs/crop_dynamic_tasks/references/OWNER_REQUESTED_ORG_EDIT_CROP.png",
                "sha256": "cefaa35b2f5ffc13a791c4b3b79b46bae10264572eea40168dea4e3fec851b21"},
            "registered_ORG_crop_sha256": "dbba976ced7c0350d77d51be61068df5bad1ce5a596047ba5cbbef9513d4ca16",
            "registered_EDIT_crop_sha256": "ee6711f5157d6782cce1f3fbe59a11b180b47fcb005254266a6b3787e72f8d67",
            "coordinate_precision_note": "V preserves unrounded prior-fit output for reproducibility; decimal digits are not a calibrated positional-accuracy claim. No absolute-origin calibration or error-propagation bound is established."},
        "W": {"definition": f"V inset by {CROP_EDGE_GUARD_MM} mm on all sides",
              "bounds_mm": result["write_region_mm"],
              "selection": "supported filled F.Cu gr_circle occurrences fully inside W; all other source geometry protected",
              "minimum_target_clearance_from_V_boundary_mm": result["minimum_target_clearance_from_V_boundary_mm"],
              "translation_sensitivity": "focused test confirms 39/7/7 partition at V translations of +/-0.001 mm in X and Y; this is a deterministic sensitivity check, not a calibrated alignment uncertainty"},
        "H": {"definition": f"V.buffer({result['halo_mm']} mm)", "supported_effective_object_count": result["supported_halo_object_count"],
              "kind_counts": result["supported_halo_kind_counts"],
              "trace_reservations": {"native_segments_and_arcs": result["reserved_trace_object_count"],
                  "protected_clearance_buffer_mm": result["policy"]["protected_gap_mm"] + result["policy"]["gap_buffer_margin_mm"],
                  "maximum_growth_influence_mm": result["policy"]["growth_cap_mm"],
                  "total_context_reach_mm": result["policy"]["growth_cap_mm"] + result["policy"]["protected_gap_mm"] + result["policy"]["gap_buffer_margin_mm"]},
              "unsupported_intersections": result["unsupported_FCu_intersecting_halo"]},
        "Q": "not used as an optimization target in T01; EDIT withheld from construction",
        "selection": result["policy"]["selection"],
        "denominator": {"eligible": result["eligible_target_count"], "eligible_ids": result["eligible_target_ids"],
            "halo_filled_circle_occurrences": result["halo_filled_circle_count"],
            "kept_small_circles": result["kept_small_circle_count"],
            "abstained_edge_or_guard_circles": result["abstained_edge_guard_circle_count"]},
        "experiment_assumptions": {"growth_cap_mm": result["policy"]["growth_cap_mm"],
            "crop_edge_guard_mm": result["crop_edge_guard_mm"],
            "protected_gap_mm": result["policy"]["protected_gap_mm"],
            "gap_buffer_safety_margin_mm": result["policy"]["gap_buffer_margin_mm"],
            "measured_gap_tolerance_mm": result["policy"]["gap_tolerance_mm"],
            "protected_core_loss_tolerance_mm2": 1e-12,
            "priority": result["policy"]["priority"],
            "finite_search": "one nominal growth proposal per eligible target; no tuning or EDIT fit; one deterministic order"},
        "limits": ["local mapping is conditional, not a globally unique registration",
            "native geometric classes do not identify pads, terminals, nets, or historical intent",
            "no electrical, manufacturing, or whole-board acceptance claim"]}
    write_json(EVIDENCE / "t00_contract.json", contract)
    # Persist every generated scene contour as a source-keyed binary geometry.
    for mode, records in (("dynamic", result["decisions"]),
                          ("static", result["static_baseline"]["decisions"])):
        for record in records:
            payload = bytes.fromhex(record.pop("candidate_wkb"))
            name = f"{mode}_{hashlib.sha256(record['source_id'].encode()).hexdigest()[:16]}.wkb"
            out = geometry_dir / name
            out.write_bytes(payload)
            record["geometry_artifact"] = str(out.relative_to(ROOT))
            record["geometry_sha256"] = hashlib.sha256(payload).hexdigest()
    # Numeric/source records stay in the receipt; geometry payloads are separately hash-bound.
    for d in result["decisions"]:
        d["core_loss_tolerance_mm2"] = 1e-12
    receipt = {"schema": "crop-dynamic-t01-receipt/1", "created_utc": datetime.now(timezone.utc).isoformat(),
               "contract_sha256": hashlib.sha256((EVIDENCE/"t00_contract.json").read_bytes()).hexdigest(),
               "superseded_failed_attempts": [
                   {"observation": "GEOS covers() was false at machine precision although measured source-core loss was <=1e-12 mm2",
                    "correction": "preserve source core by union and verify measured loss against explicit 1e-12 mm2 tolerance"},
                   {"observation": "initial protected-buffer overlays produced measured raw gaps below 0.02 mm",
                    "correction": "reapply the complete forbidden-buffer union and use a 0.005 mm conservative buffer margin; independently remeasure final raw gaps"}],
               "run": result, "status": {"task_execution": "COMPLETE", "technical_checks": "PENDING"}}
    write_json(EVIDENCE / "t01_run.json", receipt)
    # Rehydrate candidate geometries from the bound WKB files for rendering.
    render_result = json.loads(json.dumps(result))
    for record in render_result["decisions"]:
        record["candidate_wkb"] = (ROOT / record["geometry_artifact"]).read_bytes().hex()
    render(source, render_result, EVIDENCE / "t01_full_crop.svg")
    static_render = json.loads(json.dumps(render_result))
    static_by_id = {d["source_id"]: d for d in result["static_baseline"]["decisions"]}
    for record in static_render["decisions"]:
        record["candidate_wkb"] = (ROOT / static_by_id[record["source_id"]]["geometry_artifact"]).read_bytes().hex()
    render(source, static_render, EVIDENCE / "t01_static_baseline.svg")
    event_rows = [d for d in result["decisions"] if d["adapted_by_prior_acceptance"]]
    label_by_id = {d["source_id"]: f"site-{d['order']+1:02d}" for d in result["decisions"]}
    report = ["# T00/T01 crop run", "", f"- ORG SHA-256: `{sha}`",
              f"- Viewport: `{V_BOUNDS}` mm; halo: {result['halo_mm']} mm",
              f"- Halo inventory: {result['supported_halo_object_count']} supported copper objects, including {result['reserved_trace_object_count']} native segment/arc trace geometries; source trace footprints receive a {result['policy']['protected_gap_mm'] + result['policy']['gap_buffer_margin_mm']:.3f} mm runtime clearance buffer.",
              f"- Eligible denominator frozen before running: {result['eligible_target_count']}",
              f"- W write region is inset {result['crop_edge_guard_mm']:.3f} mm from V; crop-edge guard abstentions: {result['abstained_edge_guard_circle_count']} ({result['abstained_edge_guard_large_circle_count']} large, {result['abstained_edge_guard_small_circle_count']} small)",
              f"- Kept smaller circles: {result['kept_small_circle_count']}; frozen target denominator: {result['eligible_target_count']}",
              f"- Accepted growth area: {result['total_growth_area_mm2']:.6f} mm²; static baseline: {result['static_baseline']['total_growth_area_mm2']:.6f} mm²",
              f"- Measured dynamic adaptation events: {len(event_rows)} (target was at least 3; no forced events)",
              f"- All {sum(d['decision'] == 'GROW' for d in result['decisions'])} eligible sites have a GROW decision; the {len(event_rows)} adaptation events are distinct later-site decisions.",
              f"- Minimum measured added-copper gap: {min(d['minimum_optional_growth_gap_mm'] for d in result['decisions'] if d['minimum_optional_growth_gap_mm'] is not None):.6f} mm",
              "- The operator reads ORG only. EDIT is withheld from construction.",
              "- Status: geometry experiment only; no pad/net/electrical/manufacturing claims.", "",
              "## Actual prior-neighbor adaptation events", "",
              "| Site | Center (mm) | Earlier accepted sites consulted | Dynamic/static symmetric difference (mm²) | Accepted growth (mm²) |", "|---|---|---|---:|---:|"]
    for d in event_rows:
        previous = ", ".join(label_by_id[n] for n in d["limiting_prior_source_ids"])
        center = f"({d['center_mm'][0]:.4f}, {d['center_mm'][1]:.4f})"
        report.append(f"| {label_by_id[d['source_id']]} | {center} | {previous} | {d['dynamic_vs_static_symmetric_difference_mm2']:.8g} | {d['accepted_area_delta_mm2']:.8g} |")
    (EVIDENCE / "t01_report.md").write_text("\n".join(report) + "\n")
    import csv
    with (EVIDENCE / "site_inventory.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["site", "source_id", "source_span", "center_x_mm", "center_y_mm", "diameter_mm", "decision", "growth_area_mm2", "limiting_prior_source_ids"])
        for d in result["decisions"]:
            w.writerow([label_by_id[d["source_id"]], d["source_id"], d["source_span"], *d["center_mm"], d["diameter_mm"], d["decision"], d["accepted_area_delta_mm2"], ";".join(d["limiting_prior_source_ids"])])
    print(json.dumps({"contract": str(EVIDENCE/"t00_contract.json"), "receipt": str(EVIDENCE/"t01_run.json"),
                      "visual": str(EVIDENCE/"t01_full_crop.svg"),
                      "eligible": result["eligible_target_count"], "adaptation_events": result["dynamic_adaptation_event_count"],
                      "growth_area_mm2": result["total_growth_area_mm2"],
                      "static_growth_area_mm2": result["static_baseline"]["total_growth_area_mm2"]}, indent=2))


if __name__ == "__main__":
    main()
