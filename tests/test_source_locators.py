import unittest
from src.source_locators import locate,LocatorError

class SourceLocatorTests(unittest.TestCase):
    def test_nested_occurrences_and_exact_original_bytes(self):
        raw=b'(kicad_pcb\n (footprint "x" (pad "1" (uuid repeated)))\n (footprint "x" (pad "1" (uuid repeated))))'
        spans=locate(raw);pads=[s for s in spans if s.head=='pad']
        self.assertEqual(len(pads),2);self.assertNotEqual(pads[0].identity,pads[1].identity)
        self.assertEqual(pads[0].bytes_from(raw),b'(pad "1" (uuid repeated))')
        by_start={s.start:s for s in spans}
        self.assertTrue(all(by_start[p.parent_start].head=='footprint' for p in pads))
    def test_utf8_offsets_escapes_and_comment_parentheses(self):
        raw='(root (name "铜(板)\\\"x") ; ignored ()\n (pad "1"))'.encode()
        spans=locate(raw)
        self.assertEqual([s.head for s in spans],['root','name','pad'])
        self.assertEqual(spans[-1].bytes_from(raw),b'(pad "1")')
    def test_source_revision_mismatch_is_not_empty(self):
        span=locate(b'(pad "1")')[0]
        with self.assertRaisesRegex(LocatorError,'SOURCE_REVISION_MISMATCH'):span.bytes_from(b'(pad "2")')
    def test_malformed_input_is_not_partial_inventory(self):
        for raw in [b'(root (pad)',b')',b'(root "unterminated)']:
            with self.subTest(raw=raw),self.assertRaises(LocatorError):locate(raw)
