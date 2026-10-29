from __future__ import annotations

import json
import math
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile

import pytest
from shapely.geometry import LineString, Point, box
from shapely import to_wkb
from shapely.ops import unary_union

from src.t03_route_preflight import (
    BUFFER_TESSELLATION_TOLERANCE_MM,
    PreflightError,
    Primitive,
    SourcePath,
    SOURCE_GEOMETRY_TOLERANCE_MM,
    SOURCE_SPAN_JOIN_RESIDUAL_MAX_MM2,
    SOURCE_SPAN_UNION_TOLERANCE_MM2,
    WIDTH_MM,
    buffer_centerline,
    candidate_source_copper_by_id,
    construct_candidate_centerline,
    construct_candidate_centerline_source_spans,
    enumerate_candidate_specs,
    enumerate_cut_ports,
    serialize_candidate,
    verify_scene,
    verify_candidate_copper,
    _bounded_source_span_fraction,
)


def _digest(data: bytes) -> str:
    return sha256(data).hexdigest()


def _path() -> SourcePath:
    return SourcePath((
        Primitive("line-a", "segment", (0.0, 0.0), (0.3, 0.0), 0.10008),
        Primitive("arc-b", "arc", (0.3, 0.0), (0.4, 0.1), 0.10008, (0.37, 0.03)),
        Primitive("line-c", "segment", (0.4, 0.1), (0.8, 0.1), 0.10008),
    ), initial_patch_end_mm=0.3)


def test_source_path_rejects_gap_and_width_change():
    with __import__("pytest").raises(PreflightError, match="SOURCE_CHAIN_GAP"):
        SourcePath((
            Primitive("a", "segment", (0, 0), (0.2, 0), 0.10008),
            Primitive("b", "segment", (0.21, 0), (0.5, 0), 0.10008),
        ), 0.2)
    with __import__("pytest").raises(PreflightError, match="WIDTH_MISMATCH"):
        Primitive("narrow", "segment", (0, 0), (1, 0), 0.099)


def test_bounded_source_span_fraction_handles_endpoint_rounding_by_one_ulp():
    # Candidate-1's accumulated source station produced this same one-ULP
    # endpoint overshoot: (stop - start) / length == 1.0000000000000002.
    start = 0.2029999999999994
    length = 0.09944994308317721
    stop = start + length
    raw_fraction = (stop - start) / length
    assert raw_fraction == math.nextafter(1.0, math.inf)
    assert _bounded_source_span_fraction(start, stop, length) == 1.0

    partial_stop = math.nextafter(stop, -math.inf)
    partial_fraction = _bounded_source_span_fraction(start, partial_stop, length)
    assert 0.0 <= partial_fraction <= 1.0


def test_source_span_fraction_stays_fail_closed_for_out_of_range_stations():
    start = 0.2029999999999994
    length = 0.09944994308317721
    endpoint = start + length
    with pytest.raises(PreflightError, match="PRIMITIVE_FRACTION_OUT_OF_RANGE"):
        _bounded_source_span_fraction(start, math.nextafter(endpoint, math.inf), length)
    with pytest.raises(PreflightError, match="PRIMITIVE_FRACTION_OUT_OF_RANGE"):
        Primitive("strict", "segment", (0.0, 0.0), (1.0, 0.0), 0.10008).point(
            math.nextafter(1.0, math.inf)
        )


def test_port_grid_is_sorted_deduplicated_and_fail_closed_at_transitions():
    ports = enumerate_cut_ports(_path(), step_mm=__import__("decimal").Decimal("0.05"), transition_buffer_mm=0.04)
    keys = [(p.distance_mm, p.source_id) for p in ports]
    assert keys == sorted(keys)
    assert len({p.distance_mm for p in ports}) == len(ports)
    assert any(p.reason == "TRANSITION_BUFFER" for p in ports)
    assert all(p.extension_mm <= __import__("decimal").Decimal("0.500") for p in ports)


def test_candidate_specs_have_frozen_total_order_and_budget():
    path = _path()
    candidates = enumerate_candidate_specs(path)
    keys = [
        (p.extension_mm, max(abs(v) for v in d), sum(abs(v) for v in d), *d, p.source_id)
        for p, d in candidates
    ]
    assert keys == sorted(keys)
    assert len(candidates) <= 10_000
    assert candidates


