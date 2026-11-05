"""Exact retained support failure, unchanged thresholds and actual contour reparse."""
import hashlib
import json
from pathlib import Path
import pytest
from shapely import from_wkb
from shapely.geometry import box
from src.gerber_u05 import pipeline as p
from src.gerber_u05 import exporter as e
from src.u05_board.export import export_region
from src.junction_spindle_stage import CONTRACT
from test_gerber_source import source_circle
from src.gerber_u05.export_absorption import supported_region


def fixture():
    folder = Path(__file__).with_name('fixtures') / 'export_support'
    manifest = json.loads((folder / 'MANIFEST.json').read_bytes())
    values = {}
    for name, sha in manifest['files'].items():
        blob = (folder / (name + '.wkb')).read_bytes()
        assert hashlib.sha256(blob).hexdigest() == sha
        values[name] = from_wkb(blob)
    return values


def test_actual_support_is_built_only_from_existing_owner_and_reparses(tmp_path):
    g = fixture()
    with pytest.raises(ValueError, match='SUPPORT_CHANGES_QUALIFIED_COPPER'):
        export_region(g['addition'], g['owner'], g['window'])
    region, support = export_region(g['addition'], g['owner'], g['window'], support_from_owner=True)
    selected, _, mode = supported_region(g['addition'], g['owner'], g['window'])
    assert mode == 'CHECKED_OWNER_FIRST_ALTERNATE'
    assert p.to_wkb(selected) == p.to_wkb(region)
    assert support.difference(g['owner']).area <= CONTRACT.area_epsilon_mm2
    assert g['addition'].difference(region).area <= CONTRACT.area_epsilon_mm2
    assert g['owner'].union(region).symmetric_difference(g['target']).area <= CONTRACT.area_epsilon_mm2
    assert region.difference(g['window']).area <= CONTRACT.area_epsilon_mm2
    store = p.Store(tmp_path / 'store')
    records, blocks = [], []
    e.append_regions(region, 't05', 'retained-support-failure', records, blocks, store)
    base, _ = e.canonical_base(source_circle())
    parsed = e.parse((base + ''.join(blocks) + 'M02*\n').encode())
    actual = p.unary_union([p.affine_scale(p.source_profile.object_geometry(o)[0], 1, -1, origin=(0, 0))
                            for o in parsed.objects[-len(records):]])
    reference = p.unary_union([p.geometry(store, row['reference_ref']) for row in records])
    assert e.fidelity(reference, actual)['passed']


def test_supported_region_cannot_hide_an_addition_outside_its_window():
    with pytest.raises(ValueError, match='SUPPORT_CHANGES_QUALIFIED_COPPER'):
        export_region(box(2, 0, 3, 1), box(0, 0, 1, 1), box(-1, -1, 1.5, 2), support_from_owner=True)
