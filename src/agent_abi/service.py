"""Read-only inspection and immutable planning facade for CAM Agent ABI v0.1."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import ABI_VERSION
from .models import ABIError, Response, exact_int, validate_request
from .ports import declared_port
from .registry import canonical_json, load_profile, load_registry, site_record


def _artifact_ref(profile: dict[str, Any], name: str) -> dict[str, str]:
    item = profile["artifacts"][name]
    return {"path": item["path"], "sha256": item["sha256"]}


def _require_profile_id(request: dict[str, Any], name: str = "profile_id") -> str:
    value = request[name]
    if not value:
        raise ABIError("PROFILE_ID_REQUIRED", f"{name} is required for this operation.")
    return value


def _require_crop(loaded: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    profile = loaded["profile"]
    if profile["kind"] != "crop_run":
        raise ABIError("CROP_RUN_REQUIRED", "This operation requires a registered crop run profile.")
    return profile, loaded["decoded"]


def _profile_summary(profile: dict[str, Any], decision: dict[str, Any]) -> dict[str, Any]:
    return {
        "profile_id": profile["profile_id"],
        "label": profile["label"],
        "kind": profile["kind"],
        "owner_status": decision["status"],
        "technical_status": profile["claims"]["technical_geometry"],
        "behavior_status": profile["claims"]["t01_behavior"],
        "engineering_status": profile["claims"]["engineering"],
        "manufacturing_status": profile["claims"]["manufacturing"],
        "source_sha256": profile["source"]["sha256"],
        "policy_sha256": profile["policy_sha256"],
        "scene_sha256": profile.get("scene_sha256"),
    }


def _describe(registry: dict[str, Any]) -> dict[str, Any]:
    return {
        "abi_version": ABI_VERSION,
        "transport": "one JSON request on stdin or --input; one JSON response on stdout",
        "profile_ids": sorted(registry["profiles"]),
        "operations": {
            "cam_describe": {"status": "AVAILABLE", "effect": "read_only"},
            "cam_inspect": {"status": "AVAILABLE", "effect": "read_only"},
            "cam_plan": {"status": "AVAILABLE", "effect": "deterministic_plan_only"},
            "cam_run": {"status": "DECLARED_UNAVAILABLE", "effect": "no_execution"},
            "cam_verify": {"status": "DECLARED_UNAVAILABLE", "effect": "no_rerun"},
            "cam_compare": {"status": "AVAILABLE", "effect": "read_only"},
            "cam_review": {"status": "AVAILABLE", "effect": "read_only"},
        },
        "boundaries": [
            "Only registered local profiles and their hash-bound artifacts are addressable.",
            "A scoped geometry audit PASS does not promote T01 behavioral, engineering, or manufacturing status.",
            "cam_run and cam_verify are declarations only; no execution adapter is qualified.",
        ],
    }


def _inspect(loaded: dict[str, Any], root: Path, site_id: str | None) -> dict[str, Any]:
    profile, decision, decoded = loaded["profile"], loaded["decision"], loaded["decoded"]
    result = {
        "profile": _profile_summary(profile, decision),
        "source": profile["source"],
        "owner_decision": decision,
        "evidence": {name: _artifact_ref(profile, name) for name in sorted(profile["artifacts"])},
    }
    if profile["kind"] == "historical_r1":
        run, verification = decoded["run"], decoded["fresh_verification"]
        result["historical_run"] = {
            "owner_acceptance": run.get("status", {}).get("owner_acceptance"),
            "task_execution": run.get("status", {}).get("task_execution"),
            "technical_checks": run.get("status", {}).get("technical_checks"),
            "fresh_verification_status": verification.get("status"),
            "fresh_verification_binding": "SOURCE_AND_POLICY_BOUND; EXACT_RUN_DIGEST_NOT_PRESENT_IN_HISTORICAL_FORMAT",
            "warning": "The technical PASS_WITH_SCOPE_LIMITS is not owner acceptance.",
        }
        if site_id is not None:
            raise ABIError("SITE_INSPECTION_UNAVAILABLE", "T01-R1 historical profile does not expose site-level ABI records.")
        return result
    report, audit = decoded["report"], decoded["audit"]
    result["run"] = {
        "site_count": len(report["decisions"]),
        "occurrence_count": decoded["selection"]["occurrences"],
        "report_status": report.get("acceptance_status"),
        "fresh_audit_status": audit["status"],
        "t01_overall": audit["t01_overall"],
        "actual_adapted_later_sites": audit["actual_adapted_later_sites"],
        "required_actual_sites": audit["required_actual_sites"],
        "counts": report["counts"],
    }
    if site_id is not None:
        result["site"] = site_record(loaded, site_id, root)
        # Attach only a round-promotion diagnostic explicitly bound to this profile.
        if "coverage" in decoded:
            canonical_site_id = result["site"]["site_id"]
            control = next((item for item in audit.get("round_next_class_controls", []) if item.get("key") == canonical_site_id), None)
            coverage = next((item for item in decoded["coverage"].get("sites", []) if item.get("key") == canonical_site_id), None)
            if control is not None and coverage is not None:
                result["site"]["next_class_test"] = {
                    "status": coverage.get("status"),
                    "allocated_diameter_mm": coverage.get("allocated_diameter_mm"),
                    "proposed_diameter_mm": coverage.get("next_class_diameter_mm"),
                    "local_desired_diameter_mm": coverage.get("local_desired_diameter_mm"),
                    "source_case": control.get("source_case"),
                    "reservation_case": control.get("reservation_case"),
                    "round_blockers": control.get("round_blockers"),
                    "square_blockers": control.get("square_blockers"),
                    "diagnostic_geometry": control.get("geometry"),
                    "evidence": {
                        "coverage": _artifact_ref(profile, "coverage"),
                        "fresh_audit": _artifact_ref(profile, "audit"),
                    },
                }
    return result


def _plan(loaded: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    profile, decision = loaded["profile"], loaded["decision"]
    if profile["kind"] != "crop_run":
        raise ABIError("PLAN_PROFILE_UNSUPPORTED", "Only registered crop recipes can be planned.")
    overrides = request["overrides"]
    if overrides not in (None, {}):
        raise ABIError("POLICY_CHANGE_REQUIRED", "ABI v0.1 accepts no caller overrides; revise and review a separately pinned policy first.")
    recipe_id = profile.get("recipe_id")
    steps = [
        {"step_id": "bind_source_and_scene", "status": "PLANNED", "effect": "read_only"},
        {"step_id": "load_registered_policy_and_selection", "status": "PLANNED", "effect": "read_only"},
        {"step_id": "construct_candidate", "status": "NOT_RUN", "adapter": "cam_run_unavailable"},
        {"step_id": "persist_versioned_candidate", "status": "NOT_RUN", "adapter": "cam_run_unavailable"},
        {"step_id": "fresh_process_verification", "status": "NOT_RUN", "adapter": "cam_verify_unavailable"},
    ]
    core = {
        "schema": "cam-agent-plan/0.1",
        "status": "PLANNED",
        "profile_id": profile["profile_id"],
        "recipe_id": recipe_id,
        "owner_decision_id": decision["decision_id"],
        "owner_decision_status": decision["status"],
        "execution_authorization": "NOT_GRANTED_BY_PLAN",
        "scope": {"kind": "whole_registered_selection", "site_count": len(loaded["decoded"]["report"]["decisions"])},
        "bindings": {
            "source": profile["source"],
            "scene": profile["scene"],
            "policy_sha256": profile["policy_sha256"],
            "selection_sha256": profile["selection_sha256"],
            "registered_report_sha256": profile["artifacts"]["report"]["sha256"],
        },
        "steps": steps,
        "execution_status": "NOT_RUN",
        "verification_status": "NOT_RUN",
        "write_scope": "none",
        "status_note": "The plan is content-addressed and returned only; this ABI does not invoke the recipe.",
    }
    plan_id = "sha256:" + __import__("hashlib").sha256(canonical_json(core)).hexdigest()
    return {"plan_id": plan_id, **core}


def _compare(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    lp, rp = left["profile"], right["profile"]
    if lp["kind"] != "crop_run" or rp["kind"] != "crop_run":
        raise ABIError("COMPARISON_PROFILE_UNSUPPORTED", "Comparison currently requires two structured crop run profiles.")
    if lp["source"]["sha256"] != rp["source"]["sha256"] or lp.get("scene_sha256") != rp.get("scene_sha256"):
        raise ABIError("INCOMPATIBLE_SOURCE_OR_SCENE", "Run profiles do not share both source and scene identities.")
    ld, rd = left["decoded"]["report"], right["decoded"]["report"]
    lrows = {row["source_id"]: row for row in ld["decisions"]}
    rrows = {row["source_id"]: row for row in rd["decisions"]}
    if set(lrows) != set(rrows):
        raise ABIError("INCOMPATIBLE_SITE_CENSUS", "Run profiles have different source-identified site censuses.")
    changed = []
    for source_id in sorted(lrows):
        a, b = lrows[source_id], rrows[source_id]
        if a.get("candidate_sha256") != b.get("candidate_sha256"):
            changed.append({"source_id": source_id, "left_site_id": a["key"], "right_site_id": b["key"], "left_candidate_sha256": a["candidate_sha256"], "right_candidate_sha256": b["candidate_sha256"], "left_proposed_envelope_diameter_mm": 2*a["proposed_radius_mm"], "right_proposed_envelope_diameter_mm": 2*b["proposed_radius_mm"]})
    return {
        "status": "COMPARISON_COMPLETE",
        "compatibility": {"source_compatible": True, "scene_compatible": True, "policy_compatible": lp["policy_sha256"] == rp["policy_sha256"], "selection_compatible": lp["selection_sha256"] == rp["selection_sha256"]},
        "left_profile_id": lp["profile_id"], "right_profile_id": rp["profile_id"],
        "left_policy_sha256": lp["policy_sha256"], "right_policy_sha256": rp["policy_sha256"],
        "changed_site_count": len(changed), "changed_sites": changed,
        "claim_limit": "Byte-level candidate differences only; policy differences prevent treating outputs as an equivalent replay.",
    }


def dispatch(request: Any, *, root: Path | None = None) -> dict[str, Any]:
    operation = request.get("operation", "") if type(request) is dict else ""
    try:
        request = validate_request(request)
        root = (root or Path(__file__).resolve().parents[2]).resolve()
        registry, decisions = load_registry(root)
        op = request["operation"]
        if op == "cam_describe":
            result = _describe(registry)
        elif op in {"cam_run", "cam_verify"}:
            result = declared_port(op).response_result()
            return Response(ABI_VERSION, op, "NOT_RUN", result, None).to_dict()
        elif op in {"cam_inspect", "cam_plan", "cam_review"}:
            pid = _require_profile_id(request)
            loaded = load_profile(root, registry, decisions, pid)
            if op == "cam_inspect":
                result = _inspect(loaded, root, request["site_id"])
            elif op == "cam_plan":
                result = _plan(loaded, request)
            else:
                profile, decision = loaded["profile"], loaded["decision"]
                result = {
                    "profile": _profile_summary(profile, decision),
                    "decision": decision,
                    "review_artifacts": {name: _artifact_ref(profile, name) for name in sorted(profile["artifacts"]) if name in {"report", "audit", "receipt", "coverage", "owner_review", "decision"}},
                    "replay_status": "READ_ONLY_SAVED_RESULT",
                }
        elif op == "cam_compare":
            left_id, right_id = request["left_profile_id"], request["right_profile_id"]
            if not left_id or not right_id:
                raise ABIError("COMPARISON_PROFILE_IDS_REQUIRED", "left_profile_id and right_profile_id are required.")
            result = _compare(load_profile(root, registry, decisions, left_id), load_profile(root, registry, decisions, right_id))
        else:  # validate_request makes this unreachable
            raise ABIError("OPERATION_UNKNOWN", "Operation is not registered.")
        return Response(ABI_VERSION, op, "OK", result, None).to_dict()
    except ABIError as exc:
        return Response(ABI_VERSION, operation if type(operation) is str else "", exc.status, None, {"code": exc.code, "message": str(exc)}).to_dict()
    except (KeyError, TypeError, ValueError, OSError, json.JSONDecodeError) as exc:
        return Response(ABI_VERSION, operation if type(operation) is str else "", "FAIL", None, {"code": "LOCAL_ADAPTER_ERROR", "message": f"Local evidence could not be safely interpreted: {type(exc).__name__}: {exc}"}).to_dict()
