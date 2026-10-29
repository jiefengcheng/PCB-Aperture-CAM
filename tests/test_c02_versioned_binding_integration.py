from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from shapely import from_wkb, get_coordinates, to_wkb
from shapely.geometry import Polygon
from src.crop_attachment_diagnostic import bind_circle_attachment, _decode
from src.crop_pinned_circle_binding import PINS, SOURCE
from tools.run_c02_four_attachment_diagnostic_v2 import bind_to_authoritative_scene

ROOT = Path(__file__).resolve().parents[1]


class VersionedBindingIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = (ROOT/'out/crop_dynamic_tasks/c02_focused_growth_coverage_20261028_05/inputs/ORG_source.kicad_pcb').read_bytes()

    def test_native_alternate_never_becomes_scene_or_port_operand(self):
        for span, target in [('1651778:1651902','1914089:1914270'),
                             ('1652641:1652766','1914273:1914454')]:
            sid = SOURCE+':bytes:'+span
            binding = bind_circle_attachment(self.raw, SOURCE+':bytes:'+target, sid)
            # The decoder may return either admitted representation. The scene
            # authority is always the exact REV05 cache, on every platform.
            canonical = (ROOT/'out/crop_dynamic_tasks/c02_focused_growth_coverage_20261028_05/inputs/source_wkb'/f'{PINS[sid]["cached"]}.wkb').read_bytes()
            points = get_coordinates(from_wkb(canonical)).tolist()
            points[174][1] = float.fromhex(PINS[sid]['alternate_y'])
            alternate = to_wkb(Polygon(points))
            _, (record,) = _decode(self.raw, [sid])
            native_record = (record[0], record[1], from_wkb(alternate), record[3])
            scene = SimpleNamespace(objects={binding.target_id:{'geometry':from_wkb(binding.target_wkb)},
                                             sid:{'geometry':from_wkb(canonical)}})
            with patch('src.crop_pinned_circle_binding._decode', return_value=(SOURCE,[native_record])):
                kept, evidence = bind_to_authoritative_scene(self.raw, replace(binding, obstacle_wkb=alternate), scene)
            self.assertEqual(kept.obstacle_wkb, canonical)
            self.assertEqual(evidence[1]['status'], 'PINNED_ALTERNATE_REPRESENTATION')
            self.assertEqual(scene.objects[sid]['geometry'].wkb, canonical)

    def test_unpinned_operand_mismatch_fails_closed(self):
        sid = SOURCE+':bytes:1650795:1650921'
        b = bind_circle_attachment(self.raw, SOURCE+':bytes:1913721:1913902', sid)
        scene = SimpleNamespace(objects={b.target_id:{'geometry':from_wkb(b.target_wkb)},
                                         sid:{'geometry':from_wkb(b.obstacle_wkb)}})
        changed = replace(b, target_wkb=to_wkb(Polygon([(0,0),(1,0),(1,1),(0,0)])))
        with self.assertRaisesRegex(ValueError, 'UNPINNED_SOURCE_BINDING_NOT_EXACT'):
            bind_to_authoritative_scene(self.raw, changed, scene)
        changed = replace(b, obstacle_wkb=changed.target_wkb)
        with self.assertRaisesRegex(ValueError, 'UNPINNED_SOURCE_BINDING_NOT_EXACT'):
            bind_to_authoritative_scene(self.raw, changed, scene)


if __name__ == '__main__':
    unittest.main()
