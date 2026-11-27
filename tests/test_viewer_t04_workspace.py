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


def test_touching_display_images_have_no_copper_in_their_shared_wire():
    stage,report=fixture()
    value=build(stage,report,box(0,0,1,1),box(1,0,2,1),
        layer='F.Cu',source_sha='a'*64,input_sha='b'*64)
    assert {p['kind']for p in value['parts']}=={'added','removed'}
    assert value['addedAreaMM2']==value['removedAreaMM2']==1


def test_display_area_parts_retain_tiny_faces_and_ignore_only_zero_area():
    from shapely.geometry import GeometryCollection,LineString,Point
    from src.viewer_abi.board_growth import area_parts
    tiny=box(0,0,1e-10,1e-10);large=box(1,1,2,2)
    mixed=GeometryCollection([LineString([(0,0),(1,0)]),
        GeometryCollection([tiny,Point(0,0)]),large])
    assert [to_wkb(g)for g in area_parts(mixed)]==[to_wkb(tiny),to_wkb(large)]


def test_saved_corner_and_endpoint_findings_remain_distinct_and_explained():
    stage,_=fixture();items=findings(stage)
    assert [f['kind']for f in items]==['corner','endpoint']
    assert 'Too little trace length' in items[0]['description']
    assert items[1]['missingSectionMM']==.001
    assert len({f['id']for f in items})==2


def test_completed_review_result_keeps_endpoint_corner_and_unfilled_pocket_places():
    stage,report=fixture()
    reviews=[dict(kind='corner',reason='FINISHED_BOUNDARY_HAS_SHARP_POINT',point_mm=[4.,5.],source_ids=['s']),
             dict(kind='unfilled_pocket',reason='OUTSIDE_ADMITTED_JOINT_CAPS',bounds_mm=[6.,7.,6.01,7.01])]
    stage['hybrid_components']['output_review_findings']=reviews
    report.update(completion='COMPLETED_WITH_REVIEW_FINDINGS',review_findings=reviews)
    data=build(stage,report,box(0,0,1,1),box(0,0,1.1,1),layer='F.Cu',source_sha='a'*64,input_sha='b'*64)
    assert data['completion']=='COMPLETED_WITH_REVIEW_FINDINGS'
    assert 'completed with review findings'in data['summary']
    assert [f['kind']for f in data['findings']]==['corner','endpoint','corner','pocket']
    assert all(f['severity']=='REVIEW'for f in data['findings'])
    assert data['findings'][1]['missingSectionMM']==.001


def test_transition_navigation_uses_saved_angle_and_explicit_growth_withdrawal():
    stage,report=fixture()
    stage['hybrid_components']['boundary_transitions']=dict(maximum_transition_angle_degrees=10.,reports=[
        dict(route_id='r',point_mm=[4,5],source_ids=['s'],kind='THREE_WAY',status='SMOOTHED',optional_growth_withdrawn=True)])
    record=findings(stage)[-1]
    assert record['kind']=='transition' and record['bounds']==dict(x=3.8,y=4.8,width=.4,height=.4)
    assert '10.0 degrees' in record['description'] and 'withdrawn' in record['description']


def test_terminal_handoff_stays_pending_in_a_distinct_saved_list():
    stage,_=fixture()
    stage['hybrid_components']['boundary_transitions']=dict(deferred_terminals=[dict(
        route_id='r',source_ids=['trace'],land_ids=['pad'],points_mm=[[1,2]])])
    record=findings(stage)[-1]
    assert record['kind']=='terminal'and record['reasons']==['DEFERRED_TO_T05']
    assert record['sourceIDs']==['trace','pad']and 'pending'in record['description']


def test_withdrawn_old_chain_recipe_is_not_advertised_as_final_growth():
    stage,_=fixture()
    stage['hybrid_components'].update(residual_end_matching=dict(reports=[dict(
        optional_floor_replaced=True,shared_contour_sha256='a'*64,route_id='r',source_ids=['s'])]),
        boundary_transitions=dict(chains=[dict(source_ids=['s'],recipe=None)]))
    assert not any(r['kind']=='continuity'for r in review_places(stage,{'s':box(0,0,1,1)}))


def test_unchanged_normal_chain_record_survives_finishing_elsewhere():
    stage,_=fixture()
    stage['hybrid_components'].update(residual_end_matching=dict(reports=[dict(
        optional_floor_replaced=True,shared_contour_sha256='a'*64,route_id='r',source_ids=['s'])]),
        boundary_transitions=dict(chains=[dict(source_ids=['other'],recipe=None)]))
    assert any(r['kind']=='continuity'for r in review_places(stage,{'s':box(0,0,1,1)}))


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


def test_covered_segment_in_exposed_route_is_navigable_from_saved_measurements():
    stage,_=fixture();stage.update(requested_routes=['r'],native_trace_source_ids_by_route=dict(r=['a','b']),
        trace_eligibility_policy=dict(kept_routes={},candidate_source_coverage=dict(r=dict(
            a=dict(keep=True,other_entry_coverage_fraction=.996),
            b=dict(keep=False,other_entry_coverage_fraction=.2)))))
    places=review_places(stage,dict(a=box(0,0,1,1),b=box(1,0,10,1)))
    assert len(places)==1 and places[0]['sourceIDs']==['a']and places[0]['routeID']=='r'
    assert places[0]['kind']=='eligibility'and '99.600%'in places[0]['description']
    assert places[0]['bounds']['width']==pytest.approx(1.08)


def test_large_fill_segment_explanation_does_not_claim_ordinary_pad_coverage():
    stage,_=fixture();stage.update(requested_routes=['r'],trace_eligibility_policy=dict(
        kept_routes={},candidate_source_coverage=dict(r=dict(a=dict(keep=True,
            basis='INDEPENDENT_BROAD_FILL',other_entry_coverage_fraction=.866)))))
    places=review_places(stage,dict(a=box(0,0,1,1)))
    assert 'Large filled copper covers 86.600%'in places[0]['description']
    assert 'Ordinary pad overlap does not'in places[0]['description']
    assert places[0]['reasons']==['LARGELY_COVERED_SOURCE_SEGMENT_BY_LARGE_FILLED_COPPER']


def test_saved_gap_bridges_show_net_gain_and_held_gaps_preserve_widening():
    stage,_=fixture()
    stage['hybrid_components']['boundary_transitions']=dict(schema='t04-growth-gap-bridges/1',
        maximum_transition_angle_degrees=10.,reports=[
            dict(route_id='r',point_mm=[1,2],source_ids=['s'],status='BRIDGED',added_area_mm2=.02,
                 removed_area_mm2=.01,net_growth_area_mm2=.01),
            dict(route_id='q',point_mm=[2,3],source_ids=['t'],status='UNRESOLVED',reason='WIDTH_CAP')])
    records=[r for r in findings(stage)if r['kind']=='transition']
    assert len(records)==2 and 'net gain 0.010000000'in records[0]['description']
    assert 'previous widening is unchanged'in records[1]['description'].lower()
    assert all('only preceding optional growth was removed'not in r['description']for r in records)


def test_rejected_floor_overlay_is_explained_without_claiming_actual_copper_loss():
    from src.viewer_abi.t04_workspace import bridge_reason
    text=bridge_reason('BASELINE_RETAINED; SOURCE_FLOOR_POSITIVE_COPPER_STILL_MISSING,LOCAL_GROWTH_LOSS')
    assert 'proposed overlay'in text and 'rejected'in text and 'would remove more'in text
    assert 'SOURCE_FLOOR'not in text
