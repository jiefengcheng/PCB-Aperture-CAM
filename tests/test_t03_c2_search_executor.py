from __future__ import annotations

import json
from dataclasses import replace
from hashlib import sha256
from pathlib import Path
from zipfile import ZIP_STORED, ZipFile, ZipInfo

import pytest
from shapely import to_wkb
from shapely.geometry import LineString, Point, box

from src.t03_c2_search_executor import (
    PASS_STATUS,
    REJECT_STATUS,
    CandidateSpec,
    SearchDomain,
    SearchExecutorError,
    build_locked_search_domain,
    create_no_search_qualification_receipt,
    execute_ordered_search,
    _execute_ordered_search_core,
    make_trusted_candidate_evaluator,
    make_source_bound_c2_archive_factory,
)
import src.t03_c2_search_executor as executor_module
from src.t03_c2_source_verifier import verify_c2_source_obligations
import src.t03_c2_source_verifier as source_verifier_module
from src.t03_route_preflight import PreflightError, SOURCE_GEOMETRY_TOLERANCE_MM, SOURCE_SURFACE_TARGET_MM, WIDTH_MM


ROOT = Path(__file__).resolve().parents[1]
_FIXTURE_CANDIDATES = (
    ROOT / "tests/fixtures/t03_c2_packet12",
    Path(__file__).resolve().parent / "fixtures/t03_c2_packet12",
    ROOT / "out/crop_dynamic_tasks/t03_t04_s2b_c2_archive_materializer_20261026_v01/tests/fixtures/t03_c2_packet12",
)
PORTABLE_FIXTURE = next((path for path in _FIXTURE_CANDIDATES if path.is_dir()), _FIXTURE_CANDIDATES[0])
if not (
    (PORTABLE_FIXTURE / "complete_scene/package_scene_manifest.json").is_file()
    and (PORTABLE_FIXTURE / "s2a/adaptive_patch_witness.json").is_file()
    and (PORTABLE_FIXTURE / "t02_inherited/SHA256SUMS.txt").is_file()
):
    raise RuntimeError("PORTABLE_PACKET12_FIXTURE_MISSING_OR_INCOMPLETE")
EVIDENCE = PORTABLE_FIXTURE
SCENE = EVIDENCE / "complete_scene"
S2A = EVIDENCE / "s2a"
T02 = EVIDENCE / "t02_inherited"


@pytest.fixture(scope="module")
def source_report():
    return verify_c2_source_obligations(
        SCENE / "package_scene_manifest.json",
        S2A / "adaptive_patch_witness.json",
        T02 / "future_trace_work_items.json",
        T02 / "review_issue_ids.json",
        T02 / "SHA256SUMS.txt",
    )


@pytest.fixture(scope="module")
def domain(source_report):
    return build_locked_search_domain(source_report)


def test_real_source_bound_domain_is_four_ports_and_1372_stable_candidates(domain):
    assert len(domain.candidates) == 1_372
    assert len({row.candidate_id for row in domain.candidates}) == 1_372
    assert [domain.candidates[i].cut_port["extension_mm"] for i in (0, 343, 686, 1029)] == [0.225, 0.25, 0.275, 0.3]
    keys = [
        (
            row.cut_port["extension_mm"],
            max(abs(value) for value in row.offsets_mm),
            sum(abs(value) for value in row.offsets_mm),
            *row.offsets_mm,
            row.cut_port["source_id"],
        )
        for row in domain.candidates
    ]
    assert keys == sorted(keys)
    assert len(domain.domain_sha256) == 64


def test_no_search_qualification_binds_real_sources_and_creates_no_candidates(source_report):
    receipt = create_no_search_qualification_receipt(
        source_report,
        executor_source_path=ROOT / "src/t03_c2_search_executor.py",
    )
    assert receipt["status"] == "PASS_SEARCH_EXECUTOR_PREFLIGHT_NO_CANDIDATES_GENERATED"
    assert receipt["candidate_count"] == 1_372
    assert receipt["eligible_port_count"] == 4
    assert receipt["attempted_candidate_count"] == 0
    assert receipt["route_search_executed"] is False
    assert receipt["route_geometry_created"] is False
    assert receipt["source_sha256"] == source_report["source_sha256"]


