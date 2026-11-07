"""Owner threshold, frozen source union, exact KEEP and deliberate mutations."""
import copy
import json
from unittest.mock import patch
import pytest
from shapely.geometry import Point, box
from shapely import to_wkb
from src.shape_containment import ContainmentIndex, policy as containment_policy
from src.t01_circle_overlap import capture, from_bytes, assess
from src.stage_abi.store import canonical
from src.stage_abi.contracts import StageABIError


def assessment(core, others, settings=None, aliases=()):
    index=ContainmentIndex(dict(target=core,**others))
    return assess(core,index.assess('target',aliases),settings or capture())


@pytest.mark.parametrize('fraction,keep',[(0,False),(.69,False),(.70,False),(.700001,True),(.90,True),(1,True)])
def test_strict_area_boundary_and_preserved_full_containment(fraction,keep):
    # Exact rational rectangle area isolates threshold arithmetic from polygon
    # approximation; callers apply this measurement only to discovered circles.
    core=box(0,0,1,1)
    parent=box(-1,-1,1,2) if fraction==1 else box(0,0,fraction,1)
    result=assessment(core,{'other':parent} if fraction else {})
    assert result['keep'] is keep
    assert result['fully_contained'] is (fraction==1)
    assert result['other_copper_coverage_fraction']==fraction


def test_real_circle_union_coverage_excludes_aliases_without_double_counting():
    circle=Point(0,0).buffer(.15,quad_segs=128)
    assert not assessment(circle,{'alias':circle})['keep']
    left=box(-1,-1,.04,1);right=box(-.04,-1,1,1)
    a=assessment(circle,{'left':left,'right':right,'alias':circle})
    b=assessment(circle,{'right':right,'alias':circle,'left':left})
    assert a==b and a['keep'] and a['fully_contained']
    assert a['excluded_aliases']==['alias','target']
    assert a['other_copper_coverage_fraction']==1
    assert not assessment(circle,{'touch':box(.15,-1,1,1)})['keep']


def test_partial_overlap_is_separate_from_unchanged_containment_and_entry_is_frozen():
    circle=Point(0,0).buffer(.15,quad_segs=128);others={'ribbon':box(-1,-.149,1,.149)}
    index=ContainmentIndex(dict(target=circle,**others))
    old=index.assess('target');others['ribbon']=box(-1,-1,1,1)
    result=assess(circle,old,capture())
    assert not old['contained'] and result['keep'] and not result['fully_contained']
    assert containment_policy()['partial_coverage']=='NOT_CONTAINED'


@pytest.mark.parametrize('bad',[True,-.01,1.01,float('nan'),float('inf'),'0.7'])
def test_bad_provisional_threshold_rejects(bad):
    value=json.loads(capture().raw_json)
    value['maximum_other_copper_coverage_fraction_for_growth']=bad
    with pytest.raises(ValueError):from_bytes(json.dumps(value).encode())


def test_replaceable_global_setting_changes_new_policy_and_rejects_old_policy():
    from src.t01_canonical import marker,require
    from src.t01_board.policy import compile_policy,english
    policy=compile_policy(english(),dict(artifact_id='t01-binding:'+'a'*64,sha256='a'*64))
    value=json.loads(capture().raw_json);value['maximum_other_copper_coverage_fraction_for_growth']=.8
    changed=from_bytes(json.dumps(value).encode())
    with patch('src.t01_canonical.overlap_settings',return_value=changed):
        assert marker()['circle_overlap_settings']['maximum_other_copper_coverage_fraction_for_growth']==.8
        with pytest.raises(StageABIError):require(policy)
    with pytest.raises(ValueError,match='DUPLICATE'):
        from_bytes(capture().raw_json.replace('"revision": 1','"revision": 1, "revision": 2').encode())