def test_centerline_is_deterministic_and_endpoints_stay_fixed():
    path = _path()
    port = next(p for p in enumerate_cut_ports(path, transition_buffer_mm=0.01) if p.eligible and p.extension_mm >= 0.1)
    kwargs = dict(cut_distance_mm=float(port.distance_mm), offsets_mm=(0.15, -0.05, 0.1))
    first = construct_candidate_centerline(path, **kwargs)
    second = construct_candidate_centerline(path, **kwargs)
    first_bytes, first_hash = serialize_candidate(first)
    second_bytes, second_hash = serialize_candidate(second)
    assert first_hash == second_hash
    assert first_bytes == second_bytes
    assert first.is_valid and first.geom_type == "LineString"
    assert first.coords[0] == path.point_at(0.0)
    assert first.coords[-1] == path.point_at(float(port.distance_mm))
    # Smoothstep interpolation must not overshoot the supplied knot palette.
    xs = [c[0] for c in first.coords]
    assert min(xs) > -0.26 and max(xs) < 0.81


def test_source_span_attribution_reconstructs_exact_generated_route():
    path = _path()
    port = next(
        row for row in enumerate_cut_ports(path, transition_buffer_mm=0.01)
        if row.eligible and row.source_id == "line-c"
    )
    offsets = (0.05, -0.05, 0.15)
    canonical = construct_candidate_centerline(path, float(port.distance_mm), offsets)
    attributed, spans = construct_candidate_centerline_source_spans(
        path, float(port.distance_mm), offsets
    )
    assert attributed.equals_exact(canonical, tolerance=0.0)
    assert list(spans) == ["line-a", "arc-b", "line-c"]
    assert all(span.is_valid and span.length > 0 for span in spans.values())
    assert spans["line-c"].coords[-1] == canonical.coords[-1]


def test_four_distinct_selected_ports_have_exact_source_span_partitions():
    from src.t03_c2_source_verifier import _downstream_source_suffix

    path = SourcePath((
        Primitive("source-a", "segment", (0.0, 0.0), (0.2, 0.0), 0.10008),
        Primitive("source-b", "segment", (0.2, 0.0), (0.4, 0.0), 0.10008),
        Primitive("source-cut", "segment", (0.4, 0.0), (1.0, 0.0), 0.10008),
    ), initial_patch_end_mm=0.4)
    source_cut_geometry = box(0.4, -0.05004, 1.0, 0.05004)
    cut_distances = (0.50, 0.55, 0.60, 0.65)
    suffix_hashes = set()
    saw_nonempty_seam_residual = False
    for distance in cut_distances:
        line, spans = construct_candidate_centerline_source_spans(path, distance, (0.05, 0.0, -0.05))
        copper, _ = buffer_centerline(line)
        raw_span_union = unary_union([
            buffer_centerline(span)[0].intersection(copper) for span in spans.values()
        ])
        residual = copper.difference(raw_span_union)
        if not residual.is_empty:
            saw_nonempty_seam_residual = True
            joins = [
                Point(
                    (
                        (spans[left].coords[-1][0] + spans[right].coords[0][0]) / 2,
                        (spans[left].coords[-1][1] + spans[right].coords[0][1]) / 2,
                    )
                ).buffer(
                    WIDTH_MM / 2 + SOURCE_GEOMETRY_TOLERANCE_MM, quad_segs=256
                )
                for left, right in zip(spans, list(spans)[1:])
            ]
            assert unary_union(joins).covers(residual)
            assert residual.area <= len(joins) * SOURCE_SPAN_JOIN_RESIDUAL_MAX_MM2
        source_map = candidate_source_copper_by_id(
            spans, ("source-a", "source-b", "source-cut"), "source-cut", copper
        )
        assert set(source_map) == {"source-a", "source-b", "source-cut"}
        assert unary_union(list(source_map.values())).symmetric_difference(copper).area <= SOURCE_SPAN_UNION_TOLERANCE_MM2
        assert source_map["source-cut"].intersection(source_map["source-b"]).area > 0
        cut_xy = (distance, 0.0)
        suffix = _downstream_source_suffix(source_cut_geometry, cut_xy, (1.0, 0.0))
        final_source_map = dict(source_map)
        final_source_map["source-cut"] = unary_union([source_map["source-cut"], suffix])
        assert unary_union(list(final_source_map.values())).symmetric_difference(copper.union(suffix)).area <= SOURCE_SPAN_UNION_TOLERANCE_MM2
        suffix_hashes.add(sha256(to_wkb(suffix, byte_order=0, output_dimension=2, include_srid=False)).hexdigest())
    assert len(suffix_hashes) == 4
    assert saw_nonempty_seam_residual


