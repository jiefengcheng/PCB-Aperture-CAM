from shapely.geometry import box
import pytest
from src.viewer_abi.copper_cleanup import cleanup_cases


def test_saved_rule_and_original_causing_area_not_fill_area_are_displayed():
    original=dict(fill=box(0,0,5,5),trace=box(-.1,1,.1,1.1))
    removed=box(-.1,1,0,1.1)
    rows={s:dict(metadata=dict(gerber_ordinal=i)) for i,s in enumerate(original)}
    stage=dict(owner_marked_shallow_straight_edges=dict(records=[dict(source_id='trace',
        area_noise_check=dict(original_feature_area_mm2=original['trace'].area,
                              protrusion_area_mm2=removed.area,is_noise=False),
        geometry_checks=dict(reference_evidence=dict(first=[[0,.5],[0,.8]],second=[[0,1.2],[0,1.5]])))]),
        owner_detected_supported_edge_cleanup=dict(deferred=[dict(bounds_mm=[2,2,3,3],reason='AREA_RULE_NOT_ESTABLISHED')]))
    data=cleanup_cases(stage,rows,original,removed,box(10,10,11,11),lambda g:(g,0))
    assert len(data['cases'])==2
    case=data['cases'][0]
    assert case['sources'][0]['originalAreaMM2']==original['trace'].area
    assert case['sources'][0]['areaFraction']>.1
    assert case['rule']=='SHALLOW_SOURCE_EDGE'
    assert case['referencePath'].startswith('M ') and ' Z' not in case['referencePath']
    assert data['cases'][1]['status']=='unresolved'
    assert data['areaComparison']=='STRICTLY_LESS_THAN'


def test_no_cleanup_is_inferred_from_unrelated_trace_growth():
    original=dict(a=box(0,0,1,1))
    result=cleanup_cases({},dict(a=dict(metadata={})),original,box(0,0,0,0),box(1,0,2,1),lambda g:(g,0))
    assert result['cases']==[]


def test_generic_multiple_places_on_one_cause_keep_their_own_exact_witnesses():
    from shapely.ops import unary_union
    original=dict(fill=box(0,0,4,4),trace=box(-.02,.5,.2,3.5))
    rows={s:dict(metadata={}) for s in original}
    cuts=[box(-.01,1,0,1.1),box(-.02,3,0,3.1)]
    findings=[]
    for y,cut in zip((1,3),cuts):
        proof=dict(causing_source_id='trace',rule='AREA_NOISE',
            original_feature_area_mm2=original['trace'].area,whole_physical_protrusion_area_mm2=cut.area,
            geometry_checks=dict(reference_evidence=dict(first=[[0,y-.2],[0,y-.1]],second=[[0,y+.2],[0,y+.3]])))
        findings.append(dict(status='corrected',bounds_mm=list(cut.buffer(.001).bounds),proof=proof))
    saved=cleanup_cases(dict(operation='TRIM_ONLY',large_copper_cleanup=dict(findings=findings)),rows,
        original,unary_union(cuts),box(0,0,0,0),lambda g:(g,0))
    for case in saved['cases']:
        source=case['sources'][0]
        assert source['protrudingAreaMM2']==pytest.approx(case['areaMM2'])
        y=case['bounds']['y']
        assert str(y-.2) in case['referencePath']


def test_trim_only_presentation_rejects_positive_material():
    with pytest.raises(ValueError,match='TRIM_ONLY_PRESENTATION_CONTAINS_ADDITION'):
        cleanup_cases(dict(operation='TRIM_ONLY'),dict(a=dict(metadata={})),
                      dict(a=box(0,0,2,2)),box(0,0,0,0),box(2,0,3,1),lambda g:(g,0))