def canonical_case():
    from src.t01_canonical import marker,specification,allocate
    core=Point(0,0).buffer(.15,quad_segs=128);ribbon=box(-1,-.149,1,.149)
    roomy=Point(3,0).buffer(.15,quad_segs=128)
    shapes=[core,core,ribbon,roomy]
    rows=[dict(id=s,kind=k,trace_width_mm=0.)for s,k in
          [('target','gr_circle'),('alias','gr_circle'),('ribbon','gr_poly'),('roomy','gr_circle')]]
    sites=[dict(source_id=s,aliases=aliases,indexes=indexes,core=g,center=[x,0],radius=.15,
                enlarged_radius=.225,geometry_sha256='test',physical_contact_group=group)
           for s,aliases,indexes,g,x,group in
           [('target',['target','alias'],[0,1],core,0,'joined'),('roomy',['roomy'],[3],roomy,3,'roomy')]]
    spec=specification();policy=dict(canonical_t01=marker(),family=marker()['family'],
                                   settings=spec['settings'],diameter_classes_mm=spec['diameter_classes_mm'])
    result=allocate(b'',rows,shapes,sites,policy,dict(reviewed_pairs=[],recess_source_ids=[]))
    return rows,shapes,sites,result


def test_allocation_excludes_overlap_from_priorities_pairs_and_growth_but_keeps_inventory():
    rows,shapes,sites,(settings,allocation,targets,square)=canonical_case()
    assert allocation['circle_overlap_keep_source_ids']==['target']
    assert allocation['contained_keep_source_ids']==[]
    assert targets['target']==.15 and targets['roomy']>.15
    assert 'target' not in allocation['priorities_by_physical_component'].values()
    assert next(g for g in allocation['groups']if 'target'in g['site_ids'])['site_ids']==['target']
    assert allocation['priority_pool_source_ids']==['roomy','target'] and not square
    assert allocation['circle_overlap']['target']['excluded_aliases']==['alias','target']
    from src.crop_balanced_t01 import execute
    from src.t01_canonical_surface import SurfaceGuard
    result=execute(b'',rows,shapes,sites,allocation['groups'],allocation['priorities_by_physical_component'],
                   settings=settings,targets=targets,surface_guard=SurfaceGuard(rows,shapes,sites))
    assert to_wkb(result['scene'].accepted['target'])==to_wkb(shapes[0])
    assert result['scene'].accepted['roomy'].area>shapes[3].area


def test_board_adapter_rejects_growth_of_partial_overlap_keep_and_tampered_plan(tmp_path):
    from tests.test_t01_board import environment
    from src.t01_board.adapter import BoardAdapter,PORT_STORE
    from src.t01_board.policy import compile_policy,english
    from src.t01_board.source import context
    store,_,req,_,scene,bref,bounds,_=environment(tmp_path)
    adapter=BoardAdapter();policy=compile_policy(english(),bref)
    sites=context(store,scene,policy)[-1]
    # Nested source circle is fully covered in this fixture. Emulate the new
    # partial-only classification at the shared allocation boundary, while
    # retaining real native planning, core comparison and output construction.
    details=adapter.plan(store,scene,policy,dict(stage='t01',scene_ref=req('x',{})['scene_ref'],
                         source_ids=[s['source_id']for s in sites]),store.get_json(bounds,kind='bounds'))
    sid=details['allocation']['contained_keep_source_ids'][0]
    original_allocate=adapter._allocate
    def partial(*args):
        settings,a,targets,square=original_allocate(*args)
        a['containment'][sid]['contained']=False
        a['contained_keep_source_ids']=[]
        return settings,a,targets,square
    with patch.object(adapter,'_allocate',side_effect=partial):
        token=PORT_STORE.set(store)
        try:details['allocation']=partial(*context(store,scene,policy)[1:],policy,context(store,scene,policy)[0])[1]
        finally:PORT_STORE.reset(token)
        candidate=adapter._compute(store,scene,policy,{'details':details},lambda _:None)
        d=next(d for d in candidate['decisions']if d['source_id']==sid)
        assert d['keep_reason']=='KEEP_OTHER_COPPER_COVERAGE_ABOVE_LIMIT'
        assert d['candidate_ref']==next(r['geometry_ref']for r in scene['objects']if r['source_id']==sid)
        import src.t01_abi.adapter as module
        original_execute=module.execute
        def forged(*args,**kwargs):
            result=original_execute(*args,**kwargs)
            result['scene'].accepted[sid]=next(s['core']for s in sites if s['source_id']==sid).buffer(.001)
            return result
        with patch.object(module,'execute',side_effect=forged):
            with pytest.raises(StageABIError) as caught:
                adapter._compute(store,scene,policy,{'details':details},lambda _:None)
            assert caught.value.code=='T01_OVERLAP_KEEP_SOURCE_CHANGED'
