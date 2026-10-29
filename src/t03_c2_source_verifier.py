"""Source-bound C2 preflight checks for the bounded T03 trace patch.

This module audits frozen inputs, source topology, inherited T02 findings and
saved-candidate serialization. It does not search for a route; it re-derives a
saved candidate from its frozen source and grid specification before checking it.
"""
from __future__ import annotations

from hashlib import sha256
from decimal import Decimal
import json
import math
from pathlib import Path
import re
from typing import Any
from zipfile import ZIP_STORED, ZipFile

from shapely import wkb
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union
from shapely.strtree import STRtree

from src.t03_route_preflight import (
    MAX_ADDED_SPANS,
    MAX_CANDIDATES,
    MAX_EXTENSION_MM,
    OFFSETS_MM,
    PORT_TRANSITION_BUFFER_MM,
    REGULAR_PORT_STEP_MM,
    ROUTE_TESSELLATION_TOLERANCE_MM,
    WIDTH_MM,
    SOURCE_GEOMETRY_TOLERANCE_MM,
    SOURCE_SPAN_UNION_TOLERANCE_MM2,
    SOURCE_SURFACE_TARGET_MM,
    PreflightError,
    Primitive,
    SourcePath,
    buffer_centerline,
    candidate_source_copper_by_id,
    construct_candidate_centerline,
    construct_candidate_centerline_source_spans,
    enumerate_cut_ports,
    verify_candidate_copper,
    verify_scene,
)


def _sha(data: bytes) -> str:
    return sha256(data).hexdigest()


