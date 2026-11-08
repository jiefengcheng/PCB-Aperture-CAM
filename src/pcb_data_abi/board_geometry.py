"""Board-only grid normalization and legal axial cut-ins for filled polygons."""
import math
from shapely import set_precision,to_wkb,get_coordinates
from shapely.geometry import Polygon,LineString,Point
from shapely.geometry.polygon import orient
from src.stage_abi.store import digest
from src.native_boundary_metric import distance as boundary_distance
from .geometry import GRID_MM,POLYGON_TOLERANCE_MM,CIRCLE_TOLERANCE_MM
from .crop_quantization import export_reference as crop_reference


def file_grid(shape):
    # Reconstructed Gerber contours lose the GEOS precision tag. Running the
    # topology reducer again can delete an otherwise valid minimum-grid triangle.
    # Exact file-grid vertices need no rounding or topological reduction.
    coords=get_coordinates(shape)
    exact=(not shape.is_empty and shape.is_valid and
        shape.geom_type in ('Polygon','MultiPolygon') and
        all(math.isfinite(float(v)) and float(v)==round(float(v),6)
            for row in coords for v in row))
    return set_precision(shape,GRID_MM,mode='pointwise' if exact else 'valid_output')


def quantize(shape):
    if shape.geom_type not in('Polygon','MultiPolygon')or shape.is_empty or not shape.is_valid:raise ValueError('UNSUPPORTED_TARGET_POLYGON')
    q=file_grid(shape)
    if q.geom_type=='MultiPolygon'and len(q.geoms)==1:q=q.geoms[0]
    if q.geom_type!='Polygon'or q.is_empty or not q.is_valid:raise ValueError('BOARD_FILE_GRID_MULTIPART_NOT_SUPPORTED')
    area=shape.symmetric_difference(q).area;bound=2*shape.length*GRID_MM+math.pi*GRID_MM**2
    if area>bound:raise ValueError('FILE_GRID_AREA_CHANGE_EXCEEDS_BOUND')
    return q,dict(grid_mm=GRID_MM,mode='valid_output',raw_boundary_hausdorff_mm=boundary_distance(shape.boundary,q.boundary),raw_symmetric_difference_mm2=area,area_change_bound_mm2=bound,vertices_before=sum(len(p.exterior.coords)-1 for p in shape.geoms)if shape.geom_type=='MultiPolygon'else len(shape.exterior.coords)-1,vertices_after=len(q.exterior.coords)-1,subgrid_collapse_visible=boundary_distance(shape,q)>POLYGON_TOLERANCE_MM,holes_after=len(q.interiors))

def export_reference(shape):
    try:return crop_reference(shape)
    except ValueError as error:
        if str(error)not in('UNSUPPORTED_TARGET_POLYGON','UNSUPPORTED_RESOLVABLE_TARGET_HOLE'):raise
    q,metrics=quantize(shape)
    proof=dict(policy='Existing 0.000001 mm valid_output normalization; unwrap a single grid component and preserve every resolvable hole with legal axial cut-ins',verified_geometry_sha256=digest(to_wkb(shape,byte_order=1)),export_reference_sha256=digest(to_wkb(q,byte_order=1)),normalized_geometry_sha256=digest(to_wkb(q,byte_order=1)),grid_mm=GRID_MM,raw_type=shape.geom_type,resolvable_holes_preserved=len(q.interiors),direct_normalization_equal=q.equals(set_precision(shape,GRID_MM,mode='valid_output')),raw_geometry_hausdorff_mm=boundary_distance(shape,q),raw_symmetric_difference_mm2=metrics['raw_symmetric_difference_mm2'],area_change_bound_mm2=metrics['area_change_bound_mm2'],ordinary_quantization=metrics,verified_geometry_unchanged=True)
    return q,proof

def fidelity(reference,actual,*,native_circle=False):
    if actual.is_empty or not actual.is_valid:raise ValueError('REOPENED_GEOMETRY_INVALID')
    expected=reference if native_circle else quantize(reference)[0];observed=actual if native_circle else file_grid(actual);tol=CIRCLE_TOLERANCE_MM if native_circle else POLYGON_TOLERANCE_MM
    if expected.is_empty or observed.is_empty or not expected.is_valid or not observed.is_valid:raise ValueError('FILE_GRID_COMPARISON_GEOMETRY_INVALID')
    distance=boundary_distance(expected,observed);area=expected.symmetric_difference(observed).area;bound=2*expected.length*tol+math.pi*tol**2
    result=dict(passed=all(math.isfinite(v) for v in (distance,area,bound)) and distance<=tol and area<=bound,comparison='native analytic circle vs bounded source approximation'if native_circle else'file-grid verified contour, including preserved holes',hausdorff_mm=distance,symmetric_difference_mm2=area,tolerance_mm=tol,area_bound_mm2=bound)
    if not result['passed']:raise ValueError('CONTOUR_FIDELITY_FAILED:'+str(result))
    return result

def bridge_contour(shape):
    q=orient(shape,sign=1.);outline=[tuple(p)for p in q.exterior.coords[:-1]]
    for ring in q.interiors:
        hole=[tuple(p)for p in ring.coords[:-1]];choices=[]
        exterior=list(q.exterior.coords)
        for hi,h in enumerate(hole):
            for a,b in zip(exterior,exterior[1:]):
                if a[1]==b[1]or not min(a[1],b[1])<=h[1]<=max(a[1],b[1]):continue
                x=a[0]+(h[1]-a[1])*(b[0]-a[0])/(b[1]-a[1]);p=(x,h[1]);line=LineString([p,h])
                if line.length>0 and q.covers(line):choices.append((line.length,hi,p))
        inserted=False
        for _,hi,p in sorted(choices):
            p=(round(p[0],6),round(p[1],6));h=hole[hi]
            if p==h:continue
            for i,a in enumerate(outline):
                b=outline[(i+1)%len(outline)];edge=LineString([a,b])
                if edge.distance(Point(p))>GRID_MM*.75 or q.exterior.distance(edge.interpolate(.5,normalized=True))>GRID_MM:continue
                if p==a:at=i
                elif p==b:at=(i+1)%len(outline)
                else:outline.insert(i+1,p);at=i+1
                loop=hole[hi:]+hole[:hi]+[h,p]
                outline[at+1:at+1]=loop;inserted=True;break
            if inserted:break
        if not inserted:raise ValueError('BOARD_AXIAL_HOLE_BRIDGE_NOT_ESTABLISHED')
    # Reuse the unchanged qualified contour parser, with exact axial out/back
    # edges. Any intersection/winding ambiguity fails instead of being repaired.
    from src.gerber_image import contour
    restored=contour(outline+[outline[0]]);fidelity(shape,restored)
    if len(restored.interiors)!=len(q.interiors):raise ValueError('BOARD_HOLE_TOPOLOGY_NOT_PRESERVED')
    return outline
