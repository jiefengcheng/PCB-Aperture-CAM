"""FC-1 hand-authored oracle for ONE hash-bound Ucamco example.

This module does not read or parse Gerber commands. It is not a production
validator or editing operator. The analytic expectation and polygon witness
are separate constructions from the source-derived mathematical contract.
"""
import math
import numpy as np
from shapely.geometry import Point, LineString
from shapely.ops import unary_union
from shapely import affinity

QUADRANTS=512
ARC_SEGMENTS=2048
LINEAR_BUDGET=1e-5
AREA_BUDGET=1e-4
# Read from source manually: translation, X/Y mirror, rotation, uniform scale.
PLACEMENTS=((0,0,1,1,0,1),(10,0,-1,1,0,1),
            (0,8,1,-1,30,1),(10,8,-1,-1,45,.8))
# Independently written matrices for scale * rotation * mirror; no Shapely output.
C=math.sqrt(3)/2; H=.8/math.sqrt(2)
MATRICES=((1,0,0,1,0,0),(-1,0,0,1,10,0),
          (C,.5,.5,-C,0,8),(-H,H,-H,-H,10,8))
LOCAL_LANDMARKS=(('hole',(-2.5,-1),False),('ring',(-2.125,-1),True),
 ('disk',(-2.5,1),True),('straight',(1,-1),True),
 ('arc_mid',(.5+math.sqrt(2),-1+math.sqrt(2)),True),
 ('arc_inner_void',(1.5,0),False),('absent_major_arc',(-1.5,-1),False),
 ('arc_end',(.5,1),True))

def analytic_area():
    r=.25;R=2;a=R-r
    integral=.5*(r*math.sqrt(a*a-r*r)+a*a*math.asin(r/a))
    intersection=3*math.pi*r*r/4+R*r-integral
    return 1.5+1.0625*math.pi-intersection

def project(point,matrix):
    x,y=point;a,b,c,d,tx,ty=matrix
    return (a*x+b*y+tx,c*x+d*y+ty)

def analytic_bounds(matrix):
    """Exact directional extrema of disks, segment and quarter-arc + stroke."""
    a,b,c,d,tx,ty=matrix;s=math.hypot(a,c)
    def axis(u,v,t):
        values=[]
        for x,y,r in ((-2.5,-1,.5),(-2.5,1,.5)):
            center=u*x+v*y+t;values += [center-s*r,center+s*r]
        for x,y in ((-.5,-1),(2.5,-1)):
            center=u*x+v*y+t;values += [center-s*.25,center+s*.25]
        angles=[0,math.pi/2]
        critical=math.atan2(v,u)
        for angle in (critical,critical+math.pi,critical-math.pi):
            if 0<=angle<=math.pi/2:angles.append(angle)
        radial=[u*(.5+2*math.cos(t0))+v*(-1+2*math.sin(t0))+t for t0 in angles]
        values += [min(radial)-s*.25,max(radial)+s*.25]
        return min(values),max(values)
    lo_x,hi_x=axis(a,b,tx);lo_y,hi_y=axis(c,d,ty)
    return (lo_x,lo_y,hi_x,hi_y)

def analytic_membership(x,y):
    """Exact point-set equations, vectorized; no polygon or parser input."""
    low=np.hypot(x+2.5,y+1);upper=np.hypot(x+2.5,y-1)
    seg=np.hypot(x-np.clip(x,-.5,2.5),y+1)
    dx=x-.5;dy=y+1
    arc=np.where((dx>=0)&(dy>=0),np.abs(np.hypot(dx,dy)-2),
                 np.minimum(np.hypot(x-2.5,y+1),np.hypot(x-.5,y-1)))
    inside=((low<=.5)&(low>=.25))|(upper<=.5)|(seg<=.25)|(arc<=.25)
    # Conservative distance-to-any-boundary band, including hidden primitive
    # edges. This only removes ambiguous samples; it never labels a mismatch PASS.
    margin=np.minimum.reduce([np.abs(low-.5),np.abs(low-.25),np.abs(upper-.5),np.abs(seg-.25),np.abs(arc-.25)])
    return inside,margin