def test_generated_source_attribution_preserves_join_overlap_without_partitioning():
    path = SourcePath((
        Primitive("left", "segment", (0.0, 0.0), (0.5, 0.0), 0.10008),
        Primitive("right", "segment", (0.5, 0.0), (1.0, 0.0), 0.10008),
    ), initial_patch_end_mm=0.25)
    line, spans = construct_candidate_centerline_source_spans(path, 0.75, (0.0, 0.0, 0.0))
    copper, _ = buffer_centerline(line)
    attributed = candidate_source_copper_by_id(spans, ("left", "right"), "right", copper)

    assert set(attributed) == {"left", "right"}
    assert attributed["left"].intersection(attributed["right"]).area > 0
    assert unary_union(list(attributed.values())).equals(copper)
    assert attributed["right"].difference(copper).area == 0


def test_source_span_seam_residual_outside_declared_join_neighborhood_is_rejected():
    path = SourcePath((
        Primitive("left", "segment", (0.0, 0.0), (0.5, 0.0), 0.10008),
        Primitive("right", "segment", (0.5, 0.0), (1.0, 0.0), 0.10008),
    ), initial_patch_end_mm=0.25)
    line, spans = construct_candidate_centerline_source_spans(path, 0.75, (0.0, 0.0, 0.0))
    copper, _ = buffer_centerline(line)
    foreign_island = box(3.0, 3.0, 3.00001, 3.00001)
    canonical_with_unrelated_island = unary_union([copper, foreign_island])

    with pytest.raises(PreflightError, match="CANDIDATE_SOURCE_SPAN_UNION_GAP_OUTSIDE_JOIN_NEIGHBORHOOD"):
        candidate_source_copper_by_id(
            spans, ("left", "right"), "right", canonical_with_unrelated_island
        )


def test_source_span_join_residual_above_derived_per_join_bound_is_rejected(monkeypatch):
    path = SourcePath((
        Primitive("left", "segment", (0.0, 0.0), (0.5, 0.0), 0.10008),
        Primitive("right", "segment", (0.5, 0.0), (1.0, 0.0), 0.10008),
    ), initial_patch_end_mm=0.25)
    line, spans = construct_candidate_centerline_source_spans(path, 0.75, (0.0, 0.0, 0.0))
    copper, _ = buffer_centerline(line)
    # Fault-inject both independently mapped spans with a missing local disk.
    # The canonical route stays unchanged, so the residual tests the join cap
    # without widening the accepted copper envelope.
    join_blob = Point(0.5, 0.0).buffer(0.002)
    assert join_blob.area > SOURCE_SPAN_JOIN_RESIDUAL_MAX_MM2
    original_buffer = buffer_centerline

    def omit_join_disk(centerline, width_mm=WIDTH_MM):
        mapped_copper, quad_segs = original_buffer(centerline, width_mm)
        return mapped_copper.difference(join_blob), quad_segs

    monkeypatch.setattr("src.t03_route_preflight.buffer_centerline", omit_join_disk)

    with pytest.raises(PreflightError, match="CANDIDATE_SOURCE_SPAN_JOIN_RESIDUAL_EXCEEDS_TOLERANCE:left:right"):
        candidate_source_copper_by_id(
            spans, ("left", "right"), "right", copper
        )


def test_surface_buffer_keeps_exact_width_and_bounded_quad_segs():
    copper, quad_segs = buffer_centerline(LineString([(0, 0), (1, 0)]))
    assert copper.is_valid
    assert quad_segs > 1
    assert BUFFER_TESSELLATION_TOLERANCE_MM == 0.00001
    assert abs(copper.bounds[3] - copper.bounds[1] - 0.10008) < 1e-9


def test_candidate_clearance_checks_surfaces_and_marks_unclassified_blocking():
    centerline = LineString([(0, 0), (1, 0)])
    copper, _ = buffer_centerline(centerline)
    obstacle = box(0.3, 0.071, 0.7, 0.2)
    result = verify_candidate_copper(
        centerline,
        copper,
        [{"source_id": "protected-1", "geometry": obstacle, "disposition": "protected"}],
    )
    assert result["status"] == "PASS_GEOMETRIC_CLEARANCE_ONLY"
    assert result["obstacle_checks"][0]["distance_mm"] == pytest.approx(0.02096, abs=1e-8)
    with pytest.raises(PreflightError, match="UNCLASSIFIED_SCENE_OBSTACLE"):
        verify_candidate_copper(
            centerline,
            copper,
            [{"source_id": "unknown-1", "geometry": obstacle, "disposition": "unknown"}],
        )


