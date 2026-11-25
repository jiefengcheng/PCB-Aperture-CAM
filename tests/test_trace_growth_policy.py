import json
from dataclasses import replace
import pytest
from shapely.geometry import box,LineString
from src.trace_growth_policy import capture,Policy,classify,read_snapshot,capture_job,SNAPSHOT
from src.t04_settings import capture as limits,from_bytes,read_snapshot as read_limits
from src.t04_ladder import solve


def test_global_width_boundary_and_new_job_snapshot_are_frozen(tmp_path):
    policy=capture();assert policy.too_wide(.25)and policy.too_wide(.250000001)
    assert policy.too_wide(.249935)and not policy.too_wide(.24949)
    frozen=capture_job(tmp_path);assert read_snapshot(tmp_path/SNAPSHOT)==frozen
    settings=limits();assert settings.rung(.25,0)['within_growth_limits']
    assert settings.rung(.250000001,1)['blocking_reason']=='SOURCE_WIDTH_EXCEEDS_GLOBAL_LIMIT'
    assert settings.rung(.249935,1)['blocking_reason']=='NOMINAL_SOURCE_WIDTH_AT_GLOBAL_LIMIT'
    assert settings.rung(.3,0)['within_growth_limits']
    settings.write_snapshot(tmp_path/'new.json');assert read_limits(tmp_path/'new.json')==settings
    historical=from_bytes(settings._raw);historical.write_snapshot(tmp_path/'old.json')
    assert read_limits(tmp_path/'old.json')._eligibility is None
    assert read_limits(tmp_path/'old.json').rung(.3,2)['within_growth_limits']


def fixture(gap=False,small_pad=False):
    bulk=box(0,0,.5,.5)if small_pad else box(0,0,4,4)
    x=.5 if small_pad else 4
    points=[[x+.05001 if gap else x, .25 if small_pad else 2],[x+3,.25 if small_pad else 2]]
    shapes=dict(bulk=bulk,trace=LineString(points).buffer(.05),other=LineString([[10,0],[12,0]]).buffer(.2))
    rows=dict(bulk=dict(kind='region',metadata={}),trace=dict(kind='stroke',metadata=dict(minimum_caliper_mm=.1)),other=dict(kind='stroke',metadata=dict(minimum_caliper_mm=.4)))
    return rows,shapes,dict(connected=['trace'],wide=['other'])


def test_connected_large_fill_and_complete_route_are_fixed_without_contour_changes():
    rows,shapes,paths=fixture();before={s:g.wkb for s,g in shapes.items()}
    value=capture().value;value['preserve_routes_connected_to_large_fill']=True
    ledger,_=classify(rows,shapes,paths,Policy(json.dumps(value).encode()))
    assert ledger['kept_routes']['connected']==['CONNECTED_TO_LARGE_FILLED_COPPER']
    assert ledger['kept_routes']['wide']==['SOURCE_WIDTH_EXCEEDS_GLOBAL_LIMIT']
    assert set(ledger['fixed_source_ids'])==set(shapes)
    assert before=={s:g.wkb for s,g in shapes.items()}


def test_width_only_policy_releases_attached_trace_but_preserves_fill_and_wide_route():
    rows,shapes,paths=fixture()
    policy=capture();assert policy.value['preserve_routes_connected_to_large_fill']is False
    ledger,_=classify(rows,shapes,paths,policy)
    assert 'connected'not in ledger['kept_routes']
    assert 'trace'not in ledger['fixed_source_ids']
    assert ledger['kept_routes']['wide']==['SOURCE_WIDTH_EXCEEDS_GLOBAL_LIMIT']
    assert set(ledger['protected_large_fill_source_ids'])=={'bulk'}
    assert set(ledger['fixed_source_ids'])=={'bulk','other'}


@pytest.mark.parametrize('gap,small_pad',[(True,False),(False,True)])
def test_real_gap_or_ordinary_small_pad_does_not_freeze_an_eligible_trace(gap,small_pad):
    rows,shapes,paths=fixture(gap,small_pad);ledger,_=classify(rows,shapes,paths,capture())
    assert 'connected'not in ledger['kept_routes']
    assert 'other'in ledger['fixed_source_ids']


