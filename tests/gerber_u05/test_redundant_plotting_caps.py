import copy
import pytest
from shapely.geometry import box,Point,LineString
from src.shared_copper_context import for_board
from src.bulk_edge_restore import fit_straight_flanks,propose
from src.gerber_u05.source_edge_cleanup import CleanupBatch
from src.gerber_image import disk


def fixture():
    points=[[-.02,2],[2,2]];circle=disk(points[0],.0254)
    shapes=dict(fill=box(0,0,4,4),trace=LineString(points).buffer(.0254,quad_segs=128),cap1=circle,cap2=circle)
    rows={s:dict(kind='stroke',metadata={}) for s in shapes}
    rows['trace']['metadata']=dict(route_points_mm=points,original_width_mm=.0508)
    for s in ('cap1','cap2'):
        rows[s]=dict(kind='circle',metadata=dict(center_mm=points[0],radius_mm=.0254,qualified_land=True,
                                               alias_source_ids=['cap1','cap2']))
    domain=box(-.1,1.8,0,2.2);edge=LineString([(0,1),(0,3)])
    _,evidence=fit_straight_flanks([(0,1.5),(0,1.7)],[(0,2.3),(0,2.5)],(.2,2),domain)
    return rows,shapes,dict(causing_id='trace',domain=domain,smooth_edge=edge,reference_evidence=evidence,backing_point=(.2,2))


def test_duplicate_covered_endpoint_flashes_trim_with_the_whole_under_ten_percent_bump(tmp_path):
    rows,g,f=fixture();before=copy.deepcopy(rows)
    with for_board(g,root=tmp_path/'context') as c:
        batch=CleanupBatch(rows,g,c.source,[f],allow_redundant_flashes=True)
        record=batch.propose(0);after,proof=batch.finish()
        assert record['conservative_area_fraction']<.1
        assert len(record['redundant_endpoint_flash_trims'])==2
        assert not after.values['cap1'].covers(Point(-.02,2))
        assert proof['actual_added_mm2']==0 and proof['clearance_checks']==proof['clearance_searches']==0
        assert rows==before and rows['cap1']['metadata']['qualified_land']


@pytest.mark.parametrize('reason',['protected_alias','explicit_terminal','wrong_width','no_duplicate'])
def test_real_or_unproved_terminals_remain_protected(tmp_path,reason):
    rows,g,f=fixture();protected=()
    if reason=='protected_alias':protected=('cap1',)
    if reason=='explicit_terminal':rows['cap2']['metadata']['declared_terminal']=True
    if reason=='wrong_width':rows['trace']['metadata']['original_width_mm']=.1
    if reason=='no_duplicate':
        for s in ('cap1','cap2'):rows[s]['metadata']['alias_source_ids']=[s]
    with for_board(g,root=tmp_path/'context') as c:
        batch=CleanupBatch(rows,g,c.source,[f],allow_redundant_flashes=True,protected_source_ids=protected)
        with pytest.raises(ValueError,match='TERMINAL_SHAPE_TOUCHED'):batch.propose(0)


def test_trim_only_rejects_any_recess_addition_before_clearance_work():
    body=box(0,0,2,2);reference=box(0,0,2.01,2);window=box(1.9,.9,2.1,1.1)
    with pytest.raises(ValueError,match='TRIM_ONLY_ADDITION_FORBIDDEN'):
        propose(body,reference,window,smooth_edge=LineString([(2,0),(2,2)]),
                reference_evidence=dict(kind='TEST_SOURCE_FLANKS'),trim_only=True,
                foreign=[('unneeded',box(10,10,11,11))])


def test_single_flash_requires_two_distinct_matching_endpoint_strokes(tmp_path):
    from src.gerber_u05.redundant_plotting_caps import qualify
    rows,g,f=fixture()
    for s in ('cap1','cap2'):rows[s]['metadata']['alias_source_ids']=[s]
    rows['second']=dict(kind='stroke',metadata=dict(route_points_mm=[[-.02,2],[2,2.1]],original_width_mm=.0508))
    g['second']=LineString(rows['second']['metadata']['route_points_mm']).buffer(.0254,quad_segs=128)
    with for_board(g,root=tmp_path/'paired') as c:
        proof=qualify(rows,g,c.source,'cap1')
        assert proof['endpoint_support']=='TWO_DISTINCT_MATCHING_APERTURE_STROKES'
        assert not proof['source_family_reclassified']


@pytest.mark.parametrize('shape',['circle','rectangle'])
def test_explicit_pad_noise_trim_retains_center_and_all_contacts(tmp_path,shape):
    core=disk((.11,2),.15) if shape=='circle' else box(-.01,1.8,.3,2.2)
    g=dict(fill=box(0,0,4,4),pad=core)
    rows=dict(fill=dict(kind='region',metadata={}),pad=dict(kind=shape,metadata=dict(alias_source_ids=['pad'])))
    if shape=='circle':rows['pad']['metadata'].update(center_mm=[.11,2],radius_mm=.15)
    domain=box(-.1,1.7,0,2.3);edge=LineString([(0,1),(0,3)])
    _,e=fit_straight_flanks([(0,1.5),(0,1.6)],[(0,2.4),(0,2.5)],(.2,2),domain)
    f=dict(causing_id='pad',domain=domain,smooth_edge=edge,reference_evidence=e,backing_point=(.2,2))
    with for_board(g,root=tmp_path/shape) as c:
        with pytest.raises(ValueError,match='EXPLICIT_CAUSING_PAD|RECTANGULAR_BUMPS_DEFERRED'):CleanupBatch(rows,g,c.source,[f]).propose(0)
        if shape=='rectangle':
            with pytest.raises(ValueError,match='RECTANGULAR_BUMPS_DEFERRED'):
                CleanupBatch(rows,g,c.source,[f],allow_causing_pads=True).propose(0)
        b=CleanupBatch(rows,g,c.source,[f],allow_causing_pads=True,allow_causing_rectangles=shape=='rectangle')
        r=b.propose(0);after,proof=b.finish()
        assert r['causing_pad_trim'] and r['conservative_area_fraction']<.1
        assert after.values['pad'].covers(core.centroid) and proof['actual_added_mm2']==0
        rows['pad']['metadata']['declared_pin']=True
        with pytest.raises(ValueError,match='PROTECTED_OR_UNBOUND'):
            CleanupBatch(rows,g,c.source,[f],allow_causing_pads=True,allow_causing_rectangles=shape=='rectangle').propose(0)


def test_nearby_pad_cannot_supply_area_denominator_for_an_unrelated_bump(tmp_path):
    rows,g,f=fixture();rows['cap1']['metadata']['alias_source_ids']=['cap1']
    g['cap1']=box(-.001,1.85,.4,2.15);rows['cap1']=dict(kind='rectangle',metadata={})
    f['causing_id']='cap1'
    with for_board(g,root=tmp_path/'unrelated') as c:
        with pytest.raises(ValueError,match='PHYSICAL_BUMP_NOT_CONTAINED'):
            CleanupBatch(rows,g,c.source,[f],allow_causing_pads=True,allow_causing_rectangles=True).propose(0)
