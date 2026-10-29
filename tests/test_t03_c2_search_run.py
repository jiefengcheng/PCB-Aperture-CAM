from __future__ import annotations

import json
import hashlib
import shutil
import uuid
from dataclasses import replace
from pathlib import Path

import pytest
from shapely.geometry import box, LineString
from shapely import wkb

from src import t03_c2_search_run as launcher
from src.t03_c2_cumulative_result import render_verified_cumulative_scene
from src import t03_c2_search_guard as integrity_guard
from src.t03_c2_source_verifier import write_candidate_geometry_archive


def test_source_bound_preflight_pins_the_exact_domain_without_search():
    domain, binding = launcher.verify_preflight_bindings()
    assert len(domain.candidates) == 1_372
    assert domain.domain_sha256 == launcher.LOCKED["domain_sha256"]
    assert binding["source_sha256"] == "850c4c74d55717a721d4bbed7ec876ee086f475efd97f69bb5b5164ef77533a0"
    assert binding["candidate_count"] == 1_372


def test_checkpoint_hash_mismatch_aborts_before_domain_or_run_directory(monkeypatch, tmp_path):
    pins = dict(launcher.LOCKED)
    pins["packet12_zip_sha256"] = "0" * 64
    called = False

    def forbidden_loader(**_kwargs):
        nonlocal called
        called = True
        raise AssertionError("domain must not be loaded after checkpoint mismatch")

    run_id = f"test_hash_{uuid.uuid4().hex}"
    with pytest.raises(RuntimeError, match="PACKET12_SHA256_MISMATCH"):
        launcher.launch_one_bounded_search(
            run_id,
            pins=pins,
            domain_loader=forbidden_loader,
            repo_root=launcher.REPO_ROOT,
        )
    assert not called
    assert not (launcher.RUNS_ROOT / run_id).exists()


@pytest.mark.parametrize("mutated", ["launcher", "renderer"])
def test_independent_guard_rejects_mutated_executable_before_launch(tmp_path, mutated):
    launcher_copy = tmp_path / "t03_c2_search_run.py"
    renderer_copy = tmp_path / "t03_c2_cumulative_result.py"
    launcher_copy.write_bytes(integrity_guard.LAUNCHER_PATH.read_bytes())
    renderer_copy.write_bytes(integrity_guard.RENDERER_PATH.read_bytes())
    target = launcher_copy if mutated == "launcher" else renderer_copy
    target.write_bytes(target.read_bytes() + b"\\n# post-audit mutation\\n")
    called = []

    with pytest.raises(RuntimeError, match=f"EXECUTION_GUARD_{mutated.upper()}_SHA256_MISMATCH"):
        integrity_guard.run_guarded(
            "must_not_launch",
            launcher_path=launcher_copy,
            renderer_path=renderer_copy,
            launch=lambda run_id: called.append(run_id) or 0,
        )
    assert called == []
    assert not (launcher.RUNS_ROOT / "must_not_launch").exists()


def test_direct_launcher_cli_requires_guard_and_creates_no_run_directory(monkeypatch, capsys):
    run_id = f"test_unguarded_cli_{uuid.uuid4().hex}"
    monkeypatch.delenv("T03_C2_EXECUTION_GUARD", raising=False)
    assert launcher.main(["--run-id", run_id]) == 2
    assert "EXECUTION_GUARD_REQUIRED" in capsys.readouterr().err
    assert not (launcher.RUNS_ROOT / run_id).exists()


def test_missing_witness_aborts_before_directory_creation(tmp_path):
    def missing_witness_loader(**_kwargs):
        raise RuntimeError("C2_SOURCE_WITNESS_MISSING")

    run_id = f"test_witness_{uuid.uuid4().hex}"
    with pytest.raises(RuntimeError, match="C2_SOURCE_WITNESS_MISSING"):
        launcher.launch_one_bounded_search(run_id, domain_loader=missing_witness_loader)
    assert not (launcher.RUNS_ROOT / run_id).exists()


