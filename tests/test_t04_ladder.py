import copy
import pytest
from shapely.geometry import box,LineString
from shapely.ops import unary_union
from src.t04_settings import capture
from src.t04_ladder import solve,replay
from src.t04_incremental import IncrementalRoutes
from src import component_clearance as cc,source_channel_scope as functional,pin_separation as pin,t04_width_fence as fence
from src.prepared_width_scene import PreparedWidthScene


@pytest.fixture(autouse=True)
def restore_contexts():
    old=cc.ACTIVE,functional.ACTIVE,pin.ACTIVE,fence.ACTIVE
    cc.ACTIVE=functional.ACTIVE=pin.ACTIVE=fence.ACTIVE=None
    yield
    cc.ACTIVE,functional.ACTIVE,pin.ACTIVE,fence.ACTIVE=old


def test_independent_routes_fixed_order_both_caps_and_ten_passes():
    settings=capture();state={'a':1.,'b':1.,'c':1.};calls=[]
    def check(s,f):
        calls.append((s,f,dict(state)))
        ok=s!='a' or f<=1.10
        return dict(passed=ok,failures=[]if ok else[dict(reason='FOREIGN_CLEARANCE')])
    solution=solve(dict(c=.3,b=.05,a=.065),settings,check,lambda s,f:state.update({s:f}))
    assert solution['selected_rungs']==dict(a=2,b=10,c=2)
    assert solution['stable_route_order']==['a','b','c']
    assert len(solution['passes'])==10
    assert all(d['attempts']<=10 for d in solution['decisions'])
    assert [s for s,_,_ in calls[:3]]==['a','b','c']
    assert calls[1][2]['a']==1.05  # Immediate acceptance is visible to next route.
    assert solution['maximum_claim'].startswith('NONE')


def test_stop_early_and_failed_proposal_does_not_publish():
    state={};calls=[]
    def reject(s,f):calls.append((s,f));return dict(passed=False,failures=[dict(reason='PIN_SEPARATION')])
    solution=solve({'b':.05,'a':.05},capture(),reject,lambda s,f:state.update({s:f}))
    assert len(solution['passes'])==1 and len(calls)==2 and not state
    assert solution['selected_rungs']=={'a':0,'b':0}
    assert solution['stop_reason']=='NO_ROUTE_ADVANCED'


def test_fresh_process_proof_replays_attempts_and_rejects_corruption():
    def check(s,f):return dict(passed=f<=1.10,failures=[]if f<=1.10 else[dict(reason='CLEARANCE')])
    settings=capture();widths={'route':.05};solution=solve(widths,settings,check)
    assert replay(widths,settings,solution,check)['complete_ladder_replayed']
    for mutation in ('rung','omit_attempt','width','factor','order'):
        changed=copy.deepcopy(solution)
        if mutation=='rung':changed['selected_rungs']['route']=3
        elif mutation=='omit_attempt':changed['evaluations'].pop()
        elif mutation=='width':changed['decisions'][0]['resulting_width_mm']+=.001
        elif mutation=='factor':changed['selected_scales']['route']=1.111
        else:changed['stable_route_order']=[]
        with pytest.raises(ValueError,match='FRESH_LADDER_REPLAY_CHANGED'):replay(widths,settings,changed,check)


def test_route_local_owner_checks_match_fresh_complete_scene_after_each_attempt():
    widths={'a':.05,'b':.05,'c':.05};ys={'a':0.,'b':.095,'c':.4}
    source={s:LineString([(0,y),(2,y)]).buffer(.025,quad_segs=128)for s,y in ys.items()}
    cc.bind(unary_union(list(source.values())),'1'*64,source)
    base=[dict(id=s,original=g,candidate=g,verified_original_width_mm=.05)for s,g in source.items()]
    def build(s,f,e):return source[s]if f==1 else source[s].buffer(.05*(f-1)/2,quad_segs=128)
    inc=IncrementalRoutes(base,[],build,capture(),widths);full=PreparedWidthScene(base,[]);state=dict.fromkeys(source,1.)
    def evaluate(s,f):
        q=inc.evaluate(s,f);trial=dict(state,**{s:f})
        actual=full.check([dict(id=t,original=source[t],candidate=build(t,trial[t],True),verified_original_width_mm=.05)for t in sorted(source)],fail_fast=True)
        assert q['passed']==actual['passed']
        return q
    def accept(s,f):inc.accept(s,f);state[s]=f
    result=solve(widths,capture(),evaluate,accept)
    assert result['selected_rungs']['c']==10
    assert result['selected_rungs']['a']+result['selected_rungs']['b']<10
    assert inc.diagnostics()['full_scene_checks_during_attempts']==0
    assert inc.diagnostics()['cached_distance_hits']>0


def test_integral_joint_has_no_artificial_internal_clearance():
    trace=box(0,0,2,.05);pad=box(1.9,-.1,2.2,.15);foreign=box(0,.2,2,.25)
    cc.bind(unary_union([trace,pad,foreign]),'2'*64,dict(trace=trace,pad=pad,foreign=foreign))
    baseline=[dict(id='trace',original=trace,candidate=trace,verified_original_width_mm=.05)]
    fixed=[dict(id=s,geometry=g)for s,g in dict(pad=pad,foreign=foreign).items()]
    inc=IncrementalRoutes(baseline,fixed,lambda s,f,e:trace.buffer(.05*(f-1)/2),capture(),{'trace':.05})
    assert inc.evaluate('trace',1.5)['passed']


