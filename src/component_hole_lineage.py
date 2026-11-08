"""Preserve source-hole identities without exempting newly split-off pockets."""
import hashlib
from shapely import STRtree,normalize,to_wkb
from shapely.geometry import Polygon

def identity(g):return hashlib.sha256(to_wkb(normalize(g))).hexdigest()
def hole_polygons(shape):
 if shape.is_empty:return []
 if not shape.is_valid or shape.geom_type not in('Polygon','MultiPolygon'):raise ValueError('VALID_COPPER_REQUIRED_FOR_SOURCE_HOLE_LINEAGE')
 parts=[shape]if shape.geom_type=='Polygon'else sorted(shape.geoms,key=identity)
 return [Polygon(r)for p in parts for r in p.interiors]

def classify(original,current,*,epsilon=1e-12):
 if epsilon!=1e-12:raise ValueError('SOURCE_HOLE_LINEAGE_EPSILON_CHANGED')
 from src.hole_acceptance import required
 if not required():
  return dict(schema='source-hole-descendant-identities/1',keeper_ids=[],ancestry={},source_holes=[],basis='ACCEPT_WITHOUT_SOURCE_ANCESTRY')
 old=hole_polygons(original);now=hole_polygons(current);tree=STRtree(now);keepers=set();ancestry={identity(h):[]for h in now};records=[]
 for source_hole in sorted(old,key=identity):
  source_id=identity(source_hole);matches=[]
  for j in sorted(map(int,tree.query(source_hole))):
   overlap=source_hole.intersection(now[j]).area
   # Even a minimum-grid source hole remains a protected source feature.
   # The areal comparison epsilon cannot erase its ancestry.
   if overlap>0:matches.append((overlap,identity(now[j])));ancestry[identity(now[j])].append(source_id)
  matches.sort(key=lambda p:(-p[0],p[1]));keeper=matches[0][1]if matches else None
  if keeper is not None:keepers.add(keeper)
  records.append(dict(source_hole_sha256=source_id,principal_current_hole_sha256=keeper,descendant_holes=[h for _,h in matches],source_hole_survives=keeper is not None))
 return dict(schema='source-hole-descendant-identities/1',keeper_ids=sorted(keepers),ancestry=ancestry,source_holes=records,basis='One principal surviving empty descendant per source hole; additional enclosed descendants remain repair candidates. Foreign copper never receives a clearance exemption.')
