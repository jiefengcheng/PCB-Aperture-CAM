"""Controls for deterministic scope and atomic rejection, not Gerber substitutes."""
from pathlib import Path
import copy,json,tempfile,unittest
from src.v2_executor import ROOT,plan,execute,sha
from src.v2_discovery import discover

class V2Executor(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract=json.loads((ROOT/'contracts/v2_move_pad.json').read_text());cls.source=ROOT/cls.contract['source'];cls.text=cls.source.read_text()
        (ROOT/'out/v2/unit_tests').mkdir(parents=True,exist_ok=True)
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=ROOT/'out/v2/unit_tests');self.base=Path(self.tmp.name)
    def tearDown(self):self.tmp.cleanup()
    def okexport(self,board,stage):return stage
    def okvalidation(self,output):
        return {'overall':'PASS','checks':[{'id':k,'mandatory':True,'status':'PASS'} for k in self.contract['required_validation_checks']]}
    def test_compute_without_candidate_input_and_protected_text(self):
        a,p=plan(self.text,self.contract);b,q=plan(self.text,self.contract)
        self.assertEqual(a,b);self.assertEqual(p,q);self.assertEqual(p['computed_center_mm'],[20.05,20.0]);self.assertEqual(len(p['write_set']),4)
        self.assertEqual(a,(ROOT/'assets/starter/fixtures/candidate/kicad/coupon.kicad_pcb').read_text())
        changed=[(l,r) for l,r in zip(self.text.splitlines(),a.splitlines()) if l!=r]
        self.assertEqual(len(changed),4)
        for uid in p['protected']:
            self.assertEqual([l for l in self.text.splitlines() if uid in l],[l for l in a.splitlines() if uid in l])
    def test_legacy_discovery_includes_pad_and_context_is_not_write_set(self):
        _,p=plan(self.text,self.contract)
        self.assertEqual(p['pcb_Z_qualification']['legacy_layer_items'],5);self.assertEqual(p['pcb_Z_qualification']['adapter_added_pads'],4)
        self.assertEqual(len(p['connected_context']),6);self.assertEqual(len(p['read_only_obstacles']),3)
        self.assertEqual(set(p['connected_context'])-set(p['write_set']),{'ea0071af-1b1a-5f00-b94d-a094b4cb7bda','0b757436-b9bf-53d1-bc3a-4f33f834f4ef'})
    def test_wrong_source_and_target_rejected(self):
        with self.assertRaisesRegex(ValueError,'revision mismatch'):plan(self.text+'\n',self.contract)
        m=copy.deepcopy(self.contract);m['target']='1efd0f0a-2e44-5d07-96e8-4e9d47cc8b9b'
        with self.assertRaisesRegex(ValueError,'target'):plan(self.text,m)
    def test_legacy_duplicate_id_and_missing_pad_rejected(self):
        duplicate=self.text.replace('ea0071af-1b1a-5f00-b94d-a094b4cb7bda',self.contract['target'])
        with self.assertRaisesRegex(ValueError,'duplicate'):discover(duplicate,self.contract)
        m=copy.deepcopy(self.contract);m['pcb_Z_source_sha256']['import_pcb.py']='0'*64
        with self.assertRaisesRegex(ValueError,'pcb_Z source changed'):discover(self.text,m)
    def test_wrong_dependency_or_policy_hash_rejected(self):
        m=copy.deepcopy(self.contract);m['dependents'][2]='0b757436-b9bf-53d1-bc3a-4f33f834f4ef'
        with self.assertRaisesRegex(ValueError,'route'):plan(self.text,m)
        m=copy.deepcopy(self.contract);m['policy_sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'custody'):plan(self.text,m)
    def test_infeasible_overlap_and_movement_budget_rejected(self):
        import hashlib
        policy=json.loads((ROOT/self.contract['policy']).read_text())
        for name,key,value,message in [('movement','maximum_pad_move_mm',.1,'movement budget'),('overlap','minimum_overlap_mm',1.0,'unsatisfiable')]:
            changed={**policy,key:value};path=self.base/(name+'.json');path.write_text(json.dumps(changed))
            m=copy.deepcopy(self.contract);m['policy']=str(path);m['policy_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
            with self.assertRaisesRegex(ValueError,message):plan(self.text,m)
    def test_failure_and_unknown_never_publish(self):
        for status in ('FAIL','NOT_ESTABLISHED','NOT_RUN'):
            r=execute(self.source,self.contract,self.base/status,self.okexport,lambda o:{'overall':status,'checks':[]})
            self.assertEqual(r['state'],'REJECTED');self.assertTrue(r['source_unchanged']);self.assertFalse((self.base/status/'accepted').exists())
        r=execute(self.source,self.contract,self.base/'incomplete',self.okexport,lambda o:{'overall':'PASS','checks':[]})
        self.assertEqual(r['state'],'REJECTED')
    def test_stage_and_export_faults_preserve_previous_acceptance(self):
        prior=self.base/'previous';r=execute(self.source,self.contract,prior,self.okexport,self.okvalidation);self.assertEqual(r['state'],'COMMITTED');old=sha(Path(r['accepted']))
        for phase in ('PLANNED','STAGED','EXPORTED','VALIDATED'):
            def fault(name,ws):
                if name==phase:raise OSError('injected '+phase)
            ws=self.base/phase;r=execute(self.source,self.contract,ws,self.okexport,self.okvalidation,fault)
            self.assertEqual(r['state'],'REJECTED');self.assertTrue(r['source_unchanged']);self.assertFalse((ws/'accepted').exists());self.assertEqual(sha(prior/'accepted/coupon.kicad_pcb'),old)
        def export_failure(board,stage):raise RuntimeError('injected tool failure')
        r=execute(self.source,self.contract,self.base/'tool',export_failure,self.okvalidation)
        self.assertEqual(r['state'],'REJECTED')
    def test_changed_protected_candidate_cannot_publish(self):
        def tamper(phase,ws):
            if phase=='STAGED':
                p=ws/'staging/coupon.kicad_pcb';p.write_text(p.read_text().replace('(at 3.000000 0.000000)','(at 3.300000 0.000000)'))
        r=execute(self.source,self.contract,self.base/'tamper',self.okexport,self.okvalidation,tamper)
        self.assertEqual(r['state'],'REJECTED');self.assertIn('changed before export',r['reason'])
    def test_validation_or_postvalidation_tamper_rejected(self):
        def tamper(output):
            p=output/'coupon.kicad_pcb';p.write_text(p.read_text()+'\n');return self.okvalidation(output)
        r=execute(self.source,self.contract,self.base/'validation_tamper',self.okexport,tamper)
        self.assertEqual(r['state'],'REJECTED')
        def last_hook(phase,ws):
            if phase=='VALIDATED':
                p=ws/'staging/coupon.kicad_pcb';p.write_text(p.read_text()+'\n')
        r=execute(self.source,self.contract,self.base/'last',self.okexport,self.okvalidation,last_hook)
        self.assertEqual(r['state'],'REJECTED')
    def test_replay_workspace_collision_and_reapply_refusal(self):
        ws=self.base/'one';r=execute(self.source,self.contract,ws,self.okexport,self.okvalidation)
        with self.assertRaisesRegex(ValueError,'already exists'):execute(self.source,self.contract,ws,self.okexport,self.okvalidation)
        with self.assertRaisesRegex(ValueError,'revision mismatch'):plan(Path(r['accepted']).read_text(),self.contract)
        with self.assertRaisesRegex(ValueError,'outside V2'):execute(self.source,self.contract,ROOT/'out/not_v2',self.okexport,self.okvalidation)
