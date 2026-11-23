import pytest
from shapely.geometry import box, LineString, Point
from src.large_copper_discovery import discover
from src.shared_copper_context import CopperContext
from src.gerber_u05.source_edge_cleanup import CleanupBatch


def fixture(x=.01, y=2):
    values=dict(fill=box(0,0,4,4), trace=LineString([(x,y),(2,y)]).buffer(.0254,quad_segs=128))
    rows=dict(fill=dict(kind='fixed_source',metadata={}), trace=dict(kind='stroke',metadata=dict(
        source_kind='Line', route_points_mm=[[x,y],[2,y]],original_width_mm=.0508)))
    return rows,values


def context(tmp_path,values):
    return CopperContext(values,source_binding=dict(source_sha256='a'*64),
        frame=dict(units='mm',axes='X_RIGHT_Y_DOWN'),root=tmp_path/'context')


def test_discovers_without_ordinals_or_windows_and_preserves_path(tmp_path):
    rows,values=fixture()
    with context(tmp_path,values) as copper:
        features,findings,coverage=discover(rows,values,copper.source)
        assert len(features)==len(findings)==1
        assert features[0]['causing_id']=='trace'
        assert findings[0]['area_fraction']<.1 and coverage[0]['edges']>4
        batch=CleanupBatch(rows,values,copper.source,features,
                           preserve_source_paths=True,preserve_all_contacts=True)
        batch.propose(0)
        revision,proof=batch.finish()
        assert proof['passed'] and proof['actual_added_mm2']==0
        assert revision.values['trace'].bounds[0]>=-1e-12
        assert copper.stats['cleanup_batch_board_unions']==1
        assert copper.stats['boundary_index_builds']==1


def test_translation_and_overlap_do_not_supply_another_denominator(tmp_path):
    from shapely.affinity import translate
    rows,values=fixture()
    values={s:translate(g,17,-31) for s,g in values.items()}
    rows['trace']['metadata']['route_points_mm']=[[17.01,-29],[19,-29]]
    values['fragment']=values['trace'].intersection(box(16.98,-29.01,17,-28.99))
    rows['fragment']=dict(kind='fixed_source',metadata={})
    with context(tmp_path,values) as copper:
        fs,findings,_=discover(rows,values,copper.source)
        assert len(fs)==1 and findings[0]['causing_source_id']=='trace'
        assert findings[0]['physical_protrusion_area_mm2']==pytest.approx(values['trace'].difference(values['fill']).area)


def test_no_larger_nearby_pad_can_supply_unrelated_denominator(tmp_path):
    rows,values=fixture()
    values['pad']=Point(.12,2).buffer(.1)
    rows['pad']=dict(kind='circle',metadata=dict(center_mm=[.12,2]))
    with context(tmp_path,values) as copper:
        fs,findings,_=discover(rows,values,copper.source)
        assert fs[0]['causing_id']=='trace' and findings[0]['original_feature_area_mm2']==values['trace'].area


def test_rectangle_bump_is_ignored_and_curve_support_is_explicit(tmp_path):
    rows,values=fixture()
    values['trace']=box(-.01,1.99,.3,2.01)
    rows['trace']=dict(kind='rectangle',metadata={})
    with context(tmp_path,values) as copper:
        fs,findings,coverage=discover(rows,values,copper.source)
        assert not fs and findings[0]['status']=='ignored'
        assert coverage[0]['completeness'].startswith('EXACT_STRAIGHT_SURVEY')


def test_execution_rejects_source_path_retreat_without_mutating_batch(tmp_path):
    rows,values=fixture(x=-.02)
    with context(tmp_path,values) as copper:
        fs,_,_=discover(rows,values,copper.source)
        batch=CleanupBatch(rows,values,copper.source,fs,preserve_source_paths=True)
        with pytest.raises(ValueError,match='ORIGINAL_SOURCE_PATH_LOST'):batch.propose(0)
        assert not batch.records and not batch.cuts
        assert all(g.wkb==batch.working[s].wkb for s,g in values.items())


