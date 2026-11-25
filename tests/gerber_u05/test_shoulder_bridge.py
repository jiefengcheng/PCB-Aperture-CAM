import numpy as np
from shapely.geometry import LineString, Polygon, box
from shapely.ops import unary_union
from src.gerber_u05.shoulder_bridge import run,steps,patch,complete_contact
from src.gerber_u05.boundary_finish import sharp_points


def straight():
    points=[[-1.,0.],[1.,0.]]
    rows={'s':dict(metadata=dict(route_points_mm=points,route_kind='segment',minimum_caliper_mm=.1))}
    floor={'s':LineString(points).buffer(.05,quad_segs=128)}
    body={'s':floor['s'].union(box(-.8,-.065,0,.065))}
    return rows,{'r':['s']},body,floor,{'s':.13}


def prepare(plans,forbidden=Polygon()):
    return {i:dict(forbidden=forbidden,context=Polygon(),neighbors=[])for i,p in enumerate(plans)},dict(queries=0)


def test_additive_steps_are_found_without_an_arc_or_catalogue_seam():
    rows,paths,before,floor,caps=straight()
    after,changes,_,q=run(rows,paths,before,floor,caps,prepare=prepare)
    assert q['smoothed']>=2
    assert not before['s'].difference(after['s']).area
    assert after['s'].area>before['s'].area
    assert changes and not q['complete_board_unions'] and not q['scene_indexes_built']
    assert all(r['profile']['maximum_materialized_alignment_angle_degrees']<=10 for r in q['reports']if r['status']=='BRIDGED')
    # The two corners on each original step disappear, rather than moving the
    # same discontinuity to another end of a shortened widening section.
    assert not [p for p in sharp_points(after['s'],floor['s'],10)if abs(p[0])<.3]


def test_step_on_native_bend_is_discovered_without_requiring_parallel_edges():
    body=Polygon([[-.2,-.1],[.2,-.1],[.2,.01],[0,.01],[0,0],[-.2,.1]])
    floor=box(-.2,-.1,.2,-.08)
    assert any(np.linalg.norm(np.asarray(s['point_mm'])-[0,.005])<1e-9 for s in steps(body,floor))
    assert not steps(body,body)


def test_prepared_foreign_barrier_rejects_addition_and_retains_exact_wkb():
    rows,paths,before,floor,caps=straight()
    after,_,_,q=run(rows,paths,before,floor,caps,prepare=lambda p:prepare(p,box(-2,-2,2,2)))
    assert not q['smoothed'] and q['unresolved']
    assert after['s'].wkb==before['s'].wkb
    for record in q['reports']:
        if record['status']=='UNRESOLVED'and record.get('attempts'):
            assert set(record['rejection_counts'])=={reason for a in record['attempts']for reason in a['reasons']}


def test_local_finishing_rejects_runaway_proposals_instead_of_searching(monkeypatch):
    import pytest
    import src.gerber_u05.shoulder_bridge as module
    rows,paths,before,floor,caps=straight()
    def runaway(plan,image,required,angle):
        while True:
            yield dict(image=image,domain=plan['repair_domain'],proof={})
    monkeypatch.setattr(module,'edge_profile_variants',runaway)
    with pytest.raises(ValueError,match='LOCAL_SHOULDER_PROPOSAL_BOUND_EXCEEDED'):
        run(rows,paths,before,floor,caps,prepare=prepare)


