import pytest
from shapely.geometry import box,LineString
from src.gerber_u05.corner_transition import propose,run
from src.gerber_u05.smooth_transition import value


def fixture():
    rows={s:dict(metadata=dict(route_points_mm=pts))for s,pts in [('large',[[-1.,0.],[0.,0.]]),('small',[[0.,0.],[1.,0.]])]}
    desc={s:dict(points=r['metadata']['route_points_mm'],source_width_mm=.05,
                offsets_mm=[-w/2,w/2])for (s,r),w in zip(rows.items(),(.075,.05))}
    material=dict(large=box(-1.,-.0375,0.,.0375),small=box(0.,-.025,1.,.025))
    return rows,desc,material


def test_larger_corner_tapers_to_smaller_face_without_removing_copper():
    rows,desc,material=fixture();before={s:g.wkb for s,g in material.items()}
    patches,q=run(rows,dict(r=list(rows)),material,lambda s:('r',),desc)
    assert len(patches)==2 and q['filled']==2 and q['unresolved']==0
    assert {s:g.wkb for s,g in material.items()}==before
    for p in patches:
        recipe=p['recipe'];cs=recipe['initial_correction_controls_mm']
        assert [value(c,1.)for c in cs]==[0.,0.]
        assert recipe['blend_endpoint_derivatives']==[0.,0.]
        assert recipe['endpoint_step_slope_mm_per_mm']<=.25
        assert p['source_id']=='small'
    assert q['constructed_groups_audited']==0 and q['scene_indexes_built']==1


def test_unfillable_new_pocket_withdraws_its_joint_but_keeps_other_sites_and_old_voids():
    from shapely.ops import unary_union
    from src.gerber_u05.corner_transition import reject_enclosing_additions,new_pocket_regions
    floor=box(0.,0.,3.,3.).difference(box(1.,1.,2.,3.))
    old_void=box(.2,.2,.4,.4);floor=floor.difference(old_void)
    before=floor.wkb
    bridge=dict(endpoint_mm=[1.5,2.1],geometry=box(.9,2.,2.1,2.1))
    other=dict(endpoint_mm=[-.1,.5],geometry=box(-.1,.4,.1,.6))
    kept,proof=reject_enclosing_additions(floor,[bridge,other])
    assert kept==[other]and proof['passed']
    assert proof['rejected_endpoints_mm']==[[1.5,2.1]]
    after=unary_union([floor,*[p['geometry']for p in kept]])
    assert not new_pocket_regions(floor,after)and not after.intersects(old_void.buffer(-.00001))
    assert floor.wkb==before and after.covers(other['geometry'])
    assert not proof['floor_changed']and proof['constructed_groups_audited']==0


def test_withdrawal_follows_an_overlapping_joint_that_reveals_a_second_enclosure():
    from src.gerber_u05.corner_transition import reject_enclosing_additions
    floor=box(0.,0.,3.,3.).difference(box(1.,1.,2.,3.))
    first=dict(endpoint_mm=[1.5,1.8],geometry=box(.9,1.8,2.1,2.9))
    second=dict(endpoint_mm=[1.5,3.],geometry=box(.8,2.,2.2,3.).difference(box(1.1,2.2,1.9,2.8)))
    other=dict(endpoint_mm=[-.1,.5],geometry=box(-.1,.4,.1,.6))
    kept,proof=reject_enclosing_additions(floor,[first,second,other])
    assert proof['passed']and kept==[other]
    assert len(proof['rounds'])==2 and len(proof['withdrawn_patch_sha256'])==2
    assert proof['rounds'][0]['rejected_endpoints_mm']==[[1.5,1.8]]
    assert proof['rounds'][1]['rejected_endpoints_mm']==[[1.5,3.]]


