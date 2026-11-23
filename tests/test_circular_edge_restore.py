import math
import pytest
from shapely.geometry import Point, box
from src.bulk_edge_restore import fit_circular_void_flanks, propose


def arc(lo, hi, radius=1.):
    return [(radius*math.cos(math.radians(a)),radius*math.sin(math.radians(a)))
            for a in range(lo,hi+1)]


def test_intruding_fill_is_trimmed_without_deleting_isolated_round_pad():
    domain=box(-2,-2,2,2)
    reference,edge,evidence=fit_circular_void_flanks(arc(-75,-45),arc(45,75),(0,0),domain)
    # The surrounding fill intrudes 50 um into the right side of the void.
    fill=domain.difference(Point(0,0).buffer(1.,quad_segs=512)).union(box(.95,-.3,2,.3))
    pad=Point(0,0).buffer(.7)
    result,removed,added,proof=propose(fill,reference,box(.94,-.35,1.05,.35),
        protected=[('round-pad',pad)],reference_evidence=evidence,smooth_edge=edge)
    assert proof['passed'] and removed.area>0 and added.is_empty
    assert result.distance(pad)>=fill.distance(pad)
    assert removed.intersection(pad).is_empty
    assert result.difference(fill).is_empty


def test_incompatible_arc_supports_reject_instead_of_guessing():
    with pytest.raises(ValueError,match='DISAGREE'):
        fit_circular_void_flanks(arc(-75,-45),arc(45,75,1.02),(0,0),box(-2,-2,2,2))
    with pytest.raises(ValueError,match='DISJOINT'):
        fit_circular_void_flanks(arc(-75,-45),arc(-60,-30),(0,0),box(-2,-2,2,2))


def test_large_intrusion_is_rejected_in_one_pass():
    domain=box(-2,-2,2,2)
    reference,edge,evidence=fit_circular_void_flanks(arc(-75,-45),arc(45,75),(0,0),domain)
    fill=reference.union(box(.8,-.3,2,.3))
    _,_,_,proof=propose(fill,reference,box(.79,-.35,1.05,.35),
        reference_evidence=evidence,smooth_edge=edge)
    assert not proof['passed'] and 'EDGE_RESTORATION_DEPTH_LIMIT'in proof['failures']


def test_protected_connection_cannot_be_trimmed():
    domain=box(-2,-2,2,2)
    reference,edge,evidence=fit_circular_void_flanks(arc(-75,-45),arc(45,75),(0,0),domain)
    fill=reference.union(box(.95,-.3,2,.3));connection=box(.94,-.01,1.1,.01)
    _,_,_,proof=propose(fill,reference,box(.94,-.35,1.05,.35),protected=[('connection',connection)],
        reference_evidence=evidence,smooth_edge=edge)
    assert not proof['passed'] and 'PROTECTED_FEATURE_CHANGED:connection'in proof['failures']


def test_zero_area_overlay_fragments_do_not_become_copper():
    from shapely.geometry import GeometryCollection, LineString
    material=box(-1,-1,1,0)
    reference=GeometryCollection([material,LineString([(-.1,.01),(.1,.01)])])
    result,removed,added,proof=propose(material,reference,box(-.2,-.1,.2,.1),
        reference_evidence={'fixture':'overlay-only line'},smooth_edge=LineString([(-1,0),(1,0)]))
    assert proof['passed'] and result.equals(material)
    assert removed.is_empty and added.is_empty and result.geom_type=='Polygon'


def test_shallow_rule_can_admit_a_short_source_artifact_above_ten_percent():
    from shapely.geometry import LineString
    from src.bulk_edge_restore import shallow_trace_edge_check, fit_straight_flanks
    from src.edge_restoration_settings import classify_protrusion
    trace=box(0,-.05,.1,0);cut=box(0,-.0177,.1,0)
    _,evidence=fit_straight_flanks([(-.2,-.0177),(-.1,-.0177)],[(.2,-.0177),(.3,-.0177)],(0,-.04),box(-1,-1,1,1))
    assert not classify_protrusion(cut,trace,source_id='short-stroke')['is_noise']
    proof=shallow_trace_edge_check(cut,trace,LineString([(0,-.025),(.1,-.025)]),
        LineString([(-1,-.0177),(1,-.0177)]),.05,evidence)
    assert proof['passed'] and proof['original_path_preserved']
    from src.stage_abi.contracts import finite_json
    finite_json(proof)


def test_circular_reference_receipt_is_plain_json_for_saved_constructions():
    from src.stage_abi.contracts import finite_json
    _,_,receipt=fit_circular_void_flanks(arc(-75,-45),arc(45,75),(0,0),box(-2,-2,2,2))
    finite_json(receipt)


def test_shallow_rule_cannot_cut_a_source_path_or_omit_flank_proof():
    from shapely.geometry import LineString
    from src.bulk_edge_restore import shallow_trace_edge_check, fit_straight_flanks
    trace=box(0,-.05,.1,0);cut=box(0,-.03,.1,0);path=LineString([(0,-.025),(.1,-.025)])
    _,evidence=fit_straight_flanks([(-.2,-.03),(-.1,-.03)],[(.2,-.03),(.3,-.03)],(0,-.04),box(-1,-1,1,1))
    proof=shallow_trace_edge_check(cut,trace,path,LineString([(-1,0),(1,0)]),.05,evidence)
    assert not proof['passed'] and 'ORIGINAL_TRACE_PATH_LOST'in proof['failures']
    with pytest.raises(ValueError,match='SOURCE_SUPPORTED'):
        shallow_trace_edge_check(cut,trace,path,LineString([(-1,0),(1,0)]),.05,{})
