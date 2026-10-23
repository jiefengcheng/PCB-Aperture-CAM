"""Small source-located ORG-only geometry operators for the G22 experiment."""
from __future__ import annotations

import hashlib
import json
import math
import re
import uuid

import sexpdata
from shapely import wkb
from shapely.geometry import LineString, Point
from shapely.ops import unary_union

from .native_inventory import arc_points, geometry as native_geometry, inventory, steps


SOURCE_ID_RE = re.compile(r"^([0-9a-f]{64}):bytes:(\d+):(\d+)$")
FIELD_RE = {
    "width": re.compile(rb"\(width\s+([-+0-9.eE]+)\)"),
    "end": re.compile(rb"\(end\s+([-+0-9.eE]+)\s+([-+0-9.eE]+)\)"),
}


def _named(node, name):
    return next((item for item in node if isinstance(item, list) and item and str(item[0]) == name), None)


def _point(node, name):
    item = _named(node, name)
    if item is None or len(item) < 3:
        raise ValueError(f"MISSING_{name.upper()}")
    return float(item[1]), float(item[2])


def _row_for_identity(inv, identity):
    rows = [row for row in inv["objects"] if row["id"] == identity]
    if len(rows) != 1:
        raise ValueError(f"SOURCE_IDENTITY_NOT_UNIQUE:{identity}")
    return rows[0]


def _raw_span(identity, row, expected_sha, raw):
    match = SOURCE_ID_RE.fullmatch(identity)
    if not match or match.group(1) != expected_sha or row["source_sha256"] != expected_sha:
        raise ValueError(f"SOURCE_REVISION_MISMATCH:{identity}")
    start, end = map(int, match.group(2, 3))
    if row["source_span"] != [start, end] or not 0 <= start < end <= len(raw):
        raise ValueError(f"SOURCE_LOCATOR_MISMATCH:{identity}")
    return start, end


def _round(value, digits=5):
    return round(float(value), digits)


def _source_nodes(raw, inv, source_hash):
    result = {}
    for row in inv["objects"]:
        if row.get("source_sha256") != source_hash:
            raise ValueError("MIXED_SOURCE_INVENTORY")
        a, b = row["source_span"]
        result[row["id"]] = (row, raw[a:b])
    return result


def _geometry_for_change(row, raw_object, kind, *, radius_delta=0.0, width_delta=0.0):
    node = sexpdata.loads(raw_object.decode("utf-8"))
    if kind == "gr_circle":
        if _named(node, "fill") is None or str(_named(node, "fill")[1]) not in ("yes", "solid"):
            raise ValueError("UNFILLED_SEED_CIRCLE")
        center = _point(node, "center")
        end = _point(node, "end")
        radius = math.dist(center, end)
        if radius <= 0 or radius_delta < 0:
            raise ValueError("INVALID_RADIUS_CHANGE")
        return Point(center).buffer(radius + radius_delta, quad_segs=steps(radius + radius_delta))
    if kind in ("segment", "arc"):
        start = _point(node, "start")
        end = _point(node, "end")
        coords = [start, end]
        if kind == "arc":
            coords = arc_points(start, _point(node, "mid"), end)
        width_form = _named(node, "width")
        if width_form is None:
            raise ValueError("MISSING_TRACE_WIDTH")
        width = float(width_form[1]) + width_delta
        if width <= 0:
            raise ValueError("NON_POSITIVE_TRACE_WIDTH")
        return LineString(coords).buffer(width / 2, quad_segs=steps(width / 2))
    raise ValueError(f"UNSUPPORTED_G22_OPERATOR_KIND:{kind}")


def _replace_object(raw_object: bytes, kind: str, radius_delta: float, width_delta: float) -> bytes:
    updated = raw_object
    if kind == "gr_circle" and radius_delta:
        node = sexpdata.loads(raw_object.decode("utf-8"))
        cx, cy = _point(node, "center")
        ex, ey = _point(node, "end")
        radius = math.dist((cx, cy), (ex, ey))
        if radius <= 0:
            raise ValueError("INVALID_SEED_RADIUS")
        ux, uy = (ex-cx)/radius, (ey-cy)/radius
        match = FIELD_RE["end"].search(updated)
        if not match:
            raise ValueError("SOURCE_END_FORM_NOT_FOUND")
        repl = f"(end {_round(cx + ux * (radius + radius_delta)):.5f} {_round(cy + uy * (radius + radius_delta)):.5f})".encode()
        updated = updated[:match.start()] + repl + updated[match.end():]
    elif kind in ("segment", "arc") and width_delta:
        match = FIELD_RE["width"].search(updated)
        if not match:
            raise ValueError("SOURCE_WIDTH_FORM_NOT_FOUND")
        width = float(match.group(1)) + width_delta
        repl = f"(width {width:.5f})".encode()
        updated = updated[:match.start()] + repl + updated[match.end():]
    return updated


