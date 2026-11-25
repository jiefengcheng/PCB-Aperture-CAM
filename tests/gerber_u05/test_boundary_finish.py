import math
import pytest
from shapely.geometry import LineString,box
from shapely.ops import unary_union
from src.gerber_u05.boundary_finish import run,sharp_points


def fixture(points,widths=None,growth=None):
    widths=widths or{s:.05 for s in points};growth=growth or{s:.075 for s in points}
    rows={s:dict(metadata=dict(route_points_mm=p,minimum_caliper_mm=widths[s]))for s,p in points.items()}
    floor={s:LineString(p).buffer(widths[s]/2,quad_segs=128)for s,p in points.items()}
    bodies={s:LineString(p).buffer(growth[s]/2,quad_segs=128)for s,p in points.items()}
    return rows,floor,bodies,growth


def check(rows,floor,bodies,caps,**kwargs):
    after,cuts,sections,q=run(rows,{'r':list(rows)},bodies,floor,caps,**kwargs)
    assert q['scene_indexes_built']==q['clearance_queries']==q['complete_board_unions']==q['owner_reconstructions']==0
    for s,g in after.items():
        assert g.difference(bodies[s]).area<1e-12
        assert floor[s].difference(g).area<1e-12
        if s in cuts:
            assert cuts[s].difference(bodies[s]).area<1e-12
            assert bodies[s].difference(g).symmetric_difference(cuts[s]).area<1e-12
    for r in q['reports']:
        for p in r.get('profiles',[]):
            assert p['recipe']['maximum_materialized_alignment_angle_degrees']<=10+1e-8
            for proof in p['recipe']['profile']['side_field_proofs']:
                assert math.degrees(math.atan(proof['actual_maximum_side_slope']))<=10+1e-8
    return after,cuts,sections,q


def test_t_junction_uses_one_common_outline_and_preserves_original_carriers():
    rows,floor,bodies,caps=fixture(dict(left=[[-1,0],[0,0]],right=[[0,0],[1,0]],up=[[0,0],[0,1]]))
    after,cuts,_,q=check(rows,floor,bodies,caps)
    assert cuts and any(r['kind']=='THREE_WAY'and r['status']=='SMOOTHED'for r in q['reports'])
    before=unary_union(list(bodies.values()));result=unary_union(list(after.values()));core=unary_union(list(floor.values()))
    assert len(sharp_points(result,core,10))<len(sharp_points(before,core,10))
    assert result.geom_type=='Polygon'
    assert result.difference(core).area > .8*before.difference(core).area
    assert not q['withdrawn_growth']


def test_t_junction_joins_separate_catalogue_routes_and_crosses_fragment_seams():
    points=dict(left=[[-1,0],[0,0]],right=[[0,0],[.01,0]],far=[[.01,0],[1,0]],up=[[0,0],[0,1]])
    rows,floor,bodies,caps=fixture(points)
    after,cuts,sections,q=run(rows,{'through':['left','right','far'],'branch':['up']},bodies,floor,caps)
    core=unary_union(list(floor.values()));before=unary_union(list(bodies.values()));result=unary_union(list(after.values()))
    assert q['unresolved']==0 and q['partial']==0
    assert any(r['kind']=='THREE_WAY' for r in q['reports'])
    assert not sharp_points(result,core,10)
    assert result.difference(core).area > .8*before.difference(core).area
    assert any(set(c['source_ids'])=={'right','far'}for c in q['chains'])
    assert ('right',(.01,0.))in sections and ('far',(.01,0.))in sections


def test_curve_transition_retains_source_and_has_no_optional_shoulders():
    import numpy as np
    points=[[float(math.cos(t)),float(math.sin(t))]for t in np.linspace(0,math.pi/2,121)]
    rows,floor,bodies,caps=fixture(dict(curve=points[:61],fixed=points[60:]),growth=dict(curve=.075,fixed=.05))
    after,cuts,sections,q=check(rows,floor,bodies,caps,covered={'fixed'})
    assert q['unresolved']==0 and cuts
    assert not sharp_points(unary_union(list(after.values())),unary_union(list(floor.values())),10)
    assert after['curve'].difference(floor['curve']).area>.7*bodies['curve'].difference(floor['curve']).area
    assert any(c['recipe']for c in q['chains'])