def canonical_source_preflight_report_bytes(report: dict[str, Any]) -> bytes:
    """Return the single canonical byte representation used for report identity."""
    return (
        json.dumps(report, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n"
    ).encode("utf-8")


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _span(source_id: str) -> tuple[int, int]:
    match = re.search(r":bytes:(\d+):(\d+)$", source_id)
    if not match:
        raise PreflightError(f"INVALID_SOURCE_OCCURRENCE_ID:{source_id}")
    return int(match.group(1)), int(match.group(2))


def _source_record(source: bytes, source_id: str) -> bytes:
    start, end = _span(source_id)
    record = source[start:end]
    if not record:
        raise PreflightError(f"EMPTY_SOURCE_RECORD:{source_id}")
    return record


def _object_source_id(source_id: str) -> str:
    return source_id


def _downstream_source_suffix(source_geom, cut_xy: tuple[float, float], tangent_xy: tuple[float, float]):
    """Clip one source trace object to the downstream side of a cut plane."""
    tx, ty = tangent_xy
    norm = math.hypot(tx, ty)
    if norm <= 1e-15:
        raise PreflightError("C2_CUT_PORT_ZERO_TANGENT")
    tx, ty = tx / norm, ty / norm
    nx, ny = -ty, tx
    minx, miny, maxx, maxy = source_geom.bounds
    reach = max(maxx - minx, maxy - miny, *(math.dist(cut_xy, p) for p in ((minx,miny),(minx,maxy),(maxx,miny),(maxx,maxy)))) * 4.0 + 1.0
    x, y = cut_xy
    half_plane = Polygon((
        (x - nx * reach, y - ny * reach),
        (x + nx * reach, y + ny * reach),
        (x + nx * reach + tx * reach, y + ny * reach + ty * reach),
        (x - nx * reach + tx * reach, y - ny * reach + ty * reach),
    ))
    suffix = source_geom.intersection(half_plane)
    if suffix.is_empty or not suffix.is_valid:
        raise PreflightError("C2_FIXED_CUTPORT_SUFFIX_MISSING")
    return suffix


def _load_scene(package_manifest_path: Path):
    package_manifest_path = Path(package_manifest_path)
    root = package_manifest_path.resolve().parent
    scene_receipt = verify_scene(package_manifest_path)
    spec = _json(package_manifest_path)
    source_bytes = (root / spec["source"]["path"]).read_bytes()
    inventory_bytes = (root / spec["inventory"]["path"]).read_bytes()
    inventory = json.loads(inventory_bytes)
    rows = inventory["rows"]
    fcu_rows = [r for r in rows if "F.Cu" in r.get("layers", []) and r.get("coverage") == "GEOMETRY_AVAILABLE"]
    ids = [r.get("id") for r in fcu_rows]
    if len(ids) != len(set(ids)):
        raise PreflightError("DUPLICATE_ORG_FCU_SOURCE_ID")
    archive_path = root / spec["org_archive"]["path"]
    with ZipFile(archive_path) as archive:
        if archive.testzip() is not None:
            raise PreflightError("ORG_ARCHIVE_CRC")
        members = {n[:-4]: n for n in archive.namelist() if n.endswith(".wkb")}
        geometry_by_id = {}
        for row in fcu_rows:
            geom_hash = row.get("geometry_sha256")
            if not geom_hash or geom_hash not in members:
                raise PreflightError(f"ORG_GEOMETRY_UNBOUND:{row.get('id')}")
            data = archive.read(members[geom_hash])
            if _sha(data) != geom_hash:
                raise PreflightError(f"ORG_GEOMETRY_HASH:{row['id']}")
            geom = wkb.loads(data)
            if geom.is_empty or not geom.is_valid:
                raise PreflightError(f"ORG_GEOMETRY_INVALID:{row['id']}")
            geometry_by_id[row["id"]] = geom
    land_manifest = _json(root / spec["land_manifest"]["path"])
    land_root = root / spec["land_manifest"]["target_root"]
    lands = {}
    for target in land_manifest["targets"]:
        source_id = target["source_id"]
        path = land_root / Path(target["candidate_wkb_path"]).name
        data = path.read_bytes()
        if len(data) != target["candidate_wkb_bytes"] or _sha(data) != target["candidate_wkb_sha256"]:
            raise PreflightError(f"V69_LAND_HASH:{source_id}")
        geom = wkb.loads(data)
        if geom.is_empty or not geom.is_valid:
            raise PreflightError(f"V69_LAND_INVALID:{source_id}")
        lands[source_id] = geom
    return root, scene_receipt, spec, source_bytes, fcu_rows, geometry_by_id, lands


def _contact_census(
    fcu_rows: list[dict[str, Any]],
    geometry_by_id: dict[str, Any],
    lands: dict[str, Any],
    seed_ids: set[str],
) -> list[dict[str, Any]]:
    """Return every positive-area ORG/accepted-land contact touching a seed."""
    rows = fcu_rows
    geoms = [geometry_by_id[r["id"]] for r in rows]
    tree = STRtree(geoms)
    by_id = {r["id"]: geometry_by_id[r["id"]] for r in rows}
    all_features = [(r["id"], by_id[r["id"]], "ORG_FCU") for r in rows]
    all_features.extend((f"T02v69:{sid}", geom, "ACCEPTED_T02_LAND") for sid, geom in lands.items())
    # The R-tree contains source copper. Accepted lands are few and use direct
    # bounds checks, avoiding a second large index and keeping identities clear.
    results: dict[tuple[str, str], dict[str, Any]] = {}
    for source_id in sorted(seed_ids):
        source_geom = by_id[source_id]
        for index in tree.query(source_geom):
            row = rows[int(index)]
            other_id = row["id"]
            if other_id == source_id:
                continue
            other_geom = by_id[other_id]
            if not source_geom.intersects(other_geom):
                continue
            area = float(source_geom.intersection(other_geom).area)
            if area > 0:
                key = tuple(sorted((source_id, other_id)))
                results[key] = {"a": key[0], "b": key[1], "area_mm2": area, "kind": "ORG_FCU"}
        for land_id, land_geom in lands.items():
            if not source_geom.intersects(land_geom):
                continue
            area = float(source_geom.intersection(land_geom).area)
            if area > 0:
                a, b = sorted((source_id, f"T02v69:{land_id}"))
                results[(a, b)] = {"a": a, "b": b, "area_mm2": area, "kind": "ACCEPTED_T02_LAND"}
    return sorted(results.values(), key=lambda r: (r["a"], r["b"]))


def verify_c2_source_obligations(
    package_manifest_path: Path,
    witness_path: Path,
    future_work_items_path: Path,
    t02_review_issue_ids_path: Path,
    t02_checksum_manifest_path: Path,
) -> dict[str, Any]:
    """Verify the real C2 scene, patch identities, contacts and inherited ledger.

    The function returns diagnostics only. It never enumerates or constructs a
    route candidate.
    """
    root, scene_receipt, spec, source, fcu_rows, geometry_by_id, lands = _load_scene(package_manifest_path)
    witness = _json(Path(witness_path))
    future = _json(Path(future_work_items_path))
    issue_ids = _json(Path(t02_review_issue_ids_path))
    execution = _json(root / spec["execution_receipt"]["path"])
    witness_case = witness["c2_case"]
    expanded = list(witness_case["expanded_patch_source_ids"])
    branch_ids = [witness_case["fixed_upper_source_id"], witness_case["fixed_upper_external_branch_source_id"]]
    all_seed_ids = set(expanded + branch_ids)
    id_to_row = {r["id"]: r for r in fcu_rows}
    missing = sorted(all_seed_ids - set(id_to_row))
    if missing:
        raise PreflightError(f"C2_SOURCE_OBJECT_MISSING:{missing[0]}")

    source_text_hashes = witness["source_bindings"]["source_text_sha256_by_id"]
    source_geometry_hashes = witness["source_bindings"]["source_geometry_wkb_sha256_by_id"]
    native_records = witness_case["native_source_records"]
    widths: dict[str, float] = {}
    for source_id in sorted(all_seed_ids):
        if id_to_row[source_id].get("source_sha256") != spec["source"]["sha256"]:
            raise PreflightError(f"C2_SOURCE_HASH_BINDING:{source_id}")
        if id_to_row[source_id].get("geometry_sha256") != source_geometry_hashes[source_id]:
            raise PreflightError(f"C2_SOURCE_GEOMETRY_BINDING:{source_id}")
        record = _source_record(source, source_id)
        if _sha(record) != source_text_hashes[source_id]:
            raise PreflightError(f"C2_SOURCE_TEXT_BINDING:{source_id}")
        expected = native_records.get(source_id)
        if expected is None or expected.encode("utf-8") != record:
            raise PreflightError(f"C2_NATIVE_RECORD_BINDING:{source_id}")
        width = re.search(rb"\(width\s+([0-9]+(?:\.[0-9]+)?)\)", record)
        if not width:
            raise PreflightError(f"C2_SOURCE_WIDTH_UNAVAILABLE:{source_id}")
        widths[source_id] = float(width.group(1))
        if widths[source_id] != 0.10008:
            raise PreflightError(f"C2_SOURCE_WIDTH_MISMATCH:{source_id}:{widths[source_id]}")

    # Rebuild the ordered source-chain endpoint sequence from byte-bound native
    # records; the source's record order and each primitive's stored direction
    # are not assumed to equal route direction.
    route_order = expanded
    directed_endpoints = []
    for index, source_id in enumerate(route_order):
        record = _source_record(source, source_id).decode("utf-8")
        points = re.findall(r"\((?:start|mid|end)\s+(-?[0-9]+(?:\.[0-9]+)?)\s+(-?[0-9]+(?:\.[0-9]+)?)\)", record)
        if len(points) < 2:
            raise PreflightError(f"C2_ROUTE_ENDPOINTS_UNAVAILABLE:{source_id}")
        start_xy = tuple(map(float, points[0]))
        end_xy = tuple(map(float, points[-1]))
        if index in (0, 1, 2):
            directed_endpoints.append((end_xy, start_xy))
        else:
            directed_endpoints.append((end_xy, start_xy))
    chain_gaps = [
        {"from_source_id": route_order[i], "to_source_id": route_order[i + 1], "gap_mm": __import__("math").dist(directed_endpoints[i][1], directed_endpoints[i + 1][0])}
        for i in range(len(route_order) - 1)
    ]
    if any(row["gap_mm"] > 1e-9 for row in chain_gaps):
        raise PreflightError("C2_SOURCE_CHAIN_DISCONTINUITY")
    land_attachment_id = witness["source_bindings"]["accepted_target_land_source_id"]
    if land_attachment_id not in lands:
        raise PreflightError("C2_ACCEPTED_ATTACHMENT_LAND_MISSING")
    if not lands[land_attachment_id].covers(Point(directed_endpoints[0][0])):
        raise PreflightError("C2_SOURCE_CHAIN_START_OUTSIDE_ACCEPTED_LAND")
    cut_xy = tuple(map(float, witness_case["candidate_cut_port"]["coordinate_mm"]))
    vertical_record = _source_record(source, route_order[-1]).decode("utf-8")
    vertical_points = re.findall(r"\((?:start|mid|end)\s+(-?[0-9]+(?:\.[0-9]+)?)\s+(-?[0-9]+(?:\.[0-9]+)?)\)", vertical_record)
    vertical_a, vertical_b = tuple(map(float, vertical_points[0])), tuple(map(float, vertical_points[-1]))
    if abs(cut_xy[0] - vertical_a[0]) > 1e-9 or abs(cut_xy[0] - vertical_b[0]) > 1e-9 or not min(vertical_a[1], vertical_b[1]) < cut_xy[1] < max(vertical_a[1], vertical_b[1]):
        raise PreflightError("C2_CUT_PORT_NOT_INTERIOR_TO_BOUND_SOURCE_SPAN")
    transition_to_ends = [abs(cut_xy[1] - vertical_a[1]), abs(cut_xy[1] - vertical_b[1])]
    if min(transition_to_ends) < 0.1201:
        raise PreflightError("C2_CUT_PORT_TRANSITION_BUFFER")

    # Serialize the exact directed source-chain centerline for downstream
    # candidate corridor checks. Segment/arc sampling uses the same declared
    # sagitta tolerance as the route generator and remains source-record bound.
    source_path_coords: list[tuple[float, float]] = []
    source_primitives: list[Primitive] = []
    for source_id in route_order:
        record = _source_record(source, source_id).decode("utf-8")
        kind_match = re.search(r"\(\s*(segment|arc)\b", record)
        points = re.findall(r"\((?:start|mid|end)\s+(-?[0-9]+(?:\.[0-9]+)?)\s+(-?[0-9]+(?:\.[0-9]+)?)\)", record)
        if not kind_match or len(points) < 2:
            raise PreflightError(f"C2_CENTERLINE_SOURCE_UNSUPPORTED:{source_id}")
        native_points = [tuple(map(float, p)) for p in points]
        width_match = re.search(r"\(width\s+([0-9]+(?:\.[0-9]+)?)\)", record)
        if not width_match:
            raise PreflightError(f"C2_CENTERLINE_WIDTH_UNAVAILABLE:{source_id}")
        primitive = Primitive(
            source_id,
            kind_match.group(1),
            native_points[-1],
            native_points[0],
            float(width_match.group(1)),
            native_points[1] if kind_match.group(1) == "arc" else None,
        )
        source_primitives.append(primitive)
        if primitive.kind == "arc":
            _, radius, _, _ = primitive.arc
            max_step = math.sqrt(8.0 * ROUTE_TESSELLATION_TOLERANCE_MM * radius)
            pieces = max(1, math.ceil(primitive.length_mm / max_step))
        else:
            pieces = 1
        for i in range(pieces + 1):
            point = primitive.point(i / pieces)
            if source_path_coords and i == 0:
                if math.dist(source_path_coords[-1], point) > 1e-9:
                    raise PreflightError("C2_CENTERLINE_SOURCE_CHAIN_GAP")
                continue
            source_path_coords.append(point)
    source_path_centerline = LineString(source_path_coords)
    if source_path_centerline.is_empty or not source_path_centerline.is_valid:
        raise PreflightError("C2_SOURCE_PATH_CENTERLINE_INVALID")
    source_path_centerline_bytes = wkb.dumps(source_path_centerline, byte_order=0, output_dimension=2, include_srid=False)
    initial_patch_ids = list(witness_case["initial_patch_source_ids"])
    if route_order[:len(initial_patch_ids)] != initial_patch_ids:
        raise PreflightError("C2_INITIAL_PATCH_NOT_CHAIN_PREFIX")
    initial_patch_end_mm = sum(p.length_mm for p in source_primitives[:len(initial_patch_ids)])
    source_path = SourcePath(tuple(source_primitives), initial_patch_end_mm)
    eligible_cut_ports = []
    for port in enumerate_cut_ports(
        source_path,
        step_mm=REGULAR_PORT_STEP_MM,
        max_extension_mm=MAX_EXTENSION_MM,
        transition_buffer_mm=PORT_TRANSITION_BUFFER_MM,
        max_added_spans=MAX_ADDED_SPANS,
    ):
        if port.eligible:
            xy = source_path.point_at(float(port.distance_mm))
            tangent = source_path.tangent_at(float(port.distance_mm))
            eligible_cut_ports.append({
                "distance_mm": float(port.distance_mm),
                "extension_mm": float(port.extension_mm),
                "source_id": port.source_id,
                "coordinate_xy": list(xy),
                "tangent_xy": list(tangent),
                "status": "ELIGIBLE_BOUNDED_CUT_PORT",
            })
    if not eligible_cut_ports or len(eligible_cut_ports) * len(OFFSETS_MM) ** 3 > MAX_CANDIDATES:
        raise PreflightError("C2_BOUNDED_CANDIDATE_DOMAIN_INVALID")

    # Preserve the exact existing attachment as a narrowly scoped v15 port
    # exception. Both the unchanged ORG land contribution and accepted v69
    # land are represented; neither is omitted from the obstacle set.
    attachment_trace_id = witness_case["required_contact_pairs"][0]["a"]
    attachment_org_land_id = witness_case["required_contact_pairs"][0]["b"]
    if attachment_trace_id not in geometry_by_id or attachment_org_land_id not in geometry_by_id:
        raise PreflightError("C2_ATTACHMENT_SOURCE_GEOMETRY_MISSING")
    policy_bytes = (root / spec["policy"]["path"]).read_bytes()
    policy = json.loads(policy_bytes)
    port_radius = widths[attachment_trace_id] + float(policy["construction_gap_mm"])
    attachment_exceptions = []
    for kind, obstacle_id, obstacle_geom in (
        ("ORG_SOURCE_LAND", attachment_org_land_id, geometry_by_id[attachment_org_land_id]),
        ("ACCEPTED_T02_LAND", land_attachment_id, lands[land_attachment_id]),
    ):
        raw_contact = geometry_by_id[attachment_trace_id].intersection(obstacle_geom)
        if raw_contact.is_empty or raw_contact.area <= 0:
            raise PreflightError(f"C2_ATTACHMENT_CONTACT_MISSING:{kind}")
        exception_geom = raw_contact.buffer(port_radius, quad_segs=policy.get("quad_segs", 128))
        exception_bytes = wkb.dumps(exception_geom, byte_order=0, output_dimension=2, include_srid=False)
        attachment_exceptions.append({
            "kind": kind,
            "trace_source_id": attachment_trace_id,
            "obstacle_source_id": obstacle_id,
            "source_contact_area_mm2": float(raw_contact.area),
            "v15_port_buffer_radius_mm": port_radius,
            "allowed_contact_region_wkb_sha256": _sha(exception_bytes),
            "allowed_contact_region_bounds_mm": list(exception_geom.bounds),
        })

    # The vertical source occurrence crosses the cut port. Split its exact
    # source copper only for the patch contract: lower prefix is writable,
    # upper suffix remains protected and is bound by its WKB hash.
    vertical_geom = geometry_by_id[route_order[-1]]
    minx, miny, maxx, maxy = vertical_geom.bounds
    suffix_clip = box(minx - 1.0, cut_xy[1], maxx + 1.0, maxy + 1.0)
    vertical_suffix = vertical_geom.intersection(suffix_clip)
    if vertical_suffix.is_empty or not vertical_suffix.is_valid:
        raise PreflightError("C2_FIXED_CUTPORT_SUFFIX_MISSING")
    vertical_suffix_bytes = wkb.dumps(vertical_suffix, byte_order=0, output_dimension=2, include_srid=False)

    expected_fcu = int(spec["org_archive"]["fcu_object_count"])
    expected_lands = int(spec["land_manifest"]["target_count"])
    if len(fcu_rows) != expected_fcu or len(lands) != expected_lands:
        raise PreflightError("C2_EXHAUSTIVE_INPUT_COUNT_MISMATCH")

    # Source occurrence/inventory binding for every object, not just the patch.
    source_inventory_sha = _sha((root / spec["inventory"]["path"]).read_bytes())
    expected_inventory_sha = spec["inventory"]["sha256"]
    if source_inventory_sha != expected_inventory_sha:
        raise PreflightError("C2_INVENTORY_HASH_MISMATCH")

    # Recompute the local contact graph against every source object and all 80
    # accepted lands. The existing P1-P8 list is a required subset, not assumed
    # exhaustive; additional observed contacts remain protected and reported.
    contacts = _contact_census(fcu_rows, geometry_by_id, lands, all_seed_ids)
    expected_pairs = witness_case["required_contact_pairs"]
    contact_by_pair = {(r["a"], r["b"]): r for r in contacts}
    contact_checks = []
    for pair in expected_pairs:
        aid = pair["a"]
        bid = pair["b"]
        if aid in lands:
            aid = f"T02v69:{aid}"
        if bid in lands:
            bid = f"T02v69:{bid}"
        key = tuple(sorted((aid, bid)))
        observed = contact_by_pair.get(key)
        if observed is None:
            raise PreflightError(f"C2_REQUIRED_CONTACT_MISSING:{pair['id']}")
        if abs(observed["area_mm2"] - float(pair["area_mm2"])) > 1e-10:
            raise PreflightError(f"C2_REQUIRED_CONTACT_AREA_MISMATCH:{pair['id']}")
        writable_participant = aid in set(expanded) or bid in set(expanded)
        contact_checks.append({
            "id": pair["id"], "a": aid, "b": bid,
            "area_mm2": observed["area_mm2"],
            "geometry_policy": (
                "PRESERVE_POSITIVE_AREA_CONNECTION_WITHIN_DECLARED_PATCH"
                if writable_participant else "PRESERVE_EXACT_CONTACT_AREA"
            ),
            "status": "PASS_RECOMPUTED",
        })
    required_by_id = {row["id"]: row for row in contact_checks}
    fixed_branch_contact = required_by_id.get("P8_FIXED_UPPER_ARC_TO_EXTERNAL_BRANCH")
    if fixed_branch_contact is None or fixed_branch_contact["a"] not in branch_ids or fixed_branch_contact["b"] not in branch_ids:
        raise PreflightError("C2_FIXED_BRANCH_TOPOLOGY_UNBOUND")
    if set(branch_ids) & set(expanded):
        raise PreflightError("C2_FIXED_BRANCH_MARKED_WRITABLE")

    # Bind the complete inherited T02 findings instead of silently dropping
    # findings that are outside this one candidate's local patch.
    future_sha = _sha(Path(future_work_items_path).read_bytes())
    if future_sha != execution.get("future_trace_work_items_sha256"):
        raise PreflightError("INHERITED_V69_WORK_ITEMS_HASH_MISMATCH")
    if future.get("source_sha256") != spec["source"]["sha256"] or future.get("trace_changed_in_t02") is not False:
        raise PreflightError("INHERITED_V69_WORK_ITEMS_BINDING")
    clearances = future.get("clearance_issues", [])
    overlaps = future.get("items", [])
    if len(clearances) != execution.get("future_trace_clearance_issue_count"):
        raise PreflightError("INHERITED_V69_CLEARANCE_COUNT_MISMATCH")
    if len(overlaps) != execution.get("future_trace_overlap_count"):
        raise PreflightError("INHERITED_V69_OVERLAP_COUNT_MISMATCH")
    if len(issue_ids) != len(clearances):
        raise PreflightError("INHERITED_V69_REVIEW_ID_COUNT_MISMATCH")
    review_ids = [item.get("review_id") for item in issue_ids]
    if None in review_ids or len(review_ids) != len(set(review_ids)):
        raise PreflightError("INHERITED_V69_REVIEW_ID_SET_MISMATCH")
    # These are two distinct T02 registers: the execution-bound future-work
    # ledger and the separately identified review issue ledger. Keep both; do
    # not fabricate row-by-row equivalence or collapse their identities.
    checksum_rows = {}
    for line in Path(t02_checksum_manifest_path).read_text(encoding="utf-8").splitlines():
        match = re.match(r"^([0-9a-f]{64})  (.+)$", line)
        if match:
            checksum_rows[match.group(2)] = match.group(1)
    issue_rel = Path(t02_review_issue_ids_path).name
    if checksum_rows.get(issue_rel) != _sha(Path(t02_review_issue_ids_path).read_bytes()):
        raise PreflightError("INHERITED_V69_REVIEW_LEDGER_HASH_MISMATCH")
    patch_set = set(expanded)
    local_findings = []
    for row in clearances:
        if row.get("trace_source_id") in patch_set or row.get("rectangle_source_id") in patch_set:
            local_findings.append({"review_id": row.get("review_id"), "source_pair": [row.get("trace_source_id"), row.get("rectangle_source_id")], "status": row.get("status"), "disposition": row.get("disposition")})
    local_overlap_findings = []
    for row in overlaps:
        pair = set(row.get("source_ids", [])) | {row.get("a_source_id"), row.get("b_source_id"), row.get("trace_source_id"), row.get("rectangle_source_id")}
        pair.discard(None)
        if pair & patch_set:
            local_overlap_findings.append({"source_ids": sorted(pair), "status": row.get("status", "INHERITED_OPEN"), "kind": row.get("issue_type", row.get("kind", "T02_TRACE_OVERLAP"))})

    required_pairs = {(tuple(sorted((x["a"], x["b"])))) for x in contact_checks}
    extra_contacts = [c for c in contacts if tuple(sorted((c["a"], c["b"]))) not in required_pairs]
    p1_source_land_aliases = [c for c in extra_contacts if land_attachment_id in {c["a"], c["b"]}]
    additional_unlisted_source_contacts = [c for c in extra_contacts if c not in p1_source_land_aliases]
    extra_contact_source_records = []
    for source_id in sorted({sid for c in additional_unlisted_source_contacts for sid in (c["a"], c["b"])}):
        if source_id not in id_to_row:
            raise PreflightError(f"C2_ADDITIONAL_CONTACT_SOURCE_MISSING:{source_id}")
        record = _source_record(source, source_id)
        width_match = re.search(rb"\(width\s+([0-9]+(?:\.[0-9]+)?)\)", record)
        extra_contact_source_records.append({
            "source_id": source_id,
            "source_text_sha256": _sha(record),
            "geometry_sha256": id_to_row[source_id]["geometry_sha256"],
            "width_mm": float(width_match.group(1)) if width_match else None,
            "classification": "FIXED_PROTECTED_EXTERNAL_CONTINUATION",
        })
    source_dispositions = [
        {"source_id": row["id"], "geometry_sha256": row["geometry_sha256"], "kind": row["kind"], "disposition": "WRITABLE_PATCH_SOURCE" if row["id"] in patch_set else "PROTECTED_SOURCE"}
        for row in fcu_rows
    ]
    bound_land_hashes = {row["source_id"]: row["candidate_wkb_sha256"] for row in _json(root / spec["land_manifest"]["path"])["targets"]}
    land_dispositions = [
        {"source_id": sid, "wkb_sha256": bound_land_hashes[sid], "disposition": "FIXED_ACCEPTED_T02_LAND", "attachment_exception": sid == land_attachment_id}
        for sid, geom in sorted(lands.items())
    ]
    return {
        "status": "PASS_C2_SOURCE_BOUND_PREFLIGHT_OBLIGATIONS",
        "scene_status": scene_receipt["status"],
        "source_sha256": spec["source"]["sha256"],
        "inventory_sha256": source_inventory_sha,
        "org_fcu_object_count": len(fcu_rows),
        "accepted_v69_land_count": len(lands),
        "patch_source_ids": expanded,
        "fixed_boundary_source_ids": branch_ids,
        "source_widths_mm": widths,
        "source_width_preserved": all(v == 0.10008 for v in widths.values()),
        "clearance_policy": {
            "sha256": _sha(policy_bytes),
            "width_mm": 0.10008,
            "hard_floor_mm": float(policy["hard_experimental_gap_mm"]),
            "construction_target_mm": float(policy["construction_gap_mm"]),
            "numeric_tolerance_mm": float(policy["geometry_tolerance_mm"]),
            "quad_segs": int(policy["quad_segs"]),
            "measurement": "FINITE_WIDTH_COPPER_SURFACE",
        },
        "source_text_and_geometry_bindings": "PASS_ALL_SIX_SOURCE_RECORDS",
        "source_chain_endpoint_checks": {"directed_endpoints": [{"source_id": sid, "start_xy": list(directed_endpoints[i][0]), "end_xy": list(directed_endpoints[i][1])} for i, sid in enumerate(route_order)], "adjacent_gaps": chain_gaps, "accepted_land_id": land_attachment_id, "start_covered_by_accepted_land": True, "cut_port_xy": list(cut_xy), "cut_port_transition_clearance_to_ends_mm": transition_to_ends, "required_transition_buffer_mm": 0.1201},
        "attachment_exceptions": attachment_exceptions,
        "fixed_cutport_suffix": {"source_id": route_order[-1], "cut_port_xy": list(cut_xy), "protected_suffix_geometry_sha256": _sha(vertical_suffix_bytes), "protected_suffix_area_mm2": float(vertical_suffix.area), "status": "RETAIN_EXACT_SOURCE_COPPER_ABOVE_CUT_PORT"},
        "source_obstacle_partition": source_dispositions,
        "source_obstacle_partition_count": len(source_dispositions),
        "accepted_land_partition": land_dispositions,
        "accepted_land_partition_count": len(land_dispositions),
        "contact_census": contacts,
        "contact_census_count": len(contacts),
        "required_p1_p8_checks": contact_checks,
        "required_p1_p8_count": len(contact_checks),
        "source_topology": {
            "ordered_writable_chain_source_ids": route_order,
            "required_internal_and_attachment_edges": [row for row in contact_checks if row["id"] != "P8_FIXED_UPPER_ARC_TO_EXTERNAL_BRANCH"],
            "fixed_external_branch_edge": fixed_branch_contact,
            "fixed_branch_source_ids": branch_ids,
            "fixed_branch_excluded_from_writable_patch": True,
            "cut_port_inside_bound_vertical_source": True,
            "protected_suffix_geometry_sha256": _sha(vertical_suffix_bytes),
            "status": "PASS_SOURCE_TOPOLOGY_AND_CUTPORT_BINDING",
        },
        "source_path_centerline": {
            "coordinates": [list(point) for point in source_path_coords],
            "wkb_sha256": _sha(source_path_centerline_bytes),
            "native_primitives": [
                {
                    "source_id": primitive.source_id,
                    "kind": primitive.kind,
                    "start_xy": list(primitive.start),
                    "end_xy": list(primitive.end),
                    "mid_xy": list(primitive.mid) if primitive.mid is not None else None,
                    "width_mm": primitive.width_mm,
                }
                for primitive in source_primitives
            ],
            "tessellation_sagitta_mm": ROUTE_TESSELLATION_TOLERANCE_MM,
            "max_lateral_offset_mm": max(abs(float(value)) for value in OFFSETS_MM),
            "initial_patch_end_mm": initial_patch_end_mm,
            "eligible_cut_ports": eligible_cut_ports,
            "cut_port_grid_step_mm": float(REGULAR_PORT_STEP_MM),
            "max_extension_mm": float(MAX_EXTENSION_MM),
            "max_added_source_spans": MAX_ADDED_SPANS,
            "transition_buffer_mm": PORT_TRANSITION_BUFFER_MM,
            "candidate_budget": MAX_CANDIDATES,
            "precomputed_domain_size": len(eligible_cut_ports) * len(OFFSETS_MM) ** 3,
            "status": "PASS_NATIVE_RECORD_DERIVED_CENTERLINE",
        },
        "additional_contacts_beyond_p1_p8": extra_contacts,
        "p1_original_land_source_aliases": p1_source_land_aliases,
        "additional_unlisted_source_contacts": additional_unlisted_source_contacts,
        "additional_external_positive_area_contact_count": len(additional_unlisted_source_contacts),
        "additional_contact_source_records": extra_contact_source_records,
        "inherited_v69": {
            "future_work_items_sha256": future_sha,
            "clearance_issue_count": len(clearances),
            "overlap_item_count": len(overlaps),
            "review_issue_id_count": len(issue_ids),
            "review_issue_ids_sha256": _sha(Path(t02_review_issue_ids_path).read_bytes()),
            "review_issue_register_is_distinct_from_future_work_ledger": True,
            "all_findings_retained": True,
            "clearance_findings": clearances,
            "overlap_findings": overlaps,
            "local_patch_clearance_findings": local_findings,
            "local_patch_review_issues": [
                {"review_id": row["review_id"], "source_pair": [row.get("trace_source_id"), row.get("rectangle_source_id")], "status": row.get("status"), "disposition": row.get("disposition")}
                for row in issue_ids
                if row.get("trace_source_id") in patch_set or row.get("rectangle_source_id") in patch_set
            ],
            "local_patch_overlap_findings": local_overlap_findings,
            "unrelated_findings": "REMAIN_OPEN_AND_INHERITED; NO_BLANKET_WAIVER",
        },
        "p3_semantics": "NOT_ESTABLISHED; geometry is preserved as an obligation; no net inference",
        "electrical_intent": "NOT_ESTABLISHED",
        "route_search_executed": False,
        "route_geometry_created": False,
        "native_export_executed": False,
    }


def verify_saved_candidate_wkb(
    candidate_wkb: bytes,
    *,
    expected_sha256: str,
    expected_start_xy: tuple[float, float],
    expected_end_xy: tuple[float, float],
    max_width_mm: float = 0.10008,
) -> dict[str, Any]:
    """Validate deterministic saved geometry serialization and fixed ports.

    This focused function is reusable by a later candidate checker. It makes
    no route feasibility claim and does not perform a search.
    """
    if _sha(candidate_wkb) != expected_sha256:
        raise PreflightError("SAVED_CANDIDATE_HASH_MISMATCH")
    geom = wkb.loads(candidate_wkb)
    if geom.is_empty or not geom.is_valid or geom.geom_type != "LineString" or geom.length <= 0:
        raise PreflightError("SAVED_CANDIDATE_GEOMETRY_INVALID")
    coords = list(geom.coords)
    if (abs(coords[0][0] - expected_start_xy[0]) > 1e-9 or abs(coords[0][1] - expected_start_xy[1]) > 1e-9):
        raise PreflightError("SAVED_CANDIDATE_START_PORT_MISMATCH")
    if (abs(coords[-1][0] - expected_end_xy[0]) > 1e-9 or abs(coords[-1][1] - expected_end_xy[1]) > 1e-9):
        raise PreflightError("SAVED_CANDIDATE_END_PORT_MISMATCH")
    if max_width_mm != 0.10008:
        raise PreflightError("SAVED_CANDIDATE_WIDTH_POLICY_MISMATCH")
    return {
        "status": "PASS_SAVED_CANDIDATE_GEOMETRY_BINDING_ONLY",
        "candidate_sha256": expected_sha256,
        "geometry_type": geom.geom_type,
        "coordinate_count": len(coords),
        "length_mm": float(geom.length),
        "start_xy": list(coords[0]),
        "end_xy": list(coords[-1]),
        "width_mm": max_width_mm,
        "route_feasibility": "NOT_ESTABLISHED",
        "clearance": "NOT_CHECKED_BY_THIS_FUNCTION",
    }


def verify_saved_candidate_bundle(
    *,
    source_preflight_report: dict[str, Any],
    candidate_line_wkb: bytes,
    candidate_copper_wkb: bytes,
    expected_line_sha256: str,
    expected_copper_sha256: str,
    expected_start_xy: tuple[float, float],
    expected_end_xy: tuple[float, float],
    candidate_cut_port: dict[str, Any],
    candidate_offsets_mm: tuple[float, float, float],
    source_geometries: dict[str, Any],
    expected_source_ids: set[str],
    source_wkb_by_id: dict[str, bytes],
    expected_source_wkb_sha256: dict[str, str],
    writable_source_ids: set[str],
    result_source_geometries: dict[str, Any],
    accepted_lands: dict[str, Any],
    expected_land_ids: set[str],
    land_wkb_by_id: dict[str, bytes],
    expected_land_wkb_sha256: dict[str, str],
    result_lands: dict[str, Any],
    attachment_exception_regions: dict[str, Any],
    expected_attachment_exception_sha256: dict[str, str],
    required_contacts: list[dict[str, Any]],
    width_mm: float = WIDTH_MM,
    area_tolerance_mm2: float = 1e-12,
) -> dict[str, Any]:
    """End-to-end check of a *saved* C2 candidate bundle.

    The caller must provide complete, source-bound maps from the C2
    preflight: every ORG F.Cu object and all accepted v69 lands. The output
    source map retains the same source identities; only explicitly writable
    patch objects may differ. A split fixed suffix remains under its source
    identity and is checked separately from the replacement union. This
    validates geometry, not electrical intent or a native KiCad export.
    """
    if width_mm != WIDTH_MM:
        raise PreflightError("C2_CANDIDATE_WIDTH_POLICY_MISMATCH")
    if source_preflight_report.get("status") != "PASS_C2_SOURCE_BOUND_PREFLIGHT_OBLIGATIONS":
        raise PreflightError("C2_SOURCE_PREFLIGHT_NOT_PASS")
    clearance_policy = source_preflight_report.get("clearance_policy", {})
    if (
        clearance_policy.get("measurement") != "FINITE_WIDTH_COPPER_SURFACE"
        or clearance_policy.get("width_mm") != WIDTH_MM
        or clearance_policy.get("hard_floor_mm") != 0.02
        or clearance_policy.get("construction_target_mm") != 0.02002
        or clearance_policy.get("numeric_tolerance_mm") != 0.00001
    ):
        raise PreflightError("C2_CLEARANCE_POLICY_NOT_SOURCE_BOUND")
    if _sha(candidate_line_wkb) != expected_line_sha256:
        raise PreflightError("C2_CANDIDATE_LINE_HASH_MISMATCH")
    if _sha(candidate_copper_wkb) != expected_copper_sha256:
        raise PreflightError("C2_CANDIDATE_COPPER_HASH_MISMATCH")
    line = wkb.loads(candidate_line_wkb)
    copper = wkb.loads(candidate_copper_wkb)
    if (
        line.is_empty
        or not line.is_valid
        or line.geom_type != "LineString"
        or line.length <= 0
        or not line.is_simple
        or getattr(line, "has_z", False)
        or getattr(line, "has_m", False)
    ):
        raise PreflightError("C2_CANDIDATE_LINE_INVALID")
    if copper.is_empty or not copper.is_valid or copper.geom_type not in {"Polygon", "MultiPolygon"}:
        raise PreflightError("C2_CANDIDATE_COPPER_INVALID")
    coords = list(line.coords)
    if any(not all(math.isfinite(value) for value in point[:2]) for point in coords):
        raise PreflightError("C2_CANDIDATE_LINE_NONFINITE")
    if any(math.dist(left[:2], right[:2]) <= 0 for left, right in zip(coords, coords[1:])):
        raise PreflightError("C2_CANDIDATE_LINE_ZERO_LENGTH_SPAN")
    if math.dist(coords[0], expected_start_xy) > 1e-9:
        raise PreflightError("C2_CANDIDATE_START_PORT_MISMATCH")
    if math.dist(coords[-1], expected_end_xy) > 1e-9:
        raise PreflightError("C2_CANDIDATE_END_PORT_MISMATCH")
    endpoint_contract = source_preflight_report.get("source_chain_endpoint_checks", {})
    directed = endpoint_contract.get("directed_endpoints", [])
    if not directed or math.dist(expected_start_xy, tuple(directed[0]["start_xy"])) > 1e-9:
        raise PreflightError("C2_CANDIDATE_ENDPOINTS_NOT_PREFLIGHT_BOUND")
    source_path_info = source_preflight_report.get("source_path_centerline", {})
    eligible_ports = source_path_info.get("eligible_cut_ports", [])
    port_match = next((port for port in eligible_ports if port == candidate_cut_port), None)
    if port_match is None or math.dist(expected_end_xy, tuple(candidate_cut_port.get("coordinate_xy", (math.inf, math.inf)))) > 1e-9:
        raise PreflightError("C2_CANDIDATE_CUTPORT_NOT_IN_BOUNDED_DOMAIN")
    if math.dist(expected_end_xy, coords[-1]) > 1e-9:
        raise PreflightError("C2_CANDIDATE_END_PORT_MISMATCH")
    source_path = LineString(source_path_info.get("coordinates", []))
    source_path_bytes = wkb.dumps(source_path, byte_order=0, output_dimension=2, include_srid=False) if not source_path.is_empty else b""
    if (
        source_path_info.get("status") != "PASS_NATIVE_RECORD_DERIVED_CENTERLINE"
        or _sha(source_path_bytes) != source_path_info.get("wkb_sha256")
        or source_path.is_empty
        or not source_path.is_valid
    ):
        raise PreflightError("C2_SOURCE_PATH_CENTERLINE_NOT_PREFLIGHT_BOUND")
    max_lateral_offset = float(source_path_info["max_lateral_offset_mm"])
    path_tolerance = float(source_path_info["tessellation_sagitta_mm"])
    max_extension = float(source_path_info.get("max_extension_mm", -1))
    initial_patch_end = float(source_path_info.get("initial_patch_end_mm", -1))
    port_distance = float(candidate_cut_port.get("distance_mm", math.nan))
    port_extension = float(candidate_cut_port.get("extension_mm", math.nan))
    port_on_path_distance = source_path.project(Point(candidate_cut_port["coordinate_xy"]))
    if (
        max_lateral_offset != 0.25
        or path_tolerance != ROUTE_TESSELLATION_TOLERANCE_MM
        or max_extension != float(MAX_EXTENSION_MM)
        or initial_patch_end <= 0
        or not math.isfinite(port_distance)
        or not math.isfinite(port_extension)
        or port_extension < 0
        or port_extension > max_extension
        or abs(port_distance - initial_patch_end - port_extension) > 1e-9
        or port_distance > source_path.length + path_tolerance
        or abs(port_on_path_distance - port_distance) > path_tolerance + 1e-9
    ):
        raise PreflightError("C2_SOURCE_PATH_OFFSET_POLICY_MISMATCH")
    native_rows = source_path_info.get("native_primitives", [])
    try:
        native_primitives = tuple(
            Primitive(
                row["source_id"],
                row["kind"],
                tuple(map(float, row["start_xy"])),
                tuple(map(float, row["end_xy"])),
                float(row["width_mm"]),
                tuple(map(float, row["mid_xy"])) if row.get("mid_xy") is not None else None,
            )
            for row in native_rows
        )
        native_source_path = SourcePath(native_primitives, initial_patch_end)
    except (KeyError, TypeError, ValueError) as error:
        raise PreflightError("C2_SOURCE_PATH_NATIVE_PRIMITIVES_INVALID") from error
    native_ids = [primitive.source_id for primitive in native_primitives]
    topology_ids = source_preflight_report.get("source_topology", {}).get("ordered_writable_chain_source_ids", [])
    reported_patch_ids = source_preflight_report.get("patch_source_ids", [])
    if (
        not native_primitives
        or native_ids != topology_ids
        or native_ids != reported_patch_ids
        or set(native_ids) != writable_source_ids
    ):
        raise PreflightError("C2_SOURCE_PATH_NATIVE_PRIMITIVES_NOT_BOUND")
    reconstructed_coords: list[tuple[float, float]] = []
    for primitive in native_primitives:
        if primitive.kind == "arc":
            _, radius, _, _ = primitive.arc
            max_step = math.sqrt(8.0 * path_tolerance * radius)
            pieces = max(1, math.ceil(primitive.length_mm / max_step))
        else:
            pieces = 1
        for index in range(pieces + 1):
            point = primitive.point(index / pieces)
            if reconstructed_coords and index == 0:
                if math.dist(reconstructed_coords[-1], point) > 1e-9:
                    raise PreflightError("C2_SOURCE_PATH_NATIVE_CHAIN_GAP")
                continue
            reconstructed_coords.append(point)
    reconstructed_path = LineString(reconstructed_coords)
    reconstructed_path_bytes = wkb.dumps(reconstructed_path, byte_order=0, output_dimension=2, include_srid=False)
    if _sha(reconstructed_path_bytes) != source_path_info.get("wkb_sha256"):
        raise PreflightError("C2_SOURCE_PATH_NATIVE_GEOMETRY_MISMATCH")
    try:
        native_port_source_id = native_source_path.primitive_at(port_distance)[1].source_id
        native_start = native_source_path.point_at(0.0)
        native_cut = native_source_path.point_at(port_distance)
        native_tangent = native_source_path.tangent_at(port_distance)
    except PreflightError as error:
        raise PreflightError("C2_CANDIDATE_CUTPORT_NATIVE_GEOMETRY_MISMATCH") from error
    if (
        native_port_source_id != candidate_cut_port.get("source_id")
        or math.dist(native_start, expected_start_xy) > 1e-9
        or math.dist(native_cut, expected_end_xy) > 1e-9
        or math.dist(native_cut, tuple(candidate_cut_port["coordinate_xy"])) > 1e-9
        or math.dist(native_tangent, tuple(candidate_cut_port["tangent_xy"])) > 1e-9
    ):
        raise PreflightError("C2_CANDIDATE_CUTPORT_NATIVE_GEOMETRY_MISMATCH")
    try:
        offsets = tuple(Decimal(str(value)) for value in candidate_offsets_mm)
    except (TypeError, ValueError, ArithmeticError) as error:
        raise PreflightError("C2_CANDIDATE_OFFSET_GRID_INVALID") from error
    if len(offsets) != 3 or any(value not in OFFSETS_MM for value in offsets):
        raise PreflightError("C2_CANDIDATE_OFFSET_GRID_INVALID")
    route_corridor = source_path.buffer(max_lateral_offset + path_tolerance, quad_segs=256)
    if not route_corridor.covers(line):
        raise PreflightError("C2_CANDIDATE_OUTSIDE_SOURCE_CORRIDOR")
    expected_line = construct_candidate_centerline(
        native_source_path,
        port_distance,
        tuple(float(value) for value in offsets),
    )
    if not line.equals_exact(expected_line, tolerance=0.0):
        raise PreflightError("C2_CANDIDATE_DOES_NOT_MATCH_FROZEN_GRID_SPEC")
    expected_copper, quad_segs = buffer_centerline(line, width_mm)
    if not copper.equals(expected_copper):
        raise PreflightError("C2_CANDIDATE_COPPER_WIDTH_MISMATCH")

    # Bind each saved writable source identity to its exact generated route
    # span. The selected cut-source object is retained only as its fixed
    # downstream suffix; its generated prefix is attributed to the preceding
    # source span. Shared-boundary residue is assigned deterministically to the
    # first source identity; the explicit area tolerance is below 1e-15 mm².
    cut_source_id = candidate_cut_port["source_id"]
    if not result_source_geometries or set(result_source_geometries) != expected_source_ids:
        raise PreflightError("C2_RESULT_SOURCE_PARTITION_INCOMPLETE")
    _, generated_spans = construct_candidate_centerline_source_spans(
        native_source_path, port_distance, tuple(float(value) for value in offsets)
    )
    ordered_ids = [primitive.source_id for primitive in native_primitives]
    replacement_ids = ordered_ids[:-1]
    if set(replacement_ids) != writable_source_ids - {cut_source_id}:
        raise PreflightError("C2_CANDIDATE_REPLACEMENT_SOURCE_SET_MISMATCH")
    expected_replacement_geometries = candidate_source_copper_by_id(
        generated_spans, ordered_ids, cut_source_id, copper, width_mm=width_mm
    )
    generated_union = unary_union(list(expected_replacement_geometries.values()))
    if generated_union.symmetric_difference(copper).area > SOURCE_SPAN_UNION_TOLERANCE_MM2:
        raise PreflightError("C2_GENERATED_SOURCE_SPAN_UNION_MISMATCH")
    for source_id, expected_geometry in expected_replacement_geometries.items():
        if source_id == cut_source_id:
            continue  # Verified below together with the immutable suffix.
        if not result_source_geometries[source_id].equals(expected_geometry):
            raise PreflightError(f"C2_CANDIDATE_SOURCE_SPAN_ATTRIBUTION_MISMATCH:{source_id}")

    if not source_geometries or set(source_geometries) != expected_source_ids or set(source_geometries) != set(result_source_geometries):
        raise PreflightError("C2_RESULT_SOURCE_PARTITION_INCOMPLETE")
    if source_preflight_report.get("source_obstacle_partition_count") != len(expected_source_ids):
        raise PreflightError("C2_SOURCE_PREFLIGHT_OBJECT_COUNT_MISMATCH")
    preflight_source_hashes = {row["source_id"]: row["geometry_sha256"] for row in source_preflight_report.get("source_obstacle_partition", [])}
    if set(preflight_source_hashes) != expected_source_ids or preflight_source_hashes != expected_source_wkb_sha256:
        raise PreflightError("C2_SOURCE_HASHES_NOT_PREFLIGHT_BOUND")
    if set(source_preflight_report.get("patch_source_ids", [])) != writable_source_ids:
        raise PreflightError("C2_SOURCE_PREFLIGHT_WRITABLE_SET_MISMATCH")
    if set(source_wkb_by_id) != expected_source_ids or set(expected_source_wkb_sha256) != expected_source_ids:
        raise PreflightError("C2_SOURCE_WKB_PARTITION_INCOMPLETE")
    if not writable_source_ids or not writable_source_ids <= set(source_geometries):
        raise PreflightError("C2_WRITABLE_SOURCE_PARTITION_INVALID")
    if set(accepted_lands) != expected_land_ids or set(accepted_lands) != set(result_lands):
        raise PreflightError("C2_RESULT_ACCEPTED_LAND_PARTITION_INCOMPLETE")
    if source_preflight_report.get("accepted_land_partition_count") != len(expected_land_ids):
        raise PreflightError("C2_LAND_PREFLIGHT_COUNT_MISMATCH")
    preflight_land_hashes = {row["source_id"]: row["wkb_sha256"] for row in source_preflight_report.get("accepted_land_partition", [])}
    if set(preflight_land_hashes) != expected_land_ids or preflight_land_hashes != expected_land_wkb_sha256:
        raise PreflightError("C2_LAND_HASHES_NOT_PREFLIGHT_BOUND")
    if set(land_wkb_by_id) != expected_land_ids or set(expected_land_wkb_sha256) != expected_land_ids:
        raise PreflightError("C2_LAND_WKB_PARTITION_INCOMPLETE")
    if not accepted_lands:
        raise PreflightError("C2_ACCEPTED_LANDS_MISSING")
    preflight_contacts = source_preflight_report.get("contact_census", [])
    if source_preflight_report.get("contact_census_count") != len(required_contacts) or required_contacts != preflight_contacts:
        raise PreflightError("C2_REQUIRED_CONTACTS_NOT_PREFLIGHT_BOUND")
    cut_source_id = candidate_cut_port["source_id"]
    suffix_key = f"CUT_SUFFIX:{cut_source_id}"
    valid_exception_ids = set(source_geometries) | {f"T02v69:{land_id}" for land_id in accepted_lands}
    if not set(attachment_exception_regions) <= valid_exception_ids | {suffix_key}:
        raise PreflightError("C2_ATTACHMENT_EXCEPTION_ID_UNBOUND")
    preflight_exceptions = {}
    for item in source_preflight_report.get("attachment_exceptions", []):
        key = item["obstacle_source_id"]
        if item["kind"] == "ACCEPTED_T02_LAND":
            key = f"T02v69:{key}"
        preflight_exceptions[key] = item["allowed_contact_region_wkb_sha256"]
    for key, digest in preflight_exceptions.items():
        if expected_attachment_exception_sha256.get(key) != digest:
            raise PreflightError(f"C2_PREFLIGHT_ATTACHMENT_EXCEPTION_MISMATCH:{key}")

    for source_id, original in source_geometries.items():
        raw = source_wkb_by_id[source_id]
        if _sha(raw) != expected_source_wkb_sha256[source_id]:
            raise PreflightError(f"C2_SOURCE_WKB_HASH_MISMATCH:{source_id}")
        bound = wkb.loads(raw)
        result = result_source_geometries[source_id]
        if original is None or result is None or original.is_empty or result.is_empty or not original.is_valid or not result.is_valid:
            raise PreflightError(f"C2_RESULT_SOURCE_GEOMETRY_INVALID:{source_id}")
        if bound.is_empty or not bound.is_valid or not original.equals(bound):
            raise PreflightError(f"C2_SOURCE_GEOMETRY_BINDING_MISMATCH:{source_id}")
        if source_id not in writable_source_ids and not original.equals(result):
            raise PreflightError(f"C2_PROTECTED_SOURCE_CHANGED:{source_id}")
    for land_id, original in accepted_lands.items():
        raw = land_wkb_by_id[land_id]
        if _sha(raw) != expected_land_wkb_sha256[land_id]:
            raise PreflightError(f"C2_LAND_WKB_HASH_MISMATCH:{land_id}")
        bound = wkb.loads(raw)
        result = result_lands[land_id]
        if original is None or result is None or original.is_empty or result.is_empty or not original.is_valid or not result.is_valid:
            raise PreflightError(f"C2_RESULT_LAND_GEOMETRY_INVALID:{land_id}")
        if bound.is_empty or not bound.is_valid or not original.equals(bound):
            raise PreflightError(f"C2_LAND_GEOMETRY_BINDING_MISMATCH:{land_id}")
        if not original.equals(result):
            raise PreflightError(f"C2_ACCEPTED_LAND_CHANGED:{land_id}")

    protected_suffix = _downstream_source_suffix(
        source_geometries[cut_source_id],
        tuple(candidate_cut_port["coordinate_xy"]),
        tuple(candidate_cut_port["tangent_xy"]),
    )
    suffix_id = cut_source_id
    if suffix_id is not None and suffix_id not in writable_source_ids:
        raise PreflightError("C2_FIXED_SUFFIX_SOURCE_NOT_IN_PATCH")
    expected_cut_source = unary_union([
        expected_replacement_geometries[cut_source_id], protected_suffix,
    ])
    if not result_source_geometries[cut_source_id].equals(expected_cut_source):
        raise PreflightError("C2_CUT_SOURCE_PREFIX_SUFFIX_ATTRIBUTION_MISMATCH")
    patch_union = unary_union([result_source_geometries[source_id] for source_id in sorted(writable_source_ids)])
    expected_cumulative_patch = copper.union(protected_suffix)
    if patch_union.symmetric_difference(expected_cumulative_patch).area > SOURCE_SPAN_UNION_TOLERANCE_MM2:
        raise PreflightError("C2_RESULT_PATCH_DELTA_MISMATCH")
    endpoint_clearance_region = Point(expected_end_xy).buffer(width_mm / 2.0 + SOURCE_SURFACE_TARGET_MM + SOURCE_GEOMETRY_TOLERANCE_MM, quad_segs=256)
    expected_join = protected_suffix.intersection(endpoint_clearance_region)
    region = attachment_exception_regions.get(suffix_key)
    expected_region_hash = expected_attachment_exception_sha256.get(suffix_key)
    if expected_join.is_empty or expected_join.area <= 0:
        raise PreflightError("C2_FIXED_SUFFIX_ATTACHMENT_MISSING")
    if region is None or expected_region_hash is None:
        raise PreflightError("C2_FIXED_SUFFIX_ATTACHMENT_EXCEPTION_MISSING")
    if _sha(wkb.dumps(region, byte_order=0, output_dimension=2, include_srid=False)) != expected_region_hash:
        raise PreflightError("C2_FIXED_SUFFIX_ATTACHMENT_EXCEPTION_HASH_MISMATCH")
    if not region.equals(expected_join):
        raise PreflightError("C2_FIXED_SUFFIX_ATTACHMENT_EXCEPTION_SCOPE")
    suffix_contact = copper.intersection(protected_suffix)
    if suffix_contact.area <= area_tolerance_mm2:
        raise PreflightError("C2_FIXED_SUFFIX_CONNECTIVITY_MISSING")
    if not region.covers(suffix_contact):
        raise PreflightError("C2_FIXED_SUFFIX_CONNECTIVITY_OUTSIDE_PORT_REGION")

    # Prove the obstacle map is exhaustive and each exception is explicitly
    # bounded. Patch sources remain present in the partition but are writable.
    obstacles: list[dict[str, Any]] = []
    for source_id, geom in source_geometries.items():
        if source_id in writable_source_ids:
            disposition = "writable"
        elif source_id in attachment_exception_regions:
            disposition = "attachment_exception"
        else:
            disposition = "protected"
        row = {"source_id": source_id, "geometry": geom, "disposition": disposition}
        if disposition == "attachment_exception":
            region = attachment_exception_regions[source_id]
            expected_region_hash = expected_attachment_exception_sha256.get(source_id)
            if expected_region_hash is None or _sha(wkb.dumps(region, byte_order=0, output_dimension=2, include_srid=False)) != expected_region_hash:
                raise PreflightError(f"C2_ATTACHMENT_EXCEPTION_HASH_MISMATCH:{source_id}")
            row["allowed_contact_region"] = region
        obstacles.append(row)
    for land_id, geom in accepted_lands.items():
        source_id = f"T02v69:{land_id}"
        if source_id in attachment_exception_regions:
            region = attachment_exception_regions[source_id]
            expected_region_hash = expected_attachment_exception_sha256.get(source_id)
            if expected_region_hash is None or _sha(wkb.dumps(region, byte_order=0, output_dimension=2, include_srid=False)) != expected_region_hash:
                raise PreflightError(f"C2_ATTACHMENT_EXCEPTION_HASH_MISMATCH:{source_id}")
            obstacles.append({"source_id": source_id, "geometry": geom, "disposition": "attachment_exception", "allowed_contact_region": region})
        else:
            obstacles.append({"source_id": source_id, "geometry": geom, "disposition": "protected"})
    obstacles.append({
        "source_id": suffix_key,
        "geometry": protected_suffix,
        "disposition": "attachment_exception",
        "allowed_contact_region": attachment_exception_regions[suffix_key],
    })
    clearance = verify_candidate_copper(
        line,
        copper,
        obstacles,
        width_mm=width_mm,
        hard_floor_mm=float(clearance_policy["hard_floor_mm"]),
        construction_target_mm=float(clearance_policy["construction_target_mm"]),
        numeric_tolerance_mm=float(clearance_policy["numeric_tolerance_mm"]),
    )
    if clearance["status"] != "PASS_GEOMETRIC_CLEARANCE_ONLY":
        raise PreflightError(f"C2_CANDIDATE_CLEARANCE_NOT_PASS:{clearance['status']}")

    # Check declared source contacts against the candidate replacement plus
    # unchanged scene. Protected-to-protected areas remain exact; a declared
    # writable-chain join only needs positive-area continuity. No net inference.
    result_features = dict(result_source_geometries)
    result_features.update({f"T02v69:{sid}": geom for sid, geom in result_lands.items()})
    contact_results = _verify_contact_obligations(
        required_contacts=required_contacts,
        original_features={**source_geometries, **{f"T02v69:{sid}": geom for sid, geom in accepted_lands.items()}},
        result_features=result_features,
        writable_source_ids=writable_source_ids,
        attachment_exception_regions=attachment_exception_regions,
        area_tolerance_mm2=area_tolerance_mm2,
    )
    inherited_comparison = _classify_inherited_v69_findings(
        source_preflight_report=source_preflight_report,
        source_geometries=source_geometries,
        accepted_lands=accepted_lands,
        candidate_copper=copper,
        result_source_geometries=result_source_geometries,
        writable_source_ids=writable_source_ids,
        attachment_exception_regions=attachment_exception_regions,
        hard_floor_mm=float(clearance_policy["hard_floor_mm"]),
        numeric_tolerance_mm=float(clearance_policy["numeric_tolerance_mm"]),
    )

    return {
        "status": "PASS_SAVED_C2_CANDIDATE_GEOMETRY",
        "candidate_line_sha256": expected_line_sha256,
        "candidate_copper_sha256": expected_copper_sha256,
        "candidate_offsets_mm": [float(value) for value in offsets],
        "width_mm": width_mm,
        "line_length_mm": float(line.length),
        "coordinate_count": len(coords),
        "buffer_quad_segs": quad_segs,
        "corridor": "PASS_SOURCE_BOUND",
        "source_preflight_status": source_preflight_report["status"],
        "clearance_policy_sha256": clearance_policy["sha256"],
        "source_object_count": len(source_geometries),
        "writable_source_ids": sorted(writable_source_ids),
        "protected_source_count": len(source_geometries) - len(writable_source_ids),
        "accepted_land_count": len(accepted_lands),
        "protected_sources_and_lands": "PASS_EXACT_GEOMETRIC_PRESERVATION",
        "clearance": clearance,
        "required_contacts": contact_results,
        "source_contact_census_count": len(contact_results),
        "inherited_v69_candidate_comparison": inherited_comparison,
        "electrical_intent": "NOT_ESTABLISHED",
        "native_export": "NOT_RUN",
    }


def write_candidate_geometry_archive(
    output_path: Path,
    *,
    candidate_line_wkb: bytes,
    candidate_copper_wkb: bytes,
    candidate_cut_port: dict[str, Any],
    candidate_offsets_mm: tuple[float, float, float],
    source_preflight_report: dict[str, Any],
    result_source_geometries: dict[str, Any],
    result_lands: dict[str, Any],
    attachment_exception_regions: dict[str, Any],
) -> str:
    """Write a deterministic geometry-only archive for a later verifier run.

    The source preflight and original source/land maps remain external inputs;
    the archive stores only the proposed cumulative result geometries.
    """
    import io
    import zipfile

    members: dict[str, bytes] = {
        "candidate/line.wkb": candidate_line_wkb,
        "candidate/copper.wkb": candidate_copper_wkb,
    }
    for prefix, geometries in (
        ("result/source", result_source_geometries),
        ("result/lands", result_lands),
        ("exceptions", attachment_exception_regions),
    ):
        for identity, geom in geometries.items():
            key = _sha(identity.encode("utf-8"))
            members[f"{prefix}/{key}.wkb"] = wkb.dumps(geom, byte_order=0, output_dimension=2, include_srid=False)
    manifest = {
        "schema": "T03_C2_SAVED_GEOMETRY_ARCHIVE_V1",
        "source_preflight_report_sha256": _sha(canonical_source_preflight_report_bytes(source_preflight_report)),
        "candidate_spec": {
            "cut_port": candidate_cut_port,
            "offsets_mm": [float(value) for value in candidate_offsets_mm],
        },
        "members": {name: _sha(data) for name, data in sorted(members.items())},
        "identity_members": {
            prefix: {_sha(identity.encode("utf-8")): identity for identity in sorted(geometries)}
            for prefix, geometries in (
                ("result/source", result_source_geometries),
                ("result/lands", result_lands),
                ("exceptions", attachment_exception_regions),
            )
        },
    }
    members["manifest.json"] = (json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output_path, "w", compression=ZIP_STORED) as archive:
        for name, data in sorted(members.items()):
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_STORED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data)
    return _sha(output_path.read_bytes())


