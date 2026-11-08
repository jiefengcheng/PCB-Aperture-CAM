"""Local Euler checks detect a route closing a new empty pocket.

Original empty descendants are checked locally on every proposal. Euler counts
alone cannot detect a source hole disappearing while a new pocket is formed.
Other topology events assemble one source owner, never the board.
"""
import math
from src.hole_acceptance import required as holes_required
from shapely import STRtree,to_wkb
from shapely.ops import unary_union
from src.component_clearance import surfaces
from src.component_hole_lineage import classify,identity,hole_polygons
from src.pcb_data_abi.geometry import POLYGON_TOLERANCE_MM


def characteristic(g):
 return sum(1-len(p.interiors)for p in surfaces(g))


class SourceVoids:
 """Prepared source-hole operands, charged to the existing dependency budget."""
 def __init__(self,dependencies,limit):
  self.d=dependencies;self.records=[];self.bytes=0
  for own in (sorted(set(dependencies.owners.values())) if holes_required() else []):
   for hole in sorted(hole_polygons(dependencies.context.cores[own]),key=identity):
    opening=hole.difference(dependencies.before[own])
    if not opening.is_valid or not math.isfinite(opening.area)or opening.area<=0:
     raise ValueError('T04_SOURCE_VOID_MISSING_AT_STAGE_ENTRY:'+identity(hole))
    self.bytes+=len(to_wkb(hole))+len(to_wkb(opening))+640
    if self.bytes>limit:raise ValueError('T04_SOURCE_VOID_INDEX_MEMORY_BUDGET_EXCEEDED')
    self.records.append(dict(owner=own,hole=hole,opening=opening,source_hole_sha256=identity(hole)))
  self.tree=STRtree([r['hole']for r in self.records])

 def remaining(self,row,current,versions,*,sid=None,candidate=None):
  d=self.d;opening=row['opening']
  if candidate is not None:opening=opening.difference(candidate)
  for i in sorted(map(int,d.route_tree.query(row['hole'].envelope))):
   other=d.route_ids[i]
   if other==sid or d.owners[other]!=row['owner']or versions[other]==1:continue
   opening=opening.difference(current[other])
   if opening.is_empty:break
  return opening

 def result(self,indices,current,versions,*,sid=None,candidate=None):
  failures=[];checked=0
  for i in indices:
   row=self.records[i]
   if sid is not None and row['owner']!=self.d.owners[sid]:continue
   if candidate is not None and not candidate.intersects(row['opening']):continue
   remaining=self.remaining(row,current,versions,sid=sid,candidate=candidate);checked+=1
   if not remaining.is_valid or not math.isfinite(remaining.area)or remaining.area<=0:
    failures.append(dict(trace_id=sid,owner=row['owner'],reason='ORIGINAL_SOURCE_ROUTE_VOID_REMOVED',source_hole_sha256=row['source_hole_sha256']))
  return dict(passed=not failures,failures=failures,source_holes=len(self.records),checked_holes=checked,
              basis='Positive empty descendant of every original source hole; no areal epsilon erases a source feature')

 def check(self,sid,candidate,current,versions):
  return self.result(sorted(map(int,self.tree.query(candidate.envelope))),current,versions,sid=sid,candidate=candidate)

 def complete(self,current,versions):
  return self.result(range(len(self.records)),current,versions)


def check(dependencies,sid,factor,candidate,current,versions):
 if not holes_required():
  return dict(passed=True,failures=[],ordinary_holes='ACCEPT_WITHOUT_SOURCE_ANCESTRY',
              scope='Ordinary-hole topology only; clearance, pin/channel separation, source cores and width checks remain external mandatory predicates')
 d=dependencies;own=d.owners[sid]
 relevant=[s for i in sorted(map(int,d.route_tree.query(candidate.envelope)))
           if(s:=d.route_ids[i])!=sid and d.owners[s]==own and versions[s]!=1]
 # A rare complete-owner event can depend on a remote accepted route too:
 # bind every same-owner version rather than just the local intersection list.
 key=('topology',sid,factor,*[v for s in d.route_ids if d.owners[s]==own for v in(s,versions[s])])
 def calculate():
  voids=d.source_voids.check(sid,candidate,current,versions)
  if not voids['passed']:return dict(voids,topology_event=True)
  pieces=[d.before[own].intersection(candidate),current[sid].intersection(candidate)]
  pieces.extend(current[s].intersection(candidate)for s in relevant)
  intersection=unary_union(pieces)
  if characteristic(intersection)==characteristic(candidate):
   return dict(passed=True,failures=[],topology_event=False,source_voids=voids)
  # Euler changed: identify actual new empty holes or lost original cutouts.
  # Most attempts never need this owner assembly. It is memoized against all
  # intersecting accepted route versions, including rejected repeat attempts.
  existing=[d.before[own],*[current[s]for s in d.route_ids if d.owners[s]==own and versions[s]!=1]]
  before=unary_union(existing);after=before.union(candidate)
  lineage=classify(before,after);keepers=set(lineage['keeper_ids']);failures=[]
  for h in hole_polygons(after):
   if identity(h)in keepers or h.buffer(-POLYGON_TOLERANCE_MM).is_empty:continue
   # An enclosing channel may surround a foreign source conductor. Such a
   # clearance cavity is retained by the existing final inventory as well.
   foreign=[d.ids[i]for i in sorted(map(int,d.tree.query(h)))
            if d.ids[i]!=own and h.intersection(d.foreign[d.ids[i]]).area>0]
   if foreign:continue
   failures.append(dict(trace_id=sid,reason='NEW_RESOLVABLE_EMPTY_ROUTE_POCKET',
                        area_mm2=h.area,bounds_mm=list(h.bounds)))
  source=classify(d.context.cores[own],after)
  if any(not row['source_hole_survives']for row in source['source_holes']):
   failures.append(dict(trace_id=sid,reason='ORIGINAL_SOURCE_ROUTE_VOID_REMOVED'))
  return dict(passed=not failures,failures=failures,topology_event=True,source_voids=voids,
              scope='Changed source owner only; original void and final native checks unchanged')
 return d.memo(key,calculate)
