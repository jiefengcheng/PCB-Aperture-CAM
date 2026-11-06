from pathlib import Path
import hashlib,json
from shapely import from_wkb,to_wkb
from shapely.geometry import box
from src.gerber_u05.component_stages import guard_legacy_floor
from src.clearance_policy import CONSTRUCTION_GAP_MM

def operands():
 root=Path(__file__).parent/'fixtures/t01_floor';manifest=json.loads((root/'MANIFEST.json').read_text());result={}
 for name,expected in manifest.items():
  raw=(root/name).read_bytes();assert hashlib.sha256(raw).hexdigest()==expected;result[name]=from_wkb(raw)
 return [result[n+'.wkb']for n in('core','candidate','foreign')]

def test_actual_inherited_floor_is_reclipped_without_relaxing_guard():
 core,floor,foreign=operands();assert floor.difference(core).distance(foreign)<CONSTRUCTION_GAP_MM
 corrected,receipt=guard_legacy_floor(core,floor,core,[foreign],False)
 assert corrected.covers(core)
 assert corrected.difference(core).distance(foreign)>=CONSTRUCTION_GAP_MM
 assert corrected.difference(floor).area<=1e-12
 assert receipt['removed_optional_area_mm2']>0
 assert corrected.area>core.area

def test_safe_floor_is_byte_identical():
 core=box(0,0,1,1);floor=box(0,0,1.1,1);foreign=box(2,0,3,1)
 corrected,receipt=guard_legacy_floor(core,floor,core,[foreign],False)
 assert to_wkb(corrected)==to_wkb(floor) and receipt is None

def test_complete_round_cannot_be_replaced_by_a_clipped_land():
 core,floor,foreign=operands();corrected,receipt=guard_legacy_floor(core,floor,core,[foreign],True)
 assert to_wkb(corrected)==to_wkb(core)
 assert receipt['corrected_new_copper_gap_mm']is None
