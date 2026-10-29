from __future__ import annotations

from hashlib import sha256
import json
import inspect
from pathlib import Path
import re

import pytest
from shapely import to_wkb
from shapely.geometry import LineString, Point, box
from shapely.ops import unary_union

from src.t03_c2_source_verifier import (
    _classify_inherited_v69_findings,
    _downstream_source_suffix,
    _verify_contact_obligations,
    canonical_source_preflight_report_bytes,
    verify_c2_source_obligations,
    verify_saved_candidate_archive,
    verify_saved_candidate_archive_from_c2_package,
    verify_saved_candidate_bundle,
    verify_saved_candidate_wkb,
    write_candidate_geometry_archive,
)
from src.t03_route_preflight import PreflightError, Primitive, SourcePath, SOURCE_GEOMETRY_TOLERANCE_MM, SOURCE_SURFACE_TARGET_MM, WIDTH_MM, buffer_centerline, candidate_source_copper_by_id, construct_candidate_centerline, construct_candidate_centerline_source_spans


ROOT = Path(__file__).resolve().parents[1]
_FIXTURE_CANDIDATES = (
    ROOT / "tests/fixtures/t03_c2_packet12",
    Path(__file__).resolve().parent / "fixtures/t03_c2_packet12",
    ROOT / "t03_c2_packet12",
    ROOT / "out/crop_dynamic_tasks/t03_t04_s2b_c2_archive_materializer_20261026_v01/tests/fixtures/t03_c2_packet12",
)
_PORTABLE_EVIDENCE = next(
    (path for path in _FIXTURE_CANDIDATES if
     (path / "complete_scene/package_scene_manifest.json").is_file() and
     (path / "s2a/adaptive_patch_witness.json").is_file() and
     (path / "t02_inherited/SHA256SUMS.txt").is_file()),
    None,
)
if _PORTABLE_EVIDENCE is None:
    raise RuntimeError("PORTABLE_PACKET12_FIXTURE_MISSING_OR_INCOMPLETE")
_BUNDLED_EVIDENCE = _PORTABLE_EVIDENCE
SCENE = _BUNDLED_EVIDENCE / "complete_scene"
S2A = _BUNDLED_EVIDENCE / "s2a"
T02 = _BUNDLED_EVIDENCE / "t02_inherited"


def test_source_preflight_report_identity_has_one_canonical_newline_encoding():
    report = {"z": 1, "nested": {"name": "café"}}
    canonical = b'{"nested":{"name":"caf\\u00e9"},"z":1}\n'
    assert canonical_source_preflight_report_bytes(report) == canonical
    assert sha256(canonical_source_preflight_report_bytes(report)).hexdigest() != sha256(canonical[:-1]).hexdigest()
    changed = {"z": 1, "nested": {"name": "cafe"}}
    assert canonical_source_preflight_report_bytes(changed) != canonical


def test_source_bound_c2_obligations_recheck_complete_scene_contacts_and_inherited_findings():
    result = verify_c2_source_obligations(
        SCENE / "package_scene_manifest.json",
        S2A / "adaptive_patch_witness.json",
        T02 / "future_trace_work_items.json",
        T02 / "review_issue_ids.json",
        T02 / "SHA256SUMS.txt",
    )
    assert result["status"] == "PASS_C2_SOURCE_BOUND_PREFLIGHT_OBLIGATIONS"
    assert result["org_fcu_object_count"] == 17_849
    assert result["accepted_v69_land_count"] == 80
    assert result["source_obstacle_partition_count"] == 17_849
    assert result["accepted_land_partition_count"] == 80
    assert result["required_p1_p8_count"] == 8
    assert result["source_topology"]["status"] == "PASS_SOURCE_TOPOLOGY_AND_CUTPORT_BINDING"
    assert result["source_topology"]["fixed_branch_excluded_from_writable_patch"] is True
    ports = result["source_path_centerline"]["eligible_cut_ports"]
    assert len(ports) == 4
    assert result["source_path_centerline"]["precomputed_domain_size"] == 1372
    assert result["source_path_centerline"]["precomputed_domain_size"] <= result["source_path_centerline"]["candidate_budget"]
    assert [row["source_id"] for row in result["source_path_centerline"]["native_primitives"]] == result["source_topology"]["ordered_writable_chain_source_ids"]
    assert result["additional_external_positive_area_contact_count"] == 2
    assert result["inherited_v69"]["clearance_issue_count"] == 255
    assert result["inherited_v69"]["overlap_item_count"] == 120
    assert len(result["inherited_v69"]["local_patch_clearance_findings"]) == 2
    assert len(result["inherited_v69"]["clearance_findings"]) == 255
    assert len(result["inherited_v69"]["overlap_findings"]) == 120
    assert result["p3_semantics"].startswith("NOT_ESTABLISHED")
    assert result["route_search_executed"] is False
    assert result["route_geometry_created"] is False


def test_saved_candidate_wkb_binds_hash_and_fixed_ports_only():
    line = LineString([(0.0, 0.0), (0.5, 0.1), (1.0, 0.0)])
    data = to_wkb(line, byte_order=0, output_dimension=2, include_srid=False)
    digest = sha256(data).hexdigest()
    result = verify_saved_candidate_wkb(
        data,
        expected_sha256=digest,
        expected_start_xy=(0.0, 0.0),
        expected_end_xy=(1.0, 0.0),
    )
    assert result["status"] == "PASS_SAVED_CANDIDATE_GEOMETRY_BINDING_ONLY"
    assert result["route_feasibility"] == "NOT_ESTABLISHED"
    with pytest.raises(PreflightError, match="SAVED_CANDIDATE_END_PORT_MISMATCH"):
        verify_saved_candidate_wkb(
            data,
            expected_sha256=digest,
            expected_start_xy=(0.0, 0.0),
            expected_end_xy=(1.0, 0.1),
        )