def test_kept_routes_never_build_or_evaluate_growth_proposals():
    calls=[];settings=limits()
    result=solve({'keep':.05,'grow':.05},settings,
        lambda r,f:(calls.append(r)or dict(passed=True,failures=[])),keep_routes={'keep':['CONNECTED_TO_LARGE_FILLED_COPPER']})
    assert 'keep'not in calls and result['selected_scales']['keep']==1
    assert result['selected_scales']['grow']==1.5


def test_invalid_global_parameters_and_corrupt_snapshot_reject(tmp_path):
    value=capture().value;value['maximum_eligible_source_width_mm']=float('nan')
    with pytest.raises(ValueError):Policy(json.dumps(value).encode())
    capture_job(tmp_path);value=json.loads((tmp_path/SNAPSHOT).read_bytes());value['sha256']='0'*64
    (tmp_path/SNAPSHOT).write_text(json.dumps(value))
    with pytest.raises(ValueError,match='SNAPSHOT_CHANGED'):read_snapshot(tmp_path/SNAPSHOT)


def test_original_source_job_freezes_current_policy_alongside_historical_ladder(tmp_path):
    from types import SimpleNamespace
    from src.trace_growth_policy import for_job
    from src.t04_settings import SNAPSHOT_NAME
    historical=from_bytes(limits()._raw)
    historical.write_snapshot(tmp_path/SNAPSHOT_NAME)
    frozen=capture_job(tmp_path)
    store=SimpleNamespace(root=tmp_path/'runtime')
    assert for_job(store)==frozen
    data=json.loads((tmp_path/SNAPSHOT).read_bytes());data['sha256']='f'*64
    (tmp_path/SNAPSHOT).write_text(json.dumps(data))
    with pytest.raises(ValueError,match='TRACE_ELIGIBILITY_SNAPSHOT_CHANGED'):
        for_job(store)


def test_almost_buried_route_kept_but_attached_exposed_branch_still_grows():
    shapes=dict(fill=box(0,0,10,5),buried=box(1,4.91,2,5.01),branch=box(10,2,12,2.1))
    rows={s:dict(kind='stroke',metadata=dict(minimum_caliper_mm=.1))for s in shapes}
    ledger,_=classify(rows,shapes,dict(buried=['buried'],branch=['branch']),capture())
    assert ledger['kept_routes']['buried']==['LARGELY_COVERED_BY_LARGE_FILLED_COPPER']
    assert 'branch'not in ledger['kept_routes']
    assert ledger['large_fill_route_coverage']['buried']['large_fill_coverage_fraction']==pytest.approx(.9)
    assert ledger['large_fill_route_coverage']['branch']['large_fill_coverage_fraction']==0


def test_owner_selected_eighty_percent_boundary_is_inclusive():
    assert capture().value['minimum_large_fill_coverage_fraction']==.8
    shapes=dict(fill=box(0,0,10,5),at_limit=box(1,4.75,2,5.0625),below=box(3,4.75,4,5.063))
    rows={s:dict(kind='stroke',metadata=dict(minimum_caliper_mm=.1))for s in shapes}
    ledger,_=classify(rows,shapes,dict(at_limit=['at_limit'],below=['below']),capture())
    assert ledger['large_fill_route_coverage']['at_limit']['large_fill_coverage_fraction']==.8
    assert 'at_limit'in ledger['kept_routes']and 'below'not in ledger['kept_routes']


