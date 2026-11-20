import copy
import hashlib
import json
import pytest
from shapely import to_wkb
from shapely.geometry import box
from src.gerber_u05.profile_floor import CopperFloor, SCHEMA
from src.gerber_u05.profile_schedule import solve, SCHEDULE
from src.t04_settings import capture


def example():
    raw = to_wkb(box(0, 0, 1, .05))
    sha = hashlib.sha256(raw).hexdigest()
    seed = dict(schema=SCHEMA, source_sha256='source', input_scene_sha256='scene',
                reference_only=True, proof_reuse=False, routes={'r': dict(sha256=sha)}, bulk={})
    binding = dict(source_sha256='source', scene_ref=dict(sha256='scene'))
    return seed, raw, binding


def test_floor_is_source_bound_and_geometry_only():
    seed, raw, binding = example()
    floor = CopperFloor(json.dumps(seed).encode(), lambda q: raw)
    _, bodies, bulk = floor.load(binding, {'r': ['s']})
    assert bodies['r'].equals_exact(box(0, 0, 1, .05), 0) and not bulk
    for key, value in [('source_sha256', 'other'), ('proof_reuse', True), ('reference_only', False)]:
        changed = dict(seed, **{key: value})
        with pytest.raises(ValueError, match='BINDING_CHANGED'):
            CopperFloor(json.dumps(changed).encode(), lambda q: raw).load(binding, {'r': ['s']})


def test_changed_body_or_missing_route_cannot_reuse_a_floor():
    seed, raw, binding = example()
    with pytest.raises(ValueError, match='GEOMETRY_CHANGED'):
        CopperFloor(json.dumps(seed).encode(), lambda q: to_wkb(box(0, 0, 1, .06))).load(binding, {'r': ['s']})
    with pytest.raises(ValueError, match='BINDING_CHANGED'):
        CopperFloor(json.dumps(seed).encode(), lambda q: raw).load(binding, {'r': ['s'], 'neighbor': ['n']})


def test_floor_adapter_rejects_path_traversal(tmp_path):
    seed, raw, binding = example()
    seed['routes']['r']['file'] = '../escape.wkb'
    path = tmp_path/'floor.json'
    data = json.dumps(seed).encode();path.write_bytes(data)
    floor = CopperFloor.saved(path, hashlib.sha256(data).hexdigest())
    with pytest.raises(ValueError, match='PATH_INVALID'):
        floor.load(binding, {'r': ['s']})


def test_profile_ladder_rechecks_a_rejection_after_neighbor_updates():
    settings = capture()
    calls = []
    def evaluate(route, factor):
        calls.append((route, factor))
        passed = route == 'b' or len([r for r, f in calls if r == 'a']) > 1
        return dict(passed=passed, failures=[] if passed else [dict(reason='MUTABLE_NEIGHBOR')])
    selected = {}
    result = solve({'a': .05, 'b': .05}, settings, evaluate, lambda r, f: selected.update({r: f}), pass_increments=SCHEDULE)
    assert calls[:3] == [('a', 1.05), ('b', 1.05), ('a', 1.05)]
    assert result['pass_increments'] == list(SCHEDULE) and selected['a'] > 1
    with pytest.raises(ValueError, match='SCHEDULE_CHANGED'):
        solve({'a': .05}, settings, evaluate, lambda *a: None, pass_increments=[2]*5)
