"""Hash-checked registry and evidence adapters for local T01 artifacts."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .models import ABIError, exact_int, exact_pass


# Updated only together with the reviewed, project-local v0.1 registry files.
TRUSTED_REGISTRY_SHA256 = "f5e0cac1e46e0d88da8f4952ea931e557544c197dfc9de1d0a0f8c00a62e433c"
TRUSTED_OWNER_DECISIONS_SHA256 = "da2ac4ebb3523ac4111e0e3f9593b29be90e6fd04c2d3938fd4186920cbb7aa5"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _read_pinned_json(root: Path, relative: str, expected_sha256: str) -> dict[str, Any]:
    path = root / relative
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ABIError("REGISTRY_EVIDENCE_MISSING", f"Required local registry file is unavailable: {relative}.", status="NOT_RUN") from exc
    actual = sha256_bytes(raw)
    if expected_sha256 != "PENDING" and actual != expected_sha256:
        raise ABIError("TRUSTED_REGISTRY_HASH_MISMATCH", f"Trusted registry hash mismatch: {relative}.", status="FAIL")
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ABIError("REGISTRY_JSON_INVALID", f"Invalid JSON in {relative}.", status="FAIL") from exc
    if type(value) is not dict:
        raise ABIError("REGISTRY_SHAPE_INVALID", f"Expected a JSON object in {relative}.", status="FAIL")
    return value


def load_registry(root: Path | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    root = (root or project_root()).resolve()
    registry = _read_pinned_json(root, "contracts/agent_abi/v0_1/registry.json", TRUSTED_REGISTRY_SHA256)
    decisions = _read_pinned_json(root, "contracts/agent_abi/v0_1/owner_decisions.json", TRUSTED_OWNER_DECISIONS_SHA256)
    if registry.get("schema") != "cam-agent-abi-registry/0.1" or decisions.get("schema") != "cam-agent-owner-decisions/0.1":
        raise ABIError("REGISTRY_SCHEMA_UNSUPPORTED", "Local registry schema is not CAM Agent ABI v0.1.", status="FAIL")
    if type(registry.get("profiles")) is not dict or type(decisions.get("decisions")) is not dict:
        raise ABIError("REGISTRY_SHAPE_INVALID", "Profiles and owner decisions must be objects.", status="FAIL")
    return registry, decisions


def _safe_project_file(root: Path, relative: str) -> Path:
    if type(relative) is not str or not relative or Path(relative).is_absolute():
        raise ABIError("EVIDENCE_PATH_INVALID", "Evidence paths must be non-empty project-relative paths.", status="FAIL")
    path = (root / relative).resolve()
    if not path.is_relative_to(root):
        raise ABIError("EVIDENCE_PATH_OUTSIDE_PROJECT", "Evidence path resolves outside this checkout.", status="FAIL")
    if not (path.is_relative_to(root / "out") or path.is_relative_to(root / "dataset") or path.is_relative_to(root / "docs")):
        raise ABIError("EVIDENCE_PATH_OUTSIDE_ALLOWED_ROOT", "ABI artifacts must stay under out/, dataset/, or docs/.", status="FAIL")
    return path


def _load_artifacts(root: Path, profile: dict[str, Any]) -> tuple[dict[str, bytes], dict[str, Any]]:
    artifacts: dict[str, bytes] = {}
    decoded: dict[str, Any] = {}
    for name, spec in profile.get("artifacts", {}).items():
        if type(spec) is not dict or set(spec) != {"path", "sha256"}:
            raise ABIError("ARTIFACT_BINDING_INVALID", f"Invalid artifact binding for {name}.", status="FAIL")
        path = _safe_project_file(root, spec["path"])
        try:
            raw = path.read_bytes()
        except OSError as exc:
            raise ABIError("ARTIFACT_MISSING", f"Required evidence is missing: {spec['path']}.", status="NOT_RUN") from exc
        if sha256_bytes(raw) != spec["sha256"]:
            raise ABIError("ARTIFACT_HASH_MISMATCH", f"Evidence hash mismatch: {spec['path']}.", status="FAIL")
        artifacts[name] = raw
        if name in {"policy", "selection", "report", "audit", "receipt", "coverage", "run", "fresh_verification"}:
            try:
                decoded[name] = json.loads(raw)
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ABIError("ARTIFACT_JSON_INVALID", f"Invalid JSON artifact: {spec['path']}.", status="FAIL") from exc
    return artifacts, decoded


def _check_scene_and_source(root: Path, profile: dict[str, Any]) -> None:
    source = profile.get("source")
    if type(source) is not dict or set(source) != {"path", "sha256"}:
        raise ABIError("SOURCE_BINDING_INVALID", "Registered profile must bind one source path and SHA-256.", status="FAIL")
    source_path = _safe_project_file(root, source["path"])
    try:
        actual = sha256_file(source_path)
    except OSError as exc:
        raise ABIError("SOURCE_MISSING", f"Registered source is missing: {source['path']}.", status="NOT_RUN") from exc
    if actual != source["sha256"]:
        raise ABIError("SOURCE_HASH_MISMATCH", "Registered source bytes differ from the pinned profile.", status="FAIL")
    scene = profile.get("scene")
    if scene is not None:
        if type(scene) is not dict or set(scene) != {"path", "sha256"}:
            raise ABIError("SCENE_BINDING_INVALID", "Scene binding must contain path and SHA-256.", status="FAIL")
        scene_path = _safe_project_file(root, scene["path"])
        try:
            actual_scene = sha256_file(scene_path)
        except OSError as exc:
            raise ABIError("SCENE_MISSING", f"Registered scene is missing: {scene['path']}.", status="NOT_RUN") from exc
        if actual_scene != scene["sha256"]:
            raise ABIError("SCENE_HASH_MISMATCH", "Registered scene bytes differ from the pinned profile.", status="FAIL")


def _validate_historical_r1(profile: dict[str, Any], decision: dict[str, Any], decoded: dict[str, Any]) -> None:
    run, verification = decoded["run"], decoded["fresh_verification"]
    if run.get("source_sha256") != profile["source"]["sha256"] or verification.get("source_sha256") != profile["source"]["sha256"]:
        raise ABIError("HISTORICAL_SOURCE_MISMATCH", "Historical R1 record is bound to another source.", status="FAIL")
    if run.get("policy_sha256") != profile["policy_sha256"] or verification.get("policy_sha256") != profile["policy_sha256"]:
        raise ABIError("HISTORICAL_POLICY_MISMATCH", "Historical R1 record is bound to another policy.", status="FAIL")
    if run.get("source_path") != profile["source"]["path"] or run.get("policy_path") != profile["artifacts"]["policy"]["path"]:
        raise ABIError("HISTORICAL_PATH_BINDING_MISMATCH", "Historical run paths differ from the registered source or policy.", status="FAIL")
    nested_run = run.get("run")
    if type(nested_run) is not dict or nested_run.get("contract_sha256") != profile["policy_sha256"]:
        raise ABIError("HISTORICAL_CONTRACT_BINDING_MISMATCH", "Historical run contract does not match the registered policy.", status="FAIL")
    run_status = run.get("status")
    if type(run_status) is not dict or run_status.get("fresh_verification_path") != profile["artifacts"]["fresh_verification"]["path"]:
        raise ABIError("HISTORICAL_VERIFICATION_PATH_MISMATCH", "Historical run does not point to the registered fresh-verification artifact.", status="FAIL")
    technical_status = run_status.get("technical_checks")
    if type(technical_status) is not str or verification.get("status") != technical_status or profile.get("claims", {}).get("technical_geometry") != technical_status:
        raise ABIError("HISTORICAL_TECHNICAL_STATUS_MISMATCH", "Run, verification, and registered technical statuses disagree.", status="FAIL")
    checks, failed_checks = verification.get("checks"), verification.get("failed_checks")
    if type(checks) is not list or type(failed_checks) is not list:
        raise ABIError("HISTORICAL_VERIFICATION_SHAPE_INVALID", "Historical verification checks and failures must be lists.", status="FAIL")
    if technical_status.startswith("PASS") and (not checks or failed_checks or any(type(item) is not dict or item.get("status") != "PASS" for item in checks)):
        raise ABIError("HISTORICAL_PASS_CHECK_MISMATCH", "Historical PASS status conflicts with its per-check verification evidence.", status="FAIL")
    if technical_status == "FAIL" and (not failed_checks or not any(type(item) is dict and item.get("status") == "FAIL" for item in checks)):
        raise ABIError("HISTORICAL_FAIL_CHECK_MISMATCH", "Historical FAIL status is not supported by failed per-check evidence.", status="FAIL")
    if run_status.get("owner_acceptance") != "NOT_ACCEPTED":
        raise ABIError("HISTORICAL_REJECTION_NOT_PRESERVED", "T01-R1 rejection status changed or is absent.", status="FAIL")
    if decision.get("report_sha256") != profile["artifacts"]["run"]["sha256"] or decision.get("policy_sha256") != profile["policy_sha256"]:
        raise ABIError("HISTORICAL_OWNER_BINDING_MISMATCH", "T01-R1 owner rejection is not bound to this run and policy.", status="FAIL")
    if decision.get("owner_review_sha256") != profile["artifacts"]["owner_review"]["sha256"]:
        raise ABIError("HISTORICAL_OWNER_DOCUMENT_MISMATCH", "T01-R1 rejection is not bound to the owner review document.", status="FAIL")
    if decision.get("status") != profile.get("claims", {}).get("owner_review"):
        raise ABIError("HISTORICAL_OWNER_STATUS_MISMATCH", "Historical owner rejection status differs from the pinned decision record.", status="FAIL")


def load_profile(root: Path, registry: dict[str, Any], decisions: dict[str, Any], profile_id: str) -> dict[str, Any]:
    profiles = registry["profiles"]
    if profile_id not in profiles:
        raise ABIError("PROFILE_UNKNOWN", f"No registered profile named {profile_id!r}.")
    profile = profiles[profile_id]
    if type(profile) is not dict or profile.get("profile_id") != profile_id:
        raise ABIError("PROFILE_REGISTRY_INVALID", "Profile identity is inconsistent.", status="FAIL")
    _check_scene_and_source(root, profile)
    raw_artifacts, decoded = _load_artifacts(root, profile)
    decision_id = profile.get("owner_decision_id")
    decision = decisions["decisions"].get(decision_id)
    if type(decision) is not dict or decision.get("decision_id") != decision_id:
        raise ABIError("OWNER_DECISION_UNKNOWN", "Profile has no trusted owner decision record.", status="FAIL")
    if decision.get("source_sha256") != profile["source"]["sha256"]:
        raise ABIError("OWNER_DECISION_SOURCE_MISMATCH", "Owner decision is not bound to this source.", status="FAIL")
    if profile.get("kind") == "crop_run":
        _validate_crop_run(root, profile, decoded)
        if decision.get("status") != profile.get("claims", {}).get("owner_review"):
            raise ABIError("OWNER_DECISION_STATUS_MISMATCH", "Registered owner status and hash-bound decision record differ.", status="FAIL")
        expected_decision_bindings = {
            "report_sha256": profile["artifacts"]["report"]["sha256"],
            "policy_sha256": profile["policy_sha256"],
            "scene_sha256": profile["scene_sha256"],
            "audit_sha256": profile["artifacts"]["audit"]["sha256"],
        }
        if any(decision.get(key) != value for key, value in expected_decision_bindings.items()):
            raise ABIError("OWNER_DECISION_RUN_MISMATCH", "Owner decision is bound to another report, policy, scene, or audit.", status="FAIL")
    elif profile.get("kind") == "historical_r1":
        _validate_historical_r1(profile, decision, decoded)
    else:
        raise ABIError("PROFILE_KIND_UNSUPPORTED", f"Unsupported local profile kind: {profile.get('kind')}.", status="FAIL")
    return {"profile": profile, "decision": decision, "raw_artifacts": raw_artifacts, "decoded": decoded}


def _validate_crop_run(root: Path, profile: dict[str, Any], decoded: dict[str, Any]) -> None:
    required = {"policy", "selection", "report", "audit", "receipt"}
    if not required.issubset(decoded):
        raise ABIError("RUN_EVIDENCE_INCOMPLETE", "Crop profile lacks a required policy, scene, report, audit, or receipt.", status="NOT_RUN")
    policy, selection, report, audit, receipt = (decoded[k] for k in ("policy", "selection", "report", "audit", "receipt"))
    source_sha = profile["source"]["sha256"]
    policy_sha = profile["artifacts"]["policy"]["sha256"]
    selection_sha = profile["artifacts"]["selection"]["sha256"]
    report_sha = profile["artifacts"]["report"]["sha256"]
    audit_sha = profile["artifacts"]["audit"]["sha256"]
    if policy.get("source_sha256") != source_sha or report.get("source_sha256") != source_sha or selection.get("source_sha256") != source_sha:
        raise ABIError("RUN_SOURCE_BINDING_MISMATCH", "Run artifacts do not share the registered source identity.", status="FAIL")
    if policy.get("source") != profile["source"]["path"]:
        raise ABIError("RUN_SOURCE_PATH_MISMATCH", "Policy source path differs from the registered source identity.", status="FAIL")
    if report.get("policy_sha256") != policy_sha or profile.get("policy_sha256") != policy_sha:
        raise ABIError("RUN_POLICY_BINDING_MISMATCH", "Report, policy bytes, and registered policy identity differ.", status="FAIL")
    if profile.get("report_sha256") != report_sha:
        raise ABIError("RUN_REPORT_ALIAS_MISMATCH", "Duplicated report identity does not match the validated report artifact.", status="FAIL")
    if report.get("selection_sha256") != selection_sha or profile.get("selection_sha256") != selection_sha:
        raise ABIError("RUN_SELECTION_BINDING_MISMATCH", "Report and registered source selection differ.", status="FAIL")
    if audit.get("report_sha256") != report_sha or receipt.get("report_sha256") != report_sha:
        raise ABIError("RUN_AUDIT_REPORT_BINDING_MISMATCH", "Fresh audit/receipt do not bind the exact report bytes.", status="FAIL")
    if receipt.get("audit_sha256") != audit_sha or receipt.get("selection_sha256") != selection_sha:
        raise ABIError("RUN_RECEIPT_BINDING_MISMATCH", "Publication receipt does not bind this audit and selection.", status="FAIL")
    if "coverage" in decoded:
        coverage = decoded["coverage"]
        if coverage.get("report_sha256") != report_sha or coverage.get("audit_sha256") != audit_sha:
            raise ABIError("RUN_COVERAGE_BINDING_MISMATCH", "Round-priority coverage is not bound to this exact report and audit.", status="FAIL")
    if audit.get("status") != "PASS_SCOPED_FRESH_CROP_AUDIT":
        raise ABIError("FRESH_AUDIT_NOT_PASS", "Fresh audit is absent or does not have the exact scoped PASS status.", status="NOT_RUN")
    if audit.get("t01_overall") != "PARTIAL_INSUFFICIENT_ACTUAL_DYNAMIC_EVENTS":
        raise ABIError("T01_STATUS_UNEXPECTED", "T01 overall status is not the expected bounded PARTIAL result.", status="FAIL")
    adapted, required_events = audit.get("actual_adapted_later_sites"), audit.get("required_actual_sites")
    if not exact_int(adapted) or not exact_int(required_events):
        raise ABIError("AUDIT_COUNT_TYPE_INVALID", "Audit event counts must be JSON integers, never booleans.", status="FAIL")
    if adapted != 0 or required_events != 3:
        raise ABIError("AUDIT_BEHAVIORAL_STATUS_MISMATCH", "The frozen crop's adaptation evidence changed unexpectedly.", status="FAIL")
    if profile.get("scene") is None or profile["scene"]["sha256"] != profile.get("scene_sha256"):
        raise ABIError("RUN_SCENE_BINDING_MISMATCH", "Run scene does not match the profile's pinned scene identity.", status="FAIL")
    decisions = report.get("decisions")
    selected_sites = selection.get("sites")
    unique_sites, occurrences = selection.get("unique_sites"), selection.get("occurrences")
    if not exact_int(unique_sites) or not exact_int(occurrences):
        raise ABIError("SELECTION_COUNT_TYPE_INVALID", "Selection counts must be JSON integers, never booleans.", status="FAIL")
    if type(selected_sites) is not list or len(selected_sites) != unique_sites:
        raise ABIError("SELECTION_SITE_CENSUS_INVALID", "Selection must contain one source-identified record per unique site.", status="FAIL")
    selected_source_ids = []
    for selected in selected_sites:
        if type(selected) is not dict or type(selected.get("source_id")) is not str:
            raise ABIError("SELECTION_SITE_IDENTITY_INVALID", "Every selected site must include a string source_id.", status="FAIL")
        selected_source_ids.append(selected["source_id"])
    if len(set(selected_source_ids)) != len(selected_source_ids):
        raise ABIError("SELECTION_SITE_IDENTITY_DUPLICATED", "Selection contains duplicate source identities.", status="FAIL")
    if type(decisions) is not list or len(decisions) != unique_sites:
        raise ABIError("RUN_SITE_CENSUS_MISMATCH", "Per-site report and source selection have different site counts.", status="FAIL")
    counts = report.get("counts")
    if type(counts) is not dict or any(not exact_int(value) for value in counts.values()):
        raise ABIError("REPORT_COUNT_TYPE_INVALID", "Report counts must be JSON integers, never booleans.", status="FAIL")
    run_dir = _safe_project_file(root, profile["artifact_dir"])
    seen_keys: set[str] = set()
    seen_source_ids: set[str] = set()
    row_by_key: dict[str, dict[str, Any]] = {}
    for row in decisions:
        if type(row) is not dict or type(row.get("key")) is not str or type(row.get("source_id")) is not str:
            raise ABIError("SITE_IDENTITY_INVALID", "Every crop decision requires a string site key and source identity.", status="FAIL")
        if row["key"] in seen_keys or row["source_id"] in seen_source_ids:
            raise ABIError("SITE_IDENTITY_DUPLICATED", "Crop report contains duplicate site or source identities.", status="FAIL")
        seen_keys.add(row["key"])
        seen_source_ids.add(row["source_id"])
        row_by_key[row["key"]] = row
        verification = row.get("verification")
        checks = verification.get("checks") if type(verification) is dict else None
        mandatory_checks = {
            "all_optional_parts_attached", "hard_gap_outside_source_attachment_ports",
            "inside_declared_envelope", "source_core_preserved", "valid",
        }
        if type(checks) is not dict or not mandatory_checks.issubset(checks):
            raise ABIError("SITE_VERIFICATION_CHECKS_MISSING", "Each site must include all mandatory checks for the registered crop report contract.", status="FAIL")
        if any(type(value) is not bool for value in checks.values()):
            raise ABIError("SITE_VERIFICATION_CHECK_TYPE_INVALID", "Every site check value must be a JSON boolean.", status="FAIL")
        if not exact_pass(verification.get("passed")) or any(checks[name] is not True for name in mandatory_checks):
            raise ABIError("SITE_VERIFICATION_STATUS_INVALID", "A site PASS requires every mandatory check to be literal true.", status="FAIL")
        violations = verification.get("hard_gap_violations")
        if type(violations) is not list or violations:
            raise ABIError("SITE_VERIFICATION_VIOLATION_MISMATCH", "A site PASS cannot include recorded hard-gap violations.", status="FAIL")
        geometry_path = row.get("geometry", {}).get("dynamic")
        candidate_sha = row.get("candidate_sha256")
        if type(geometry_path) is not str or type(candidate_sha) is not str or len(candidate_sha) != 64:
            raise ABIError("SITE_CANDIDATE_BINDING_MISSING", "Every site requires a saved candidate path and SHA-256.", status="NOT_RUN")
        candidate = (run_dir / geometry_path).resolve()
        if not candidate.is_relative_to(run_dir) or not candidate.is_file():
            raise ABIError("SITE_CANDIDATE_MISSING", f"Saved candidate is missing or escapes its run: {row['key']}.", status="NOT_RUN")
        if sha256_file(candidate) != candidate_sha:
            raise ABIError("SITE_CANDIDATE_HASH_MISMATCH", f"Saved candidate bytes do not match site {row['key']}'s report record.", status="FAIL")
    if set(selected_source_ids) != seen_source_ids:
        raise ABIError("REPORT_SELECTION_IDENTITY_MISMATCH", "Report source identities do not match the registered source selection.", status="FAIL")

    if "coverage" in decoded:
        coverage_sites = decoded["coverage"].get("sites")
        if type(coverage_sites) is not list:
            raise ABIError("COVERAGE_SITE_LIST_INVALID", "Round-priority coverage sites must be a list.", status="FAIL")
        for item in coverage_sites:
            if type(item) is not dict or type(item.get("key")) is not str or item.get("key") not in row_by_key:
                raise ABIError("COVERAGE_SITE_IDENTITY_INVALID", "Coverage site does not resolve to a registered report row.", status="FAIL")
            if item.get("source_id") != row_by_key[item["key"]]["source_id"]:
                raise ABIError("COVERAGE_SOURCE_IDENTITY_MISMATCH", "Coverage site key and source identity refer to different records.", status="FAIL")

    controls = audit.get("round_next_class_controls", [])
    if type(controls) is not list:
        raise ABIError("DIAGNOSTIC_CONTROL_LIST_INVALID", "Next-class diagnostic controls must be a list.", status="FAIL")
    for control in controls:
        if type(control) is not dict or type(control.get("key")) is not str or control.get("key") not in row_by_key:
            raise ABIError("DIAGNOSTIC_SITE_IDENTITY_INVALID", "Next-class diagnostic does not resolve to a registered report row.", status="FAIL")
        if control.get("source_id") != row_by_key[control["key"]]["source_id"]:
            raise ABIError("DIAGNOSTIC_SOURCE_IDENTITY_MISMATCH", "Next-class diagnostic key and source identity refer to different records.", status="FAIL")
        geometry = control.get("geometry")
        if type(geometry) is not dict or set(geometry) != {"blockers", "circle", "intrusion"}:
            raise ABIError("DIAGNOSTIC_GEOMETRY_BINDING_INVALID", "Each next-class diagnostic must bind blocker, proposed-circle, and intrusion geometries.", status="FAIL")
        for label, binding in geometry.items():
            if type(binding) is not dict or set(binding) != {"path", "sha256"} or type(binding["path"]) is not str or not binding["path"] or type(binding["sha256"]) is not str or len(binding["sha256"]) != 64 or any(ch not in "0123456789abcdef" for ch in binding["sha256"]):
                raise ABIError("DIAGNOSTIC_GEOMETRY_BINDING_INVALID", f"Invalid {label} diagnostic geometry binding.", status="FAIL")
            diagnostic = (run_dir / binding["path"]).resolve()
            if not diagnostic.is_relative_to(run_dir):
                raise ABIError("DIAGNOSTIC_GEOMETRY_PATH_INVALID", f"Diagnostic geometry escapes the registered run: {label}.", status="FAIL")
            if not diagnostic.is_file():
                raise ABIError("DIAGNOSTIC_GEOMETRY_MISSING", f"Diagnostic geometry is unavailable: {label}.", status="NOT_RUN")
            if sha256_file(diagnostic) != binding["sha256"]:
                raise ABIError("DIAGNOSTIC_GEOMETRY_HASH_MISMATCH", f"Diagnostic geometry hash differs: {label}.", status="FAIL")


def site_record(loaded: dict[str, Any], site_id: str, root: Path) -> dict[str, Any]:
    profile, decoded = loaded["profile"], loaded["decoded"]
    if profile["kind"] != "crop_run":
        raise ABIError("SITE_INSPECTION_UNAVAILABLE", "This historical profile has no site-level crop report.")
    matches = [row for row in decoded["report"]["decisions"] if row.get("key") == site_id or row.get("source_id") == site_id]
    if len(matches) != 1:
        raise ABIError("SITE_NOT_FOUND_OR_AMBIGUOUS", f"Site {site_id!r} does not resolve to exactly one record.")
    row = matches[0]
    geometry_path = row.get("geometry", {}).get("dynamic")
    if not geometry_path or "candidate_sha256" not in row:
        raise ABIError("SITE_CANDIDATE_BINDING_MISSING", "Site has no exact saved candidate binding.", status="NOT_RUN")
    run_dir = _safe_project_file(root, profile["artifact_dir"])
    candidate = (run_dir / geometry_path).resolve()
    if not candidate.is_relative_to(run_dir) or not candidate.is_file():
        raise ABIError("SITE_CANDIDATE_MISSING", "Saved site candidate is missing or escapes its run bundle.", status="NOT_RUN")
    candidate_sha = sha256_file(candidate)
    if candidate_sha != row["candidate_sha256"]:
        raise ABIError("SITE_CANDIDATE_HASH_MISMATCH", "Site candidate bytes do not match this report row.", status="FAIL")
    return {
        "site_id": row["key"], "source_id": row["source_id"], "decision": row["decision"],
        "proposed_envelope_diameter_mm": 2 * row["proposed_radius_mm"], "verification_status": "PASS",
        "candidate": {"path": f"{profile['artifact_dir']}/{geometry_path}", "sha256": candidate_sha},
        "minimum_unexempted_addition_gap_mm": row["verification"].get("minimum_unexempted_addition_gap_mm"),
        "minimum_gap_source_id": row["verification"].get("minimum_gap_source_id"),
    }
