"""Deterministic, bounded orchestration for the C2 T03 candidate search.

This module defines the search domain, no-search qualification receipt, and
fail-closed attempt loop. It does not run at import time. The production loop
requires an explicit candidate evaluator, which must materialize a saved
candidate archive and invoke the trusted C2-package verifier.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from hashlib import sha256
import json
import os
from pathlib import Path
import platform
import uuid
from typing import Any, Callable
from zipfile import ZipFile

from shapely import geos_version_string, to_wkb
from shapely.geometry import Point
from shapely.ops import unary_union

from src.t03_c2_source_verifier import (
    PreflightError,
    canonical_source_preflight_report_bytes,
    _downstream_source_suffix,
    _load_scene,
    verify_c2_source_obligations,
    verify_saved_candidate_archive_from_c2_package,
    write_candidate_geometry_archive,
)
from src.t03_route_preflight import (
    MAX_CANDIDATES,
    OFFSETS_MM,
    PORT_TRANSITION_BUFFER_MM,
    REGULAR_PORT_STEP_MM,
    MAX_ADDED_SPANS,
    MAX_EXTENSION_MM,
    Primitive,
    SourcePath,
    WIDTH_MM,
    buffer_centerline,
    candidate_source_copper_by_id,
    candidate_order_key,
    construct_candidate_centerline_source_spans,
    enumerate_candidate_specs,
    enumerate_cut_ports,
)


LOCKED_SOURCE_SHA256 = "850c4c74d55717a721d4bbed7ec876ee086f475efd97f69bb5b5164ef77533a0"
LOCKED_INVENTORY_SHA256 = "e8f85e9f3ddf98dd13bd79606a77ba2934e801c404a4c4d396edac03ae774355"
LOCKED_POLICY_SHA256 = "54c9542dd7c31fb8fb24698d97741dcc72a049b050bae6408c421f1b25174df8"
LOCKED_PORT_EXTENSIONS_MM = tuple(Decimal(v) for v in ("0.225", "0.250", "0.275", "0.300"))
PASS_STATUS = "PASS_SAVED_C2_CANDIDATE_GEOMETRY"
REJECT_STATUS = "REJECTED_CANDIDATE"


class SearchExecutorError(PreflightError):
    """A search setup or execution contract failed closed."""


@dataclass(frozen=True)
class CandidateSpec:
    ordinal: int
    candidate_id: str
    cut_port: dict[str, Any]
    offsets_mm: tuple[Decimal, Decimal, Decimal]

    def canonical_record(self) -> dict[str, Any]:
        return {
            "ordinal": self.ordinal,
            "candidate_id": self.candidate_id,
            "cut_port": self.cut_port,
            "offsets_mm": [str(value) for value in self.offsets_mm],
        }


@dataclass(frozen=True)
class SearchDomain:
    report: dict[str, Any]
    source_path: SourcePath
    candidates: tuple[CandidateSpec, ...]
    domain_sha256: str
    source_report_sha256: str


_TRUSTED_EVALUATOR_TOKEN = object()


@dataclass(frozen=True, init=False)
class TrustedCandidateEvaluator:
    """Callable capability created only by the trusted source-package factory."""

    callback: Callable[[CandidateSpec], dict[str, Any]]
    package_manifest_path: Path

    def __init__(self, callback, package_manifest_path, *, _token=None):
        if _token is not _TRUSTED_EVALUATOR_TOKEN:
            raise SearchExecutorError("TRUSTED_EVALUATOR_CONSTRUCTOR_FORBIDDEN")
        object.__setattr__(self, "callback", callback)
        object.__setattr__(self, "package_manifest_path", Path(package_manifest_path).resolve())

    def __call__(self, candidate: CandidateSpec) -> dict[str, Any]:
        return self.callback(candidate)


def _canonical_json(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode("utf-8")


def _sha(data: bytes) -> str:
    return sha256(data).hexdigest()


def _source_path_from_report(report: dict[str, Any]) -> SourcePath:
    info = report.get("source_path_centerline")
    if not isinstance(info, dict):
        raise SearchExecutorError("SEARCH_SOURCE_PATH_MISSING")
    primitives_raw = info.get("native_primitives")
    if not isinstance(primitives_raw, list) or not primitives_raw:
        raise SearchExecutorError("SEARCH_NATIVE_PRIMITIVES_MISSING")
    primitives = tuple(
        Primitive(
            source_id=row["source_id"],
            kind=row["kind"],
            start=tuple(map(float, row["start_xy"])),
            end=tuple(map(float, row["end_xy"])),
            width_mm=float(row["width_mm"]),
            mid=tuple(map(float, row["mid_xy"])) if row.get("mid_xy") is not None else None,
        )
        for row in primitives_raw
    )
    return SourcePath(primitives, float(info["initial_patch_end_mm"]))


def build_locked_search_domain(report: dict[str, Any]) -> SearchDomain:
    """Recompute and lock the source-bound C2 domain; never trust a grid count."""
    if report.get("status") != "PASS_C2_SOURCE_BOUND_PREFLIGHT_OBLIGATIONS":
        raise SearchExecutorError("SEARCH_SOURCE_PREFLIGHT_NOT_PASS")
    if report.get("source_sha256") != LOCKED_SOURCE_SHA256:
        raise SearchExecutorError("SEARCH_SOURCE_HASH_CHANGED")
    if report.get("inventory_sha256") != LOCKED_INVENTORY_SHA256:
        raise SearchExecutorError("SEARCH_INVENTORY_HASH_CHANGED")
    policy = report.get("clearance_policy", {})
    if policy.get("sha256") != LOCKED_POLICY_SHA256:
        raise SearchExecutorError("SEARCH_POLICY_HASH_CHANGED")
    if report.get("org_fcu_object_count") != 17_849 or report.get("accepted_v69_land_count") != 80:
        raise SearchExecutorError("SEARCH_COMPLETE_SCENE_COUNTS_CHANGED")
    if report.get("source_width_preserved") is not True or set(report.get("source_widths_mm", {}).values()) != {0.10008}:
        raise SearchExecutorError("SEARCH_SOURCE_WIDTH_CONTRACT_CHANGED")

    path = _source_path_from_report(report)
    all_ports = enumerate_cut_ports(
        path,
        step_mm=REGULAR_PORT_STEP_MM,
        max_extension_mm=MAX_EXTENSION_MM,
        transition_buffer_mm=PORT_TRANSITION_BUFFER_MM,
        max_added_spans=MAX_ADDED_SPANS,
    )
    eligible = tuple(port for port in all_ports if port.eligible)
    port_records = report["source_path_centerline"].get("eligible_cut_ports", [])
    if len(port_records) != 4 or len(eligible) != 4:
        raise SearchExecutorError("SEARCH_ELIGIBLE_PORT_COUNT_CHANGED")
    if tuple(port.extension_mm for port in eligible) != LOCKED_PORT_EXTENSIONS_MM:
        raise SearchExecutorError("SEARCH_ELIGIBLE_PORT_EXTENSIONS_CHANGED")

    # Bind the independently recomputed port identities/geometry to the report.
    for computed, recorded in zip(eligible, port_records, strict=True):
        xy = path.point_at(float(computed.distance_mm))
        tangent = path.tangent_at(float(computed.distance_mm))
        if (
            recorded.get("status") != "ELIGIBLE_BOUNDED_CUT_PORT"
            or recorded.get("source_id") != computed.source_id
            or Decimal(str(recorded.get("extension_mm"))) != computed.extension_mm
            or abs(float(recorded.get("distance_mm")) - float(computed.distance_mm)) > 1e-12
            or any(abs(float(recorded["coordinate_xy"][i]) - xy[i]) > 1e-9 for i in (0, 1))
            or any(abs(float(recorded["tangent_xy"][i]) - tangent[i]) > 1e-9 for i in (0, 1))
        ):
            raise SearchExecutorError("SEARCH_PORT_REPORT_BINDING_MISMATCH")

    raw_specs = enumerate_candidate_specs(path)
    if len(raw_specs) != 4 * len(OFFSETS_MM) ** 3 or len(raw_specs) != 1_372 or len(raw_specs) > MAX_CANDIDATES:
        raise SearchExecutorError("SEARCH_DOMAIN_CARDINALITY_MISMATCH")
    candidates: list[CandidateSpec] = []
    prior_key = None
    seen: set[str] = set()
    for ordinal, (port, offsets) in enumerate(raw_specs, start=1):
        key = candidate_order_key(port, offsets)
        if prior_key is not None and key < prior_key:
            raise SearchExecutorError("SEARCH_DOMAIN_ORDER_INVALID")
        prior_key = key
        port_record = next(
            row for row in port_records
            if row["source_id"] == port.source_id
            and abs(float(row["distance_mm"]) - float(port.distance_mm)) <= 1e-12
        )
        identity = {
            "cut_port": port_record,
            "offsets_mm": [str(v) for v in offsets],
            "source_sha256": report["source_sha256"],
            "inventory_sha256": report["inventory_sha256"],
            "policy_sha256": policy["sha256"],
        }
        candidate_id = _sha(_canonical_json(identity))
        if candidate_id in seen:
            raise SearchExecutorError("SEARCH_CANDIDATE_ID_DUPLICATE")
        seen.add(candidate_id)
        candidates.append(CandidateSpec(ordinal, candidate_id, port_record, offsets))
    domain_body = {
        "schema": "T03_C2_SEARCH_DOMAIN_V1",
        "source_sha256": report["source_sha256"],
        "inventory_sha256": report["inventory_sha256"],
        "policy_sha256": policy["sha256"],
        "candidates": [candidate.canonical_record() for candidate in candidates],
    }
    report_bytes = canonical_source_preflight_report_bytes(report)
    return SearchDomain(report, path, tuple(candidates), _sha(_canonical_json(domain_body)), _sha(report_bytes))


def load_c2_search_domain(
    *,
    package_manifest_path: Path,
    witness_path: Path,
    future_work_items_path: Path,
    t02_review_issue_ids_path: Path,
    t02_checksum_manifest_path: Path,
) -> SearchDomain:
    """Load search authority only after rechecking the complete C2 package."""
    report = verify_c2_source_obligations(
        Path(package_manifest_path),
        Path(witness_path),
        Path(future_work_items_path),
        Path(t02_review_issue_ids_path),
        Path(t02_checksum_manifest_path),
    )
    return build_locked_search_domain(report)


def make_source_bound_c2_archive_factory(
    *,
    package_manifest_path: Path,
    witness_path: Path,
    future_work_items_path: Path,
    t02_review_issue_ids_path: Path,
    t02_checksum_manifest_path: Path,
    output_directory: Path,
) -> Callable[[CandidateSpec], tuple[Path, str]]:
    """Build saved candidate archives from one verified C2 package snapshot.

    Package and T02 evidence are verified before the returned factory is used;
    the trusted evaluator independently reloads and verifies them for every
    candidate. No candidate geometry is generated while constructing the
    factory. The selected cut port is always re-bound to the frozen domain.
    """
    package_manifest_path = Path(package_manifest_path).resolve()
    witness_path = Path(witness_path).resolve()
    future_work_items_path = Path(future_work_items_path).resolve()
    t02_review_issue_ids_path = Path(t02_review_issue_ids_path).resolve()
    t02_checksum_manifest_path = Path(t02_checksum_manifest_path).resolve()
    output_directory = Path(output_directory).resolve()
    domain = load_c2_search_domain(
        package_manifest_path=package_manifest_path,
        witness_path=witness_path,
        future_work_items_path=future_work_items_path,
        t02_review_issue_ids_path=t02_review_issue_ids_path,
        t02_checksum_manifest_path=t02_checksum_manifest_path,
    )
    root, _, spec, _, fcu_rows, source_geometries, accepted_lands = _load_scene(package_manifest_path)
    source_hashes = {row["source_id"]: row["geometry_sha256"] for row in domain.report["source_obstacle_partition"]}
    if set(source_geometries) != set(source_hashes):
        raise SearchExecutorError("ARCHIVE_FACTORY_SOURCE_PARTITION_MISMATCH")
    source_archive_path = root / spec["org_archive"]["path"]
    source_wkb_by_id: dict[str, bytes] = {}
    with ZipFile(source_archive_path) as archive:
        member_by_hash = {name[:-4]: name for name in archive.namelist() if name.endswith(".wkb")}
        for row in fcu_rows:
            source_id = row["id"]
            expected_hash = source_hashes[source_id]
            member = member_by_hash.get(expected_hash)
            if member is None:
                raise SearchExecutorError(f"ARCHIVE_FACTORY_SOURCE_WKB_MISSING:{source_id}")
            payload = archive.read(member)
            if _sha(payload) != expected_hash:
                raise SearchExecutorError(f"ARCHIVE_FACTORY_SOURCE_WKB_HASH:{source_id}")
            source_wkb_by_id[source_id] = payload
    if set(source_wkb_by_id) != set(source_geometries):
        raise SearchExecutorError("ARCHIVE_FACTORY_SOURCE_WKB_PARTITION_MISMATCH")

    land_manifest_path = root / spec["land_manifest"]["path"]
    land_manifest = json.loads(land_manifest_path.read_text(encoding="utf-8"))
    land_root = root / spec["land_manifest"]["target_root"]
    land_wkb_by_id: dict[str, bytes] = {}
    for target in land_manifest["targets"]:
        land_id = target["source_id"]
        payload = (land_root / Path(target["candidate_wkb_path"]).name).read_bytes()
        if _sha(payload) != target["candidate_wkb_sha256"]:
            raise SearchExecutorError(f"ARCHIVE_FACTORY_LAND_WKB_HASH:{land_id}")
        land_wkb_by_id[land_id] = payload
    if set(land_wkb_by_id) != set(accepted_lands):
        raise SearchExecutorError("ARCHIVE_FACTORY_LAND_PARTITION_MISMATCH")

    policy = domain.report["clearance_policy"]
    exception_regions: dict[str, Any] = {}
    for item in domain.report.get("attachment_exceptions", []):
        trace_id = item["trace_source_id"]
        obstacle_id = item["obstacle_source_id"]
        if item["kind"] == "ACCEPTED_T02_LAND":
            key = f"T02v69:{obstacle_id}"
            obstacle = accepted_lands.get(obstacle_id)
        else:
            key = obstacle_id
            obstacle = source_geometries.get(obstacle_id)
        if trace_id not in source_geometries or obstacle is None:
            raise SearchExecutorError("ARCHIVE_FACTORY_ATTACHMENT_SOURCE_MISSING")
        region = source_geometries[trace_id].intersection(obstacle).buffer(
            float(item["v15_port_buffer_radius_mm"]), quad_segs=policy["quad_segs"]
        )
        digest = _sha(to_wkb(region, byte_order=0, output_dimension=2, include_srid=False))
        if digest != item["allowed_contact_region_wkb_sha256"]:
            raise SearchExecutorError(f"ARCHIVE_FACTORY_ATTACHMENT_HASH:{key}")
        exception_regions[key] = region

    report_source_id_set = set(domain.report["patch_source_ids"])
    if report_source_id_set != {primitive.source_id for primitive in domain.source_path.primitives}:
        raise SearchExecutorError("ARCHIVE_FACTORY_WRITABLE_PATH_PARTITION_MISMATCH")
    output_directory.mkdir(parents=True, exist_ok=True)

    def factory(candidate: CandidateSpec) -> tuple[Path, str]:
        if candidate.ordinal < 1 or candidate.ordinal > len(domain.candidates):
            raise SearchExecutorError("ARCHIVE_FACTORY_CANDIDATE_ORDINAL_INVALID")
        if domain.candidates[candidate.ordinal - 1] != candidate:
            raise SearchExecutorError("ARCHIVE_FACTORY_CANDIDATE_NOT_SOURCE_BOUND")
        port = candidate.cut_port
        cut_distance = float(port["distance_mm"])
        line, source_spans = construct_candidate_centerline_source_spans(
            domain.source_path, cut_distance,
            tuple(float(value) for value in candidate.offsets_mm),
        )
        copper, _ = buffer_centerline(line)
        cut_source_id = str(port["source_id"])
        replacement_geometries = candidate_source_copper_by_id(
            source_spans,
            [primitive.source_id for primitive in domain.source_path.primitives],
            cut_source_id,
            copper,
        )
        result_source_geometries = dict(source_geometries)
        result_source_geometries.update(replacement_geometries)
        cut_xy = tuple(map(float, port["coordinate_xy"]))
        suffix = _downstream_source_suffix(
            source_geometries[cut_source_id], cut_xy, tuple(map(float, port["tangent_xy"]))
        )
        # The cut source retains both its generated prefix and its exact
        # immutable downstream suffix under the same original source ID.
        result_source_geometries[cut_source_id] = unary_union([
            result_source_geometries[cut_source_id], suffix,
        ])
        candidate_exceptions = dict(exception_regions)
        suffix_key = f"CUT_SUFFIX:{cut_source_id}"
        endpoint_region = suffix.intersection(Point(cut_xy).buffer(
            WIDTH_MM / 2.0 + float(policy["construction_target_mm"]) + float(policy["numeric_tolerance_mm"]),
            quad_segs=256,
        ))
        if endpoint_region.is_empty or endpoint_region.area <= 0:
            raise SearchExecutorError("ARCHIVE_FACTORY_FIXED_SUFFIX_EXCEPTION_EMPTY")
        candidate_exceptions[suffix_key] = endpoint_region
        archive_path = output_directory / f"{candidate.ordinal:04d}-{candidate.candidate_id}.zip"
        if archive_path.exists():
            raise SearchExecutorError("ARCHIVE_FACTORY_OUTPUT_ALREADY_EXISTS")
        archive_sha256 = write_candidate_geometry_archive(
            archive_path,
            candidate_line_wkb=to_wkb(line, byte_order=0, output_dimension=2, include_srid=False),
            candidate_copper_wkb=to_wkb(copper, byte_order=0, output_dimension=2, include_srid=False),
            candidate_cut_port=port,
            candidate_offsets_mm=tuple(float(value) for value in candidate.offsets_mm),
            source_preflight_report=domain.report,
            result_source_geometries=result_source_geometries,
            result_lands=accepted_lands,
            attachment_exception_regions=candidate_exceptions,
        )
        return archive_path, archive_sha256

    return factory


def create_no_search_qualification_receipt(
    report: dict[str, Any],
    *,
    executor_source_path: Path,
) -> dict[str, Any]:
    """Qualify the locked domain without constructing or evaluating any route."""
    domain = build_locked_search_domain(report)
    return {
        "schema": "T03_C2_SEARCH_EXECUTOR_QUALIFICATION_V1",
        "status": "PASS_SEARCH_EXECUTOR_PREFLIGHT_NO_CANDIDATES_GENERATED",
        "route_search_executed": False,
        "route_geometry_created": False,
        "attempted_candidate_count": 0,
        "candidate_count": len(domain.candidates),
        "eligible_port_count": 4,
        "candidate_domain_sha256": domain.domain_sha256,
        "source_preflight_report_sha256": domain.source_report_sha256,
        "executor_source_sha256": _sha(Path(executor_source_path).read_bytes()),
        "source_sha256": report["source_sha256"],
        "inventory_sha256": report["inventory_sha256"],
        "policy_sha256": report["clearance_policy"]["sha256"],
        "eligible_ports": [candidate.cut_port for candidate in domain.candidates if candidate.ordinal in {1, 344, 687, 1030}],
        "runtime": {"python": platform.python_version(), "shapely_geos": geos_version_string},
        "native_export_executed": False,
        "electrical_intent": "NOT_ESTABLISHED",
    }


def _append_record(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = _canonical_json(record)
    with path.open("ab") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    _fsync_directory(path.parent)


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temporary.open("wb") as stream:
        stream.write(_canonical_json(value))
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    _fsync_directory(path.parent)


def make_trusted_candidate_evaluator(
    *,
    archive_factory: Callable[[CandidateSpec], tuple[Path, str]],
    package_manifest_path: Path,
    witness_path: Path,
    future_work_items_path: Path,
    t02_review_issue_ids_path: Path,
    t02_checksum_manifest_path: Path,
) -> TrustedCandidateEvaluator:
    """Bind archive materialization to the trusted source-package verifier.

    Only the two expected geometric search failures are treated as candidate
    rejections. Any setup, integrity, topology, or unclassified exception
    bubbles to the executor and becomes an aborted run.
    """
    package_manifest_path = Path(package_manifest_path).resolve()
    expected_package_manifest_sha256 = _sha(package_manifest_path.read_bytes())
    def evaluate(candidate: CandidateSpec) -> dict[str, Any]:
        archive_path, archive_sha256 = archive_factory(candidate)
        archive_path = Path(archive_path).resolve()
        if not archive_path.is_file() or _sha(archive_path.read_bytes()) != archive_sha256:
            raise SearchExecutorError("TRUSTED_EVALUATOR_ARCHIVE_BYTES_NOT_BOUND")
        kwargs = {
            "archive_path": archive_path,
            "expected_archive_sha256": archive_sha256,
            "package_manifest_path": package_manifest_path,
            "witness_path": Path(witness_path),
            "future_work_items_path": Path(future_work_items_path),
            "t02_review_issue_ids_path": Path(t02_review_issue_ids_path),
            "t02_checksum_manifest_path": Path(t02_checksum_manifest_path),
            "candidate_cut_port": candidate.cut_port,
            "candidate_offsets_mm": tuple(float(value) for value in candidate.offsets_mm),
        }
        try:
            result = verify_saved_candidate_archive_from_c2_package(**kwargs)
        except PreflightError as exc:
            error = str(exc)
            if error.startswith("C2_CANDIDATE_CLEARANCE_NOT_PASS:") or error.startswith("C2_INHERITED_FINDING_NEW_OR_WORSENED:"):
                return {
                    "status": REJECT_STATUS,
                    "reason_code": error.split(":", 1)[0],
                    "saved_archive_sha256": archive_sha256,
                    "saved_archive_path": str(archive_path),
                }
            raise
        if (
            result.get("status") != PASS_STATUS
            or result.get("serialized_candidate_reloaded") is not True
            or result.get("saved_archive_sha256") != archive_sha256
            or result.get("trusted_source_package_manifest_sha256") != expected_package_manifest_sha256
            or result.get("trusted_invocation_boundary") != "PASS_REVERIFIED_C2_PACKAGE"
            or not isinstance(result.get("trusted_source_package_preflight_sha256"), str)
            or len(result["trusted_source_package_preflight_sha256"]) != 64
        ):
            raise SearchExecutorError("TRUSTED_VERIFIER_RETURNED_UNQUALIFIED_STATUS")
        return {
            "status": PASS_STATUS,
            "saved_archive_sha256": result["saved_archive_sha256"],
            "saved_archive_path": str(archive_path),
            "trusted_source_package_manifest_sha256": result.get("trusted_source_package_manifest_sha256"),
            "trusted_source_package_preflight_sha256": result.get("trusted_source_package_preflight_sha256"),
        }
    return TrustedCandidateEvaluator(evaluate, package_manifest_path, _token=_TRUSTED_EVALUATOR_TOKEN)


def execute_ordered_search(
    domain: SearchDomain,
    *,
    evaluate: Callable[[CandidateSpec], dict[str, Any]],
    attempt_ledger_path: Path,
    state_receipt_path: Path | None = None,
) -> dict[str, Any]:
    """Run only with the source-package-bound evaluator capability."""
    if not isinstance(evaluate, TrustedCandidateEvaluator):
        raise SearchExecutorError("SEARCH_TRUSTED_EVALUATOR_REQUIRED")
    package_path = evaluate.package_manifest_path
    if not package_path.is_file():
        raise SearchExecutorError("SEARCH_TRUSTED_PACKAGE_MANIFEST_MISSING")
    binding = {
        "source_package_manifest_sha256": _sha(package_path.read_bytes()),
        "source_preflight_report_sha256": domain.source_report_sha256,
        "source_sha256": domain.report["source_sha256"],
        "inventory_sha256": domain.report["inventory_sha256"],
        "policy_sha256": domain.report["clearance_policy"]["sha256"],
        "candidate_domain_sha256": domain.domain_sha256,
        "executor_source_sha256": _sha(Path(__file__).read_bytes()),
    }
    def bound_evaluate(candidate: CandidateSpec) -> dict[str, Any]:
        result = evaluate(candidate)
        if result.get("status") == PASS_STATUS and (
            result.get("trusted_source_package_manifest_sha256") != binding["source_package_manifest_sha256"]
            or result.get("trusted_source_package_preflight_sha256") != binding["source_preflight_report_sha256"]
        ):
            raise SearchExecutorError("SEARCH_TRUSTED_VERIFIER_BINDING_MISMATCH")
        return result
    return _execute_ordered_search_core(
        domain,
        evaluate=bound_evaluate,
        attempt_ledger_path=attempt_ledger_path,
        state_receipt_path=state_receipt_path,
        custody_binding=binding,
    )


def _execute_ordered_search_core(
    domain: SearchDomain,
    *,
    evaluate: Callable[[CandidateSpec], dict[str, Any]],
    attempt_ledger_path: Path,
    state_receipt_path: Path | None = None,
    custody_binding: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run candidates in locked order, stopping at first trusted PASS.

    Evaluators must return exactly PASS_STATUS with a saved-archive hash, or
    REJECT_STATUS with a stable rejection code. Unknown/missing fields and
    exceptions abort; they never become a geometric rejection or no-pass.
    """
    locked_domain = build_locked_search_domain(domain.report)
    if (
        len(domain.candidates) != 1_372
        or len({c.candidate_id for c in domain.candidates}) != 1_372
        or domain.domain_sha256 != locked_domain.domain_sha256
        or domain.candidates != locked_domain.candidates
    ):
        raise SearchExecutorError("SEARCH_DOMAIN_NOT_LOCKED")
    if attempt_ledger_path.exists() and attempt_ledger_path.stat().st_size:
        raise SearchExecutorError("SEARCH_ATTEMPT_LEDGER_ALREADY_EXISTS")
    state_path = state_receipt_path or attempt_ledger_path.with_suffix(".state.json")
    if state_path.exists():
        raise SearchExecutorError("SEARCH_STATE_ALREADY_EXISTS")
    run_id = str(uuid.uuid4())
    binding = dict(custody_binding or {})
    _atomic_json(state_path, {
        "schema": "T03_C2_CANDIDATE_SEARCH_STATE_V1",
        "status": "SEARCH_RUNNING",
        "attempted_candidate_count": 0,
        "candidate_domain_sha256": domain.domain_sha256,
        "run_id": run_id,
        "next_candidate_ordinal": 1,
        "last_committed_attempt_ledger_sha256": _sha(b""),
        **binding,
    })
    attempts = 0
    for candidate in domain.candidates:
        record_base = {
            "ordinal": candidate.ordinal,
            "candidate_id": candidate.candidate_id,
            "candidate_spec": candidate.canonical_record(),
        }
        try:
            outcome = evaluate(candidate)
        except Exception as exc:
            _append_record(attempt_ledger_path, {
                **record_base,
                "status": "ABORTED_EVALUATOR_EXCEPTION",
                "error_type": type(exc).__name__,
                "error": str(exc),
            })
            receipt = {
                "schema": "T03_C2_CANDIDATE_SEARCH_RESULT_V1",
                "status": "ABORTED_EXECUTION",
                "attempted_candidate_count": attempts + 1,
                "candidate_domain_sha256": domain.domain_sha256,
                "attempt_ledger_path": str(attempt_ledger_path),
                "attempt_ledger_sha256": _sha(attempt_ledger_path.read_bytes()),
                "run_id": run_id,
                **binding,
            }
            _atomic_json(state_path, receipt)
            return receipt
        if not isinstance(outcome, dict):
            outcome = {}
        status = outcome.get("status")
        if status == PASS_STATUS:
            archive_sha = outcome.get("saved_archive_sha256")
            if not isinstance(archive_sha, str) or len(archive_sha) != 64:
                _append_record(attempt_ledger_path, {**record_base, "status": "ABORTED_PASS_WITHOUT_ARCHIVE_HASH"})
                receipt = {
                    "schema": "T03_C2_CANDIDATE_SEARCH_RESULT_V1",
                    "status": "ABORTED_EXECUTION",
                    "attempted_candidate_count": attempts + 1,
                    "candidate_domain_sha256": domain.domain_sha256,
                    "attempt_ledger_path": str(attempt_ledger_path),
                    "attempt_ledger_sha256": _sha(attempt_ledger_path.read_bytes()),
                    "run_id": run_id,
                    **binding,
                }
                _atomic_json(state_path, receipt)
                return receipt
            attempts += 1
            _append_record(attempt_ledger_path, {
                **record_base,
                "status": "PASS_FIRST_VALID_CANDIDATE",
                "saved_archive_sha256": archive_sha,
                "saved_archive_path": outcome.get("saved_archive_path"),
                "verifier_status": status,
            })
            receipt = {
                "schema": "T03_C2_CANDIDATE_SEARCH_RESULT_V1",
                "status": "FIRST_VALID_CANDIDATE",
                "attempted_candidate_count": attempts,
                "candidate_domain_sha256": domain.domain_sha256,
                "candidate_id": candidate.candidate_id,
                "saved_archive_sha256": archive_sha,
                "saved_archive_path": outcome.get("saved_archive_path"),
                "attempt_ledger_path": str(attempt_ledger_path),
                "attempt_ledger_sha256": _sha(attempt_ledger_path.read_bytes()),
                "run_id": run_id,
                "route_search_executed": True,
                "candidate_accepted_for_engineering_or_manufacture": False,
                **binding,
            }
            _atomic_json(state_path, receipt)
            return receipt
        if status == REJECT_STATUS and isinstance(outcome.get("reason_code"), str) and outcome["reason_code"]:
            attempts += 1
            _append_record(attempt_ledger_path, {
                **record_base,
                "status": REJECT_STATUS,
                "reason_code": outcome["reason_code"],
            })
            _atomic_json(state_path, {
                "schema": "T03_C2_CANDIDATE_SEARCH_STATE_V1",
                "status": "SEARCH_RUNNING",
                "attempted_candidate_count": attempts,
                "last_candidate_id": candidate.candidate_id,
                "candidate_domain_sha256": domain.domain_sha256,
                "run_id": run_id,
                "next_candidate_ordinal": candidate.ordinal + 1,
                "last_committed_attempt_ledger_sha256": _sha(attempt_ledger_path.read_bytes()),
                **binding,
            })
            continue
        _append_record(attempt_ledger_path, {
            **record_base,
            "status": "ABORTED_UNEXPECTED_VERIFIER_OUTCOME",
            "verifier_status": status,
        })
        receipt = {
            "schema": "T03_C2_CANDIDATE_SEARCH_RESULT_V1",
            "status": "ABORTED_EXECUTION",
            "attempted_candidate_count": attempts + 1,
            "candidate_domain_sha256": domain.domain_sha256,
            "attempt_ledger_path": str(attempt_ledger_path),
            "attempt_ledger_sha256": _sha(attempt_ledger_path.read_bytes()),
            "run_id": run_id,
            **binding,
        }
        _atomic_json(state_path, receipt)
        return receipt
    receipt = {
        "schema": "T03_C2_CANDIDATE_SEARCH_RESULT_V1",
        "status": "NO_VALID_CANDIDATE_WITHIN_FROZEN_BOUNDS",
        "attempted_candidate_count": attempts,
        "candidate_domain_sha256": domain.domain_sha256,
        "attempt_ledger_path": str(attempt_ledger_path),
        "attempt_ledger_sha256": _sha(attempt_ledger_path.read_bytes()),
        "run_id": run_id,
        "route_search_executed": True,
        "candidate_accepted_for_engineering_or_manufacture": False,
        **binding,
    }
    _atomic_json(state_path, receipt)
    return receipt
