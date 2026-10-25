"""The revised six-case publication must reject incomplete or tampered evidence."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from tools import run_crop_square_rotated_priority as runner


class RotatedPublicationTests(unittest.TestCase):
    def setUp(self):
        self.scratch=tempfile.TemporaryDirectory(dir=runner.ROOT/'out')
        self.addCleanup(self.scratch.cleanup)
        self.out=Path(self.scratch.name)/'bundle'
        shutil.copytree(runner.DEFAULT_OUT,self.out)

    def test_missing_check_and_boolean_event_cannot_publish(self):
        report=json.loads((self.out/'report.json').read_bytes())
        for mutation in ('missing_check','boolean_event'):
            changed=json.loads(json.dumps(report))
            if mutation=='missing_check':
                changed['checks'].pop(next(iter(changed['checks'])))
            else:
                changed['causal_actual_source_events']=True
            runner.dump(self.out/'report.json',changed)
            with self.assertRaises(AssertionError):
                runner.publish(self.out)

    def test_tampered_contour_and_stale_audit_cannot_publish(self):
        path=self.out/'b_accepted.wkb'
        original=path.read_bytes()
        path.write_bytes((self.out/'b_core.wkb').read_bytes())
        with self.assertRaises(AssertionError):
            runner.publish(self.out)
        path.write_bytes(original)
        audit=json.loads((self.out/'local_full_inventory_audit.json').read_bytes())
        audit['report_sha256']='0'*64
        runner.dump(self.out/'local_full_inventory_audit.json',audit)
        with self.assertRaises(AssertionError):
            runner.publish(self.out)

    def test_missing_audit_or_reused_output_is_rejected(self):
        (self.out/'local_full_inventory_audit.json').unlink()
        with self.assertRaises(FileNotFoundError):
            runner.publish(self.out)
        with self.assertRaises(ValueError):
            runner.main(self.out)


if __name__=='__main__':
    unittest.main()