def test_repair_does_not_copy_neighbour_skin_into_an_unrelated_carrier(tmp_path):
    from src.shared_copper_context import CopperContext
    from src.gerber_u05.boundary_prepare import supports,shoulder_dependencies
    rows,paths,before,floor,caps=straight()
    points=[[.3,.03],[.8,.03]]
    rows['peer']=dict(metadata=dict(route_points_mm=points,route_kind='segment',minimum_caliper_mm=.1))
    paths['peer-route']=['peer'];floor['peer']=LineString(points).buffer(.05,quad_segs=128)
    before['peer']=LineString(points).buffer(.065,quad_segs=128);caps['peer']=.13
    with CopperContext(floor,source_binding=dict(source='carrier-assignment'),frame=dict(units='mm'),root=tmp_path/'prepared')as context:
        contacts=supports(rows,paths,floor,context.source,with_sources=True,admitted=before)
        after,_,_,report=run(rows,paths,before,floor,caps,supports=contacts,
            review_bounds=[[-.2,-.2,.2,.2]],prepare=lambda p:shoulder_dependencies(p,before,context.source,native_ids=set(rows)))
    assert report['smoothed'] and after['s'].area>before['s'].area
    assert after['peer'].wkb==before['peer'].wkb


def test_covered_and_nominally_ineligible_sources_are_never_modified():
    rows,paths,before,floor,caps=straight()
    after,_,_,q=run(rows,paths,before,floor,caps,covered=['s'],prepare=prepare)
    assert not q['reports'] and after['s'].wkb==before['s'].wkb


def test_original_pad_neck_without_admitted_widening_stays_for_t05():
    rows,paths,before,floor,caps=straight();floor=dict(before)
    after,_,_,q=run(rows,paths,before,floor,caps,prepare=prepare)
    assert not q['reports'] and after['s'].wkb==before['s'].wkb


def test_local_contact_completion_is_additive_and_checks_actual_union():
    before=box(-1,-.05,1,.05).union(box(.2,.05,1,.4))
    reference=LineString([[-.1,.05],[.3,.05]]).buffer(.01,quad_segs=128)
    added,proof=complete_contact(before,reference,10)
    after=before.union(added)
    assert not before.difference(after).area
    assert not sharp_points(after,before,10)
    assert not proof['new_shoulders']


def test_exact_empty_and_mixed_dimension_area_predicate():
    from shapely.geometry import GeometryCollection
    from src.gerber_u05.shoulder_bridge import overlap_area
    mixed=GeometryCollection([box(0,0,1,1),LineString([(3,0),(4,0)])])
    assert overlap_area(mixed,Polygon())==0
    assert overlap_area(mixed,box(3,-1,4,1))==0
    assert overlap_area(mixed,box(.5,.5,2,2))==.25


def test_local_recession_cannot_borrow_gain_from_a_remote_window():
    from src.gerber_u05.shoulder_bridge import local_variants
    image=box(0,0,1,.1);required=box(0,0,1,.05)
    remote=box(10,0,11,1)
    domain=box(.4,-.1,.6,.2)
    for variant in local_variants(image,required,remote,Polygon(),10,domain=domain):
        assert variant['removed'].difference(domain).is_empty
        assert variant['added'].area>=variant['removed'].area
        assert required.difference(variant['image']).area==0


def test_native_window_keeps_the_existing_frame_instead_of_inventing_end_kinks():
    import pytest
    from src.gerber_u05.ribbon_profile import frame,window_frame
    from src.gerber_u05.boundary_finish import materialize,AlignmentRejected
    theta=np.linspace(0,np.pi/2,101)
    points=np.column_stack((.3*np.cos(theta),.3*np.sin(theta))).tolist()
    _,_,stations,_=frame(points)
    first=float(stations[np.argmin(abs(stations-.08))]-1e-7)
    last=float(stations[np.argmin(abs(stations-.36))]+1e-7)
    p,n,t,length=window_frame(points,first,last)
    floor=LineString(points).buffer(.025,quad_segs=128);original=floor.wkb
    local=dict(points=p.tolist(),width=.05,floor=floor,stations=t,
               values=np.full((len(t),2),.01),local_controls=True)
    # Resetting normals on the tiny remainder of the first/last chord causes
    # a false fold. The inherited frame gives the actual native curved rails.
    with pytest.raises(AlignmentRejected):materialize(local,1.,np.tan(np.radians(10)))
    local['native_frame']=dict(points=points,interval_mm=[first,last])
    image,proof=materialize(local,1.,np.tan(np.radians(10)))
    assert proof['maximum_materialized_alignment_angle_degrees']<=10
    assert floor.difference(image).area<=1e-12
    assert floor.wkb==original and not image.is_empty and image.is_valid