def test_coverage_uses_complete_route_area_not_tiny_pad_entry_or_segment_count():
    shapes=dict(fill=box(0,0,10,5),entry=box(9,2,10,2.1),exposed=box(10,2,15,2.1))
    rows={s:dict(kind='stroke',metadata=dict(minimum_caliper_mm=.1))for s in shapes}
    ledger,_=classify(rows,shapes,dict(route=['entry','exposed']),capture())
    assert 'route'not in ledger['kept_routes']
    assert ledger['large_fill_route_coverage']['route']['large_fill_coverage_fraction']==pytest.approx(1/6)
    assert ledger['candidate_source_coverage']['route']['entry']['keep']
    assert not ledger['candidate_source_coverage']['route']['exposed']['keep']
    assert ledger['keep_source_reasons']['entry']==['LARGELY_COVERED_SOURCE_SEGMENT_BY_LARGE_FILLED_COPPER']
    assert 'entry'in ledger['fixed_source_ids']and 'exposed'not in ledger['fixed_source_ids']


def test_holes_other_native_traces_and_exact_aliases_cannot_establish_fill_coverage():
    fill=box(0,0,10,10).difference(box(2,2,8,8))
    trace=box(3,3,7,3.1)
    shapes=dict(fill=fill,trace=trace,alias=trace,other=box(3,3,7,3.2))
    rows={s:dict(kind='stroke',metadata=dict(minimum_caliper_mm=.1))for s in shapes}
    value=capture().value;value['revision']=5;del value['candidate_coverage_mode'];del value['coverage_granularity'];del value['source_coverage_mode']
    ledger,_=classify(rows,shapes,dict(route=['trace'],other=['other']),Policy(json.dumps(value).encode()))
    assert 'route'not in ledger['kept_routes']
    assert 'alias'not in ledger['large_fill_coverage_support_source_ids']
    assert ledger['large_fill_route_coverage']['route']['large_fill_coverage_fraction']==0


def test_previous_policy_snapshot_does_not_acquire_new_coverage_exclusion():
    value=capture().value;value['revision']=3;del value['minimum_large_fill_coverage_fraction'];del value['smooth_native_route_profiles'];del value['candidate_coverage_mode'];del value['coverage_granularity'];del value['source_coverage_mode']
    shapes=dict(fill=box(0,0,10,5),trace=box(1,4.91,2,5.01))
    rows={s:dict(kind='stroke',metadata=dict(minimum_caliper_mm=.1))for s in shapes}
    ledger,_=classify(rows,shapes,dict(route=['trace']),Policy(json.dumps(value).encode()))
    assert not ledger['kept_routes']and not ledger['large_fill_route_coverage']


def test_shared_revision_coverage_matches_standalone_after_trim_and_builds_no_owner_index(tmp_path,monkeypatch):
    from src.shared_copper_context import CopperContext
    shapes=dict(fill=box(0,0,10,5),trace=box(1,4.91,2,5.01))
    rows={s:dict(kind='stroke',metadata=dict(minimum_caliper_mm=.1))for s in shapes};paths=dict(route=['trace'])
    current=dict(shapes,fill=box(0,0,10,4.5))
    expected,_=classify(rows,current,paths,capture())
    with CopperContext(shapes,source_binding=dict(source='coverage'),frame=dict(units='mm'),root=tmp_path/'context')as context:
        context.acquire(current)
        def forbidden(*a,**k):raise AssertionError('eligibility rebuilt full-board ownership')
        monkeypatch.setattr('src.trace_growth_policy.OriginalOwners',forbidden)
        actual,_=classify(rows,current,paths,capture(),copper=context)
        assert actual==expected
        assert context.stats['source_subset_unions']==1
        assert not actual['kept_routes']


@pytest.mark.parametrize('fraction',[0,1.1,float('nan'),True])
def test_invalid_large_fill_fraction_rejects(fraction):
    value=capture().value;value['minimum_large_fill_coverage_fraction']=fraction
    with pytest.raises(ValueError,match='INVALID_LARGE_FILL_COVERAGE_POLICY'):Policy(json.dumps(value).encode())


def test_independent_native_stroke_artwork_covers_candidate_before_growth():
    shapes=dict(trace=box(0,0,2,.1),left=box(-.1,-.01,1.1,.11),right=box(1,-.01,2.1,.11))
    rows={s:dict(kind='stroke',metadata=dict(minimum_caliper_mm=.1))for s in shapes}
    ledger,_=classify(rows,shapes,dict(route=['trace'],artwork=['left','right']),capture())
    assert ledger['kept_routes']['route']==['LARGELY_COVERED_BY_OTHER_ENTRY_COPPER']
    record=ledger['candidate_route_coverage']['route']
    assert record['other_entry_coverage_fraction']==1
    assert record['support_source_ids']==['left','right']
    assert ledger['large_fill_route_coverage']['route']['large_fill_coverage_fraction']==0