def test_exact_launcher_production_factory_rejects_unbound_cut_port_before_archive(tmp_path):
    class ProductionFactoryFaultAPI:
        def make_source_bound_c2_archive_factory(self, **kwargs):
            factory = launcher.executor.make_source_bound_c2_archive_factory(**kwargs)
            domain = launcher.executor.load_c2_search_domain(**launcher._package_paths(launcher.FIXTURE_ROOT))
            first = domain.candidates[0]
            invalid_port = {**first.cut_port, "source_id": "not-a-domain-source"}
            factory(replace(first, cut_port=invalid_port))
            return factory

        def make_trusted_candidate_evaluator(self, **_kwargs):
            raise AssertionError("evaluator must not be constructed after invalid-port rejection")

        def execute_ordered_search(self, *_args, **_kwargs):
            raise AssertionError("search must not run after invalid-port rejection")

    run_id = f"test_real_factory_port_{uuid.uuid4().hex}"
    root = launcher.RUNS_ROOT / run_id
    with pytest.raises(Exception, match="ARCHIVE_FACTORY_CANDIDATE_NOT_SOURCE_BOUND"):
        launcher.launch_one_bounded_search(run_id, api=ProductionFactoryFaultAPI())
    try:
        abort = json.loads((root / "launcher_abort.json").read_text())
        assert abort["status"] == "ABORTED_LAUNCHER_EXCEPTION"
        assert not list((root / "archives").glob("*.zip"))
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_exact_launcher_production_evaluator_exception_fails_closed(monkeypatch):
    class ProductionEvaluatorFaultAPI:
        PASS_STATUS = launcher.executor.PASS_STATUS

        def make_source_bound_c2_archive_factory(self, *, output_directory, **_kwargs):
            output_directory.mkdir(parents=True, exist_ok=True)

            def make_placeholder_archive(_candidate):
                path = output_directory / "verifier-exception-placeholder.bin"
                payload = b"not route geometry; verifier exception fault injection"
                path.write_bytes(payload)
                return path, hashlib.sha256(payload).hexdigest()

            return make_placeholder_archive

        def make_trusted_candidate_evaluator(self, **kwargs):
            evaluator = launcher.executor.make_trusted_candidate_evaluator(**kwargs)
            domain = launcher.executor.load_c2_search_domain(**launcher._package_paths(launcher.FIXTURE_ROOT))
            evaluator(domain.candidates[0])
            return evaluator

        def execute_ordered_search(self, *_args, **_kwargs):
            raise AssertionError("search must not run after injected trusted-verifier exception")

    def injected_verifier_failure(**_kwargs):
        raise RuntimeError("INJECTED_TRUSTED_VERIFIER_EXCEPTION")

    monkeypatch.setattr(launcher.executor, "verify_saved_candidate_archive_from_c2_package", injected_verifier_failure)
    run_id = f"test_real_verifier_exception_{uuid.uuid4().hex}"
    root = launcher.RUNS_ROOT / run_id
    with pytest.raises(RuntimeError, match="INJECTED_TRUSTED_VERIFIER_EXCEPTION"):
        launcher.launch_one_bounded_search(run_id, api=ProductionEvaluatorFaultAPI())
    try:
        abort = json.loads((root / "launcher_abort.json").read_text())
        assert abort["status"] == "ABORTED_LAUNCHER_EXCEPTION"
        assert abort["deliverable_status"] == "INCOMPLETE_NO_SEARCH_RESULT_ACCEPTANCE"
        assert not (root / "search_result.json").exists()
    finally:
        shutil.rmtree(root, ignore_errors=True)


class _NoSearchAPI:
    PASS_STATUS = "PASS_SAVED_C2_CANDIDATE_GEOMETRY"

    def __init__(self, *, factory_error=None, execute_result=None, execute_error=None):
        self.factory_error = factory_error
        self.execute_result = execute_result or {"status": "ABORTED_EXECUTION", "attempted_candidate_count": 0}
        self.execute_error = execute_error
        self.calls = []

    def make_source_bound_c2_archive_factory(self, **kwargs):
        self.calls.append("factory")
        if self.factory_error:
            raise self.factory_error
        return lambda candidate: (_ for _ in ()).throw(AssertionError("no candidates may be materialized"))

    def make_trusted_candidate_evaluator(self, **kwargs):
        self.calls.append("evaluator")
        return object()

    def execute_ordered_search(self, *args, **kwargs):
        self.calls.append("execute")
        if self.execute_error:
            raise self.execute_error
        return self.execute_result


