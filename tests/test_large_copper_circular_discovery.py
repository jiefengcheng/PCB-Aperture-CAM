import pytest
from shapely import to_wkb
from shapely.geometry import Point,LineString,box
from shapely.affinity import translate
from src.bulk_edge_restore import fit_circular_void_flanks
from src.large_copper_circular_discovery import patches,flank_runs
from src.large_copper_discovery import discover
from src.shared_copper_context import CopperContext
from src.gerber_u05.source_edge_cleanup import CleanupBatch


def example():
    circle=Point(0,0).buffer(.5,quad_segs=512)
    values=dict(fill=box(-2,-2,2,2).difference(circle),
                trace=LineString([(.48,0),(1.6,0)]).buffer(.02,quad_segs=128),
                anchor=Point(0,0).buffer(.2,quad_segs=128))
    rows=dict(fill=dict(kind='fixed_source',metadata={}),
        trace=dict(kind='stroke',metadata=dict(source_kind='Line',route_points_mm=[[.48,0],[1.6,0]],
                   original_width_mm=.04,aperture_family=['C',.04])),
        anchor=dict(kind='circle',metadata=dict(center_mm=[0,0],radius_mm=.2)))
    return rows,values


def test_native_center_discovers_complete_flat_cap_without_ordinals_or_windows(tmp_path):
    rows,values=example()
    with CopperContext(values,source_binding=dict(source_sha256='a'*64),
          frame=dict(units='mm',axes='X_RIGHT_Y_DOWN'),root=tmp_path/'ctx') as ctx:
        fs,findings,coverage=discover(rows,values,ctx.source)
        curved=[f for f in fs if f['reference_evidence']['kind'].startswith('CIRCULAR')]
        assert len(curved)==1
        f=curved[0]
        assert f['causing_id']=='trace' and f['reference_owner']==ctx.source.owner('anchor')[0]
        assert f['reference_evidence']['radius_mm']==pytest.approx(.5,abs=1e-12)
        # The minimum lies INSIDE the long flat native edge, not at a vertex.
        assert .5-f['removal_mask'].distance(Point(0,0))==pytest.approx(.04,abs=1e-6)
        batch=CleanupBatch(rows,values,ctx.source,[f],preserve_causing_paths=True,
                           allow_causing_free_end_trim=True)
        record=batch.propose(0);after,proof=batch.finish()
        assert record['bounded_free_end_trim']['original_ends_only']
        assert proof['actual_added_mm2']==0 and proof['passed']
        assert to_wkb(after.values['anchor'])==to_wkb(values['anchor'])


def test_circular_discovery_translation_and_authenticated_reopen_are_deterministic(tmp_path):
    rows,values=example();results=[]
    for iteration in range(2):
        with CopperContext(values,source_binding=dict(source_sha256='b'*64),
              frame=dict(units='mm',axes='X_RIGHT_Y_DOWN'),root=tmp_path/'same') as ctx:
            fs,findings,coverage=discover(rows,values,ctx.source)
            results.append(([to_wkb(f['removal_mask']) for f in fs],findings,coverage))
    assert results[0]==results[1]
    moved={k:translate(g,17,-31) for k,g in values.items()}
    rows['trace']['metadata']['route_points_mm']=[[17.48,-31],[18.6,-31]]
    rows['anchor']['metadata']['center_mm']=[17,-31]
    with CopperContext(moved,source_binding=dict(source_sha256='c'*64),
          frame=dict(units='mm',axes='X_RIGHT_Y_DOWN'),root=tmp_path/'moved') as ctx:
        fs,_,_=discover(rows,moved,ctx.source)
        curved=[f for f in fs if f['reference_evidence']['kind'].startswith('CIRCULAR')]
        assert len(curved)==1 and curved[0]['causing_id']=='trace'
        assert curved[0]['reference_evidence']['center_mm']==[17,-31]


def test_long_chord_is_not_a_circular_flank_even_if_its_vertices_fit():
    import math
    pts=[(.5*math.cos(math.radians(a)),.5*math.sin(math.radians(a))) for a in (-40,0,40)]
    assert not flank_runs([pts],[0,0],.5,Point(9,9).buffer(.1))


def test_bounded_area_noise_free_end_exception_never_removes_path_interior(tmp_path):
    values=dict(fill=box(0,0,4,4),trace=LineString([(.5,1),(-.01,2),(.5,3)]).buffer(.02,quad_segs=128))
    rows=dict(fill=dict(kind='fixed_source',metadata={}),trace=dict(kind='stroke',metadata=dict(
         route_points_mm=[[.5,1],[-.01,2],[.5,3]],original_width_mm=.04,source_kind='Arc')))
    with CopperContext(values,source_binding=dict(source_sha256='d'*64),
          frame=dict(units='mm',axes='X_RIGHT_Y_DOWN'),root=tmp_path/'ctx') as ctx:
        fs,_,_=discover(rows,values,ctx.source)
        assert len(fs)==1
        batch=CleanupBatch(rows,values,ctx.source,fs,preserve_causing_paths=True,allow_causing_free_end_trim=True)
        with pytest.raises(ValueError,match='ORIGINAL_CAUSING_TRACE_PATH_LOST'):
            batch.propose(0)
        assert not batch.records and not batch.cuts


def test_hidden_inner_pad_cannot_supply_round_endpoint_reference():
    from src.large_copper_circular_discovery import native_exposure
    body=LineString([(0,0),(.6,0)]).buffer(.3,quad_segs=128)
    assert native_exposure(body,[0,0],.3)[0]>170
    assert native_exposure(body,[.003,0],.1)[0]<10


