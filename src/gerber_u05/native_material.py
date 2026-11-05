"""Exact material normal form for polygons on the declared native integer grid."""
import hashlib,json,math

def integer_ring(coordinates,grid_mm,positive):
 points=[]
 for x,y in coordinates:
  point=[]
  for value in(x,y):
   integer=round(value/grid_mm)
   if not math.isfinite(value)or abs(value-integer*grid_mm)>4*math.ulp(value):raise ValueError('NATIVE_MATERIAL_REQUIRES_EXISTING_GRID')
   point.append(integer)
  point=tuple(point)
  if not points or points[-1]!=point:points.append(point)
 if points and points[0]==points[-1]:points.pop()
 if len(points)<3:raise ValueError('NATIVE_INTEGER_RING_COLLAPSED')
 kept=[]
 for i,b in enumerate(points):
  a=points[i-1];c=points[(i+1)%len(points)];cross=(b[0]-a[0])*(c[1]-b[1])-(b[1]-a[1])*(c[0]-b[0]);between=(b[0]-a[0])*(b[0]-c[0])+(b[1]-a[1])*(b[1]-c[1])<=0
  if cross or not between:kept.append(b)
 if len(kept)<3:raise ValueError('NATIVE_INTEGER_RING_COLLAPSED')
 area=sum(a[0]*b[1]-a[1]*b[0]for a,b in zip(kept,kept[1:]+kept[:1]))
 if not area:raise ValueError('NATIVE_INTEGER_RING_ZERO_AREA')
 if(area>0)!=positive:kept.reverse()
 start=min(range(len(kept)),key=lambda i:kept[i]);return tuple(kept[start:]+kept[:start])

def normal_form(shape,*,grid_mm):
 if not math.isfinite(grid_mm)or grid_mm<=0:raise ValueError('NATIVE_MATERIAL_GRID_INVALID')
 if shape.geom_type!='Polygon'or shape.is_empty or not shape.is_valid:raise ValueError('NATIVE_MATERIAL_VALID_POLYGON_REQUIRED')
 return(integer_ring(shape.exterior.coords,grid_mm,True),tuple(sorted(integer_ring(h.coords,grid_mm,False)for h in shape.interiors)))

def equality(reference,actual,*,grid_mm):
 one=normal_form(reference,grid_mm=grid_mm);two=normal_form(actual,grid_mm=grid_mm)
 if one!=two:raise ValueError('NATIVE_INTEGER_MATERIAL_CHANGED')
 digest=hashlib.sha256(json.dumps(one,separators=(',',':')).encode()).hexdigest()
 return dict(status='EXACT_NATIVE_INTEGER_MATERIAL',material_sha256=digest,grid_mm=grid_mm,holes=len(one[1]),tolerance_allowance=False,basis='Exact oriented native-grid boundaries, removing only exact collinear subdivisions; no positive face or hole omitted')