def test_review_retains_actual_causing_pad_area_and_over_limit_reason():
    original=dict(fill=box(0,0,5,5),pad=box(-.1,1,.1,1.1));rows={s:dict(metadata={})for s in original}
    review=dict(review_number=1,index=4,status='unresolved',bounds_mm=[-.1,1,0,1.1],causing_source_id='pad',
                ordinal=7,original_feature_area_mm2=original['pad'].area,whole_physical_protrusion_area_mm2=.01,
                area_fraction=.5,depth_mm=.1,reason='OVER_TEN_PERCENT',reference_evidence={},explanation='Place 1/8: above ten percent; kept.')
    stage=dict(owner_detected_supported_edge_cleanup=dict(deferred=[dict(index=4,bounds_mm=review['bounds_mm'])]),
               owner_unresolved_place_review=dict(records=[review]))
    data=cleanup_cases(stage,rows,original,box(0,0,0,0),box(0,0,0,0),lambda g:(g,0));case=data['cases'][0]
    assert case['reviewNumber']==1 and case['areaMM2']==.01 and case['sources'][0]['areaFraction']==.5
    assert case['disposition']==review['explanation'] and case['sources'][0]['originalAreaMM2']==original['pad'].area
    review['original_feature_area_mm2']=1
    with pytest.raises(ValueError,match='SOURCE_AREA_CHANGED'):
        cleanup_cases(stage,rows,original,box(0,0,0,0),box(0,0,0,0),lambda g:(g,0))


def test_ignored_rectangle_is_navigable_without_a_saved_trim():
    original=dict(fill=box(0,0,5,5),pad=box(-.01,1,.3,1.3));rows={s:dict(metadata={})for s in original}
    review=dict(review_number=8,index=18,status='ignored',bounds_mm=[-.1,.9,0,1.4],causing_source_id='pad',ordinal=8,
                original_feature_area_mm2=original['pad'].area,whole_physical_protrusion_area_mm2=.003,
                area_fraction=.003/original['pad'].area,depth_mm=.01,reason='RECTANGULAR_BUMPS_DEFERRED_BY_OWNER',
                reference_evidence={},explanation='Place 8/8: rectangular bumps ignored; original retained.')
    data=cleanup_cases(dict(operation='TRIM_ONLY',owner_unresolved_place_review=dict(records=[review])),rows,original,
                       box(0,0,0,0),box(0,0,0,0),lambda g:(g,0))
    assert len(data['cases'])==1 and data['cases'][0]['status']=='ignored' and data['cases'][0]['reviewNumber']==8
    assert all(p['kind']=='source'for p in data['parts'])


def test_round_stroke_end_reference_is_visible_as_a_circular_edge():
    original=dict(fill=box(0,0,5,5),trace=box(-.01,1,.2,1.1));rows={s:dict(metadata={})for s in original}
    removed=box(-.01,1,0,1.1)
    stage=dict(owner_marked_circular_edge_corrections=dict(noise_area_checks=[dict(case='end',source_id='trace',
        original_feature_area_mm2=original['trace'].area,protrusion_area_mm2=removed.area)],records=[dict(case='end',proof=dict(reference_evidence=dict(
        kind='CIRCULAR_VOID_FLANKS_AT_NATIVE_STROKE_ENDPOINT',native_stroke_ordinal=9,maximum_radial_fit_error_mm=.001)))]))
    data=cleanup_cases(stage,rows,original,removed,box(0,0,0,0),lambda g:(g,0));case=data['cases'][0]
    assert case['boundaryKind']=='circular' and 'source trace 9' in case['disposition']
    assert 'reference trace is unchanged' in case['disposition']


def test_isolated_view_contains_treated_big_copper_without_highlighted_trace_growth():
    original=dict(fill=box(0,0,5,5),other_fill=box(10,0,15,5),trace=box(-.01,1,.1,1.1))
    rows={s:dict(metadata=dict(gerber_ordinal=i)) for i,s in enumerate(original)}
    removed=box(-.01,1,0,1.1);unrelated_added_trace=box(8,8,9,9)
    stage=dict(source_pad_cleanup=dict(fill_source_ids=['fill','other_fill']),
               owner_supported_physical_noise_corrections=dict(records=[dict(causing_source_id='trace',
                   original_feature_area_mm2=original['trace'].area,whole_physical_protrusion_area_mm2=removed.area)]))
    data=cleanup_cases(stage,rows,original,removed,unrelated_added_trace,lambda g:(g,0),layer='F.Cu')
    assert len(data['objects'])==1 and data['objects'][0]['areaMM2']>=25
    assert data['cases'][0]['objectIDs']==['bulk:0']
    assert not any(p['kind']=='added' for p in data['parts'])
    assert all(p['bounds']['x']+p['bounds']['width']<=5 for p in data['parts'])
    assert all(p['layer']=='F.Cu' for p in data['parts'])
