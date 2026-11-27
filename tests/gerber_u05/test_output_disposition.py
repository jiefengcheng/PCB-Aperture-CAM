import copy
import pytest
from shapely.geometry import LineString,box
from src.gerber_u05 import group_board_job as board
from src.gerber_u05.group_components import positive_addition
from src.gerber_u05.output_disposition import outline_disposition,ENDPOINT_REASON,combine_findings


def reviewed_stage():
    return dict(publication_ready=False,output_scene_ref=None,hybrid_components=dict(
        reference_checks=dict(passed=True),functional_checks=dict(passed=True),bulk=dict(error=None),
        joint_connections=dict(reports=[dict(passed=True)]),constructed_groups_audited=0,
        constructed_group_bytes_preserved=True,covered_trace_copper_preserved=True,
        frozen_endpoint_obligations=dict(passed=False,failures=[dict(reason=ENDPOINT_REASON,
            endpoint_mm=[1.,2.],source_id='s',route_id='r',missing_section_length_mm=.015)]),
        corner_smoothing=dict(unresolved=1,pocket_completion=dict(passed=False,rejected_enclosures=0,reports=[],
            original_source_baseline=dict(schema='t04-source-baseline-joint-pockets/1',original_holes_preserved=True,
                constructed_group_bytes_changed=False,records=[dict(status='KEEP_UNQUALIFIED',reason='OUTSIDE_ADMITTED_JOINT_CAPS',
                    bounds_mm=[1.,2.,1.01,2.01],area_mm2=.00003,pocket_sha256='a'*64)]))),
        boundary_transitions=dict(schema='t04-retained-widening-bridges/1',unresolved=0,partial=1,
            preserved_unresolved=True,reports=[],copper_budgets=dict(passed=True),
            final_dependency_checks=dict(passed=False,groups=[dict(passed=False,source_floor_preserved=True,
                new_pockets=0,new_corners_mm=[[3.,4.]],source_ids=['s'])]))))


def test_finishing_findings_allow_completion_and_preserve_failed_raw_verdicts():
    stage=reviewed_stage();before=copy.deepcopy(stage)
    result=board.checked(stage)
    assert stage==before
    assert result['output_valid']is True
    assert result['completion']=='COMPLETED_WITH_REVIEW_FINDINGS'
    assert {r['kind']for r in result['review_findings']}=={'endpoint','corner','unfilled_pocket'}
    assert result['pockets']is False and result['frozen_endpoint_obligations']['passed']is False


@pytest.mark.parametrize('defect',['spacing','connection','source_loss','budget','unknown_endpoint',
                                 'missing_floor_proof','new_bridge_pocket','unknown_pocket','protected_copper'])
def test_invalid_or_unproven_output_still_stops(defect):
    stage=reviewed_stage();h=stage['hybrid_components'];t=h['boundary_transitions']
    if defect=='spacing':h['functional_checks']['passed']=False
    elif defect=='connection':h['joint_connections']['reports'][0]['passed']=False
    elif defect=='source_loss':t['final_dependency_checks']['groups'][0]['source_floor_preserved']=False
    elif defect=='budget':t['copper_budgets']['passed']=False
    elif defect=='unknown_endpoint':h['frozen_endpoint_obligations']['failures'][0]['reason']='UNKNOWN'
    elif defect=='missing_floor_proof':del t['final_dependency_checks']['groups'][0]['source_floor_preserved']
    elif defect=='new_bridge_pocket':t['final_dependency_checks']['groups'][0]['new_pockets']=1
    elif defect=='protected_copper':h['covered_trace_copper_preserved']=False
    else:h['corner_smoothing']['pocket_completion']['original_source_baseline']['records'][0]['reason']='MATERIAL_OR_ATTACHMENT_MISMATCH'
    with pytest.raises(ValueError,match='COMPONENT_FAILURE'):board.checked(stage)


def outline(**changes):
    return dict(dict(passed=False,new_pockets=0,additional_shoulders=1,points_mm=[[3.,4.]],
                     bridge_net_growth_area_mm2=.0001),**changes)


def test_outline_quality_does_not_turn_into_a_geometry_error():
    receipt=outline();before=copy.deepcopy(receipt);result=outline_disposition(receipt)
    assert result['output_valid']and result['completion']=='COMPLETED_WITH_REVIEW_FINDINGS'
    assert receipt==before and not receipt['passed']
    child=outline_disposition(outline(additional_shoulders=0,points_mm=[],shoulder_phase=receipt))
    assert child['output_valid']


@pytest.mark.parametrize('changes',[dict(bridge_net_growth_area_mm2=-.0001),dict(new_pockets=1),
                                   dict(points_mm=[]),dict(points_mm=[],additional_shoulders=0)])
def test_outline_material_errors_or_unknown_failure_remain_fatal(changes):
    assert not outline_disposition(outline(**changes))['output_valid']


def test_source_recovery_is_not_growth_but_true_added_copper_keeps_its_clearance_check():
    source=LineString([(0.,0.),(1.,0.)]).buffer(.025,quad_segs=128)
    reference=source.difference(box(.4,-.03,.6,.03))
    assert not source.difference(reference).is_empty
    assert positive_addition(source,reference,source).is_empty
    actual=source.union(box(.4,.025,.6,.04));neighbor=box(.4,.07,.6,.1)
    added=positive_addition(actual,reference,source)
    assert added.area>0 and added.distance(neighbor)<.0401


def test_one_review_place_can_retain_multiple_saved_check_reasons():
    a=dict(kind='corner',severity='REVIEW',point_mm=[1.,2.],reason='LOCAL')
    b=dict(a,reason='ASSEMBLED')
    combined=combine_findings([a],[b])
    assert len(combined)==1 and combined[0]['reasons']==['LOCAL','ASSEMBLED']


def test_growth_into_previously_trimmed_space_is_still_new_copper():
    raw=box(0,0,1,1);trimmed=box(0,0,.8,1)
    added=positive_addition(raw,trimmed,trimmed)
    assert added.area==pytest.approx(.2)
