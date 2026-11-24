import math
import pytest
from shapely.geometry import LineString
from src.gerber_u05.raster_fill import RasterFill
from src.gerber_u05.covered_traces import prepare


def scene():
    width=.2
    pts=[[2*math.cos(t),2*math.sin(t)] for t in [i*.04 for i in range(-10,11)]]
    rows={'curve':dict(kind='stroke',metadata=dict(route_kind='arc',minimum_caliper_mm=width,route_points_mm=pts))}
    original={'curve':LineString(pts).buffer(width/2)}
    for i,p in enumerate(pts):
        sid=f'hatch-{i}';op=[[p[0]-.0025,p[1]],[p[0]+.0025,p[1]]]
        rows[sid]=dict(kind='stroke',metadata=dict(route_kind='segment',minimum_caliper_mm=width,route_points_mm=op))
        original[sid]=LineString(op).buffer(width/2)
    return rows,original


def test_original_hatches_prove_fill_role_without_claiming_finite_containment(tmp_path):
    rows,original=scene();before={s:g.wkb for s,g in original.items()}
    proof=RasterFill(rows,original).witness('curve')
    assert proof['original_interior_fully_in_hatch_copper']
    assert len(proof['original_hatch_source_ids'])>=3
    active,ledger,_=prepare(tmp_path,{},rows,original,{'route':['curve']},original=original)
    assert active=={} and ledger['fixed_raster_fill_source_ids']==['curve']
    assert ledger['reports']['curve']['raster_fill_witness']==proof
    assert {s:g.wkb for s,g in original.items()}==before


@pytest.mark.parametrize('case',['isolated','missing_middle','wrong_aperture','repeated_aliases','partial_pad'])
def test_actual_exposure_or_aliases_cannot_establish_raster_fill(case):
    rows,original=scene()
    if case=='isolated':original={'curve':original['curve']};rows={'curve':rows['curve']}
    if case=='missing_middle':
        for i in range(7,14):rows.pop(f'hatch-{i}');original.pop(f'hatch-{i}')
    if case=='wrong_aperture':
        for k in rows:
            if k!='curve':rows[k]['metadata']['minimum_caliper_mm']=.1
    if case=='repeated_aliases':
        for k in rows:
            if k!='curve':original[k]=original['hatch-0']
    if case=='partial_pad':
        for i in range(3,21):rows.pop(f'hatch-{i}');original.pop(f'hatch-{i}')
    assert RasterFill(rows,original).witness('curve') is None


def test_owner_keep_is_explicit_not_a_false_coverage_proof(tmp_path):
    pts=[[0,0],[2,0]];rows={'s':dict(kind='stroke',metadata=dict(route_kind='segment',minimum_caliper_mm=.1,route_points_mm=pts))}
    copper={'s':LineString(pts).buffer(.05)}
    active,ledger,_=prepare(tmp_path,{},rows,copper,{'route':['s']},keep_source_ids=['s'])
    assert active=={} and ledger['owner_keep_source_ids']==['s']
    assert not ledger['reports']['s']['fully_covered']
    assert ledger['reports']['s']['owner_requested_keep']
    with pytest.raises(ValueError,match='SELECTED_NATIVE_SOURCE'):
        prepare(tmp_path,{},rows,copper,{'route':['s']},keep_source_ids=['unknown'])