def test_candidate_clearance_rejects_surface_overlap_and_unbounded_attachment_exception():
    centerline = LineString([(0, 0), (1, 0)])
    copper, _ = buffer_centerline(centerline)
    overlap = box(0.4, 0.03, 0.6, 0.08)
    failed = verify_candidate_copper(
        centerline,
        copper,
        [{"source_id": "protected-2", "geometry": overlap, "disposition": "protected"}],
    )
    assert failed["status"] == "FAIL"
    assert failed["obstacle_checks"][0]["status"] == "FAIL_OVERLAP"
    geom = box(0.4, -0.03, 0.6, 0.03)
    region = box(0.39, -0.03, 0.5, 0.03)
    exception = verify_candidate_copper(
        centerline,
        copper,
        [{"source_id": "join-1", "geometry": geom, "disposition": "attachment_exception", "allowed_contact_region": region}],
    )
    assert exception["status"] == "FAIL"
    with pytest.raises(PreflightError, match="ATTACHMENT_EXCEPTION_UNBOUNDED"):
        verify_candidate_copper(
            centerline,
            copper,
            [{"source_id": "join-2", "geometry": geom, "disposition": "attachment_exception"}],
        )


def test_candidate_rejects_width_change_and_mismatched_buffer():
    centerline = LineString([(0, 0), (1, 0)])
    copper, _ = buffer_centerline(centerline)
    obstacles = [{"source_id": "p", "geometry": box(2, 2, 3, 3), "disposition": "protected"}]
    with pytest.raises(PreflightError, match="WIDTH_CHANGE_FORBIDDEN"):
        verify_candidate_copper(centerline, copper, obstacles, width_mm=0.09)
    with pytest.raises(PreflightError, match="CANDIDATE_WIDTH_OR_BUFFER_MISMATCH"):
        verify_candidate_copper(centerline, box(-1, -1, 2, 2), obstacles)


def test_numeric_tolerance_never_waives_hard_floor_or_target():
    centerline = LineString([(0, 0), (1, 0)])
    copper, _ = buffer_centerline(centerline)
    below_floor = box(0.4, 0.070039, 0.6, 0.2)
    floor_result = verify_candidate_copper(
        centerline,
        copper,
        [{"source_id": "below-floor", "geometry": below_floor, "disposition": "protected"}],
    )
    assert floor_result["obstacle_checks"][0]["distance_mm"] == pytest.approx(0.019999, abs=1e-8)
    assert floor_result["obstacle_checks"][0]["status"] == "FAIL_HARD_CLEARANCE_FLOOR"
    assert floor_result["status"] == "FAIL"

    between_floor_and_target = box(0.4, 0.07005, 0.6, 0.2)
    target_result = verify_candidate_copper(
        centerline,
        copper,
        [{"source_id": "below-target", "geometry": between_floor_and_target, "disposition": "protected"}],
    )
    assert target_result["obstacle_checks"][0]["distance_mm"] == pytest.approx(0.02001, abs=1e-8)
    assert target_result["obstacle_checks"][0]["status"] == "BELOW_TARGET_WITHIN_HARD_FLOOR"
    assert target_result["status"] == "NOT_TARGET_COMPLIANT"


def test_threshold_boundaries_are_conservative_and_explicit():
    centerline = LineString([(0, 0), (1, 0)])
    copper, _ = buffer_centerline(centerline)
    exact_floor_y = 0.05004 + 0.02000
    exact_target_y = 0.05004 + 0.02002
    floor_check = verify_candidate_copper(
        centerline,
        copper,
        [{"source_id": "exact-floor", "geometry": box(0.4, exact_floor_y, 0.6, 0.2), "disposition": "protected"}],
    )
    target_check = verify_candidate_copper(
        centerline,
        copper,
        [{"source_id": "exact-target", "geometry": box(0.4, exact_target_y, 0.6, 0.2), "disposition": "protected"}],
    )
    assert floor_check["obstacle_checks"][0]["distance_mm"] == pytest.approx(0.02000, abs=1e-12)
    assert floor_check["obstacle_checks"][0]["status"] == "BELOW_TARGET_WITHIN_HARD_FLOOR"
    assert target_check["obstacle_checks"][0]["distance_mm"] == pytest.approx(0.02002, abs=1e-12)
    # The binary geometry kernel reports the nominal decimal target a few ulps
    # low here; conservative direct comparison must not use tolerance to pass it.
    assert target_check["obstacle_checks"][0]["distance_mm"] < 0.02002
    assert target_check["obstacle_checks"][0]["status"] == "BELOW_TARGET_WITHIN_HARD_FLOOR"


