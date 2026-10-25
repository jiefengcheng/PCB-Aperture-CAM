"""Reject positive presentation of failed or incomplete square-mechanism runs."""
import contextlib
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import audit_crop_square_neighbor_experiment as auditor
from tools import run_crop_square_neighbor_experiment as runner


class SquareNeighborPublicationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=runner.ROOT/"out")
        self.directory = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)

    def test_failed_empty_and_incomplete_reports_never_publish_a_positive_page(self):
        complete_checks = dict.fromkeys(runner.REQUIRED_EXECUTION_CHECKS, True)
        partial_checks = dict(complete_checks)
        partial_checks.pop("assembled_actual_copper_constraints")
        false_checks = {**complete_checks, "assembled_actual_copper_constraints": False}
        nonboolean_checks = {**complete_checks, "assembled_actual_copper_constraints": "PASS"}
        reports = [
            {},
            {"status": "FAIL", "checks": {}},
            {"status": "MECHANISM_DEMONSTRATION_SIZE_NOT_QUALIFIED", "checks": {}, "causal_actual_source_events": 1},
            {"status": "MECHANISM_DEMONSTRATION_SIZE_NOT_QUALIFIED", "checks": partial_checks, "causal_actual_source_events": 1},
            {"status": "MECHANISM_DEMONSTRATION_SIZE_NOT_QUALIFIED", "checks": false_checks, "causal_actual_source_events": 1},
            {"status": "MECHANISM_DEMONSTRATION_SIZE_NOT_QUALIFIED", "checks": nonboolean_checks, "causal_actual_source_events": 1},
            {"status": "MECHANISM_DEMONSTRATION_SIZE_NOT_QUALIFIED", "checks": complete_checks, "causal_actual_source_events": 0},
        ]
        with patch.object(runner, "OUT", self.directory):
            for report in reports:
                with self.subTest(report=report):
                    # Deliberately no workbench geometry is available.
                    runner.gallery(None, None, None, None, None, None, report)
                    page = (self.directory/"index.html").read_text()
                    self.assertIn("Mechanism not established for this run", page)
                    self.assertNotIn("MECHANISM_DEMONSTRATION — SIZE_NOT_QUALIFIED", page)
                    self.assertNotIn("The square now changes", page)
                    self.assertFalse(list(self.directory.glob("step_*.svg")))

    def test_failed_execution_status_cannot_be_overridden_by_all_true_checks(self):
        report = {"status": "MECHANISM_NOT_ESTABLISHED",
                  "checks": dict.fromkeys(runner.REQUIRED_EXECUTION_CHECKS, True),
                  "causal_actual_source_events": 1}
        self.assertTrue(runner.positive_gallery_issues(report))

    def test_true_check_fields_without_bound_evidence_do_not_publish_success(self):
        report = {"status": "MECHANISM_DEMONSTRATION_SIZE_NOT_QUALIFIED",
                  "checks": dict.fromkeys(runner.REQUIRED_EXECUTION_CHECKS, True),
                  "causal_actual_source_events": 1}
        self.assertFalse(runner.positive_gallery_issues(report))
        with patch.object(runner, "OUT", self.directory):
            self.assertFalse(runner.gallery(None, None, None, None, None, None, report))
        text = (self.directory/"index.html").read_text()
        self.assertIn("Mechanism not established", text)
        self.assertNotIn("The square now changes", text)

    def test_interrupted_page_replacement_cannot_publish_partial_html(self):
        page = self.directory/"index.html"
        page.write_text("complete previous page")
        with patch.object(runner, "OUT", self.directory), \
             patch.object(Path, "replace", side_effect=OSError("interrupted before atomic replace")):
            with self.assertRaises(OSError):
                runner.write_landing_page("complete new page")
        self.assertEqual(page.read_text(), "complete previous page")

    def test_no_qualifying_pair_replaces_stale_success_page_and_exits_nonzero(self):
        policy = (runner.OUT/"policy.json").read_bytes()
        (self.directory/"policy.json").write_bytes(policy)
        (self.directory/"index.html").write_text("The square now changes the neighbor-facing copper")
        inv = {"source_sha256": json.loads(policy)["source_sha256"]}
        with patch.object(runner, "OUT", self.directory), \
             patch.object(runner, "source_scene", return_value=(inv, [], [], None, [])), \
             contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit) as raised:
                runner.main()
        self.assertEqual(raised.exception.code, 1)
        self.assertIn("Mechanism not established", (self.directory/"index.html").read_text())
        self.assertNotIn("The square now changes", (self.directory/"index.html").read_text())
        report = json.loads((self.directory/"report.json").read_bytes())
        self.assertEqual(report["status"], "NO_QUALIFYING_SQUARE_AWARE_INTERACTION_WITHIN_DECLARED_RANGE")

    def test_historical_source_binding_requires_exact_snapshot_hash(self):
        root = self.directory
        bundle = root/"out"/"bundle"
        relative = "tools/runner.py"
        current = root/relative
        snapshot = bundle/"review_source"/relative
        current.parent.mkdir(parents=True)
        snapshot.parent.mkdir(parents=True)
        current.write_bytes(b"later implementation")
        snapshot.write_bytes(b"executed implementation")
        expected = hashlib.sha256(snapshot.read_bytes()).hexdigest()
        with patch.object(auditor, "ROOT", root), patch.object(auditor, "OUT", bundle):
            self.assertEqual(auditor.bound_source_path(relative, expected), snapshot)
            snapshot.write_bytes(b"corrupted snapshot")
            with self.assertRaisesRegex(AssertionError, "BOUND_IMPLEMENTATION_UNAVAILABLE"):
                auditor.bound_source_path(relative, expected)

    def test_existing_execution_and_publication_are_never_overwritten(self):
        report = self.directory/"report.json"
        page = self.directory/"index.html"
        report.write_bytes(b"frozen execution")
        page.write_bytes(b"frozen publication")
        with patch.object(runner, "OUT", self.directory):
            with self.assertRaisesRegex(SystemExit, "EXISTING_EVIDENCE_RETAINED"):
                runner.main()
            with self.assertRaisesRegex(SystemExit, "EXISTING_EVIDENCE_RETAINED"):
                runner.main(self.directory)
        self.assertEqual(report.read_bytes(), b"frozen execution")
        self.assertEqual(page.read_bytes(), b"frozen publication")


if __name__ == "__main__":
    unittest.main()
