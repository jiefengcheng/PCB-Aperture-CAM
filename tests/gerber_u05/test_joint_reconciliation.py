from shapely.geometry import LineString,Point,box
from shapely.ops import unary_union
from src.gerber_u05.joint_reconciliation import run


def example(shift=False):
    points={'a':[[-1.,0.],[0.,0.]],'b':[[0.,0.],[1.,0.]]}
    rows={s:dict(metadata=dict(route_points_mm=p))for s,p in points.items()}
    desc={s:dict(points=p,source_width_mm=.05,offsets_mm=[-.025,.025])for s,p in points.items()}
    core={s:LineString(p).buffer(.025,quad_segs=128)for s,p in points.items()}
    if shift:grown={'a':box(-1,-.04,0,.035),'b':box(0,-.03,1,.045)}
    else:grown={'a':box(-1,-.0375,0,.0375),'b':box(0,-.03,1,.03)}
    bodies={s:unary_union([core[s],grown[s]])for s in points}
    return rows,desc,core,bodies


def test_a_wider_optional_end_retracts_to_a_c1_meeting_without_new_copper():
    rows,desc,core,bodies=example();before={s:g.wkb for s,g in bodies.items()}
    after,cuts,sections,report=run(rows,{'r':['a','b']},bodies,desc,{('r',(0.,0.))},{'a':.075,'b':.075},core)
    from src.stage_abi.contracts import finite_json
    finite_json(report)
    assert report['trimmed_joints']==1 and sections
    assert after['a'].area<bodies['a'].area
    assert all(bodies[s].covers(after[s])and after[s].covers(core[s])for s in bodies)
    assert {s:g.wkb for s,g in bodies.items()}==before
    q=report['reports'][0]
    assert q['copper_added_mm2']==q['original_copper_removed_mm2']==0
    assert report['scene_indexes_built']==report['clearance_queries']==0
    assert q['profiles'][0]['recipe']['profile']['side_field_proofs'][0]['endpoint_derivatives']==[0.,0.]


def test_equal_widths_with_shifted_edges_retract_both_optional_sides():
    rows,desc,core,bodies=example(shift=True)
    after,cuts,sections,q=run(rows,{'r':['a','b']},bodies,desc,{('r',(0.,0.))},{'a':.075,'b':.075},core)
    assert q['trimmed_joints']==1 and set(cuts)=={'a','b'}
    section=sections['r',(0.,0.)]
    assert abs(LineString([section['lower_mm'],section['upper_mm']]).length-.065)<1e-9
    assert all(bodies[s].covers(after[s])and after[s].covers(core[s])for s in bodies)


def test_fixed_wider_contribution_and_native_branches_are_never_trimmed():
    rows,desc,core,bodies=example()
    after,cuts,_,q=run(rows,{'r':['a','b']},bodies,desc,{('r',(0.,0.))},{'a':.075,'b':.075},core,covered={'a'})
    assert not cuts and q['reports'][0]['status']=='KEEP_FIXED_WIDER_CONTRIBUTION'
    assert all(after[s].wkb==bodies[s].wkb for s in bodies)


def test_custody_seam_uses_the_same_cubic_inside_a_longer_taper():
    from src.gerber_u05.joint_reconciliation import taper,custody_sections
    from src.gerber_u05.smooth_transition import value
    rows,desc,core,bodies=example()
    target=dict(normal=[0.,1.],lower_mm=[0.,-.03],upper_mm=[0.,.03])
    pts=[[-1.,0.],[-.02,0.],[0.,0.]];d=dict(desc['a'],points=pts)
    _,_,recipe=taper(d,1,bodies['a'],target,.075)
    from src.stage_abi.contracts import finite_json
    finite_json(recipe)
    sections=custody_sections(recipe,bodies['a'],{(-.02,0.)})
    q=sections[-.02,0.]
    assert LineString([q['lower_mm'],q['upper_mm']]).length>.06
    assert LineString([q['lower_mm'],q['upper_mm']]).length<.075
    assert recipe['profile']['side_field_proofs'][0]['endpoint_derivatives']==[0.,0.]


def test_failed_matched_width_turn_retracts_optional_growth_to_original_carrier():
    points={'a':[[0.,-1.],[0.,0.]],'b':[[0.,0.],[-1.,0.]]}
    rows={s:dict(metadata=dict(route_points_mm=p))for s,p in points.items()}
    desc={s:dict(points=p,source_width_mm=.05,offsets_mm=[-.0375,.0375])for s,p in points.items()}
    core={s:LineString(p).buffer(.025,quad_segs=128)for s,p in points.items()}
    grown={s:LineString(p).buffer(.0375,quad_segs=128)for s,p in points.items()}
    after,cuts,sections,receipt=run(rows,{'r':['a','b']},grown,desc,{('r',(0.,0.))},{'a':.075,'b':.075},core)
    assert receipt['reports'][0]['status']=='TRIMMED_OPTIONAL_INTERFACE'
    assert receipt['reports'][0]['target_mode']=='ORIGINAL_CARRIER_SECTION'
    assert set(cuts)==set(points)and sections
    assert not receipt['kept_original_components']
    for s in points:
        assert after[s].difference(grown[s]).area<=1e-12
        assert core[s].difference(after[s]).area<=1e-12
        assert core[s].area<after[s].area<grown[s].area
    # The shared outer cap must retract too, rather than leaving a projection
    # beyond both native endpoint planes while both incoming tapers pass.
    combined=unary_union(list(after.values()))
    assert not combined.covers(Point(.02,.02))
    cap=combined.intersection(box(-1e-6,0.,1e-6,.05))
    assert cap.bounds[3]<=.02501
    assert receipt['scene_indexes_built']==receipt['clearance_queries']==0