def _candidate_bundle(blocker_y=0.30):
    synthetic_path = SourcePath((
        Primitive("patch", "segment", (0.0, 0.0), (0.5, 0.0), WIDTH_MM),
        Primitive("vertical", "segment", (0.5, 0.0), (1.0, 0.0), WIDTH_MM),
    ), 0.5)
    line = construct_candidate_centerline(synthetic_path, 1.0, (0.0, 0.0, 0.0))
    line_bytes = to_wkb(line, byte_order=0, output_dimension=2, include_srid=False)
    copper, _ = buffer_centerline(line)
    _, generated_spans = construct_candidate_centerline_source_spans(synthetic_path, 1.0, (0.0, 0.0, 0.0))
    generated = candidate_source_copper_by_id(
        generated_spans, ("patch", "vertical"), "vertical", copper
    )
    copper_bytes = to_wkb(copper, byte_order=0, output_dimension=2, include_srid=False)
    source = {
        "patch": box(0.0, -0.01, 0.1, 0.01),
        "vertical": box(0.9, -0.03, 1.2, 0.03),
        "protected": box(0.45, blocker_y, 0.55, blocker_y + 0.1),
    }
    suffix = box(1.0, -0.03, 1.2, 0.03)
    endpoint_region = suffix.intersection(Point(1.0, 0.0).buffer(WIDTH_MM / 2.0 + SOURCE_SURFACE_TARGET_MM + SOURCE_GEOMETRY_TOLERANCE_MM, quad_segs=256))
    suffix_exception_key = "CUT_SUFFIX:vertical"
    suffix_exception_hash = sha256(to_wkb(endpoint_region, byte_order=0, output_dimension=2, include_srid=False)).hexdigest()
    source_wkb = {key: to_wkb(geom, byte_order=0, output_dimension=2, include_srid=False) for key, geom in source.items()}
    output = {
        "patch": generated["patch"],
        "vertical": unary_union([generated["vertical"], suffix]),
        "protected": source["protected"],
    }
    lands = {"land-1": box(4.0, 4.0, 4.2, 4.2)}
    land_wkb = {key: to_wkb(geom, byte_order=0, output_dimension=2, include_srid=False) for key, geom in lands.items()}
    return dict(
        source_preflight_report={
            "status": "PASS_C2_SOURCE_BOUND_PREFLIGHT_OBLIGATIONS",
            "source_obstacle_partition_count": len(source),
            "accepted_land_partition_count": len(lands),
            "patch_source_ids": ["patch", "vertical"],
            "source_obstacle_partition": [
                {"source_id": key, "geometry_sha256": sha256(data).hexdigest()}
                for key, data in source_wkb.items()
            ],
            "accepted_land_partition": [
                {"source_id": key, "wkb_sha256": sha256(data).hexdigest()}
                for key, data in land_wkb.items()
            ],
            "required_p1_p8_count": 0,
            "required_p1_p8_checks": [],
            "contact_census_count": 0,
            "contact_census": [],
            "clearance_policy": {
                "sha256": "a" * 64,
                "width_mm": WIDTH_MM,
                "hard_floor_mm": 0.02,
                "construction_target_mm": 0.02002,
                "numeric_tolerance_mm": 0.00001,
                "measurement": "FINITE_WIDTH_COPPER_SURFACE",
            },
            "source_chain_endpoint_checks": {
                "directed_endpoints": [{"start_xy": [0.0, 0.0]}],
                "cut_port_xy": [1.0, 0.0],
            },
            "source_path_centerline": {
                "coordinates": [[0.0, 0.0], [0.5, 0.0], [1.0, 0.0]],
                "wkb_sha256": sha256(to_wkb(LineString([(0.0, 0.0), (0.5, 0.0), (1.0, 0.0)]), byte_order=0, output_dimension=2, include_srid=False)).hexdigest(),
                "native_primitives": [
                    {"source_id": "patch", "kind": "segment", "start_xy": [0.0, 0.0], "end_xy": [0.5, 0.0], "mid_xy": None, "width_mm": WIDTH_MM},
                    {"source_id": "vertical", "kind": "segment", "start_xy": [0.5, 0.0], "end_xy": [1.0, 0.0], "mid_xy": None, "width_mm": WIDTH_MM},
                ],
                "max_lateral_offset_mm": 0.25,
                "tessellation_sagitta_mm": 0.00001,
                "initial_patch_end_mm": 0.5,
                "max_extension_mm": 0.5,
                "status": "PASS_NATIVE_RECORD_DERIVED_CENTERLINE",
                "eligible_cut_ports": [{
                    "source_id": "vertical",
                    "coordinate_xy": [1.0, 0.0],
                    "tangent_xy": [1.0, 0.0],
                    "distance_mm": 1.0,
                    "extension_mm": 0.5,
                    "status": "ELIGIBLE_BOUNDED_CUT_PORT",
                }],
            },
            "attachment_exceptions": [],
            "source_topology": {"ordered_writable_chain_source_ids": ["patch", "vertical"]},
        },
        candidate_line_wkb=line_bytes,
        candidate_copper_wkb=copper_bytes,
        expected_line_sha256=sha256(line_bytes).hexdigest(),
        expected_copper_sha256=sha256(copper_bytes).hexdigest(),
        expected_start_xy=(0.0, 0.0),
        expected_end_xy=(1.0, 0.0),
        source_geometries=source,
        expected_source_ids=set(source),
        source_wkb_by_id=source_wkb,
        expected_source_wkb_sha256={key: sha256(data).hexdigest() for key, data in source_wkb.items()},
        candidate_cut_port={
            "source_id": "vertical",
            "coordinate_xy": [1.0, 0.0],
            "tangent_xy": [1.0, 0.0],
            "distance_mm": 1.0,
            "extension_mm": 0.5,
            "status": "ELIGIBLE_BOUNDED_CUT_PORT",
        },
        candidate_offsets_mm=(0.0, 0.0, 0.0),
        writable_source_ids={"patch", "vertical"},
        result_source_geometries=output,
        accepted_lands=lands,
        expected_land_ids=set(lands),
        land_wkb_by_id=land_wkb,
        expected_land_wkb_sha256={key: sha256(data).hexdigest() for key, data in land_wkb.items()},
        result_lands=lands,
        attachment_exception_regions={suffix_exception_key: endpoint_region},
        expected_attachment_exception_sha256={suffix_exception_key: suffix_exception_hash},
        required_contacts=[],
    )


def _materialized_source_result(path, cut_distance, offsets, suffix, source_geometries):
    line, spans = construct_candidate_centerline_source_spans(path, cut_distance, offsets)
    copper, _ = buffer_centerline(line)
    source_ids = tuple(primitive.source_id for primitive in path.primitives)
    cut_source_id = source_ids[-1]
    generated = candidate_source_copper_by_id(spans, source_ids, cut_source_id, copper)
    result = dict(source_geometries)
    result.update(generated)
    result[cut_source_id] = unary_union([generated[cut_source_id], suffix])
    return line, copper, result


def _bind_source_geometry(kwargs, source_id, geom):
    data = to_wkb(geom, byte_order=0, output_dimension=2, include_srid=False)
    kwargs["source_wkb_by_id"][source_id] = data
    kwargs["expected_source_wkb_sha256"][source_id] = sha256(data).hexdigest()
    row = next((r for r in kwargs["source_preflight_report"]["source_obstacle_partition"] if r["source_id"] == source_id), None)
    if row is None:
        kwargs["source_preflight_report"]["source_obstacle_partition"].append({"source_id": source_id, "geometry_sha256": sha256(data).hexdigest()})
    else:
        row["geometry_sha256"] = sha256(data).hexdigest()


def test_saved_candidate_bundle_checks_full_partition_corridor_buffer_and_clearance():
    result = verify_saved_candidate_bundle(**_candidate_bundle())
    assert result["status"] == "PASS_SAVED_C2_CANDIDATE_GEOMETRY"
    assert result["corridor"] == "PASS_SOURCE_BOUND"
    assert result["protected_source_count"] == 1
    assert result["accepted_land_count"] == 1