def test_executor_stops_on_first_trusted_pass_and_records_each_attempt(domain, tmp_path):
    ledger = tmp_path / "attempts.jsonl"
    calls = []

    def evaluate(candidate):
        calls.append(candidate.candidate_id)
        if len(calls) == 1:
            return {"status": REJECT_STATUS, "reason_code": "SYNTHETIC_CLEARANCE_REJECT"}
        return {"status": PASS_STATUS, "saved_archive_sha256": "a" * 64}

    result = _execute_ordered_search_core(domain, evaluate=evaluate, attempt_ledger_path=ledger)
    rows = [json.loads(line) for line in ledger.read_text().splitlines()]
    assert result["status"] == "FIRST_VALID_CANDIDATE"
    assert result["attempted_candidate_count"] == 2
    assert len(calls) == 2
    assert [row["ordinal"] for row in rows] == [1, 2]
    assert rows[0]["reason_code"] == "SYNTHETIC_CLEARANCE_REJECT"
    assert rows[1]["status"] == "PASS_FIRST_VALID_CANDIDATE"
    assert result["candidate_accepted_for_engineering_or_manufacture"] is False


def test_executor_records_bounded_no_pass_when_all_candidates_reject(domain, tmp_path):
    ledger = tmp_path / "attempts.jsonl"
    calls = 0

    def evaluate(_candidate):
        nonlocal calls
        calls += 1
        return {"status": REJECT_STATUS, "reason_code": "SYNTHETIC_BLOCKED"}

    result = _execute_ordered_search_core(domain, evaluate=evaluate, attempt_ledger_path=ledger)
    assert result["status"] == "NO_VALID_CANDIDATE_WITHIN_FROZEN_BOUNDS"
    assert result["attempted_candidate_count"] == 1_372
    assert calls == 1_372
    assert len(ledger.read_text().splitlines()) == 1_372


@pytest.mark.parametrize(
    "outcome",
    [None, {"status": "PASS_GEOMETRIC_CLEARANCE_ONLY"}, {"status": PASS_STATUS}],
)
def test_executor_aborts_on_unknown_or_incomplete_verifier_outcome(domain, tmp_path, outcome):
    ledger = tmp_path / "attempts.jsonl"
    result = _execute_ordered_search_core(domain, evaluate=lambda _candidate: outcome, attempt_ledger_path=ledger)
    assert result["status"] == "ABORTED_EXECUTION"
    assert len(ledger.read_text().splitlines()) == 1
    assert json.loads(ledger.read_text())["status"].startswith("ABORTED_")


def test_executor_aborts_and_logs_unexpected_exception(domain, tmp_path):
    ledger = tmp_path / "attempts.jsonl"

    def evaluate(_candidate):
        raise RuntimeError("synthetic verifier crash")

    result = _execute_ordered_search_core(domain, evaluate=evaluate, attempt_ledger_path=ledger)
    assert result["status"] == "ABORTED_EXECUTION"
    record = json.loads(ledger.read_text())
    assert record["status"] == "ABORTED_EVALUATOR_EXCEPTION"
    assert record["error_type"] == "RuntimeError"


def test_executor_refuses_to_overwrite_attempt_history(domain, tmp_path):
    ledger = tmp_path / "attempts.jsonl"
    ledger.write_text("prior record\n")
    with pytest.raises(SearchExecutorError, match="SEARCH_ATTEMPT_LEDGER_ALREADY_EXISTS"):
        _execute_ordered_search_core(domain, evaluate=lambda _: {}, attempt_ledger_path=ledger)


def test_public_executor_refuses_untrusted_evaluator(domain, tmp_path):
    ledger = tmp_path / "attempts.jsonl"
    with pytest.raises(SearchExecutorError, match="SEARCH_TRUSTED_EVALUATOR_REQUIRED"):
        execute_ordered_search(domain, evaluate=lambda _: {}, attempt_ledger_path=ledger)
    assert not ledger.exists()


