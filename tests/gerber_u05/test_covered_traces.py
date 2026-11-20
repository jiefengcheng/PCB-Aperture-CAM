import pytest
from shapely.geometry import box
from src.gerber_u05 import covered_traces as c
from src.stage_abi.store import canonical


def fixture():
    current=dict(hidden=box(0,0,1,.05),visible=box(1,0,2,.05),bulk=box(-.1,-.1,1.2,.2))
    rows={s:dict(kind='stroke',metadata=dict(route_kind='segment',minimum_caliper_mm=.05))for s in('hidden','visible')}
    rows['bulk']=dict(kind='region',metadata={})
    return rows,current,dict(route=['hidden','visible'])


def test_covered_occurrence_in_an_exposed_route_keeps_native_custody(tmp_path):
    rows,current,paths=fixture();before={s:g.wkb for s,g in current.items()}
    active,ledger,timing=c.prepare(tmp_path,dict(scene='first'),rows,current,paths)
    assert active==dict(route=['visible'])and ledger['covered_source_ids']==['hidden']
    assert ledger['native_source_ids_by_route']==paths and not ledger['source_ids_deleted']
    assert not ledger['reports']['visible']['fully_covered']
    assert before=={s:g.wkb for s,g in current.items()}


def test_warm_coverage_has_identical_ledger_without_repeating_geometry(tmp_path,monkeypatch):
    rows,current,paths=fixture();a,first,_=c.prepare(tmp_path,{},rows,current,paths)
    monkeypatch.setattr(c.eligibility,'classify_stroke',lambda *args,**kw:pytest.fail('recomputed coverage'))
    b,second,timing=c.prepare(tmp_path,{},rows,current,paths)
    assert a==b and canonical(first)==canonical(second)
    assert timing['hits']==2 and timing['misses']==0


def test_changed_covering_copper_invalidates_the_stage_entry_decision(tmp_path):
    rows,current,paths=fixture();active,_,_=c.prepare(tmp_path,dict(scene='before'),rows,current,paths)
    current['bulk']=box(-.1,-.1,.5,.2)
    changed,_,timing=c.prepare(tmp_path,dict(scene='after'),rows,current,paths)
    assert active==dict(route=['visible'])and changed==paths and timing['misses']==2


def test_exact_trace_aliases_cannot_cover_themselves(tmp_path):
    rows,current,paths=fixture();current.pop('bulk');rows.pop('bulk')
    current['alias']=current['hidden'];rows['alias']=rows['hidden']
    active,ledger,_=c.prepare(tmp_path,{},rows,current,paths)
    assert active==paths and ledger['covered_source_ids']==[]
    assert ledger['reports']['hidden']['ignored_exact_alias_ids']==['alias']


def test_union_of_other_copper_covers_a_trace_but_a_real_slit_does_not(tmp_path):
    rows,current,_=fixture();current['bulk']=box(-.1,-.1,.5,.2)
    rows['other']=dict(kind='region',metadata={});current['other']=box(.5,-.1,1.1,.2)
    paths=dict(route=['hidden'])
    active,ledger,_=c.prepare(tmp_path,dict(scene='closed'),rows,current,paths)
    assert active=={}and ledger['keep_routes']==['route']
    current['other']=box(.50001,-.1,1.1,.2)
    active,ledger,_=c.prepare(tmp_path,dict(scene='slit'),rows,current,paths)
    assert active==paths and ledger['reports']['hidden']['exposed_area_mm2']>0


def test_boundary_fringe_is_partial_exposure_and_cannot_freeze_a_trace(tmp_path):
    rows,current,paths=fixture();paths=dict(route=['hidden'])
    current['bulk']=box(-.1,-.1,1.1,.0499)
    before=current['hidden'].wkb
    active,ledger,_=c.prepare(tmp_path,{},rows,current,paths)
    assert active==paths and ledger['boundary_noise_covered_source_ids']==[]
    assert ledger['boundary_noise_observed_source_ids']==['hidden']
    assert not ledger['reports']['hidden']['fully_covered']
    assert current['hidden'].wkb==before


def test_long_overlapping_fill_strokes_are_fixed_but_separate_traces_are_active(tmp_path):
    from shapely.geometry import LineString
    rows={s:dict(kind='stroke',metadata=dict(route_kind='segment',minimum_caliper_mm=.05,
        route_points_mm=[[0,y],[2,y]]))for s,y in [('a',0),('b',.03),('c',.2)]}
    current={s:LineString(r['metadata']['route_points_mm']).buffer(.025)for s,r in rows.items()}
    paths={s:[s]for s in rows}
    active,ledger,_=c.prepare(tmp_path,{},rows,current,paths)
    assert active==dict(c=['c'])and ledger['fixed_fill_source_ids']==['a','b']
    assert ledger['exactly_covered_source_ids']==[]


def test_a_long_exposed_tail_cannot_be_hidden_by_a_short_fill_overlap(tmp_path):
    from shapely.geometry import LineString
    points=dict(a=[[0,0],[2,0]],b=[[.9,.03],[1.1,.03]])
    rows={s:dict(kind='stroke',metadata=dict(route_kind='segment',minimum_caliper_mm=.05,route_points_mm=p))for s,p in points.items()}
    current={s:LineString(p).buffer(.025)for s,p in points.items()}
    active,ledger,_=c.prepare(tmp_path,{},rows,current,dict(a=['a'],b=['b']))
    assert active['a']==['a']and not ledger['reports']['a']['growth_excluded']


def test_short_fill_connector_is_fixed_but_a_short_trace_leaving_bulk_is_active(tmp_path):
    from shapely.geometry import LineString
    points=dict(a=[[0,0],[2,0]],b=[[0,.03],[2,.03]],connector=[[1.98,-.023],[1.99,-.022]],trace=[[1.98,-.02],[1.98,-.06]])
    rows={s:dict(kind='stroke',metadata=dict(route_kind='segment',minimum_caliper_mm=.05,route_points_mm=p))for s,p in points.items()}
    current={s:LineString(p).buffer(.025)for s,p in points.items()}
    active,ledger,_=c.prepare(tmp_path,{},rows,current,{s:[s]for s in points})
    assert 'connector'not in active and 'connector'in ledger['fixed_fill_connector_source_ids']
    assert active['trace']==['trace']