def test_only_nearby_prepared_repairs_can_share_actual_copper_gain():
    from src.gerber_u05.bridge_budget import NeighborhoodBudget
    plans=[dict(record=dict(point_mm=p,primary_source_id=s))for p,s in[([0,0],'a'),([0,.2],'b'),([5,5],'remote')]]
    local={0:dict(neighbors=['b']),1:dict(neighbors=['a']),2:dict(neighbors=[])}
    budget=NeighborhoodBudget(plans,local)
    assert not budget.allows(1,-.001)
    budget.commit(0,.003)
    assert budget.allows(1,-.001) and not budget.allows(2,-.001)
    budget.commit(1,-.001)
    assert not budget.allows(1,-.003)
    assert budget.receipt()['passed']


def test_budget_does_not_join_unrelated_or_transitively_remote_repair_sites():
    from src.gerber_u05.bridge_budget import NeighborhoodBudget
    plans=[dict(record=dict(point_mm=[x,0],primary_source_id=str(i)))for i,x in enumerate((0,.2,.4))]
    local={i:dict(neighbors=['0','1','2'])for i in range(3)}
    budget=NeighborhoodBudget(plans,local)
    budget.commit(0,1.)
    assert budget.allows(1,-.1) and not budget.allows(2,-.1)


def test_exposed_rail_mode_still_rejects_real_curvature_angle_excess():
    import pytest
    from src.gerber_u05.ribbon_profile import frame
    from src.gerber_u05.boundary_finish import materialize,AlignmentRejected
    theta=np.linspace(0,np.pi/2,51)
    points=np.column_stack((.1*np.cos(theta),.1*np.sin(theta))).tolist()
    _,_,t,length=frame(points)
    # Each scalar side slope is below ten degrees, and the total width is
    # below 1.5x. The exposed inner curved rail still exceeds ten degrees.
    values=np.column_stack([np.zeros(len(t)),.015*t/length])
    chain=dict(points=points,width=.04,floor=LineString(points).buffer(.02,quad_segs=128),
               stations=t,values=values,exposed_controls=True)
    with pytest.raises(AlignmentRejected):materialize(chain,1.,np.tan(np.radians(10)))


def test_prepared_editable_contacts_do_not_cross_a_fill_to_another_trace(tmp_path):
    from src.shared_copper_context import CopperContext
    from src.gerber_u05.boundary_prepare import shoulder_dependencies
    # Both horizontal traces have one physical owner through the vertical
    # fill. Only the lower chain and its directly touching branch may edit
    # one another's local widening. Ownership alone is insufficient.
    material=dict(chain=box(-.5,-.025,.5,.025),
                  branch=box(-.02,0,.02,.12),
                  parallel=box(-.5,.2,.5,.25),
                  fill=box(-.5,-.1,-.4,.3))
    material['alias']=material['chain']
    plan=dict(patch=box(0,.02,.05,.04),chain=dict(source_ids=['chain']),
              native_seed_sources=['chain'])
    with CopperContext(material,source_binding=dict(source='local-contacts'),
                       frame=dict(units='mm'),root=tmp_path/'prepared')as context:
        revision=context.source
        assert revision.membership['chain']==revision.membership['parallel']
        local,_=shoulder_dependencies([plan],material,revision,
                    native_ids={'chain','branch','parallel','alias'})
        assert set(local[0]['native_contact_sources'])=={'chain','branch','alias'}
        assert 'parallel'in local[0]['native_sources']
        assert context.stats['source_index_builds']==1


def test_curve_alignment_uses_original_axis_and_rejects_steep_edges():
    from src.gerber_u05.boundary_curve_bridge import alignment
    axis=LineString([(0,0),(1,0)])
    assert alignment(np.array([[0,.02],[1,.02]]),axis,(0,0),native=True)==0
    # Axis orientation does not change the physical slope.
    reverse=LineString([(1,0),(0,0)])
    assert alignment(np.array([[0,.02],[1,.02]]),reverse,(0,0),native=True)==0
    assert alignment(np.array([[0,0],[1,.2]]),axis,(0,0),native=True)>10