def test_a_new_pocket_inside_an_existing_bounded_void_is_not_hidden_by_zero_new_void_area():
    from shapely.ops import unary_union
    from src.gerber_u05.corner_transition import new_pocket_regions,reject_enclosing_additions
    floor=box(0,0,5,5).difference(box(1,1,4,4))
    bridge=dict(endpoint_mm=[2.5,1.45],geometry=box(.9,1.4,4.1,1.5))
    after=unary_union([floor,bridge['geometry']])
    pockets=new_pocket_regions(floor,after)
    assert len(pockets)==1 and pockets[0].area==pytest.approx(1.2)
    kept,proof=reject_enclosing_additions(floor,[bridge])
    assert not kept and proof['passed']
    assert not new_pocket_regions(floor,unary_union([floor,box(.9,1,1.2,4)]))


def test_joint_pocket_cap_includes_both_native_paths_without_increasing_the_radius():
    from shapely.geometry import Point
    from src.gerber_u05.corner_transition import joined_cap_envelope
    desc=dict(receiver=dict(points=[[-1.,0.],[0.,0.]]),donor=dict(points=[[0.,0.],[0.,1.]]),
              unrelated=dict(points=[[-1.,.2],[1.,.2]]))
    radius=.03
    receiver=LineString(desc['receiver']['points']).buffer(radius+.00001,quad_segs=128)
    point=Point(.02,.08)
    cap=joined_cap_envelope(desc,[('receiver',1),('donor',0)],radius)
    assert not receiver.covers(point)and cap.covers(point)
    assert not cap.covers(Point(.04,.08))
    assert not cap.covers(Point(-.5,.2))


def test_asymmetric_corner_fills_only_the_face_that_is_larger():
    rows,desc,material=fixture();desc['large']['offsets_mm']=[-.025,.05]
    material['large']=box(-1.,-.025,0.,.05)
    patches,q=run(rows,dict(r=list(rows)),material,lambda s:('r',),desc)
    assert len(patches)==1 and patches[0]['side']==1


def test_foreign_clearance_limits_the_crowded_face_without_waiving_the_guard():
    from shapely.ops import unary_union
    rows,desc,material=fixture();material['foreign']=box(.001,.075,1.,.2)
    patches,q=run(rows,dict(r=list(rows)),material,lambda s:('other',)if s=='foreign'else('r',),desc)
    assert len([p for p in patches if p['side']!='JOINT_SKIN'])==2
    assert q['filled']==1 and q['clearance_limited']==1
    own=unary_union([material['large'],material['small']])
    for patch in patches:
        delta=patch['geometry'].difference(own)
        assert delta.buffer(.00001,quad_segs=128).distance(material['foreign'])>=.0401-1e-12
    assert all(f['reason']=='NEW_EXPOSED_COPPER_BELOW_CONSTRUCTION_GUARD'for r in q['reports']for a in r['attempts']for f in a.get('failures',[]))


def test_covered_receiving_occurrences_cannot_get_joint_growth():
    rows,desc,material=fixture()
    patches,q=run(rows,dict(r=list(rows)),material,lambda s:('r',),desc,covered={'small'})
    assert not patches and q['filled']==0


def test_reach_outlier_and_short_transition_are_not_accepted():
    _,desc,_=fixture()
    with pytest.raises(ValueError,match='TOO_SHORT'):propose(desc['small'],0,[0.,.0375],1,.01)
    with pytest.raises(ValueError,match='OUTLIER'):propose(desc['small'],0,[0.,.2],1,1.,maximum_slope=1.)


def test_taper_into_an_arc_preserves_the_existing_arc_and_source_path():
    import math
    rows,desc,material=fixture()
    points=[[.4*math.sin(t),.4*(1-math.cos(t))]for t in[i*math.pi/200 for i in range(101)]]
    rows['small']['metadata']['route_points_mm']=points;desc['small']['points']=points
    material['small']=LineString(points).buffer(.025,quad_segs=128)
    before=material['small'].wkb
    patches,q=run(rows,dict(r=list(rows)),material,lambda s:('r',),desc)
    assert patches and all(p['recipe']['source_path_changed']is False for p in patches)
    assert material['small'].wkb==before and desc['small']['points']==points
    assert all(p['recipe']['extra_reach_bound_mm']<=.11 for p in patches)


