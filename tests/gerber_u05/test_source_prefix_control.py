from src.gerber_u05.source_prefix_control import mutate_source_coordinate
from test_gerber_source import source_circle
from src.gerber_u05 import exporter as e


def test_source_corruption_keeps_format_valid_and_changes_the_exact_prefix():
    base, _ = e.canonical_base(source_circle())
    body = (base + 'M02*\n').encode()
    mutated = mutate_source_coordinate(body)
    assert mutated != body
    assert b'%FSLAX46Y46*%' in mutated
    assert len(e.parse(mutated).objects) == len(e.parse(body).objects)
    assert not mutated.startswith(base.encode())
    assert sum(a != b for a, b in zip(body, mutated)) == 1
