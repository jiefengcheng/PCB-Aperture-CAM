#!/usr/bin/env python3
"""Independently check T02 rectangle eligibility against native ORG spans.

Unlike the inventory classifier, this audit reads the original source text and
checks the gr_poly coordinates directly; it does not use the Shapely/WKB shape
classifier. It remains a local geometry audit, not an electrical/DFM review.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import sys

import sexpdata

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _child(node, name):
    for item in node:
        if isinstance(item, list) and item and str(item[0]) == name:
            return item
    return None


def native_filled_rectangle(raw: bytes, span: list[int], tolerance: float = 1e-9):
    """Return native coordinate dimensions if this exact source span is a rectangle."""
    start, end = map(int, span)
    if start < 0 or end <= start or end > len(raw):
        return None
    try:
        node = sexpdata.loads(raw[start:end].decode("utf-8"))
    except (UnicodeDecodeError, ValueError, TypeError):
        return None
    if not isinstance(node, list) or not node or str(node[0]) != "gr_poly":
        return None
    layer = _child(node, "layer")
    fill = _child(node, "fill")
    points = _child(node, "pts")
    if not layer or len(layer) != 2 or str(layer[1]) != "F.Cu":
        return None
    if not fill or len(fill) != 2 or str(fill[1]) != "yes":
        return None
    if not points:
        return None
    xy = [p for p in points[1:] if isinstance(p, list) and p and str(p[0]) == "xy"]
    if len(xy) != 4 or any(len(p) != 3 for p in xy):
        return None
    coords = [(float(p[1]), float(p[2])) for p in xy]
    if len(set(coords)) != 4:
        return None
    edges = [(coords[(i + 1) % 4][0] - coords[i][0],
              coords[(i + 1) % 4][1] - coords[i][1]) for i in range(4)]
    lengths = [math.hypot(x, y) for x, y in edges]
    if min(lengths) <= tolerance:
        return None
    if abs(lengths[0] - lengths[2]) > tolerance or abs(lengths[1] - lengths[3]) > tolerance:
        return None
    if abs(edges[0][0] * edges[1][0] + edges[0][1] * edges[1][1]) > tolerance * lengths[0] * lengths[1]:
        return None
    area2 = sum(coords[i][0] * coords[(i + 1) % 4][1] -
                coords[(i + 1) % 4][0] * coords[i][1] for i in range(4))
    if abs(abs(area2) / 2.0 - lengths[0] * lengths[1]) > tolerance:
        return None
    return {
        "size_mm": [lengths[0], lengths[1]],
        "orientation_radians": math.atan2(edges[0][1], edges[0][0]),
        "bounds_mm": [min(x for x, _ in coords), min(y for _, y in coords),
                      max(x for x, _ in coords), max(y for _, y in coords)],
    }


def run_audit(output_rel: str = "out/crop_dynamic_tasks/t02_org_inventory_20261025_v7") -> dict:
    output = ROOT / output_rel
    report = json.loads((output / "inventory_report.json").read_text())
    table = json.loads((output / "feature_dispositions.json").read_text())
    source = ROOT / report["source_path"]
    raw = source.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    checks = []

    def check(name, passed, detail):
        checks.append({"check": name, "passed": bool(passed), "detail": detail})

    check("source_sha256_matches_inventory", digest == report["source_sha256"], digest)
    check("table_source_hash_matches", table["source_sha256"] == digest, table["source_sha256"])
    check("target_set_hash_matches", table["target_set_sha256"] == report["candidate_target_ids_sha256"],
          table["target_set_sha256"])

    counts = Counter(row["disposition"] for row in table["dispositions"])
    expected_counts = report["disposition_counts"]
    check("expected_disposition_counts", counts == expected_counts, dict(counts))
    targets = [row for row in table["dispositions"] if row["disposition"] == "TREAT"]
    parsed_sizes = []
    bad = []
    for row in targets:
        span = row["source_span"]
        if row["source_id"] != f"{digest}:bytes:{span[0]}:{span[1]}":
            bad.append({"source_id": row["source_id"], "reason": "identity_span_mismatch"})
            continue
        if hashlib.sha256(raw[span[0]:span[1]]).hexdigest() != row["source_record_sha256"]:
            bad.append({"source_id": row["source_id"], "reason": "source_record_hash_mismatch"})
            continue
        native = native_filled_rectangle(raw, span)
        if native is None:
            bad.append({"source_id": row["source_id"], "reason": "native_source_not_filled_rectangle"})
            continue
        if any(abs(a - b) > 1e-8 for a, b in zip(sorted(native["size_mm"]), sorted(row["source_size_mm"]))):
            bad.append({"source_id": row["source_id"], "reason": "native_dimensions_disagree"})
            continue
        if any(abs(a - b) > 1e-8 for a, b in zip(native["bounds_mm"], row["bounds_mm"])):
            bad.append({"source_id": row["source_id"], "reason": "native_bounds_disagree"})
            continue
        parsed_sizes.append(native["size_mm"])
    check("all_treat_rows_are_native_filled_rectangles",
          not bad and len(parsed_sizes) == int(report["candidate_target_count"]),
          {"verified": len(parsed_sizes), "failures": bad[:10]})

    nonrect_polys = [row for row in table["dispositions"]
                     if row.get("source_kind") == "gr_poly" and row["disposition"] == "KEEP_PROTECTED"
                     and native_filled_rectangle(raw, row.get("source_span", [])) is None]
    poly_checks = []
    for row in nonrect_polys:
        if row.get("source_geometry_sha256") is None:
            poly_checks.append(False)
            continue
        native = native_filled_rectangle(raw, row["source_span"])
        poly_checks.append(native is None)
    check("intersecting_nonrectangle_polygons_remain_protected",
          len(nonrect_polys) == 2 and all(poly_checks),
          {"protected_polygon_count": len(nonrect_polys), "native_rectangle_checks": poly_checks})

    audit = {
        "schema": "crop-t02-org-inventory-audit/1",
        "scope": "ORG-only eligibility and source-binding check; no EDIT geometry, no candidate construction",
        "status": "PASS_ORG_SOURCE_RECTANGLE_AUDIT" if all(c["passed"] for c in checks) else "FAIL_ORG_SOURCE_RECTANGLE_AUDIT",
        "source_sha256": digest,
        "checks": checks,
        "verified_rectangle_candidates": len(parsed_sizes),
        "shared_kernel_note": "Native-coordinate geometry classification is recomputed from exact source spans without the Shapely/WKB rectangle classifier; inventory completeness and source-object enumeration still depend on native_inventory/2.",
        "limitations": [
            "This validates geometric source eligibility, not object ownership as a semantic PCB pad or electrical net.",
            "This source-span audit does not establish admissibility against the accepted T01 scene; the separate T02 composition audit checks that binding and scope.",
            "This does not validate any grown geometry, clearance, electrical behavior, native export, or manufacturing rule.",
        ],
    }
    audit_path = output / "fresh_org_source_audit.json"
    audit_path.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n")
    names = ["feature_dispositions.json", "fresh_org_source_audit.json", "inventory_report.json"]
    sums = "".join(
        f"{hashlib.sha256((output / name).read_bytes()).hexdigest()}  {name}\n"
        for name in names
    )
    (output / "SHA256SUMS.txt").write_text(sums)
    return audit


if __name__ == "__main__":
    result = run_audit()
    print(json.dumps(result, indent=2, sort_keys=True))
    raise SystemExit(0 if result["status"].startswith("PASS") else 1)
