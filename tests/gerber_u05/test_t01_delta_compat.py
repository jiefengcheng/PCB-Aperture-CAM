from pathlib import Path
import hashlib
import pytest
from src.gerber_u05.t01_delta_compat import BEFORE,AFTER,known,prove


def sources():
 after=(Path(__file__).resolve().parents[2]/'src/gerber_u05/component_stages.py').read_text()
 start=after.index('def t01_land_checker(');end=after.index('def run_t01(',start)
 before=(after[:start]+after[end:]).replace(' checker=t01_land_checker(lands,fixed)\n',' checker=p.PreparedLandScene(lands,fixed)\n')
 return before,after


def test_exact_factory_delta_retains_legacy_branch_and_other_stages():
 before,after=sources()
 assert hashlib.sha256(before.encode()).hexdigest()==BEFORE
 assert hashlib.sha256(after.encode()).hexdigest()==AFTER
 assert known(BEFORE,AFTER)
 proof=prove(before,after)
 assert proof['legacy_branch_unchanged']and proof['all_other_stage_code_unchanged']
 assert proof['geometry_proposals_unchanged']


@pytest.mark.parametrize('change',['threshold','factory','source_guard'])
def test_arbitrary_upstream_change_cannot_get_reuse(change):
 before,after=sources()
 if change=='threshold':after=after.replace('p.CONSTRUCTION_GAP_MM','0.001',1)
 elif change=='factory':after=after.replace('checker._source_width_added_material','lambda *args: p.Polygon()',1)
 else:after=after.replace("if cc.ACTIVE is None:return p.legacy_run_t01(store,scene,binding)","if False:return p.legacy_run_t01(store,scene,binding)",1)
 with pytest.raises(ValueError,match='T01_POSITIVE_DELTA'):prove(before,after)
 assert not known(BEFORE,hashlib.sha256(after.encode()).hexdigest())