def test_complete_route_and_exact_member_aliases_never_cover_themselves():
    shapes=dict(a=box(0,0,2,.1),b=box(.01,0,2.01,.1),alias=box(0,0,2,.1))
    rows={s:dict(kind='stroke',metadata=dict(minimum_caliper_mm=.1))for s in shapes}
    ledger,_=classify(rows,shapes,dict(route=['a','b']),capture())
    assert 'route'not in ledger['kept_routes']
    assert ledger['candidate_route_coverage']['route']['other_entry_coverage_fraction']==0
    assert ledger['candidate_route_coverage']['route']['support_source_ids']==[]


def test_direct_candidate_coverage_respects_holes_exposure_and_eighty_percent():
    shapes=dict(at=box(0,0,1,.1),below=box(0,1,1,1.1),exposed=box(0,2,1,2.1),
        cover_a=box(0,0,.8,.1),cover_b=box(0,1,.799,1.1),
        hole=box(-1,1.5,2,3).difference(box(-.1,1.9,1.1,2.2)))
    rows={s:dict(kind='stroke',metadata=dict(minimum_caliper_mm=.1))for s in shapes}
    ledger,_=classify(rows,shapes,dict(at=['at'],below=['below'],exposed=['exposed']),capture())
    assert ledger['candidate_route_coverage']['at']['other_entry_coverage_fraction']==pytest.approx(.8)
    assert 'at'in ledger['kept_routes']and 'below'not in ledger['kept_routes']and 'exposed'not in ledger['kept_routes']


def test_candidate_coverage_borrows_revision_source_index_after_trim(tmp_path):
    from src.shared_copper_context import CopperContext
    shapes=dict(trace=box(0,0,1,.1),support=box(-.1,-.01,1.1,.11))
    current=dict(shapes,support=box(-.1,-.01,.5,.11))
    rows={s:dict(kind='stroke',metadata=dict(minimum_caliper_mm=.1))for s in shapes}
    with CopperContext(shapes,source_binding=dict(source='candidate'),frame=dict(units='mm'),root=tmp_path/'context')as context:
        first,_=classify(rows,shapes,dict(route=['trace']),capture(),copper=context)
        second,_=classify(rows,current,dict(route=['trace']),capture(),copper=context)
        third,_=classify(rows,current,dict(route=['trace']),capture(),copper=context)
        assert first['candidate_route_coverage']['route']['keep']
        assert not second['candidate_route_coverage']['route']['keep']
        assert second==third
        assert context.stats['revision_overlay_index_builds']==1
        # Three coverage queries plus one bounded revision-publication query
        # borrow the same source index; publication no longer scans every owner.
        assert context.stats['source_queries']==4
        assert context.stats['source_index_builds']==1


def test_each_piece_uses_its_own_area_and_retains_exposed_neighbour(tmp_path):
    from src.gerber_u05.covered_traces import prepare
    shapes=dict(at=box(0,0,1,.1),below=box(1,0,2,.1),tail=box(2,0,8,.1),
        cover_a=box(-4,-3,.8,3),cover_b=box(1,-3,1.799,3))
    rows={s:dict(kind='stroke',metadata=dict(minimum_caliper_mm=.1,route_kind='segment'))for s in shapes}
    paths=dict(route=['at','below','tail'])
    ledger,_=classify(rows,shapes,paths,capture())
    assert 'route'not in ledger['kept_routes']
    records=ledger['candidate_source_coverage']['route']
    assert records['at']['other_entry_coverage_fraction']==pytest.approx(.8)
    assert records['at']['keep']and not records['below']['keep']and not records['tail']['keep']
    active,coverage,_=prepare(tmp_path,{},rows,shapes,paths,fixed_source_reasons=ledger['keep_source_reasons'])
    assert active==dict(route=['below','tail'])
    assert coverage['reports']['at']['growth_excluded']and not coverage['reports']['at']['fully_covered']


