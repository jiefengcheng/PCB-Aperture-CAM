from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import build_arc_attribution_sweep as builder
from tools import evaluate_arc_attribution_sweep as evaluator


class ArcAttributionSweepTests(unittest.TestCase):
    def test_source_pair_must_differ_by_only_the_serialized_target_arc(self):
        target = {
            "start": [30.0, 20.0],
            "mid": [30.001, 20.0],
            "end": [30.002, 20.0],
            "width": 0.08,
        }
        scenario = {"id": "case", "target": target}
        baseline_text = "(kicad_pcb\n (segment (width 0.1))\n)\n"
        arc = builder.serialize_target("case:target", target)
        treated_text = baseline_text[:-2] + arc + ")\n"
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            baseline = root / "without.kicad_pcb"
            treated = root / "with.kicad_pcb"
            baseline.write_text(baseline_text)
            treated.write_text(treated_text)
            case = {
                "scenario": scenario,
                "source_pair": {
                    "without_target": {"path": "without.kicad_pcb", "sha256": evaluator.sha(baseline)},
                    "with_target": {"path": "with.kicad_pcb", "sha256": evaluator.sha(treated)},
                },
            }
            with patch.object(evaluator, "ROOT", root):
                checked = evaluator.verify_pair_source(root, case)
                self.assertTrue(checked["target_only_byte_delta"])
                treated.write_text(treated_text.replace("(segment (width 0.1))", "(segment (width 0.2))"))
                case["source_pair"]["with_target"]["sha256"] = evaluator.sha(treated)
                with self.assertRaises(SystemExit):
                    evaluator.verify_pair_source(root, case)

    def test_normalized_plot_hash_ignores_only_kicad_timestamp_metadata(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            a, b, c = root / "a.gbr", root / "b.gbr", root / "c.gbr"
            a.write_text("%TF.CreationDate,2026-01-01*%\nG04 Created by KiCad (PCBNEW) 10.99*\nD10*\nX001Y002D02*\n")
            b.write_text("%TF.CreationDate,2026-01-02*%\nG04 Created by KiCad (PCBNEW) 10.99*\nD10*\nX001Y002D02*\n")
            c.write_text("%TF.CreationDate,2026-01-02*%\nG04 Created by KiCad (PCBNEW) 10.99*\nD10*\nX001Y003D02*\n")
            self.assertEqual(evaluator.normalized_plot_hash(a), evaluator.normalized_plot_hash(b))
            self.assertNotEqual(evaluator.normalized_plot_hash(a), evaluator.normalized_plot_hash(c))


if __name__ == "__main__":
    unittest.main()