def test_straight_limit_does_not_shrink_an_admitted_bend_end():
    from src.gerber_u05.shoulder_bridge import source_interval_caps
    chain=dict(width=.05,source_intervals=[(0.,.4,'arc'),(.4,1.,'straight')])
    limits=source_interval_caps(chain,dict(arc=.075,straight=.065),np.array([.2,.6,.9]),.015)
    np.testing.assert_allclose(limits,[.025,.015,.015],atol=1e-16)
    # The former whole-chain minimum assigned .015 to the arc as well.
    assert limits[0]>.015


def test_endpoint_requirements_are_propagated_before_slope_limiting():
    from src.gerber_u05.shoulder_bridge import retain_endpoint_fields
    from src.gerber_u05.boundary_finish import minorant
    stations=np.array([0.,.1,.2,.3]);rates=np.full(3,.1)
    old=np.full((4,2),.01);goals=np.full((4,2),.002)
    values=retain_endpoint_fields(goals,old,np.full((4,2),.02),np.full(4,.025),rates,stations)
    values[0]=old[0];values[-1]=old[-1]
    chain=dict(values=values,stations=stations,rates=rates);minorant(chain)
    np.testing.assert_allclose(values[[0,-1]],old[[0,-1]],atol=1e-15)
    assert np.all(values.sum(axis=1)<=.025)
    # A short interval cannot silently lower its retained end sections to
    # accommodate a middle obstruction. It needs different bridge ends.
    old=np.array([[.01,.01],[0.,0.],[.01,.01]])
    result=retain_endpoint_fields(np.zeros((3,2)),old,old,np.full(3,.02),
                                 np.full(2,.1),np.array([0.,.001,.002]))
    assert result is None


def test_tiny_shoulder_gets_a_local_curve_instead_of_replacing_the_bend():
    from src.gerber_u05.boundary_curve_bridge import variants
    image=box(-.1,-.025,0,.0255).union(box(0,-.025,.1,.025))
    floor=box(-.1,-.025,.1,.024)
    step=min(steps(image,floor),key=lambda s:abs(s['point_mm'][0]))
    previous=image.wkb
    candidate,proof,domain=next(variants(image,step,10,native_axis=LineString([(-.1,0),(.1,0)])))
    assert proof['length_mm']<.02
    assert proof['maximum_materialized_alignment_angle_degrees']<=10
    assert candidate.is_valid and image.wkb==previous
    assert candidate.symmetric_difference(image).difference(domain).area==0


def test_internal_drawing_end_does_not_extend_its_tighter_cap_over_the_bend():
    from src.gerber_u05.shoulder_bridge import native_continuation,width_barrier
    from shapely.geometry import Point
    rows={s:dict(metadata=dict(route_points_mm=points,minimum_caliper_mm=.05))for s,points in
          dict(bend=[[-.3,0],[0,0]],straight=[[0,0],[.3,0]]).items()}
    assert native_continuation(rows,['bend','straight'],'straight',0)
    assert not native_continuation(rows,['straight'],'straight',0)
    # A duplicate occurrence points inward from the same end; it is not a
    # continuation beyond that end and cannot exempt a real terminal cap.
    rows['alias']=rows['straight']
    assert not native_continuation(rows,['straight','alias'],'straight',0)
    skin=box(-.3,-.0275,0,.0275).union(box(0,-.0325,.3,.0325))
    barrier=width_barrier(rows,['bend','straight'],skin,dict(point_mm=[-.04,.028]),
                         box(-.2,-.1,.2,.1),dict(bend=.075,straight=.065))
    assert not barrier.covers(Point(-.04,.043))


