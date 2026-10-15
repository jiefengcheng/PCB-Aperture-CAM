"""Replay must not combine a stored PASS with changed input or candidate bytes."""
import json
import unittest
from pathlib import Path
from tests.local_scratch import temporary_directory
from tools.client_visual_demo import verify_operation_evidence,sha

class ClientReplayIntegrityTests(unittest.TestCase):
    def fixture(self,root):
        source=root/'source';run=root/'run';source.mkdir();(run/'accepted').mkdir(parents=True)
        for name in ['vme-wren-Bottom Layer.gbr','vme-wren-Bottom Solder.gbr']:
            (source/name).write_text(name)
        (run/'controlled_before.gbr').write_text('controlled')
        (run/'accepted/candidate.gbr').write_text('accepted')
        contract={'source_sha256':sha(source/'vme-wren-Bottom Layer.gbr'),'mask_sha256':sha(source/'vme-wren-Bottom Solder.gbr'),'input_sha256':sha(run/'controlled_before.gbr')}
        (run/'contract.json').write_text(json.dumps(contract))
        positive={'status':'PASS','candidate_sha256':sha(run/'accepted/candidate.gbr')}
        (run/'accepted/validation.json').write_text(json.dumps(positive))
        result={'status':'PASS','contract_sha256':sha(run/'contract.json'),'source_sha256':{p.name:sha(p) for p in source.iterdir()},'positive':positive,'controls':{}}
        return source,run,result,contract

    def test_changed_source_or_candidate_rejected(self):
        for kind in ['source','candidate','validation']:
            with self.subTest(kind=kind),temporary_directory() as d:
                source,run,result,contract=self.fixture(Path(d))
                verify_operation_evidence(source,run,result,contract)
                path={'source':source/'vme-wren-Bottom Layer.gbr','candidate':run/'accepted/candidate.gbr','validation':run/'accepted/validation.json'}[kind]
                path.write_text('{}')
                with self.assertRaises(RuntimeError):verify_operation_evidence(source,run,result,contract)

    def test_changed_control_receipt_rejected(self):
        with temporary_directory() as d:
            source,run,result,contract=self.fixture(Path(d));control=run/'open';control.mkdir()
            (control/'candidate.gbr').write_text('open');(control/'validation.json').write_text('{}')
            result['controls']['open']={'candidate_sha256':sha(control/'candidate.gbr'),'report_sha256':sha(control/'validation.json')}
            verify_operation_evidence(source,run,result,contract)
            (control/'validation.json').write_text('{"changed":true}')
            with self.assertRaises(RuntimeError):verify_operation_evidence(source,run,result,contract)
