import copy,json,unittest
from pathlib import Path
from src.source_aware import evaluate,electrical_status
ROOT=Path(__file__).resolve().parents[1]
class SourceAwareTests(unittest.TestCase):
    def setUp(self):
        self.m=json.loads((ROOT/'contracts/source_aware_v1.json').read_text())
        self.r=json.loads((ROOT/self.m['baseline_report']).read_text())
    def test_positive_and_original_unknown(self):
        result=evaluate(self.r,self.m)
        self.assertEqual(result['status'],'PASS')
        self.assertEqual(result['original_overall'],'NOT_ESTABLISHED')
    def test_missing_intent_never_passes(self):
        for ts in ([],[{'net':None}],[{'net':''}],[{'net':'GND'},{'net':None}]):
            self.assertEqual(electrical_status(ts,'PASS'),'NOT_ESTABLISHED')
        self.assertEqual(electrical_status([{'net':'GND'}],'PASS'),'PASS')
        self.assertEqual(electrical_status([{'net':'GND'}],'FAIL'),'FAIL')
    def test_false_electrical_pass_rejected(self):
        self.r['boards']['GlowStitch']['electrical_profile']='PASS'
        self.assertEqual(evaluate(self.r,self.m)['status'],'FAIL')
    def test_missing_or_bad_required_checks_rejected(self):
        for field in ('layers','anchors','physical_connections','faults','source_terminals','intent'):
            r=copy.deepcopy(self.r);r['boards']['HALPI2-HDMI-FPC'].pop(field)
            self.assertEqual(evaluate(r,self.m)['status'],'FAIL',field)
        r=copy.deepcopy(self.r);r['boards']['GlowStitch']['layers']['F.Cu']['replay']['status']='FAIL'
        self.assertEqual(evaluate(r,self.m)['status'],'FAIL')
    def test_duplicate_identity_rejected(self):
        ts=self.r['boards']['GlowStitch']['source_terminals'];ts[1]=copy.deepcopy(ts[0])
        self.assertEqual(evaluate(self.r,self.m)['status'],'FAIL')
    def test_policy_not_fixture_name(self):
        r=copy.deepcopy(self.r);m=copy.deepcopy(self.m)
        r['boards']['renamed']=r['boards'].pop('GlowStitch');m['fixtures']['renamed']=m['fixtures'].pop('GlowStitch')
        self.assertEqual(evaluate(r,m)['status'],'PASS')