def test_saved_candidate_bundle_accepts_rederived_nonzero_grid_candidate():
    kwargs = _candidate_bundle()
    path = SourcePath((
        Primitive("patch", "segment", (0.0, 0.0), (0.5, 0.0), WIDTH_MM),
        Primitive("vertical", "segment", (0.5, 0.0), (1.0, 0.0), WIDTH_MM),
    ), 0.5)
    offsets = (0.05, 0.0, 0.0)
    line = construct_candidate_centerline(path, 1.0, offsets)
    line_bytes = to_wkb(line, byte_order=0, output_dimension=2, include_srid=False)
    copper, _ = buffer_centerline(line)
    copper_bytes = to_wkb(copper, byte_order=0, output_dimension=2, include_srid=False)
    kwargs.update({
        "candidate_line_wkb": line_bytes,
        "candidate_copper_wkb": copper_bytes,
        "expected_line_sha256": sha256(line_bytes).hexdigest(),
        "expected_copper_sha256": sha256(copper_bytes).hexdigest(),
        "candidate_offsets_mm": offsets,
    })
    _, _, kwargs["result_source_geometries"] = _materialized_source_result(
        path, 1.0, offsets, _downstream_source_suffix(
            kwargs["source_geometries"]["vertical"], (1.0, 0.0), (1.0, 0.0)
        ), kwargs["source_geometries"],
    )
    result = verify_saved_candidate_bundle(**kwargs)
    assert result["status"] == "PASS_SAVED_C2_CANDIDATE_GEOMETRY"
    assert result["candidate_offsets_mm"] == [0.05, 0.0, 0.0]


def test_saved_candidate_bundle_rejects_arbitrary_path_inside_source_corridor():
    kwargs = _candidate_bundle()
    line = LineString([(0.0, 0.0), (0.5, 0.1), (1.0, 0.0)])
    line_bytes = to_wkb(line, byte_order=0, output_dimension=2, include_srid=False)
    copper, _ = buffer_centerline(line)
    copper_bytes = to_wkb(copper, byte_order=0, output_dimension=2, include_srid=False)
    kwargs.update({
        "candidate_line_wkb": line_bytes,
        "candidate_copper_wkb": copper_bytes,
        "expected_line_sha256": sha256(line_bytes).hexdigest(),
        "expected_copper_sha256": sha256(copper_bytes).hexdigest(),
    })
    kwargs["result_source_geometries"]["patch"] = copper
    with pytest.raises(PreflightError, match="C2_CANDIDATE_DOES_NOT_MATCH_FROZEN_GRID_SPEC"):
        verify_saved_candidate_bundle(**kwargs)


def test_saved_candidate_bundle_rejects_native_primitive_path_mutation():
    kwargs = _candidate_bundle()
    kwargs["source_preflight_report"]["source_path_centerline"]["native_primitives"][0]["start_xy"] = [0.001, 0.0]
    with pytest.raises(PreflightError, match="C2_SOURCE_PATH_NATIVE_GEOMETRY_MISMATCH"):
        verify_saved_candidate_bundle(**kwargs)


def test_saved_candidate_bundle_rejects_cutport_tangent_not_derived_from_native_path():
    kwargs = _candidate_bundle()
    bad_port = dict(kwargs["candidate_cut_port"], tangent_xy=[0.0, 1.0])
    kwargs["candidate_cut_port"] = bad_port
    kwargs["source_preflight_report"]["source_path_centerline"]["eligible_cut_ports"] = [bad_port]
    with pytest.raises(PreflightError, match="C2_CANDIDATE_CUTPORT_NATIVE_GEOMETRY_MISMATCH"):
        verify_saved_candidate_bundle(**kwargs)


def test_saved_candidate_bundle_rejects_native_chain_not_matching_writable_partition():
    kwargs = _candidate_bundle()
    kwargs["source_preflight_report"]["source_topology"]["ordered_writable_chain_source_ids"] = ["vertical"]
    with pytest.raises(PreflightError, match="C2_SOURCE_PATH_NATIVE_PRIMITIVES_NOT_BOUND"):
        verify_saved_candidate_bundle(**kwargs)


def test_saved_candidate_bundle_accepts_candidate_at_declared_extension_limit():
    kwargs = _candidate_bundle()
    synthetic_path = SourcePath((
        Primitive("patch", "segment", (0.0, 0.0), (0.5, 0.0), WIDTH_MM),
        Primitive("vertical", "segment", (0.5, 0.0), (1.0, 0.0), WIDTH_MM),
    ), 0.3)
    line = construct_candidate_centerline(synthetic_path, 0.8, (0.0, 0.0, 0.0))
    line_bytes = to_wkb(line, byte_order=0, output_dimension=2, include_srid=False)
    copper, _ = buffer_centerline(line)
    copper_bytes = to_wkb(copper, byte_order=0, output_dimension=2, include_srid=False)
    kwargs["candidate_line_wkb"] = line_bytes
    kwargs["candidate_copper_wkb"] = copper_bytes
    kwargs["expected_line_sha256"] = sha256(line_bytes).hexdigest()
    kwargs["expected_copper_sha256"] = sha256(copper_bytes).hexdigest()
    kwargs["expected_end_xy"] = (0.8, 0.0)
    kwargs["candidate_cut_port"] = {
        "source_id": "vertical",
        "coordinate_xy": [0.8, 0.0],
        "tangent_xy": [1.0, 0.0],
        "distance_mm": 0.8,
        "extension_mm": 0.5,
        "status": "ELIGIBLE_BOUNDED_CUT_PORT",
    }
    kwargs["source_preflight_report"]["source_path_centerline"]["eligible_cut_ports"] = [kwargs["candidate_cut_port"]]
    kwargs["source_preflight_report"]["source_path_centerline"]["initial_patch_end_mm"] = 0.3
    source_suffix = box(0.7, -0.03, 1.2, 0.03)
    kwargs["source_geometries"]["vertical"] = source_suffix
    _bind_source_geometry(kwargs, "vertical", source_suffix)
    suffix = box(0.8, -0.03, 1.2, 0.03)
    kwargs["result_source_geometries"]["vertical"] = suffix
    region = suffix.intersection(
        Point(0.8, 0.0).buffer(WIDTH_MM / 2.0 + SOURCE_SURFACE_TARGET_MM + SOURCE_GEOMETRY_TOLERANCE_MM, quad_segs=256)
    )
    kwargs["attachment_exception_regions"]["CUT_SUFFIX:vertical"] = region
    kwargs["expected_attachment_exception_sha256"]["CUT_SUFFIX:vertical"] = sha256(
        to_wkb(region, byte_order=0, output_dimension=2, include_srid=False)
    ).hexdigest()
    _, _, kwargs["result_source_geometries"] = _materialized_source_result(
        synthetic_path, 0.8, (0.0, 0.0, 0.0), _downstream_source_suffix(
            kwargs["source_geometries"]["vertical"], (0.8, 0.0), (1.0, 0.0)
        ), kwargs["source_geometries"],
    )
    result = verify_saved_candidate_bundle(**kwargs)
    assert result["status"] == "PASS_SAVED_C2_CANDIDATE_GEOMETRY"
    assert result["corridor"] == "PASS_SOURCE_BOUND"


