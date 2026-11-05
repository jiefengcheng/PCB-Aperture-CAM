"""Bounded exact axial cut-ins; unsuccessful cases retain the exact partition."""
import heapq
from shapely.geometry import LineString
from shapely.geometry.polygon import orient
from shapely.prepared import prep
from .native_material import equality
MAX_PAIRS=8_000_000
CANDIDATES_PER_HOLE=64

def bridge(shape,*,grid_mm):
 from src.gerber_image import contour
 from src.validator import Unsupported
 source=orient(shape,sign=1.);shell=[(round(x/grid_mm),round(y/grid_mm))for x,y in source.exterior.coords[:-1]];holes=[[(round(x/grid_mm),round(y/grid_mm))for x,y in h.coords[:-1]]for h in source.interiors]
 if len(shell)*sum(len(h)for h in holes)>MAX_PAIRS:raise ValueError('EXACT_AXIAL_SEARCH_RESOURCE_BOUND')
 prepared=prep(source);failure=None
 for vertical in(False,True):
  outline=list(shell);tags=[True]*len(outline)
  try:
   for hole in holes:
    heap=[]
    for hi,h in enumerate(hole):
     for ei,a in enumerate(shell):
      b=shell[(ei+1)%len(shell)];dx,dy=b[0]-a[0],b[1]-a[1]
      denominator=dx if vertical else dy;along=h[0]-a[0]if vertical else h[1]-a[1]
      if not denominator or not min(0,denominator)<=along<=max(0,denominator):continue
      numerator=along*(dy if vertical else dx)
      if numerator%denominator:continue
      point=(h[0],a[1]+numerator//denominator)if vertical else(a[0]+numerator//denominator,h[1])
      length=(point[0]-h[0])**2+(point[1]-h[1])**2
      if not length:continue
      entry=(-length,-hi,-point[0],-point[1],-ei)
      if len(heap)<CANDIDATES_PER_HOLE:heapq.heappush(heap,entry)
      elif entry>heap[0]:heapq.heapreplace(heap,entry)
    inserted=False
    for negative in sorted(heap,reverse=True):
     _,hi,px,py,ei=(-v for v in negative);point=(px,py);h=hole[hi]
     line=LineString([(point[0]*grid_mm,point[1]*grid_mm),(h[0]*grid_mm,h[1]*grid_mm)])
     if not prepared.covers(line):continue
     for i,a in enumerate(outline):
      if not tags[i]:continue
      b=outline[(i+1)%len(outline)];dx,dy=b[0]-a[0],b[1]-a[1];cross=dx*(py-a[1])-dy*(px-a[0]);dot=(px-a[0])*(px-b[0])+(py-a[1])*(py-b[1])
      if cross or dot>0:continue
      if point==a:at=i
      elif point==b:
       matches=[j for j,v in enumerate(outline)if v==point and tags[j]]
       if not matches:continue
       at=matches[0]
      else:
       outline.insert(i+1,point);tags.insert(i+1,True);at=i+1
      loop=hole[hi:]+hole[:hi]+[h,point];outline[at+1:at+1]=loop;tags[at:at+1]=[False]*len(loop)+[True];inserted=True;break
     if inserted:break
    if not inserted:raise ValueError('EXACT_AXIAL_HOLE_BRIDGE_NOT_FOUND')
   points=[(x*grid_mm,y*grid_mm)for x,y in outline];native=[(round(x/grid_mm)*grid_mm,round(y/grid_mm)*grid_mm)for x,y in points];restored=contour(native+[native[0]]);proof=equality(shape,restored,grid_mm=grid_mm)
   return points,dict(proof,encoding='EXACT_AXIAL_CUT_IN',axis='VERTICAL'if vertical else'HORIZONTAL',candidate_limit_per_hole=CANDIDATES_PER_HOLE,max_source_pairs=MAX_PAIRS)
  except(ValueError,Unsupported)as error:
   # Only the other fixed axis is tried; unexpected runtime errors propagate.
   failure=error
 raise ValueError('EXACT_AXIAL_CUT_IN_NOT_ESTABLISHED:'+str(failure))