def test_piece_coverage_reuses_shared_route_query_and_excludes_siblings_and_aliases(tmp_path):
    from src.shared_copper_context import CopperContext
    shapes=dict(a=box(0,0,2,.1),b=box(.01,0,2.01,.1),alias=box(0,0,2,.1),
        exposed=box(2,0,6,.1),cover=box(-3,-3,1.8,3))
    rows={s:dict(kind='stroke',metadata=dict(minimum_caliper_mm=.1))for s in shapes}
    paths=dict(route=['a','b','exposed'])
    expected,_=classify(rows,shapes,paths,capture())
    with CopperContext(shapes,source_binding=dict(source='pieces'),frame=dict(units='mm'),root=tmp_path/'context')as context:
        actual,_=classify(rows,shapes,paths,capture(),copper=context)
        assert actual==expected
        assert context.stats['source_queries']==1
        assert context.stats['source_index_builds']==1
    records=actual['candidate_source_coverage']['route']
    assert records['a']['other_entry_coverage_fraction']==pytest.approx(.9)
    assert records['b']['other_entry_coverage_fraction']==pytest.approx(.895)
    assert not records['exposed']['keep']


def test_revision_six_keeps_original_route_only_semantics():
    value=capture().value;value['revision']=6;del value['coverage_granularity'];del value['source_coverage_mode']
    shapes=dict(fill=box(0,0,1,.1),entry=box(0,0,1,.1),tail=box(1,0,5,.1))
    # An independent non-alias cover, so the historical route is genuinely partial.
    shapes['fill']=box(-.01,-.01,1,.11)
    rows={s:dict(kind='stroke',metadata=dict(minimum_caliper_mm=.1))for s in shapes}
    ledger,_=classify(rows,shapes,dict(route=['entry','tail']),Policy(json.dumps(value).encode()))
    assert 'candidate_source_coverage'not in ledger
    assert 'entry'not in ledger['keep_source_reasons']


def test_invalid_piece_policy_rejects():
    value=capture().value;value['coverage_granularity']='ROUTE_ONLY'
    with pytest.raises(ValueError,match='INVALID_COVERAGE_GRANULARITY'):Policy(json.dumps(value).encode())


@pytest.mark.parametrize('pad_kind',['rectangle','circle'])
def test_ordinary_pad_overlap_does_not_freeze_partly_exposed_source_piece(tmp_path,pad_kind):
    from src.gerber_u05.covered_traces import prepare
    from shapely.geometry import Point
    shapes=dict(pad=box(-.1,-.2,.89,.2),entry=box(0,0,1,.1),tail=box(1,0,5,.1))
    if pad_kind=='circle':shapes['pad']=Point(.445,.05).buffer(.445,quad_segs=128)
    rows={s:dict(kind=pad_kind if s=='pad'else'stroke',metadata=dict(minimum_caliper_mm=.1,route_kind='segment'))for s in shapes}
    paths=dict(route=['entry','tail'])
    ledger,_=classify(rows,shapes,paths,capture())
    assert 'entry'not in ledger['keep_source_reasons']
    assert ledger['candidate_source_coverage']['route']['entry']['other_entry_coverage_fraction']==0
    active,_,_=prepare(tmp_path,{},rows,shapes,paths,fixed_source_reasons=ledger['keep_source_reasons'])
    assert active==paths
    old=capture().value;old['revision']=7;del old['source_coverage_mode']
    previous,_=classify(rows,shapes,paths,Policy(json.dumps(old).encode()))
    assert previous['candidate_source_coverage']['route']['entry']['keep']


def test_invalid_source_coverage_mode_rejects():
    value=capture().value;value['source_coverage_mode']='ANY_PAD'
    with pytest.raises(ValueError,match='INVALID_SOURCE_COVERAGE_MODE'):Policy(json.dumps(value).encode())
