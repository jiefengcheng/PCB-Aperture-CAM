import random
import pytest
from shapely.geometry import Point
from shapely import to_wkb
from src.u03_board.assembly import GroupCandidateAssembly


class Model:
    chains = {'a': {}, 'b': {}, 'c': {}}
    assignment = {'a': 'pair', 'b': 'pair', 'c': 'single'}
    group_ids = {'pair', 'single'}
    def __init__(self): self.calls = []; self.fail = False
    def construct(self, sid, factor):
        self.calls.append((sid, factor))
        if self.fail and sid == 'b': raise ValueError('construction failure')
        g = Point(ord(sid), 0).buffer(factor)
        return {'verified_original_width_mm': .1}, {}, {}, g, g, g


def signature(rows):
    return [(r['id'], to_wkb(r['original']), to_wkb(r['candidate']), r['verified_original_width_mm']) for r in rows]


def test_updates_complete_groups_and_preserves_prior_trials():
    m=Model();a=GroupCandidateAssembly(m);base={'pair':1.,'single':1.}
    first=a.traces(base);before=signature(first);m.calls.clear()
    a.traces(dict(base,pair=1.25));assert m.calls==[('a',1.25),('b',1.25)]
    assert signature(first)==before
    m.calls.clear();a.traces(base);assert m.calls==[('a',1.),('b',1.)]
    m.calls.clear();a.traces(base);assert m.calls==[]
    m.fail=True
    with pytest.raises(ValueError,match='construction failure'):a.traces(dict(base,pair=1.5))
    assert a.scales==base and signature(a.rows)==before


@pytest.mark.parametrize('bad',[{}, {'pair':1.,'single':1.,'extra':1.},
    {'pair':True,'single':1.},{'pair':float('nan'),'single':1.},
    {'pair':float('inf'),'single':1.},{'pair':1.500001,'single':1.}, {'pair':.999,'single':1.}])
def test_invalid_vectors_never_update_state(bad):
    a=GroupCandidateAssembly(Model())
    with pytest.raises(ValueError):a.traces(bad)
    assert a.scales=={} and a.calls==0


def test_random_trial_rejection_rollback_and_final_proof_vectors_match_fresh_assembly():
    m=Model();a=GroupCandidateAssembly(m);rng=random.Random(4)
    vectors=[{'pair':1.,'single':1.}]
    for _ in range(60):vectors.append({g:rng.choice([1.,1.125,1.25,1.5]) for g in m.group_ids})
    vectors.extend([vectors[0],vectors[-1],vectors[0]])
    for scales in vectors:
        reference=[]
        for sid in sorted(m.chains):
            r,_,_,core,_,envelope=m.construct(sid,scales[m.assignment[sid]])
            reference.append(dict(id=sid,original=core,candidate=envelope,verified_original_width_mm=r['verified_original_width_mm']))
        assert signature(a.traces(scales))==signature(reference)
