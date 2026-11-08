import pytest
from shapely.geometry import Polygon,box
from src.gerber_u05 import pipeline as p,legacy_export as e
from src.pcb_data_abi.geometry import POLYGON_TOLERANCE_MM

G=1e-6

def raw_patch():
 return Polygon([(1-.1*G,.4),(1+.51*G,.4007775),(1+1.49*G,.4007),(1+.51*G,.4000005)])

def encode(tmp_path,patch):
 store=p.Store(tmp_path/'runtime');rows=[];blocks=[];e.append_regions(patch,'t05','route',rows,blocks,store)
 return store,rows,blocks,[p.geometry(store,r['geometry_ref'])for r in rows]

def test_large_fragment_needs_a_real_connected_pregrid_surface(tmp_path):
 owner=box(0,0,1,1);raw=raw_patch();store,rows,blocks,pieces=encode(tmp_path,raw)
 assert owner.union(raw).geom_type=='Polygon'
 assert owner.union(p.unary_union(pieces)).geom_type=='MultiPolygon'
 with pytest.raises(ValueError,match='NOT_FILE_GRID_POINT_CONTACT'):
  e.preserve_point_contacts(owner,pieces,'route',rows,blocks,store)
 caps=e.preserve_point_contacts(owner,pieces,'route',rows,blocks,store,pregrid=(owner,raw))
 assert caps and all(row['encoding_support']['cap_radius_mm']==G for row in rows if 'encoding_support'in row)
 after=owner.union(p.unary_union([*pieces,*caps]))
 assert after.is_valid and after.geom_type=='Polygon'
 from src.native_boundary_metric import distance
 assert distance(owner.union(p.unary_union(pieces)),after)<=POLYGON_TOLERANCE_MM
 witness=next(row['encoding_support']['pregrid_connection']for row in rows if 'encoding_support'in row)
 assert p.geometry(store,witness['model_owner_ref']).wkb==owner.wkb
 assert p.geometry(store,witness['region_ref']).wkb==raw.wkb

def test_same_owner_label_cannot_authorize_a_disconnected_pregrid_island(tmp_path):
 owner=box(0,0,1+.2*G,1);island=box(1+G,.4,1+2*G,.401)
 store,rows,blocks,pieces=encode(tmp_path,island)
 with pytest.raises(ValueError,match='UNQUALIFIED_PREGRID_CONNECTED_SURFACE'):
  e.preserve_point_contacts(owner,pieces,'route',rows,blocks,store,pregrid=(owner,island))

def test_connected_pregrid_witness_cannot_increase_the_one_grid_gap_limit(tmp_path):
 owner=box(0,0,1,1);island=box(1+10*G,.4,1+20*G,.401)
 qualified_region=island.union(box(.99,.4001,1+11*G,.4001001))
 assert owner.union(qualified_region).geom_type=='Polygon'
 store,rows,blocks,pieces=encode(tmp_path,island)
 with pytest.raises(ValueError,match='NOT_FILE_GRID_POINT_CONTACT'):
  e.preserve_point_contacts(owner,pieces,'route',rows,blocks,store,pregrid=(owner,qualified_region))

def test_full_native_fidelity_gate_still_rejects_bad_connector_geometry(tmp_path,monkeypatch):
 owner=box(0,0,1,1);raw=raw_patch();store,rows,blocks,pieces=encode(tmp_path,raw)
 original=e.append_regions
 def wrong_cap(shape,stage,sid,records,blocks,store,**kwargs):
  return original(box(.5,.5,2,2),stage,sid,records,blocks,store,**kwargs)
 monkeypatch.setattr(e,'append_regions',wrong_cap)
 with pytest.raises(ValueError,match='POINT_CONTACT_SUPPORT_NOT_QUALIFIED'):
  e.preserve_point_contacts(owner,pieces,'route',rows,blocks,store,pregrid=(owner,raw))
