import pytest
from shapely import to_wkb
from shapely.affinity import rotate
from shapely.geometry import Point, box
from shapely.ops import unary_union

from src import pin_separation as pin
from src.gerber_u05.t05_pin_check import require_parts
from src.gerber_u05.prefix import worker_prefix_same


def fixture(angle=0):
    transform = lambda g: rotate(g, angle, origin=(0, 0))
    left, right = box(.2, 0, .3, 2), box(.4, 0, .5, 2)
    joint = Point(.25, 1.5).buffer(.08, quad_segs=128)
    source = unary_union([left, right, box(.2, 1.9, .5, 2.1), joint])
    slot = pin.Slot('a' * 64, 'pair', ('left', 'right'),
                    transform(box(.25, -.1, .45, 1.8)), transform(source),
                    (transform(left), transform(right)), ('integral-pad-joint',))
    rule = pin.Rule([slot], construction_gap=.0401, finished_gap=.04)
    return rule, source, left, right, transform


@pytest.mark.parametrize('angle', [0, 17, 90])
def test_complete_projection_matches_union_for_normal_uniform_growth(angle):
    rule, source, left, right, transform = fixture(angle)
    material = [transform(source), transform(left.buffer(.025)),
                transform(right.buffer(.025)), transform(box(10, 10, 11, 11))]
    before = [to_wkb(g) for g in material]
    projected = require_parts(rule, iter(material))
    global_check = rule.require(unary_union(material))
    assert projected['passed'] == global_check['passed'] is True
    assert projected['source_binding'] == global_check['source_binding']
    for a, b in zip(projected['checks'], global_check['checks']):
        assert a['failures'] == b['failures'] == []
        assert a['domain_sha256'] == b['domain_sha256']
        assert a['gap_mm'] == pytest.approx(b['gap_mm'], abs=1e-12)
    assert before == [to_wkb(g) for g in material]
    assert rule.rejected_count == 0 and rule.rejected.is_empty


@pytest.mark.parametrize('y', [.8, 1.79])
def test_new_same_component_bridge_fails_through_complete_transition(y):
    rule, source, _, _, _ = fixture()
    # The original branches already share their remote common attachment.
    # Two separately stored additions together create a new local bridge.
    parts = [source, box(.29, y, .35, y + .001),
             box(.35, y, .41, y + .001)]
    with pytest.raises(ValueError, match='PIN_SEPARATION_T05_COMPLETE_FAILED'):
        require_parts(rule, parts)
    proof = rule.check_parts(parts, finished=True)
    assert 'PIN_BRANCH_LOCAL_BRIDGE' in proof['checks'][0]['failures']


def test_spacing_failure_is_not_replaced_by_connectivity_only():
    rule, source, left, right, _ = fixture()
    with pytest.raises(ValueError, match='PIN_SEPARATION_T05_COMPLETE_FAILED'):
        require_parts(rule, [source, left.buffer(.035), right.buffer(.035)])


def test_existing_integral_joint_and_unrelated_geometry_remain_allowed():
    rule, source, _, _, _ = fixture()
    assert require_parts(rule, [source, box(.18, 1.3, .32, 1.6),
                                box(10, 10, 11, 11)])['passed']


def test_missing_original_branch_is_not_a_projection_skip():
    rule, _, left, _, _ = fixture()
    with pytest.raises(ValueError, match='PIN_SEPARATION_T05_COMPLETE_FAILED'):
        require_parts(rule, [left])


def test_projection_does_not_call_whole_board_union(monkeypatch):
    from src.gerber_u05 import pipeline
    rule, source, _, _, _ = fixture()
    monkeypatch.setattr(pipeline, 'unary_union', lambda _: (_ for _ in ()).throw(
        AssertionError('unrelated whole-board overlay must not run')))
    assert require_parts(rule, [source])['passed']


def worker_pair():
    old = """def compute(run,name):
 value=dict(value,output_scene_ref=store.put_json('scene',scene),pin_separation=pin.ACTIVE.require(p.unary_union(list(material.values())),scope=name+'_complete'))
 return value
"""
    new = """def compute(run,name):
 if name=='t05':p.save(run/'completion_checkpoints'/('t05_'+os.environ.get('U05_WORKER_MODE','unit')+'_geometry.json'),value)
 if name=='t05':
  from .t05_pin_check import require_parts
 value=dict(value,output_scene_ref=store.put_json('scene',scene),pin_separation=(require_parts(pin.ACTIVE,material.values(),scope=name+'_complete')if name=='t05'else pin.ACTIVE.require(p.unary_union(list(material.values())),scope=name+'_complete')))
 return value
"""
    return old, new


def test_prefix_permission_is_limited_to_exact_t05_projection_and_capture():
    old, new = worker_pair()
    assert worker_prefix_same(old, new)['status'] == 'UNCHANGED_UPSTREAM_AST'
    assert worker_prefix_same(new, new)['status'] == 'UNCHANGED_UPSTREAM_AST'


@pytest.mark.parametrize('before,after', [
    ("name=='t05'", "name=='t04'"),
    ('material.values()', 'material_subset.values()'),
    ('scope=name+', 'scope=other+'),
    ('return value', 'return changed_value'),
])
def test_prefix_rejects_other_scope_or_weakened_operand(before, after):
    old, new = worker_pair()
    with pytest.raises(ValueError, match='UPSTREAM_WORKER_CHANGED'):
        worker_prefix_same(old, new.replace(before, after))
