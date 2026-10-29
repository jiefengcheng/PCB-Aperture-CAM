import copy
from pathlib import Path
import unittest
from shapely import from_wkb, get_coordinates, to_wkb
from shapely.geometry import Polygon
from src.crop_pinned_circle_binding import PINS, bind_pinned_circle, verify_representation
from src.crop_attachment_diagnostic import _decode

ROOT = Path(__file__).resolve().parents[1]
CAPTURE = ROOT/'out/crop_dynamic_tasks/c02_native_binding_capture_author_20261029_11'
SOURCE = ROOT/'out/crop_dynamic_tasks/c02_focused_growth_coverage_20261028_05/inputs/ORG_source.kicad_pcb'


class PinnedCircleBindingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = SOURCE.read_bytes()

    def fixture(self, sid):
        pin = PINS[sid]
        blob = (CAPTURE/f'{pin["site"]}_obstacle_cached.wkb').read_bytes()
        _, ((kind, attrs, _, _),) = _decode(self.source, [sid])
        start, end = map(int, sid.rsplit(':', 2)[1:])
        fragment = self.source[start:end]
        vertices = get_coordinates(from_wkb(blob)).tolist()
        vertices[174][1] = float.fromhex(pin['alternate_y'])
        alternate = to_wkb(Polygon(vertices))
        return fragment, kind, attrs, blob, alternate

    def test_both_pinned_alternates_and_canonical_authority(self):
        for sid in PINS:
            fragment, kind, attrs, blob, alternate = self.fixture(sid)
            for native, status in [(blob, 'CANONICAL_EXACT'),
                                   (alternate, 'PINNED_ALTERNATE_REPRESENTATION')]:
                r = verify_representation(sid, fragment, kind, attrs, blob, native)
                self.assertEqual(r['status'], status)
                self.assertEqual(r['geometry_authority'], 'EXACT_REV05_CACHED_WKB_ONLY')
                self.assertEqual(r['acceptance'], 'NONE')
            kept, r = bind_pinned_circle(self.source, sid, blob)
            self.assertIs(kept, blob)
            self.assertEqual(r['authoritative_wkb_sha256'], PINS[sid]['cached'])

    def test_third_hash_extra_vertex_and_count_rejected(self):
        for sid in PINS:
            fragment, kind, attrs, blob, alternate = self.fixture(sid)
            vertices = get_coordinates(from_wkb(alternate)).tolist()
            vertices[1][0] += 1e-13
            changed = to_wkb(Polygon(vertices))
            removed = to_wkb(Polygon(vertices[:-2]))
            for native in (changed, removed):
                with self.assertRaisesRegex(ValueError, 'UNLISTED_RECONSTRUCTION_HASH'):
                    verify_representation(sid, fragment, kind, attrs, blob, native)

    def test_wrong_source_cache_and_swapped_variant_rejected(self):
        sid, other = list(PINS)
        fragment, kind, attrs, blob, _ = self.fixture(sid)
        _, _, _, other_blob, alternate = self.fixture(other)
        for cached, native in [(other_blob, blob), (blob, alternate)]:
            with self.assertRaises(ValueError):
                verify_representation(sid, fragment, kind, attrs, cached, native)
        with self.assertRaisesRegex(ValueError, 'SOURCE_OR_CACHE_HASH_MISMATCH'):
            verify_representation(sid, fragment+b' ', kind, attrs, blob, blob)
        with self.assertRaisesRegex(ValueError, 'SOURCE_NOT_PINNED'):
            bind_pinned_circle(self.source+b' ', sid, blob)
        with self.assertRaisesRegex(ValueError, 'SOURCE_NOT_PINNED'):
            bind_pinned_circle(self.source, sid+'0', blob)

    def test_changed_inputs_or_semantics_rejected(self):
        for sid in PINS:
            fragment, kind, attrs, blob, alternate = self.fixture(sid)
            for key, value in [('center', [0., 0.]), ('end', [0., 0.]),
                               ('fill', ['none']), ('layer', ['B.Cu'])]:
                bad = copy.deepcopy(attrs)
                bad[key] = value
                with self.assertRaises(ValueError):
                    verify_representation(sid, fragment, kind, bad, blob, alternate)


if __name__ == '__main__':
    unittest.main()
