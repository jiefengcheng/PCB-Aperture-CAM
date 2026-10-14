"""Source edits during generation cannot produce a verified artifact."""
import contextlib
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from tests.local_scratch import temporary_directory
from tools import visual_report

class VisualSourceGuardTests(unittest.TestCase):
    def test_mid_generation_source_edit_is_explicitly_unverified(self):
        with temporary_directory() as d:
            root=Path(d);(root/'out/visual').mkdir(parents=True);(root/'contracts').mkdir()
            (root/'contracts/visual_inputs_v1.json').write_text('{}')
            paths=['src/visual_scene.py','tools/visual_report.py','web/workbench.html','web/workbench.js','web/replay_model.js','web/pipeline_views.js','web/backend_model.js','src/pipeline_scene.py','src/evidence_records.py']
            for name in paths:
                p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('/* captured source */')
            (root/'web/workbench.html').write_text('<meta name="scene-sha256" content="__DIGEST__"><script id="scene-data">__SCENE__</script><script>__APP__</script>')
            def changed(manifest,out):
                (root/'web/workbench.js').write_text('/* changed source */')
                return {'integrity':'VERIFIED_AT_GENERATION','cases':[],'provenance':[]}
            with patch.object(visual_report,'ROOT',root),patch.object(visual_report,'build_scene',side_effect=changed),patch('src.evidence_records.add_record_pages'),patch.object(visual_report.subprocess,'check_output',return_value='test-head'),patch.object(sys,'argv',['visual_report']),contextlib.redirect_stdout(io.StringIO()):
                self.assertTrue(visual_report.main())
            run=next((root/'out/visual').iterdir());receipt=json.loads((run/'build_receipt.json').read_text());scene=json.loads((run/'scene.json').read_text())
            self.assertEqual(receipt['status'],'UNVERIFIED');self.assertFalse(receipt['source_stable_during_generation'])
            self.assertEqual(scene['integrity'],'STALE_UNVERIFIED')
            self.assertIn('source changed',scene['error'])
            self.assertNotIn('changed source',(run/'index.html').read_text())
