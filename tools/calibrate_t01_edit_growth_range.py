#!/usr/bin/env python3
"""Separate same-job ORG/EDIT calibration of T01 circular radius classes.

This is evaluation/calibration only. It does not generate or write candidate
geometry. Construction receives only its frozen radius-class bounds.
"""
from __future__ import annotations

import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

from shapely import from_wkb
from shapely.geometry import box

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.crop_dynamic_t01_r1 import ERROR_MM, V_BOUNDS, _circle_metrics, _filled_circle  # noqa: E402
from src.native_inventory import inventory  # noqa: E402

DATA = ROOT / "dataset/szu-comm_3020301113B_intake_ready_20261021_v2/raw"
OUTPUT = ROOT / "out/crop_dynamic_tasks/t01_r1_edit_calibrated"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def circle_rows(source: bytes, inventory_result: dict) -> list[dict]:
    viewport = box(*V_BOUNDS)
    by_geometry = {}
    for row in inventory_result["objects"]:
        if row["kind"] != "gr_circle" or "F.Cu" not in row["layers"] or not row["geometry_sha256"]:
            continue
        geometry = from_wkb(inventory_result["payloads"][row["geometry_sha256"]])
        if not geometry.intersects(viewport) or not _filled_circle(source, row):
            continue
        center, radius, round_error = _circle_metrics(geometry)
        item = by_geometry.setdefault(row["geometry_sha256"], {
            "geometry_sha256": row["geometry_sha256"],
            "center_mm": [center.x, center.y], "radius_mm": radius,
            "roundness_error_mm": round_error, "source_ids": []})
        item["source_ids"].append(row["id"])
    return sorted(by_geometry.values(), key=lambda item: (item["center_mm"][1],
        item["center_mm"][0], item["geometry_sha256"]))


def main() -> None:
    org_path = DATA / "ORG/top.kicad_pcb"
    edit_path = DATA / "EDIT/top_layer.kicad_pcb"
    org_source, edit_source = org_path.read_bytes(), edit_path.read_bytes()
    org_inventory, edit_inventory = inventory(org_source), inventory(edit_source)
    org_rows = circle_rows(org_source, org_inventory)
    edit_rows = circle_rows(edit_source, edit_inventory)
    matches, unmatched, ambiguous = [], [], []
    class_samples = defaultdict(list)
    for org in org_rows:
        ox, oy = org["center_mm"]
        nearby = sorted(((((ox-ex)**2+(oy-ey)**2)**0.5), row["geometry_sha256"], row)
                        for row in edit_rows
                        for ex, ey in [row["center_mm"]])
        exact = [row for distance, _, row in nearby if distance <= ERROR_MM]
        if len(exact) == 1:
            edit = exact[0]
            source_radius_class = round(org["radius_mm"], 5)
            matches.append({"org_source_ids": org["source_ids"],
                "org_geometry_sha256": org["geometry_sha256"],
                "edit_source_ids": edit["source_ids"],
                "edit_geometry_sha256": edit["geometry_sha256"],
                "center_mm": org["center_mm"],
                "center_distance_mm": ((ox-edit["center_mm"][0])**2 +
                    (oy-edit["center_mm"][1])**2)**0.5,
                "org_radius_mm": org["radius_mm"], "edit_radius_mm": edit["radius_mm"],
                "radius_delta_mm": edit["radius_mm"]-org["radius_mm"],
                "org_radius_class_mm": source_radius_class})
            class_samples[source_radius_class].append(edit["radius_mm"])
        elif exact:
            ambiguous.append({"org_source_ids": org["source_ids"],
                "center_mm": org["center_mm"],
                "edit_candidates": [row["source_ids"] for row in exact]})
        else:
            distance, _, closest = nearby[0]
            unmatched.append({"org_source_ids": org["source_ids"],
                "center_mm": org["center_mm"], "org_radius_mm": org["radius_mm"],
                "closest_edit_center_distance_mm": distance,
                "closest_edit_source_ids": closest["source_ids"]})

    class_ranges = []
    for radius_class, final_radii in sorted(class_samples.items()):
        class_matches = [row for row in matches if row["org_radius_class_mm"] == radius_class]
        class_ranges.append({"org_radius_class_mm": radius_class,
            "matched_site_count": len(class_matches),
            "observed_edit_radius_min_mm": min(final_radii),
            "observed_edit_radius_max_mm": max(final_radii),
            "observed_edit_radius_median_mm": sorted(final_radii)[len(final_radii)//2],
            "observed_growth_min_mm": min(row["radius_delta_mm"] for row in class_matches),
            "observed_growth_max_mm": max(row["radius_delta_mm"] for row in class_matches),
            "frozen_constructor_max_final_radius_mm": max(final_radii),
            "constructor_note": "class maximum only; no per-site EDIT contours or radii are passed to construction"})

    result = {"schema": "t01-edit-radius-calibration/1",
        "status": "CALIBRATION_ONLY_SAME_JOB_NOT_BLIND_GENERALIZATION",
        "viewport_mm": list(V_BOUNDS), "center_match_tolerance_mm": ERROR_MM,
        "org_source": str(org_path.relative_to(ROOT)), "org_sha256": sha(org_source),
        "edit_source": str(edit_path.relative_to(ROOT)), "edit_sha256": sha(edit_source),
        "org_unique_supported_circle_count": len(org_rows),
        "edit_unique_supported_circle_count": len(edit_rows),
        "exact_center_unique_match_count": len(matches),
        "unmatched_org_count": len(unmatched), "ambiguous_org_count": len(ambiguous),
        "class_ranges": class_ranges, "matches": matches,
        "unmatched_org_sites": unmatched, "ambiguous_org_sites": ambiguous,
        "policy": "EDIT is used only in this separate calibration/evaluation step; construction receives source-radius-class maximum final radii, not EDIT geometry or per-site values."}
    OUTPUT.mkdir(parents=True, exist_ok=True)
    path = OUTPUT / "edit_range_calibration.json"
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": result["status"], "org_sites": len(org_rows),
        "edit_sites": len(edit_rows), "matches": len(matches),
        "unmatched": len(unmatched), "ambiguous": len(ambiguous),
        "classes": class_ranges, "output": str(path)}, indent=2))


if __name__ == "__main__":
    main()