def test_saved_candidate_archive_round_trips_and_rechecks_external_source_bindings(tmp_path):
    kwargs = _candidate_bundle()
    archive_path = tmp_path / "candidate_geometry.zip"
    archive_sha = write_candidate_geometry_archive(
        archive_path,
        candidate_line_wkb=kwargs["candidate_line_wkb"],
        candidate_copper_wkb=kwargs["candidate_copper_wkb"],
        candidate_cut_port=kwargs["candidate_cut_port"],
        candidate_offsets_mm=kwargs["candidate_offsets_mm"],
        source_preflight_report=kwargs["source_preflight_report"],
        result_source_geometries=kwargs["result_source_geometries"],
        result_lands=kwargs["result_lands"],
        attachment_exception_regions=kwargs["attachment_exception_regions"],
    )
    reference_inputs = {
        key: value
        for key, value in kwargs.items()
        if key not in {
            "candidate_line_wkb", "candidate_copper_wkb", "expected_line_sha256",
            "expected_copper_sha256", "result_source_geometries", "result_lands",
            "attachment_exception_regions",
        }
    }
    result = verify_saved_candidate_archive(
        archive_path,
        expected_archive_sha256=archive_sha,
        expected_source_preflight_report_sha256=sha256(canonical_source_preflight_report_bytes(kwargs["source_preflight_report"])).hexdigest(),
        reference_inputs=reference_inputs,
    )
    assert result["status"] == "PASS_SAVED_C2_CANDIDATE_GEOMETRY"
    assert result["serialized_candidate_reloaded"] is True
    assert result["saved_archive_sha256"] == archive_sha


def test_trusted_archive_entrypoint_rechecks_authoritative_package_before_candidate(tmp_path):
    assert "reference_inputs" not in inspect.signature(verify_saved_candidate_archive_from_c2_package).parameters
    bad_checksum = tmp_path / "tampered_t02_checksums.txt"
    bad_checksum.write_text("0" * 64 + "  review_issue_ids.json\n", encoding="utf-8")
    with pytest.raises(PreflightError, match="INHERITED_V69_REVIEW_LEDGER_HASH_MISMATCH"):
        verify_saved_candidate_archive_from_c2_package(
            tmp_path / "candidate-not-read.zip",
            expected_archive_sha256="0" * 64,
            package_manifest_path=SCENE / "package_scene_manifest.json",
            witness_path=S2A / "adaptive_patch_witness.json",
            future_work_items_path=T02 / "future_trace_work_items.json",
            t02_review_issue_ids_path=T02 / "review_issue_ids.json",
            t02_checksum_manifest_path=bad_checksum,
            candidate_cut_port={},
            candidate_offsets_mm=(0.0, 0.0, 0.0),
        )


def test_saved_candidate_archive_rejects_changed_saved_bytes(tmp_path):
    kwargs = _candidate_bundle()
    archive_path = tmp_path / "candidate_geometry.zip"
    archive_sha = write_candidate_geometry_archive(
        archive_path,
        candidate_line_wkb=kwargs["candidate_line_wkb"],
        candidate_copper_wkb=kwargs["candidate_copper_wkb"],
        candidate_cut_port=kwargs["candidate_cut_port"],
        candidate_offsets_mm=kwargs["candidate_offsets_mm"],
        source_preflight_report=kwargs["source_preflight_report"],
        result_source_geometries=kwargs["result_source_geometries"],
        result_lands=kwargs["result_lands"],
        attachment_exception_regions=kwargs["attachment_exception_regions"],
    )
    archive_path.write_bytes(archive_path.read_bytes() + b"tampered")
    reference_inputs = {
        key: value
        for key, value in kwargs.items()
        if key not in {
            "candidate_line_wkb", "candidate_copper_wkb", "expected_line_sha256",
            "expected_copper_sha256", "result_source_geometries", "result_lands",
            "attachment_exception_regions",
        }
    }
    with pytest.raises(PreflightError, match="C2_SAVED_ARCHIVE_SHA256_MISMATCH"):
        verify_saved_candidate_archive(
            archive_path,
            expected_archive_sha256=archive_sha,
            expected_source_preflight_report_sha256=sha256(canonical_source_preflight_report_bytes(kwargs["source_preflight_report"])).hexdigest(),
            reference_inputs=reference_inputs,
        )


def test_saved_candidate_archive_rejects_preflight_report_substitution(tmp_path):
    kwargs = _candidate_bundle()
    archive_path = tmp_path / "candidate_geometry.zip"
    archive_sha = write_candidate_geometry_archive(
        archive_path,
        candidate_line_wkb=kwargs["candidate_line_wkb"],
        candidate_copper_wkb=kwargs["candidate_copper_wkb"],
        candidate_cut_port=kwargs["candidate_cut_port"],
        candidate_offsets_mm=kwargs["candidate_offsets_mm"],
        source_preflight_report=kwargs["source_preflight_report"],
        result_source_geometries=kwargs["result_source_geometries"],
        result_lands=kwargs["result_lands"],
        attachment_exception_regions=kwargs["attachment_exception_regions"],
    )
    reference_inputs = {
        key: value
        for key, value in kwargs.items()
        if key not in {
            "candidate_line_wkb", "candidate_copper_wkb", "expected_line_sha256",
            "expected_copper_sha256", "result_source_geometries", "result_lands",
            "attachment_exception_regions",
        }
    }
    expected_report_sha = sha256(canonical_source_preflight_report_bytes(kwargs["source_preflight_report"])).hexdigest()
    reference_inputs["source_preflight_report"] = dict(kwargs["source_preflight_report"])
    reference_inputs["source_preflight_report"]["status"] = "ALTERED"
    with pytest.raises(PreflightError, match="C2_SAVED_ARCHIVE_SOURCE_PREFLIGHT_BINDING_MISMATCH"):
        verify_saved_candidate_archive(
            archive_path,
            expected_archive_sha256=archive_sha,
            expected_source_preflight_report_sha256=expected_report_sha,
            reference_inputs=reference_inputs,
        )


