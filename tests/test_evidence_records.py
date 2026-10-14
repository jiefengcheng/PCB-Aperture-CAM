import unittest
from src.evidence_records import resolve_pointer
class EvidencePointerTests(unittest.TestCase):
    def test_rfc6901_keys_and_arrays(self):
        data={'a/b':{'~key':[{'status':'FAIL'}]}}
        self.assertEqual(resolve_pointer(data,'/a~1b/~0key/0/status'),'FAIL')
        self.assertIs(resolve_pointer(data,''),data)
    def test_missing_and_invalid_are_errors(self):
        with self.assertRaises(KeyError):resolve_pointer({},'/missing')
        for p in ['/01','/-1','bad']:
            with self.subTest(pointer=p),self.assertRaises(ValueError):resolve_pointer([1],p)