def test_flexible_end_repair_is_primary_and_never_gated_by_a_fixed_seed(monkeypatch):
    import src.gerber_u05.shoulder_bridge as module
    rows,paths,before,floor,caps=straight()
    def unavailable(*a,**k):raise AssertionError('fixed seed was consulted')
    monkeypatch.setattr(module,'patch',unavailable)
    after,changes,_,report=run(rows,paths,before,floor,caps,prepare=prepare)
    assert changes and report['smoothed']
    assert all(r['repair_principle']=='FLEXIBLE_ENDS_PRIMARY'for r in report['reports'])
    assert before['s'].area<=after['s'].area+1e-12
    assert floor['s'].difference(after['s']).area<1e-12


def test_saved_contact_widening_is_not_mistaken_for_original_floor():
    rows,paths,before,floor,caps=straight()
    # A second saved source carries this chain's widening as well as its own
    # distant original copper. It is retained context, not an original floor
    # which can make the still-visible step disappear from verification.
    rows['peer']=dict(metadata=dict(route_points_mm=[[3.,0.],[4.,0.]],
        route_kind='segment',minimum_caliper_mm=.1))
    floor['peer']=LineString([[3.,0.],[4.,0.]]).buffer(.05,quad_segs=128)
    before['peer']=before['s'].union(floor['peer'])
    def prepared(plans):
        return {i:dict(forbidden=Polygon(),context=before['peer'],
            operands={'s':before['s'],'peer':before['peer']},neighbors=['peer'])
            for i in range(len(plans))},dict(queries=0)
    after,changes,_,report=run(rows,paths,before,floor,caps,prepare=prepared)
    assert report['smoothed']>=2 and changes
    assert before['s'].difference(after['s']).area==0
    assert after['peer'].wkb==before['peer'].wkb
    assert all(r['status']!='RESOLVED_BY_COUPLED_BRIDGE'for r in report['reports'])


def test_both_bridge_ends_move_when_the_additive_end_pair_is_blocked():
    rows,paths,before,floor,caps=straight()
    barrier=box(.001,.059,.03,.1)
    after,changes,_,report=run(rows,paths,before,floor,caps,
        prepare=lambda plans:prepare(plans,barrier))
    moved=[r for r in report['reports']if r['status']=='BRIDGED'and
        r['profile'].get('left_reach_mm',0)>0 and
        r['profile'].get('right_reach_mm',0)>0]
    assert moved and changes and not report['unresolved']
    assert any(r['removed_area_mm2']>1e-12 for r in moved)
    assert all(r['net_growth_area_mm2']>=-1e-12 for r in moved)
    assert after['s'].area>=before['s'].area
    assert floor['s'].difference(after['s']).area==0
    assert after['s'].difference(before['s']).intersection(barrier).area==0
    assert report['copper_budgets']['passed']
    assert all(r['profile']['maximum_materialized_alignment_angle_degrees']<=10
        for r in moved)


def test_junction_classification_does_not_block_flexible_boundary_ends():
    from src.gerber_u05.shoulder_bridge import edge_profile_variants
    from shapely.geometry import Point
    rows,paths,before,floor,caps=straight()
    step=min(steps(before['s'],floor['s']),key=lambda s:Point(s['point_mm']).distance(Point(0,0)))
    plan=dict(record=dict(point_mm=step['point_mm'],height_mm=step['height_mm'],
        primary_source_id='s'),junction=box(-2,-2,2,2),
        batch=dict(chains=[dict(source_ids=['s'],line=LineString([[-1,0],[1,0]]))]))
    candidate=next(edge_profile_variants(plan,before['s'],floor['s'],10))
    assert candidate['proof']['maximum_materialized_alignment_angle_degrees']<=10
    assert candidate['added'].area>0