def test_uniform_route_cannot_close_a_large_empty_pocket_in_same_owner():
    route=LineString([(0,0),(2,0)]).buffer(.04,quad_segs=128)
    rest=LineString([(2,0),(2,2),(0,2),(0,.09)]).buffer(.04,quad_segs=128)
    cc.bind(route.union(rest),'6'*64,dict(route=route,rest=rest))
    baseline=[dict(id='route',original=route,candidate=route,verified_original_width_mm=.08)]
    inc=IncrementalRoutes(baseline,[dict(id='rest',geometry=rest)],
                          lambda s,f,e:route.buffer(.08*(f-1)/2),capture(),{'route':.08})
    assert inc.evaluate('route',1.05)['passed']
    # Larger allowed factors close the remaining opening only when the fixed
    # return path is included: the candidate route itself has no hole.
    candidate=route.buffer(.08*(1.35-1)/2)
    assert not any(p.interiors for p in [candidate])
    check=inc.evaluate('route',1.35)
    assert not check['passed']
    assert any(q['reason']=='NEW_RESOLVABLE_EMPTY_ROUTE_POCKET'for q in check['failures'])


def test_retained_foreign_copper_is_a_real_dependency():
    a=box(0,0,1,.05);b=box(0,.15,1,.2)
    context=cc.bind(unary_union([a,b]),'3'*64,dict(a=a,b=b));own=context.owner('b',b)
    context.reserved={own:box(0,.1,1,.2)}
    base=[dict(id='a',original=a,candidate=a,verified_original_width_mm=.05)]
    inc=IncrementalRoutes(base,[dict(id='b',geometry=b)],lambda s,f,e:a.buffer(.05*(f-1)/2),capture(),{'a':.05})
    assert not inc.evaluate('a',1.5)['passed']


def test_no_logical_fill_can_bypass_frozen_width_decision_after_clipping():
    from src.growth_remedy_constraints import remedy,encoded_remedy
    owner=box(0,0,1,1);denied=box(1,0,1.01,1);fence.ACTIVE=fence.Rule(denied,owner,'binding')
    complete=box(.9,.2,1.02,.3)
    assert not remedy(complete,owner)['passed']
    assert not encoded_remedy(complete,complete.difference(denied),owner)['passed']
    assert remedy(box(.1,.9,.2,1.02),owner)['passed']  # Unrelated corner repair survives.
    with pytest.raises(ValueError,match='BYPASSES_FROZEN_WIDTH'):fence.require(owner.union(complete),scope='reparsed')


def test_width_fence_survives_scene_state_reload(tmp_path):
    from src.stage_abi.store import ArtifactStore
    owner=box(0,0,1,1);fence.ACTIVE=fence.Rule(box(1,0,1.01,1),owner,'binding')
    store=ArtifactStore(tmp_path/'store');state=fence.ACTIVE.state(store)
    fence.restore(store,dict(lineage=[dict(t04_width_fence=state)]))
    assert not fence.remedy(box(.9,0,1.005,.1),owner)['passed']


@pytest.mark.parametrize('skin_mm,passed',[(.000001,True),(.000003,False)])
def test_current_native_grid_duplicate_uses_existing_fidelity_only(skin_mm,passed):
    owner=box(0,0,1,1)
    rule=fence.Rule(box(1,0,1.01,1),owner,'native-grid')
    current=box(0,0,1.005,1) # Independently qualified preceding T05 joint.
    proposal=box(.9,.2,1.005+skin_mm,.8)
    proof=rule.remedy(proposal,current)
    assert proof['passed'] is passed
    assert proof['raw_difference_area_mm2']>0
    assert proof['current_native_fidelity_mm']==.000002


def test_overlapping_dependency_corridors_do_not_forbid_approved_neighbour_growth():
    source=box(0,0,1,.1).union(box(.5,.1,.6,.5))
    approved=source.union(box(.49,.09,.61,.5))
    corridors=box(-.03,-.03,1.03,.13).union(box(.47,.07,.63,.53))
    rule=fence.Rule.from_accepted(corridors,approved,source,'frozen')
    assert rule.remedy(approved,source)['passed']
    assert rule.remedy(box(.2,.099,.3,.105),approved)['passed'] is False


def test_incremental_owner_context_replacement_is_rejected():
    source=box(0,0,1,.05);cc.bind(source,'4'*64,dict(a=source))
    base=[dict(id='a',original=source,candidate=source,verified_original_width_mm=.05)]
    inc=IncrementalRoutes(base,[],lambda s,f,e:source.buffer(.05*(f-1)/2),capture(),{'a':.05})
    cc.bind(source,'4'*64,dict(a=source))
    with pytest.raises(ValueError,match='FROZEN_OWNER_DEPENDENCIES_CHANGED'):inc.evaluate('a',1.05)


@pytest.mark.parametrize('separation,passed',[(.115119,False),(.115121,True)])
def test_prepared_bounds_include_full_conservative_envelope_at_ceiling(separation,passed):
    from src.native_inventory import ERROR_MM
    originals={s:LineString([(0,y),(2,y)]).buffer(.025,quad_segs=128)
               for s,y in [('a',0.),('b',separation)]}
    cc.bind(unary_union(list(originals.values())),'5'*64,originals)
    base=[dict(id=s,original=g,candidate=g,verified_original_width_mm=.05)for s,g in originals.items()]
    def build(s,f,e):return originals[s].buffer(.05*(f-1)/2+(ERROR_MM if e else 0),quad_segs=128)
    inc=IncrementalRoutes(base,[],build,capture(),dict(a=.05,b=.05))
    assert inc.evaluate('b',1.5)['passed'];inc.accept('b',1.5)
    assert inc.evaluate('a',1.5)['passed'] is passed
    complete=PreparedWidthScene(base,[]).check([dict(id=s,original=g,candidate=build(s,1.5,True),verified_original_width_mm=.05)for s,g in originals.items()])
    assert complete['passed'] is passed
