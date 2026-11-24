import json
import pytest
from shapely.geometry import box
from shapely import to_wkb
from src.viewer_abi.publisher import digest,encode
from src.viewer_abi.t04_workspace import build,findings,saved_input,review_places


def fixture():
    stage=dict(summary=dict(routes=2,keep_covered_routes=3),hybrid_components=dict(
        corner_smoothing=dict(reports=[dict(status='FILLED',endpoint_mm=[1,1]),
            dict(status='KEEP_UNRESOLVED',endpoint_mm=[2,2],route_id='r',source_id='s',
                 attempts=[dict(reasons=['CORNER_TRANSITION_TOO_SHORT'])])]),
        frozen_endpoint_obligations=dict(failures=[dict(reason='FROZEN_END_SECTION_NOT_REALIZED_BY_EMITTED_ROUTE',
            route_id='r',source_id='s',endpoint_mm=[3,3],missing_section_length_mm=.001)])))
    report=dict(checks=dict(native_connections=5),settings=dict(maximum_factor=1.5,maximum_total_width_increase_mm=.03))
    return stage,report


def test_t04_partition_uses_cleaned_input_and_does_not_relabel_inherited_trims():
    stage,report=fixture();cleaned=box(0,0,1,1);result=box(0,0,1.1,1)
    value=build(stage,report,cleaned,result,layer='F.Cu',source_sha='a'*64,input_sha='b'*64)
    assert value['removedAreaMM2']==0 and value['addedAreaMM2']==pytest.approx(.1)
    assert {p['kind']for p in value['parts']}=={'source','added'}
    assert all(p['id'].startswith('growth:t04:')for p in value['parts'])
    assert value['inputSceneSHA256']=='b'*64 and value['connectionChecks']==5


def test_saved_corner_and_endpoint_findings_remain_distinct_and_explained():
    stage,_=fixture();items=findings(stage)
    assert [f['kind']for f in items]==['corner','endpoint']
    assert 'Too little trace length' in items[0]['description']
    assert items[1]['missingSectionMM']==.001
    assert len({f['id']for f in items})==2


def test_bounded_scope_and_eighty_percent_policy_are_saved_display_data():
    stage,report=fixture();stage['full_board_run']=False
    report['settings']['trace_eligibility']=dict(source_json=json.dumps(dict(minimum_large_fill_coverage_fraction=.8)))
    value=build(stage,report,box(0,0,1,1),box(0,0,1.1,1),layer='F.Cu',source_sha='a'*64,input_sha='b'*64)
    assert value['fullBoard']is False and value['largeFillCoverageFraction']==.8


def test_kept_route_and_smoothed_chain_have_saved_navigation_without_becoming_unresolved_findings():
    stage,report=fixture();stage.update(requested_routes=['keep','grow'],native_trace_source_ids_by_route=dict(keep=['a'],grow=['b']),
        trace_eligibility_policy=dict(kept_routes=dict(keep=['LARGELY_COVERED_BY_LARGE_FILLED_COPPER']),
            large_fill_route_coverage=dict(keep=dict(large_fill_coverage_fraction=.85))))
    stage['hybrid_components']['residual_end_matching']=dict(reports=[dict(optional_floor_replaced=True,
        shared_contour_sha256='a'*64,route_id='grow',source_ids=['b'])])
    places=review_places(stage,dict(a=box(0,0,1,1),b=box(3,0,4,1)))
    assert [p['kind']for p in places]==['eligibility','continuity']
    assert '85.000%'in places[0]['description']
    assert len(findings(stage))==2


def test_cleaned_input_requires_exact_bound_scene_and_geometry_bytes(tmp_path):
    original={'s':box(0,0,2,1)};cleaned=box(0,0,1,1);folder=tmp_path/'runtime/artifacts';folder.mkdir(parents=True)
    raw=to_wkb(cleaned);ref=dict(artifact_id='geometry:'+digest(raw),sha256=digest(raw));(folder/ref['artifact_id']).write_bytes(raw)
    data=encode(dict(objects=[dict(source_id='s',geometry_ref=ref)]));scene=dict(artifact_id='scene:'+digest(data),sha256=digest(data));(folder/scene['artifact_id']).write_bytes(data)
    report=dict(inputs=dict(trimmed_entry_scene_ref=scene));value,sha=saved_input(report,tmp_path/'RESULT.json',original)
    assert value['s'].equals(cleaned)and sha==scene['sha256']
    (folder/ref['artifact_id']).write_bytes(to_wkb(original['s']))
    with pytest.raises(ValueError,match='(CHANGED|checksum|CHECKSUM)'):
        saved_input(report,tmp_path/'RESULT.json',original)