def test_public_executor_binds_completed_receipt_to_package_code_archive_and_ledger(monkeypatch, domain, tmp_path):
    package = tmp_path / "package.json"
    package.write_text("same-package")
    package_hash = sha256(package.read_bytes()).hexdigest()
    archive_dir = tmp_path / "archives"
    archive_dir.mkdir()

    def archive_factory(candidate):
        path = archive_dir / f"{candidate.candidate_id}.zip"
        path.write_bytes(candidate.candidate_id.encode())
        return path, sha256(path.read_bytes()).hexdigest()

    def fake_verify(**kwargs):
        return {
            "status": PASS_STATUS,
            "serialized_candidate_reloaded": True,
            "saved_archive_sha256": kwargs["expected_archive_sha256"],
            "trusted_source_package_manifest_sha256": package_hash,
            "trusted_source_package_preflight_sha256": domain.source_report_sha256,
            "trusted_invocation_boundary": "PASS_REVERIFIED_C2_PACKAGE",
        }

    monkeypatch.setattr(executor_module, "verify_saved_candidate_archive_from_c2_package", fake_verify)
    evaluate = make_trusted_candidate_evaluator(
        archive_factory=archive_factory,
        package_manifest_path=package,
        witness_path=tmp_path / "witness.json",
        future_work_items_path=tmp_path / "future.json",
        t02_review_issue_ids_path=tmp_path / "issues.json",
        t02_checksum_manifest_path=tmp_path / "checksums.txt",
    )
    ledger = tmp_path / "attempts.jsonl"
    state = tmp_path / "state.json"
    result = execute_ordered_search(
        domain, evaluate=evaluate, attempt_ledger_path=ledger, state_receipt_path=state
    )
    assert result["status"] == "FIRST_VALID_CANDIDATE"
    assert result["candidate_accepted_for_engineering_or_manufacture"] is False
    assert result["source_package_manifest_sha256"] == package_hash
    assert result["source_preflight_report_sha256"] == domain.source_report_sha256
    assert result["executor_source_sha256"] == sha256(Path(executor_module.__file__).read_bytes()).hexdigest()
    assert result["attempt_ledger_sha256"] == sha256(ledger.read_bytes()).hexdigest()
    assert result["saved_archive_path"] == str(next(archive_dir.glob("*.zip")).resolve())
    assert json.loads(state.read_text())["status"] == "FIRST_VALID_CANDIDATE"


def test_changed_source_binding_fails_before_domain_enumeration(source_report):
    bad = dict(source_report)
    bad["source_sha256"] = "0" * 64
    with pytest.raises(SearchExecutorError, match="SEARCH_SOURCE_HASH_CHANGED"):
        build_locked_search_domain(bad)


def test_changed_or_reordered_port_report_fails_closed(source_report):
    bad = dict(source_report)
    bad_info = dict(source_report["source_path_centerline"])
    bad["source_path_centerline"] = bad_info
    bad_ports = list(bad_info["eligible_cut_ports"])
    bad_info["eligible_cut_ports"] = list(reversed(bad_ports))
    with pytest.raises(SearchExecutorError, match="SEARCH_PORT_REPORT_BINDING_MISMATCH"):
        build_locked_search_domain(bad)


def test_executor_rejects_caller_reordered_or_duplicated_domain(domain, tmp_path):
    ledger = tmp_path / "attempts.jsonl"
    reordered = replace(domain, candidates=(domain.candidates[1], domain.candidates[0], *domain.candidates[2:]))
    with pytest.raises(SearchExecutorError, match="SEARCH_DOMAIN_NOT_LOCKED"):
        _execute_ordered_search_core(reordered, evaluate=lambda _: {}, attempt_ledger_path=ledger)
    assert not ledger.exists()
    duplicated = replace(domain, candidates=(domain.candidates[0], *domain.candidates[:-1]))
    with pytest.raises(SearchExecutorError, match="SEARCH_DOMAIN_NOT_LOCKED"):
        _execute_ordered_search_core(duplicated, evaluate=lambda _: {}, attempt_ledger_path=ledger)
    assert not ledger.exists()