def test_transport_follows_a_turn_instead_of_reusing_a_world_space_delta():
    import math
    points=[[.15*math.sin(t),.15*(1-math.cos(t))]
            for t in [i*math.pi/200 for i in range(201)]]
    receiver=dict(points=points,source_width_mm=.05,offsets_mm=[-.025,.025])
    shape,proof=propose(receiver,0,[0.,.0375],1,.4)
    assert shape.is_valid and proof['extra_reach_bound_mm']<=.11
    corridor=LineString(points).buffer(proof['input_face_envelope_radius_mm']+.00001,quad_segs=128)
    assert shape.difference(corridor).area<1e-12


def test_a_receiving_profile_cannot_grow_a_new_bulb_above_both_input_faces():
    rows,desc,material=fixture()
    desc['small']['fields']=[dict(first_mm=0.,last_mm=.1,controls=[[-.025,-.025,-.0375,-.0375],[.025,.025,.0375,.0375]]),
                              dict(first_mm=.1,last_mm=1.,controls=[[-.0375]*4,[.0375]*4])]
    shape,recipe=propose(desc['small'],0,[0.,.0375],1,.5)
    assert shape.bounds[3]<=.0375+1e-12
    assert recipe['field_policy']=='CONVEX_ENDPOINT_SECTION_TRANSPORT_IN_NATIVE_FRAME'


def test_corner_fill_does_not_leave_a_new_enclosed_sliver_under_its_support_rail():
    from shapely.ops import unary_union
    rows,desc,material=fixture()
    material['small']=material['small'].difference(box(0.,.0245,.02,.026))
    patches,q=run(rows,dict(r=list(rows)),material,lambda s:('r',),desc)
    joined=unary_union([*material.values(),*[p['geometry']for p in patches]])
    assert q['filled']==2 and joined.geom_type=='Polygon'and not joined.interiors


def test_one_ended_short_receiver_uses_its_full_length_and_keeps_supported_overlap():
    rows,desc,material=fixture()
    rows['small']['metadata']['route_points_mm']=[[0.,0.],[.08,0.]]
    desc['small']['points']=rows['small']['metadata']['route_points_mm']
    material['small']=box(0.,-.025,.08,.025)
    patches,q=run(rows,dict(r=list(rows)),material,lambda s:('r',),desc)
    assert q['filled']==2 and q['unresolved']==0
    assert all(p['recipe']['length_mm']==.08 for p in patches)
    assert all(p['geometry'].intersection(material['small']).area>0 for p in patches)


def test_a_native_source_seam_does_not_stop_a_valid_joint_taper():
    rows,desc,material=fixture()
    points=[[0.,0.],[.01,0.]]
    rows['small']['metadata']['route_points_mm']=points;desc['small']['points']=points
    material['small']=box(0.,-.025,.01,.025)
    points=[[.01,0.],[1.,0.]]
    rows['continuation']=dict(metadata=dict(route_points_mm=points))
    desc['continuation']=dict(points=points,source_width_mm=.05,offsets_mm=[-.025,.025])
    material['continuation']=box(.01,-.025,1.,.025)
    patches,report=run(rows,dict(r=list(rows)),material,lambda s:('r',),desc)
    fills=[p for p in patches if p['source_id']=='small' and p['side'] in (0,1)]
    assert len(fills)==2 and all(p['recipe']['length_mm']>.01 for p in fills)
    assert all(p['recipe']['source_seams_are_not_taper_boundaries'] for p in fills)
    blocked,report=run(rows,dict(r=list(rows)),material,lambda s:('r',),desc,covered={'continuation'})
    assert not any(p['source_id']=='small' and p['side'] in (0,1) for p in blocked)