@pytest.mark.parametrize(
    "api,expected",
    [
        (_NoSearchAPI(factory_error=RuntimeError("C2_TRUSTED_CANDIDATE_CUTPORT_NOT_IN_DOMAIN")), "C2_TRUSTED_CANDIDATE_CUTPORT_NOT_IN_DOMAIN"),
        (_NoSearchAPI(execute_error=RuntimeError("SAVED_ARCHIVE_VERIFIER_EXCEPTION")), "SAVED_ARCHIVE_VERIFIER_EXCEPTION"),
        (_NoSearchAPI(execute_error=InterruptedError("TEST_INTERRUPTION")), "TEST_INTERRUPTION"),
        (_NoSearchAPI(execute_result={"status": "UNEXPECTED_STATUS"}), "UNEXPECTED_EXECUTOR_RESULT"),
    ],
)
def test_exact_launcher_fails_closed_without_materializing_candidates(api, expected):
    run_id = f"test_abort_{uuid.uuid4().hex}"
    with pytest.raises(Exception, match=expected):
        launcher.launch_one_bounded_search(run_id, api=api)
    root = launcher.RUNS_ROOT / run_id
    try:
        assert root.is_dir()
        abort = json.loads((root / "launcher_abort.json").read_text())
        assert abort["status"] in {"ABORTED_LAUNCHER_EXCEPTION", "ABORTED_UNEXPECTED_EXECUTOR_RESULT", "ABORTED_INTERRUPTED"}
        assert not list((root / "archives").glob("*.zip")) if (root / "archives").exists() else True
        assert "execute" not in api.calls or api.execute_error is not None or api.execute_result["status"] == "UNEXPECTED_STATUS"
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_fresh_run_directory_is_exclusive():
    run_id = f"test_existing_{uuid.uuid4().hex}"
    root = launcher.RUNS_ROOT / run_id
    root.mkdir(parents=True)
    try:
        with pytest.raises(RuntimeError, match="RUN_DIRECTORY_ALREADY_EXISTS"):
            launcher.launch_one_bounded_search(run_id)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_executor_abort_is_not_misreported_as_bounded_no_pass():
    api = _NoSearchAPI(execute_result={"status": "ABORTED_EXECUTION", "reason_code": "INJECTED_ABORT"})
    run_id = f"test_executor_abort_{uuid.uuid4().hex}"
    try:
        result = launcher.launch_one_bounded_search(run_id, api=api)
        assert result["deliverable_status"] == "INCOMPLETE_ABORTED_EXECUTION"
        assert result["status"] == "ABORTED_EXECUTION"
    finally:
        shutil.rmtree(launcher.RUNS_ROOT / run_id, ignore_errors=True)


