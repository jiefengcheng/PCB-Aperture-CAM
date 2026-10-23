import unittest

from tools.build_copper_group_review import (
    _circle_links, _fit_translation_from_anchors, _mutual_unique_pairs,
    _rectangle_links, draw,
)


def circle_source(radius):
    return (f'(gr_circle (center 1.0 2.0) (end {1.0 + radius:.8f} 2.0) '
            '(stroke (width 0) (type solid)) (fill yes) (layer F.Cu))').encode()


def row(identity, raw, kind='gr_circle'):
    return {'id': identity, 'kind': kind, 'layers': ['F.Cu'],
            'source_span': [0, len(raw)]}


def rectangle_source(width, height):
    x0, x1 = 1 - width / 2, 1 + width / 2
    y0, y1 = 2 - height / 2, 2 + height / 2
    return (f'(gr_poly (pts (xy {x0:.8f} {y0:.8f}) (xy {x1:.8f} {y0:.8f}) '
            f'(xy {x1:.8f} {y1:.8f}) (xy {x0:.8f} {y1:.8f})) '
            '(stroke (width 0) (type solid)) (fill yes) (layer F.Cu))').encode()


class RegistrationTests(unittest.TestCase):
    def test_fits_translation_from_shape_descriptors_without_coordinate_descriptors(self):
        before = [
            {'identity': 'b1', 'descriptor': ('circle', .2, 'yes'), 'center_mm': (0., 0.)},
            {'identity': 'b2', 'descriptor': ('rect', .4, .8, 'yes'), 'center_mm': (3., 0.)},
            {'identity': 'b3', 'descriptor': ('circle', .3, 'yes'), 'center_mm': (0., 4.)},
            {'identity': 'b4', 'descriptor': ('rect', .6, .9, 'yes'), 'center_mm': (4., 4.)},
        ]
        after = [
            {'identity': 'a1', 'descriptor': before[0]['descriptor'], 'center_mm': (.125, -.25)},
            {'identity': 'a2', 'descriptor': before[1]['descriptor'], 'center_mm': (3.125, -.25)},
            {'identity': 'a3', 'descriptor': before[2]['descriptor'], 'center_mm': (.125, 3.75)},
            {'identity': 'a4', 'descriptor': before[3]['descriptor'], 'center_mm': (4.125, 3.75)},
        ]
        result = _fit_translation_from_anchors(before, after)
        self.assertEqual(result['translation_vote_mm_after_minus_before'], [.125, -.25])
        self.assertEqual(result['inlier_count'], 4)
        self.assertAlmostEqual(result['max_inlier_residual_mm'], 0.)
        self.assertNotIn('center_mm', result['descriptor'])

    def test_mutual_unique_matching_leaves_duplicate_choices_unpaired(self):
        pairs = _mutual_unique_pairs([(1., 2.)], [(1., 2.), (1.0005, 2.)], .001)
        self.assertEqual(pairs, [])

    def test_mutual_unique_matching_accepts_a_single_registered_center_offset(self):
        pairs = _mutual_unique_pairs([(1., 2.)], [(1.0005, 2.)], .001)
        self.assertEqual(len(pairs), 1)
        self.assertEqual(pairs[0][:2], (0, 0))
        self.assertAlmostEqual(pairs[0][2], .0005)


class CopperGroupReviewTests(unittest.TestCase):
    def test_filled_zero_width_circles_match_by_unique_center_and_keep_radius_change(self):
        before = circle_source(.1)
        after = circle_source(.2)
        links = _circle_links(
            {'before': before, 'after': after},
            {'before': [row('before-circle', before)],
             'after': [row('after-circle', after)]},
        )
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0]['before_identity'], 'before-circle')
        self.assertEqual(links[0]['after_identity'], 'after-circle')
        self.assertAlmostEqual(links[0]['before_radius_mm'], .1)
        self.assertAlmostEqual(links[0]['after_radius_mm'], .2)
        self.assertGreater(links[0]['added_area_mm2'], 0)

    def test_duplicate_circle_centers_are_not_claimed_as_a_match(self):
        before = circle_source(.1)
        after = circle_source(.2)
        links = _circle_links(
            {'before': before, 'after': after},
            {'before': [row('before-a', before), row('before-b', before)],
             'after': [row('after', after)]},
        )
        self.assertEqual(links, [])

    def test_filled_circle_is_drawn_as_copper_disc(self):
        svg = draw({'shape': 'circle', 'points': [(0, 0), (.1, 0)],
                    'width': 0, 'fill': 'yes'}, 10, 10, 100, '#14828a')
        self.assertIn('fill="#14828a"', svg)
        self.assertIn('stroke="none"', svg)

    def test_group_svg_carries_exact_source_identity_and_side_for_selection(self):
        svg = draw({'shape': 'circle', 'points': [(0, 0), (.1, 0)],
                    'width': 0, 'fill': 'yes',
                    'source_identity': 'hash:bytes:10:20',
                    'source_side': 'before'}, 10, 10, 100, '#14828a')
        self.assertIn('data-source-identity="hash:bytes:10:20"', svg)
        self.assertIn('data-source-side="before"', svg)
        self.assertIn('<circle', svg)

    def test_filled_rectangles_match_by_unique_center_and_compare_area(self):
        before = rectangle_source(.2, .4)
        after = rectangle_source(.3, .4)
        links = _rectangle_links(
            {'before': before, 'after': after},
            {'before': [row('before-rect', before, 'gr_poly')],
             'after': [row('after-rect', after, 'gr_poly')]},
        )
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0]['before_identity'], 'before-rect')
        self.assertEqual(links[0]['after_identity'], 'after-rect')
        self.assertAlmostEqual(links[0]['before_area_mm2'], .08)
        self.assertAlmostEqual(links[0]['after_area_mm2'], .12)
        self.assertGreater(links[0]['added_area_mm2'], 0)

    def test_filled_circles_match_within_registration_tolerance_and_compare_radius(self):
        before = circle_source(.1)
        after = (b'(gr_circle (center 1.0005 2.0) (end 1.2005 2.0) '
                 b'(stroke (width 0) (type solid)) (fill yes) (layer F.Cu))')
        links = _circle_links(
            {'before': before, 'after': after},
            {'before': [row('before-circle', before)],
             'after': [row('after-circle', after)]},
            tolerance_mm=.001,
        )
        self.assertEqual(len(links), 1)
        self.assertAlmostEqual(links[0]['center_displacement_mm'], .0005)
        self.assertAlmostEqual(links[0]['before_radius_mm'], .1)
        self.assertAlmostEqual(links[0]['after_radius_mm'], .2)


if __name__ == '__main__':
    unittest.main()