def _verify_contact_obligations(
    *,
    required_contacts: list[dict[str, Any]],
    original_features: dict[str, Any],
    result_features: dict[str, Any],
    writable_source_ids: set[str],
    attachment_exception_regions: dict[str, Any],
    area_tolerance_mm2: float,
) -> list[dict[str, Any]]:
    """Keep protected contacts exact while permitting declared patch joins to change area.

    The contact census itself is source-bound and exhaustive for the selected
    C2 boundary. Only contacts that touch a writable source receive the
    positive-area continuity rule; protected-to-protected contacts retain
    exact area equality. A preflight exception, when present for the other
    endpoint, bounds the location of the changed contact.
    """
    rows = []
    for contact in required_contacts:
        aid, bid = contact["a"], contact["b"]
        contact_id = contact.get("id") or _stable_contact_id(aid, bid)
        contact_label = f"{contact_id}[{aid}|{bid}]"
        if aid not in result_features or bid not in result_features:
            raise PreflightError(f"C2_REQUIRED_RESULT_CONTACT_MISSING:{contact_label}")
        intersection = result_features[aid].intersection(result_features[bid])
        area = float(intersection.area)
        expected_area = float(contact["area_mm2"])
        mutable_join = aid in writable_source_ids or bid in writable_source_ids
        if mutable_join:
            if area <= area_tolerance_mm2:
                raise PreflightError(f"C2_REQUIRED_RESULT_CONTACT_DISCONNECTED:{contact_label}")
            exception = attachment_exception_regions.get(aid) or attachment_exception_regions.get(bid)
            if exception is not None and not exception.covers(intersection):
                raise PreflightError(f"C2_REQUIRED_RESULT_CONTACT_OUTSIDE_EXCEPTION:{contact_label}")
            policy = "PRESERVE_POSITIVE_AREA_CONNECTION_WITHIN_DECLARED_PATCH"
        else:
            if aid not in original_features or bid not in original_features:
                raise PreflightError(f"C2_PROTECTED_CONTACT_SOURCE_MISSING:{contact.get('id', '?')}")
            original_area = float(original_features[aid].intersection(original_features[bid]).area)
            if abs(original_area - expected_area) > max(area_tolerance_mm2, 1e-10):
                raise PreflightError(f"C2_PROTECTED_CONTACT_BASELINE_MISMATCH:{contact.get('id', '?')}")
            if abs(area - expected_area) > max(area_tolerance_mm2, 1e-10):
                raise PreflightError(f"C2_PROTECTED_CONTACT_AREA_CHANGED:{contact.get('id', '?')}")
            policy = "PRESERVE_EXACT_CONTACT_AREA"
        rows.append({
            "id": contact_id, "a": aid, "b": bid,
            "original_area_mm2": expected_area,
            "result_area_mm2": area,
            "geometry_policy": policy,
            "status": "PASS_GEOMETRIC_CONTACT_RETAINED",
        })
    return rows