def _write_scene_fixture(root: Path) -> Path:
    source = b"synthetic native source"
    source_hash = _digest(source)
    (root / "source.kicad_pcb").write_bytes(source)
    geom = box(0, 0, 1, 1)
    geom_bytes = to_wkb(geom, byte_order=0, output_dimension=2, include_srid=False)
    geometry_hash = _digest(geom_bytes)
    with ZipFile(root / "org.zip", "w") as archive:
        archive.writestr(f"{geometry_hash}.wkb", geom_bytes)
    inventory = {
        "source_hash": source_hash,
        "rows": [{
            "id": f"{source_hash}:bytes:0:1",
            "source_sha256": source_hash,
            "kind": "segment",
            "layers": ["F.Cu"],
            "coverage": "GEOMETRY_AVAILABLE",
            "geometry_sha256": geometry_hash,
        }],
    }
    inv_bytes = json.dumps(inventory, sort_keys=True).encode()
    (root / "inventory.json").write_bytes(inv_bytes)
    target_geom = box(2, 2, 3, 3)
    target_bytes = to_wkb(target_geom, byte_order=0, output_dimension=2, include_srid=False)
    target_hash = _digest(target_bytes)
    (root / "lands").mkdir()
    (root / "lands" / "land.wkb").write_bytes(target_bytes)
    target_manifest = {
        "status": "HASH_BOUND_TO_FROZEN_T02_V69_DECISIONS",
        "all_candidate_wkb_valid_bounds_hash_bound": True,
        "targets": [{
            "source_id": "land-1",
            "candidate_wkb_path": "v69_per_target/land.wkb",
            "candidate_wkb_sha256": target_hash,
            "candidate_wkb_bytes": len(target_bytes),
            "accepted_bounds_mm": list(target_geom.bounds),
        }],
    }
    land_bytes = json.dumps(target_manifest, sort_keys=True).encode()
    (root / "land_manifest.json").write_bytes(land_bytes)
    policy = {"schema": "crop-rect-t02-policy/15", "task": "T02_ONLY"}
    policy_bytes = json.dumps(policy, sort_keys=True).encode()
    (root / "policy.json").write_bytes(policy_bytes)
    receipt = {"t02_policy_sha256": _digest(policy_bytes), "trace_changed_in_t02": False}
    receipt_bytes = json.dumps(receipt, sort_keys=True).encode()
    (root / "receipt.json").write_bytes(receipt_bytes)
    det = {"status": "PASS_BYTE_IDENTICAL_REPLAY"}
    det_bytes = json.dumps(det, sort_keys=True).encode()
    (root / "det.json").write_bytes(det_bytes)
    spec = {
        "test_fixture": True,
        "source": {"path": "source.kicad_pcb", "sha256": source_hash},
        "inventory": {"path": "inventory.json", "sha256": _digest(inv_bytes), "row_count": 1},
        "org_archive": {
            "path": "org.zip", "sha256": _digest((root / "org.zip").read_bytes()),
            "unique_wkb_count": 1, "fcu_object_count": 1, "fcu_kind_counts": {"segment": 1},
        },
        "land_manifest": {
            "path": "land_manifest.json", "sha256": _digest(land_bytes),
            "target_root": "lands", "target_count": 1,
        },
        "policy": {"path": "policy.json", "sha256": _digest(policy_bytes)},
        "execution_receipt": {"path": "receipt.json", "sha256": _digest(receipt_bytes)},
        "determinism_receipt": {"path": "det.json", "sha256": _digest(det_bytes)},
    }
    (root / "package_manifest.json").write_text(json.dumps(spec, indent=2) + "\n")
    return root / "package_manifest.json"


def test_complete_scene_loader_accepts_hash_bound_fixture_and_reports_no_search():
    with TemporaryDirectory() as tmp:
        result = verify_scene(_write_scene_fixture(Path(tmp)))
        assert result["status"] == "PASS_COMPLETE_SCENE_INPUT_HASH_AND_LOAD"
        assert result["org_fcu_geometry_count"] == 1
        assert result["accepted_v69_land_count"] == 1
        assert result["route_search_executed"] is False


def test_complete_scene_loader_rejects_mutated_inventory_before_load():
    with TemporaryDirectory() as tmp:
        manifest = _write_scene_fixture(Path(tmp))
        root = manifest.parent
        (root / "inventory.json").write_text("{}")
        with __import__("pytest").raises(PreflightError, match="INPUT_HASH_MISMATCH:inventory.json"):
            verify_scene(manifest)