def test_saved_candidate_archive_binds_cut_port_and_offsets(tmp_path):
    kwargs = _candidate_bundle()
    archive_path = tmp_path / "candidate_geometry.zip"
    archive_sha = write_candidate_geometry_archive(
        archive_path,
        candidate_line_wkb=kwargs["candidate_line_wkb"],
        candidate_copper_wkb=kwargs["candidate_copper_wkb"],
        candidate_cut_port=kwargs["candidate_cut_port"],
        candidate_offsets_mm=kwargs["candidate_offsets_mm"],
        source_preflight_report=kwargs["source_preflight_report"],
        result_source_geometries=kwargs["result_source_geometries"],
        result_lands=kwargs["result_lands"],
        attachment_exception_regions=kwargs["attachment_exception_regions"],
    )
    reference_inputs = {
        key: value
        for key, value in kwargs.items()
        if key not in {
            "candidate_line_wkb", "candidate_copper_wkb", "expected_line_sha256",
            "expected_copper_sha256", "result_source_geometries", "result_lands",
            "attachment_exception_regions",
        }
    }
    reference_inputs["candidate_offsets_mm"] = (0.05, 0.0, 0.0)
    with pytest.raises(PreflightError, match="C2_SAVED_ARCHIVE_CANDIDATE_SPEC_MISMATCH"):
        verify_saved_candidate_archive(
            archive_path,
            expected_archive_sha256=archive_sha,
            expected_source_preflight_report_sha256=sha256(canonical_source_preflight_report_bytes(kwargs["source_preflight_report"])).hexdigest(),
            reference_inputs=reference_inputs,
        )


def test_saved_candidate_bundle_rejects_candidate_below_clearance_floor():
    with pytest.raises(PreflightError, match="C2_CANDIDATE_CLEARANCE_NOT_PASS:FAIL"):
        verify_saved_candidate_bundle(**_candidate_bundle(blocker_y=0.06))


def test_saved_candidate_bundle_rejects_changed_protected_source():
    kwargs = _candidate_bundle()
    kwargs["result_source_geometries"]["protected"] = box(0.46, 0.30, 0.56, 0.40)
    with pytest.raises(PreflightError, match="C2_PROTECTED_SOURCE_CHANGED:protected"):
        verify_saved_candidate_bundle(**kwargs)


def test_saved_candidate_bundle_rejects_incomplete_source_partition():
    kwargs = _candidate_bundle()
    kwargs["result_source_geometries"].pop("protected")
    with pytest.raises(PreflightError, match="C2_RESULT_SOURCE_PARTITION_INCOMPLETE"):
        verify_saved_candidate_bundle(**kwargs)


def test_saved_candidate_bundle_rejects_source_geometry_hash_mutation():
    kwargs = _candidate_bundle()
    kwargs["source_wkb_by_id"]["protected"] = b"mutated source geometry"
    with pytest.raises(PreflightError, match="C2_SOURCE_WKB_HASH_MISMATCH:protected"):
        verify_saved_candidate_bundle(**kwargs)


def test_saved_candidate_bundle_rejects_candidate_copper_hash_mutation():
    kwargs = _candidate_bundle()
    kwargs["candidate_copper_wkb"] += b"x"
    with pytest.raises(PreflightError, match="C2_CANDIDATE_COPPER_HASH_MISMATCH"):
        verify_saved_candidate_bundle(**kwargs)


def test_saved_candidate_bundle_rejects_self_intersecting_route_centerline():
    kwargs = _candidate_bundle()
    line = LineString([(0.0, 0.0), (0.8, 0.2), (0.2, 0.2), (0.8, -0.2), (1.0, 0.0)])
    line_bytes = to_wkb(line, byte_order=0, output_dimension=2, include_srid=False)
    copper, _ = buffer_centerline(line)
    copper_bytes = to_wkb(copper, byte_order=0, output_dimension=2, include_srid=False)
    kwargs["candidate_line_wkb"] = line_bytes
    kwargs["expected_line_sha256"] = sha256(line_bytes).hexdigest()
    kwargs["candidate_copper_wkb"] = copper_bytes
    kwargs["expected_copper_sha256"] = sha256(copper_bytes).hexdigest()
    kwargs["result_source_geometries"]["patch"] = copper
    with pytest.raises(PreflightError, match="C2_CANDIDATE_LINE_INVALID"):
        verify_saved_candidate_bundle(**kwargs)


def test_saved_candidate_bundle_rejects_source_hashes_not_matching_preflight_partition():
    kwargs = _candidate_bundle()
    kwargs["expected_source_wkb_sha256"]["protected"] = "0" * 64
    with pytest.raises(PreflightError, match="C2_SOURCE_HASHES_NOT_PREFLIGHT_BOUND"):
        verify_saved_candidate_bundle(**kwargs)


def test_saved_candidate_bundle_rejects_unbound_clearance_policy():
    kwargs = _candidate_bundle()
    kwargs["source_preflight_report"]["clearance_policy"]["hard_floor_mm"] = 0.019
    with pytest.raises(PreflightError, match="C2_CLEARANCE_POLICY_NOT_SOURCE_BOUND"):
        verify_saved_candidate_bundle(**kwargs)


def test_saved_candidate_bundle_rejects_endpoints_not_matching_preflight():
    kwargs = _candidate_bundle()
    kwargs["source_preflight_report"]["source_chain_endpoint_checks"]["directed_endpoints"][0]["start_xy"] = [0.1, 0.0]
    with pytest.raises(PreflightError, match="C2_CANDIDATE_ENDPOINTS_NOT_PREFLIGHT_BOUND"):
        verify_saved_candidate_bundle(**kwargs)


def test_saved_candidate_bundle_rejects_cut_port_outside_preflight_domain():
    kwargs = _candidate_bundle()
    kwargs["candidate_cut_port"] = dict(kwargs["candidate_cut_port"], coordinate_xy=[0.99, 0.0])
    with pytest.raises(PreflightError, match="C2_CANDIDATE_CUTPORT_NOT_IN_BOUNDED_DOMAIN"):
        verify_saved_candidate_bundle(**kwargs)


def test_saved_candidate_bundle_rejects_omitted_preflight_contact_obligations():
    kwargs = _candidate_bundle()
    required = {"id": "P1", "a": "patch", "b": "protected", "area_mm2": 0.001, "status": "PASS_RECOMPUTED"}
    kwargs["source_preflight_report"]["contact_census"] = [required]
    kwargs["source_preflight_report"]["contact_census_count"] = 1
    with pytest.raises(PreflightError, match="C2_REQUIRED_CONTACTS_NOT_PREFLIGHT_BOUND"):
        verify_saved_candidate_bundle(**kwargs)


def test_saved_candidate_bundle_rejects_candidate_outside_source_corridor():
    kwargs = _candidate_bundle()
    line = LineString([(0.0, 0.0), (0.5, 0.4), (1.0, 0.0)])
    line_bytes = to_wkb(line, byte_order=0, output_dimension=2, include_srid=False)
    copper, _ = buffer_centerline(line)
    copper_bytes = to_wkb(copper, byte_order=0, output_dimension=2, include_srid=False)
    kwargs.update({
        "candidate_line_wkb": line_bytes,
        "candidate_copper_wkb": copper_bytes,
        "expected_line_sha256": sha256(line_bytes).hexdigest(),
        "expected_copper_sha256": sha256(copper_bytes).hexdigest(),
    })
    kwargs["result_source_geometries"]["patch"] = copper
    with pytest.raises(PreflightError, match="C2_CANDIDATE_OUTSIDE_SOURCE_CORRIDOR"):
        verify_saved_candidate_bundle(**kwargs)