def test_post_pass_renderer_failure_records_incomplete_delivery_and_never_writes_result():
    class PassThenRendererFailAPI:
        PASS_STATUS = "PASS_SAVED_C2_CANDIDATE_GEOMETRY"

        def __init__(self):
            self.archive_path = None
            self.archive_sha = None

        def make_source_bound_c2_archive_factory(self, *, output_directory, **_kwargs):
            output_directory.mkdir(parents=True, exist_ok=True)
            self.archive_path = output_directory / "synthetic-pass.zip"
            payload = b"synthetic-only post-pass binding fixture"
            self.archive_path.write_bytes(payload)
            self.archive_sha = hashlib.sha256(payload).hexdigest()
            return lambda _candidate: (self.archive_path, self.archive_sha)

        def make_trusted_candidate_evaluator(self, **_kwargs):
            return object()

        def execute_ordered_search(self, domain, **_kwargs):
            return {
                "status": "FIRST_VALID_CANDIDATE",
                "candidate_id": domain.candidates[0].candidate_id,
                "saved_archive_path": str(self.archive_path),
                "saved_archive_sha256": self.archive_sha,
            }

        def _load_scene(self, _manifest_path):
            return None, None, {
                "accepted_scene": {
                    "receipt_commit": "fixture",
                    "t02_result": "v69",
                    "t02_policy": "v15",
                }
            }, None, [{}] * 17_849, {"source": box(0, 0, 1, 1)}, {f"land-{i}": box(i + 2, 0, i + 3, 1) for i in range(80)}

    api = PassThenRendererFailAPI()
    run_id = f"test_render_fail_{uuid.uuid4().hex}"
    root = launcher.RUNS_ROOT / run_id

    def trusted_reload(**kwargs):
        return {
            "status": api.PASS_STATUS,
            "saved_archive_sha256": kwargs["expected_archive_sha256"],
            "trusted_source_package_manifest_sha256": "a" * 64,
            "trusted_source_package_preflight_sha256": "b" * 64,
        }

    def failed_renderer(**_kwargs):
        raise RuntimeError("SYNTHETIC_RENDER_FAILURE")

    with pytest.raises(RuntimeError, match="SYNTHETIC_RENDER_FAILURE"):
        launcher.launch_one_bounded_search(
            run_id,
            api=api,
            source_verifier=trusted_reload,
            renderer=failed_renderer,
        )
    try:
        abort = json.loads((root / "launcher_abort.json").read_text())
        assert abort["status"] == "ABORTED_POST_PASS_DELIVERY_INCOMPLETE"
        assert abort["deliverable_status"] == "INCOMPLETE_NO_SEARCH_RESULT_ACCEPTANCE"
        assert not (root / "search_result.json").exists()
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_verified_archive_renders_cumulative_scene_and_binds_every_output(tmp_path):
    source_id = "source:trace"
    land_id = "T02v69:land"
    source = {source_id: box(0, 0, 2, 1)}
    lands = {land_id: box(2.02, 0, 3, 1)}
    archive = tmp_path / "candidate.zip"
    archive_sha = write_candidate_geometry_archive(
        archive,
        candidate_line_wkb=wkb.dumps(LineString([(0, 0.5), (2, 0.5)])),
        candidate_copper_wkb=wkb.dumps(box(0, 0.45, 2, 0.55)),
        candidate_cut_port={"source_id": "source:trace", "coordinate_xy": [2, 0.5], "tangent_xy": [1, 0]},
        candidate_offsets_mm=(0.0, 0.0, 0.0),
        source_preflight_report={},
        result_source_geometries=source,
        result_lands=lands,
        attachment_exception_regions={},
    )
    receipt = render_verified_cumulative_scene(
        archive_path=archive,
        expected_archive_sha256=archive_sha,
        expected_source_ids=set(source),
        expected_land_ids=set(lands),
        output_directory=tmp_path / "review",
        receipt_bindings={"candidate_id": "synthetic-only"},
    )
    assert receipt["status"] == "PASS_RENDERED_CUMULATIVE_REVIEW_ARTIFACT"
    assert receipt["source_object_count"] == 1 and receipt["accepted_v69_land_count"] == 1
    assert (tmp_path / "review/index.html").is_file()
    assert "source:trace" in (tmp_path / "review/cumulative.svg").read_text()
    assert "T02v69:land" in (tmp_path / "review/cumulative.svg").read_text()
    assert json.loads((tmp_path / "review/render_receipt.json").read_text())["outputs_sha256"]["cumulative.svg"]


def test_renderer_rejects_archive_partition_mismatch(tmp_path):
    archive = tmp_path / "candidate.zip"
    archive_sha = write_candidate_geometry_archive(
        archive,
        candidate_line_wkb=wkb.dumps(LineString([(0, 0), (1, 0)])),
        candidate_copper_wkb=wkb.dumps(box(0, 0, 1, 0.1)),
        candidate_cut_port={}, candidate_offsets_mm=(0.0, 0.0, 0.0),
        source_preflight_report={}, result_source_geometries={"source": box(0, 0, 1, 1)},
        result_lands={"land": box(2, 0, 3, 1)}, attachment_exception_regions={},
    )
    with pytest.raises(ValueError, match="C2_RENDER_RESULT_PARTITION_MISMATCH"):
        render_verified_cumulative_scene(
            archive_path=archive, expected_archive_sha256=archive_sha,
            expected_source_ids={"source", "omitted"}, expected_land_ids={"land"},
            output_directory=tmp_path / "bad", receipt_bindings={},
        )
