"""Exact primitive identity plus the existing U03 stroke approximation bound."""
import math
from fractions import Fraction
from gerbonara import graphic_objects as go
from gerbonara.apertures import CircleAperture
from src.native_reference import one,children

# These are the retained U03 native-source/plot bounds, not polygon allowances.
STROKE_GEOMETRY_BOUND_MM=.000025
ENDPOINT_BOUND_MM=.000002

def primitive_match(node,obj,*,require_center=True):
    kind=str(node[0]);arc=kind in ('arc','gr_arc')
    if kind not in ('segment','gr_line','arc','gr_arc') or not isinstance(obj,go.Arc if arc else go.Line) or not obj.polarity_dark:return False
    if not isinstance(obj.aperture,CircleAperture) or obj.aperture.hole_dia not in (None,0):return False
    width=float(one(node,'width',one((children(node,'stroke') or [[]])[0],'width',[0]))[0])
    if round(width,6)!=round(obj.aperture.diameter,6):return False
    xy=lambda key:tuple(map(float,one(node,key)));a,b=xy('start'),xy('end');p,q=(obj.x1,-obj.y1),(obj.x2,-obj.y2)
    forward=max(math.dist(a,p),math.dist(b,q))<=ENDPOINT_BOUND_MM
    reverse=max(math.dist(a,q),math.dist(b,p))<=ENDPOINT_BOUND_MM
    if not forward and not reverse:return False
    if not arc:return True
    if not require_center:return True
    # Rational circumcenter in native 1 nm integer units avoids cancellation
    # from fitting a small arc at a large board coordinate.
    ax,ay,mx,my,bx,by=[int(round(v*1e6)) for point in (a,xy('mid'),b) for v in point]
    den=2*(ax*(my-by)+mx*(by-ay)+bx*(ay-my))
    if not den:return False
    cx=float(Fraction((ax*ax+ay*ay)*(my-by)+(mx*mx+my*my)*(by-ay)+(bx*bx+by*by)*(ay-my),den))/1e6
    cy=float(Fraction((ax*ax+ay*ay)*(bx-mx)+(mx*mx+my*my)*(ax-bx)+(bx*bx+by*by)*(mx-ax),den))/1e6
    if math.dist((cx,cy),(obj.x1+obj.cx,-obj.y1-obj.cy))>ENDPOINT_BOUND_MM:return False
    clockwise=((mx-ax)*(by-ay)-(my-ay)*(bx-ax))>0
    return obj.clockwise==(clockwise if forward else not clockwise)

def stroke_fidelity(reference,actual):
    distance=reference.hausdorff_distance(actual);area=reference.symmetric_difference(actual).area;bound=2*reference.length*STROKE_GEOMETRY_BOUND_MM+math.pi*STROKE_GEOMETRY_BOUND_MM**2
    if distance>STROKE_GEOMETRY_BOUND_MM or area>bound:raise ValueError('U05_NATIVE_STROKE_GEOMETRY_BINDING_FAILED')
    return dict(comparison='Source primitive identity with retained U03 nominal-stroke approximation bound',hausdorff_mm=distance,symmetric_difference_mm2=area,tolerance_mm=STROKE_GEOMETRY_BOUND_MM,area_bound_mm2=bound,endpoint_tolerance_mm=ENDPOINT_BOUND_MM)
