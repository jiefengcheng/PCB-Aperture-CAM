from shapely.geometry import box,LineString
from shapely.ops import unary_union
from src.gerber_u05.tangent_finish import trim_wider_ends


def fixture():
    rows={s:dict(metadata=dict(route_points_mm=pts))for s,pts in [('wide',[[-1.,0.],[0.,0.]]),('narrow',[[0.,0.],[1.,0.]])]}
    bodies=dict(wide=box(-1.,-.0375,0.,.0375),narrow=box(0.,-.025,1.,.025))
    desc={s:dict(points=r['metadata']['route_points_mm'],source_width_mm=.05,offsets_mm=[-w/2,w/2],support=bodies[s])for(s,r),w in zip(rows.items(),(.075,.05))}
    cores={s:LineString(d['points']).buffer(.025,quad_segs=128)for s,d in desc.items()}
    return rows,bodies,desc,cores


def test_existing_tangent_cutter_can_remove_accepted_wider_shoulder_copper():
    rows,bodies,desc,cores=fixture()
    after,cuts,q=trim_wider_ends(rows,dict(r=['wide','narrow']),bodies,desc,source_cores=cores)
    assert q['trimmed_joints']==1 and cuts['wide'].intersection(bodies['wide']).area>0
    assert bodies['wide'].covers(after['wide'])
    assert not q['old_larger_endpoint_is_target']and not q['wider_shoulder_is_fixed']
    assert q['targets'][0]['radius_mm']==.05
    assert q['targets'][0]['maximum_depth_mm']==.005


def test_old_wider_width_is_not_a_trim_obligation_and_shared_aliases_do_not_restore_it():
    rows,bodies,desc,cores=fixture();rows['alias']=rows['wide'];bodies['alias']=bodies['wide']
    # A maximal-member shared operand must be cut even when its source end
    # is not a second native endpoint at this site.
    after,cuts,q=trim_wider_ends(rows,dict(r=['wide','narrow','alias']),bodies,desc,source_cores=cores)
    assert q['trimmed_joints']==1 and not q['old_larger_endpoint_is_target']
    assert 'wide'in cuts and'alias'in cuts
    result=unary_union(list(after.values()))
    assert result.geom_type=='Polygon'and not result.interiors
    assert result.covers(unary_union(list(cores.values())).intersection(unary_union(list(bodies.values()))))
    assert bodies['wide'].area>after['wide'].area
    assert after['wide'].intersection(box(-1,-1,-.2,1)).equals(bodies['wide'].intersection(box(-1,-1,-.2,1)))
    assert q['constructed_groups_audited']==0


def test_nominal_and_covered_copper_are_still_protected():
    rows,bodies,desc,cores=fixture()
    after,_,q=trim_wider_ends(rows,dict(r=['wide','narrow']),bodies,desc,covered={'wide'},source_cores=cores)
    assert q['trimmed_joints']==0 and after['wide'].wkb==bodies['wide'].wkb
    # The narrower continuation cannot demand a neck-down of original copper.
    cores['wide']=bodies['wide']
    after,_,q=trim_wider_ends(rows,dict(r=['wide','narrow']),bodies,desc,source_cores=cores)
    assert q['trimmed_joints']==0 and after['wide'].wkb==bodies['wide'].wkb
    assert all(r['status']=='NO_TANGENT_PROTRUSION'for r in q['reports'])
