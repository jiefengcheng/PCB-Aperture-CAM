import math
import unittest
from shapely import from_wkb
from src.native_inventory import inventory,ERROR_MM

HEADER='(kicad_pcb (version 20260101) (layers (0 "F.Cu" signal) (4 "In1.Cu" signal) (2 "B.Cu" signal) (1 "F.Mask" user) (3 "B.Mask" user)) '
class NativeInventoryTests(unittest.TestCase):
    def parse(self,body):return inventory((HEADER+body+')').encode())
    def test_nested_pad_transform_multilayer_and_repeated_identity(self):
        data=self.parse('(footprint "x" (layer "F.Cu") (at 10 20 90) (pad "1" smd rect (at 2 0 90) (size 2 1) (layers "F.Cu" "F.Mask") (uuid same))) (footprint "y" (layer "F.Cu") (at 0 0) (pad "1" smd rect (at 0 0) (size 2 1) (layers "F.Cu") (uuid same)))')
        pads=[r for r in data['objects'] if r['kind']=='pad']
        self.assertEqual(len(pads),2);self.assertNotEqual(pads[0]['id'],pads[1]['id'])
        self.assertEqual(pads[0]['layers'],['F.Cu','F.Mask'])
        self.assertAlmostEqual(pads[0]['bounds_mm'][0],9.5)
        self.assertAlmostEqual(pads[0]['bounds_mm'][1],17)
        self.assertAlmostEqual(pads[0]['filled_area_mm2'],2)
        self.assertIsNotNone(pads[0]['parent_id'])
    def test_via_layers_and_hole_not_solid_bbox(self):
        data=self.parse('(via (at 0 0) (size 2) (drill 1) (layers "F.Cu" "B.Cu") (uuid same))')
        via=data['objects'][0];shape=from_wkb(data['payloads'][via['geometry_sha256']])
        self.assertEqual(via['layers'],['B.Cu','F.Cu','In1.Cu'])
        self.assertFalse(shape.contains(__import__('shapely').geometry.Point(0,0)))
        self.assertAlmostEqual(via['filled_area_mm2'],math.pi*.75,places=4)
        self.assertEqual(via['bbox_area_mm2'],4)
    def test_arcs_fills_voids_and_unknowns_accounted(self):
        data=self.parse('(arc (start -1 0) (mid 0 1) (end 1 0) (width .2) (layer "F.Cu")) (zone (net 0) (layer "F.Cu") (polygon (pts (xy 0 0) (xy 2 0) (xy 2 2))) (filled_polygon (layer "F.Cu") (pts (xy 0 0) (xy 2 0) (xy 2 2) (xy 0 2)))) (gr_curve (pts (xy 0 0))) (future_copper (layer "F.Cu"))')
        self.assertEqual(data['counts'],{'arc':1,'zone':1,'polygon':1,'filled_polygon':1,'gr_curve':1,'future_copper':1})
        self.assertEqual(data['geometry_available'],2)
        self.assertEqual(data['source_objects'],sum(data['counts'].values()))
        self.assertEqual(data['counts']['future_copper'],1)
        self.assertTrue(all(r['coverage']=='GEOMETRY_AVAILABLE' or r['unsupported_reason'] for r in data['objects']))
        fill=next(r for r in data['objects'] if r['kind']=='filled_polygon');self.assertEqual(fill['filled_area_mm2'],4)
    def test_back_transform_custom_pad_unresolved_layers_explicit(self):
        data=self.parse('(footprint "b" (layer "B.Cu") (at 0 0) (pad "1" smd rect (at 0 0) (size 2 1) (layers "B.Cu"))) (pad "2" smd custom (at 0 0) (size 1 1) (layers "F.Cu") (primitives (gr_poly))) (segment (start 0 0) (end 1 0) (width 1) (layer "Absent.Cu"))')
        self.assertTrue(any(r['unsupported_reason']=='BACK_FOOTPRINT_TRANSFORM_NOT_QUALIFIED' for r in data['objects']))
        self.assertTrue(any(r['unsupported_reason']=='CUSTOM_PAD_PRIMITIVES' for r in data['objects']))
        self.assertTrue(any(r['unsupported_reason']=='UNRESOLVED_LAYER_MEMBERSHIP' for r in data['objects']))

    def test_stored_fill_retains_void_and_custom_children_are_unsupported(self):
        from shapely.geometry import Point
        data=self.parse('(zone (layer "F.Cu") (filled_polygon (layer "F.Cu") (pts (xy 0 0) (xy 4 0) (xy 4 4) (xy 0 4) (xy 0 1) (xy 1 1) (xy 1 3) (xy 3 3) (xy 3 1) (xy 1 1) (xy 0 1) (xy 0 0)))) (pad "2" smd custom (at 0 0) (size 1 1) (layers "F.Cu") (primitives (gr_poly (pts (xy 0 0) (xy 1 0) (xy 0 1)) (fill solid))))')
        fill=next(r for r in data['objects'] if r['kind']=='filled_polygon')
        self.assertEqual(fill['coverage'],'GEOMETRY_AVAILABLE')
        shape=from_wkb(data['payloads'][fill['geometry_sha256']])
        self.assertAlmostEqual(shape.area,12);self.assertFalse(shape.contains(Point(2,2)))
        primitive=next(r for r in data['objects'] if r['kind']=='gr_poly')
        self.assertEqual(primitive['unsupported_reason'],'CUSTOM_PAD_PRIMITIVE_CONTEXT_NOT_QUALIFIED')

    def test_via_span_uses_copper_stack_order_not_serialized_enum_order(self):
        raw=b'(kicad_pcb (layers (0 "F.Cu" signal) (2 "B.Cu" signal) (4 "In1.Cu" signal)) (via (at 0 0) (size 2) (drill 1) (layers "F.Cu" "B.Cu")))'
        result=inventory(raw)
        self.assertEqual(result['objects'][0]['layers'],['B.Cu','F.Cu','In1.Cu'])
