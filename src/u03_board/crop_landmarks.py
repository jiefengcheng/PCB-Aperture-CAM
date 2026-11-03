"""Source-proved observability of image landmarks; copper inventory is unchanged.

The existing image witness detects erosion peaks strictly above four pixels.
A standalone source circle at or below that radius cannot supply such a peak.
A circle strictly inside other original copper has no distinct silhouette.
Both dispositions require explicit evidence; all other in-window circles remain
required, including partially covered circles. Matching/acceptance is unchanged.
"""
from shapely import STRtree,prepare
from shapely.ops import unary_union

PEAK_FLOOR_PX=4


def observable(features,manifest,shapes,bounds,mask_shape):
    x0,y0,x1,y1=bounds;ppm=min(mask_shape[1]/(x1-x0),mask_shape[0]/(y1-y0))
    source={r['id']:(i,g) for i,(r,g) in enumerate(zip(manifest['objects'],shapes,strict=True))}
    tree=STRtree(shapes);eligible=[];census=[];unions={};prepared=set()
    for feature in features:
        x,y=feature['center'];r=feature['radius'];coverage=[]
        if not (x0+r<x<x1-r and y0+r<y<y1-r):status='OUTSIDE_COMPLETE_LANDMARK_WINDOW'
        elif r*ppm<=PEAK_FLOOR_PX:status='NOT_OBSERVABLE_BELOW_EXISTING_PEAK_FLOOR'
        else:
            _,core=source[feature['source_id']];aliases=set(feature['aliases'])
            nearby=tuple(sorted(int(i) for i in tree.query(core) if manifest['objects'][int(i)]['id'] not in aliases))
            for i in nearby:
                other=shapes[i]
                if i not in prepared:prepare(other);prepared.add(i)
                if other.covers(core) and other.boundary.disjoint(core.boundary):coverage=[manifest['objects'][i]['id']];break
            if not coverage and nearby:
                if nearby not in unions:unions[nearby]=unary_union([shapes[i] for i in nearby])
                if unions[nearby].covers(core) and unions[nearby].boundary.disjoint(core.boundary):coverage=[manifest['objects'][i]['id'] for i in nearby]
            status='NOT_OBSERVABLE_FULLY_COVERED_SOURCE' if coverage else 'REQUIRED_VISIBLE_LANDMARK'
        census.append(dict(source_id=feature['source_id'],aliases=feature['aliases'],native_center_mm=feature['center'],
                           radius_mm=r,predicted_radius_px=r*ppm,disposition=status,coverage_source_ids=coverage))
        if status=='REQUIRED_VISIBLE_LANDMARK':eligible.append(feature)
    return eligible,census
