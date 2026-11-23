"""Study prototype: clearance belongs to frozen original copper components.

This does not authorize filling inherited voids, widening beyond stage caps, or
merging separate originals. It is not wired into the app or operator route.
"""
import hashlib,math
from shapely import STRtree,get_precision,normalize,prepare,to_wkb
from shapely.ops import unary_union

def sha(g):return hashlib.sha256(to_wkb(normalize(g))).hexdigest()
def polygons(g):
 if g.is_empty or not g.is_valid or g.geom_type not in('Polygon','MultiPolygon'):raise ValueError('VALID_FILLED_SOURCE_REQUIRED')
 return [g]if g.geom_type=='Polygon'else list(g.geoms)

class OriginalOwners:
 @classmethod
 def from_prepared(cls,source,owners,ids):
  """Restore the same ownership structure from authenticated preparation."""
  if len(owners)!=len(ids) or [sha(g)for g in owners]!=list(ids):
   raise ValueError('PREPARED_ORIGINAL_OWNER_BINDING_CHANGED')
  result=cls.__new__(cls);result.source=source;result.source_sha256=sha(source)
  result.owners=list(owners);result.ids=list(ids);result.tree=STRtree(result.owners)
  prepare(result.owners)
  result._floating_valid_owners={id(g):g for g in result.owners if get_precision(g)==0 and g.is_valid}
  result.fingerprint=hashlib.sha256((result.source_sha256+'\n'+'\n'.join(result.ids)).encode()).hexdigest()
  return result

 def __init__(self,source):
  # Partition source polygon faces by connected components. Stable geometry
  # hashes fix face traversal, owner ordering and public owner identities.
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
  prepare(self.owners)
  self._floating_valid_owners = {id(g):g for g in self.owners if get_precision(g)==0 and g.is_valid}
  self.source_sha256=sha(source);self.source=source;self.fingerprint=hashlib.sha256((self.source_sha256+'\n'+'\n'.join(self.ids)).encode()).hexdigest()
 def memberships(self,originals,*,reuse=None):
  """Reuse a source batch only for byte-identical predicate operands.

  Keep immutable witnesses, not references to the caller's mutable result map.
  Different partitions (including analytically removed frames), ordering or
  precision miss the cache. Each new process computes its first batch afresh.
  """
  def witness(g):return (float(get_precision(g)),to_wkb(g,include_srid=True))
  # An equal input occurrence is insufficient when the analytic partition
  # removes a frame or otherwise changes owners. Bind the ordered partition
  # first, then match each occurrence independently.
  partition=(witness(self.source),tuple((sid,witness(g))for sid,g in zip(self.ids,self.owners)))
  previous=getattr(reuse,'_source_memberships',None)
  cached=dict(previous[1])if previous is not None and previous[0]==partition else {}
  result={};records=[]
  for sid,g in originals.items():
   key=witness(g);known=cached.get(sid)
   owners=known[1]if known is not None and known[0]==key else tuple(self.membership(g))
   result[sid]=list(owners);records.append((sid,(key,owners)))
  self._source_memberships=(partition,tuple(records))
  return result
 def membership(self,original_contribution):
  # Every positive source surface is retained, including sub-epsilon triangles.
  candidates=sorted(map(int,self.tree.query(original_contribution)))
  if not candidates:return []
  filled=(original_contribution.geom_type in ('Polygon','MultiPolygon')
          and get_precision(original_contribution)==0 and original_contribution.area>0
          and original_contribution.is_valid)
  owners=[]
  for i in candidates:
   owner=self.owners[i]
   # Full coverage proves a positive overlap. Partial contacts and fixed-grid
   # geometry continue through the original positive-area predicate.
   covered=filled and get_precision(owner)==0 and owner.covers(original_contribution)
   # Reuse the prepared polygon to discard disjoint bounding-box hits.
   # Fixed-grid and unsupported operands keep the original overlay semantics.
   if not covered and filled and self._floating_valid_owners.get(id(owner)) is owner and not owner.intersects(original_contribution):
    continue
   if covered or owner.intersection(original_contribution).area>0:
    owners.append(self.ids[i])
  return owners
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

 def prepared_membership(self, contribution):
    """Prove conclusive overlap or disjointness before constructing a polygon."""
    matches = []
    positive_polygon = (get_precision(contribution) == 0
                        and contribution.geom_type in ('Polygon', 'MultiPolygon')
                        and contribution.is_valid and contribution.area > 0)
    point = None
    if positive_polygon:
        candidate = contribution.representative_point()
        if contribution.contains(candidate):
            point = candidate

    for index in sorted(map(int, self.tree.query(contribution))):
        owner = self.owners[index]
        if positive_polygon and get_precision(owner)==0:
            # An interior point in both valid polygons proves positive area.
            if point is not None and owner.contains(point):
                matches.append(self.ids[index])
                continue
            if not owner.intersects(contribution):
                continue
            if owner.covers(contribution):
                matches.append(self.ids[index])
                continue
        # Edge contact, ambiguous positive overlap and fixed precision still
        # use the original overlay without an area tolerance.
        if owner.intersection(contribution).area > 0:
            matches.append(self.ids[index])
    return matches