def test_executor_keeps_running_state_unfinished_on_rejection_then_exception(domain, tmp_path):
    ledger = tmp_path / "attempts.jsonl"
    state = tmp_path / "state.json"
    calls = 0

    def evaluate(_candidate):
        nonlocal calls
        calls += 1
        if calls == 1:
            return {"status": REJECT_STATUS, "reason_code": "SYNTHETIC_CLEARANCE_REJECT"}
        raise RuntimeError("synthetic crash after a rejection")

    result = _execute_ordered_search_core(domain, evaluate=evaluate, attempt_ledger_path=ledger, state_receipt_path=state)
    assert result["status"] == "ABORTED_EXECUTION"
    assert json.loads(state.read_text())["status"] == "ABORTED_EXECUTION"
    assert len(ledger.read_text().splitlines()) == 2
    with pytest.raises(SearchExecutorError, match="SEARCH_ATTEMPT_LEDGER_ALREADY_EXISTS"):
        _execute_ordered_search_core(domain, evaluate=lambda _: {}, attempt_ledger_path=ledger, state_receipt_path=state)


def test_trusted_evaluator_uses_source_package_boundary_and_pinned_candidate(monkeypatch, domain, tmp_path):
    observed = {}
    package_manifest = tmp_path / "package.json"
    package_manifest.write_text("trusted synthetic package")
    package_sha256 = sha256(package_manifest.read_bytes()).hexdigest()
    archive = tmp_path / "candidate.zip"
    archive.write_bytes(b"synthetic-archive")
    archive_sha256 = sha256(archive.read_bytes()).hexdigest()

    def fake_verify(**kwargs):
        observed.update(kwargs)
        return {
            "status": PASS_STATUS, "serialized_candidate_reloaded": True,
            "saved_archive_sha256": archive_sha256,
            "trusted_source_package_manifest_sha256": package_sha256,
            "trusted_source_package_preflight_sha256": domain.source_report_sha256,
            "trusted_invocation_boundary": "PASS_REVERIFIED_C2_PACKAGE",
        }

    monkeypatch.setattr(executor_module, "verify_saved_candidate_archive_from_c2_package", fake_verify)
    candidate = domain.candidates[0]
    evaluate = make_trusted_candidate_evaluator(
        archive_factory=lambda item: (archive, archive_sha256),
        package_manifest_path=package_manifest,
        witness_path=tmp_path / "witness.json",
        future_work_items_path=tmp_path / "future.json",
        t02_review_issue_ids_path=tmp_path / "issues.json",
        t02_checksum_manifest_path=tmp_path / "checksums.txt",
    )
    result = evaluate(candidate)
    assert result["status"] == PASS_STATUS
    assert result["saved_archive_sha256"] == archive_sha256
    assert result["saved_archive_path"] == str(archive.resolve())
    assert observed["expected_archive_sha256"] == archive_sha256
    assert observed["candidate_cut_port"] == candidate.cut_port
    assert observed["candidate_offsets_mm"] == tuple(float(v) for v in candidate.offsets_mm)
    assert "reference_inputs" not in observed


