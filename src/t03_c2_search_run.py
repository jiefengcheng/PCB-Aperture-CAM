"""Pinned one-shot launcher for the single frozen C2 candidate-search run.

Importing this module performs no search. The CLI has no arbitrary input or
output paths: it verifies fixed checkpoint snapshots and one exact domain,
then atomically creates one new run directory below the approved out path.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import sys
from typing import Any
from zipfile import ZipFile

import shapely

from src import t03_c2_search_executor as executor
from src.t03_c2_cumulative_result import render_verified_cumulative_scene
from src.t03_c2_source_verifier import canonical_source_preflight_report_bytes, verify_saved_candidate_archive_from_c2_package


REPO_ROOT = Path(__file__).resolve().parents[1]
if (REPO_ROOT / "tests/fixtures/t03_c2_packet12").is_dir():
    # The reviewed source snapshot is self-contained and keeps the same
    # production preflight executable for portable no-search qualification.
    PACKET_ROOT = REPO_ROOT
else:
    PACKET_ROOT = REPO_ROOT / "out/crop_dynamic_tasks/t03_t04_c2_search_rebinding_20261026_07/source_snapshot"
FIXTURE_ROOT = PACKET_ROOT / "tests/fixtures/t03_c2_packet12"
PACKET12_ZIP = REPO_ROOT / "out/crop_dynamic_tasks/t03_t04_s2b_c2_verifier_20261026_v12/T03T04-S2B-C2-VERIFIER-20261026-12.zip"
MATERIALIZER02_ZIP = REPO_ROOT / "out/crop_dynamic_tasks/t03_t04_s2b_c2_archive_materializer_20261026_v02/T03T04-S2B-C2-ARCHIVE-MATERIALIZER-20261026-02.zip"
RUNS_ROOT = REPO_ROOT / "out/crop_dynamic_tasks/t03_t04_c2_search_runs"

LOCKED = {
    "packet12_zip_sha256": "b7e5843f060ea1d1f4fe0da782ca0da326f1312cf2df155d06b20c1c5e8ff632",
    "materializer02_zip_sha256": "ffaf5b08d8c22430995952f8a7fd98fd60beaefc781173a239ace46cb06c51fd",
    "source_report_file_sha256": "c32134dc0e700b5edc6d8521ecd58d762a55e5b3bbb1391befbc08ff9793d375",
    "source_report_canonical_sha256": "0d5b401ff4e86b5d7dd79c9b2dd510b842c19a8493585cce1bac07e4005da737",
    "domain_sha256": "6eaa0aac33b831f336c101de88bc443964139bf638561ff320d2f7cbb059ae83",
    "executor_sha256": "1a903bb8fc42c8bc4ea7cc1db52c69f09b6147563492746c250edba3cb5d443b",
    "source_verifier_sha256": "d6bb4ce3833f10b59eaec179a07dc7afe86c86ddda2118dea417926972a3af72",
    "route_preflight_sha256": "b9609baf6d49b5688d001a7863ef03c41469e53762a5fec45be2036af282b262",
    "renderer_sha256": "d0d61ff3668fd6b174cfcbf185b9668eec837c484b9a6bbc44ccd3e2646d9673",
    "python": "3.14.5",
    "shapely": "2.1.2",
    "geos": "3.13.1",
}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _file_sha(path: Path) -> str:
    return _sha(Path(path).read_bytes())


def _write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    path = Path(path)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    payload = json.dumps(value, sort_keys=True, indent=2) + "\n"
    with temporary.open("x", encoding="utf-8") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    try:
        directory_fd = os.open(path.parent, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def _verify_zip(path: Path, expected: str, code: str) -> None:
    if _file_sha(path) != expected:
        raise RuntimeError(f"{code}_SHA256_MISMATCH")
    with ZipFile(path) as archive:
        if archive.testzip() is not None:
            raise RuntimeError(f"{code}_ZIP_CRC_FAILURE")


def _verify_manifest(root: Path, manifest_path: Path) -> dict[str, str]:
    entries: dict[str, str] = {}
    for line in manifest_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        digest, rel = line.split(None, 1)
        rel = rel.strip().lstrip("*")
        path = (root / rel).resolve()
        if not path.is_relative_to(root.resolve()) or not path.is_file():
            raise RuntimeError(f"PACKET_MANIFEST_PATH_INVALID:{rel}")
        if _file_sha(path) != digest:
            raise RuntimeError(f"PACKET_MANIFEST_HASH_MISMATCH:{rel}")
        entries[rel] = digest
    if not entries:
        raise RuntimeError("PACKET_MANIFEST_EMPTY")
    return entries


def _package_paths(fixture_root: Path) -> dict[str, Path]:
    return {
        "package_manifest_path": fixture_root / "complete_scene/package_scene_manifest.json",
        "witness_path": fixture_root / "s2a/adaptive_patch_witness.json",
        "future_work_items_path": fixture_root / "t02_inherited/future_trace_work_items.json",
        "t02_review_issue_ids_path": fixture_root / "t02_inherited/review_issue_ids.json",
        "t02_checksum_manifest_path": fixture_root / "t02_inherited/SHA256SUMS.txt",
    }


def _verify_source_report_in_packet12(packet12_zip: Path, expected_sha256: str, expected_report: dict[str, Any]) -> str:
    member = "evidence/c2_source_verification.json"
    with ZipFile(packet12_zip) as archive:
        try:
            payload = archive.read(member)
        except KeyError as exc:
            raise RuntimeError("PACKET12_SOURCE_REPORT_MISSING") from exc
    if _sha(payload) != expected_sha256:
        raise RuntimeError("PACKET12_SOURCE_REPORT_HASH_MISMATCH")
    if json.loads(payload) != expected_report:
        raise RuntimeError("PACKET12_SOURCE_REPORT_CONTENT_MISMATCH")
    return _sha(canonical_source_preflight_report_bytes(expected_report))


def verify_preflight_bindings(
    *,
    repo_root: Path = REPO_ROOT,
    packet_root: Path = PACKET_ROOT,
    fixture_root: Path = FIXTURE_ROOT,
    packet12_zip: Path = PACKET12_ZIP,
    materializer02_zip: Path = MATERIALIZER02_ZIP,
    pins: dict[str, str] = LOCKED,
    domain_loader=executor.load_c2_search_domain,
) -> tuple[Any, dict[str, Any]]:
    """Verify all source/checkpoint/code/runtime pins and the ordered domain."""
    if platform.python_version() != pins["python"] or shapely.__version__ != pins["shapely"] or shapely.geos_version_string != pins["geos"]:
        raise RuntimeError("SEARCH_RUNTIME_VERSION_MISMATCH")
    _verify_zip(packet12_zip, pins["packet12_zip_sha256"], "PACKET12")
    _verify_zip(materializer02_zip, pins["materializer02_zip_sha256"], "MATERIALIZER02")
    _verify_manifest(packet_root, packet_root / "SHA256SUMS.txt")
    current_sources = {
        "executor_sha256": repo_root / "src/t03_c2_search_executor.py",
        "source_verifier_sha256": repo_root / "src/t03_c2_source_verifier.py",
        "route_preflight_sha256": repo_root / "src/t03_route_preflight.py",
    }
    for name, path in current_sources.items():
        if _file_sha(path) != pins[name]:
            raise RuntimeError(f"{name.upper()}_MISMATCH")
        packet_copy = packet_root / "src" / path.name
        if _file_sha(packet_copy) != pins[name]:
            raise RuntimeError(f"PACKET_{name.upper()}_MISMATCH")
    if _file_sha(repo_root / "src/t03_c2_cumulative_result.py") != pins["renderer_sha256"]:
        raise RuntimeError("RENDERER_SHA256_MISMATCH")
    paths = _package_paths(fixture_root)
    for name, path in paths.items():
        if not path.is_file():
            raise RuntimeError(f"SOURCE_PACKAGE_INPUT_MISSING:{name}")
    domain = domain_loader(**paths)
    if len(domain.candidates) != 1_372 or domain.domain_sha256 != pins["domain_sha256"]:
        raise RuntimeError("SEARCH_DOMAIN_BINDING_MISMATCH")
    report_sha = _verify_source_report_in_packet12(packet12_zip, pins["source_report_file_sha256"], domain.report)
    if report_sha != pins["source_report_canonical_sha256"] or domain.source_report_sha256 != report_sha:
        raise RuntimeError("SEARCH_SOURCE_REPORT_BINDING_MISMATCH")
    binding = {
        "packet12_zip_sha256": pins["packet12_zip_sha256"],
        "materializer02_zip_sha256": pins["materializer02_zip_sha256"],
        "source_report_file_sha256": pins["source_report_file_sha256"],
        "source_report_canonical_sha256": report_sha,
        "candidate_domain_sha256": domain.domain_sha256,
        "candidate_count": len(domain.candidates),
        "source_sha256": domain.report["source_sha256"],
        "inventory_sha256": domain.report["inventory_sha256"],
        "policy_sha256": domain.report["clearance_policy"]["sha256"],
        "executor_sha256": pins["executor_sha256"],
        "source_verifier_sha256": pins["source_verifier_sha256"],
        "route_preflight_sha256": pins["route_preflight_sha256"],
        "packet_manifest_entry_count": len(_verify_manifest(packet_root, packet_root / "SHA256SUMS.txt")),
        "python": platform.python_version(),
        "shapely": shapely.__version__,
        "geos": shapely.geos_version_string,
    }
    return domain, binding


def launch_one_bounded_search(
    run_id: str,
    *,
    repo_root: Path = REPO_ROOT,
    packet_root: Path = PACKET_ROOT,
    fixture_root: Path = FIXTURE_ROOT,
    packet12_zip: Path = PACKET12_ZIP,
    materializer02_zip: Path = MATERIALIZER02_ZIP,
    pins: dict[str, str] = LOCKED,
    api=executor,
    source_verifier=verify_saved_candidate_archive_from_c2_package,
    renderer=render_verified_cumulative_scene,
    domain_loader=executor.load_c2_search_domain,
) -> dict[str, Any]:
    """Execute exactly one frozen run; all preflight checks precede candidate 1."""
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", run_id):
        raise RuntimeError("RUN_ID_INVALID")
    domain, binding = verify_preflight_bindings(
        repo_root=repo_root, packet_root=packet_root, fixture_root=fixture_root,
        packet12_zip=packet12_zip, materializer02_zip=materializer02_zip,
        pins=pins, domain_loader=domain_loader,
    )
    runs_root = (repo_root / "out/crop_dynamic_tasks/t03_t04_c2_search_runs").resolve()
    if not runs_root.is_relative_to(Path(repo_root).resolve()):
        raise RuntimeError("RUNS_ROOT_ESCAPES_CHECKOUT")
    requested_root = runs_root / run_id
    if requested_root.exists():
        raise RuntimeError("RUN_DIRECTORY_ALREADY_EXISTS")
    runs_root.mkdir(parents=True, exist_ok=True)
    run_root = runs_root / run_id
    run_root.mkdir(exist_ok=False)  # Exclusive mkdir closes the check/create race.
    binding["launcher_sha256"] = _file_sha(repo_root / "src/t03_c2_search_run.py")
    binding["run_id"] = run_id
    binding["run_directory"] = str(run_root)
    binding["candidate_archive_directory"] = str(run_root / "archives")
    binding["attempt_ledger_path"] = str(run_root / "attempts.jsonl")
    binding["state_receipt_path"] = str(run_root / "search.state.json")
    binding["scope"] = "one bounded C2 candidate-search run; not engineering/manufacturing acceptance"
    try:
        _write_json_atomic(run_root / "preflight_binding.json", binding)
    except BaseException as exc:
        _write_json_atomic(run_root / "launcher_abort.json", {
            **binding,
            "status": "ABORTED_PREFLIGHT_RECEIPT_WRITE",
            "exception_type": type(exc).__name__,
            "error": str(exc),
            "deliverable_status": "INCOMPLETE_NO_SEARCH_RESULT_ACCEPTANCE",
        })
        raise

    package_args = _package_paths(fixture_root)
    executor_status = None
    try:
        archive_factory = api.make_source_bound_c2_archive_factory(
            **package_args,
            output_directory=run_root / "archives",
        )
        evaluator = api.make_trusted_candidate_evaluator(archive_factory=archive_factory, **package_args)
        result = api.execute_ordered_search(
            domain,
            evaluate=evaluator,
            attempt_ledger_path=run_root / "attempts.jsonl",
            state_receipt_path=run_root / "search.state.json",
        )
        executor_status = result.get("status")
        if result.get("status") not in {"FIRST_VALID_CANDIDATE", "NO_VALID_CANDIDATE_WITHIN_FROZEN_BOUNDS", "ABORTED_EXECUTION"}:
            raise RuntimeError("UNEXPECTED_EXECUTOR_RESULT")
        result = {**result, "launcher_sha256": binding["launcher_sha256"], "checkpoint_bindings": binding}
        if result.get("status") == "FIRST_VALID_CANDIDATE":
            candidate = next((item for item in domain.candidates if item.candidate_id == result.get("candidate_id")), None)
            archive_path = Path(result.get("saved_archive_path", "")).resolve()
            if candidate is None or not archive_path.is_file():
                raise RuntimeError("PASS_RESULT_CANDIDATE_OR_ARCHIVE_MISSING")
            if not archive_path.is_relative_to(run_root.resolve()):
                raise RuntimeError("PASS_RESULT_ARCHIVE_OUTSIDE_RUN_DIRECTORY")
            verify_kwargs = {
                "archive_path": archive_path,
                "expected_archive_sha256": result["saved_archive_sha256"],
                **package_args,
                "candidate_cut_port": candidate.cut_port,
                "candidate_offsets_mm": tuple(float(v) for v in candidate.offsets_mm),
            }
            trusted = source_verifier(**verify_kwargs)
            if trusted.get("status") != api.PASS_STATUS or trusted.get("saved_archive_sha256") != result["saved_archive_sha256"]:
                raise RuntimeError("POST_PASS_TRUSTED_RELOAD_FAILED")
            _, scene_receipt, spec, _, fcu_rows, source_geometries, accepted_lands = api._load_scene(package_args["package_manifest_path"])
            if len(fcu_rows) != 17_849 or len(accepted_lands) != 80:
                raise RuntimeError("POST_PASS_FULL_SCENE_INCOMPLETE")
            render_receipt = renderer(
                archive_path=archive_path,
                expected_archive_sha256=result["saved_archive_sha256"],
                expected_source_ids=set(source_geometries),
                expected_land_ids=set(accepted_lands),
                output_directory=run_root / "cumulative_review",
                receipt_bindings={
                    "candidate_id": candidate.candidate_id,
                    "candidate_domain_sha256": domain.domain_sha256,
                    "source_package_manifest_sha256": trusted["trusted_source_package_manifest_sha256"],
                    "source_preflight_sha256": trusted["trusted_source_package_preflight_sha256"],
                    "packet12_zip_sha256": pins["packet12_zip_sha256"],
                    "materializer02_zip_sha256": pins["materializer02_zip_sha256"],
                    "accepted_scene_receipt_commit": spec["accepted_scene"]["receipt_commit"],
                    "accepted_scene_t02_result": spec["accepted_scene"]["t02_result"],
                    "accepted_scene_t02_policy": spec["accepted_scene"]["t02_policy"],
                },
            )
            if render_receipt.get("status") != "PASS_RENDERED_CUMULATIVE_REVIEW_ARTIFACT":
                raise RuntimeError("POST_PASS_CUMULATIVE_RENDER_NOT_PASS")
            result["cumulative_render"] = render_receipt
            result["deliverable_status"] = "COMPLETE_WITH_CUMULATIVE_REVIEW_ARTIFACT"
        else:
            result["deliverable_status"] = (
                "COMPLETE_NO_PASS_WITHIN_FROZEN_BOUNDS"
                if result.get("status") == "NO_VALID_CANDIDATE_WITHIN_FROZEN_BOUNDS"
                else "INCOMPLETE_ABORTED_EXECUTION"
            )
        result_path = run_root / "search_result.json"
        _write_json_atomic(result_path, result)
        return result
    except BaseException as exc:
        existing_abort = run_root / "launcher_abort.json"
        if not existing_abort.exists():
            abort_status = (
                "ABORTED_UNEXPECTED_EXECUTOR_RESULT" if str(exc) == "UNEXPECTED_EXECUTOR_RESULT"
                else "ABORTED_INTERRUPTED" if isinstance(exc, (KeyboardInterrupt, InterruptedError))
                else "ABORTED_POST_PASS_DELIVERY_INCOMPLETE" if executor_status == "FIRST_VALID_CANDIDATE"
                else "ABORTED_LAUNCHER_EXCEPTION"
            )
            abort = {
                **binding,
                "status": abort_status,
                "exception_type": type(exc).__name__,
                "error": str(exc),
                "deliverable_status": "INCOMPLETE_NO_SEARCH_RESULT_ACCEPTANCE",
            }
            _write_json_atomic(run_root / "launcher_abort.json", abort)
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True, help="Unique run directory name; an existing name is rejected")
    args = parser.parse_args(argv)
    if os.environ.get("T03_C2_EXECUTION_GUARD") != "T03_C2_SEARCH_GUARD_V1":
        print(json.dumps({"status": "ABORTED_UNGUARDED_LAUNCH", "error": "EXECUTION_GUARD_REQUIRED"}, sort_keys=True), file=sys.stderr)
        return 2
    try:
        result = launch_one_bounded_search(args.run_id)
    except Exception as exc:
        print(json.dumps({"status": "ABORTED_SETUP_OR_EXECUTION", "error_type": type(exc).__name__, "error": str(exc)}, sort_keys=True), file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0 if result.get("status") in {"FIRST_VALID_CANDIDATE", "NO_VALID_CANDIDATE_WITHIN_FROZEN_BOUNDS"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
