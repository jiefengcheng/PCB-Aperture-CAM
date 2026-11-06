"""T05-only exact coalescing of a proved triangular serialization partition.

Internal triangle edges are removed with integer arithmetic. Every positive
face, hole and boundary is proved again by the original partition predicate.
This changes representation only; no precision or clearance allowance is used.
"""
import heapq
from collections import defaultdict
from shapely.geometry import Polygon
from shapely.geometry.polygon import orient
from shapely import to_wkb
from .contours import contours as original_contours,verify_partition,_ring_points,_edges

def require_budget(regions,attachments,limit):
 if type(limit)is not int or limit<1 or type(attachments)is not int or attachments<1:
  raise ValueError('T05_LOCAL_REGION_BUDGET_INVALID')
 if regions>attachments*limit:
  raise ValueError('T05_LOCAL_REGION_BUDGET_EXCEEDED:'+str(dict(regions=regions,attachments=attachments,limit_per_attachment=limit)))
 return dict(regions=regions,attachments=attachments,limit_per_attachment=limit,passed=True)


def _key(edge):
 a,b=edge
 return (a,b)if a<b else(b,a)


def _loop(edges):
 outgoing={};incoming=set()
 for a,b in edges:
  if a in outgoing or b in incoming:return None
  outgoing[a]=b;incoming.add(b)
 if set(outgoing)!=incoming:return None
 start=min(outgoing);point=start;points=[];visited=set()
 for _ in range(len(edges)):
  if point in visited:return None
  visited.add(point);points.append(point);point=outgoing[point]
 if point!=start:return None
 return points


def coalesce(shape,pieces,*,grid_mm):
 verify_partition(shape,pieces,grid_mm=grid_mm)
 boundaries={i:set(_edges(_ring_points(orient(g,sign=1.).exterior,grid_mm)))for i,g in enumerate(pieces)}
 edge_groups=defaultdict(set);queue=[];versions={i:0 for i in boundaries};queued=set()
 for i,edges in boundaries.items():
  for edge in edges:edge_groups[_key(edge)].add(i)
 def schedule(a,b):
  a,b=sorted((a,b))
  if a==b or a not in boundaries or b not in boundaries:return
  item=(a,b,versions[a],versions[b])
  if item not in queued:heapq.heappush(queue,item);queued.add(item)
 for ids in edge_groups.values():
  if len(ids)==2:schedule(*ids)
 attempts=merges=0
 while queue:
  a,b,va,vb=heapq.heappop(queue)
  if a not in boundaries or b not in boundaries or versions[a]!=va or versions[b]!=vb:continue
  left,right=boundaries[a],boundaries[b];shared={e for e in left if(e[1],e[0])in right}
  if not shared:continue
  attempts+=1
  merged=(left-shared)|(right-{(b,a)for a,b in shared})
  points=_loop(merged)
  if points is None:continue
  # Mesh edges cannot cross; require one valid hole-free positive surface too.
  polygon=Polygon([(x*grid_mm,y*grid_mm)for x,y in points])
  if not polygon.is_valid or polygon.is_empty or polygon.area<=0:continue
  for i,edges in [(a,left),(b,right)]:
   for edge in edges:
    ids=edge_groups[_key(edge)];ids.discard(i)
    if not ids:del edge_groups[_key(edge)]
  del boundaries[b];del versions[b];boundaries[a]=merged;versions[a]+=1;merges+=1
  for edge in merged:edge_groups[_key(edge)].add(a)
  neighbours={i for edge in merged for i in edge_groups[_key(edge)]if i!=a}
  for other in sorted(neighbours):schedule(a,other)
 result=[]
 for edges in boundaries.values():
  points=_loop(edges)
  if points is None:raise ValueError('COMPACT_PARTITION_BOUNDARY_NOT_SIMPLE')
  result.append(Polygon([(x*grid_mm,y*grid_mm)for x,y in points]))
 result.sort(key=to_wkb);proof=verify_partition(shape,result,grid_mm=grid_mm)
 return result,dict(proof,status='EXACT_COALESCED_INTEGER_PARTITION',input_triangles=len(pieces),regions=len(result),merges=merges,merge_attempts=attempts)


def contours(shape,bridge,*,grid_mm):
 serialized,proof=original_contours(shape,bridge,grid_mm=grid_mm)
 if proof['status']!='EXACT_INTEGER_GRID_PARTITION':return serialized,proof
 pieces,compact=coalesce(shape,[g for g,_ in serialized],grid_mm=grid_mm)
 from src.gerber_image import contour
 from .native_material import equality
 result=[]
 for piece in pieces:
  points=list(orient(piece,sign=1.).exterior.coords)[:-1]
  equality(piece,contour(points+[points[0]]),grid_mm=grid_mm)
  result.append((piece,points))
 compact['original_cut_in_rejection']=proof['original_cut_in_rejection']
 return result,compact