def test_arc_taper_cutoff_keeps_the_original_member_offset_normal():
    import numpy as np
    from src.gerber_u05.ribbon_profile import frame
    desc=dict(points=[[0.,0.],[.2,0.],[.3,.1],[.3,.3]],source_width_mm=.05,offsets_mm=[-.025,.025])
    length=.25
    shape,_=propose(desc,0,[0.,.03],1,length)
    p,n,t,_=frame(desc['points'],extra_stations=[length]);i=np.argmin(abs(t-length))
    from shapely.geometry import Point
    assert shape.distance(Point(p[i]+n[i]*.025))<1e-12


def test_actual_skin_anchor_overlaps_donor_and_receiver_without_a_hairline():
    from shapely.ops import unary_union
    rows,desc,material=fixture()
    # The mathematical face and plotted face differ slightly at a source seam.
    material['large']=box(-1.,-.0377,-.00001,.0377)
    for s in desc:desc[s]['support']=material[s]
    patches,q=run(rows,dict(r=list(rows)),material,lambda s:('r',),desc)
    assert q['filled']==2
    for patch in patches:
        assert patch['geometry'].intersection(material['large']).area>0
        assert patch['geometry'].intersection(material['small']).area>0
    joined=unary_union([*material.values(),*[p['geometry']for p in patches]])
    assert joined.geom_type=='Polygon'and not joined.interiors
    from shapely import from_wkb,to_wkb
    restored=unary_union([from_wkb(to_wkb(g))for g in [*material.values(),*[p['geometry']for p in patches]]])
    assert restored.geom_type=='Polygon'and not restored.interiors


def test_plotted_skin_step_is_filled_even_when_declared_sections_match():
    rows,desc,material=fixture()
    desc['large']['offsets_mm']=desc['small']['offsets_mm'][:]
    for s in desc:desc[s]['support']=material[s]
    patches,q=run(rows,dict(r=list(rows)),material,lambda s:('r',),desc)
    assert q['filled']==2 and q['unresolved']==0


def test_crowded_corner_can_use_a_shorter_blend_without_relaxing_clearance():
    rows,desc,material=fixture()
    material['foreign']=box(.04,.066,.5,.2)
    patches,q=run(rows,dict(r=list(rows)),material,lambda s:('other',)if s=='foreign'else('r',),desc)
    upper=next(p for p in patches if p['side']==1)
    assert q['unresolved']==0
    assert upper['recipe']['endpoint_step_slope_mm_per_mm']>.25
    assert upper['geometry'].distance(material['foreign'])>=.0401


def test_equal_endpoint_sections_do_not_hide_a_notch_on_the_arc_shoulder():
    from shapely.ops import unary_union
    rows,desc,material=fixture()
    desc['large']['offsets_mm']=[-.025,.025]
    material['large']=box(-1.,-.025,0.,.025)
    material['small']=material['small'].difference(box(.0001,.021,.004,.03))
    for s in desc:desc[s]['support']=material[s]
    before=unary_union(list(material.values()))
    patches,q=run(rows,dict(r=list(rows)),material,lambda s:('r',),desc)
    assert q['filled']==0 and q['skin_closure']['filled']==1
    assert all(p['side']=='JOINT_SKIN'for p in patches)
    joined=unary_union([before,*[p['geometry']for p in patches]])
    assert before.difference(joined).area<1e-14
    notch=box(.0001,.021,.004,.0249)
    assert notch.difference(joined).area<1e-12
    assert joined.geom_type=='Polygon'and not joined.interiors


def test_skin_closure_cannot_fill_an_existing_support_hole():
    from src.gerber_u05.corner_transition import skin_fill
    hole=box(.001,.015,.003,.018)
    support=box(-.1,-.025,.1,.025).difference(hole)
    addition=skin_fill(support,LineString([[-.1,0.],[.1,0.]]),box(-.015,-.04,.015,.04),.025)
    assert addition.intersection(hole).is_empty