def test_saved_candidate_bundle_preserves_declared_contact_only_with_hash_bound_exception():
    kwargs = _candidate_bundle(blocker_y=-0.02)
    blocker = box(0.45, -0.02, 0.55, 0.02)
    kwargs["source_geometries"]["protected"] = blocker
    _bind_source_geometry(kwargs, "protected", blocker)
    kwargs["result_source_geometries"]["protected"] = blocker
    patch_copper = kwargs["result_source_geometries"]["patch"]
    overlap = float(patch_copper.intersection(blocker).area)
    exception = blocker
    exception_hash = sha256(to_wkb(exception, byte_order=0, output_dimension=2, include_srid=False)).hexdigest()
    kwargs["attachment_exception_regions"]["protected"] = exception
    kwargs["expected_attachment_exception_sha256"]["protected"] = exception_hash
    kwargs["source_preflight_report"]["attachment_exceptions"] = [
        {"kind": "ORG_SOURCE_LAND", "obstacle_source_id": "protected", "allowed_contact_region_wkb_sha256": exception_hash}
    ]
    kwargs["required_contacts"] = [{"id": "P1", "a": "patch", "b": "protected", "area_mm2": overlap}]
    kwargs["source_preflight_report"]["contact_census"] = kwargs["required_contacts"]
    kwargs["source_preflight_report"]["contact_census_count"] = 1
    kwargs["source_preflight_report"]["attachment_exceptions"] = [
        {"kind": "ORG_SOURCE_LAND", "obstacle_source_id": "protected", "allowed_contact_region_wkb_sha256": exception_hash}
    ]
    result = verify_saved_candidate_bundle(**kwargs)
    assert result["required_contacts"][0]["status"] == "PASS_GEOMETRIC_CONTACT_RETAINED"


def test_mutable_declared_contact_may_change_area_but_must_remain_connected():
    original = {"patch": box(0, 0, 1, 0.1), "protected": box(0.8, 0, 1.2, 0.1)}
    result = {"patch": box(0, 0, 0.95, 0.1), "protected": original["protected"]}
    rows = _verify_contact_obligations(
        required_contacts=[{"id": "P1", "a": "patch", "b": "protected", "area_mm2": 0.02}],
        original_features=original,
        result_features=result,
        writable_source_ids={"patch"},
        attachment_exception_regions={},
        area_tolerance_mm2=1e-12,
    )
    assert rows[0]["geometry_policy"] == "PRESERVE_POSITIVE_AREA_CONNECTION_WITHIN_DECLARED_PATCH"
    assert rows[0]["result_area_mm2"] != rows[0]["original_area_mm2"]


def test_mutable_declared_contact_rejects_disconnect():
    with pytest.raises(PreflightError, match="C2_REQUIRED_RESULT_CONTACT_DISCONNECTED:P1"):
        _verify_contact_obligations(
            required_contacts=[{"id": "P1", "a": "patch", "b": "protected", "area_mm2": 0.02}],
            original_features={"patch": box(0, 0, 1, 0.1), "protected": box(0.8, 0, 1.2, 0.1)},
            result_features={"patch": box(0, 0, 0.79, 0.1), "protected": box(0.8, 0, 1.2, 0.1)},
            writable_source_ids={"patch"},
            attachment_exception_regions={},
            area_tolerance_mm2=1e-12,
        )


def test_legacy_contact_without_id_reports_stable_identity_and_source_pair():
    contact = {"a": "source-a", "b": "source-b", "area_mm2": 0.01}
    kwargs = {
        "required_contacts": [contact],
        "original_features": {"source-a": box(0, 0, 1, 0.1), "source-b": box(0.8, 0, 1.2, 0.1)},
        "result_features": {"source-a": box(0, 0, 0.79, 0.1), "source-b": box(0.8, 0, 1.2, 0.1)},
        "writable_source_ids": {"source-a"},
        "attachment_exception_regions": {},
        "area_tolerance_mm2": 1e-12,
    }
    with pytest.raises(PreflightError, match=r"C2_REQUIRED_RESULT_CONTACT_DISCONNECTED:CONTACT-[0-9a-f]{16}\[source-a\|source-b\]") as caught:
        _verify_contact_obligations(**kwargs)
    message = str(caught.value)
    with pytest.raises(PreflightError, match=re.escape(message)):
        _verify_contact_obligations(**kwargs)


def test_protected_contact_stays_exact():
    with pytest.raises(PreflightError, match="C2_PROTECTED_CONTACT_AREA_CHANGED:P8"):
        _verify_contact_obligations(
            required_contacts=[{"id": "P8", "a": "fixed-a", "b": "fixed-b", "area_mm2": 0.02}],
            original_features={"fixed-a": box(0, 0, 1, 0.1), "fixed-b": box(0.8, 0, 1.2, 0.1)},
            result_features={"fixed-a": box(0, 0, 0.9, 0.1), "fixed-b": box(0.8, 0, 1.2, 0.1)},
            writable_source_ids=set(),
            attachment_exception_regions={},
            area_tolerance_mm2=1e-12,
        )


def test_inherited_clearance_comparison_preserves_open_rows_and_flags_new_collision():
    trace_id, rect_id = "trace", "rect"
    preflight = {"inherited_v69": {
        "clearance_findings": [{
            "trace_source_id": trace_id, "rectangle_source_id": rect_id,
            "status": "OPEN_FUTURE_TRACE_SESSION", "disposition": "DEFERRED_TO_FUTURE_TRACE_SESSION",
            "original_attachment": False,
        }],
        "overlap_findings": [],
    }, "contact_census": []}
    target = box(0, 0, 1, 0.1)
    source = {trace_id: box(0, 0.13, 1, 0.23), rect_id: target}
    unchanged = _classify_inherited_v69_findings(
        source_preflight_report=preflight, source_geometries=source, accepted_lands={rect_id: target},
        candidate_copper=box(0, 0.13, 1, 0.23), result_source_geometries=source,
        writable_source_ids={trace_id}, attachment_exception_regions={},
        hard_floor_mm=0.02, numeric_tolerance_mm=0.00001,
    )
    assert unchanged["clearance_classifications"][0]["group_classification"] == "PASS_NO_NEW_CLEARANCE_VIOLATION"
    assert unchanged["clearance_classifications"][0]["inherited_open_disposition_preserved"] is True
    with pytest.raises(PreflightError, match="C2_INHERITED_FINDING_NEW_OR_WORSENED"):
        _classify_inherited_v69_findings(
            source_preflight_report=preflight, source_geometries=source, accepted_lands={rect_id: target},
            candidate_copper=box(0, 0.11, 1, 0.21), result_source_geometries=source,
            writable_source_ids={trace_id}, attachment_exception_regions={},
            hard_floor_mm=0.02, numeric_tolerance_mm=0.00001,
        )