def _stable_contact_id(aid: str, bid: str) -> str:
    """Derive a stable diagnostic ID when a legacy census row has no ID."""
    pair = sorted((str(aid), str(bid)))
    payload = json.dumps(pair, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return f"CONTACT-{_sha(payload)[:16]}"


def _classify_inherited_v69_findings(
    *,
    source_preflight_report: dict[str, Any],
    source_geometries: dict[str, Any],
    accepted_lands: dict[str, Any],
    candidate_copper: Any,
    result_source_geometries: dict[str, Any],
    writable_source_ids: set[str],
    attachment_exception_regions: dict[str, Any],
    hard_floor_mm: float,
    numeric_tolerance_mm: float,
) -> dict[str, Any]:
    """Compare inherited findings at canonical writable-chain/target scope.

    The original T02 OPEN rows are retained verbatim in the preflight report.
    Affected writable trace spans are grouped by protected target and the
    complete candidate replacement is measured once per group. This layer
    adds candidate-local group measurements without inventing per-source
    correspondence or rewriting historical dispositions.
    """
    inherited = source_preflight_report.get("inherited_v69", {})
    clearances = inherited.get("clearance_findings", [])
    overlaps = inherited.get("overlap_findings", [])
    contact_pairs = {
        tuple(sorted((row["a"], row["b"])))
        for row in source_preflight_report.get("contact_census", [])
    }
    output_clearances = []
    new_or_worsened = []
    # A candidate replaces a connected writable chain, not one source object
    # at a time. Group every affected trace-to-land ledger row by the protected
    # target and measure the replacement conductor once against that target.
    # The source-pair ledger rows remain individually retained as provenance;
    # the new disposition is explicitly scoped to their canonical interaction
    # group, so it cannot imply that the complete replacement belonged to each
    # individual source span.
    clearance_group_sources: dict[str, set[str]] = {}
    for item in clearances:
        trace_id, rect_id = item.get("trace_source_id"), item.get("rectangle_source_id")
        if trace_id in writable_source_ids:
            if rect_id in writable_source_ids:
                raise PreflightError("C2_INHERITED_GROUP_TARGET_MUST_BE_PROTECTED")
            clearance_group_sources.setdefault(rect_id, set()).add(trace_id)
    overlap_group_sources: dict[str, set[str]] = {}
    for item in overlaps:
        trace_id, rect_id = item.get("trace_source_id"), item.get("rectangle_source_id")
        if trace_id in writable_source_ids:
            if rect_id in writable_source_ids:
                raise PreflightError("C2_INHERITED_GROUP_TARGET_MUST_BE_PROTECTED")
            overlap_group_sources.setdefault(rect_id, set()).add(trace_id)

    clearance_group_measurements: dict[str, dict[str, Any]] = {}
    overlap_group_measurements: dict[str, dict[str, Any]] = {}
    for row in clearances:
        trace_id = row.get("trace_source_id")
        rect_id = row.get("rectangle_source_id")
        if trace_id not in source_geometries or rect_id not in source_geometries:
            raise PreflightError("C2_INHERITED_CLEARANCE_SOURCE_ID_UNBOUND")
        affected = trace_id in writable_source_ids or rect_id in writable_source_ids
        if not affected:
            output_clearances.append({
                "source_pair": [trace_id, rect_id],
                "classification": "INHERITED_OPEN_UNAFFECTED",
                "inherited_status": row.get("status"),
                "inherited_disposition": row.get("disposition"),
                "measurement": "NOT_REMEASURED_UNAFFECTED_SOURCE",
            })
            continue
        if rect_id in writable_source_ids:
            raise PreflightError("C2_INHERITED_GROUP_TARGET_MUST_BE_PROTECTED")
        before_target = accepted_lands.get(rect_id, source_geometries[rect_id])
        target = accepted_lands.get(
            rect_id,
            result_source_geometries[rect_id] if rect_id in writable_source_ids else source_geometries[rect_id],
        )
        before_gap = float(source_geometries[trace_id].distance(before_target))
        recorded_before_gap = row.get("final_surface_gap_mm")
        if recorded_before_gap is not None and abs(before_gap - float(recorded_before_gap)) > numeric_tolerance_mm:
            raise PreflightError(f"C2_INHERITED_CLEARANCE_BASELINE_MISMATCH:{trace_id}:{rect_id}")
        if trace_id in writable_source_ids:
            group = clearance_group_measurements.get(rect_id)
            if group is None:
                source_ids = sorted(clearance_group_sources[rect_id])
                before_group = unary_union([source_geometries[sid] for sid in source_ids])
                before_group_gap = float(before_group.distance(before_target))
                after_group_gap = float(candidate_copper.distance(target))
                group_overlap = candidate_copper.intersection(target)
                group_overlap_area = float(group_overlap.area)
                declared_regions = []
                for member_id in source_ids:
                    member_rows = [r for r in clearances if r.get("trace_source_id") == member_id and r.get("rectangle_source_id") == rect_id]
                    member_declared = any(
                        bool(r.get("original_attachment"))
                        and tuple(sorted((member_id, rect_id))) in contact_pairs
                        or bool(r.get("original_attachment"))
                        and tuple(sorted((member_id, f"T02v69:{rect_id}"))) in contact_pairs
                        for r in member_rows
                    )
                    if member_declared:
                        declared_regions.append(
                            attachment_exception_regions.get(f"T02v69:{rect_id}")
                            or attachment_exception_regions.get(rect_id)
                            or source_geometries[member_id].intersection(before_target)
                        )
                declared_region = unary_union(declared_regions) if declared_regions else None
                has_declared_attachment = bool(declared_regions)
                is_group_attachment = (
                    before_group.intersection(before_target).area > 0.0
                    and group_overlap_area > 0.0
                    and declared_region is not None
                    and declared_region.covers(group_overlap)
                )
                if has_declared_attachment and group_overlap_area > 0.0 and not is_group_attachment:
                    new_or_worsened.append(["WRITABLE_TRACE_GROUP", rect_id, "UNAUTHORIZED_SOURCE_ATTACHMENT_CONTACT"])
                if group_overlap_area > 0.0 and not is_group_attachment and before_group.intersection(before_target).area <= max(numeric_tolerance_mm, 1e-12):
                    new_or_worsened.append(["WRITABLE_TRACE_GROUP", rect_id, "UNAUTHORIZED_NEW_OVERLAP"])
                if is_group_attachment:
                    group_classification = "AUTHORIZED_SOURCE_ATTACHMENT_CONTACT"
                elif after_group_gap < hard_floor_mm:
                    if before_group_gap >= hard_floor_mm:
                        group_classification = "NEW_BELOW_HARD_FLOOR"
                        new_or_worsened.append(["WRITABLE_TRACE_GROUP", rect_id, group_classification])
                    elif after_group_gap < before_group_gap - numeric_tolerance_mm:
                        group_classification = "WORSENED_INHERITED_VIOLATION"
                        new_or_worsened.append(["WRITABLE_TRACE_GROUP", rect_id, group_classification])
                    else:
                        group_classification = "INHERITED_OPEN_NOT_WORSENED"
                elif before_group_gap < hard_floor_mm:
                    group_classification = "RESOLVED_IN_CANDIDATE"
                else:
                    group_classification = "PASS_NO_NEW_CLEARANCE_VIOLATION"
                group = {
                    "group_id": f"CLEARANCE:{rect_id}",
                    "target_source_id": rect_id,
                    "source_trace_ids": source_ids,
                    "before_surface_gap_mm": before_group_gap,
                    "after_surface_gap_mm": after_group_gap,
                    "after_overlap_area_mm2": group_overlap_area,
                    "classification": group_classification,
                    "measurement_scope": "CANONICAL_WRITABLE_CHAIN_VS_PROTECTED_TARGET",
                }
                clearance_group_measurements[rect_id] = group
            after_gap = float(group["after_surface_gap_mm"])
            overlap_area = float(group["after_overlap_area_mm2"])
            classification = str(group["classification"])
            original_attachment_area = float(source_geometries[trace_id].intersection(before_target).area)
            is_declared_attachment = classification == "AUTHORIZED_SOURCE_ATTACHMENT_CONTACT"
            row_before_gap = before_gap
        else:
            result_trace = result_source_geometries[trace_id]
            after_gap = float(result_trace.distance(target))
            overlap = result_trace.intersection(target)
            overlap_area = float(overlap.area)
            original_attachment_area = float(source_geometries[trace_id].intersection(before_target).area)
            contact_region = (
                attachment_exception_regions.get(f"T02v69:{rect_id}")
                or attachment_exception_regions.get(rect_id)
                or source_geometries[trace_id].intersection(before_target)
            )
            is_declared_attachment = (
                bool(row.get("original_attachment"))
                and (
                    tuple(sorted((trace_id, rect_id))) in contact_pairs
                    or tuple(sorted((trace_id, f"T02v69:{rect_id}"))) in contact_pairs
                )
                and original_attachment_area > 0.0
                and overlap_area > 0.0
                and contact_region.covers(overlap)
            )
            if row.get("original_attachment") and overlap_area > 0.0 and not is_declared_attachment:
                new_or_worsened.append([trace_id, rect_id, "UNAUTHORIZED_SOURCE_ATTACHMENT_CONTACT"])
            if is_declared_attachment:
                classification = "AUTHORIZED_SOURCE_ATTACHMENT_CONTACT"
            elif after_gap < hard_floor_mm:
                if before_gap >= hard_floor_mm:
                    classification = "NEW_BELOW_HARD_FLOOR"
                    new_or_worsened.append([trace_id, rect_id, classification])
                elif after_gap < before_gap - numeric_tolerance_mm:
                    classification = "WORSENED_INHERITED_VIOLATION"
                    new_or_worsened.append([trace_id, rect_id, classification])
                else:
                    classification = "INHERITED_OPEN_NOT_WORSENED"
            elif before_gap < hard_floor_mm:
                classification = "RESOLVED_IN_CANDIDATE"
            else:
                classification = "PASS_NO_NEW_CLEARANCE_VIOLATION"
            row_before_gap = before_gap
        output_clearances.append({
            "source_pair": [trace_id, rect_id],
            "interaction_group_id": f"CLEARANCE:{rect_id}" if trace_id in writable_source_ids else None,
            "classification_scope": "CANONICAL_WRITABLE_CHAIN_VS_PROTECTED_TARGET" if trace_id in writable_source_ids else "SOURCE_PAIR",
            "group_classification": classification,
            "inherited_status": row.get("status"),
            "inherited_disposition": row.get("disposition"),
            "inherited_open_disposition_preserved": row.get("disposition") in {
                "DEFERRED_TO_FUTURE_TRACE_SESSION", "OPEN_FUTURE_TRACE_SESSION", "OPEN"
            },
            "before_surface_gap_mm": row_before_gap,
            "before_group_surface_gap_mm": group.get("before_surface_gap_mm") if trace_id in writable_source_ids else None,
            "inherited_recorded_surface_gap_mm": recorded_before_gap,
            "after_surface_gap_mm": after_gap,
            "after_overlap_area_mm2": overlap_area,
            "source_attachment_area_mm2": original_attachment_area,
            "measurement": "FINITE_WIDTH_COPPER_SURFACE",
        })
    output_overlaps = []
    for row in overlaps:
        trace_id = row.get("trace_source_id")
        rect_id = row.get("rectangle_source_id")
        if trace_id not in source_geometries or rect_id not in source_geometries:
            raise PreflightError("C2_INHERITED_OVERLAP_SOURCE_ID_UNBOUND")
        affected = trace_id in writable_source_ids or rect_id in writable_source_ids
        if not affected:
            output_overlaps.append({
                "source_pair": [trace_id, rect_id],
                "classification": "INHERITED_OPEN_UNAFFECTED",
                "inherited_status": row.get("status"),
                "inherited_disposition": row.get("disposition"),
                "measurement": "NOT_REMEASURED_UNAFFECTED_SOURCE",
            })
            continue
        if rect_id in writable_source_ids:
            raise PreflightError("C2_INHERITED_GROUP_TARGET_MUST_BE_PROTECTED")
        before_target = accepted_lands.get(rect_id, source_geometries[rect_id])
        target = accepted_lands.get(
            rect_id,
            result_source_geometries[rect_id] if rect_id in writable_source_ids else source_geometries[rect_id],
        )
        before_area = float(source_geometries[trace_id].intersection(before_target).area)
        recorded_before_area = row.get("overlap_area_mm2")
        if recorded_before_area is not None and abs(before_area - float(recorded_before_area)) > max(numeric_tolerance_mm, 1e-12):
            raise PreflightError(f"C2_INHERITED_OVERLAP_BASELINE_MISMATCH:{trace_id}:{rect_id}")
        if trace_id in writable_source_ids:
            group = overlap_group_measurements.get(rect_id)
            if group is None:
                source_ids = sorted(overlap_group_sources[rect_id])
                before_group = unary_union([source_geometries[sid] for sid in source_ids])
                before_area_group = float(before_group.intersection(before_target).area)
                after_intersection_group = candidate_copper.intersection(target)
                after_area_group = float(after_intersection_group.area)
                declared_regions = []
                for member_id in source_ids:
                    member_rows = [r for r in overlaps if r.get("trace_source_id") == member_id and r.get("rectangle_source_id") == rect_id]
                    member_declared = any(
                        bool(r.get("original_attachment"))
                        and tuple(sorted((member_id, rect_id))) in contact_pairs
                        or bool(r.get("original_attachment"))
                        and tuple(sorted((member_id, f"T02v69:{rect_id}"))) in contact_pairs
                        for r in member_rows
                    )
                    if member_declared:
                        declared_regions.append(
                            attachment_exception_regions.get(f"T02v69:{rect_id}")
                            or attachment_exception_regions.get(rect_id)
                            or source_geometries[member_id].intersection(before_target)
                        )
                declared_region = unary_union(declared_regions) if declared_regions else None
                has_declared_attachment = bool(declared_regions)
                is_group_attachment = (
                    before_area_group > 0.0 and after_area_group > 0.0
                    and declared_region is not None
                    and declared_region.covers(after_intersection_group)
                )
                if has_declared_attachment and after_area_group > 0.0 and not is_group_attachment:
                    new_or_worsened.append(["WRITABLE_TRACE_GROUP", rect_id, "UNAUTHORIZED_SOURCE_ATTACHMENT_CONTACT"])
                if after_area_group > 0.0 and not is_group_attachment and before_area_group <= max(numeric_tolerance_mm, 1e-12):
                    new_or_worsened.append(["WRITABLE_TRACE_GROUP", rect_id, "UNAUTHORIZED_NEW_OVERLAP"])
                if is_group_attachment:
                    group_classification = "AUTHORIZED_SOURCE_ATTACHMENT_CONTACT"
                elif after_area_group > before_area_group + max(numeric_tolerance_mm, 1e-12):
                    group_classification = "WORSENED_INHERITED_OVERLAP"
                    new_or_worsened.append(["WRITABLE_TRACE_GROUP", rect_id, group_classification])
                elif after_area_group <= max(numeric_tolerance_mm, 1e-12) and before_area_group > max(numeric_tolerance_mm, 1e-12):
                    group_classification = "RESOLVED_IN_CANDIDATE"
                elif after_area_group > 0:
                    group_classification = "INHERITED_OPEN_NOT_WORSENED"
                else:
                    group_classification = "PASS_NO_NEW_OVERLAP"
                group = {
                    "group_id": f"OVERLAP:{rect_id}",
                    "target_source_id": rect_id,
                    "source_trace_ids": source_ids,
                    "before_overlap_area_mm2": before_area_group,
                    "after_overlap_area_mm2": after_area_group,
                    "classification": group_classification,
                    "measurement_scope": "CANONICAL_WRITABLE_CHAIN_VS_PROTECTED_TARGET",
                }
                overlap_group_measurements[rect_id] = group
            after_area = float(group["after_overlap_area_mm2"])
            classification = str(group["classification"])
            is_declared_attachment = classification == "AUTHORIZED_SOURCE_ATTACHMENT_CONTACT"
        else:
            result_trace = result_source_geometries[trace_id]
            after_intersection = result_trace.intersection(target)
            after_area = float(after_intersection.area)
            contact_region = (
                attachment_exception_regions.get(f"T02v69:{rect_id}")
                or attachment_exception_regions.get(rect_id)
                or source_geometries[trace_id].intersection(before_target)
            )
            is_declared_attachment = (
                (
                    tuple(sorted((trace_id, rect_id))) in contact_pairs
                    or tuple(sorted((trace_id, f"T02v69:{rect_id}"))) in contact_pairs
                )
                and before_area > 0.0
                and after_area > 0.0
                and contact_region.covers(after_intersection)
            )
            if after_area > 0.0 and not is_declared_attachment and before_area <= max(numeric_tolerance_mm, 1e-12):
                new_or_worsened.append([trace_id, rect_id, "UNAUTHORIZED_NEW_OVERLAP"])
            if is_declared_attachment:
                classification = "AUTHORIZED_SOURCE_ATTACHMENT_CONTACT"
            elif after_area > before_area + max(numeric_tolerance_mm, 1e-12):
                classification = "WORSENED_INHERITED_OVERLAP"
                new_or_worsened.append([trace_id, rect_id, classification])
            elif after_area <= max(numeric_tolerance_mm, 1e-12) and before_area > max(numeric_tolerance_mm, 1e-12):
                classification = "RESOLVED_IN_CANDIDATE"
            elif after_area > 0:
                classification = "INHERITED_OPEN_NOT_WORSENED"
            else:
                classification = "PASS_NO_NEW_OVERLAP"
        output_overlaps.append({
            "source_pair": [trace_id, rect_id],
            "interaction_group_id": f"OVERLAP:{rect_id}" if trace_id in writable_source_ids else None,
            "classification_scope": "CANONICAL_WRITABLE_CHAIN_VS_PROTECTED_TARGET" if trace_id in writable_source_ids else "SOURCE_PAIR",
            "group_classification": classification,
            "inherited_status": row.get("status"),
            "inherited_disposition": row.get("disposition"),
            "inherited_open_disposition_preserved": row.get("disposition") in {
                "DEFERRED_TO_FUTURE_TRACE_SESSION", "OPEN_FUTURE_TRACE_SESSION", "OPEN"
            },
            "before_overlap_area_mm2": before_area,
            "after_overlap_area_mm2": after_area,
            "before_group_overlap_area_mm2": group.get("before_overlap_area_mm2") if trace_id in writable_source_ids else None,
            "inherited_recorded_overlap_area_mm2": row.get("overlap_area_mm2"),
            "measurement": "SOURCE_BOUND_COPPER_INTERSECTION",
        })
    if new_or_worsened:
        raise PreflightError(f"C2_INHERITED_FINDING_NEW_OR_WORSENED:{new_or_worsened[0]}")
    return {
        "status": "PASS_INHERITED_FINDING_COMPARISON",
        "clearance_issue_count": len(clearances),
        "overlap_issue_count": len(overlaps),
        "clearance_classifications": output_clearances,
        "overlap_classifications": output_overlaps,
        "clearance_group_measurements": [clearance_group_measurements[key] for key in sorted(clearance_group_measurements)],
        "overlap_group_measurements": [overlap_group_measurements[key] for key in sorted(overlap_group_measurements)],
        "new_or_worsened_count": 0,
        "historical_open_dispositions_rewritten": False,
    }


def verify_saved_candidate_archive(
    archive_path: Path,
    *,
    expected_archive_sha256: str,
    expected_source_preflight_report_sha256: str,
    reference_inputs: dict[str, Any],
) -> dict[str, Any]:
    """Reload a saved geometry archive and run the complete source-bound check.

    `reference_inputs` must come from the verified C2 preflight package, not
    from the candidate archive. Archive members and identities are exhaustive.
    """
    archive_path = Path(archive_path)
    raw_archive = archive_path.read_bytes()
    if _sha(raw_archive) != expected_archive_sha256:
        raise PreflightError("C2_SAVED_ARCHIVE_SHA256_MISMATCH")
    with ZipFile(archive_path) as archive:
        if archive.testzip() is not None:
            raise PreflightError("C2_SAVED_ARCHIVE_CRC")
        names = archive.namelist()
        if len(names) != len(set(names)) or "manifest.json" not in names:
            raise PreflightError("C2_SAVED_ARCHIVE_MEMBERS_INVALID")
        manifest = json.loads(archive.read("manifest.json"))
        if manifest.get("schema") != "T03_C2_SAVED_GEOMETRY_ARCHIVE_V1":
            raise PreflightError("C2_SAVED_ARCHIVE_SCHEMA")
        report = reference_inputs.get("source_preflight_report")
        report_sha256 = _sha(canonical_source_preflight_report_bytes(report)) if isinstance(report, dict) else ""
        if report_sha256 != expected_source_preflight_report_sha256 or manifest.get("source_preflight_report_sha256") != expected_source_preflight_report_sha256:
            raise PreflightError("C2_SAVED_ARCHIVE_SOURCE_PREFLIGHT_BINDING_MISMATCH")
        expected_candidate_spec = {
            "cut_port": reference_inputs.get("candidate_cut_port"),
            "offsets_mm": [float(value) for value in reference_inputs.get("candidate_offsets_mm", ())],
        }
        if manifest.get("candidate_spec") != expected_candidate_spec:
            raise PreflightError("C2_SAVED_ARCHIVE_CANDIDATE_SPEC_MISMATCH")
        declared = manifest.get("members", {})
        actual_payload_names = set(names) - {"manifest.json"}
        if set(declared) != actual_payload_names:
            raise PreflightError("C2_SAVED_ARCHIVE_MEMBER_SET_MISMATCH")
        payload = {}
        for name in sorted(actual_payload_names):
            data = archive.read(name)
            if _sha(data) != declared[name]:
                raise PreflightError(f"C2_SAVED_ARCHIVE_MEMBER_HASH:{name}")
            payload[name] = data
    identity_members = manifest.get("identity_members", {})
    reconstructed: dict[str, dict[str, Any]] = {}
    for prefix in ("result/source", "result/lands", "exceptions"):
        mapping = identity_members.get(prefix, {})
        expected_names = {f"{prefix}/{key}.wkb" for key in mapping}
        if expected_names != {name for name in payload if name.startswith(prefix + "/")}:
            raise PreflightError(f"C2_SAVED_ARCHIVE_IDENTITY_SET:{prefix}")
        geometries = {}
        for key, identity in mapping.items():
            if _sha(identity.encode("utf-8")) != key:
                raise PreflightError(f"C2_SAVED_ARCHIVE_IDENTITY_HASH:{prefix}")
            data = payload[f"{prefix}/{key}.wkb"]
            geom = wkb.loads(data)
            if geom.is_empty or not geom.is_valid:
                raise PreflightError(f"C2_SAVED_ARCHIVE_GEOMETRY_INVALID:{prefix}:{identity}")
            geometries[identity] = geom
        reconstructed[prefix] = geometries
    required_fixed = {"candidate/line.wkb", "candidate/copper.wkb"}
    if not required_fixed <= set(payload) or set(payload) - required_fixed - {
        f"{prefix}/{key}.wkb"
        for prefix in ("result/source", "result/lands", "exceptions")
        for key in identity_members.get(prefix, {})
    }:
        raise PreflightError("C2_SAVED_ARCHIVE_MEMBER_UNEXPECTED")
    args = dict(reference_inputs)
    args.update({
        "candidate_line_wkb": payload["candidate/line.wkb"],
        "candidate_copper_wkb": payload["candidate/copper.wkb"],
        "expected_line_sha256": _sha(payload["candidate/line.wkb"]),
        "expected_copper_sha256": _sha(payload["candidate/copper.wkb"]),
        "result_source_geometries": reconstructed["result/source"],
        "result_lands": reconstructed["result/lands"],
        "attachment_exception_regions": reconstructed["exceptions"],
    })
    result = verify_saved_candidate_bundle(**args)
    result["saved_archive_sha256"] = expected_archive_sha256
    result["serialized_candidate_reloaded"] = True
    return result


def verify_saved_candidate_archive_from_c2_package(
    archive_path: Path,
    *,
    expected_archive_sha256: str,
    package_manifest_path: Path,
    witness_path: Path,
    future_work_items_path: Path,
    t02_review_issue_ids_path: Path,
    t02_checksum_manifest_path: Path,
    candidate_cut_port: dict[str, Any],
    candidate_offsets_mm: tuple[float, float, float],
) -> dict[str, Any]:
    """Verify a saved candidate by loading its authority from the exact C2 package.

    Unlike ``verify_saved_candidate_archive``, this public boundary does not
    accept caller-built ``reference_inputs`` or a caller-provided preflight
    report. It first re-verifies the complete source package and inherited
    ledgers, then derives all source/land maps and exception regions from that
    verified package. The candidate cut port and grid offsets remain explicit
    invocation inputs and must match the bounded source-derived domain.
    """
    package_manifest_path = Path(package_manifest_path)
    source_preflight_report = verify_c2_source_obligations(
        package_manifest_path,
        Path(witness_path),
        Path(future_work_items_path),
        Path(t02_review_issue_ids_path),
        Path(t02_checksum_manifest_path),
    )
    if source_preflight_report.get("status") != "PASS_C2_SOURCE_BOUND_PREFLIGHT_OBLIGATIONS":
        raise PreflightError("C2_TRUSTED_SOURCE_PREFLIGHT_NOT_PASS")
    root, _, spec, _, fcu_rows, source_geometries, accepted_lands = _load_scene(package_manifest_path)
    inventory_hashes = {row["source_id"]: row["geometry_sha256"] for row in source_preflight_report["source_obstacle_partition"]}
    if set(inventory_hashes) != set(source_geometries):
        raise PreflightError("C2_TRUSTED_SOURCE_PARTITION_MISMATCH")
    source_archive_path = root / spec["org_archive"]["path"]
    with ZipFile(source_archive_path) as archive:
        members = {name[:-4]: name for name in archive.namelist() if name.endswith(".wkb")}
        source_wkb_by_id = {}
        for row in fcu_rows:
            source_id = row["id"]
            digest = inventory_hashes[source_id]
            name = members.get(digest)
            if name is None:
                raise PreflightError(f"C2_TRUSTED_SOURCE_WKB_MISSING:{source_id}")
            data = archive.read(name)
            if _sha(data) != digest:
                raise PreflightError(f"C2_TRUSTED_SOURCE_WKB_HASH:{source_id}")
            source_wkb_by_id[source_id] = data
    land_manifest = _json(root / spec["land_manifest"]["path"])
    land_root = root / spec["land_manifest"]["target_root"]
    land_wkb_by_id = {}
    expected_land_wkb_sha256 = {}
    for target in land_manifest["targets"]:
        land_id = target["source_id"]
        path = land_root / Path(target["candidate_wkb_path"]).name
        data = path.read_bytes()
        if _sha(data) != target["candidate_wkb_sha256"]:
            raise PreflightError(f"C2_TRUSTED_LAND_WKB_HASH:{land_id}")
        land_wkb_by_id[land_id] = data
        expected_land_wkb_sha256[land_id] = target["candidate_wkb_sha256"]

    source_path_info = source_preflight_report["source_path_centerline"]
    if candidate_cut_port not in source_path_info.get("eligible_cut_ports", []):
        raise PreflightError("C2_TRUSTED_CANDIDATE_CUTPORT_NOT_IN_DOMAIN")
    writable_source_ids = set(source_preflight_report["patch_source_ids"])
    expected_source_wkb_sha256 = inventory_hashes
    expected_attachment_exception_sha256: dict[str, str] = {}
    attachment_exception_regions: dict[str, Any] = {}
    for item in source_preflight_report.get("attachment_exceptions", []):
        trace_id = item["trace_source_id"]
        obstacle_id = item["obstacle_source_id"]
        if item["kind"] == "ACCEPTED_T02_LAND":
            key = f"T02v69:{obstacle_id}"
            obstacle = accepted_lands.get(obstacle_id)
        else:
            key = obstacle_id
            obstacle = source_geometries.get(obstacle_id)
        if trace_id not in source_geometries or obstacle is None:
            raise PreflightError("C2_TRUSTED_ATTACHMENT_EXCEPTION_SOURCE_MISSING")
        region = source_geometries[trace_id].intersection(obstacle).buffer(
            float(item["v15_port_buffer_radius_mm"]), quad_segs=source_preflight_report["clearance_policy"]["quad_segs"]
        )
        digest = _sha(wkb.dumps(region, byte_order=0, output_dimension=2, include_srid=False))
        if digest != item["allowed_contact_region_wkb_sha256"]:
            raise PreflightError(f"C2_TRUSTED_ATTACHMENT_EXCEPTION_HASH:{key}")
        attachment_exception_regions[key] = region
        expected_attachment_exception_sha256[key] = digest

    cut_source_id = candidate_cut_port["source_id"]
    cut_xy = tuple(map(float, candidate_cut_port["coordinate_xy"]))
    suffix_key = f"CUT_SUFFIX:{cut_source_id}"
    protected_suffix = _downstream_source_suffix(
        source_geometries[cut_source_id], cut_xy, tuple(map(float, candidate_cut_port["tangent_xy"]))
    )
    endpoint_region = protected_suffix.intersection(Point(cut_xy).buffer(
        WIDTH_MM / 2.0 + SOURCE_SURFACE_TARGET_MM + SOURCE_GEOMETRY_TOLERANCE_MM,
        quad_segs=256,
    ))
    if endpoint_region.is_empty or endpoint_region.area <= 0:
        raise PreflightError("C2_TRUSTED_FIXED_SUFFIX_EXCEPTION_EMPTY")
    attachment_exception_regions[suffix_key] = endpoint_region
    expected_attachment_exception_sha256[suffix_key] = _sha(
        wkb.dumps(endpoint_region, byte_order=0, output_dimension=2, include_srid=False)
    )
    report_sha256 = _sha(canonical_source_preflight_report_bytes(source_preflight_report))
    reference_inputs = {
        "source_preflight_report": source_preflight_report,
        "expected_start_xy": tuple(source_preflight_report["source_chain_endpoint_checks"]["directed_endpoints"][0]["start_xy"]),
        "expected_end_xy": cut_xy,
        "candidate_cut_port": candidate_cut_port,
        "candidate_offsets_mm": candidate_offsets_mm,
        "source_geometries": source_geometries,
        "expected_source_ids": set(source_geometries),
        "source_wkb_by_id": source_wkb_by_id,
        "expected_source_wkb_sha256": expected_source_wkb_sha256,
        "writable_source_ids": writable_source_ids,
        "accepted_lands": accepted_lands,
        "expected_land_ids": set(accepted_lands),
        "land_wkb_by_id": land_wkb_by_id,
        "expected_land_wkb_sha256": expected_land_wkb_sha256,
        "attachment_exception_regions": attachment_exception_regions,
        "expected_attachment_exception_sha256": expected_attachment_exception_sha256,
        "required_contacts": source_preflight_report["contact_census"],
        "width_mm": WIDTH_MM,
    }
    result = verify_saved_candidate_archive(
        archive_path,
        expected_archive_sha256=expected_archive_sha256,
        expected_source_preflight_report_sha256=report_sha256,
        reference_inputs=reference_inputs,
    )
    result["trusted_source_package_manifest_sha256"] = _sha(package_manifest_path.read_bytes())
    result["trusted_source_package_preflight_sha256"] = report_sha256
    result["trusted_invocation_boundary"] = "PASS_REVERIFIED_C2_PACKAGE"
    return result
