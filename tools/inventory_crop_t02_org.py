#!/usr/bin/env python3
"""Build a fresh ORG-only source disposition for the declared T02 viewport.

This inventories native F.Cu geometry and names geometric rectangle candidates.
It does not consult EDIT, apply growth, or claim that candidate eligibility is
final until a qualified accepted T01 scene is admitted to T02.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

from shapely import wkb
from shapely.geometry import box

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.crop_rect_t02 import rectangular_feature
from src.native_inventory import inventory


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        default="out/crop_dynamic_tasks/t02_org_inventory_20261025_v2",
        help="fresh output directory under out/",
    )
    parser.add_argument(
        "--policy",
        default="contracts/crop_rect_t02_policy_v8.json",
        help="frozen source and eligibility policy relative to the checkout",
    )
    args = parser.parse_args()
    output = (ROOT / args.output).resolve()
    if ROOT / "out" not in output.parents:
        raise SystemExit("OUTPUT_MUST_BE_UNDER_OUT")
    output.mkdir(parents=True, exist_ok=True)

    policy_path = (ROOT / args.policy).resolve()
    if ROOT not in policy_path.parents:
        raise SystemExit("POLICY_MUST_BE_INSIDE_CHECKOUT")
    policy_raw = policy_path.read_bytes()
    policy = json.loads(policy_raw)
    source_path = ROOT / policy["source"]
    source_raw = source_path.read_bytes()
    source_hash = sha(source_raw)
    if source_hash != policy["source_sha256"]:
        raise SystemExit("ORG_SOURCE_HASH_MISMATCH")

    crop_bounds = policy["crop_bounds_org_mm"]
    if len(crop_bounds) != 4:
        raise SystemExit("INVALID_CROP_BOUNDS")
    crop = box(*map(float, crop_bounds))
    inv = inventory(source_raw)
    rows = inv["objects"]
    payloads = inv["payloads"]

    dispositions = []
    intersecting_counts: Counter[str] = Counter()
    polygon_shapes: Counter[str] = Counter()
    candidate_ids = []
    for row in rows:
        if "F.Cu" not in row.get("layers", []):
            continue
        start, end = map(int, row["source_span"])
        if start < 0 or end <= start or end > len(source_raw):
            raise SystemExit(f"INVALID_SOURCE_SPAN:{row.get('id')}")
        if row.get("source_sha256") != source_hash:
            raise SystemExit(f"SOURCE_HASH_BINDING_MISMATCH:{row.get('id')}")
        if row.get("id") != f"{source_hash}:bytes:{start}:{end}":
            raise SystemExit(f"SOURCE_ID_BINDING_MISMATCH:{row.get('id')}")

        payload = payloads.get(row.get("geometry_sha256"))
        geom = wkb.loads(payload) if payload else None
        in_crop = bool(geom is not None and not geom.is_empty and geom.intersects(crop))
        if not in_crop:
            bounds = row.get("bounds_mm")
            if geom is None and bounds and box(*bounds).intersects(crop):
                status = "UNSUPPORTED_GEOMETRY"
                reason = row.get("unsupported_reason") or "GEOMETRY_UNAVAILABLE_FOR_INTERSECTING_BOUNDS"
                item = {
                    "source_id": row["id"],
                    "source_sha256": source_hash,
                    "source_span": [start, end],
                    "source_record_sha256": sha(source_raw[start:end]),
                    "source_kind": row.get("kind"),
                    "source_geometry_sha256": row.get("geometry_sha256"),
                    "bounds_mm": bounds,
            "disposition": status,
                    "disposition_stage": "PROVISIONAL_GEOMETRIC_ELIGIBILITY_ONLY",
                    "reason": reason,
                }
                dispositions.append(item)
            continue

        intersecting_counts[row["kind"]] += 1
        rect = rectangular_feature(row, payloads, crop,
                                   max_axis_factor=float(policy["factor_per_axis"]))
        if row["kind"] == "gr_poly":
            if geom.geom_type == "Polygon":
                polygon_shapes[f"Polygon/{len(geom.exterior.coords)-1}vertices/{len(geom.interiors)}holes"] += 1
            else:
                polygon_shapes[f"{geom.geom_type}"] += 1

        disposition = "TREAT" if rect else "KEEP_PROTECTED"
        if rect:
            candidate_ids.append(row["id"])
            reason = (
                "ORG-derived exact source-bound filled rectangle; four unique vertices, "
                "perpendicular adjacent edges, equal opposite sides; no pad/net identity inferred."
            )
            geometric_class = "filled_rectangle"
            orientation = rect["orientation_radians"]
            size = rect["source_size_mm"]
        else:
            vertex_count = len(geom.exterior.coords) - 1 if geom.geom_type == "Polygon" else None
            rect_without_cap_gate = rectangular_feature(
                row, payloads, crop, enforce_full_cap_in_crop=False,
                max_axis_factor=float(policy["factor_per_axis"]))
            if rect_without_cap_gate is not None:
                reason = (
                    "Exact ORG source rectangle withheld unchanged because its complete 1.5x per-axis "
                    "growth envelope crosses the reviewed crop boundary."
                )
                geometric_class = "crop_edge_rectangle_withheld"
            elif row["kind"] == "gr_poly" and vertex_count != 4 and not crop.covers(geom):
                reason = (
                    f"ORG filled polygon with {vertex_count} boundary vertices crosses the reviewed crop edge; "
                    "retain its complete source contribution unchanged because local ownership and a bounded "
                    "write envelope are not established."
                )
                geometric_class = "crop_crossing_nonrectangle_polygon"
            else:
                reason = (
                    "ORG F.Cu contribution retained unchanged; not a supported standalone "
                    "filled rectangle under the frozen T02 eligibility test."
                )
                geometric_class = None
            orientation = None
            size = None

        dispositions.append({
            "source_id": row["id"],
            "source_sha256": source_hash,
            "source_span": [start, end],
            "source_record_sha256": sha(source_raw[start:end]),
            "source_kind": row.get("kind"),
            "source_layer": "F.Cu",
            "source_geometry_role": row.get("geometry_role"),
            "source_geometry_sha256": row.get("geometry_sha256"),
            "bounds_mm": list(geom.bounds),
            "geometric_class": geometric_class,
            "source_size_mm": size,
            "orientation_radians": orientation,
            "net_name": row.get("net_name"),
            "footprint_reference": row.get("reference"),
            "disposition": disposition,
            "disposition_stage": (
                "PROVISIONAL_GEOMETRIC_ELIGIBILITY_ONLY" if rect else "SOURCE_COPPER_PROTECTED"
            ),
            "reason": reason,
        })

    disposition_counts = Counter(row["disposition"] for row in dispositions)
    if sum(intersecting_counts.values()) != (
        disposition_counts["TREAT"] + disposition_counts["KEEP_PROTECTED"]
    ):
        raise SystemExit("DISPOSITION_COVERAGE_MISMATCH")

    report = {
        "schema": "crop-t02-org-inventory/1",
        "task": "T02_ONLY",
        "status": "ORG_RECTANGLE_TARGET_SET_FROZEN",
        "source_path": str(source_path.relative_to(ROOT)),
        "source_sha256": source_hash,
        "source_record_count": len(rows),
        "source_inventory_version": inv["version"],
        "units": inv["units"],
        "coordinate_system": inv["coordinates"],
        "geometry_error_mm": inv["geometry_error_mm"],
        "per_curve_approximation_error_mm": inv["per_curve_approximation_error_mm"],
        "crop_bounds_org_mm": crop_bounds,
        "policy_path": str(policy_path.relative_to(ROOT)),
        "policy_sha256": sha(policy_raw),
        "edit_geometry_read": False,
        "intersecting_supported_fcu_counts_by_kind": dict(sorted(intersecting_counts.items())),
        "intersecting_supported_fcu_count": sum(intersecting_counts.values()),
        "intersecting_fcu_polygon_shape_counts": dict(sorted(polygon_shapes.items())),
        "disposition_counts": dict(sorted(disposition_counts.items())),
        "candidate_target_count": len(candidate_ids),
        "candidate_target_ids_sha256": sha("\n".join(sorted(candidate_ids)).encode()),
        "candidate_target_set_is_final": True,
        "operation_authorized": False,
        "candidate_target_set_limitation": (
            "Final ORG-only geometric rectangle set under the policy hash above; the T02 runner "
            "must independently bind the latest accepted T01 scene before construction."
        ),
        "identity_and_role_limits": [
            "TREAT means provisional geometric eligibility only, not authorization to modify; scene admission and overlap checks remain pending.",
            "The source file has no native pad, net, or electrical identity for these geometric rectangle candidates.",
            "Every other intersecting F.Cu source contribution is separately retained as KEEP_PROTECTED; ambiguous unsupported geometry is not counted as absence.",
            "Generated T01 geometry is not in the ORG inventory and cannot enter the T02 candidate set by serialization shape.",
            "This inventory does not consult EDIT contours or derive construction geometry.",
        ],
    }

    (output / "inventory_report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    (output / "feature_dispositions.json").write_text(json.dumps({
        "schema": "crop-t02-feature-dispositions/2",
        "source_sha256": source_hash,
        "crop_bounds_org_mm": crop_bounds,
        "target_count": len(candidate_ids),
        "target_set_sha256": report["candidate_target_ids_sha256"],
        "candidate_set_status": report["status"],
        "dispositions": dispositions,
    }, indent=2, sort_keys=True) + "\n")
    files = ["feature_dispositions.json", "inventory_report.json"]
    sums = "".join(f"{sha((output / name).read_bytes())}  {name}\n" for name in files)
    (output / "SHA256SUMS.txt").write_text(sums)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
