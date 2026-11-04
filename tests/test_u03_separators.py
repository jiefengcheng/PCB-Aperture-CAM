"""Exact report/solver parity and stale-state rejection for local computation."""
from dataclasses import FrozenInstanceError,replace
import random
import pytest
from shapely.geometry import LineString,Point,box
from shapely import STRtree
from shapely.affinity import translate
from src.u03_board.assembly import GroupCandidateAssembly,CandidateSnapshot,CandidateTrace
from src.u03_board.separators import SeparatorWidthScene,PartitionMap
from src.u03_board.source_union import SourceUnionWidthScene
from src.u03_board.solver import solve


class Model:
    def __init__(self,n=8):
        self.chains={str(i):{} for i in range(n)};self.assignment={s:'group'+s for s in self.chains};self.group_ids=set(self.assignment.values())
        self.cores={s:LineString([(0,int(s)*.16),(1,int(s)*.16)]).buffer(.05) for s in self.chains};self.calls=0
    def construct(self,sid,f):
        self.calls+=1;g=self.cores[sid];candidate=g if f==1 else g.buffer(.05*(f-1))
        return dict(verified_original_width_mm=.1),{},{},g,candidate,candidate
    def baseline(self):
        return [dict(id=s,original=g,candidate=g,verified_original_width_mm=.1) for s,g in self.cores.items()]


def test_snapshot_and_previous_partition_states_are_immutable():
    m=Model();a=GroupCandidateAssembly(m);v=dict.fromkeys(m.group_ids,1.);snap=a.traces(v)
    with pytest.raises(TypeError):snap[0]['candidate']=Point(50,50).buffer(.1)
    with pytest.raises(FrozenInstanceError):snap[0].candidate=Point(50,50).buffer(.1)
    with pytest.raises(FrozenInstanceError):snap.rows=()
    c=SeparatorWidthScene(m.baseline(),[],groups=m.assignment,separator_leaf_limit=2,union_workers=0)
    assert c.check(snap,fail_fast=True)['passed'];old=c.state;old_current=dict(old.current)
    c.check(a.traces(dict(v,group0=1.5,group1=1.5)),fail_fast=True)
    assert dict(old.current)==old_current
    assert c.check(snap,fail_fast=True)['passed'];c.close()


@pytest.mark.parametrize('budget',[0,2048,16*1024**2])
def test_complete_reports_match_with_separator_changes_rejections_rollbacks_and_full_closure(budget):
    m=Model();a=GroupCandidateAssembly(m);base=dict.fromkeys(m.group_ids,1.);rng=random.Random(71)
    old=SourceUnionWidthScene(m.baseline(),[],groups=m.assignment,union_workers=0)
    new=SeparatorWidthScene(m.baseline(),[],groups=m.assignment,separator_leaf_limit=2,condition_budget=budget,union_workers=0)
    vectors=[base,dict(base,group0=1.5),dict(base,group0=1.5,group1=1.5),base]
    vectors += [{g:rng.choice([1.,1.1,1.25,1.5]) for g in m.group_ids} for _ in range(80)]
    for v in vectors:
        snap=a.traces(v);assert new.check(snap,fail_fast=True)==old.check(snap,fail_fast=True)
        assert new.local_proofs.weight<=budget
    snap=a.traces(base)
    assert new.check(snap,materialize_scene=True)==old.check(snap,materialize_scene=True)
    assert new.local_proofs.weight==0 and new.pool is None
    assert new.check(snap,fail_fast=True)==old.check(snap,fail_fast=True)
    new.close();old.close()


