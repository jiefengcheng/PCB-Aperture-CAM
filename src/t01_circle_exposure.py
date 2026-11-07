"""Measure original exposed circumference, not covered disk area or pixels.

Polygon edges split the analytic source circle into angular intervals. An
interval midpoint determines whether that whole open arc lies in other copper.
Tangencies have zero arc length. All contributors are unioned before measuring.
"""
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
from shapely.geometry import Point, box
from shapely.ops import unary_union
from shapely import to_wkb

REGISTRY=Path(__file__).resolve().parents[1]/'contracts/t01_circle_exposure/settings.json'
SCHEMA='t01-circle-exposure-settings/1'


def _pairs(pairs):
    result={}
    for key,value in pairs:
        if key in result:raise ValueError('DUPLICATE_T01_CIRCLE_EXPOSURE_SETTING:'+key)
        result[key]=value
    return result


@dataclass(frozen=True)
class Settings:
    minimum_exposed_circumference_fraction_for_growth: float
    source_sha256: str
    raw_json: str

    def snapshot(self):
        return dict(json.loads(self.raw_json),registry_sha256=self.source_sha256,
                    registry_json=self.raw_json)


def from_bytes(raw):
    def invalid(value):raise ValueError('NONFINITE_T01_CIRCLE_EXPOSURE_SETTING:'+value)
    value=json.loads(raw,object_pairs_hook=_pairs,parse_constant=invalid)
    fixed=dict(schema=SCHEMA,revision=1,status='PROVISIONAL',
               comparison='GROWTH_ELIGIBLE_WHEN_GREATER_OR_EQUAL',
               context='COMPLETE_ORIGINAL_STAGE_ENTRY_RESOLVED_COPPER',
               exclude='SELF_AND_EXACT_GEOMETRIC_ALIASES',
               measurement='ANALYTIC_SOURCE_CIRCLE_ARC_LENGTH_AGAINST_ORIGINAL_FINITE_COPPER_UNION',
               action_below_limit='KEEP_EXACT_PREDECESSOR',
               scope='T01_CIRCLES_ONLY; existing full-containment KEEP and all growth checks remain')
    key='minimum_exposed_circumference_fraction_for_growth'
    if (type(value)is not dict or set(value)!={*fixed,key}
            or type(value['revision'])is not int or any(value[k]!=v for k,v in fixed.items())):
        raise ValueError('T01_CIRCLE_EXPOSURE_SETTINGS_SCHEMA_CHANGED')
    limit=value[key]
    if type(limit)not in(int,float)or not math.isfinite(limit)or not 0<=limit<=1:
        raise ValueError('T01_CIRCLE_EXPOSURE_FRACTION_OUT_OF_RANGE')
    return Settings(float(limit),hashlib.sha256(raw).hexdigest(),raw.decode('utf-8'))


def capture(path=REGISTRY):return from_bytes(Path(path).read_bytes())


def exposed_arcs(center,radius,other):
    if (len(center)!=2 or any(not math.isfinite(v)for v in center)
            or not math.isfinite(radius)or radius<=0 or not other.is_valid):
        raise ValueError('T01_EXPOSURE_FINITE_CIRCLE_REQUIRED')
    cx,cy=center;events={0.,2*math.pi}
    def rings(g):
        if g.geom_type=='Polygon':return [g.exterior,*g.interiors]
        return [r for child in getattr(g,'geoms',())for r in rings(child)]
    for ring in rings(other):
        coords=list(ring.coords)
        for a,b in zip(coords,coords[1:]):
            # Normalize to a unit circle before solving segment intersections.
            x,y=(a[0]-cx)/radius,(a[1]-cy)/radius
            vx,vy=(b[0]-a[0])/radius,(b[1]-a[1])/radius
            length2=vx*vx+vy*vy
            if not length2:continue
            t=-(x*vx+y*vy)/length2
            px,py=x+t*vx,y+t*vy
            height2=1.-(px*px+py*py)
            if height2<0:continue
            offset=math.sqrt(height2/length2)
            for root in (t-offset,t+offset):
                if 0<=root<=1:
                    events.add(math.atan2(y+root*vy,x+root*vx)%(2*math.pi))
    angles=sorted(events);intervals=[]
    for start,end in zip(angles,angles[1:]):
        mid=(start+end)/2
        covered=other.covers(Point(cx+radius*math.cos(mid),cy+radius*math.sin(mid)))
        intervals.append(dict(start_radians=start,end_radians=end,exposed=not covered))
    angle=math.fsum(v['end_radians']-v['start_radians']for v in intervals if v['exposed'])
    return angle/(2*math.pi),intervals


def assess(site,index,settings,containment=None):
    """Use the immutable original index; current growth is never an operand."""
    sid=site['source_id'];core=site['core'];cx,cy=site['center'];radius=site['radius']
    nearby=sorted(index.ids[int(i)]for i in index.tree.query(box(cx-radius,cy-radius,cx+radius,cy+radius)))
    excluded={sid,*site['aliases']}|{s for s in nearby if index.geometries[s].equals(core)}
    contributors=[s for s in nearby if s not in excluded]
    other=unary_union([index.geometries[s]for s in contributors])
    # Clip only outside the analytic circle's bounding box. This changes no
    # circular arc and bounds the polygon-edge work and interval witness size.
    other=other.intersection(box(cx-radius,cy-radius,cx+radius,cy+radius))
    fraction,intervals=exposed_arcs(site['center'],radius,other)
    fully_contained=(containment or index.assess(sid,site['aliases']))['contained']
    eligible=fraction>=settings.minimum_exposed_circumference_fraction_for_growth
    return dict(source_id=sid,source_geometry_sha256=hashlib.sha256(to_wkb(core)).hexdigest(),
                excluded_aliases=sorted(excluded),context_source_ids=contributors,
                other_copper_union_sha256=hashlib.sha256(to_wkb(other)).hexdigest(),
                center_mm=list(site['center']),radius_mm=radius,
                circumference_mm=2*math.pi*radius,
                exposed_arc_length_mm=fraction*2*math.pi*radius,
                exposed_circumference_fraction=fraction,arc_intervals=intervals,
                minimum_exposed_circumference_fraction_for_growth=settings.minimum_exposed_circumference_fraction_for_growth,
                comparison='GREATER_OR_EQUAL; no percentage tolerance added',
                fully_contained=fully_contained,keep=fully_contained or not eligible,
                disposition='KEEP_CONTAINED'if fully_contained else
                    'ELIGIBLE_FOR_ORDINARY_T01_CHECKS'if eligible else'KEEP_EXPOSED_CIRCUMFERENCE_BELOW_LIMIT',
                settings_sha256=settings.source_sha256)
