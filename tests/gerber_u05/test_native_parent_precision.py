from tests.gerber_u05.producer_fixture import historical_source
import pytest
from shapely import get_precision,set_precision,to_wkb,union_all
from shapely.geometry import Point,box
from src import pin_separation as pin
from src.gerber_u05.channel_finish import canonical_parent
from src.component_voids import components,RemedyContract

G=1e-6

def scene():
 core=Point(.12345613,.12345613).buffer(.5,quad_segs=8)
 core=core.difference(Point(.12345613,.12345613).buffer(.05,quad_segs=8))
 bounds=[(.294057,-.02878,.544057,.22122),(-.025099,.390888,.224901,.640888),(.068934,-.350065,.318934,-.100065)]
 return core,[set_precision(box(*b),G)for b in bounds]

def test_mixed_native_precision_does_not_snap_the_analytic_source(monkeypatch):
 monkeypatch.setattr(pin,'ACTIVE',None)
 core,parents=scene();bad=union_all([core,*parents])
 assert core.difference(bad).area>RemedyContract().area_epsilon_mm2
 with pytest.raises(ValueError,match='PREDECESSOR_SOURCE_COPPER_REMOVED'):components(core,bad,RemedyContract())
 plain=[canonical_parent(g,grid_mm=G)for g in parents]
 assert all(to_wkb(a)==to_wkb(b)for a,b in zip(parents,plain))
 assert all(get_precision(g)==0 for g in plain)
 current=union_all([core,*plain]);assert core.difference(current).is_empty
 assert len(current.interiors)==1
 assert not current.intersects(Point(.12345613,.12345613).buffer(.04))
 assert components(core,current,RemedyContract())[2]==[0]

def test_resetting_metadata_cannot_restore_actually_removed_source(monkeypatch):
 monkeypatch.setattr(pin,'ACTIVE',None)
 core,_=scene();removed=core.difference(box(.3,.3,.7,.7))
 unchanged=canonical_parent(removed,grid_mm=G)
 assert to_wkb(unchanged)==to_wkb(removed)
 with pytest.raises(ValueError,match='PREDECESSOR_SOURCE_COPPER_REMOVED'):components(core,unchanged,RemedyContract())

def test_existing_pin_parent_canonicalization_is_preserved(monkeypatch):
 monkeypatch.setattr(pin,'ACTIVE',object())
 parent=set_precision(box(.1,.2,.3,.4),G)
 expected=pin.native_parent(parent,grid_mm=G)
 result=canonical_parent(parent,grid_mm=G)
 assert to_wkb(result)==to_wkb(expected)and get_precision(result)==0
 from src.gerber_u05.native_material import equality
 assert equality(parent,result,grid_mm=G)['status']=='EXACT_NATIVE_INTEGER_MATERIAL'

def test_non_coordinate_preserving_kernel_result_is_rejected(monkeypatch):
 import src.gerber_u05.channel_finish as finish
 monkeypatch.setattr(pin,'ACTIVE',None)
 parent=set_precision(box(0,0,1,1),G)
 monkeypatch.setattr(finish,'set_precision',lambda *args:box(0,0,2,2))
 with pytest.raises(ValueError,match='PRECISION_RESET_CHANGED_COORDINATES'):canonical_parent(parent,grid_mm=G)

def test_precision_correction_cannot_retain_connected_t04_or_extra_edits(tmp_path,monkeypatch):
 from pathlib import Path
 from src.gerber_u05 import prefix
 relative='src/gerber_u05/channel_finish.py'
 old=tmp_path/'old';new=tmp_path/'new';source=old/relative;target=new/relative
 source.parent.mkdir(parents=True);target.parent.mkdir(parents=True)
 source.write_text('old hash-bound producer fixture');target.write_bytes(historical_source(relative))
 before,after=prefix.CONNECTED_PREPARATION[relative];real_sha=prefix.sha;assert real_sha(target)==after
 monkeypatch.setattr(prefix,'sha',lambda f:before if Path(f)==source else real_sha(f))
 binding={'files':{str(source):before}}
 assert prefix.verify_code(binding,new,old,stages=('t01','t03'))
 with pytest.raises(ValueError,match='UPSTREAM_DEPENDENCY_CHANGED'):prefix.verify_code(binding,new,old)
 target.write_bytes(target.read_bytes()+b'\nGRID_MM=0.001\n')
 with pytest.raises(ValueError,match='UPSTREAM_DEPENDENCY_CHANGED'):prefix.verify_code(binding,new,old,stages=('t01','t03'))

def test_retained_reference_exception_cannot_change_its_parser_or_metrics():
 from src.gerber_u05.prefix import legacy_export_encoding_same
 old='from .export_absorption import supported_region\ndef parse():return 1\n'
 new=old.replace('import supported_region','import compact_supported_region as supported_region')
 assert legacy_export_encoding_same(old,new)['status']=='EXACT_CONSTRUCTION_AND_NATIVE_MODEL_SUPPORT_IMPORT_ONLY'
 with pytest.raises(ValueError,match='EXPORT_ENCODING_DELTA_CHANGED'):legacy_export_encoding_same(old,new.replace('return 1','return 2'))
