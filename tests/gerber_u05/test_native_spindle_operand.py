from pathlib import Path
import pytest
from shapely import from_wkb
from shapely.geometry import box
from src.gerber_u05.native_spindle_operand import operand
from src.u05_board.export import actual_spindle_check

def actual():
 d=Path(__file__).with_name('fixtures')/'native_delta'
 return {n:from_wkb((d/(n+'.wkb')).read_bytes())for n in('owner','material','addition','window')}
def test_exact_retained_readdition_failure_checks_the_actual_native_operand():
 g=actual();old=actual_spindle_check(g['owner'],[g['material']],g['addition'],g['window'],[])
 assert old['failures']==['DELTA_MISMATCH']
 region=operand([g['material']]);proof=actual_spindle_check(g['owner'],[g['material']],region,g['window'],[])
 assert proof['passed']
 assert g['material'].equals(region)and g['material'].symmetric_difference(region).area==0
 assert g['material'].difference(g['window']).area==0
 # The native source support is deliberately retained in the operand.
 assert region.intersection(g['owner']).area>0

def test_native_positive_operand_keeps_scope_and_foreign_clearance_rejections():
 g=actual();x,y,x1,y1=g['window'].bounds;bad=box(x1+.001,y,x1+.01,y+.01)
 parts=[g['material'],bad];q=actual_spindle_check(g['owner'],parts,operand(parts),g['window'],[])
 assert not q['passed']and 'OUTSIDE_WINDOW'in q['failures']
 pt=g['material'].representative_point();foreign=pt.buffer(.00001)
 q=actual_spindle_check(g['owner'],[g['material']],operand([g['material']]),g['window'],[('deliberate-foreign',foreign)])
 assert not q['passed']and 'FOREIGN_CLEARANCE:deliberate-foreign'in q['failures']