@pytest.mark.parametrize('station',[.002,.022])
def test_rounded_last_chord_cannot_clip_the_off_axis_arc_shoulder(station):
    import numpy as np
    from shapely.geometry import Polygon,Point
    u=np.array([1.,1.])/2**.5;n=np.array([-u[1],u[0]])
    paths={'a':[[-.1,-.1],[-.005,-.005],[-.002,-.0002],[0.,0.]],
           'b':[[0.,0.],[.002,.0002],[.005,.005],[.1,.1]]}
    rows={s:dict(metadata=dict(route_points_mm=p))for s,p in paths.items()}
    desc={s:dict(points=p,source_width_mm=.04,offsets_mm=[-.03,.03])for s,p in paths.items()}
    notch=Polygon([u*x+n*y for x,y in[(station-.003,-.032),(station+.003,-.032),(station+.003,-.025),(station-.003,-.025)]])
    # Shared local projection, as with overlapping native arc-end caps.
    body=Polygon([u*x+n*y for x,y in[(-.14,-.03),(.14,-.03),(.14,.03),(-.14,.03)]]).difference(notch)
    material={s:body for s in paths}
    for s in desc:desc[s]['support']=material[s]
    patches,q=run(rows,{'r':['a','b']},material,lambda s:('r',),desc)
    point=Point(u*station+n*(-.027))
    assert all(g.distance(point)>1e-5 for g in material.values())
    assert any(p['side']=='JOINT_SKIN'and p['geometry'].covers(point)for p in patches)


def test_other_route_on_the_same_owner_cannot_supply_a_joint_shoulder():
    import numpy as np
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    u=np.array([1.,1.])/2**.5;n=np.array([-u[1],u[0]])
    def rect(lo,hi,a,b):return Polygon([u*x+n*y for x,y in[(lo,a),(hi,a),(hi,b),(lo,b)]])
    paths={'a':[[-.1,-.1],[-.005,-.005],[-.002,-.0002],[0.,0.]],
           'b':[[0.,0.],[.002,.0002],[.005,.005],[.1,.1]]}
    rows={s:dict(metadata=dict(route_points_mm=p))for s,p in paths.items()}
    body=rect(-.14,.14,-.03,.03)
    desc={s:dict(points=p,source_width_mm=.04,offsets_mm=[-.03,.03],support=body)for s,p in paths.items()}
    material={s:body for s in paths}
    material['other-route']=unary_union([rect(-.05,.05,.034,.037),rect(-.05,-.04,.029,.037)])
    patches,q=run(rows,{'r':['a','b']},material,lambda s:('same-electrical-owner',),desc)
    assert not patches and q['skin_closure']['filled']==0


def test_clearance_limited_overlap_cannot_copy_another_routes_copper():
    from shapely.geometry import Point
    rows,desc,material=fixture()
    material['foreign']=box(.001,.075,1.,.2)
    material['same-owner-other-route']=box(.002,.036,.004,.037)
    for s in desc:desc[s]['support']=material[s]
    patches,q=run(rows,dict(r=list(rows)),material,lambda s:('foreign',)if s=='foreign'else('same-owner',),desc)
    assert q['clearance_limited']==1
    assert all(not p['geometry'].covers(Point(.003,.0365))for p in patches)


def test_overlapping_joint_fills_cannot_hide_a_newly_enclosed_slit():
    from shapely.ops import unary_union
    from src.gerber_u05.corner_transition import new_pocket_regions
    before=box(-.1,-.05,.1,.05).difference(box(-.02,-.005,.02,.06))
    after=unary_union([before,box(-.025,.02,.025,.03)])
    pockets=new_pocket_regions(before,after)
    assert len(pockets)==1 and pockets[0].area==pytest.approx(.04*.025)
    completed=unary_union([after,*pockets])
    assert not new_pocket_regions(before,completed)
    assert before.difference(completed).is_empty


def test_new_joint_pocket_work_list_never_includes_a_preexisting_hole():
    from src.gerber_u05.corner_transition import new_pocket_regions
    before=box(-.1,-.05,.1,.05).difference(box(-.01,-.01,.01,.01))
    assert not new_pocket_regions(before,before.union(box(.09,-.02,.12,.02)))
