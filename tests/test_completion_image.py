import math,tempfile,unittest
from pathlib import Path
from shapely.geometry import Point
from shapely.ops import unary_union
from src.gerber_image import read_image
from src.validator import Unsupported
from src.fc1_oracle import placed_polygons,analytic_area

HEADER='%FSLAX26Y26*%\n%MOMM*%\n%LPD*%\n'
class CompletionImage(unittest.TestCase):
    def load(self,text):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'out/v15_completion') as folder:
            p=Path(folder)/'control.gbr';p.write_text(text);return read_image(p)['geometry']

    def test_actual_fc1_bytes_agree_with_independent_oracle(self):
        p=Path('out/fc1/run_001/Block_with_different_orientations.gbr')
        actual=read_image(p)['geometry'];expected=unary_union(placed_polygons())
        self.assertLess(actual.symmetric_difference(expected).area,4e-4)
        self.assertLess(abs(actual.area-analytic_area()*3.64),4e-4)
        self.assertEqual(len(actual.geoms),12)
        self.assertEqual(sum(len(g.interiors) for g in actual.geoms),4)

    def test_equivalent_coordinate_encoding_and_different_filename(self):
        import re
        raw=Path('out/fc1/run_001/Block_with_different_orientations.gbr').read_text()
        encoded=re.sub(r'(?m)^[XY][^\n]*\*',lambda line:re.sub(r'([XYIJ])(-?)(\d+)',lambda m:m[1]+m[2]+m[3].zfill(8),line[0]),raw)
        a=self.load(raw);b=self.load(encoded)
        self.assertTrue(a.equals_exact(b,1e-12))

    def test_controlled_scale_variation_is_not_a_golden_file_special_case(self):
        raw=Path('out/fc1/run_001/Block_with_different_orientations.gbr').read_text()
        g=self.load(raw.replace('%LS0.8*%','%LS0.6*%'))
        self.assertLess(abs(g.area-analytic_area()*3.36),4e-4)

    def test_real_byte_reset_extension_and_leak_fault(self):
        raw=Path('out/fc1/run_001/Block_with_different_orientations.gbr').read_text()
        extension='D12*\nX0Y-5000000D03*\nM02*'
        positive=self.load(raw.replace('M02*',extension))
        leak=self.load(raw.replace('%LMN*%','').replace('%LR0.0*%','').replace('%LS1.0*%','').replace('M02*',extension))
        self.assertTrue(positive.covers(Point(-2.5,-4)))
        self.assertFalse(leak.covers(Point(-2.5,-4)))

    def test_real_byte_block_transparency_preserves_global_context(self):
        raw=Path('out/fc1/run_001/Block_with_different_orientations.gbr').read_text()
        prefix='%ADD13C,0.2*%\nD13*\nX-2500000Y-1000000D03*\n'
        raw=raw.replace('%ABD12*%',prefix+'%ABD12*%')
        g=self.load(raw)
        self.assertTrue(g.covers(Point(-2.5,-1)))
        self.assertLess(abs(g.area-analytic_area()*3.64-math.pi*.01),4e-4)

    def test_macro_local_clear_and_ordered_layer_polarity(self):
        # Circle ring macro over a pre-existing dark center; local transparent
        # hole must not erase the global context. Later layer clear must erase.
        raw=HEADER+'%AMRing*1,1,2,0,0*1,0,1,0,0*%\n%ADD10C,0.2*%\n%ADD11Ring*%\nD10*\nX0Y0D03*\nD11*\nX0Y0D03*\nM02*'
        g=self.load(raw);self.assertTrue(g.covers(Point(0,0)))
        self.assertLess(abs(g.area-(math.pi*.75+math.pi*.01)),1e-4)
        clear=self.load(raw.replace('M02*','%LPC*%\nD10*\nX0Y0D03*\nM02*'))
        self.assertFalse(clear.covers(Point(0,0)))

    def test_rotated_rectangle_macro_has_independent_area_and_bounds(self):
        raw=HEADER+'%AMRect*21,1,2,1,0,0,30*%\n%ADD10Rect*%\nD10*\nX0Y0D03*\nM02*'
        g=self.load(raw);self.assertAlmostEqual(g.area,2,places=10)
        self.assertAlmostEqual(g.bounds[2],math.sqrt(3)/2+.25,places=10)
        self.assertAlmostEqual(g.bounds[3],.5+math.sqrt(3)/4,places=10)

    def test_legal_cut_in_region_and_invalid_crossing(self):
        pts=[(0,0),(4,0),(4,4),(0,4),(0,1),(1,1),(1,3),(3,3),(3,1),(1,1),(0,1),(0,0)]
        def region(points):
            return HEADER+'G36*\n'+''.join(f'X{int(x*1e6)}Y{int(y*1e6)}D0{2 if i==0 else 1}*\n' for i,(x,y) in enumerate(points))+'G37*\nM02*'
        g=self.load(region(pts));self.assertAlmostEqual(g.area,12);self.assertFalse(g.covers(Point(2,2)))
        with self.assertRaises(Unsupported):self.load(region([(0,0),(4,4),(0,4),(4,0),(0,0)]))

    def test_semantically_unsupported_or_malformed_bytes_never_pass(self):
        valid=HEADER+'%ADD10C,1*%\nD10*\nX0Y0D03*\nM02*'
        self.assertGreater(self.load(valid).area,0)
        bad=[valid.replace('%MOMM*%',''),valid.replace('D10*\nX0','D99*\nX0'),valid.replace('M02*','G999*\nM02*'),valid+'G01*',valid.replace('M02*',''),valid.replace('D10*\nX0','D10JUNK*\nX0'),valid.replace('M02*','M02G999*'),HEADER+'%ABD11*%\n%ABD12*%\n%AB*%\n%AB*%\nM02*']
        for raw in bad:
            with self.subTest(raw=raw[:50]):
                with self.assertRaises(Unsupported):self.load(raw)

    def test_source_anchor_accepts_optional_pin_function_attribute(self):
        from src.completion_checks import anchors,intent_check
        from shapely.geometry import GeometryCollection
        self.assertEqual(intent_check(GeometryCollection(),[],{},'B.Cu')['unlabeled_components'],0)
        from shapely.geometry import box
        raw=HEADER+'%ADD10R,2X1*%\nD10*\n%TO.P,J1,1,Pin_1*%\nX0Y0D03*\nM02*'
        with tempfile.TemporaryDirectory(dir='out/v15_completion') as folder:
            path=Path(folder)/'p.gbr';path.write_text(raw);image=read_image(path)
        pads=[{'source_id':'source-pad-1','ref':'J1','pin':'1','center_mm':(0,0),'layers':['F.Cu'],'net':'source-net','shape':box(-1,-.5,1,.5)}]
        self.assertEqual(anchors(image,pads,'F.Cu')['status'],'PASS')

    def test_native_local_position_and_serialized_pad_angle(self):
        from src.native_reference import terminals
        text='(kicad_pcb (net 1 "N") (footprint "F" (layer "F.Cu") (at 10 20 90) (property "Reference" "J1") (uuid "id") (pad "1" smd rect (at 1 0 90) (size 2 1) (layers "F.Cu") (net 1 "N"))))'
        with tempfile.TemporaryDirectory(dir='out/v15_completion') as folder:
            path=Path(folder)/'p.kicad_pcb';path.write_text(text);p=terminals(path)[0]
        self.assertAlmostEqual(p['center_mm'][0],10);self.assertAlmostEqual(p['center_mm'][1],-19)
        self.assertAlmostEqual(p['shape'].bounds[0],9.5);self.assertAlmostEqual(p['shape'].bounds[1],-20)
        self.assertEqual(p['net'],'N')

    def test_same_winding_hole_is_not_silently_repaired(self):
        # Outer and inner loop both CCW: winding 2 is not a valid Gerber cut-in.
        pts=[(0,0),(4,0),(4,4),(0,4),(0,1),(1,1),(3,1),(3,3),(1,3),(1,1),(0,1),(0,0)]
        raw=HEADER+'G36*\n'+''.join(f'X{int(x*1e6)}Y{int(y*1e6)}D0{2 if i==0 else 1}*\n' for i,(x,y) in enumerate(pts))+'G37*\nM02*'
        with self.assertRaises(Unsupported):self.load(raw)