def test_inherited_attachment_contact_is_classified_only_from_bound_source_pair():
    trace_id, rect_id = "trace", "rect"
    target = box(0, 0, 1, 0.1)
    source = {trace_id: box(0, 0.05, 1, 0.15), rect_id: target}
    preflight = {"inherited_v69": {"clearance_findings": [{
        "trace_source_id": trace_id, "rectangle_source_id": rect_id,
        "status": "OPEN_FUTURE_TRACE_SESSION", "disposition": "DEFERRED_TO_FUTURE_TRACE_SESSION",
        "original_attachment": True,
    }], "overlap_findings": []}, "contact_census": [{"a": trace_id, "b": f"T02v69:{rect_id}"}]}
    result = _classify_inherited_v69_findings(
        source_preflight_report=preflight, source_geometries=source, accepted_lands={rect_id: target},
        candidate_copper=source[trace_id], result_source_geometries=source,
        writable_source_ids={trace_id}, attachment_exception_regions={},
        hard_floor_mm=0.02, numeric_tolerance_mm=0.00001,
    )
    assert result["clearance_classifications"][0]["group_classification"] == "AUTHORIZED_SOURCE_ATTACHMENT_CONTACT"


def test_multi_span_clearance_is_measured_once_per_protected_target_group():
    rect_id = "rect"
    trace_a, trace_b = "trace-a", "trace-b"
    target = box(0, 0, 1, 0.1)
    source = {
        trace_a: box(0.0, 0.12, 0.3, 0.22),
        trace_b: box(0.7, 0.15, 1.0, 0.25),
        rect_id: target,
    }
    preflight = {"inherited_v69": {"clearance_findings": [
        {"trace_source_id": trace_a, "rectangle_source_id": rect_id,
         "final_surface_gap_mm": 0.02, "status": "OPEN", "disposition": "OPEN", "original_attachment": False},
        {"trace_source_id": trace_b, "rectangle_source_id": rect_id,
         "final_surface_gap_mm": 0.05, "status": "OPEN", "disposition": "OPEN", "original_attachment": False},
    ], "overlap_findings": []}, "contact_census": []}
    candidate = unary_union([box(0.0, 0.14, 0.3, 0.24), box(0.7, 0.14, 1.0, 0.24)])
    result = _classify_inherited_v69_findings(
        source_preflight_report=preflight,
        source_geometries=source,
        accepted_lands={rect_id: target},
        candidate_copper=candidate,
        result_source_geometries=source,
        writable_source_ids={trace_a, trace_b},
        attachment_exception_regions={},
        hard_floor_mm=0.02,
        numeric_tolerance_mm=0.00001,
    )
    assert len(result["clearance_group_measurements"]) == 1
    group = result["clearance_group_measurements"][0]
    assert group["source_trace_ids"] == [trace_a, trace_b]
    assert group["measurement_scope"] == "CANONICAL_WRITABLE_CHAIN_VS_PROTECTED_TARGET"
    assert group["before_surface_gap_mm"] == pytest.approx(0.02)
    assert len(result["clearance_classifications"]) == 2
    assert {row["group_classification"] for row in result["clearance_classifications"]} == {"RESOLVED_IN_CANDIDATE"}
    assert {row["classification_scope"] for row in result["clearance_classifications"]} == {"CANONICAL_WRITABLE_CHAIN_VS_PROTECTED_TARGET"}


def test_multi_span_overlap_is_unioned_once_and_worsening_is_fail_closed():
    rect_id = "rect"
    trace_a, trace_b = "trace-a", "trace-b"
    target = box(0, 0, 1, 0.1)
    source = {
        trace_a: box(0.0, 0.05, 0.2, 0.15),
        trace_b: box(0.2, 0.05, 0.4, 0.15),
        rect_id: target,
    }
    preflight = {"inherited_v69": {"clearance_findings": [], "overlap_findings": [
        {"trace_source_id": trace_a, "rectangle_source_id": rect_id,
         "overlap_area_mm2": 0.01, "status": "OPEN", "disposition": "OPEN", "original_attachment": False},
        {"trace_source_id": trace_b, "rectangle_source_id": rect_id,
         "overlap_area_mm2": 0.01, "status": "OPEN", "disposition": "OPEN", "original_attachment": False},
    ]}, "contact_census": []}
    candidate = unary_union([source[trace_a], source[trace_b]])
    unchanged = _classify_inherited_v69_findings(
        source_preflight_report=preflight, source_geometries=source, accepted_lands={rect_id: target},
        candidate_copper=candidate, result_source_geometries=source,
        writable_source_ids={trace_a, trace_b}, attachment_exception_regions={},
        hard_floor_mm=0.02, numeric_tolerance_mm=0.00001,
    )
    assert len(unchanged["overlap_group_measurements"]) == 1
    assert unchanged["overlap_group_measurements"][0]["before_overlap_area_mm2"] == pytest.approx(0.02)
    assert unchanged["overlap_group_measurements"][0]["after_overlap_area_mm2"] == pytest.approx(0.02)
    worsened_candidate = unary_union([box(0.0, 0.04, 0.2, 0.15), box(0.2, 0.04, 0.4, 0.15)])
    with pytest.raises(PreflightError, match="C2_INHERITED_FINDING_NEW_OR_WORSENED"):
        _classify_inherited_v69_findings(
            source_preflight_report=preflight, source_geometries=source, accepted_lands={rect_id: target},
            candidate_copper=worsened_candidate, result_source_geometries=source,
            writable_source_ids={trace_a, trace_b}, attachment_exception_regions={},
            hard_floor_mm=0.02, numeric_tolerance_mm=0.00001,
        )


def test_inherited_attachment_contact_outside_bound_region_is_rejected():
    trace_id, rect_id = "trace", "rect"
    target = box(0, 0, 1, 0.1)
    source = {trace_id: box(0, 0.05, 1, 0.15), rect_id: target}
    preflight = {"inherited_v69": {"clearance_findings": [{
        "trace_source_id": trace_id, "rectangle_source_id": rect_id,
        "status": "OPEN_FUTURE_TRACE_SESSION", "disposition": "DEFERRED_TO_FUTURE_TRACE_SESSION",
        "original_attachment": True,
    }], "overlap_findings": []}, "contact_census": [{"a": trace_id, "b": f"T02v69:{rect_id}"}]}
    with pytest.raises(PreflightError, match="UNAUTHORIZED_SOURCE_ATTACHMENT_CONTACT"):
        _classify_inherited_v69_findings(
            source_preflight_report=preflight, source_geometries=source, accepted_lands={rect_id: target},
            candidate_copper=source[trace_id], result_source_geometries=source,
            writable_source_ids={trace_id}, attachment_exception_regions={f"T02v69:{rect_id}": box(2, 2, 3, 3)},
            hard_floor_mm=0.02, numeric_tolerance_mm=0.00001,
        )