def test_two_way_width_step_tapers_instead_of_ending_abruptly():
    rows,floor,bodies,caps=fixture(dict(a=[[-1,0],[0,0]],b=[[0,0],[1,0]]),growth=dict(a=.075,b=.05))
    after,cuts,_,q=check(rows,floor,bodies,caps,covered={'b'})
    assert cuts and 'b'not in cuts
    assert after['b'].wkb==bodies['b'].wkb
    assert any(r['status']=='SMOOTHED'for r in q['reports'])


def test_direct_connection_to_fixed_pad_preserves_contact_and_pad_geometry():
    rows,floor,bodies,caps=fixture(dict(a=[[-1,0],[0,0]]))
    pad=box(0,-.2,.3,.2)
    after,cuts,_,q=check(rows,floor,bodies,caps,supports={'r':pad})
    assert cuts and any(r['status']=='SMOOTHED'for r in q['reports'])
    assert unary_union([after['a'],pad]).geom_type=='Polygon'
    assert pad.wkb==box(0,-.2,.3,.2).wkb


@pytest.mark.parametrize('angle',[0,45,float('nan'),True,'10'])
def test_invalid_angle_rejects(angle):
    with pytest.raises(ValueError,match='VALID_TRANSITION_ANGLE'):run({}, {}, {}, {}, {},maximum_transition_angle_degrees=angle)


def test_local_face_counter_matches_existing_touch_and_hole_semantics():
    from shapely.geometry import Polygon,MultiPolygon
    from src.gerber_u05.boundary_finish import component_count
    from src.original_copper_owners import OriginalOwners
    cases=[box(0,0,1,1),MultiPolygon([box(0,0,1,1),box(1,1,2,2)]),
        MultiPolygon([box(0,0,1,1),box(2,0,3,1)]),box(0,0,5,5).difference(box(1,1,4,4))]
    assert component_count(Polygon())==0
    assert all(component_count(g)==len(OriginalOwners(g).owners)for g in cases)


def test_orphan_optional_fragments_are_removed_without_dropping_original_carrier():
    from shapely.geometry import MultiPolygon
    from src.gerber_u05.boundary_finish import retain_carriers
    floor=box(0,0,1,1);orphan=box(2,0,3,1)
    result=retain_carriers(MultiPolygon([floor,orphan]),floor)
    assert result.equals(floor) and result.covers(floor)


def test_unexpected_constructor_errors_are_not_silently_withdrawn(monkeypatch):
    import src.gerber_u05.boundary_finish as module
    rows,floor,bodies,caps=fixture(dict(a=[[-1,0],[0,0]],b=[[0,0],[1,0]]),growth=dict(a=.075,b=.05))
    def broken(*args):raise ValueError('UNEXPECTED_IMPLEMENTATION_ERROR')
    monkeypatch.setattr(module,'reference',broken)
    with pytest.raises(ValueError,match='UNEXPECTED_IMPLEMENTATION_ERROR'):
        run(rows,{'r':list(rows)},bodies,floor,caps,covered={'b'})


def test_original_void_restoration_is_distinct_from_new_pocket():
    from src.gerber_u05.boundary_finish import new_pockets
    grown=box(0,0,5,5);floor=grown.difference(box(1,1,4,4))
    assert not new_pockets(grown,floor,floor)
    split=grown.difference(unary_union([box(1.2,1.2,2,2),box(2.5,2.5,3.5,3.5)]))
    assert len(new_pockets(grown,floor,split))==1
    assert new_pockets(grown,box(0,0,.2,5),grown.difference(box(2,2,3,3)))


def test_fixed_contact_preparation_borrows_existing_index_once_per_route():
    from src.gerber_u05.boundary_prepare import supports
    rows,floor,bodies,caps=fixture(dict(a=[[-1,0],[0,0]],b=[[0,0],[1,0]]))
    pad=box(-.1,-.2,.1,.2);entry=dict(floor,pad=pad)
    class Revision:
        def __init__(self):
            self.calls=0
            self.membership={s:('owner',)for s in entry}
        def sources(self,window):
            self.calls+=1
            return tuple(entry)
    revision=Revision()
    result=supports(rows,{'r':['a','b']},entry,revision)
    assert revision.calls==1 and set(result)=={'r'}
    assert result['r'].difference(pad).area==0


