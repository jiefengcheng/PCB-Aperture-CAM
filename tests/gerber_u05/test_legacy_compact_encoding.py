import pytest
from shapely.geometry import box,Polygon
from src.gerber_u05 import pipeline as p,legacy_export as e,export_absorption as absorption
from src.native_boundary_metric import distance
from src.pcb_data_abi.geometry import POLYGON_TOLERANCE_MM

G=1e-6

def inputs():
 owner=box(0,0,1,1).difference(box(.2,.2,.3,.3))
 addition=Polygon([(1-.1*G,.4),(1+.51*G,.4007775),(1+1.49*G,.4007),(1+.51*G,.4000005)])
 return owner,addition,box(-1,-1,2,2)

def encoded(tmp_path,region,owner):
 store=p.Store(tmp_path/'runtime');rows=[];blocks=[]
 e.append_regions(region,'t05','route',rows,blocks,store,owner=owner)
 pieces=[p.geometry(store,r['geometry_ref'])for r in rows]
 return store,rows,blocks,pieces

def test_long_subgrid_fragment_still_fails_original_point_contact_guard(tmp_path):
 owner,addition,_=inputs();store,rows,blocks,pieces=encoded(tmp_path,addition,owner)
 fragments=[g for g in owner.union(p.unary_union(pieces)).geoms if g.intersection(owner).area==0]
 assert len(fragments)==1 and fragments[0].distance(owner)==0 and fragments[0].area>G*G
 with pytest.raises(ValueError,match='EXPORT_JUNCTION_COMPONENT_NOT_FILE_GRID_POINT_CONTACT'):
  e.preserve_point_contacts(owner,pieces,'route',rows,blocks,store)

def test_exact_addition_fallback_uses_existing_owner_without_a_new_cap(tmp_path,monkeypatch):
 owner,addition,domain=inputs()
 def unavailable(*args,**kwargs):raise ValueError('U05_NATIVE_SUPPORT_CHANGES_QUALIFIED_COPPER')
 # Model the actual case where the old overlap construction cannot satisfy
 # its Boolean predicates. Its exact-addition fallback is not itself relaxed.
 monkeypatch.setattr(absorption,'export_region',unavailable)
 region,support,mode=e.supported_region(addition,owner,domain)
 assert mode=='CHECKED_COMPLETE_LOCAL_JOINT_SURFACE'
 target=owner.union(addition);represented=owner.union(region)
 assert support.difference(owner).area<=1e-12
 assert addition.difference(region).area<=1e-12
 assert region.difference(domain).area<=1e-12
 assert target.symmetric_difference(represented).area<=1e-12
 store,rows,blocks,pieces=encoded(tmp_path,region,owner)
 assert e.preserve_point_contacts(owner,pieces,'route',rows,blocks,store)==[]
 body=b'%FSLAX46Y46*%\n%MOMM*%\n%ADD10C,0.100000*%\n'+''.join(blocks).encode()+b'M02*\n'
 native=e.parse(body)
 actual=owner.union(p.unary_union([p.affine_scale(p.source_profile.object_geometry(o)[0],1,-1,origin=(0,0))for o in native.objects]))
 assert actual.is_valid and actual.geom_type=='Polygon'
 assert distance(target,actual)<=POLYGON_TOLERANCE_MM
 assert len(actual.interiors)==len(owner.interiors)==1
 assert not actual.intersects(box(.21,.21,.29,.29))

def test_owner_support_does_not_attach_a_foreign_disconnected_island(tmp_path):
 owner,_,domain=inputs();foreign=box(1.1,.4,1.101,.401)
 region,_,_=e.supported_region(foreign,owner,domain)
 store,rows,blocks,pieces=encoded(tmp_path,region,owner)
 with pytest.raises(ValueError,match='EXPORT_JUNCTION_COMPONENT_NOT_FILE_GRID_POINT_CONTACT'):
  e.preserve_point_contacts(owner,pieces,'route',rows,blocks,store)

def test_complete_addition_outside_the_domain_remains_rejected():
 owner,addition,domain=inputs();forbidden=box(1+.5*G,.399,1+2*G,.401)
 with pytest.raises(ValueError,match='U05_NATIVE_SUPPORT_CHANGES_QUALIFIED_COPPER'):
  e.supported_region(addition,owner,domain.difference(forbidden))
