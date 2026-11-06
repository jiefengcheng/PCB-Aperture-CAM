import hashlib,json
from pathlib import Path
import pytest
from shapely import from_wkb,union_all
from shapely.geometry import Polygon,box
from src.gerber_u05 import pipeline as p,legacy_export
from src.gerber_u05.reference_recipe import append_reference_region
from src.native_grid_reference import fidelity

FIXTURE=Path(__file__).parent/'fixtures/reference_minimum_grid_hole'

def integer_surface(shape):
 def ring(coords):return [(round(x*1e6),round(y*1e6))for x,y in coords]
 return Polygon(ring(shape.exterior.coords),[ring(h.coords)for h in shape.interiors])

def encode(shape,tmp_path):
 store=p.Store(tmp_path/'runtime');records=[];blocks=[]
 refs=append_reference_region(shape,'inclusive_remedy','test',records,blocks,store)
 body=('%FSLAX46Y46*%\n%MOMM*%\n%ADD10C,0.1*%\n'+''.join(blocks)+'M02*\n').encode()
 parsed=legacy_export.parse(body);shapes=[]
 assert len(parsed.objects)==len(records)
 for obj,row in zip(parsed.objects,records):
  assert obj.polarity_dark
  actual=p.affine_scale(p.source_profile.object_geometry(obj)[0],1,-1,origin=(0,0))
  fidelity(p.geometry(store,row['geometry_ref']),actual)
  shapes.append(actual)
 return refs,records,shapes

def test_retained_minimum_grid_hole_is_encoded_without_filling_it(tmp_path):
 body=(FIXTURE/'region.wkb').read_bytes();manifest=json.loads((FIXTURE/'MANIFEST.json').read_bytes())
 assert hashlib.sha256(body).hexdigest()==manifest['sha256']
 shape=from_wkb(body);refs,records,actual=encode(shape,tmp_path)
 expected=integer_surface(shape);reopened=union_all([integer_surface(g)for g in actual])
 assert len(refs)==1 and len(shape.interiors)==1 and len(records)>1
 assert reopened.equals(expected) and len(reopened.interiors)==1
 assert Polygon(reopened.interiors[0]).area==pytest.approx(.5)
 assert all(r['component_reference_proof']['serialization_partition']['status']=='EXACT_INTEGER_GRID_PARTITION'for r in records)

def test_simple_reference_keeps_one_region(tmp_path):
 shape=box(1.,2.,3.,4.);refs,records,actual=encode(shape,tmp_path)
 assert len(refs)==len(records)==len(actual)==1
 assert actual[0].equals(shape)

def test_reference_keeps_resolvable_source_hole(tmp_path):
 shape=Polygon([(0,0),(3,0),(3,3),(0,3)],holes=[[(1,1),(1,2),(2,2),(2,1)]])
 refs,records,actual=encode(shape,tmp_path)
 assert union_all([integer_surface(g)for g in actual]).equals(integer_surface(shape))
 assert len(refs)==1 and records
