"""Production 40 um defaults, actual copper rejection and policy custody."""
import json
from pathlib import Path
from unittest.mock import patch
import pytest
from shapely.geometry import box,LineString
from src import clearance_policy as policy
from src.crop_stage_growth import GrowthContract,check_proposal
from src.trace_width_clearance import TraceWidthContract,verify_width_scene
from src.junction_spindle_stage import CONTRACT
from src.junction_spindle_blend import check_spindle

def test_all_production_stages_share_040_defaults():
    from src.crop_balanced_t01 import CropSettings
    from src.stage_abi.routes import route_parameters
    from src.stage_abi.lands import land_parameters
    from src.t01_canonical import specification
    from src.t01_board.policy import compile_policy,english
    assert GrowthContract().hard_gap_mm==TraceWidthContract().hard_gap_mm==CONTRACT.hard_gap_mm==.040
    assert GrowthContract().construction_gap_mm==TraceWidthContract().construction_gap_mm==CONTRACT.construction_gap_mm==.04010
    assert CropSettings().hard_gap==route_parameters()['hard_gap_mm']==.040
    assert land_parameters('t02')['surface_contract']['hard_gap_mm']==.040
    assert specification()['settings']['hard_gap']==.040
    p=compile_policy(english(),dict(artifact_id='t01-binding:'+'a'*64,sha256='a'*64))
    assert p['settings']['hard_gap']==.040 and p['family']=='t01-priority-companion/4'
    root=Path(__file__).resolve().parents[1]
    for name in ['u02','u03','u04']:
        assert json.loads((root/f'contracts/operator/{name}_board.json').read_bytes())['policy']['hard_gap_mm']==.040
    assert CONTRACT.barrier_gap_mm==.04011

@pytest.mark.parametrize('gap,passed',[(.030,False),(.040,False),(.04011,True)])
def test_land_growth_obeys_full_04010_construction_clearance(gap,passed):
    core=box(0,0,1,1);candidate=box(0,0,1.1,1);foreign=box(1.1+gap,0,2,1)
    q=check_proposal(core,candidate,[dict(source_id='foreign',original=foreign,geometry=foreign)])
    assert q['passed'] is passed

@pytest.mark.parametrize('gap,passed',[(.030,False),(.04011,True)])
def test_trace_growth_obeys_04010_clearance(gap,passed):
    line=LineString([(0,0),(2,0)]);old=line.buffer(.05,quad_segs=128);new=line.buffer(.075,quad_segs=128)
    foreign=box(.5,.075+gap,1.5,1)
    q=verify_width_scene([dict(id='trace',original=old,candidate=new,verified_original_width_mm=.1)],[dict(id='foreign',geometry=foreign)])
    assert q['passed'] is passed

def test_spindle_default_rejects_030_even_without_explicit_gap():
    owner=box(0,0,1,1);addition=box(1,0,1.1,1)
    assert not check_spindle(owner,owner.union(addition),addition,box(-1,-1,3,3),[('foreign',box(1.13,0,2,1))])['passed']

def test_legacy_t01_search_does_not_miss_foreign_copper_between_031_and_040():
    from src.crop_balanced_t01 import WorkingScene,CropSettings
    from shapely.geometry import Point
    core=Point(0,0).buffer(.1,quad_segs=128);foreign=box(.185,-.02,.2,.02)
    site=dict(source_id='circle',aliases=['circle'],center=(0,0),radius=.1,core=core,indexes=[0])
    rows=[dict(id='circle',kind='gr_circle'),dict(id='foreign',kind='gr_poly')]
    scene=WorkingScene(b'',rows,[core,foreign],[site],CropSettings())
    assert 'foreign' in {r['source_id'] for r in scene.obstacles(site,0)}

def test_contract_mutation_and_noop_negative_control_fail_closed(tmp_path):
    p=tmp_path/'policy.json';p.write_bytes(policy.PATH.read_bytes().replace(b'0.04,',b'0.02,'))
    with patch.object(policy,'PATH',p),pytest.raises(ValueError,match='PRODUCTION_CLEARANCE_CONTRACT_CHANGED'):
        policy.specification()
    from src.t01_board.policy import english
    original=english().encode();changed=policy.weakened_english(original)
    assert changed!=original and b'hard gap 0.001 mm' in changed
    with pytest.raises(ValueError,match='NEGATIVE_ENGLISH_CONTROL_NOT_MUTATED'):
        policy.weakened_english(b'hard gap 0.020 mm')

def test_historical_020_contract_is_preserved_and_not_current():
    import hashlib
    from src.t01_canonical import specification
    revision=specification()['clearance_revision'];raw=Path(revision['prior_contract_path']).read_bytes()
    assert hashlib.sha256(raw).hexdigest()==revision['supersedes_sha256']
    assert json.loads(raw)['settings']['hard_gap']==.020
    assert specification()['settings']['hard_gap']==.040
