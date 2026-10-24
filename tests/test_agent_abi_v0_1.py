from __future__ import annotations

import copy
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.agent_abi.models import ABIError, exact_int, exact_pass, validate_request
from src.agent_abi.registry import _validate_crop_run, _validate_historical_r1, load_profile, load_registry, sha256_file
from src.agent_abi.service import _compare, dispatch


ROOT = Path(__file__).resolve().parents[1]


def request(operation: str, **updates):
    value = {
        "abi_version": "0.1", "operation": operation, "profile_id": None,
        "site_id": None, "left_profile_id": None, "right_profile_id": None,
        "overrides": None,
    }
    value.update(updates)
    return value


class CamAgentABIv01Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry, cls.owner_decisions = load_registry(ROOT)

    def test_describe_lists_seven_operations_and_profiles(self):
        response = dispatch(request("cam_describe"), root=ROOT)
        self.assertEqual(response["status"], "OK")
        self.assertEqual(set(response["result"]["operations"]), {
            "cam_describe", "cam_inspect", "cam_plan", "cam_run", "cam_verify", "cam_compare", "cam_review"
        })
        self.assertEqual(response["result"]["operations"]["cam_run"]["status"], "DECLARED_UNAVAILABLE")

    def test_accepted_visual_crop_keeps_behavior_partial(self):
        response = dispatch(request("cam_inspect", profile_id="t01_visual_crop_accepted"), root=ROOT)
        self.assertEqual(response["status"], "OK")
        result = response["result"]
        self.assertEqual(result["profile"]["owner_status"], "ACCEPTED_VISUAL_CROP")
        self.assertEqual(result["profile"]["behavior_status"], "PARTIAL_0_OF_3")
        self.assertEqual(result["profile"]["engineering_status"], "NOT_ESTABLISHED")
        self.assertEqual(result["run"]["actual_adapted_later_sites"], 0)
        self.assertEqual(result["run"]["required_actual_sites"], 3)

    def test_site_inspection_binds_candidate_to_its_own_site_record(self):
        response = dispatch(request("cam_inspect", profile_id="t01_visual_crop_accepted", site_id="S14"), root=ROOT)
        self.assertEqual(response["status"], "OK")
        site = response["result"]["site"]
        self.assertEqual(site["site_id"], "S14")
        self.assertEqual(site["verification_status"], "PASS")
        self.assertIn("proposed_envelope_diameter_mm", site)
        self.assertNotIn("diameter_mm", site)
        self.assertEqual(sha256_file(ROOT / site["candidate"]["path"]), site["candidate"]["sha256"])
        missing = dispatch(request("cam_inspect", profile_id="t01_visual_crop_accepted", site_id="unrelated-contour"), root=ROOT)
        self.assertEqual(missing["status"], "REJECTED")
        self.assertEqual(missing["error"]["code"], "SITE_NOT_FOUND_OR_AMBIGUOUS")

    def test_promotion_inspection_exposes_s14_blocker_evidence(self):
        response = dispatch(request("cam_inspect", profile_id="t01_round_priority_promotion", site_id="S14"), root=ROOT)
        self.assertEqual(response["status"], "OK")
        detail = response["result"]["site"]["next_class_test"]
        self.assertEqual(detail["status"], "NEXT_LOCAL_CLASS_TESTED_AND_REJECTED")
        self.assertAlmostEqual(detail["allocated_diameter_mm"], 0.3749)
        self.assertAlmostEqual(detail["proposed_diameter_mm"], 0.4499)
        self.assertAlmostEqual(detail["round_blockers"][0]["gap_mm"], -0.007940264577105172)
        self.assertIn(":bytes:1540609:1540733", detail["round_blockers"][0]["source_id"])
        self.assertEqual(detail["reservation_case"]["gap_status"], "FAIL")
        for record in detail["diagnostic_geometry"].values():
            self.assertEqual(sha256_file(ROOT / "out/crop_dynamic_tasks/t01_round_priority_promotion_20261024_v3" / record["path"]), record["sha256"])

    def test_promotion_blocker_is_same_for_site_key_and_source_identity(self):
        loaded = load_profile(ROOT, self.registry, self.owner_decisions, "t01_round_priority_promotion")
        s14 = next(row for row in loaded["decoded"]["report"]["decisions"] if row["key"] == "S14")
        source_id = s14["source_id"]
        keyed = dispatch(request("cam_inspect", profile_id="t01_round_priority_promotion", site_id="S14"), root=ROOT)
        by_source = dispatch(request("cam_inspect", profile_id="t01_round_priority_promotion", site_id=source_id), root=ROOT)
        self.assertEqual(keyed["result"]["site"]["site_id"], by_source["result"]["site"]["site_id"])
        self.assertEqual(keyed["result"]["site"]["next_class_test"], by_source["result"]["site"]["next_class_test"])

    def test_owner_rejected_t01_r1_does_not_inherit_technical_pass(self):
        response = dispatch(request("cam_inspect", profile_id="t01_r1_spacing_rejected"), root=ROOT)
        self.assertEqual(response["status"], "OK")
        self.assertEqual(response["result"]["profile"]["owner_status"], "NOT_ACCEPTED_BY_OWNER")
        self.assertEqual(response["result"]["historical_run"]["technical_checks"], "PASS_WITH_SCOPE_LIMITS")
        self.assertEqual(response["result"]["historical_run"]["owner_acceptance"], "NOT_ACCEPTED")
        self.assertIn("EXACT_RUN_DIGEST_NOT_PRESENT", response["result"]["historical_run"]["fresh_verification_binding"])

    def test_plan_is_deterministic_immutable_and_non_executing(self):
        req = request("cam_plan", profile_id="t01_visual_crop_accepted")
        first = dispatch(req, root=ROOT)
        second = dispatch(req, root=ROOT)
        self.assertEqual(first, second)
        plan = first["result"]
        self.assertEqual(plan["status"], "PLANNED")
        self.assertEqual(plan["execution_status"], "NOT_RUN")
        self.assertEqual(plan["verification_status"], "NOT_RUN")
        self.assertEqual(plan["write_scope"], "none")
        self.assertEqual(plan["scope"]["kind"], "whole_registered_selection")
        self.assertEqual(plan["owner_decision_status"], "ACCEPTED_VISUAL_CROP")
        self.assertEqual(plan["execution_authorization"], "NOT_GRANTED_BY_PLAN")
        self.assertEqual(plan["bindings"]["registered_report_sha256"], self.registry["profiles"]["t01_visual_crop_accepted"]["artifacts"]["report"]["sha256"])
        changed = dispatch(request("cam_plan", profile_id="t01_visual_crop_accepted", overrides={"hard_factor": 1.6}), root=ROOT)
        self.assertEqual(changed["error"]["code"], "POLICY_CHANGE_REQUIRED")
        ignored_scope = dispatch(request("cam_plan", profile_id="t01_visual_crop_accepted", site_id="DOES_NOT_EXIST"), root=ROOT)
        self.assertEqual(ignored_scope["status"], "REJECTED")
        self.assertEqual(ignored_scope["error"]["code"], "REQUEST_FIELD_NOT_APPLICABLE")

    def test_run_and_verify_ports_are_explicitly_unavailable(self):
        for operation in ("cam_run", "cam_verify"):
            response = dispatch(request(operation), root=ROOT)
            self.assertEqual(response["status"], "NOT_RUN")
            self.assertEqual(response["result"]["reason"], "ADAPTER_NOT_QUALIFIED")

    def test_comparison_reports_policy_difference_without_equivalence_claim(self):
        response = dispatch(request("cam_compare", left_profile_id="t01_visual_crop_accepted", right_profile_id="t01_round_priority_promotion"), root=ROOT)
        self.assertEqual(response["status"], "OK")
        result = response["result"]
        self.assertTrue(result["compatibility"]["source_compatible"])
        self.assertTrue(result["compatibility"]["scene_compatible"])
        self.assertFalse(result["compatibility"]["policy_compatible"])
        self.assertEqual(result["changed_site_count"], len(result["changed_sites"]))

    def test_compare_joins_by_source_identity_not_reused_display_keys(self):
        loaded = load_profile(ROOT, self.registry, self.owner_decisions, "t01_visual_crop_accepted")
        left = copy.deepcopy(loaded)
        right = copy.deepcopy(loaded)
        a, b = right["decoded"]["report"]["decisions"][:2]
        a["source_id"], b["source_id"] = b["source_id"], a["source_id"]
        result = _compare(left, right)
        self.assertEqual(result["changed_site_count"], 2)
        self.assertEqual({item["source_id"] for item in result["changed_sites"]}, {a["source_id"], b["source_id"]})

    def test_closed_request_rejects_missing_extra_and_wrong_type_values(self):
        missing = request("cam_describe")
        del missing["site_id"]
        with self.assertRaises(ABIError):
            validate_request(missing)
        extra = request("cam_describe", approved=True)
        with self.assertRaises(ABIError):
            validate_request(extra)
        wrong = request("cam_describe", profile_id=True)
        with self.assertRaises(ABIError):
            validate_request(wrong)
        override = request("cam_inspect", overrides={"safety": 0})
        with self.assertRaises(ABIError) as caught:
            validate_request(override)
        self.assertEqual(caught.exception.code, "POLICY_CHANGE_REQUIRED")
        with self.assertRaises(ABIError) as caught:
            validate_request(request("cam_plan", profile_id="t01_visual_crop_accepted", site_id="S14"))
        self.assertEqual(caught.exception.code, "REQUEST_FIELD_NOT_APPLICABLE")
        with self.assertRaises(ABIError) as caught:
            validate_request(request("cam_describe", profile_id="t01_visual_crop_accepted"))
        self.assertEqual(caught.exception.code, "REQUEST_FIELD_NOT_APPLICABLE")
        with self.assertRaises(ABIError):
            validate_request(request("cam_inspect", profile_id=""))

    def test_pass_and_counts_require_exact_json_types(self):
        self.assertTrue(exact_pass(True))
        self.assertFalse(exact_pass("true"))
        self.assertFalse(exact_pass(1))
        self.assertTrue(exact_int(3))
        self.assertFalse(exact_int(True))

    def test_audit_pass_enum_and_counts_do_not_accept_truthy_substitutes(self):
        pid = "t01_visual_crop_accepted"
        loaded = load_profile(ROOT, self.registry, self.owner_decisions, pid)
        altered = copy.deepcopy(loaded["decoded"])
        altered["audit"]["status"] = "PASS"
        with self.assertRaises(ABIError) as caught:
            _validate_crop_run(ROOT, loaded["profile"], altered)
        self.assertEqual(caught.exception.code, "FRESH_AUDIT_NOT_PASS")
        altered = copy.deepcopy(loaded["decoded"])
        altered["audit"]["actual_adapted_later_sites"] = True
        with self.assertRaises(ABIError) as caught:
            _validate_crop_run(ROOT, loaded["profile"], altered)
        self.assertEqual(caught.exception.code, "AUDIT_COUNT_TYPE_INVALID")

    def test_site_pass_requires_present_literal_true_mandatory_checks(self):
        loaded = load_profile(ROOT, self.registry, self.owner_decisions, "t01_visual_crop_accepted")
        mandatory = "hard_gap_outside_source_attachment_ports"
        for mutation, expected in (
            (lambda checks: checks.__setitem__(mandatory, False), "SITE_VERIFICATION_STATUS_INVALID"),
            (lambda checks: checks.clear(), "SITE_VERIFICATION_CHECKS_MISSING"),
        ):
            altered = copy.deepcopy(loaded["decoded"])
            mutation(altered["report"]["decisions"][0]["verification"]["checks"])
            with self.subTest(expected=expected), self.assertRaises(ABIError) as caught:
                _validate_crop_run(ROOT, loaded["profile"], altered)
            self.assertEqual(caught.exception.code, expected)
        altered = copy.deepcopy(loaded["decoded"])
        del altered["report"]["decisions"][0]["verification"]["checks"]
        with self.assertRaises(ABIError) as caught:
            _validate_crop_run(ROOT, loaded["profile"], altered)
        self.assertEqual(caught.exception.code, "SITE_VERIFICATION_CHECKS_MISSING")

    def test_report_source_identities_must_match_registered_selection(self):
        loaded = load_profile(ROOT, self.registry, self.owner_decisions, "t01_visual_crop_accepted")
        altered = copy.deepcopy(loaded["decoded"])
        altered["report"]["decisions"][0]["source_id"] = "unregistered-source-occurrence"
        with self.assertRaises(ABIError) as caught:
            _validate_crop_run(ROOT, loaded["profile"], altered)
        self.assertEqual(caught.exception.code, "REPORT_SELECTION_IDENTITY_MISMATCH")

    def test_duplicated_report_binding_must_match_validated_artifact(self):
        loaded = load_profile(ROOT, self.registry, self.owner_decisions, "t01_visual_crop_accepted")
        profile = copy.deepcopy(loaded["profile"])
        profile["report_sha256"] = "0" * 64
        with self.assertRaises(ABIError) as caught:
            _validate_crop_run(ROOT, profile, loaded["decoded"])
        self.assertEqual(caught.exception.code, "RUN_REPORT_ALIAS_MISMATCH")

    def test_diagnostic_geometry_missing_or_tampered_blocks_successful_inspection(self):
        for damage, expected_status, expected_code in (
            ("tamper", "FAIL", "DIAGNOSTIC_GEOMETRY_HASH_MISMATCH"),
            ("delete", "NOT_RUN", "DIAGNOSTIC_GEOMETRY_MISSING"),
        ):
            temp, root, registry = self._temporary_profile_root("t01_round_priority_promotion")
            try:
                profile = registry["profiles"]["t01_round_priority_promotion"]
                diagnostic = root / profile["artifact_dir"] / "round_diagnostics/S14_circle.wkb"
                if damage == "tamper":
                    diagnostic.write_bytes(diagnostic.read_bytes() + b"tamper")
                else:
                    diagnostic.unlink()
                with patch("src.agent_abi.service.load_registry", return_value=(registry, self.owner_decisions)):
                    response = dispatch(request("cam_inspect", profile_id="t01_round_priority_promotion", site_id="S14"), root=root)
                self.assertEqual(response["status"], expected_status)
                self.assertEqual(response["error"]["code"], expected_code)
                self.assertIsNone(response["result"])
            finally:
                temp.cleanup()

    def test_diagnostic_geometry_path_must_remain_inside_registered_run(self):
        loaded = load_profile(ROOT, self.registry, self.owner_decisions, "t01_round_priority_promotion")
        altered = copy.deepcopy(loaded["decoded"])
        altered["audit"]["round_next_class_controls"][0]["geometry"]["circle"]["path"] = "../../outside.wkb"
        with self.assertRaises(ABIError) as caught:
            _validate_crop_run(ROOT, loaded["profile"], altered)
        self.assertEqual(caught.exception.code, "DIAGNOSTIC_GEOMETRY_PATH_INVALID")

    def test_historical_pass_must_agree_with_run_and_verifier_evidence(self):
        loaded = load_profile(ROOT, self.registry, self.owner_decisions, "t01_r1_spacing_rejected")
        altered = copy.deepcopy(loaded["decoded"])
        altered["fresh_verification"]["status"] = "FAIL"
        with self.assertRaises(ABIError) as caught:
            _validate_historical_r1(loaded["profile"], loaded["decision"], altered)
        self.assertEqual(caught.exception.code, "HISTORICAL_TECHNICAL_STATUS_MISMATCH")
        altered = copy.deepcopy(loaded["decoded"])
        altered["fresh_verification"]["checks"] = []
        with self.assertRaises(ABIError) as caught:
            _validate_historical_r1(loaded["profile"], loaded["decision"], altered)
        self.assertEqual(caught.exception.code, "HISTORICAL_PASS_CHECK_MISMATCH")
        altered = copy.deepcopy(loaded["decoded"])
        altered["run"]["status"]["technical_checks"] = "FAIL"
        altered["fresh_verification"]["status"] = "FAIL"
        with self.assertRaises(ABIError) as caught:
            _validate_historical_r1(loaded["profile"], loaded["decision"], altered)
        self.assertEqual(caught.exception.code, "HISTORICAL_TECHNICAL_STATUS_MISMATCH")

    def _temporary_profile_root(self, profile_id: str, *, omit_audit: bool = False, mutate_candidate: bool = False):
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        registry = copy.deepcopy(self.registry)
        profile = registry["profiles"][profile_id]
        source = ROOT / profile["source"]["path"]
        source_target = root / profile["source"]["path"]
        source_target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, source_target)
        run_dir = root / "out/abi_test" / profile_id
        run_dir.mkdir(parents=True)
        old_run_dir = ROOT / profile["artifact_dir"]
        profile["artifact_dir"] = str(run_dir.relative_to(root))
        for name, spec in list(profile["artifacts"].items()):
            if omit_audit and name == "audit":
                spec["path"] = str((run_dir / "fresh_audit.json").relative_to(root))
                continue
            old_path = ROOT / spec["path"]
            target = run_dir / old_path.name
            shutil.copy2(old_path, target)
            spec["path"] = str(target.relative_to(root))
        profile["scene"]["path"] = profile["artifacts"]["scene"]["path"]
        for subdir in ("geometry", "round_diagnostics"):
            source_dir = old_run_dir / subdir
            if source_dir.is_dir():
                shutil.copytree(source_dir, run_dir / subdir)
        if mutate_candidate:
            report = json.loads((run_dir / "report.json").read_text())
            for row in report["decisions"]:
                rel = row["geometry"]["dynamic"]
                source_geom = old_run_dir / rel
                target_geom = run_dir / rel
                if not target_geom.exists():
                    target_geom.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source_geom, target_geom)
            victim = run_dir / report["decisions"][-1]["geometry"]["dynamic"]
            victim.write_bytes(victim.read_bytes() + b"tamper")
        return temp, root, registry

    def test_missing_audit_returns_not_run_never_pass(self):
        temp, root, registry = self._temporary_profile_root("t01_visual_crop_accepted", omit_audit=True)
        try:
            with patch("src.agent_abi.service.load_registry", return_value=(registry, self.owner_decisions)):
                response = dispatch(request("cam_inspect", profile_id="t01_visual_crop_accepted"), root=root)
            self.assertEqual(response["status"], "NOT_RUN")
            self.assertEqual(response["error"]["code"], "ARTIFACT_MISSING")
            self.assertIsNone(response["result"])
        finally:
            temp.cleanup()

    def test_corrupted_unrelated_site_candidate_cannot_inherit_run_pass(self):
        temp, root, registry = self._temporary_profile_root("t01_visual_crop_accepted", mutate_candidate=True)
        try:
            with patch("src.agent_abi.service.load_registry", return_value=(registry, self.owner_decisions)):
                response = dispatch(request("cam_inspect", profile_id="t01_visual_crop_accepted"), root=root)
            self.assertEqual(response["status"], "FAIL")
            self.assertEqual(response["error"]["code"], "SITE_CANDIDATE_HASH_MISMATCH")
            self.assertIsNone(response["result"])
        finally:
            temp.cleanup()

    def test_json_schemas_are_valid_and_request_is_closed(self):
        import jsonschema
        request_schema = json.loads((ROOT / "contracts/agent_abi/v0_1/request.schema.json").read_text())
        response_schema = json.loads((ROOT / "contracts/agent_abi/v0_1/response.schema.json").read_text())
        projection = json.loads((ROOT / "contracts/agent_abi/v0_1/tool_projection.json").read_text())
        jsonschema.Draft202012Validator.check_schema(request_schema)
        jsonschema.Draft202012Validator.check_schema(response_schema)
        self.assertEqual(len(projection["tools"]), 7)
        for tool in projection["tools"]:
            jsonschema.Draft202012Validator.check_schema(tool["input_schema"])
            self.assertEqual(tool["input_schema"]["properties"]["operation"]["const"], tool["name"])
            valid_tool_request = request(tool["name"])
            if tool["name"] in {"cam_inspect", "cam_plan", "cam_review"}:
                valid_tool_request["profile_id"] = "t01_visual_crop_accepted"
            elif tool["name"] == "cam_compare":
                valid_tool_request["left_profile_id"] = "t01_visual_crop_accepted"
                valid_tool_request["right_profile_id"] = "t01_round_priority_promotion"
            jsonschema.validate(valid_tool_request, tool["input_schema"])
            applicable = {
                "cam_describe": set(), "cam_inspect": {"profile_id", "site_id"},
                "cam_plan": {"profile_id"}, "cam_run": {"profile_id"},
                "cam_verify": {"profile_id"}, "cam_compare": {"left_profile_id", "right_profile_id"},
                "cam_review": {"profile_id"},
            }[tool["name"]]
            unused = next(name for name in ("profile_id", "site_id", "left_profile_id", "right_profile_id") if name not in applicable)
            invalid_tool_request = copy.deepcopy(valid_tool_request)
            invalid_tool_request[unused] = "OUT_OF_SCOPE"
            with self.assertRaises(jsonschema.ValidationError):
                jsonschema.validate(invalid_tool_request, tool["input_schema"])
        valid = request("cam_describe")
        jsonschema.validate(valid, request_schema)
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate({**valid, "approved": True}, request_schema)
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(request("cam_plan", profile_id="t01_visual_crop_accepted", site_id="DOES_NOT_EXIST"), request_schema)
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(request("cam_describe", profile_id="t01_visual_crop_accepted"), request_schema)
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(request("cam_inspect", profile_id=None), request_schema)

        jsonschema.Draft202012Validator.check_schema(response_schema)
        responses = [
            dispatch(request("cam_describe"), root=ROOT),
            dispatch(request("cam_inspect", profile_id="t01_visual_crop_accepted"), root=ROOT),
            dispatch(request("cam_plan", profile_id="t01_visual_crop_accepted"), root=ROOT),
            dispatch(request("cam_run"), root=ROOT),
            dispatch(request("cam_verify"), root=ROOT),
            dispatch(request("cam_compare", left_profile_id="t01_visual_crop_accepted", right_profile_id="t01_round_priority_promotion"), root=ROOT),
            dispatch(request("cam_review", profile_id="t01_visual_crop_accepted"), root=ROOT),
            dispatch(request("cam_inspect", profile_id=None), root=ROOT),
        ]
        for response in responses:
            jsonschema.validate(response, response_schema)
        invalid_success = {**responses[0], "result": None}
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(invalid_success, response_schema)
        invalid_plan = dispatch(request("cam_plan", profile_id="t01_visual_crop_accepted"), root=ROOT)
        invalid_plan["result"] = {"status": "PLANNED"}
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(invalid_plan, response_schema)

    def test_local_cli_is_one_json_request_one_json_response(self):
        command = [str(ROOT / ".venv/bin/python"), str(ROOT / "tools/cam_agent_abi.py")]
        completed = subprocess.run(command, cwd=ROOT, input=json.dumps(request("cam_describe")), text=True, capture_output=True, check=True)
        response = json.loads(completed.stdout)
        self.assertEqual(response["operation"], "cam_describe")
        self.assertEqual(response["status"], "OK")
        self.assertEqual(completed.stderr, "")


if __name__ == "__main__":
    unittest.main()
