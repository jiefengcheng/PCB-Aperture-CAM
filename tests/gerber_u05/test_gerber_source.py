"""Legacy source, polarity, source-width and unchanged production-policy controls."""
import copy,math
import pytest
from shapely import from_wkb,to_wkb
from shapely.geometry import box,LineString
from src.stage_abi.store import canonical
from src.stage_abi.scene import composed
from src.clearance_policy import HARD_GAP_MM,CONSTRUCTION_GAP_MM
from src.gerber_u05 import gerber_source_profile as profile
from src.gerber_u05 import pipeline

HEADER='*\n%FSTAX35Y35*%\n%MOMM*%\n%ADD10C,0.200000*%\n%ADD11R,0.100000X0.100000*%\n%ADD12C,0.050000*%\n%IPPOS*%\n%LNfixture*%\n%LPD*%\nG75*\n'
def fixture(body):return(HEADER+body+'M02*\n').encode()
def source_circle():return fixture('D10*\nX00000000Y00000000D03*\nD12*\nX00000000Y00000000D02*\nX-00050000Y00000000D01*\n')

@pytest.mark.parametrize('value,expected',[('',0),('-',0),('+',0),('1',10000000),('-0002',-20000),('0118071',1180710),('01180710',1180710)])
def test_trailing_integer_decoder(value,expected):assert profile.decode_coordinate(value)==expected

def test_empty_zero_normalization_preserves_independent_coordinate_values():
    raw=fixture('D10*\nXY-D03*\n');g,p,proof=profile.parse_source(raw)
    assert len(g.objects)==1 and g.objects[0].x==g.objects[0].y==0
    assert proof['legacy_empty_zero_fields']==2
    assert raw[tuple(p.spans.values())[0][0]:tuple(p.spans.values())[0][1]]==b'XY-D03*'

@pytest.mark.parametrize('mutation',[lambda b:b.replace(b'M02*',b''),lambda b:b.replace(b'%IPPOS*%',b'%IPNEG*%'),lambda b:b.replace(b'%MOMM*%',b'%MOIN*%'),lambda b:b.replace(b'%MOMM*%',b'%MOMM*%%MOMM*%'),lambda b:b.replace(b'X00000000',b'XNaN')])
def test_unsupported_or_corrupt_source_rejects(mutation):
    with pytest.raises((ValueError,Exception)):profile.parse_source(mutation(source_circle()))

def test_source_prefix_and_occurrence_inventory_reconstructs(tmp_path):
    raw=source_circle();store=pipeline.Store(tmp_path/'runtime');b=pipeline.build_source(store,raw);scene=store.get_json(b['scene_ref'],kind='scene')
    assert b['source_objects']==len(b['source_ledger'])==2
    assert {r['kind']for r in scene['objects']}=={'circle','stroke'}
    for r in scene['objects']:
        a,z=r['metadata']['source_span'];assert r['source_id']==profile.digest(raw)+f':bytes:{a}:{z}'
        assert r['metadata']['prefix_sha256']==profile.digest(raw[:z])
    assert canonical(b)==canonical(pipeline.build_source(store,raw))

def test_clear_erases_only_earlier_copper_and_later_flash_remains(tmp_path):
    raw=fixture('D11*\nX00000000Y00000000D03*\n%LPC*%\nD10*\nX00000000Y00000000D03*\n%LPD*%\nD10*\nX00000000Y00000000D03*\n')
    store=pipeline.Store(tmp_path/'runtime');b=pipeline.build_source(store,raw);scene=store.get_json(b['scene_ref'],kind='scene');assert b['clear_operations']==1
    assert b['source_objects']==3 and len(b['source_ledger'])==3
    assert len(scene['objects'])==1 and scene['objects'][0]['metadata']['gerber_ordinal']==2
    assert composed(store,scene).area>0

def test_rectangular_stroke_calipers_are_source_dimensions_not_equivalent_round_width(tmp_path):
    raw=fixture('D11*\nX00000000Y00000000D02*\nX00100000Y00100000D01*\n');store=pipeline.Store(tmp_path/'runtime');b=pipeline.build_source(store,raw);r=store.get_json(b['scene_ref'],kind='scene')['objects'][0];md=r['metadata'];g=pipeline.geometry(store,r['geometry_ref'])
    assert md['minimum_caliper_mm']==.1 and math.isclose(md['source_port_width_mm'],math.sqrt(.02))
    assert math.isclose(g.area,.21) # exact square-aperture sweep, not a round cap

@pytest.mark.parametrize('factor',[.99,1.50001,float('nan'),float('inf')])
def test_width_scalar_cannot_escape_original_ceiling(factor):
    with pytest.raises(ValueError):pipeline.offset_part(box(0,0,1,1),.1,factor)

def test_source_offset_retains_core_nominal_envelope_and_directional_ceiling():
    core=box(0,0,1,.1);nom=pipeline.offset_part(core,.1,1.5);env=pipeline.offset_part(core,.1,1.5,True)
    assert nom.covers(core)and env.covers(nom)
    assert nom.bounds[3]-nom.bounds[1]<=.15+1e-12
    assert nom.bounds[2]-nom.bounds[0]<=1.5
    assert pipeline.offset_part(core,.1,1.)is core

def test_shared_production_defaults_are_not_replaced():
    assert HARD_GAP_MM==.040 and CONSTRUCTION_GAP_MM==.04010
    assert pipeline.CropSettings().hard_gap==.040

def test_positive_round_priority_component_ids_are_json_strings(tmp_path):
    raw=fixture('D10*\nX00000000Y00000000D03*\nX00200000Y00000000D03*\n');store=pipeline.Store(tmp_path/'runtime');b=pipeline.build_source(store,raw);scene=store.get_json(b['scene_ref'],kind='scene');r=pipeline.run_t01(store,scene,b)
    assert r['allocation']['priorities_by_physical_component']
    assert canonical(r)

def test_T01_reuses_actual_priority_companion_and_source_port_checks(tmp_path):
    store=pipeline.Store(tmp_path/'runtime');b=pipeline.build_source(store,source_circle());scene=store.get_json(b['scene_ref'],kind='scene');r=pipeline.run_t01(store,scene,b)
    assert r['full_surface_check']['passed']and len(r['decisions'])==1
    after=store.get_json(r['output_scene_ref'],kind='scene');q=pipeline.run_t03(store,after,b,r)
    assert q['summary']['moved']==0 and q['summary']['trace_occurrences']==1

def test_whole_source_rectangle_and_spindle_paths_keep_checks(tmp_path):
    raw=fixture('D11*\nX00000000Y00000000D03*\nD10*\nX00200000Y00000000D03*\nD12*\nX00200000Y00000000D02*\nX00150000Y00000000D01*\n');store=pipeline.Store(tmp_path/'runtime');b=pipeline.build_source(store,raw);scene=store.get_json(b['scene_ref'],kind='scene');r=pipeline.run_t02(store,scene)
    assert r['verification']['passed']and r['summary']['rectangles']==1
    from src.t04_settings import capture_job
    capture_job(store.root.parent)
    t04=pipeline.run_t04(store,scene);after=store.get_json(t04['output_scene_ref'],kind='scene');t02=pipeline.run_t02(store,after);final=pipeline.run_t05(store,store.get_json(t02['output_scene_ref'],kind='scene'),t04)
    assert final['verification']['passed']and final['summary']['source_attachments']>=1