def test_saved_candidate_bundle_rejects_unbound_attachment_exception():
    kwargs = _candidate_bundle(blocker_y=-0.02)
    kwargs["source_geometries"]["protected"] = box(0.45, -0.02, 0.55, 0.02)
    _bind_source_geometry(kwargs, "protected", kwargs["source_geometries"]["protected"])
    kwargs["result_source_geometries"]["protected"] = kwargs["source_geometries"]["protected"]
    kwargs["attachment_exception_regions"]["protected"] = kwargs["source_geometries"]["protected"]
    kwargs["expected_attachment_exception_sha256"]["protected"] = "0" * 64
    kwargs["source_preflight_report"]["attachment_exceptions"] = [
        {"kind": "ORG_SOURCE_LAND", "obstacle_source_id": "protected", "allowed_contact_region_wkb_sha256": "0" * 64}
    ]
    with pytest.raises(PreflightError, match="C2_ATTACHMENT_EXCEPTION_HASH_MISMATCH:protected"):
        verify_saved_candidate_bundle(**kwargs)


def test_saved_candidate_bundle_binds_and_checks_fixed_cut_suffix():
    kwargs = _candidate_bundle()
    source = kwargs["source_geometries"]
    output = kwargs["result_source_geometries"]
    source["vertical"] = box(0.9, -0.02, 1.2, 0.02)
    _bind_source_geometry(kwargs, "vertical", source["vertical"])
    suffix = box(1.0, -0.02, 1.2, 0.02)
    path = SourcePath((
        Primitive("patch", "segment", (0.0, 0.0), (0.5, 0.0), WIDTH_MM),
        Primitive("vertical", "segment", (0.5, 0.0), (1.0, 0.0), WIDTH_MM),
    ), 0.5)
    _, _, output = _materialized_source_result(path, 1.0, (0.0, 0.0, 0.0), suffix, source)
    kwargs["expected_source_ids"] = set(source)
    kwargs["source_preflight_report"]["source_obstacle_partition_count"] = len(source)
    kwargs["writable_source_ids"] = {"patch", "vertical"}
    kwargs["source_preflight_report"]["patch_source_ids"] = ["patch", "vertical"]
    kwargs["result_source_geometries"] = output
    suffix_key = "CUT_SUFFIX:vertical"
    region = suffix.intersection(Point(kwargs["expected_end_xy"]).buffer(WIDTH_MM / 2.0 + SOURCE_SURFACE_TARGET_MM + SOURCE_GEOMETRY_TOLERANCE_MM, quad_segs=256))
    kwargs["attachment_exception_regions"] = {suffix_key: region}
    kwargs["expected_attachment_exception_sha256"] = {
        suffix_key: sha256(to_wkb(region, byte_order=0, output_dimension=2, include_srid=False)).hexdigest()
    }
    result = verify_saved_candidate_bundle(**kwargs)
    assert result["status"] == "PASS_SAVED_C2_CANDIDATE_GEOMETRY"


def test_saved_candidate_bundle_rejects_cut_suffix_clearance_without_local_exception():
    kwargs = _candidate_bundle()
    source = kwargs["source_geometries"]
    output = kwargs["result_source_geometries"]
    source["vertical"] = box(0.9, -0.02, 1.2, 0.02)
    _bind_source_geometry(kwargs, "vertical", source["vertical"])
    suffix = box(1.0, -0.02, 1.2, 0.02)
    path = SourcePath((
        Primitive("patch", "segment", (0.0, 0.0), (0.5, 0.0), WIDTH_MM),
        Primitive("vertical", "segment", (0.5, 0.0), (1.0, 0.0), WIDTH_MM),
    ), 0.5)
    _, _, output = _materialized_source_result(path, 1.0, (0.0, 0.0, 0.0), suffix, source)
    kwargs["expected_source_ids"] = set(source)
    kwargs["source_preflight_report"]["source_obstacle_partition_count"] = len(source)
    kwargs["writable_source_ids"] = {"patch", "vertical"}
    kwargs["source_preflight_report"]["patch_source_ids"] = ["patch", "vertical"]
    kwargs["result_source_geometries"] = output
    kwargs["attachment_exception_regions"].pop("CUT_SUFFIX:vertical")
    kwargs["expected_attachment_exception_sha256"].pop("CUT_SUFFIX:vertical")
    with pytest.raises(PreflightError, match="C2_FIXED_SUFFIX_ATTACHMENT_EXCEPTION_MISSING"):
        verify_saved_candidate_bundle(**kwargs)


def test_saved_candidate_bundle_rejects_mutated_cut_suffix():
    kwargs = _candidate_bundle()
    kwargs["result_source_geometries"]["vertical"] = box(1.01, -0.03, 1.2, 0.03)
    with pytest.raises(PreflightError, match="C2_CUT_SOURCE_PREFIX_SUFFIX_ATTRIBUTION_MISMATCH"):
        verify_saved_candidate_bundle(**kwargs)


def test_saved_candidate_bundle_rejects_clearance_exception_without_physical_suffix_join():
    kwargs = _candidate_bundle()
    separated_source_suffix = box(1.06, -0.03, 1.2, 0.03)
    kwargs["source_geometries"]["vertical"] = separated_source_suffix
    _bind_source_geometry(kwargs, "vertical", separated_source_suffix)
    path = SourcePath((
        Primitive("patch", "segment", (0.0, 0.0), (0.5, 0.0), WIDTH_MM),
        Primitive("vertical", "segment", (0.5, 0.0), (1.0, 0.0), WIDTH_MM),
    ), 0.5)
    _, _, kwargs["result_source_geometries"] = _materialized_source_result(
        path, 1.0, (0.0, 0.0, 0.0), _downstream_source_suffix(separated_source_suffix, (1.0, 0.0), (1.0, 0.0)), kwargs["source_geometries"]
    )
    endpoint_region = separated_source_suffix.intersection(
        Point(kwargs["expected_end_xy"]).buffer(
            WIDTH_MM / 2.0 + SOURCE_SURFACE_TARGET_MM + SOURCE_GEOMETRY_TOLERANCE_MM,
            quad_segs=256,
        )
    )
    kwargs["attachment_exception_regions"]["CUT_SUFFIX:vertical"] = endpoint_region
    kwargs["expected_attachment_exception_sha256"]["CUT_SUFFIX:vertical"] = sha256(
        to_wkb(endpoint_region, byte_order=0, output_dimension=2, include_srid=False)
    ).hexdigest()
    with pytest.raises(PreflightError, match="C2_FIXED_SUFFIX_CONNECTIVITY_MISSING"):
        verify_saved_candidate_bundle(**kwargs)
