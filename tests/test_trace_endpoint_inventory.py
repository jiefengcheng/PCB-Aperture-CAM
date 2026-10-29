import unittest
from src.trace_endpoint_inventory import endpoint_components


def row(sid, start, end, width=.1):
    return dict(source_id=sid, endpoints_decimal_mm=[start, end], width_mm=width)


class EndpointInventoryTests(unittest.TestCase):
    def test_expands_beyond_crop_seed_and_preserves_decimal_adjacency(self):
        rows = [row('a', ['0','0'], ['1','0']), row('b', ['1.000','0'], ['2','0'])]
        result = endpoint_components(rows, ['a'])
        self.assertEqual(result[0]['source_ids'], ['a','b'])
        self.assertFalse(result[0]['unresolved_reasons'])
        self.assertEqual(endpoint_components(list(reversed(rows)), ['a']), result)

    def test_nearby_endpoints_are_not_silently_connected(self):
        rows = [row('a', ['0','0'], ['1','0']), row('b', ['1.000001','0'], ['2','0'])]
        self.assertEqual(len(endpoint_components(rows, ['a','b'])), 2)

    def test_branch_and_mixed_width_not_split_to_qualify(self):
        rows = [row('a',['0','0'],['1','0']), row('b',['1','0'],['2','0'],.2),
                row('c',['1','0'],['1','1'])]
        result = endpoint_components(rows, ['a'])[0]
        self.assertEqual(result['source_ids'], ['a','b','c'])
        self.assertIn('BRANCHED_ENDPOINT_COMPONENT', result['unresolved_reasons'])
        self.assertIn('MIXED_ORIGINAL_WIDTHS', result['unresolved_reasons'])

    def test_unknown_source_rejected(self):
        with self.assertRaisesRegex(ValueError, 'INVALID_TRACE_IDENTITIES'):
            endpoint_components([], ['missing'])


if __name__ == '__main__':
    unittest.main()
