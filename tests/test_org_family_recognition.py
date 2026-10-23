import inspect
import tempfile
from pathlib import Path
import unittest

from shapely import to_wkb
from shapely.geometry import LineString, Point, Polygon, box

from src.org_family_recognition import recognize_org_records
from src.revision_catalog import canonical, digest


def circle(x, y, radius, layer='F.Cu'):
    node = (f'(gr_circle (center {x} {y}) (end {x + radius} {y}) '
            f'(stroke (width 0) (type default)) (fill yes) (layer "{layer}"))')
    return ('gr_circle', layer, node, Point(x, y).buffer(radius, quad_segs=128))


def rectangle(x0, y0, x1, y1, layer='F.Cu'):
    node = (f'(gr_poly (pts (xy {x0} {y0}) (xy {x1} {y0}) '
            f'(xy {x1} {y1}) (xy {x0} {y1})) '
            f'(stroke (width 0) (type default)) (fill yes) (layer "{layer}"))')
    return ('gr_poly', layer, node, box(x0, y0, x1, y1))


def triangle(x, y, layer='F.Cu'):
    node = (f'(gr_poly (pts (xy {x} {y}) (xy {x + 1} {y}) '
            f'(xy {x} {y + 1})) (stroke (width 0) (type default)) '
            f'(fill yes) (layer "{layer}"))')
    return ('gr_poly', layer, node, Polygon([(x, y), (x + 1, y), (x, y + 1)]))


def segment(x0, y0, x1, y1, width=0.1, layer='F.Cu'):
    node = (f'(segment (start {x0} {y0}) (end {x1} {y1}) '
            f'(width {width}) (layer "{layer}"))')
    shape = LineString([(x0, y0), (x1, y1)]).buffer(width / 2, quad_segs=128)
    return ('segment', layer, node, shape)


def make_records(specs):
    raw_parts = []
    for _, _, node, _ in specs:
        raw_parts.append(node)
    source = ('\n'.join(raw_parts) + '\n').encode()
    source_hash = digest(source)
    objects = []
    payloads = {}
    offset = 0
    for kind, layer, node, shape in specs:
        encoded = node.encode()
        start, end = offset, offset + len(encoded)
        data = to_wkb(shape)
        geometry_hash = digest(data)
        payloads[geometry_hash] = data
        objects.append({
            'id': f'{source_hash}:bytes:{start}:{end}',
            'source_sha256': source_hash,
            'source_span': [start, end],
            'parent_id': None, 'native_id': None, 'kind': kind,
            'layers': [layer], 'geometry_sha256': geometry_hash,
            'bounds_mm': list(shape.bounds), 'coverage': 'GEOMETRY_AVAILABLE',
            'unsupported_reason': None,
        })
        offset = end + 1
    return source_hash, source, objects, payloads


def recognize(specs, *, reverse=False):
    source_hash, source, objects, payloads = make_records(specs)
    result = recognize_org_records(
        org_revision=digest(b'fixture-org-revision'), source_sha256=source_hash,
        source_bytes=source, objects=list(reversed(objects)) if reverse else objects,
        geometry_payloads=payloads)
    return result


