"""Reduced numerical overlay regression and strict positive-material controls."""
import pytest
from shapely import from_wkt
from shapely.affinity import translate
from shapely.geometry import box, Polygon, MultiPolygon
from src import component_clearance as cc, source_channel_scope, pin_separation
from src.prepared_width_scene import PreparedWidthScene


@pytest.fixture(autouse=True)
def isolated_ownership(monkeypatch):
    monkeypatch.setattr(cc, 'ACTIVE', None)
    monkeypatch.setattr(source_channel_scope, 'ACTIVE', None)
    monkeypatch.setattr(pin_separation, 'ACTIVE', None)


def numerical_case():
    # A reduced, translated numeric fragment: three elementary polygons only,
    # with no board objects, identifiers or intake dependency. Full precision
    # reproduces the large-overlay boundary spur on unchanged source copper.
    before = from_wkt('POLYGON ((0.7400000000000002 -0.4100197731755424, '
        '0.7400000000000002 -0.46, 0.6800000000000002 -0.46, '
        '0.6800000000000002 -0.4435996548323473, '
        '0.7400000000000002 -0.4100197731755424))')
    candidate = from_wkt('POLYGON ((0.7400000000000002 -0.4339999999999993, '
        '0.7400000000000002 -0.46, 0.6800000000000002 -0.46, '
        '0.6800000000000002 -0.4339999999999993, '
        '0.7400000000000002 -0.4339999999999993))')
    return before, candidate, box(.68, -.390491, .692786, -.38)


def evaluate(before, candidate, foreign):
    # This isolates the owner-clearance predicate; source route admission,
    # uniform-offset construction and scalar limits have separate regressions.
    core = box(.69, -.455, .73, -.448)
    cc.bind(cc.joined([before, core, foreign]), '0' * 64,
            dict(route=core, body=before, foreign=foreign))
    row = dict(id='route', original=core, candidate=candidate,
               verified_original_width_mm=.007)
    fixed = [dict(id='body', geometry=before), dict(id='foreign', geometry=foreign)]
    checker = PreparedWidthScene([dict(row, candidate=core)], fixed)
    return checker.check([row], materialize_scene=True), checker


def test_old_boundary_is_not_new_width_material():
    before, candidate, foreign = numerical_case()
    whole_difference = cc.joined([before, candidate]).difference(before)
    actual_addition = candidate.difference(before)
    assert whole_difference.distance(foreign) < .0401
    assert actual_addition.distance(foreign) == pytest.approx(.043509, abs=1e-15)
    result, _ = evaluate(before, candidate, foreign)
    assert result['passed'] and result['evaluation_complete']
    assert result['scene_union_materialized']
    assert all(r['original_core_preserved'] for r in result['traces'])


@pytest.mark.parametrize('approach,passed', [
    (0., True), (.003408, True), (.003409, True), (.003410, False), (.004, False)])
def test_real_new_copper_keeps_the_unchanged_construction_guard(approach, passed):
    before, candidate, foreign = numerical_case()
    result, _ = evaluate(before, candidate, translate(foreign, yoff=-approach))
    assert result['passed'] is passed
    assert result['required_gap_mm'] == .0401
    if not passed:
        assert any(r['reason'] == 'NEW_COPPER_BELOW_FOREIGN_COMPONENT_GAP'
                   for r in result['failures'])


def test_positive_material_is_not_removed_by_an_area_threshold():
    before, _, foreign = numerical_case()
    tiny = Polygon([(.685, -.385), (.6850001, -.385), (.685, -.3849999)])
    assert 0 < tiny.area < 1e-12
    core = box(.69, -.455, .73, -.448)
    result, _ = evaluate(before, MultiPolygon([core, tiny]), foreign)
    assert not result['passed']
    assert any(r.get('gap_mm') == 0. for r in result['failures'])


def test_source_core_removal_still_rejects():
    before, _, foreign = numerical_case()
    result, _ = evaluate(before, box(.70, -.454, .72, -.449), foreign)
    assert not result['passed']
    assert any(r['reason'] == 'ORIGINAL_TRACE_CORE_REMOVED'
               for r in result['failures'])


def test_final_rejection_retains_both_complete_reports(tmp_path, monkeypatch):
    import json
    from test_source_assembly import RAW
    from src.gerber_u05 import pipeline as p, source_assembly
    from src.t04_settings import capture_job
    store = p.Store(tmp_path / 'runtime')
    raw, _ = source_assembly.reconstruct(RAW, store)
    binding = p.build_source(store, raw)
    scene = store.get_json(binding['scene_ref'], kind='scene')
    capture_job(tmp_path)
    p.initialize(store, binding, scene)
    original = PreparedWidthScene.check

    def reject_final(self, rows, **kwargs):
        result = original(self, rows, **kwargs)
        if kwargs.get('materialize_scene'):
            return dict(result, passed=False,
                        failures=[*result['failures'], dict(reason='TEST_FINAL_REJECTION')])
        return result

    monkeypatch.setattr(PreparedWidthScene, 'check', reject_final)
    with pytest.raises(ValueError, match='T04_FRESH_FULL_FINAL_SCENE_REJECTED:') as error:
        p.run_t04(store, scene)
    reference = json.loads(str(error.value).split(':', 1)[1])
    report = store.get_json(reference, kind='width-final-rejection')
    assert report['qualification'] == 'REJECTED_NOT_ACCEPTED'
    assert set(report['checks']) == {'nominal', 'envelope'}
    assert all(not q['passed'] and q['evaluation_complete']
               for q in report['checks'].values())