def test_source_bound_archive_factory_round_trips_through_real_saved_archive_verifier(monkeypatch, tmp_path):
    """Exercise materialization plus the real archive/package verifier on a tiny scene.

    The source-preflight authority adapter is deliberately synthetic; all archive
    parsing, source/land hash binding, suffix derivation, and geometry checks below
    use the production verifier implementation. This is not a real C2 package run.
    """
    from src.t03_route_preflight import Primitive, SourcePath

    package_root = tmp_path / "package"
    package_root.mkdir()
    package_manifest_path = package_root / "manifest.json"
    package_manifest_path.write_text('{"schema":"synthetic-test-package"}')
    source_geometries = {
        "patch": box(0.0, -WIDTH_MM / 2, 0.5, WIDTH_MM / 2),
        "vertical": box(0.5, -0.03, 1.2, 0.03),
        "protected": box(0.0, 0.3, 1.0, 0.4),
    }
    lands = {"land-1": box(4.0, 4.0, 4.2, 4.2)}
    source_payloads = {
        key: to_wkb(value, byte_order=0, output_dimension=2, include_srid=False)
        for key, value in source_geometries.items()
    }
    source_hashes = {key: sha256(value).hexdigest() for key, value in source_payloads.items()}
    with ZipFile(package_root / "org.zip", "w") as archive:
        for source_id, payload in source_payloads.items():
            archive.writestr(f"{source_hashes[source_id]}.wkb", payload)
    land_payload = to_wkb(lands["land-1"], byte_order=0, output_dimension=2, include_srid=False)
    (package_root / "land-targets").mkdir()
    (package_root / "land-targets" / "land.wkb").write_bytes(land_payload)
    (package_root / "lands.json").write_text(json.dumps({"targets": [{
        "source_id": "land-1", "candidate_wkb_path": "nested/land.wkb",
        "candidate_wkb_sha256": sha256(land_payload).hexdigest(),
    }]}))

    line = LineString([(0.0, 0.0), (0.5, 0.0), (1.0, 0.0)])
    line_payload = to_wkb(line, byte_order=0, output_dimension=2, include_srid=False)
    port = {
        "source_id": "vertical", "coordinate_xy": [1.0, 0.0],
        "tangent_xy": [1.0, 0.0], "distance_mm": 1.0,
        "extension_mm": 0.5, "status": "ELIGIBLE_BOUNDED_CUT_PORT",
    }
    candidate = CandidateSpec(1, "c" * 64, port, (0.0, 0.0, 0.0))
    report = {
        "status": "PASS_C2_SOURCE_BOUND_PREFLIGHT_OBLIGATIONS",
        "source_sha256": "f" * 64,
        "inventory_sha256": "1" * 64,
        "source_obstacle_partition_count": len(source_geometries),
        "accepted_land_partition_count": len(lands),
        "source_obstacle_partition": [
            {"source_id": sid, "geometry_sha256": source_hashes[sid]}
            for sid in source_geometries
        ],
        "accepted_land_partition": [{"source_id": "land-1", "wkb_sha256": sha256(land_payload).hexdigest()}],
        "required_p1_p8_count": 0,
        "required_p1_p8_checks": [],
        "contact_census_count": 0,
        "contact_census": [],
        "patch_source_ids": ["patch", "vertical"],
        "attachment_exceptions": [],
        "clearance_policy": {
            "sha256": "a" * 64, "measurement": "FINITE_WIDTH_COPPER_SURFACE",
            "width_mm": WIDTH_MM, "quad_segs": 256,
            "hard_floor_mm": 0.02, "construction_target_mm": 0.02002,
            "numeric_tolerance_mm": 0.00001,
        },
        "source_chain_endpoint_checks": {"directed_endpoints": [{"start_xy": [0.0, 0.0]}]},
        "source_topology": {"ordered_writable_chain_source_ids": ["patch", "vertical"]},
        "source_path_centerline": {
            "coordinates": [list(point) for point in line.coords],
            "wkb_sha256": sha256(line_payload).hexdigest(),
            "native_primitives": [
                {"source_id": "patch", "kind": "segment", "start_xy": [0.0, 0.0], "end_xy": [0.5, 0.0], "mid_xy": None, "width_mm": WIDTH_MM},
                {"source_id": "vertical", "kind": "segment", "start_xy": [0.5, 0.0], "end_xy": [1.0, 0.0], "mid_xy": None, "width_mm": WIDTH_MM},
            ],
            "max_lateral_offset_mm": 0.25, "tessellation_sagitta_mm": 0.00001,
            "initial_patch_end_mm": 0.5, "max_extension_mm": 0.5,
            "status": "PASS_NATIVE_RECORD_DERIVED_CENTERLINE",
            "eligible_cut_ports": [port],
        },
    }
    path = SourcePath((
        Primitive("patch", "segment", (0.0, 0.0), (0.5, 0.0), WIDTH_MM),
        Primitive("vertical", "segment", (0.5, 0.0), (1.0, 0.0), WIDTH_MM),
    ), 0.5)
    domain = SearchDomain(report, path, (candidate,), "d" * 64, "e" * 64)
    monkeypatch.setattr(executor_module, "load_c2_search_domain", lambda **_kwargs: domain)
    scene_spec = {
        "org_archive": {"path": "org.zip"},
        "land_manifest": {"path": "lands.json", "target_root": "land-targets"},
    }
    scene_loader_result = (
        package_root, {}, scene_spec, b"", [{"id": sid} for sid in source_geometries],
        source_geometries, lands,
    )
    monkeypatch.setattr(executor_module, "_load_scene", lambda _path: scene_loader_result)
    monkeypatch.setattr(source_verifier_module, "verify_c2_source_obligations", lambda *_args: report)
    monkeypatch.setattr(source_verifier_module, "_load_scene", lambda _path: scene_loader_result)

    verifier_args = {
        "package_manifest_path": package_manifest_path,
        "witness_path": package_root / "witness.json",
        "future_work_items_path": package_root / "future.json",
        "t02_review_issue_ids_path": package_root / "issues.json",
        "t02_checksum_manifest_path": package_root / "checksums.txt",
        "candidate_cut_port": port,
        "candidate_offsets_mm": (0.0, 0.0, 0.0),
    }
    archive_factory = make_source_bound_c2_archive_factory(
        **{key: value for key, value in verifier_args.items() if key not in {"candidate_cut_port", "candidate_offsets_mm"}},
        output_directory=tmp_path / "candidates",
    )
    evaluate = make_trusted_candidate_evaluator(archive_factory=archive_factory, **{
        key: value for key, value in verifier_args.items()
        if key in {"package_manifest_path", "witness_path", "future_work_items_path", "t02_review_issue_ids_path", "t02_checksum_manifest_path"}
    })
    outcome = evaluate(candidate)
    archives = list((tmp_path / "candidates").glob("*.zip"))
    assert len(archives) == 1
    archive_path = archives[0]
    archive_sha256 = sha256(archive_path.read_bytes()).hexdigest()
    assert outcome["status"] == PASS_STATUS
    assert outcome["saved_archive_sha256"] == archive_sha256
    assert outcome["trusted_source_package_manifest_sha256"] == sha256(package_manifest_path.read_bytes()).hexdigest()

    def verify(path: Path, expected_hash: str, cut_port=port):
        return source_verifier_module.verify_saved_candidate_archive_from_c2_package(
            path, expected_archive_sha256=expected_hash, **{**verifier_args, "candidate_cut_port": cut_port},
        )

    with pytest.raises(PreflightError, match="C2_SAVED_ARCHIVE_SHA256_MISMATCH"):
        corrupted = tmp_path / "corrupt.zip"
        corrupted.write_bytes(archive_path.read_bytes() + b"corrupt")
        verify(corrupted, archive_sha256)
    with pytest.raises(PreflightError, match="C2_TRUSTED_CANDIDATE_CUTPORT_NOT_IN_DOMAIN"):
        verify(archive_path, archive_sha256, {**port, "coordinate_xy": [0.99, 0.0]})

    def rewrite_member(output_path: Path, member_name: str, payload: bytes) -> str:
        with ZipFile(archive_path) as original:
            members = {name: original.read(name) for name in original.namelist()}
        manifest = json.loads(members["manifest.json"])
        members[member_name] = payload
        manifest["members"][member_name] = sha256(payload).hexdigest()
        members["manifest.json"] = (json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n").encode()
        with ZipFile(output_path, "w", compression=ZIP_STORED) as mutated:
            for name, data in sorted(members.items()):
                info = ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
                info.compress_type = ZIP_STORED
                info.external_attr = 0o100644 << 16
                mutated.writestr(info, data)
        return sha256(output_path.read_bytes()).hexdigest()

    patch_member = f"result/source/{sha256(b'patch').hexdigest()}.wkb"
    bad_attribution = tmp_path / "bad-attribution.zip"
    bad_patch = to_wkb(box(0.0, -WIDTH_MM / 2, 0.7, WIDTH_MM / 2), byte_order=0, output_dimension=2, include_srid=False)
    bad_attribution_hash = rewrite_member(bad_attribution, patch_member, bad_patch)
    with pytest.raises(PreflightError, match="C2_CANDIDATE_SOURCE_SPAN_ATTRIBUTION_MISMATCH:patch"):
        verify(bad_attribution, bad_attribution_hash)

    suffix_member = f"result/source/{sha256(b'vertical').hexdigest()}.wkb"
    bad_suffix = tmp_path / "bad-suffix.zip"
    suffix_payload = to_wkb(box(1.01, -0.03, 1.2, 0.03), byte_order=0, output_dimension=2, include_srid=False)
    bad_suffix_hash = rewrite_member(bad_suffix, suffix_member, suffix_payload)
    with pytest.raises(PreflightError, match="C2_CUT_SOURCE_PREFIX_SUFFIX_ATTRIBUTION_MISMATCH"):
        verify(bad_suffix, bad_suffix_hash)
