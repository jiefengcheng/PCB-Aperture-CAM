"""Local Euler checks detect a route closing a new empty pocket.

Intersections distribute over the prepared owner operands, so normal attempts
need only route-local geometry. A topology event alone triggers assembly of
that one source owner, never the board. Final native inventory stays mandatory.
"""
from shapely.ops import unary_union
from src.component_clearance import surfaces
from src.component_hole_lineage import classify,identity,hole_polygons
from src.pcb_data_abi.geometry import POLYGON_TOLERANCE_MM


def characteristic(g):
 return sum(1-len(p.interiors)for p in surfaces(g))


def check(dependencies,sid,factor,candidate,current,versions):
 d=dependencies;own=d.owners[sid]
 relevant=[s for i in sorted(map(int,d.route_tree.query(candidate.envelope)))
           if(s:=d.route_ids[i])!=sid and d.owners[s]==own and versions[s]!=1]
 # A rare complete-owner event can depend on a remote accepted route too:
 # bind every same-owner version rather than just the local intersection list.
 key=('topology',sid,factor,*[v for s in d.route_ids if d.owners[s]==own for v in(s,versions[s])])
 def calculate():
  pieces=[d.before[own].intersection(candidate),current[sid].intersection(candidate)]
  pieces.extend(current[s].intersection(candidate)for s in relevant)
  intersection=unary_union(pieces)
  if characteristic(intersection)==characteristic(candidate):
   return dict(passed=True,failures=[],topology_event=False)
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
  return dict(passed=not failures,failures=failures,topology_event=True,
              scope='Changed source owner only; original void and final native checks unchanged')
 return d.memo(key,calculate)
