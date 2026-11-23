import math
import pytest
from shapely.geometry import Point,LineString,box
from src.bulk_edge_restore import fit_circular_stroke_end_flanks
from src.bulk_edge_restore import propose
from src.gerber_u05.source_edge_cleanup import CleanupBatch
from src.shared_copper_context import for_board


def flanks():
    return [[(.4*math.cos(math.radians(a)),.4*math.sin(math.radians(a)))for a in angles]
            for angles in (range(-44,-30),range(32,66))]


def test_round_stroke_endpoint_is_reference_without_using_an_offset_inner_pad():
    g=LineString([(0,0),(-1,-1)]).buffer(.3,quad_segs=512)
    row=dict(source_id='native-line',kind='stroke',metadata=dict(source_kind='Line',route_points_mm=[[0,0],[-1,-1]],
            original_width_mm=.6,aperture_family=['C',.6],gerber_ordinal=9))
    _,edge,e=fit_circular_stroke_end_flanks(*flanks(),row,g,0,box(.34,-.25,.45,.25))
    assert e['center_mm']==[0,0] and e['kind']=='CIRCULAR_VOID_FLANKS_AT_NATIVE_STROKE_ENDPOINT'
    assert abs(e['radius_mm']-.4)<1e-12 and e['native_stroke_source_id']=='native-line'
    assert edge.is_ring
    row['metadata']['aperture_family']=['R',.6]
    with pytest.raises(ValueError,match='AUTHENTIC_ROUND_NATIVE'):
        fit_circular_stroke_end_flanks(*flanks(),row,g,0,box(.34,-.25,.45,.25))


def test_curved_mask_trims_only_the_circle_intersection_and_preserves_fixed_copper(tmp_path):
    circle=Point(0,0).buffer(.4,quad_segs=512);stroke=LineString([(.5,-1),(.5,1)]).buffer(.15,quad_segs=128)
    original=dict(fill=box(-2,-2,2,2).difference(circle),stroke=stroke,fixed=Point(0,0).buffer(.299,quad_segs=128))
    rows=dict(fill=dict(kind='region',metadata={}),stroke=dict(kind='stroke',metadata=dict(route_points_mm=[[.5,-1],[.5,1]],original_width_mm=.3)),
              fixed=dict(kind='circle',metadata=dict(declared_pin=True)))
    domain=box(.34,-.25,.45,.25)
    f=dict(causing_id='stroke',domain=domain,removal_mask=domain.intersection(circle),smooth_edge=LineString(circle.exterior.coords),
           reference_evidence=dict(kind='CIRCULAR_VOID_FLANKS_AT_NATIVE_STROKE_ENDPOINT'),backing_point=(.65,0))
    with for_board(original,root=tmp_path/'context') as c:
        b=CleanupBatch(rows,original,c.source,[f],protected_source_ids=['fixed'])
        record=b.propose(0);after,proof=b.finish()
        assert proof['passed'] and proof['actual_added_mm2']<=1e-12
        assert record['conservative_area_fraction']<.1 and record['owner_authorized_free_source_end_retreats']==[]
        assert after.values['fixed'].equals_exact(original['fixed'],0)
        assert after.values['stroke'].symmetric_difference(stroke.difference(f['removal_mask'])).area<=1e-12
        assert not after.values['stroke'].equals(stroke.difference(domain))


def test_mask_mode_rejects_a_reference_with_any_extra_target_material():
    body=box(0,0,2,2);mask=box(1.9,.5,2,1.5);window=box(1.8,.4,2.1,1.6)
    reference=body.difference(mask).union(box(2,.6,2.01,.7))
    with pytest.raises(ValueError,match='EXACT_MASK_DIFFERENCE_REFERENCE_REQUIRED'):
        propose(body,reference,window,removal_mask=mask,trim_only=True,
                smooth_edge=LineString([(2,0),(2,2)]),reference_evidence=dict(kind='TEST_MASK_BINDING'))
