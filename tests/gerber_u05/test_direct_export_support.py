"""Retained failure: exact addition needs no redundant owner intersection."""
import hashlib
import json
from pathlib import Path
import pytest
from shapely import from_wkb
from shapely.geometry import box
from src.gerber_u05 import pipeline as p,exporter as e
from src.gerber_u05.export_absorption import supported_region
from src.u05_board.export import export_region
from src.junction_spindle_stage import CONTRACT
from test_gerber_source import source_circle


def fixture():
 folder=Path(__file__).with_name('fixtures')/'direct_export_support'
 manifest=json.loads((folder/'MANIFEST.json').read_bytes());values={}
 for name,sha in manifest['files'].items():
  body=(folder/(name+'.wkb')).read_bytes()
  assert hashlib.sha256(body).hexdigest()==sha
  values[name]=from_wkb(body)
 return values


def test_retained_double_overlap_failure_keeps_all_original_predicates(tmp_path):
 g=fixture()
 for alternate in(False,True):
  with pytest.raises(ValueError,match='SUPPORT_CHANGES_QUALIFIED_COPPER'):
   export_region(g['addition'],g['owner'],g['window'],support_from_owner=alternate)
 region,support,mode=supported_region(g['addition'],g['owner'],g['window'])
 assert mode=='EXACT_ADDITION_WITHOUT_REDUNDANT_SUPPORT'
 assert p.to_wkb(region)==p.to_wkb(g['addition'])
 assert support.is_empty
 assert support.difference(g['owner']).area<=CONTRACT.area_epsilon_mm2
 assert g['addition'].difference(region).area<=CONTRACT.area_epsilon_mm2
 assert g['owner'].union(region).symmetric_difference(g['target']).area==0
 assert region.difference(g['window']).area<=CONTRACT.area_epsilon_mm2
 store=p.Store(tmp_path/'store');records=[];blocks=[]
 e.append_regions(region,'t05','retained-double-overlap-failure',records,blocks,store)
 base,_=e.canonical_base(source_circle());plot=e.parse((base+''.join(blocks)+'M02*\n').encode())
 actual=p.unary_union([p.affine_scale(p.source_profile.object_geometry(o)[0],1,-1,origin=(0,0))for o in plot.objects[-len(records):]])
 reference=p.unary_union([p.geometry(store,row['reference_ref'])for row in records])
 assert e.fidelity(reference,actual)['passed']


def test_direct_fallback_does_not_allow_out_of_scope_copper():
 g=fixture()
 with pytest.raises(ValueError,match='SUPPORT_CHANGES_QUALIFIED_COPPER'):
  supported_region(g['addition'],g['owner'],box(0,0,1,1))