def test_partial_contact_rounding_does_not_require_old_vertices_to_survive():
    from src.gerber_u05.boundary_curve_bridge import variants
    from shapely.geometry import Point
    rows,paths,before,floor,caps=straight()
    step=min(steps(before['s'],floor['s']),key=lambda s:abs(s['point_mm'][0]))
    current=before['s'].buffer(.02,quad_segs=128).buffer(-.02,quad_segs=128)
    assert Point(step['narrow'][0]).distance(current.boundary)>.001
    saved=current.wkb
    candidate,proof,domain=next(variants(current,step,10,
        native_axis=LineString([[-1,0],[1,0]])))
    assert current.wkb==saved and candidate.is_valid
    assert candidate.area>=current.area
    assert proof['maximum_materialized_alignment_angle_degrees']<=10
    assert candidate.symmetric_difference(current).difference(domain).area<1e-12


def test_covered_transverse_edge_does_not_require_two_surviving_anchors():
    from src.gerber_u05.boundary_curve_bridge import variants
    current=Polygon([(-1,-.05),(1,-.05),(1,.05),(.05,.05),(0,.065),(-1,.065)])
    step=dict(wide=np.array([0.,.065]),narrow=np.array([[0.,.05]]),
              height_mm=.015,wide_tangent=np.array([1.,0.]))
    coords=np.asarray(current.exterior.coords)[:-1]
    assert np.argmin(np.linalg.norm(coords-step['wide'],axis=1))==np.argmin(np.linalg.norm(coords-step['narrow'][0],axis=1))
    candidate,proof,domain=next(variants(current,step,10,native_axis=LineString([[-1,0],[1,0]])))
    assert candidate.is_valid and candidate.area>=current.area
    assert proof['maximum_materialized_alignment_angle_degrees']<=10


def test_local_c1_family_preserves_admitted_copper_without_fixed_seed(monkeypatch):
    import src.gerber_u05.shoulder_bridge as module
    rows,paths,before,floor,caps=straight()
    step=min(steps(before['s'],floor['s']),key=lambda s:abs(s['point_mm'][0]))
    plan=dict(record=dict(point_mm=step['point_mm'],height_mm=step['height_mm'],primary_source_id='s'),
        step=step,junction=Polygon(),repair_domain=box(-.7,-.2,.7,.2),discovery_floor=floor['s'],
        batch=dict(chains=[dict(source_ids=['s'],line=LineString([[-1,0],[1,0]]))]))
    monkeypatch.setattr(module,'patch',lambda *a,**k:(_ for _ in()).throw(AssertionError('fixed seed consulted')))
    candidate=next(module.edge_profile_variants(plan,before['s'],floor['s'],10))
    assert before['s'].difference(candidate['image']).area==0
    assert candidate['proof']['right_reach_mm']>0 and candidate['added'].area>0
    assert candidate['proof']['maximum_materialized_alignment_angle_degrees']<=10


def test_unrelated_wide_trace_does_not_enlarge_a_prepared_junction_mouth():
    from src.gerber_u05.shoulder_bridge import junction_mouths
    from shapely.geometry import Point
    points=dict(left=[[-.4,0],[0,0]],right=[[0,0],[.4,0]],branch=[[0,0],[0,-.4]],wide=[[.8,.8],[1.2,.8]])
    rows={s:dict(metadata=dict(route_points_mm=p,minimum_caliper_mm=.55 if s=='wide'else .1))for s,p in points.items()}
    original={s:LineString(p).buffer(rows[s]['metadata']['minimum_caliper_mm']/2,quad_segs=128)for s,p in points.items()}
    caps=dict(left=.13,right=.13,branch=.13,wide=.55)
    result=junction_mouths(rows,original,caps,dict(native_sources=list(points)),box(-1,-1,2,2))
    assert result.covers(Point(0,0))
    assert not result.covers(Point(.25,0))


def test_junction_rail_uses_original_connected_branch_without_fake_connector():
    from src.gerber_u05.boundary_curve_bridge import alignment
    references=[LineString([[-1,0],[0,0]]),LineString([[0,0],[0,1]])]
    rail=np.array([[.05,.2],[.05,.8]])
    assert alignment(rail,references,(0,0),native=True)==0
    assert alignment(rail,references[0],(0,0),native=True)==90
    steep=np.array([[.05,.2],[.2,.8]])
    assert alignment(steep,references,(0,0),native=True)>10


