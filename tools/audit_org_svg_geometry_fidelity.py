#!/usr/bin/env python3
"""Audit published ORG WKB-to-SVG geometry using a strict path round-trip."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

from shapely import from_wkb

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.org_svg_geometry_fidelity import (  # noqa: E402
    compare_path_to_wkb,
    simplified_round_trip_status,
    stored_round_trip_pass,
)
from src.revision_catalog import RevisionCatalog  # noqa: E402


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha_file(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def canonical_sha(value) -> str:
    return sha_bytes(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                allow_nan=False).encode())


def quantiles(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {"max": None, "p50": None, "p95": None, "p99": None}
    ordered = sorted(values)
    def q(fraction: float) -> float:
        return ordered[min(len(ordered) - 1, math.ceil(fraction * len(ordered)) - 1)]
    return {"max": max(ordered), "p50": statistics.median(ordered),
            "p95": q(.95), "p99": q(.99)}


def run_audit(run_dir: Path, dataset_id: str, output_dir: Path) -> dict:
    run_dir = run_dir.resolve()
    scene_path = run_dir / "scene.json"
    receipt_path = run_dir / "receipt.json"
    scene, receipt = json.loads(scene_path.read_text()), json.loads(receipt_path.read_text())
    displayed = scene.get("ingestion", {}).get("org_family_maps", {}).get(dataset_id)
    if not isinstance(displayed, dict):
        raise ValueError(f"dataset is not bound in this publication: {dataset_id}")
    projection_path = (run_dir / displayed["snapshot"]).resolve()
    projection_bytes = projection_path.read_bytes()
    projection = json.loads(projection_bytes)
    if sha_bytes(projection_bytes) != displayed.get("projection_sha256"):
        raise ValueError("published projection hash does not match scene binding")
    stored_ref = projection.get("stored_geometry_paths_ref", {})
    stored_path = (run_dir / stored_ref["snapshot"]).resolve()
    stored_bytes = stored_path.read_bytes()
    if sha_bytes(stored_bytes) != stored_ref.get("sha256"):
        raise ValueError("stored geometry resource hash mismatch")
    stored_paths = json.loads(stored_bytes)
    simple_paths = projection.get("geometry_paths", {})
    bindings = projection.get("geometry_bindings", {})
    if set(simple_paths) != set(stored_paths) or set(simple_paths) != set(bindings):
        raise ValueError("simplified/stored/binding path key sets differ")

    binding = projection["binding"]
    bundle = (ROOT / displayed["bundle_path"]).resolve()
    with RevisionCatalog(bundle / "store", read_only=True) as catalog:
        org = catalog.snapshot(binding["org_revision"])
        if org["source_sha256"] != binding["org_source_sha256"]:
            raise ValueError("pinned ORG source hash does not match the published projection")
        org_objects = [row for row in org["objects"] if row.get("geometry_sha256")]
        object_bounds = {}
        for row in org_objects:
            object_bounds.setdefault(row["geometry_sha256"], []).append(row.get("bounds_mm"))
        geometry_keys = set(simple_paths)
        if not geometry_keys.issubset(object_bounds):
            raise ValueError("a published SVG path has no geometry-bearing ORG source object")
        metrics_rows = []
        bound_delta_max = 0.0
        for index, key in enumerate(sorted(geometry_keys), 1):
            payload = catalog.read_payload(key)
            if sha_bytes(payload) != key:
                raise ValueError(f"WKB payload hash mismatch: {key}")
            source = from_wkb(payload)
            if source.geom_type not in ("Polygon", "MultiPolygon") or not source.is_valid:
                raise ValueError(f"unsupported or invalid WKB geometry: {key} ({source.geom_type})")
            source_bounds = list(source.bounds)
            for bounds in object_bounds[key]:
                if bounds is not None:
                    delta = max(abs(float(a) - float(b)) for a, b in zip(source_bounds, bounds))
                    bound_delta_max = max(bound_delta_max, delta)
                    if delta > 1e-8:
                        raise ValueError(f"catalogue object bounds disagree with its WKB: {key}")
            exact_binding = bindings[key]
            if (exact_binding.get("source_wkb_sha256") != key or
                    exact_binding.get("derivation") != "pcb-org-svg-path/v1" or
                    exact_binding.get("stored_path_sha256") != sha_bytes(stored_paths[key].encode()) or
                    exact_binding.get("simplified_path_sha256") != sha_bytes(simple_paths[key].encode())):
                raise ValueError(f"geometry path identity/digest mismatch: {key}")
            exact = compare_path_to_wkb(source, stored_paths[key])
            simple = compare_path_to_wkb(source, simple_paths[key])
            exact_status = "PASS" if stored_round_trip_pass(
                exact, int(projection["display_geometry"]["stored_coordinate_decimals"])) else "FAIL"
            simple_status = simplified_round_trip_status(
                simple,
                float(projection["display_geometry"]["simplification_parameter_mm"]),
                int(projection["display_geometry"]["simplified_coordinate_decimals"]))
            metrics_rows.append({"geometry_sha256": key,
                                 "source_object_ids": [row["id"] for row in org_objects
                                                       if row.get("geometry_sha256") == key],
                                 "stored_status": exact_status,
                                 "stored": exact,
                                 "simplified_status": simple_status["status"],
                                 "simplified_limit_mm": simple_status["observed_hausdorff_limit_mm"],
                                 "simplified": simple})
            if index % 500 == 0:
                print(f"audited {index}/{len(geometry_keys)} geometries", file=sys.stderr)

    output_dir.mkdir(parents=True, exist_ok=False)
    metrics_path = output_dir / "geometry_metrics.jsonl"
    with metrics_path.open("w") as stream:
        for row in metrics_rows:
            stream.write(json.dumps(row, sort_keys=True, allow_nan=False) + "\n")
    exact_bad = [row for row in metrics_rows if row["stored_status"] != "PASS"]
    simple_bad = [row for row in metrics_rows
                  if row["simplified_status"] != "PASS_OBSERVED_BOUNDED"]
    stored_hausdorff = [row["stored"]["hausdorff_distance_mm"] for row in metrics_rows]
    simple_hausdorff = [row["simplified"]["hausdorff_distance_mm"] for row in metrics_rows]
    simple_symmetric_diff = [row["simplified"]["symmetric_difference_area_mm2"] for row in metrics_rows]
    summary = {
        "schema": "pcb-org-svg-geometry-fidelity-audit/1",
        "status": "PASS_BOUNDED" if not exact_bad and not simple_bad else "NOT_ESTABLISHED",
        "scope": "Pinned ORG WKB to published SVG path round-trip; no PCB semantic, electrical, engineering, or manufacturing qualification.",
        "review_run": str(run_dir.relative_to(ROOT)),
        "publication_receipt_sha256": sha_file(receipt_path),
        "publication_receipt_id": receipt.get("publication_id"),
        "dataset_id": dataset_id,
        "org_revision": binding["org_revision"],
        "org_source_sha256": binding["org_source_sha256"],
        "map_revision": binding["map_revision"],
        "map_content_sha256": binding["map_content_sha256"],
        "input_snapshot_id": binding["input_snapshot_id"],
        "projection_sha256": sha_bytes(projection_bytes),
        "stored_geometry_resource_sha256": sha_bytes(stored_bytes),
        "source_catalogue_revision_sha256": binding["org_revision"],
        "source_catalogue_config": org.get("config", {}),
        "geometry_count": len(metrics_rows),
        "all_source_objects_with_geometry": len(org_objects),
        "stored_coordinate_decimals": projection["display_geometry"]["stored_coordinate_decimals"],
        "simplified_coordinate_decimals": projection["display_geometry"]["simplified_coordinate_decimals"],
        "simplification_parameter_mm": projection["display_geometry"]["simplification_parameter_mm"],
        "coordinate_transform": "Identity: source WKB x/y in mm are emitted unchanged; SVG viewport uses the native SVG y-down canvas orientation.",
        "coordinate_bounds_max_delta_mm": bound_delta_max,
        "fill_rule": "evenodd explicitly set on ORG member, family overview, complete group, and excluded-feature paths",
        "clipping": "No geometry clipping in the path serializer; every path's measured bounds are compared to its source WKB and catalogue bounds.",
        "stored": {
            "status": "PASS" if not exact_bad else "FAIL",
            "failed_geometry_count": len(exact_bad),
            "hausdorff_distance_mm": quantiles(stored_hausdorff),
            "rounding_bound_mm": math.sqrt(2) * 0.5 * 10 ** (-int(projection["display_geometry"]["stored_coordinate_decimals"])),
        },
        "simplified": {
            "status": "PASS_OBSERVED_BOUNDED" if not simple_bad else "NOT_ESTABLISHED",
            "failed_geometry_count": len(simple_bad),
            "hausdorff_distance_mm": quantiles(simple_hausdorff),
            "symmetric_difference_area_mm2_sum": sum(simple_symmetric_diff),
            "symmetric_difference_area_mm2_max": max(simple_symmetric_diff, default=0),
            "topology_counts_preserved": all(row["simplified"]["topology_counts_match"] for row in metrics_rows),
            "valid_paths": all(row["simplified"]["svg_valid"] for row in metrics_rows),
            "interpretation": "Measured path-specific bound for this pinned projection; simplification_parameter_mm is not a general maximum-error guarantee.",
        },
        "browser_test_record": "browser_evidence.json in the enclosing G3 audit pack records the separate connected-Node-REPL DOM execution.",
        "code_sha256": {
            relative: sha_file(ROOT / relative) for relative in (
                "src/org_svg_geometry_fidelity.py", "src/org_family_review.py",
                "src/visual_scene.py", "web/org_family_review.js",
                "tools/audit_org_svg_geometry_fidelity.py")
        },
        "metrics_jsonl": metrics_path.name,
        "verified_at": datetime.now(timezone.utc).isoformat(),
    }
    summary_path = output_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    inventory = {path.name: sha_file(path) for path in (summary_path, metrics_path)}
    (output_dir / "SHA256SUMS").write_text("".join(f"{digest}  {name}\n" for name, digest in sorted(inventory.items())))
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True, help="verified immutable workbench publication")
    parser.add_argument("--dataset-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = run_audit(args.run, args.dataset_id, args.output)
    print(json.dumps({k: report[k] for k in ("status", "geometry_count", "stored", "simplified")}, indent=2))
    return 0 if report["status"] == "PASS_BOUNDED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