def test_accepted_reference_owner_is_immutable_and_changed_reference_rejects(tmp_path):
    values=dict(a=box(0,0,4,4),ta=LineString([(.01,2),(2,2)]).buffer(.0254,quad_segs=128),
                b=box(10,0,14,4),tb=LineString([(10.01,2),(12,2)]).buffer(.0254,quad_segs=128))
    rows={k:dict(kind='fixed_source',metadata={}) for k in values}
    for sid,x in [('ta',.01),('tb',10.01)]:
        rows[sid]=dict(kind='stroke',metadata=dict(source_kind='Line',route_points_mm=[[x,2],[x+1.99,2]],original_width_mm=.0508))
    with CopperContext(values,source_binding=dict(source_sha256='e'*64),
          frame=dict(units='mm',axes='X_RIGHT_Y_DOWN'),root=tmp_path/'ctx') as ctx:
        fs,_,_=discover(rows,values,ctx.source);by={f['causing_id']:f for f in fs}
        first=dict(by['ta'],reference_owner=ctx.source.owner('b')[0]);second=by['tb']
        batch=CleanupBatch(rows,values,ctx.source,[first,second])
        batch.propose(0)
        with pytest.raises(ValueError,match='ACCEPTED_REFERENCE_OWNER_MUST_REMAIN_UNCHANGED'):
            batch.propose(1)
        assert len(batch.records)==1 and batch.working['tb'].wkb==values['tb'].wkb
        reverse=CleanupBatch(rows,values,ctx.source,[second,first]);reverse.propose(0)
        with pytest.raises(ValueError,match='ORIGINAL_REFERENCE_OWNER_ALREADY_CHANGED'):
            reverse.propose(1)


def test_circular_flanks_cross_atan2_branch_cut_without_relaxing_fit():
    import math
    points=lambda low,high:[(.5*math.cos(math.radians(a)),.5*math.sin(math.radians(a)))
                           for a in range(low,high+1)]
    _,_,e=fit_circular_void_flanks(points(175,195),points(40,60),[0,0],box(-1,-1,1,1))
    assert e['radius_mm']==pytest.approx(.5,abs=1e-12)
    assert e['maximum_radial_fit_error_mm']<=1e-12
    with pytest.raises(ValueError,match='DISJOINT_CIRCULAR_FLANKS_REQUIRED'):
        fit_circular_void_flanks(points(175,195),points(-179,-165),[0,0],box(-1,-1,1,1))


def test_opposite_curvature_cannot_masquerade_as_native_void_flank():
    import math
    from src.large_copper_circular_discovery import curves_away_from_center
    arc=lambda cx,angles:[(cx+.5*math.cos(math.radians(a)),.5*math.sin(math.radians(a))) for a in angles]
    assert curves_away_from_center(arc(0,[-30,-15,0,15,30]),[0,0])
    assert not curves_away_from_center(arc(1,[150,165,180,195,210]),[0,0])
    assert not curves_away_from_center([(.5,-.1),(.5,0),(.5,.1)],[0,0])


def test_native_flanks_cannot_mix_two_holes_and_reverse_restores_source_order(tmp_path):
    from src.large_copper_circular_discovery import bind_native_ring
    from shapely.geometry import Polygon
    body=box(-2,-1,2,1).difference(Point(-.6,0).buffer(.3,quad_segs=128)).difference(Point(.6,0).buffer(.3,quad_segs=128))
    with CopperContext(dict(fill=body),source_binding=dict(source_sha256='f'*64),
          frame=dict(units='mm',axes='X_RIGHT_Y_DOWN'),root=tmp_path/'ctx') as ctx:
        _,native=ctx.source.owner('fill');sections=ctx.boundary_sections(native,native.envelope)
        first=list(native.interiors[0].coords);second=list(native.interiors[1].coords)
        center=Polygon(native.interiors[0]).centroid.coords[0]
        cap=native.intersection(Point(center).buffer(.31,quad_segs=128))
        with pytest.raises(ValueError,match='CIRCULAR_FLANKS_AND_BUMP_NOT_ONE_NATIVE_RING'):
            bind_native_ring(native,sections,dict(first=first[:20],second=second[:20]),cap,center)
        ordered,identity,order=bind_native_ring(native,sections,
            dict(first=list(reversed(first[:20])),second=first[100:120]),cap,center)
        assert ordered['first']==first[:20] and identity==(0,1)
        assert order[0]=='RESTORED_NATIVE_FORWARD'


def test_unrelated_owner_changes_do_not_invalidate_an_unchanged_native_reference(tmp_path):
    values=dict(a=box(0,0,4,4),ta=LineString([(.01,2),(2,2)]).buffer(.0254,quad_segs=128),
                b=box(10,0,14,4),tb=LineString([(10.01,2),(12,2)]).buffer(.0254,quad_segs=128))
    rows={k:dict(kind='fixed_source',metadata={}) for k in values}
    for sid,x in [('ta',.01),('tb',10.01)]:
        rows[sid]=dict(kind='stroke',metadata=dict(source_kind='Line',route_points_mm=[[x,2],[x+1.99,2]],original_width_mm=.0508))
    with CopperContext(values,source_binding=dict(source_sha256='1'*64),
          frame=dict(units='mm',axes='X_RIGHT_Y_DOWN'),root=tmp_path/'ctx') as ctx:
        fs,_,_=discover(rows,values,ctx.source);by={f['causing_id']:f for f in fs}
        caller_ids=['b']
        f=dict(by['ta'],reference_owner=ctx.source.owner('b')[0],reference_source_ids=caller_ids)
        batch=CleanupBatch(rows,values,ctx.source,[by['tb'],f],preserve_reference_flanks=True)
        caller_ids[0]='tb'  # source custody is frozen before external mutation
        batch.propose(0);batch.propose(1)
        after,proof=batch.finish()
        assert proof['passed'] and after.values['b'].wkb==values['b'].wkb