def test_remote_narrow_section_cannot_shrink_a_local_bridge_reference():
    from src.gerber_u05.shoulder_bridge import interval_cap
    chain=dict(width=.05,source_intervals=[(0.,1.,'local'),(1.,8.,'continuation'),(8.,9.,'remote')])
    caps=dict(local=.075,continuation=.075,remote=.061)
    assert abs(interval_cap(chain,caps,.1,.4)-.025)<1e-15
    assert abs(interval_cap(chain,caps,7.9,8.1)-.011)<1e-15


def test_bridge_station_remains_bound_to_its_causing_source_occurrence():
    from src.gerber_u05.shoulder_bridge import source_station
    from shapely.geometry import Point
    line=LineString([(0,0),(1,0),(1,1),(0,1),(0,.12),(.9,.12)])
    chain=dict(line=line,source_intervals=[(0.,1.,'causing'),(1.,4.78,'other')])
    point=Point(.5,.065)
    assert line.project(point)>3
    assert abs(source_station(chain,'causing',point)-.5)<1e-12


def test_true_three_way_width_steps_are_finished_without_losing_source(tmp_path):
    from src.shared_copper_context import CopperContext
    from src.gerber_u05.boundary_prepare import supports,shoulder_dependencies
    from src.gerber_u05.growth_bridge import meaningful_shoulders
    points=dict(left=[[-.5,0],[0,0]],right=[[0,0],[.5,0]],branch=[[0,0],[0,-.4]])
    rows={s:dict(metadata=dict(route_points_mm=p,route_kind='segment',minimum_caliper_mm=.1))for s,p in points.items()}
    original={s:LineString(p).buffer(.05,quad_segs=128)for s,p in points.items()}
    extra=unary_union([box(-.5,-.065,-.1,.065),box(.1,-.065,.5,.065),box(-.065,-.4,.065,-.1)])
    before={s:g.union(extra)for s,g in original.items()};paths={'r':list(points)};caps={s:.13 for s in points}
    with CopperContext(original,source_binding=dict(source='three-way'),frame=dict(units='mm'),root=tmp_path/'prepared')as context:
        revision=context.source;contacts=supports(rows,paths,original,revision,with_sources=True,admitted=before)
        after,_,_,report=run(rows,paths,before,original,caps,supports=contacts,
            review_bounds=[[-.2,-.2,.2,.2]],prepare=lambda p:shoulder_dependencies(p,before,revision,native_ids=set(points)))
    a=unary_union(list(before.values()));b=unary_union(list(after.values()))
    assert b.area>=a.area and all(original[s].difference(after[s]).area<1e-12 for s in points)
    assert report['smoothed'] and not report['unresolved']
    window=box(-.2,-.2,.2,.2)
    assert not[p for p in meaningful_shoulders(b,sharp_points(b,a,10))if window.covers(__import__('shapely').geometry.Point(p))]


def test_junction_end_sections_refresh_without_reclassifying_a_real_terminal():
    from src.gerber_u05.growth_bridge import affected_sections
    from src.gerber_u05.boundary_finish import key
    points=[[-.3,0],[0,0]];rows={'s':dict(metadata=dict(route_points_mm=points,minimum_caliper_mm=.1))}
    chain=dict(source_ids=['s'],points=points,line=LineString(points),width=.1,source_intervals=[(0.,.3,'s')])
    before={'s':LineString(points).buffer(.065,quad_segs=128)}
    after={'s':LineString(points).buffer(.06,quad_segs=128)}
    assert not affected_sections(rows,chain,before,after)
    result=affected_sections(rows,chain,before,after,interior_nodes={key([0,0])})
    assert ('s',key([0,0]))in result and ('s',key([-.3,0]))not in result