def test_contact_preparation_rejects_foreign_owner_and_noncontacting_same_owner():
    from src.gerber_u05.boundary_prepare import supports
    rows,floor,bodies,caps=fixture(dict(a=[[-1,0],[1,0]]))
    entry=dict(floor,foreign=box(-.1,.05,.1,.12),nearby=box(.4,.05,.6,.12),contact=box(-.1,-.2,.1,.2))
    class Revision:
        membership=dict(a=('own',),foreign=('other',),nearby=('own',),contact=('own',))
        def sources(self,window):return tuple(entry)
    result=supports(rows,{'r':['a']},entry,Revision())['r']
    assert result.difference(entry['contact']).area==0


def test_interior_native_contact_is_prepared_without_suppressing_its_whole_route():
    from src.gerber_u05.boundary_prepare import supports
    from src.gerber_u05.boundary_finish import board_outline
    points=dict(a=[[-1,0],[1,0]],b=[[0,-1],[0,1]])
    rows,floor,bodies,caps=fixture(points)
    class Revision:
        membership={s:('own',)for s in rows}
        def sources(self,window):return tuple(rows)
    paths={'a':['a'],'b':['b']}
    contacts=supports(rows,paths,floor,Revision(),with_sources=True)
    assert set(contacts['a'])=={'b'} and set(contacts['b'])=={'a'}
    assert not board_outline(floor,bodies,10)[2]['passed']
    after,cuts,_,q=run(rows,paths,bodies,floor,caps,supports=contacts)
    result=unary_union(list(after.values()));core=unary_union(list(floor.values()))
    assert q['unresolved']==0 and not sharp_points(result,core,10)
    assert result.difference(core).area>.5*unary_union(list(bodies.values())).difference(core).area
    before_image,after_image,proof=board_outline(floor,after,10)
    assert before_image.equals(core) and after_image.equals(result)
    assert proof['passed'] and proof['additional_shoulders']==0
    assert proof['complete_board_unions']==2 and proof['scene_indexes_built']==0
    with pytest.raises(ValueError,match='SOURCE_ORDER_CHANGED'):
        board_outline(floor,dict(reversed(list(after.items()))),10)


def test_fixed_pad_inside_primitive_does_not_create_an_abrupt_added_edge():
    rows,floor,bodies,caps=fixture(dict(a=[[-1,0],[1,0]]))
    pad=box(-.1,-.2,.1,.2)
    after,cuts,_,q=check(rows,floor,bodies,caps,supports={'r':pad})
    result=unary_union([after['a'],pad]);core=unary_union([floor['a'],pad])
    assert q['unresolved']==0
    assert not sharp_points(result,core,10)


def test_outline_comparisons_reuse_turns_with_identical_verdicts(monkeypatch):
    import src.gerber_u05.boundary_finish as module
    entry=box(0,0,1,1);baseline=entry.union(box(1,.2,1.1,.8));after=baseline.union(box(1.1,.4,1.2,.6))
    expected=[module.outline_images(entry,after,10,baseline=b)for b in(entry,baseline)]
    calls=[];raw=module.sharp_vertices
    def counted(body,angle):
        if body is after:calls.append(True)
        return raw(body,angle)
    monkeypatch.setattr(module,'sharp_vertices',counted)
    shared={};actual=[module.outline_images(entry,after,10,baseline=b,evaluation=shared)for b in(entry,baseline)]
    assert actual==expected and calls==[True]
    with pytest.raises(ValueError,match='SHARP_VERTEX_GEOMETRY_OR_ANGLE_CHANGED'):
        module.outline_images(entry,box(0,0,2,2),10,baseline=entry,evaluation=shared)
    with pytest.raises(ValueError,match='SHARP_VERTEX_GEOMETRY_OR_ANGLE_CHANGED'):
        module.outline_images(entry,after,11,baseline=entry,evaluation=shared)
