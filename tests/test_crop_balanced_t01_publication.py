"""Negative publication gates must fail before displaying a successful crop."""
import hashlib,json,tempfile,unittest
from pathlib import Path
from tools import render_crop_balanced_t01 as renderer


class CropPublicationTests(unittest.TestCase):
    def setUp(self):
        self.scratch=tempfile.TemporaryDirectory(dir=renderer.ROOT/'out');self.addCleanup(self.scratch.cleanup);self.out=Path(self.scratch.name)
        policy=(renderer.ROOT/'contracts/crop_balanced_t01_policy.json').read_bytes();p=json.loads(policy)
        (self.out/'policy.json').write_bytes(policy);(self.out/'selection.json').write_text('{}\n')
        self.report={'policy_sha256':hashlib.sha256(policy).hexdigest(),'source_sha256':p['source_sha256'],'selection_sha256':renderer.sha(self.out/'selection.json'),'same_policy_replay_equal':True,'unique_sites':51,'source_occurrences':53,'geometry_sha256':{}}
        (self.out/'report.json').write_text(json.dumps(self.report))
        self.audit={'status':'PASS_SCOPED_FRESH_CROP_AUDIT','report_sha256':renderer.sha(self.out/'report.json'),'dynamic_cases':[{'violations':[]} for _ in range(51)]}

    def write_audit(self):
        (self.out/'fresh_audit.json').write_text(json.dumps(self.audit))

    def test_missing_failed_and_stale_audits_cannot_publish(self):
        with self.assertRaises(FileNotFoundError):renderer.publish(self.out)
        for mutation in ['failed','stale']:
            self.audit['status']='FAIL' if mutation=='failed' else 'PASS_SCOPED_FRESH_CROP_AUDIT'
            self.audit['report_sha256']='0'*64 if mutation=='stale' else renderer.sha(self.out/'report.json')
            self.write_audit()
            with self.assertRaises(AssertionError):renderer.publish(self.out)
        self.assertFalse((self.out/'index.html').exists())

    def test_incomplete_or_violating_population_cannot_publish(self):
        for cases in [[{'violations':[]} for _ in range(50)],[{'violations':['gap failure']},*[{'violations':[]} for _ in range(50)]]]:
            self.audit['dynamic_cases']=cases;self.write_audit()
            with self.assertRaises(AssertionError):renderer.publish(self.out)
        self.assertFalse((self.out/'index.html').exists())

    def test_missing_bound_geometry_cannot_publish_even_with_true_audit_fields(self):
        self.write_audit()
        with self.assertRaises(KeyError):renderer.publish(self.out)
        self.assertFalse((self.out/'index.html').exists())

if __name__=='__main__':unittest.main()