def test_generated_skin_rejects_detached_subresolution_needle_without_changing_support():
    from shapely.geometry import box,MultiPolygon
    from src.gerber_u05.corner_transition import attached_skin
    support=box(0,0,1,.1);main=box(0,0,1,.12);needle=box(.1,.13,.2,.1300000002)
    result,proof=attached_skin(support,MultiPolygon([main,needle]))
    assert result.equals(main)and proof['passed']and proof['source_faces_removed']==0
    assert len(proof['rejected_optional_faces'])==1
    assert result.covers(support)


def test_generated_skin_defers_a_substantive_detached_proposal():
    from shapely.geometry import box,MultiPolygon
    from src.gerber_u05.corner_transition import attached_skin
    support=box(0,0,1,.1);main=box(0,0,1,.12);separate=box(.1,.2,.2,.3)
    result,proof=attached_skin(support,MultiPolygon([main,separate]))
    assert result is None and not proof['passed']



def test_saved_endpoint_section_overrides_a_plotting_chord_in_both_directions():
    import numpy as np
    from src.gerber_u05.corner_transition import corners,joint_frame,oriented
    desc=dict(points=[[0.,0.],[.001,.002],[.1,.002]],source_width_mm=.05,offsets_mm=[-.03,.03],
        endpoint_sections=[dict(normal=[0.,1.],lower_mm=[0.,-.03],upper_mm=[0.,.03]),
                           dict(normal=[0.,1.],lower_mm=[.1,-.028],upper_mm=[.1,.032])])
    for end in (0,1):
        values,n=corners(desc,end,skin=False)
        section=desc['endpoint_sections'][end]
        expected=[section[k]for k in(('lower_mm','upper_mm')if end==0 else('upper_mm','lower_mm'))]
        assert np.array_equal(values,expected)
        assert np.array_equal(n,[0.,1. if end==0 else -1.])
        _,normals,_,_=joint_frame(desc,oriented(desc,end))
        assert np.array_equal(normals[0],n)


def test_tiny_unconstructed_connector_inherits_frozen_frame_and_uses_continuation():
    from shapely.geometry import Polygon
    rows,desc,material=fixture()
    desc['large']['endpoint_sections']=[dict(normal=[0.,1.],lower_mm=[x,-.0375],upper_mm=[x,.0375])for x in(-1.,0.)]
    pts=[[0.,0.],[.002,.003]];rows['small']['metadata']['route_points_mm']=pts;desc['small']['points']=pts
    material['small']=LineString(pts).buffer(.025,quad_segs=128)
    pts=[[.002,.003],[1.,.003]];rows['next']=dict(metadata=dict(route_points_mm=pts))
    desc['next']=dict(points=pts,source_width_mm=.05,offsets_mm=[-.025,.025])
    material['next']=LineString(pts).buffer(.025,quad_segs=128)
    patches,q=run(rows,{'r':list(rows)},material,lambda s:('r',),desc)
    fills=[p for p in patches if p['source_id']=='small' and p['side']in(0,1)]
    assert fills and all(p['recipe']['length_mm']>LineString(desc['small']['points']).length for p in fills)
    assert all(p['recipe']['source_seams_are_not_taper_boundaries']for p in fills)
    assert all(p['recipe']['extra_reach_bound_mm']<=.11 for p in fills)


def test_existing_wide_skin_is_not_charged_as_new_corner_reach():
    desc=dict(points=[[0.,0.],[1.,0.]],source_width_mm=.05,offsets_mm=[-.025,.025],
              support=box(0.,-.025,1.,.3))
    shape,proof=propose(desc,0,[0.,.21],1,1.,maximum_slope=1.)
    assert proof['input_skin_raw_reach_mm']>.11
    assert proof['extra_reach_bound_mm']==.11
    assert shape.difference(desc['support']).difference(LineString(desc['points']).buffer(.135,quad_segs=128)).is_empty
