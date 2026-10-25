"""Experimental earlier-square envelope bound; final clearance uses actual copper."""
import math
from shapely.geometry import Polygon
from src.crop_square_neighbor_experiment import facing_square_side, inscribed_square


def square_bound_radius(round_center, round_radius, later_center, gap_mm, *,
                        orientation_degrees=-45, safety_mm=.00002):
    if not all(math.isfinite(x) for x in (*round_center,*later_center,round_radius,gap_mm,safety_mm)):
        raise ValueError('NONFINITE_BOUND_INPUT')
    if round_radius<=0 or gap_mm<0 or safety_mm<0:
        raise ValueError('INVALID_BOUND_INPUT')
    square=inscribed_square(round_center,round_radius,orientation_degrees=orientation_degrees)
    side=facing_square_side(square,round_center,later_center)
    distance=sum(side['normal'][i]*(later_center[i]-side['midpoint'][i]) for i in range(2))
    radius=distance-gap_mm-safety_mm
    if radius<=0:
        raise ValueError('NO_POSITIVE_ENVELOPE_RADIUS')
    return {'radius_mm':radius,'square':square,'side':side,
            'center_to_supporting_line_mm':distance,
            'square_owner':'earlier round A','scope':'Bounds proposed B envelope only; final B must still clear actual round A.'}


def outward_halfplane(side, offset_mm, extent_mm=2):
    nx,ny=side['normal']; tx,ty=-ny,nx
    mx,my=side['midpoint']; mx+=offset_mm*nx; my+=offset_mm*ny
    a=(mx+extent_mm*tx,my+extent_mm*ty); b=(mx-extent_mm*tx,my-extent_mm*ty)
    return Polygon([a,b,(b[0]+2*extent_mm*nx,b[1]+2*extent_mm*ny),
                    (a[0]+2*extent_mm*nx,a[1]+2*extent_mm*ny)])
