"""Export-local projections retain full slots, both walls and strict rejection."""
import copy
from pathlib import Path
import pytest
from shapely import to_wkb
from shapely.affinity import rotate, scale
from shapely.geometry import box
from shapely.ops import unary_union
from src import t02_shared_gaps as gaps, shared_gap_projection as projection
from src.stage_abi.store import ArtifactStore
from src.gerber_u05.prefix import shared_gap_restore_same


def case(tmp_path, rotation=0):
    original = dict(a=box(0, 0, 1, 1), b=box(0, 2, 1, 3), wall=box(2, -1, 3, 4))
    original = {s: rotate(g, rotation, origin=(0, 0)) for s, g in original.items()}
    store = ArtifactStore(tmp_path / 'runtime')
    ref = lambda g: store.put('geometry', to_wkb(g))
    scene = dict(source_sha256='a' * 64, objects=[
        dict(source_id=s, kind='fixed' if s == 'wall' else 'rectangle',
             original_ref=ref(g), geometry_ref=ref(g), metadata={})
        for s, g in original.items()])
    spec = gaps.records(scene, original, original)
    proposed = {s: scale(original[s], 1.1, 1.1, origin=original[s].centroid) for s in ('a', 'b')}
    result, proof = gaps.project(spec, original, original, proposed)
    return dict(original, **result), proof


@pytest.mark.parametrize('rotation', [0, 90])
@pytest.mark.parametrize('tolerance', [0., .000002])
def test_complete_report_matches_global_checker_and_preserves_parts(tmp_path, rotation, tolerance):
    material, proof = case(tmp_path, rotation)
    parts = list(material.values())
    before = [to_wkb(g) for g in parts]
    assert projection.complete_parts(proof, parts, tolerance_mm=tolerance) == gaps.complete(
        proof, unary_union(parts), tolerance_mm=tolerance)
    assert [to_wkb(g) for g in parts] == before


@pytest.mark.parametrize('start,end', [(0., .01), (.2, .8), (.99, 1.)])
def test_intrusions_at_both_slot_ends_and_middle_remain_rejected(tmp_path, start, end):
    material, proof = case(tmp_path)
    bad = box(1.05, start, 1.06, end)
    for check in (lambda: gaps.complete(proof, unary_union([*material.values(), bad])),
                  lambda: projection.complete_parts(proof, [*material.values(), bad])):
        with pytest.raises(ValueError, match='UNIFORMITY'):
            check()


@pytest.mark.parametrize('bank', ['a', 'wall'])
def test_missing_middle_of_each_wall_cannot_be_hidden_by_window_cut(tmp_path, bank):
    material, proof = case(tmp_path)
    cut = box(1.04, .2, 1.06, .8) if bank == 'a' else box(1.99, .2, 2.01, .8)
    material[bank] = material[bank].difference(cut)
    with pytest.raises(ValueError, match='UNIFORMITY'):
        projection.complete_parts(proof, material.values())


def test_collective_bridge_across_multiple_parts_is_not_exempt(tmp_path):
    material, proof = case(tmp_path)
    pieces = [*material.values(), box(1.04, .2, 1.53, .8), box(1.53, .2, 2.01, .8)]
    with pytest.raises(ValueError, match='UNIFORMITY'):
        projection.complete_parts(proof, pieces)


def test_long_support_is_clipped_outside_all_checked_walls_not_union_globally(tmp_path, monkeypatch):
    material, proof = case(tmp_path)
    material['wall'] = box(2, -10000, 3, 10000)
    material['remote'] = box(10000, 10000, 10001, 10001)
    expected = gaps.complete(proof, unary_union(list(material.values())))
    actual_union = projection.unary_union
    def local_only(parts):
        assert all(max(abs(v) for v in p.bounds) < 20 for p in parts)
        return actual_union(parts)
    monkeypatch.setattr(projection, 'unary_union', local_only)
    assert projection.complete_parts(proof, material.values()) == expected


def test_complete_global_predicate_is_not_replaced_by_per_zone_passes(tmp_path, monkeypatch):
    material, proof = case(tmp_path)
    proof = copy.deepcopy(proof)
    proof['zones'][1]['gap_mm'] -= .05
    original = gaps.check
    def collective(proof, material, **kwargs):
        result = original(proof, material, **kwargs)
        widths = [r['gap_mm'] for r in proof['zones']]
        if widths and max(widths) - min(widths) > .01:
            result['passed'] = False
        return result
    monkeypatch.setattr(gaps, 'check', collective)
    with pytest.raises(ValueError, match='UNIFORMITY'):
        gaps.complete(proof, unary_union(list(material.values())))
    with pytest.raises(ValueError, match='UNIFORMITY'):
        projection.complete_parts(proof, material.values())


def test_no_material_cannot_create_artificial_slot_walls(tmp_path):
    _, proof = case(tmp_path)
    with pytest.raises(ValueError, match='UNIFORMITY'):
        projection.complete_parts(proof, [])


def test_no_zones_preserves_original_complete_report(tmp_path):
    material, proof = case(tmp_path)
    proof = dict(proof, zones=[])
    assert projection.complete_parts(proof, material.values()) == gaps.complete(
        proof, unary_union(list(material.values())))


def restore_pair():
    after = Path(gaps.__file__).read_text()
    before = after.replace('def restore(store,scene,*,project_parts=False):', 'def restore(store,scene):')
    before = before.replace('  if project_parts:\n   from src.shared_gap_projection import complete_parts\n   complete_parts(ACTIVE,now.values())\n  else:\n   complete(ACTIVE,unary_union(list(now.values())))',
                            '  complete(ACTIVE,unary_union(list(now.values())))')
    assert before != after
    return before, after


def test_prefix_exception_is_exact_export_opt_in_only():
    before, after = restore_pair()
    assert shared_gap_restore_same(before, after)['status'] == 'UNCHANGED_GROWTH_AND_DEFAULT_RESTORE_AST'


@pytest.mark.parametrize('old,new', [
    ('project_parts=False', 'project_parts=True'),
    ('project_parts=False', 'project_parts: unrelated_call()=False'),
    ('complete_parts(ACTIVE,now.values())', 'complete_parts(ACTIVE,[])'),
    ('intrusion<=EPS', 'intrusion<=1.'),
    ('  ACTIVE=state', '  ACTIVE=dict(state,zones=[])'),
])
def test_prefix_exception_rejects_default_or_predicate_bypasses(old, new):
    before, after = restore_pair()
    assert old in after
    with pytest.raises(ValueError, match='REUSED_SHARED_GAP'):
        shared_gap_restore_same(before, after.replace(old, new))
