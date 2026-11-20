from src.gerber_u05.route_pose import solve


def group(axis,shift,left,right,s='s'):
    return dict(axis=axis,lanes=[dict(mutable=True,source_ids=[s],profile_midline_shift_mm=shift,
                                    face_growth_mm=dict(left=left,right=right))])


def test_one_shared_pose_satisfies_all_group_face_budgets_without_moving_strips():
    c=dict(groups=[group([1.,0.],.018,-.005,.031),group([0.,1.],0.,.01,.01)])
    q=solve(c,{'r':['s','arc']})
    assert q['passed'] and not q['constructed_group_geometry_changed']
    x,y=q['routes']['r']['translation_mm']
    assert abs(x)<1e-12 and abs(y-.005)<1e-12
    assert c['groups'][0]['lanes'][0]['profile_midline_shift_mm']==.018


def test_incompatible_group_constraints_are_not_smoothed_or_averaged_into_a_pose():
    c=dict(groups=[group([1.,0.],.02,-.02,.021),group([1.,0.],-.02,.021,-.02)])
    q=solve(c,{'r':['s']})
    assert not q['passed'] and q['conflicting_routes']==['r']


def test_translation_bound_is_a_whole_vector_bound():
    c=dict(groups=[group([1.,0.],.024,-.024,.025),group([0.,1.],-.024,.025,-.024)])
    assert not solve(c,{'r':['s']})['passed']