def test_ambiguous_native_causes_are_unresolved_not_largest_pad(tmp_path):
    rows,values=fixture()
    values['other']=LineString([(.01,2),(3,2)]).buffer(.0254,quad_segs=128)
    rows['other']=dict(kind='stroke',metadata=dict(route_points_mm=[[.01,2],[3,2]],original_width_mm=.0508))
    with context(tmp_path,values) as copper:
        fs,findings,_=discover(rows,values,copper.source)
        assert not fs and findings[0]['reason']=='AMBIGUOUS_CAUSING_SOURCE'


def test_compound_stroke_bump_uses_full_union_not_containment_or_fill_area(tmp_path):
    from src.large_copper_discovery import select_cause
    rows,values=fixture()
    # A second small original drawing extends beyond the main stroke. It must
    # neither disappear from the numerator nor prevent finding that stroke.
    values['fragment']=box(-.017,1.997,.01,2.003)
    rows['fragment']=dict(kind='fixed_source',metadata={})
    with context(tmp_path,values) as copper:
        cap=copper.source.image().difference(values['fill'])
        sid,candidates,error=select_cause(rows,values,copper.source,cap)
        assert sid=='trace' and error is None
        assert cap.difference(values['trace']).area>1e-12
        features,findings,_=discover(rows,values,copper.source)
        assert len(features)==1 and findings[0]['causing_source_id']=='trace'
        assert findings[0]['physical_protrusion_area_mm2']==pytest.approx(cap.area)
        batch=CleanupBatch(rows,values,copper.source,features,preserve_source_paths=True,preserve_all_contacts=True)
        record=batch.propose(0);after,proof=batch.finish()
        assert record['whole_physical_protrusion_area_mm2']==pytest.approx(cap.area)
        assert record['original_feature_area_mm2']==values['trace'].area
        assert proof['actual_added_mm2']==0


def test_larger_denominator_does_not_win_over_greater_physical_support(tmp_path):
    from src.large_copper_discovery import select_cause
    rows,values=fixture()
    values['long_trace']=LineString([(.019,2.01),(30,2.01)]).buffer(.0254,quad_segs=128)
    rows['long_trace']=dict(kind='stroke',metadata=dict(route_points_mm=[[.019,2.01],[30,2.01]],original_width_mm=.0508))
    cap=values['trace'].difference(values['fill'])
    with context(tmp_path,values) as copper:
        sid,candidates,error=select_cause(rows,values,copper.source,cap)
        assert values['long_trace'].area>values['trace'].area
        assert sid=='trace' and error is None


def test_degenerate_collinear_intervening_edge_is_not_a_polygon(tmp_path):
    from shapely.geometry import Polygon
    # Exact source rings can retain extra collinear vertices. Two supports
    # separated by just one such edge enclose no physical protrusion.
    values=dict(fill=Polygon([(0,0),(4,0),(4,4),(0,4),(0,3),(0,2),(0,1),(0,0)]))
    rows=dict(fill=dict(kind='fixed_source',metadata={}))
    with context(tmp_path,values) as copper:
        features,findings,coverage=discover(rows,values,copper.source)
        assert not features and not findings and coverage[0]['edges']==7


def test_subdivided_supports_are_one_native_flank(tmp_path):
    from shapely.geometry import Polygon
    rows,values=fixture()
    # Every source edge along this flank is shorter than MIN_SUPPORT_MM.
    # Their connected straight run supplies the same actual boundary.
    values['fill']=Polygon([(0,0),(4,0),(4,4),(0,4),
                            *[(0,i/100) for i in range(399,0,-1)]])
    with context(tmp_path,values) as copper:
        features,findings,_=discover(rows,values,copper.source)
        assert len(features)==1
        assert findings[0]['causing_source_id']=='trace'
        batch=CleanupBatch(rows,values,copper.source,features,
                           preserve_source_paths=True,preserve_all_contacts=True)
        batch.propose(0)
        _,proof=batch.finish()
        assert proof['passed'] and proof['actual_added_mm2']==0


def test_recess_next_to_bump_does_not_hide_bump_or_get_filled(tmp_path):
    from shapely.geometry import Polygon
    rows,values=fixture()
    recess=Polygon([(0,1.96),(.01,1.97),(0,1.975)])
    values['fill']=values['fill'].difference(recess)
    with context(tmp_path,values) as copper:
        fs,findings,_=discover(rows,values,copper.source)
        assert len(fs)==1 and findings[0]['causing_source_id']=='trace'
        batch=CleanupBatch(rows,values,copper.source,fs,preserve_source_paths=True,preserve_all_contacts=True)
        batch.propose(0);after,proof=batch.finish()
        assert after.image().intersection(recess).area<=1e-12
        assert proof['actual_added_mm2']==0