def analytic_scene(x,y):
    inside=np.zeros(np.broadcast(x,y).shape,dtype=bool);margin=np.full(inside.shape,np.inf)
    for m in MATRICES:
        a,b,c,d,tx,ty=m;det=a*d-b*c;s=math.hypot(a,c)
        lx=(d*(x-tx)-b*(y-ty))/det;ly=(-c*(x-tx)+a*(y-ty))/det
        hit,dist=analytic_membership(lx,ly);inside|=hit;margin=np.minimum(margin,dist*s)
    return inside,margin

def local_polygon(fault=None,quadrants=QUADRANTS,segments=ARC_SEGMENTS):
    disk=lambda x,y,r:Point(x,y).buffer(r,quad_segs=quadrants)
    ring=disk(-2.5,-1,.5)
    if fault!='clear_as_dark':ring=ring.difference(disk(-2.5,-1,.25))
    solid=disk(-2.5,1,.5)
    segment=LineString([(-.5,-1),(2.5,-1)]).buffer(.25,quad_segs=quadrants)
    sweep=-3*math.pi/2 if fault=='major_arc' else math.pi/2
    center=(.5,0) if fault=='wrong_arc_center' else (.5,-1)
    points=[(center[0]+2*math.cos(sweep*i/segments),center[1]+2*math.sin(sweep*i/segments)) for i in range(segments+1)]
    arc=LineString(points).buffer(.25,quad_segs=quadrants)
    return unary_union([ring,solid,segment,arc])

def placed_polygons(fault=None,quadrants=QUADRANTS,segments=ARC_SEGMENTS):
    if fault not in (None,'wrong_mirror','wrong_order','wrong_scale','clear_as_dark','major_arc','wrong_arc_center','inch_units'):
        raise ValueError('Unknown FC-1 witness fault; no silent baseline substitution')
    local=local_polygon(fault,quadrants,segments);result=[]
    for i,(x,y,mx,my,angle,scale) in enumerate(PLACEMENTS):
        if fault=='wrong_mirror' and i==2:mx,my=-1,1
        if fault=='wrong_scale' and i==3:scale=1
        if fault=='wrong_order':
            g=affinity.rotate(local,angle,origin=(0,0));g=affinity.scale(g,mx,my,origin=(0,0))
        else:
            g=affinity.scale(local,mx,my,origin=(0,0));g=affinity.rotate(g,angle,origin=(0,0))
        g=affinity.scale(g,scale,scale,origin=(0,0));g=affinity.translate(g,x,y)
        if fault=='inch_units':g=affinity.scale(g,25.4,25.4,origin=(0,0))
        result.append(g)
    return result

def assess_polygons(polygons):
    results=[]
    for index,(shape,matrix) in enumerate(zip(polygons,MATRICES)):
        scale=math.hypot(matrix[0],matrix[2]);expected_area=analytic_area()*scale*scale
        bounds=analytic_bounds(matrix);error=max(abs(a-b) for a,b in zip(shape.bounds,bounds))
        landmarks=[]
        for name,p,expected in LOCAL_LANDMARKS:
            world=project(p,matrix);actual=shape.covers(Point(world))
            landmarks.append({'name':name,'point_mm':world,'expected_copper':expected,'actual_copper':actual,'status':'PASS' if actual==expected else 'FAIL'})
        parts=list(shape.geoms) if shape.geom_type=='MultiPolygon' else [shape]
        topology={'components':len(parts),'holes':sum(len(g.interiors) for g in parts)}
        results.append({'placement':index,'status':'PASS' if abs(shape.area-expected_area)<=AREA_BUDGET and error<=LINEAR_BUDGET and all(x['status']=='PASS' for x in landmarks) and topology=={'components':3,'holes':1} else 'FAIL','topology':topology,
                        'area_mm2':shape.area,'expected_area_mm2':expected_area,'area_error_mm2':abs(shape.area-expected_area),'bounds_mm':shape.bounds,'expected_bounds_mm':bounds,'max_bounds_error_mm':error,'landmarks':landmarks})
    if len(polygons)!=4: return {'status':'FAIL','reason':'four placements required','placements':results}
    return {'status':'PASS' if all(x['status']=='PASS' for x in results) else 'FAIL','placements':results}