def test_delta_validates_all_changed_rows_and_keeps_checks_for_mutable_inputs():
    m=Model(3);a=GroupCandidateAssembly(m);base=dict.fromkeys(m.group_ids,1.);snap=a.traces(base)
    c=SeparatorWidthScene(m.baseline(),[],groups=m.assignment,union_workers=0)
    c.check(snap,fail_fast=True);before=c.validated_rows
    c.check(a.traces(dict(base,group0=1.1)),fail_fast=True)
    assert c.validated_rows==before+1 and c.reused_rows>=2
    bad=list(snap.rows);bad[1]=replace(bad[1],verified_original_width_mm=.2)
    with pytest.raises(ValueError,match='BINDING_CHANGED'):c.check(CandidateSnapshot(tuple(bad)),fail_fast=True)
    bad=list(snap.rows);bad[1]=replace(bad[1],id='0')
    with pytest.raises(ValueError,match='IDENTITIES_CHANGED'):c.check(CandidateSnapshot(tuple(bad)),fail_fast=True)
    mutable=[dict(r) for r in snap];c.check(mutable,fail_fast=True);mutable[1]['verified_original_width_mm']=.3
    with pytest.raises(ValueError,match='BINDING_CHANGED'):c.check(mutable,fail_fast=True)
    c.contract=replace(c.contract,hard_gap_mm=.01)
    with pytest.raises(ValueError,match='POLICY_CHANGED'):c.check(snap,fail_fast=True)
    c.close()


def test_local_spatial_views_match_exact_indexes_and_out_of_domain_falls_back():
    m=Model();a=GroupCandidateAssembly(m);base=dict.fromkeys(m.group_ids,1.);rng=random.Random(17)
    c=SeparatorWidthScene(m.baseline(),[],groups=m.assignment,separator_leaf_limit=2,union_workers=0)
    for k in range(15):
        v={g:rng.choice([1.,1.1,1.4]) for g in m.group_ids};c.check(a.traces(v),fail_fast=True)
        state=c.state;view=c.spatial_index(state.current);exact=STRtree([state.current[s] for s in c.ids])
        for _ in range(20):
            x,y=rng.uniform(-.1,1.1),rng.uniform(-.1,1.5);q=box(x,y,x+.05,y+.05)
            assert set(view.query(q))==set(exact.query(q))
        if k==0:old_state=state;old_view=view
    assert c.spatial_index(old_state.current).query(box(-1,-1,2,2)).size==old_view.query(box(-1,-1,2,2)).size
    snap=a.traces(base);bad=list(snap.rows);bad[0]=replace(bad[0],candidate=translate(bad[0].original,xoff=5))
    reference=SourceUnionWidthScene(m.baseline(),[],groups=m.assignment,union_workers=0)
    for v in (snap,CandidateSnapshot(tuple(bad)),snap):
        # Compare from equal accepted-state authority after a full reset.
        if v is snap:
            c.check(v,materialize_scene=True);reference.check(v,materialize_scene=True)
        assert c.check(v,fail_fast=True)==reference.check(v,fail_fast=True)
    assert c.index_fallbacks>0;c.close();reference.close()


def test_unchanged_solver_and_full_native_geometry_checks_match_exactly():
    m=Model(5);base=m.baseline();answers=[]
    for cls in (SourceUnionWidthScene,SeparatorWidthScene):
        c=cls(base,[],groups=m.assignment,union_workers=0);assembly=GroupCandidateAssembly(m);reports=[]
        def evaluate(v):
            q=c.check(assembly.traces(v),fail_fast=True);reports.append(q);return q
        solution=solve(m.group_ids,evaluate)
        final=c.check(assembly.traces(solution['selected_scales']),materialize_scene=True)
        answers.append((solution,reports,final));c.close()
    assert answers[0]==answers[1]


def test_conditioned_certificates_are_hash_checked_and_source_bound():
    m=Model(3);a=GroupCandidateAssembly(m);v=dict.fromkeys(m.group_ids,1.)
    c=SeparatorWidthScene(m.baseline(),[],groups=m.assignment,separator_leaf_limit=1,union_workers=0)
    c.check(a.traces(v),fail_fast=True);q=c.check(a.traces(dict(v,group0=1.1)),fail_fast=True)
    assert q['passed'] and c.local_proofs.entries
    c.check(a.traces(v),fail_fast=True)
    for key,(proof,weight) in list(c.local_proofs.entries.items()):c.local_proofs.entries[key]=(replace(proof,payload=b'{}'),weight)
    with pytest.raises(ValueError,match='CERTIFICATE_CHANGED'):c.check(a.traces(dict(v,group0=1.1)),fail_fast=True)
    c.close()