class OrgFamilyRecognitionTests(unittest.TestCase):
    def test_circle_and_valid_rectangle_seed_but_nonrectangle_is_excluded(self):
        result = recognize([
            circle(0, 0, 0.05), circle(0.2, 0, 0.05), circle(0.4, 0, 0.05),
            rectangle(2, 0, 3, 0.5), triangle(5, 0),
        ])
        members = [row for row in result['entities']
                   if row['entity_type'] == 'candidate_member']
        self.assertEqual(len(members), 4)
        self.assertEqual(result['coverage']['candidate_seed_count'], 4)
        self.assertEqual(result['coverage']['seed_exclusions'].get(
            'NOT_FOUR_DISTINCT_RECTANGLE_VERTICES'), 1)
        rects = [row for row in members
                 if row['geometry']['shape_signature']['primitive'] ==
                 'filled_axis_aligned_rectangle']
        self.assertEqual(len(rects), 1)

    def test_exact_trace_contact_and_ambiguous_mask_features_are_retained(self):
        result = recognize([
            circle(0, 0, 0.1), segment(0.08, 0, 0.3, 0),
            circle(0, 0, 0.08, 'F.Mask'), circle(0, 0, 0.09, 'F.Mask'),
            ('gr_circle', 'F.Mask',
             '(gr_circle (center 0 0) (end 0.1 0) '
             '(stroke (width 0.01) (type default)) (fill none) (layer "F.Mask"))',
             Point(0, 0).buffer(0.1, quad_segs=128).difference(
                 Point(0, 0).buffer(0.08, quad_segs=128))),
        ])
        member = next(row for row in result['entities']
                      if row['entity_type'] == 'candidate_member')
        self.assertEqual(len(member['trace_associations']['nominal_contacts']), 1)
        self.assertEqual(member['trace_associations']['nominal_contacts'][0]['status'],
                         'NOMINAL_CONTACT')
        self.assertEqual(member['reference_features']['F.Mask']['status'], 'AMBIGUOUS')
        self.assertEqual(len(member['reference_features']['F.Mask']['candidates']), 2)
        self.assertEqual(len(member['reference_features']['F.Mask']['unsupported_candidates']), 1)
        self.assertEqual(member['reference_features']['F.Paste']['status'], 'UNMATCHED')

    def test_near_trace_is_kept_as_uncertain_not_nominal(self):
        result = recognize([circle(0, 0, 0.1), segment(0.15002, 0, 0.4, 0)])
        member = next(row for row in result['entities']
                      if row['entity_type'] == 'candidate_member')
        self.assertEqual(member['trace_associations']['nominal_contacts'], [])
        uncertain = member['trace_associations']['uncertain_associations']
        self.assertEqual(len(uncertain), 1)
        self.assertEqual(uncertain[0]['status'], 'CONTACT_STATUS_UNCERTAIN')

    def test_repeated_vectors_form_provisional_families_and_keep_overlap(self):
        result = recognize([circle(x, 0, 0.05) for x in (0, 0.2, 0.4, 0.6)])
        members = [row for row in result['entities']
                   if row['entity_type'] == 'candidate_member']
        families = [row for row in result['entities'] if row['entity_type'] == 'family']
        self.assertTrue(any(len(family['support_pairs']) >= 2 for family in families))
        self.assertTrue(any(len(family['members']) == 4 for family in families))
        self.assertTrue(all(member['family_membership_status'] ==
                            'AMBIGUOUS_MULTIPLE_FAMILY_HYPOTHESES'
                            for member in members))

    def test_source_order_is_deterministic_and_edit_bytes_are_not_an_input(self):
        specs = [circle(x, 0, 0.05) for x in (0, 0.2, 0.4, 0.6)]
        first = recognize(specs)
        reordered = recognize(specs, reverse=True)
        first_content = digest(canonical({key: first[key] for key in
                                         ('entities', 'relations', 'coverage')}))
        reordered_content = digest(canonical({key: reordered[key] for key in
                                             ('entities', 'relations', 'coverage')}))
        self.assertEqual(first_content, reordered_content)
        self.assertNotIn('edit', {name.lower() for name in inspect.signature(
            recognize_org_records).parameters})
        with tempfile.TemporaryDirectory() as temporary:
            edit_file = Path(temporary) / 'EDIT' / 'top_layer.kicad_pcb'
            before = digest(canonical(first['entities']))
            edit_file.parent.mkdir()
            edit_file.write_bytes(b'edit version one')
            unchanged_with_edit_one = recognize(specs)
            edit_file.write_bytes(b'completely different edit version two')
            unchanged_with_edit_two = recognize(specs)
            self.assertEqual(before, digest(canonical(unchanged_with_edit_one['entities'])))
            self.assertEqual(before, digest(canonical(unchanged_with_edit_two['entities'])))


if __name__ == '__main__':
    unittest.main()
