import hashlib,json
from pathlib import Path
import pytest
from shapely import from_wkb
from src.gerber_u05.export_absorption import supported_region
from src.u05_board.export import export_region
from src.junction_spindle_stage import CONTRACT

def test_actual_legacy_failure_uses_existing_exact_addition_path():
 root=Path(__file__).parent/'fixtures/legacy_export_support';values={}
 for row in json.loads((root/'MANIFEST.json').read_bytes())['files']:
  body=(root/row['name']).read_bytes();assert hashlib.sha256(body).hexdigest()==row['sha256'];values[row['name']]=from_wkb(body)
 addition,owner,domain=[values[name+'.wkb']for name in('addition','owner','domain')]
 with pytest.raises(ValueError,match='SUPPORT_CHANGES_QUALIFIED_COPPER'):export_region(addition,owner,domain)
 region,support,mode=supported_region(addition,owner,domain)
 assert mode=='EXACT_ADDITION_WITHOUT_REDUNDANT_SUPPORT'
 assert all(value<=CONTRACT.area_epsilon_mm2 for value in(support.difference(owner).area,addition.difference(region).area,owner.union(region).symmetric_difference(owner.union(addition)).area,region.difference(domain).area))