def synthetic_probes():
    """Distinct scene extensions; neither is drawn in the official example."""
    local=local_polygon();normal=unary_union(placed_polygons())
    marker=Point(-2.5,-1).buffer(.1,quad_segs=QUADRANTS)
    composed=normal.union(marker)
    wrong_global=composed.difference(Point(-2.5,-1).buffer(.25,quad_segs=QUADRANTS))
    # A conceptual fifth flash at (0,-5), after reset, uses the identity aperture.
    identity=affinity.translate(local,0,-5)
    leaked=affinity.scale(local,-1,-1,origin=(0,0));leaked=affinity.rotate(leaked,45,origin=(0,0));leaked=affinity.scale(leaked,.8,.8,origin=(0,0));leaked=affinity.translate(leaked,0,-5)
    probe=(-2.5,-4)
    return {'transparent_clear':{'status':'PASS' if composed.covers(Point(-2.5,-1)) and not wrong_global.covers(Point(-2.5,-1)) else 'FAIL',
                                'positive_context_survives':composed.covers(Point(-2.5,-1)),'wrong_global_clear_rejected':not wrong_global.covers(Point(-2.5,-1)),
                                'reason':'Synthetic pre-existing copper inside local transparent hole must survive a dark block flash.'},
            'reset':{'status':'PASS' if identity.covers(Point(probe)) and not leaked.covers(Point(probe)) else 'FAIL','probe_mm':probe,
                     'positive_identity_copper':identity.covers(Point(probe)),'leaked_transform_rejected':not leaked.covers(Point(probe)),
                     'reason':'Synthetic fifth placement only; official file has no draw after LMN/LR0/LS1.'}}

def png_comparison(path):
    from .fc1_png import orange_components
    w,h,cells,components=orange_components(path)
    # Calibrate from two isolated unrotated disks: centers (-2.5,1), (12.5,1).
    disks=[g for g in components if 1000<g['pixels']<1100 and 390<g['centroid'][1]<430]
    if len(disks)!=2:raise ValueError('PNG calibration landmarks absent')
    left,right=sorted(disks,key=lambda g:g['centroid'][0])
    left_x,left_y=[v+.5 for v in left['centroid']];right_x,right_y=[v+.5 for v in right['centroid']]
    scale=(right_x-left_x)/15;tx=left_x+2.5*scale;ty=(left_y+right_y)/2+scale
    xx,yy=np.meshgrid(np.arange(w)+.5,np.arange(h)+.5)
    inside,margin=analytic_scene((xx-tx)/scale,(ty-yy)/scale)
    observed=np.zeros((h,w),dtype=bool)
    for x,y in cells:observed[y,x]=True
    confident=margin>2/scale
    mismatches=confident&(inside!=observed)
    return {'status':'PASS' if not mismatches.any() and len(components)==12 else 'FAIL','comparison':'Secondary raster cross-check only; not precision/conformance evidence.',
            'image_size_px':[w,h],'components':len(components),'scale_px_per_mm':scale,'origin_px':[tx,ty],
            'excluded_boundary_band_px':2,'tested_pixels':int(confident.sum()),'mismatched_interior_pixels':int(mismatches.sum()),
            'excluded_pixels':int((~confident).sum()),'calibration':'Two unrotated solid pad centroids; uniform scale and Y inversion only, no per-placement fitting.'}


def polygon_vs_analytic_grid():
    from shapely import contains_xy
    shape=unary_union(placed_polygons())
    xx,yy=np.meshgrid(np.arange(-3.5,13.5,.025),np.arange(-2,11,.025))
    expected,margin=analytic_scene(xx,yy);actual=contains_xy(shape,xx,yy)
    stable=margin>2*LINEAR_BUDGET
    mismatch=stable&(expected!=actual)
    return {'status':'PASS' if not mismatch.any() else 'FAIL','sample_spacing_mm':.025,
            'stable_samples':int(stable.sum()),'boundary_excluded_samples':int((~stable).sum()),
            'mismatches':int(mismatch.sum()),'limitation':'Finite point-set cross-check; analytic area, bounds, topology and named landmarks are separate obligations.'}