def _blend_object(center, radius, member_key, op_index):
    if radius <= 0:
        raise ValueError("BLEND_RADIUS_MUST_BE_POSITIVE")
    cx, cy = map(_round, center)
    ex = _round(cx + radius)
    object_key = uuid.uuid5(uuid.NAMESPACE_URL, f"g22:{member_key}:blend:{op_index}:{cx:.5f}:{cy:.5f}:{radius:.5f}")
    return (f'\n (gr_circle (center {cx:.5f} {cy:.5f}) (end {ex:.5f} {cy:.5f}) '
            f'(stroke (width 0) (type solid)) (fill yes) (layer F.Cu) (uuid "{object_key}"))\n').encode()


def generate_org_candidate(org_bytes: bytes, source_hash: str, operations: dict,
                           *, blend_points=(), member_key="") -> tuple[bytes, dict]:
    """Apply declared operations to an ORG copy only; EDIT is not an argument.

    `operations` maps exact ORG source identities to `{radius_delta_mm, width_delta_mm}`.
    Only filled copper circles and supported segments/arcs are editable.
    """
    actual_hash = hashlib.sha256(org_bytes).hexdigest()
    if actual_hash != source_hash:
        raise ValueError("ORG_SOURCE_HASH_MISMATCH")
    inv = inventory(org_bytes)
    rows = {row["id"]: row for row in inv["objects"]}
    replacements, updated_geometries, provenance = [], [], []
    for identity in sorted(operations):
        if identity not in rows:
            raise ValueError(f"UNKNOWN_EDITABLE_OCCURRENCE:{identity}")
        row = rows[identity]
        if "F.Cu" not in row.get("layers", []) or row.get("coverage") != "GEOMETRY_AVAILABLE":
            raise ValueError(f"UNSUPPORTED_EDITABLE_OCCURRENCE:{identity}")
        radius_delta = float(operations[identity].get("radius_delta_mm", 0.0))
        width_delta = float(operations[identity].get("width_delta_mm", 0.0))
        if radius_delta < 0 or width_delta < 0:
            raise ValueError("CUTBACK_NOT_IN_THIS_OPERATOR_FAMILY")
        if radius_delta and row["kind"] != "gr_circle":
            raise ValueError("RADIUS_DELTA_REQUIRES_FILLED_CIRCLE")
        if width_delta and row["kind"] not in ("segment", "arc"):
            raise ValueError("WIDTH_DELTA_REQUIRES_TRACE")
        start, end = _raw_span(identity, row, source_hash, org_bytes)
        raw_object = org_bytes[start:end]
        modified = _replace_object(raw_object, row["kind"], radius_delta, width_delta)
        if modified != raw_object:
            replacements.append((start, end, modified))
            provenance.append({"source_identity": identity, "source_span": [start, end],
                               "source_sha256": source_hash, "kind": row["kind"],
                               "source_object_sha256": hashlib.sha256(raw_object).hexdigest(),
                               "radius_delta_mm": radius_delta, "width_delta_mm": width_delta})
        updated_geometries.append(_geometry_for_change(row, raw_object, row["kind"],
                                                        radius_delta=radius_delta, width_delta=width_delta))
    if any(a < end and start < b for i, (a, b, _) in enumerate(replacements)
           for start, end, _ in replacements[i+1:]):
        raise ValueError("OVERLAPPING_SOURCE_PATCHES")
    candidate = org_bytes
    for start, end, replacement in sorted(replacements, reverse=True):
        candidate = candidate[:start] + replacement + candidate[end:]
    additions = b"".join(_blend_object(point, float(r), member_key, i)
                         for i, (point, r) in enumerate(blend_points))
    if additions:
        insert_at = candidate.rfind(b")")
        if insert_at < 0:
            raise ValueError("BOARD_ROOT_CLOSE_NOT_FOUND")
        candidate = candidate[:insert_at] + additions + candidate[insert_at:]
    result = {"source_role": "ORG", "source_sha256": source_hash,
              "candidate_sha256": hashlib.sha256(candidate).hexdigest(),
              "editable_source_occurrences": provenance,
              "inserted_blend_features": [{"center_mm": list(map(_round, point)), "radius_mm": float(r),
                                            "generator": "ORG-derived local source junction; filled F.Cu circle hypothesis",
                                            "feature_sha256": hashlib.sha256(_blend_object(point, float(r), member_key, i)).hexdigest()}
                                           for i, (point, r) in enumerate(blend_points)],
              "geometry_operations": "Source-located replacements plus deterministic appended F.Cu graphics; every non-allowlisted source byte is preserved.",
              "edit_target_used_as_operator": False}
    return candidate, result


def supported_union(inv, window):
    from shapely.geometry import box
    clip = box(*window)
    geometries = []
    unsupported = []
    for row in inv["objects"]:
        if "F.Cu" not in row.get("layers", []):
            continue
        if row.get("geometry_sha256"):
            geom = wkb.loads(inv["payloads"][row["geometry_sha256"]])
            if geom.intersects(clip):
                geometries.append(geom.intersection(clip))
        elif row.get("coverage") != "GEOMETRY_AVAILABLE":
            unsupported.append({"identity": row["id"], "kind": row["kind"],
                                 "reason": row.get("unsupported_reason"), "source_span": row["source_span"]})
    return unary_union(geometries), unsupported
