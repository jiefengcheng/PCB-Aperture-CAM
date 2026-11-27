import pytest
from shapely.geometry import box
from src.gerber_u05.keep_retraction import preserved_copper_conflict
from src.gerber_u05.limiting_math import GUARD
from src.viewer_abi.publisher import encode,digest
from tools.apply_t04_keep_policy import bound_ancestor


@pytest.mark.parametrize('gap',[.04012799675914491,.040116032613384214,.04011591919705588,.0401])
def test_retained_growth_inside_constructor_reserve_still_meets_functional_guard(gap):
    left=box(0,0,1,1);right=box(1+gap,0,2+gap,1)
    assert not preserved_copper_conflict(left.distance(right))


@pytest.mark.parametrize('gap',[.040099,.0400,.0399,0])
def test_real_functional_clearance_failure_is_not_relaxed(gap):
    assert preserved_copper_conflict(gap)


def test_invalid_measurement_cannot_pass():
    for gap in [float('nan'),float('inf'),-1,True]:
        with pytest.raises(ValueError):preserved_copper_conflict(gap)


def test_optional_growth_can_only_come_from_a_hash_bound_ancestor(tmp_path):
    (tmp_path/'session/snapshots').mkdir(parents=True);(tmp_path/'receipts').mkdir()
    def snapshot(revision):
        raw=encode(dict(revision=revision));sha=digest(raw)
        (tmp_path/'session/snapshots'/(sha+'.json')).write_bytes(raw);return sha
    base=snapshot('old');current=snapshot('current');state0=dict(revision='old',event='old-event')
    raw=encode(state0);(tmp_path/'receipts'/(base+'.state.json')).write_bytes(raw)
    state=dict(revision='current',parent_sha256=base,parent_state_sha256=digest(raw))
    assert bound_ancestor(tmp_path,dict(sha256=current),state,base)==(base,state0)
    with pytest.raises(ValueError,match='NOT_COMMITTED_ANCESTOR'):
        bound_ancestor(tmp_path,dict(sha256=current),state,'f'*64)
    (tmp_path/'receipts'/(base+'.state.json')).write_bytes(b'{}')
    with pytest.raises(ValueError,match='LIVE_INPUT_CHANGED'):
        bound_ancestor(tmp_path,dict(sha256=current),state,base)