def test_terminal_custody_uses_exposed_corner_instead_of_original_pad_midpoint():
    from shapely.geometry import Point
    points=[[0.,-1.],[0.,.1]]
    rows={'s':dict(metadata=dict(route_points_mm=points,minimum_caliper_mm=.05)),
          'pad':dict(metadata={})}
    original={'s':LineString(points).buffer(.025,quad_segs=128),'pad':box(-.1,0,.1,.3)}
    bodies={'s':LineString(points).buffer(.0375,quad_segs=128),'pad':original['pad']}
    optional=bodies['s'].difference(unary_union(list(original.values())))
    contact=original['s'].intersection(original['pad']).buffer(.025,quad_segs=128)
    terminal=dict(source_ids=['s'],land_ids=['pad'],window_wkb_hex=box(-1,-2,1,1).wkb_hex,
        optional_scope_wkb_hex=optional.wkb_hex,attachment_scope_wkb_hex=contact.wkb_hex)
    assert optional.distance(Point(.06875,0))>.03
    assert optional.distance(Point(.0375,0))==0 and contact.covers(Point(.0375,0))
    def no_constructor(plans):
        assert not plans, 'A genuine source attachment reached geometry construction'
        return {},dict(queries=0)
    after,changes,_,report=run(rows,{'r':['s']},bodies,original,{'s':.075},
        supports={'r':{'pad':original['pad']}},terminals=[terminal],prepare=no_constructor)
    assert not changes and not report['reports']
    assert len(report['deferred_terminal_candidate_points_mm'])==2
    assert after['s'].wkb==bodies['s'].wkb


def test_changed_miter_section_refreshes_in_its_qualified_frame():
    from src.gerber_u05.growth_bridge import affected_sections
    from src.gerber_u05.endpoint_sections import audit
    from src.gerber_u05.boundary_finish import key
    points=[[-.3,0],[0,0]];rows={'s':dict(metadata=dict(route_points_mm=points))}
    chain=dict(line=LineString(points),width=.1,source_intervals=[(0.,.3,'s')])
    before={'s':box(-.3,-.08,.08,.08)}
    # A local recession meets the diagonal qualified section while leaving
    # the raw x=0 source-normal section unchanged.
    after={'s':before['s'].difference(box(.055,.055,.09,.09))}
    frozen={('s',key([0,0])):dict(section=dict(lower_mm=[-.08,-.08],upper_mm=[.08,.08]))}
    assert not affected_sections(rows,chain,before,after,interior_nodes={key([0,0])})
    result=affected_sections(rows,chain,before,after,interior_nodes={key([0,0])},frozen_sections=frozen)
    section=result['s',key([0,0])]
    assert abs(section['normal'][0]-section['normal'][1])<1e-12
    obligation=dict(source_id='s',route_id='r',endpoint_mm=[0,0],section=section,native_frame_transition_admitted=True)
    assert audit({'r':after['s']},[obligation])['passed']


def test_invalid_generated_source_is_rejected_with_exact_evidence(monkeypatch):
    from shapely.geometry import MultiPolygon
    import src.gerber_u05.shoulder_bridge as module
    bad=MultiPolygon([box(-.2,-.02,.2,.02),box(-.1,-.01,.1,.01)])
    assert not bad.is_valid
    raw_union=module.unary_union
    fired=[]
    def invalid_materialization(shapes):
        shapes=list(shapes)
        value=raw_union(shapes)
        # Inject at source serialization, where the candidate union is made
        # from unchanged outside skin, original floor and proposed local skin.
        if len(shapes)==3 and not fired and any(g.equals(floor['s'])for g in shapes):
            fired.append(True)
            return bad
        return value
    rows,paths,before,floor,caps=straight()
    monkeypatch.setattr(module,'unary_union',invalid_materialization)
    after,_,_,report=run(rows,paths,before,floor,caps,prepare=prepare)
    rejected=[a for r in report['reports']for a in r.get('invalid_generated_proposals',[])]
    # The real bounded regression also covers this GEOS nested-shell case.
    assert fired and rejected
    assert rejected[0]['proposed_wkb_hex']==bad.wkb_hex.lower()
    assert floor['s'].difference(after['s']).area<1e-12