def test_thin_branch_requires_same_connected_broad_original_component(tmp_path):
    from shapely.ops import unary_union
    values=dict(fill=unary_union([box(0,0,4,4),box(3,1.9,6,2.02)]),
                trace=LineString([(5,1.91),(5,2.01)]).buffer(.02,quad_segs=128))
    rows=dict(fill=dict(kind='fixed_source',metadata={}),trace=dict(kind='stroke',metadata=dict(
        source_kind='Line',route_points_mm=[[5,1.91],[5,2.01]],original_width_mm=.04)))
    with context(tmp_path,values) as copper:
        fs,findings,_=discover(rows,values,copper.source)
        assert fs and all(f['connected_broad_polygon']==0 for f in fs)
        batch=CleanupBatch(rows,values,copper.source,fs,preserve_source_paths=True,preserve_all_contacts=True)
        for i in range(len(fs)):batch.propose(i)
        _,proof=batch.finish()
        assert proof['passed'] and proof['actual_added_mm2']==0
    # A disconnected broad polygon must not lend its area to a small trace.
    values['fill']=unary_union([box(0,0,4,4),box(4.5,1.9,6,2.02)])
    with context(tmp_path/'disconnected',values) as copper:
        assert not discover(rows,values,copper.source)[0]


def test_same_original_source_always_produces_same_saved_treatment(tmp_path):
    rows,values=fixture()
    results=[]
    for name in ('first','reopened'):
        with context(tmp_path/name,values) as copper:
            fs,findings,coverage=discover(rows,values,copper.source)
            batch=CleanupBatch(rows,values,copper.source,fs,
                               preserve_source_paths=True,preserve_all_contacts=True)
            for i in range(len(fs)):batch.propose(i)
            after,proof=batch.finish()
            results.append(([g.wkb for g in after.values.values()],findings,coverage,
                            proof['actual_removed_mm2'],batch.records))
    assert results[0]==results[1]


def test_cumulative_limit_counts_whole_compound_bumps_not_only_trace_overlap(tmp_path):
    rows,values=fixture()
    values['trace']=LineString([(.01,2),(3.99,2)]).buffer(.0254,quad_segs=128)
    rows['trace']['metadata']['route_points_mm']=[[.01,2],[3.99,2]]
    for name,g in [('left',box(-.09,1.94,.01,2.06)),('right',box(3.99,1.94,4.09,2.06))]:
        values[name]=g;rows[name]=dict(kind='fixed_source',metadata={})
    with context(tmp_path,values) as copper:
        fs,findings,_=discover(rows,values,copper.source)
        assert len(fs)==2 and all(f['area_fraction']<.1 for f in findings)
        batch=CleanupBatch(rows,values,copper.source,fs,preserve_source_paths=True,preserve_all_contacts=True)
        first=batch.propose(0)
        assert first['whole_physical_protrusion_area_mm2']>values['trace'].difference(batch.working['trace']).area
        with pytest.raises(ValueError,match='WHOLE_PHYSICAL_PROTRUSION_NOT_BELOW_AREA_LIMIT'):
            batch.propose(1)
        assert len(batch.records)==1


def test_survey_does_not_build_indexes_for_objects_without_features(tmp_path):
    values={str(i):box(10*i,0,10*i+4,4) for i in range(20)}
    rows={s:dict(kind='fixed_source',metadata={}) for s in values}
    with context(tmp_path,values) as copper:
        features,findings,coverage=discover(rows,values,copper.source)
        assert not features and not findings and len(coverage)==20
        assert copper.stats['boundary_index_builds']==0


def test_discovery_budget_rejects_without_truncating_or_changing_source(tmp_path):
    rows,values=fixture()
    with context(tmp_path,values) as copper:
        copper.limit=copper.weight+1
        with pytest.raises(ValueError,match='DISCOVERY_CAPACITY_EXCEEDED'):
            discover(rows,values,copper.source)
        assert all(v.wkb==copper.source.values[s].wkb for s,v in values.items())
