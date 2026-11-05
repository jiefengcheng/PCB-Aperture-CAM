"""Study prototype: clearance belongs to frozen original copper components.

This does not authorize filling inherited voids, widening beyond stage caps, or
merging separate originals. It is not wired into the app or operator route.
"""
import hashlib,math
from shapely import STRtree,normalize,to_wkb
from shapely.ops import unary_union

def sha(g):return hashlib.sha256(to_wkb(normalize(g))).hexdigest()
def polygons(g):
 if g.is_empty or not g.is_valid or g.geom_type not in('Polygon','MultiPolygon'):raise ValueError('VALID_FILLED_SOURCE_REQUIRED')
 return [g]if g.geom_type=='Polygon'else list(g.geoms)

class OriginalOwners:
 def __init__(self,source):
  faces=sorted(polygons(source),key=sha);tree=STRtree(faces);parents=list(range(len(faces)))
  def root(i):
   while parents[i]!=i:parents[i]=parents[parents[i]];i=parents[i]
   return i
  for i,face in enumerate(faces):
   for j in map(int,tree.query(face,predicate='intersects')):
    a,b=root(i),root(j)
    if a!=b:parents[max(a,b)]=min(a,b)
  groups={}
  for i,g in enumerate(faces):groups.setdefault(root(i),[]).append(g)
  self.owners=sorted([unary_union(g)for g in groups.values()],key=sha)
  self.ids=[sha(g)for g in self.owners];self.tree=STRtree(self.owners)
  self.source_sha256=sha(source);self.source=source;self.fingerprint=hashlib.sha256((self.source_sha256+'\n'+'\n'.join(self.ids)).encode()).hexdigest()
 def membership(self,original_contribution):
  # Every positive source surface is retained, including sub-epsilon triangles.
  return [self.ids[i]for i in sorted(map(int,self.tree.query(original_contribution)))if self.owners[i].intersection(original_contribution).area>0]
 def clearance(self,after_by_owner,gap_mm=.04):
  if not math.isfinite(gap_mm)or gap_mm<=0:raise ValueError('POSITIVE_FINITE_CLEARANCE_REQUIRED')
  if set(after_by_owner)!=set(self.ids):raise ValueError('ORIGINAL_OWNER_INVENTORY_CHANGED')
  rows=[];failures=[]
  for owner,core in zip(self.ids,self.owners):
   after=after_by_owner[owner];polygons(after)
   if not after.covers(core):failures.append(dict(owner=owner,reason='ORIGINAL_COPPER_REMOVED'))
   added=after.difference(core)
   if added.is_empty:continue
   for other in self.ids:
    if other==owner:continue
    distance=added.distance(after_by_owner[other]);passed=distance+1e-12>=gap_mm
    rows.append(dict(owner=owner,foreign_original_owner=other,gap_mm=distance,passed=passed))
    if not passed:failures.append(dict(owner=owner,foreign_original_owner=other,reason='FOREIGN_ORIGINAL_COMPONENT_CLEARANCE'))
  return dict(passed=not failures,failures=failures,pairs=rows,original_ownership_sha256=self.fingerprint,scope='Clearance only; stage caps, inherited-source-void protection, actual export/reparse and acceptance checks remain separate and mandatory.')
