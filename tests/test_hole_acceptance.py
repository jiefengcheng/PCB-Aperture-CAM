import json
import pytest
from shapely.geometry import box
from src import hole_acceptance as policy
from src.t05_trapped_voids import check


@pytest.fixture(autouse=True)
def reset_policy():
    token = policy.ACTIVE.set(policy.STRICT)
    yield
    policy.ACTIVE.reset(token)


def test_captured_policy_survives_registry_changes_and_old_jobs_stay_strict(tmp_path):
    job = tmp_path / 'job'
    job.mkdir()
    policy.capture(job)
    policy.bind(job)
    assert not policy.required()
    policy.bind(tmp_path)
    assert policy.required()


def test_tampered_snapshot_and_protected_separation_override_are_rejected(tmp_path):
    policy.capture(tmp_path)
    path = tmp_path / policy.SNAPSHOT
    data = json.loads(path.read_text())
    data['resolved']['ordinary_holes'] = policy.STRICT
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='SNAPSHOT_CHANGED'):
        policy.bind(tmp_path)
    value = json.loads(policy.REGISTRY.read_text())
    value['protected_separation'] = 'OPTIONAL'
    with pytest.raises(ValueError, match='POLICY_INVALID'):
        policy.decode(json.dumps(value))


def test_relaxed_ordinary_closure_does_not_invoke_source_ancestry_or_fill():
    policy.ACTIVE.set(policy.RELAXED)
    def forbidden(*args):
        raise AssertionError('An accepted hole must not become a fill proposal')
    owner = box(0, 0, 5, 3).difference(box(1, 1, 6, 2))
    candidate = owner.union(box(4, 0, 5, 3))
    result = check(owner, candidate, forbidden, area_epsilon_mm2=1e-12)
    assert result['passed'] and result['ordinary_holes'] == policy.RELAXED


def test_relaxed_t04_hole_predicate_never_reads_source_hole_ancestry():
    from src.t04_topology import SourceVoids, check as topology_check
    policy.ACTIVE.set(policy.RELAXED)
    index = SourceVoids(None, 0)
    assert index.records == [] and index.bytes == 0
    assert topology_check(None, 'route', 1.1, box(0, 0, 1, 1), {}, {})['passed']


def test_native_hole_loss_uses_captured_policy_without_losing_component_checks():
    from src import component_clearance as cc
    from src.gerber_u05.native_component_checks_final import _inventory
    source = box(0, 0, 3, 3).difference(box(1, 1, 2, 2))
    ctx = cc.Context(source, 'a' * 64, {'core': source})
    actual = {ctx.index.ids[0]: box(0, 0, 3, 3)}
    with pytest.raises(ValueError, match='NATIVE_INHERITED_SOURCE_HOLE_REMOVED'):
        _inventory(source, actual, ctx, 'original_owner_id')
    policy.ACTIVE.set(policy.RELAXED)
    result = _inventory(source, actual, ctx, 'original_owner_id')
    assert result['passed'] and result['source_hole_survival'] == []
    assert result['new_resolvable_empty_pockets'] == 'NOT_REQUIRED'


def test_relaxed_holes_do_not_exempt_same_net_pin_bridge():
    from src.pin_separation import Slot, Rule
    policy.ACTIVE.set(policy.RELAXED)
    left, right = box(.2, 0, .3, 2), box(.4, 0, .5, 2)
    source = left.union(right).union(box(.2, 1.9, .5, 2.1))
    slot = Slot('a' * 64, 'pair', ('left', 'right'),
                box(.25, -.1, .45, 1.8), source, (left, right), ())
    rule = Rule([slot], construction_gap=.0401, finished_gap=.04)
    assert rule.check(source)['passed']
    assert not rule.check(source.union(box(.29, .8, .41, .801)))['passed']


def test_relaxed_hole_fill_still_has_twenty_percent_limit():
    from src.component_voids import proposal_check, RemedyContract
    policy.ACTIVE.set(policy.RELAXED)
    patch = box(.5, .5, 2.5, 2.5)
    owner = box(0, 0, 3, 3).difference(patch)
    result = proposal_check(patch, owner, owner, [], RemedyContract())
    assert not result['passed'] and 'SHORTAGE_ABOVE_20_PERCENT' in result['reasons']
