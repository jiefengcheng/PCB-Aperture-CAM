"""Flexible-end repair of exposed steps on an already admitted outline.

Discovery uses the assembled local boundary, so a catalogue seam or a branch
does not hide the defect. Constructors receive local operands only.
"""
import math
import numpy as np
from shapely.geometry import LineString, Point, Polygon
from shapely.geometry.polygon import orient
from shapely.ops import substring
from src.native_inventory import ERROR_MM
from .boundary_finish import polygons, sharp_points as native_sharp_points
from .finite_profile_union import polygonal
from shapely.ops import unary_union
from shapely.errors import GEOSException


def unit(v):
    return v / np.linalg.norm(v)


def turn(a, b):
    return math.degrees(math.atan2(float(a[0]*b[1]-a[1]*b[0]), float(a @ b)))


def overlap_area(a,b):
    # GEOS can fail constructing the dimension of a disjoint mixed collection.
    # The exact interior predicate settles zero area without any overlay,
    # rounding, tolerance change or exemption for real overlapping copper.
    if a.is_empty or b.is_empty or not a.relate_pattern(b,'T********'):return 0.
    return a.intersection(b).area


def source_interval_caps(chain,caps,stations,fallback):
    """Ordered original source limits, in the compiled native chain frame."""
    width=chain['width'];intervals=chain.get('source_intervals',())
    return np.asarray([max([caps.get(s,width)-width for a,b,s in intervals
        if a-1e-12<=station<=b+1e-12]or[fallback])for station in stations])


def interval_cap(chain,caps,first,last):
    """Use the source sections in this repair interval, never a distant limit."""
    sources=[s for a,b,s in chain.get('source_intervals',())if a<last and b>first]
    if not sources:raise ValueError('SHOULDER_NATIVE_SOURCE_INTERVALS_REQUIRED')
    return min(caps.get(s,chain['width'])for s in sources)-chain['width']


def source_station(chain,source,point):
    """Locate the causing occurrence, not a nearby pass of a long route."""
    from shapely.ops import substring
    spans=[(a,b)for a,b,s in chain.get('source_intervals',())if s==source]
    if len(spans)!=1:raise ValueError('SHOULDER_NATIVE_SOURCE_STATION_NOT_ESTABLISHED')
    first,last=spans[0]
    return first+substring(chain['line'],first,last).project(point)


def native_continuation(rows,sources,source,end):
    """Whether a prepared native peer continues beyond this drawing end."""
    points=np.asarray(rows[source]['metadata']['route_points_mm'])
    point=points[0 if end==0 else -1]
    direction=unit(point-points[1 if end==0 else -2])
    for other in sources:
        if other==source:continue
        peer=np.asarray(rows[other]['metadata']['route_points_mm'])
        for first,second in((peer[0],peer[1]),(peer[-1],peer[-2])):
            if np.linalg.norm(first-point)<=2*ERROR_MM and float((second-point)@direction)>2*ERROR_MM:return True
    return False


def retain_endpoint_fields(values,old,capacity,caps,rates,stations):
    """Fit the local field between fixed, admitted end sections.

    Propagate the end requirements before taking a slope-bounded minorant.
    Existing material is a permitted upper bound at its own station only;
    it is never a transferable clearance or scalar allowance.
    """
    travel=np.r_[0.,np.cumsum(rates*np.diff(stations))]
    lower=np.maximum(0.,np.maximum(old[0]-travel[:,None],old[-1]-(travel[-1]-travel)[:,None]))
    upper=np.maximum(capacity,old)
    budgets=np.maximum(caps,old.sum(axis=1))
    if np.any(lower>upper+1e-12)or np.any(lower.sum(axis=1)>budgets+1e-12):return None
    result=np.minimum(np.maximum(values,lower),upper)
    spare=result-lower
    fractions=np.minimum(1.,np.maximum(0.,budgets-lower.sum(axis=1))/np.maximum(spare.sum(axis=1),1e-30))
    result=lower+spare*fractions[:,None]
    return result


def sharp_points(image,floor,angle):
    # Discovery only: exact overlays can insert nanometre collinear slivers
    # next to a real shoulder. They must not hide its physical turn merely
    # because one incident serialized segment is shorter than the error bound.
    # Neither the source floor nor the emitted contour is replaced.
    return native_sharp_points(image.simplify(ERROR_MM/10,preserve_topology=True),floor,angle)


def steps(image, floor, angle=10.):
    """Pair the convex and concave corners of a short exposed width step.

    Simplification is for discovery only. Original source contours are never
    simplified or replaced. Curved native boundaries retain their precision.
    """
    points=sharp_points(image, floor, angle)
    if not points:return []
    targets=[Point(p) for p in points];result=[]
    for face in polygons(image):
        face=orient(face)
        for ring in [face.exterior, *face.interiors]:
            coords=np.asarray(LineString(ring.coords).simplify(4*ERROR_MM).coords)[:-1]
            for i,a in enumerate(coords):
                b=coords[(i+1)%len(coords)];edge=b-a;h=float(np.linalg.norm(edge))
                if not 4*ERROR_MM<h<=.08:continue
                incoming=a-coords[i-1];outgoing=coords[(i+2)%len(coords)]-b
                if min(np.linalg.norm(incoming),np.linalg.norm(outgoing))<=2*ERROR_MM:continue
                t1,t2=turn(incoming,edge),turn(edge,outgoing)
                if t1*t2>=0 or min(abs(t1),abs(t2))<=30:continue
                # A width step can lie on an original bend. Its longitudinal
                # directions need not be parallel; the existing constructor
                # checks emitted alignment against the original native axes.
                if not any(min(p.distance(q) for p in targets)<=8*ERROR_MM for q in (Point(a),Point(b))):continue
                # A positive first turn is the convex, wide corner. Otherwise
                # walk the narrow edge in the reverse boundary direction.
                if t1>0:
                    low=np.asarray([coords[(i+1+j)%len(coords)] for j in range(len(coords))])
                    wide=a
                else:
                    low=np.asarray([coords[(i-j)%len(coords)] for j in range(len(coords))])
                    wide=b
                exposed=[list(p.coords[0])for p in targets if min(p.distance(Point(a)),p.distance(Point(b)))<=8*ERROR_MM]
                result.append(dict(point_mm=((a+b)/2).tolist(),wide=wide,narrow=low,
                    exposed_corner_points_mm=exposed,
                    height_mm=h,wide_tangent=unit(incoming if t1>0 else -outgoing)))
    return result


def patch(step,angle=10.):
    return round_aperture_bridge(step,angle)


def round_aperture_bridge(step,angle=10.,*,length=None):
    """A C1 outward offset that decays to zero along the narrow boundary.

    The cubic is an additive majorant: it retains the full wide corner and
    reaches the original narrow boundary with zero slope. Each emitted edge is
    checked against its local boundary direction, including offset curvature.
    """
    low=np.asarray(LineString(step['narrow']).simplify(16*ERROR_MM).coords)
    wide=step['wide'];height=step['height_mm']
    length=2.0*height/math.tan(math.radians(angle))if length is None else length
    line=LineString(low)
    if line.length<length+4*ERROR_MM:raise ValueError('SHOULDER_NARROW_EDGE_TOO_SHORT')
    base=substring(line,0,length)
    native=np.asarray(base.coords)
    stations=np.r_[0.,np.cumsum(np.linalg.norm(np.diff(native,axis=0),axis=1))]
    knots=np.unique(np.r_[stations,np.linspace(0,length,max(33,int(length/.001)+1))])
    knots=knots[np.r_[True,np.diff(knots)>1e-10]]
    p=np.column_stack([np.interp(knots,stations,native[:,j]) for j in (0,1)])
    f=knots/length;offset=height*(1-3*f*f+2*f*f*f)
    # Round-aperture envelopes carry the native curvature without inward
    # offset folds. Only their exposed external tangents form new taper rails.
    from .growth_bridge import exposed_alignment
    from shapely.ops import unary_union
    disks=[Point(point).buffer(float(radius),quad_segs=128) if radius>1e-14 else Point(point)
        for point,radius in zip(p,offset)]
    shape=polygonal(unary_union([disks[i].union(disks[i+1]).convex_hull for i in range(len(disks)-1)]))
    maximum,hidden,internal=exposed_alignment(shape,p,p,offset,angle)
    maximum=max(maximum,abs(turn(step['wide_tangent'],p[1]-p[0])))
    if maximum>angle+1e-6:raise ValueError('SHOULDER_MATERIALIZED_ANGLE_EXCEEDED')
    if not shape.is_valid:raise ValueError('SHOULDER_PATCH_INVALID')
    return shape,dict(maximum_materialized_alignment_angle_degrees=maximum,
        length_mm=length,height_mm=height,endpoint_derivatives=[0.,0.],
        hidden_internal_aperture_segments=hidden,maximum_internal_axis_angle_degrees=internal,
        angle_proof='EXPOSED_ROUND_APERTURE_TANGENTS; LOCAL_BOUNDARY_CUBIC_MAJORANT')


def complete_contact(image, reference, angle,*,carrier=None,whole=False,window=None):
    """Round only newly created contact corners; retain every admitted point.

    These are local shape operands, not board searches. A closing is accepted
    only through its positive difference. Each emitted outline is rechecked.
    """
    from .growth_bridge import meaningful_shoulders
    trial=polygonal((image if carrier is None else carrier).union(reference));radii=[]
    def corners(shape):
        return[p for p in meaningful_shoulders(shape,sharp_points(shape,image,angle))if window is None or window.covers(Point(p))]
    for radius in (0.,.005,.01,.02,.04,.08):
        if radius:
            points=corners(trial);fills=[]
            for point in points:
                collar=Point(point).buffer(3*radius).envelope
                local=trial.intersection(collar)
                closed=local.buffer(radius,quad_segs=128).buffer(-radius,quad_segs=128)
                fill=closed.difference(local).intersection(Point(point).buffer(radius).envelope)
                fills.extend(g for g in polygons(fill)if g.distance(reference)<=2*ERROR_MM)
            if fills:trial=polygonal(trial.union(unary_union(fills)))
            radii.append(radius)
        remaining=corners(trial)
        if not remaining:return (trial if whole else polygonal(trial.difference(image))),dict(contact_radii_mm=radii,new_shoulders=0)
    raise ValueError('SHOULDER_CONTACT_OUTLINE_UNRESOLVED')


def local_variants(image,required,reference,forbidden,angle,junction=Polygon(),*,domain=None):
    """Keep the additive solution first; permit only local, paid-for recession.

    Original and fixed contributors form a separate immutable floor. Shape
    operators cannot erase that floor or withdraw an entire native chain.
    """
    from .growth_bridge import meaningful_shoulders
    domain=reference.envelope.buffer(.1)if domain is None else domain
    contact_window=reference.envelope.buffer(.03)
    contact_window=contact_window.union(unary_union([g for g in polygons(junction)if g.distance(reference)<=.03]))
    safe=polygonal(image.union(reference.difference(forbidden)))
    if not junction.is_empty:
        # A three-way mouth is a union of arms, not a cross section of one
        # trace. Complete its concave contacts together, including inherited
        # corners which an added-corner-only detector deliberately ignores.
        radius=.03
        closed=safe.buffer(radius,quad_segs=128).buffer(-radius,quad_segs=128)
        mouth=closed.difference(safe).intersection(junction).difference(forbidden)
        safe=polygonal(safe.union(mouth))
    bases=[safe]
    reallocated=polygonal(safe.difference(forbidden.intersection(domain)).union(required))
    if image.difference(reallocated).area>1e-12:bases.append(reallocated)
    for base in bases:
        for radius in (0.,.0001,.00025,.0005,.001,.002,.004,.008,.016):
            trial=base
            if radius:
                opened=base.buffer(-radius,quad_segs=128).buffer(radius,quad_segs=128)
                trial=polygonal(unary_union([image.difference(domain),required,opened.intersection(domain)]))
            try:
                candidate,proof=complete_contact(required,trial,angle,carrier=trial,whole=True,window=contact_window)
            except ValueError:
                candidate=trial;proof={}
            added=candidate.difference(image).difference(forbidden).intersection(domain)
            removed=image.difference(candidate).intersection(domain).difference(required)
            candidate=polygonal(image.difference(removed).union(added))
            new=meaningful_shoulders(candidate,sharp_points(candidate,image,angle))
            if not new and added.area>ERROR_MM**2 and added.area+1e-12>=removed.area:
                yield dict(image=candidate,added=polygonal(added),removed=polygonal(removed),
                    proof=dict(proof,recession_radius_mm=radius,prepared_budget_reallocation=base is not safe),net_mm2=added.area-removed.area)


def discover(rows, paths, bodies, original, caps, covered, supports, angle,material):
    """Prepare component outlines once; find steps beyond catalogue seams."""
    from .boundary_finish import compile_graph
    plans=[];source_order={s:i for i,s in enumerate(original)}
    for batch in compile_graph(rows,paths,bodies,original,set(covered),supports):
        eligible=[s for s in batch['sources']if s not in covered and caps.get(s,0)>rows[s]['metadata']['minimum_caliper_mm']+2*ERROR_MM]
        if not eligible:continue
        contact_ids=sorted({s for r in batch['route_ids']for s in supports.get(r,{})}-set(batch['sources']),key=source_order.__getitem__)
        domain=unary_union([bodies[s]for s in batch['sources']]).buffer(.75).envelope
        batch['support']=polygonal(unary_union([material[s].intersection(domain)for s in contact_ids]))
        grown=polygonal(unary_union([bodies[s]for s in batch['sources']]+[batch['support']]))
        floor=polygonal(unary_union([original[s]for s in batch['sources']]+[original[s].intersection(domain)for s in contact_ids]))
        optional=polygonal(grown.difference(floor))
        if optional.is_empty:continue
        for step in steps(grown,floor,angle):
            site=Point(step['point_mm'])
            # Original pad necks belong to T05. A T04 interface must actually
            # meet admitted widening, rather than merely be in its vicinity.
            if optional.distance(site)>step['height_mm']/2+4*ERROR_MM:continue
            candidates=[s for s in eligible if bodies[s].distance(site)<=step['height_mm']/2+4*ERROR_MM]
            if not candidates:continue
            source=min(candidates,key=lambda s:(original[s].distance(site),s))
            record=dict(point_mm=step['point_mm'],kind='EXPOSED_WIDTH_SHOULDER',route_id=batch['identity'],
                route_ids=batch['route_ids'],source_ids=[source],primary_source_id=source,status='UNRESOLVED',optional_growth_withdrawn=False,
                wide_point_mm=step['wide'].tolist(),narrow_point_mm=step['narrow'][0].tolist(),height_mm=step['height_mm'],
                exposed_corner_points_mm=step['exposed_corner_points_mm'],
                maximum_transition_angle_degrees=angle,baseline_preserved=True,added_area_mm2=0.,removed_area_mm2=0.,net_growth_area_mm2=0.)
            # Endpoints are variables of the repair, not a prerequisite
            # fixed by an initial additive proposal. Discovery supplies only
            # the physical feature and a conservative local dependency bound.
            reference=None;proof=dict(repair_principle='FLEXIBLE_ENDS_PRIMARY')
            record['repair_principle']='FLEXIBLE_ENDS_PRIMARY'
            reach=max(.1,min(.75,3*step['height_mm']/math.tan(math.radians(angle))))
            envelope=site.buffer(reach).envelope;window=envelope.buffer(.25)
            # An interface can join an already wider native donor. Its
            # local width budget is the larger adjacent admitted section,
            # not a new scalar growth grant along the whole trace.
            contacts=sorted(set(batch['sources'])|{s for r in batch['route_ids']for s in supports.get(r,{})},key=source_order.__getitem__)
            # Consolidated sources may share the entire admitted chain.
            # Custody follows the original occurrence nearest this site,
            # not whichever alias carries the largest duplicate contour.
            source=min(candidates,key=lambda s:(original[s].distance(site),s));record['source_ids']=[source]
            peers=[s for s in contacts if 'route_points_mm'in rows[s]['metadata']
                and original[s].distance(bodies[source])<=2*ERROR_MM
                and original[s].distance(envelope)<=.1]
            donor_width=max([caps[source],*[max(caps.get(s,0),rows[s]['metadata']['minimum_caliper_mm'])for s in peers]])
            from .ribbon_profile import frame
            from .side_profile import extent
            native=rows[source]['metadata']['route_points_mm'];line=LineString(native)
            station=line.project(site);span=max(step['height_mm']*12,rows[source]['metadata']['minimum_caliper_mm']*2)
            stations=sorted(set(max(0.,min(line.length,station+d))for d in np.linspace(-span,span,9)))
            p,n,t,_=frame(native,extra_stations=stations)
            native_skin=polygonal(unary_union([material[s].intersection(window)for s in peers]))
            measurements=[]
            for j in np.flatnonzero((t>=max(0.,station-span))&(t<=min(line.length,station+span))):
                size=float(np.linalg.norm(n[j]))
                section=extent(native_skin,p[j],n[j]/size,max(.5,donor_width*3))
                if section is not None:measurements.append(dict(point_mm=p[j].tolist(),width_mm=sum(section)/size))
            if measurements:donor_width=max(donor_width,max(v['width_mm']for v in measurements))
            axes=[LineString(rows[s]['metadata']['route_points_mm'])for s in peers]
            # Existing T04 source fields can be displaced by up to .025 mm.
            # This broad spatial envelope is followed by an actual two-face
            # cross-section test; it is not a second width permission.
            upper=unary_union([g.buffer(donor_width/2+.025+2*ERROR_MM,quad_segs=128)for g in axes])
            upper=polygonal(upper.union(batch['support']))
            record.update(profile=proof,interface_width_budget_mm=donor_width,
                width_budget_policy='LOCAL_ADJACENT_ADMITTED_SECTION; GLOBAL_SCALAR_UNCHANGED',donor_measurements=measurements)
            # Native junction paths already bind their consolidated source
            # carriers. Splitting that path into two-arm chains must not turn
            # the other carriers of the same local widening into immutable
            # context merely because their original primitive is farther away.
            seeds=list(paths.get(next((r for r in batch['route_ids']if source in paths[r]),''),[source]))
            plans.append(dict(chain=dict(source_ids=[source]),native_seed_sources=seeds,batch=batch,record=record,step=step,patch=reference,envelope=envelope,upper=upper))

    return plans


def admitted_donor(plan,data,rows):
    """Measure the assembled adjoining native skin, including aliases.

    A contribution can carry a complete consolidated chain, while its original
    occurrence ends before the wider donor. Sample the donor's actual boundary
    station on each already prepared native axis, including its end tangent.
    No ownership or neighbor search is performed here.
    """
    from .side_profile import extent
    native=[s for s in data.get('native_sources',data.get('same_owner',[]))if 'route_points_mm'in rows[s]['metadata']]
    if not native:return
    skin=polygonal(unary_union([data['operands'][s]for s in native]));witnesses=[]
    for location in (plan['record']['wide_point_mm'],plan['record']['narrow_point_mm']):
        point=Point(location)
        for source in native:
            line=LineString(rows[source]['metadata']['route_points_mm'])
            width=rows[source]['metadata']['minimum_caliper_mm']
            if line.distance(point)>width/2+.05:continue
            station=line.project(point);q=np.asarray(line.interpolate(station).coords[0])
            a=np.asarray(line.interpolate(max(0.,station-2*ERROR_MM)).coords[0])
            b=np.asarray(line.interpolate(min(line.length,station+2*ERROR_MM)).coords[0])
            if np.linalg.norm(b-a)<=1e-14:continue
            tangent=unit(b-a);normal=np.array([-tangent[1],tangent[0]])
            q=q+tangent*float((np.asarray(location)-q)@tangent)
            for shift in (-4*ERROR_MM,0.,4*ERROR_MM):
                center=q+tangent*shift
                section=extent(skin,center,normal,.5)
                if section is not None:witnesses.append(dict(source_id=source,point_mm=center.tolist(),width_mm=sum(section)))
    if not witnesses:return
    witness=max(witnesses,key=lambda w:w['width_mm'])
    budget=max(plan['record']['interface_width_budget_mm'],witness['width_mm'])
    plan['record'].update(interface_width_budget_mm=budget,assembled_donor_witness=witness)
    upper=unary_union([LineString(rows[s]['metadata']['route_points_mm']).buffer(budget/2+.025+2*ERROR_MM,quad_segs=128)for s in native])
    plan['upper']=polygonal(plan['upper'].union(upper))


def width_barrier(rows,sources,skin,record,domain,caps):
    """Prepare two-face budgets in native frames; do not clip by a round cap.

    A disk tangent to a curved boundary can exceed a transverse width budget
    even though its radius field is smooth. The unchanged opposite face fixes
    the remaining budget, using the existing native-frame extent machinery.
    """
    from .ribbon_profile import frame,window_frame
    from .side_profile import extent
    barriers=[];point=Point(record['point_mm'])
    radius=max(domain.bounds[2]-domain.bounds[0],domain.bounds[3]-domain.bounds[1])+.1
    for s in sources:
        limit=caps[s]
        points=rows[s]['metadata']['route_points_mm'];line=LineString(points)
        if line.distance(point)>rows[s]['metadata']['minimum_caliper_mm']/2+.1:continue
        station=line.project(point);lo=max(0.,station-radius);hi=min(line.length,station+radius)
        if hi-lo<=4*ERROR_MM:continue
        extra=list(np.linspace(lo,hi,max(3,int((hi-lo)/.001)+1)))
        extra.extend(max(lo,min(hi,station+d))for d in np.linspace(-.5,.5,41))
        p,n,t,_=frame(points,extra_stations=extra)
        selected=(t>=lo-1e-12)&(t<=hi+1e-12);p,n,t=p[selected],n[selected],t[selected]
        j=int(np.argmin(abs(t-station)));side=1 if float((np.asarray(record['point_mm'])-p[j])@n[j])>=0 else -1
        # Normal cells stop at a drawing endpoint; round-aperture copper does
        # not. Continue the terminal tangent across the local seam so a patch
        # cannot evade a two-face budget just beyond that endpoint's cell.
        if lo==0. and not native_continuation(rows,sources,s,0):
            tangent=unit(np.asarray(points[1])-np.asarray(points[0]))
            p=np.vstack([p[0]-tangent*(limit+.03),p]);n=np.vstack([n[0],n])
        if hi==line.length and not native_continuation(rows,sources,s,1):
            tangent=unit(np.asarray(points[-1])-np.asarray(points[-2]))
            p=np.vstack([p,p[-1]+tangent*(limit+.03)]);n=np.vstack([n,n[-1]])
        low=[];high=[];outer_low=[];outer_high=[]
        for center,normal in zip(p,n):
            size=float(np.linalg.norm(normal));section=extent(skin,center,normal/size,limit+.2)
            if section is None:section=(rows[s]['metadata']['minimum_caliper_mm']/2,)*2
            positive,negative=[v/size for v in section];budget=max(limit,positive+negative)
            from .side_profile import CAP_RESERVE
            if side>0:positive=max(rows[s]['metadata']['minimum_caliper_mm']/2,budget-negative-CAP_RESERVE)
            else:negative=max(rows[s]['metadata']['minimum_caliper_mm']/2,budget-positive-CAP_RESERVE)
            low.append(center-normal*negative);high.append(center+normal*positive)
            reach=max(positive,negative,limit)+.03
            outer_low.append(center-normal*reach);outer_high.append(center+normal*reach)
        allowed=polygonal(unary_union([Polygon([low[i],low[i+1],high[i+1],high[i]]).convex_hull for i in range(len(p)-1)]))
        writable=polygonal(unary_union([Polygon([outer_low[i],outer_low[i+1],outer_high[i+1],outer_high[i]]).convex_hull for i in range(len(p)-1)]))
        barriers.append(writable.intersection(domain).difference(allowed))
    return polygonal(unary_union(barriers))


def junction_mouths(rows,original,caps,data,domain):
    """Bound physical multi-arm contacts from the prepared same-owner inputs.

    Endpoint caps can make a T contact even when the drawing axes stop short of
    each other. Distinct outgoing rays distinguish it from a two-arm bend or a
    collinear width change. This neither rebuilds owners nor searches a board.
    """
    ids=[s for s in data.get('native_sources',data.get('same_owner',[]))if 'route_points_mm'in rows[s]['metadata']and original[s].intersects(domain)]
    lines={s:LineString(rows[s]['metadata']['route_points_mm'])for s in ids};zones=[];seen=[]
    for i,s in enumerate(ids):
        for other in ids[i+1:]:
            if not original[s].intersects(original[other]):continue
            contact=original[s].intersection(original[other]).intersection(domain)
            if contact.area<=1e-12:continue
            point=contact.centroid
            if any(point.distance(p)<4*ERROR_MM for p in seen):continue
            rays=[];widths=[];growth=[];local_caps=[]
            for sid,line in lines.items():
                width=rows[sid]['metadata']['minimum_caliper_mm']
                if line.distance(point)>width/2+2*ERROR_MM:continue
                station=line.project(point);delta=min(.01,line.length/3)
                center=np.asarray(line.interpolate(station).coords[0])
                for at in (max(0.,station-delta),min(line.length,station+delta)):
                    vector=np.asarray(line.interpolate(at).coords[0])-center
                    if np.linalg.norm(vector)<=2*ERROR_MM:continue
                    ray=unit(vector)
                    reach=max(float((np.asarray(p)-center)@ray)for p in line.coords)
                    if reach<=width/2+2*ERROR_MM:
                        # A short cap can lead into an adjoining collinear
                        # source. Reuse that known physical contact rather
                        # than inventing another ray inside a round end cap.
                        for peer,other_line in lines.items():
                            if peer==sid or not original[sid].intersects(original[peer]):continue
                            axis=np.asarray(other_line.coords[-1])-np.asarray(other_line.coords[0])
                            if np.linalg.norm(axis)<=1e-14 or min(abs(turn(ray,axis)),abs(turn(ray,-axis)))>5:continue
                            reach=max(reach,max(float((np.asarray(p)-center)@ray)for p in other_line.coords))
                    if reach<=width/2+2*ERROR_MM:continue
                    if not any(abs(turn(ray,r))<5 for r in rays):rays.append(ray)
                widths.append(width);growth.append(max(0.,caps.get(sid,width)-width));local_caps.append(caps.get(sid,width))
            if len(rays)>=3:
                radius=max(widths)/2+max(local_caps)/2+max(growth)
                zones.append(point.buffer(radius,quad_segs=128));seen.append(point)
    boundary=data.get('fill_boundary',Polygon())
    if not boundary.is_empty:
        for source in ids:
            contact=boundary.intersection(original[source]).intersection(domain)
            if contact.is_empty:continue
            width=rows[source]['metadata']['minimum_caliper_mm'];cap=caps.get(source,width)
            for part in getattr(contact,'geoms',[contact]):
                zones.append(part.centroid.buffer(width/2+cap/2+max(0.,cap-width),quad_segs=128))
    return polygonal(unary_union(zones))


def prepare_sections(rows,sources,caps,record,clip,junction,domain,before,*,spacing=None):
    """Prepare unchanged native frames and predecessor widths once per feature.

    These are local operands from the dependency batch. Alternative bridge ends
    share their reference sections; only the emitted width is measured again.
    """
    from .ribbon_profile import frame
    from .side_profile import extent
    result=[];inner=clip.buffer(-2*ERROR_MM);site=Point(record['point_mm'])
    for source in sources:
        metadata=rows[source]['metadata'];native=metadata['route_points_mm'];line=LineString(native)
        reach=caps[source]+.03
        if line.distance(domain)>reach:continue
        station=line.project(site)
        extra=[max(0.,min(line.length,station+d))for d in np.linspace(-.5,.5,41)]
        if spacing is not None:
            # Match the construction barrier's original moving frames. This
            # is prepared once, only when a proposal enters its headroom.
            radius=max(domain.bounds[2]-domain.bounds[0],domain.bounds[3]-domain.bounds[1])+.1
            lo=max(0.,station-radius);hi=min(line.length,station+radius)
            extra.extend(np.linspace(lo,hi,max(3,math.ceil((hi-lo)/spacing)+1)))
        centers,normals,_,_=frame(native,extra_stations=extra)
        for center,normal in zip(centers,normals):
            point=Point(center)
            if point.distance(domain)>reach or not inner.covers(point)or junction.covers(point):continue
            size=float(np.linalg.norm(normal));normal=normal/size
            if not clip.covers(LineString([center-normal*reach,center+normal*reach])):continue
            old=extent(before,center,normal,reach)
            old_width=0. if old is None else sum(old)/size
            result.append(dict(source_id=source,center=center,normal=normal,size=size,reach=reach,
                old_width=old_width,old_present=old is not None,minimum=metadata['minimum_caliper_mm'],
                budget=max(caps[source],old_width)))
    return result


def run(rows,paths,bodies,original,caps,*,covered=(),supports=None,prepare=None,maximum_transition_angle_degrees=10.,progress=None,material=None,review_bounds=None,terminals=(),carriers=None,endpoint_sections=()):
    """Build flexible-end interfaces after one source-bound dependency batch."""
    from time import perf_counter
    from shapely import to_wkb
    from .source_trace_floor import preserve
    from .growth_bridge import meaningful_shoulders
    from .boundary_finish import new_pockets,component_count,retain_carriers
    started=perf_counter();angle=maximum_transition_angle_degrees
    if type(angle)not in(int,float)or not math.isfinite(angle)or not 0<angle<45:
        raise ValueError('VALID_TRANSITION_ANGLE_REQUIRED')
    plans=discover(rows,paths,bodies,original,caps,set(covered),supports or {},angle,material or bodies)
    from shapely import from_wkb
    from .terminal_handoff import interior_t04 as interior
    deferred=[];protected={};attachments={}
    for terminal in terminals:
        scope=from_wkb(bytes.fromhex(terminal['optional_scope_wkb_hex']))
        if 'attachment_scope_wkb_hex'in terminal:
            attachment=from_wkb(bytes.fromhex(terminal['attachment_scope_wkb_hex']))
            scope=scope.intersection(attachment)
            for source in terminal['source_ids']:attachments.setdefault(source,[]).append(attachment)
        for source in terminal['source_ids']:protected.setdefault(source,[]).append(scope)
    protected={s:polygonal(unary_union(regions))for s,regions in protected.items()}
    attachments={s:unary_union(regions)for s,regions in attachments.items()}
    frozen={(s['source_id'],tuple(round(v,10)for v in s['endpoint_mm'])):s for s in endpoint_sections}
    route_sections={};source_routes={}
    for obligation in endpoint_sections:route_sections.setdefault(obligation['route_id'],[]).append(obligation)
    for route,members in paths.items():
        if route in route_sections:
            for source in members:source_routes.setdefault(source,[]).append(route)
    # Keep the already-grown end section at a genuine terminal until T05 owns
    # its finishing. The existing attachment map supplies custody; no larger
    # search window, new source role or clearance lookup is introduced.
    terminal_sections={}
    for source,attachment in attachments.items():
        if source not in bodies or source not in caps:continue
        points=np.asarray(rows[source]['metadata']['route_points_mm']);strips=[]
        for index,neighbor in((0,1),(-1,-2)):
            center=points[index]
            if not attachment.covers(Point(center)):continue
            obligation=frozen.get((source,tuple(round(float(v),10)for v in center)))
            if obligation is not None:
                from shapely.affinity import translate
                section=obligation['section'];line=LineString([section['lower_mm'],section['upper_mm']])
                strips.append(line.buffer(4*ERROR_MM,cap_style=2))
                if not obligation.get('native_frame_transition_admitted',False):
                    dx,dy=obligation.get('inward_offset_mm',(0.,0.))
                    strips.append(translate(line,xoff=dx,yoff=dy).buffer(4*ERROR_MM,cap_style=2))
                continue
            tangent=unit(points[neighbor]-center);normal=np.asarray([-tangent[1],tangent[0]])
            reach=caps[source]+.03
            strips.append(LineString([center-normal*reach,center+normal*reach]).buffer(4*ERROR_MM,cap_style=2))
        if strips:
            terminal_sections[source]=unary_union(strips)
            protected[source]=polygonal(unary_union([protected.get(source,Polygon()),terminal_sections[source]]))
    if terminals:
        kept=[]
        for plan in plans:
            owned=[r for r in terminals if set(r['source_ids']).intersection(plan['record']['source_ids'])]
            # A step midpoint can lie in unchanged pad copper while its only
            # newly exposed corner is a genuine T05 attachment. Custody follows
            # every exposed corner, not the midpoint or the broad search box.
            corners=plan['record']['exposed_corner_points_mm']
            if interior(corners,owned):kept.append(plan)
            else:deferred.extend(corners)
        plans=kept
    if review_bounds is not None:
        from shapely.geometry import box
        regions=[box(*b)for b in review_bounds]
        plans=[p for p in plans if any(g.covers(Point(p['record']['point_mm']))for g in regions)]
    if prepare is None and plans:raise ValueError('SHOULDER_PREPARED_ALLOWANCE_REQUIRED')
    local,finalize=prepare(plans)if prepare is not None else({},dict(queries=0))
    prepared=callable(finalize)
    for i,plan in enumerate(plans):
        plan['record']['plan_index']=i
        data=local[i];primary=plan['record']['source_ids'][0]
        if prepared:admitted_donor(plan,data,rows)
        domain=plan['envelope'].buffer(.1)
        domain=domain.union(Point(plan['record']['point_mm']).buffer(.7)).envelope
        plan['repair_domain']=domain
        plan['reference']=plan['patch']
        editable=[s for s in data.get('native_contact_sources',data.get('same_owner',[primary]))if s in bodies and s not in covered
            and caps.get(s,0)>rows[s]['metadata']['minimum_caliper_mm']+2*ERROR_MM
            and bodies[s].difference(original[s]).intersects(domain)]
        editable=list(dict.fromkeys([primary,*editable]))
        plan['record']['source_ids']=editable;plan['chain']['source_ids']=editable
        junction=junction_mouths(rows,original,caps,data,domain.buffer(.1))if prepared else Polygon()
        plan['junction']=junction
    allowances,preparation=finalize(plans)if prepared else(local,finalize)
    working=dict(bodies);reports=[];checks=[];changes={};sections={}
    from .ribbon_profile import frame
    from .side_profile import extent
    from .bridge_budget import NeighborhoodBudget
    ledger=NeighborhoodBudget(plans,local)
    for i,plan in enumerate(plans):
        record=plan['record'];sources=record['source_ids']
        if progress:progress(dict(event='shoulder_repair_started',point_mm=record['point_mm'],plan_index=i))
        allowance=allowances[i];clip=allowance.get('clip',plan['envelope'].buffer(.5));data=local[i]
        operands={s:working[s].intersection(clip)if s in working else g for s,g in data.get('operands',{}).items()}
        context=polygonal(unary_union([g for s,g in operands.items()if s not in sources]))if operands else allowance['context']
        native_context=polygonal(unary_union([g for s,g in operands.items()if s not in sources and
            s in data.get('native_sources',data.get('same_owner',[]))and 'route_points_mm'in rows[s]['metadata']]))
        before={s:working[s]for s in sources}
        before_components={s:component_count(g)for s,g in before.items()}
        member_floors={}
        for source in sources:
            members=(carriers or {}).get(source,[source])
            # These memberships come from the qualified constructor, not a
            # neighbour/owner reconstruction. A shared contour must retain
            # every original member it represents inside the repair window.
            member_floors[source]=polygonal(unary_union([original[source],
                *[original[s].intersection(clip)for s in members if s!=source]]))
        before_image=polygonal(unary_union([g.intersection(clip)for g in before.values()]+[context]))
        before_native=polygonal(unary_union([g.intersection(clip)for g in before.values()]+[native_context]))
        # Adjoining saved widening is a retained construction operand, not
        # original copper. In particular a consolidated chain can occur in
        # several source bodies. Treating that duplicate skin as the floor
        # falsely declared an untouched shoulder already resolved.
        floor_image=polygonal(unary_union([original[s].intersection(clip)
            for s in dict.fromkeys([*sources,*operands])]))
        plan['discovery_floor']=floor_image
        if prepared:allowance['forbidden']=allowance['current_barrier'](working)
        accepted=None;attempts=[]
        # Materialize against the final batched reservation and the current
        # adjoining skin. Earlier same-owner repairs may change the opposite
        # face. Reusing its stale width allowance would overdraw one budget.
        if prepared:
            barrier=width_barrier(rows,sources,before_native,record,plan['repair_domain'],caps).difference(plan['junction'])
            forbidden=polygonal(unary_union([allowance['forbidden'],barrier]))
            required=polygonal(unary_union([member_floors[s].intersection(clip)for s in sources]+[context]))
        else:
            barrier=Polygon();forbidden=allowance['forbidden']
            required=polygonal(unary_union([member_floors[s].intersection(clip)for s in sources]+[context]))
        required=polygonal(unary_union([required,*[before[s].intersection(protected[s]).intersection(clip)for s in sources if s in protected]]))
        target=Point(record['point_mm']).buffer(max(.03,2*record['height_mm']))
        inherited=[p for p in meaningful_shoulders(before_image,sharp_points(before_image,floor_image,angle))if target.covers(Point(p))]
        if not inherited:
            record.update(status='RESOLVED_BY_COUPLED_BRIDGE',added_area_mm2=0.,removed_area_mm2=0.,net_growth_area_mm2=0.,
                remaining_shoulders=0,baseline_preserved=True,disposition='NO_REPEATED_TREATMENT_OF_COMPLETED_FEATURE')
            reports.append(record);continue
        probes=prepare_sections(rows,sources,caps,record,clip,plan['junction'],plan['repair_domain'],before_native)
        dense_probes=None
        from itertools import chain as variants_in_order
        variants=variants_in_order(junction_profile_variants(plan,before_image,forbidden,angle),
            edge_profile_variants(plan,before_image,required,angle),
            native_profile_variants(
                plan,rows,original,caps,before_image,before_native,required,allowance['forbidden'],angle,
                bodies={s:g.intersection(clip)for s,g in before.items()}))
        if forbidden.covers(plan['repair_domain'])and ledger.members[i]['credit_mm2']<=1e-12:
            variants=();attempts.append(dict(reasons=['NO_FREE_PREPARED_ADDITION_DOMAIN'],
                verification='EXACT_PREPARED_DOMAIN_COVERAGE; NO_LOCAL_COPPER_CREDIT'))
        for variant in variants:
            record['local_proposals_evaluated']=record.get('local_proposals_evaluated',0)+1
            if record['local_proposals_evaluated']>14:raise ValueError('LOCAL_SHOULDER_PROPOSAL_BOUND_EXCEEDED')
            trial={};reasons=[];trial_sections={};rejected_geometry=None
            native_reference=variant['proof'].get('angle_proof','').startswith('EXISTING_NATIVE_TWO_FACE_MATERIALIZER')
            addition_parts=[]if native_reference else list(polygons(variant['image'].difference(before_image)))
            try:
                for source in sources:
                    domain=None;owned=None;proposed=None;source_floor=None
                    if native_reference:
                        if source not in variant['reference_sources']:
                            trial[source]=before[source];continue
                        domain=variant['domain'].intersection(clip);cut_domain=domain.buffer(-2*ERROR_MM)
                        proposed=polygonal(unary_union([before[source].difference(cut_domain),original[source],variant['reference'].intersection(domain)]))
                    else:
                        domain=variant.get('domain',plan['repair_domain']).intersection(clip)
                        # Apply the actual physical change, retaining duplicate
                        # source carriers. Subtracting all context from a full
                        # replacement needlessly erased overlapped optional
                        # widening even for a purely additive bridge.
                        intended=variant['image']
                        retained=before[source].intersection(intended)
                        # Only newly added physical copper needs a carrier.
                        # Copying all of intended-minus-context also copied
                        # other traces' existing skin into every editable
                        # source, including detached fragments far from it.
                        connected=[part for part in addition_parts if part.intersects(retained)]
                        owned=polygonal(unary_union([retained,*connected]))
                        proposed=polygonal(unary_union([before[source].difference(domain),original[source],owned.intersection(domain)]))
                    source_floor=member_floors[source]if source not in protected else polygonal(member_floors[source].union(before[source].intersection(protected[source])))
                    trial[source],_=preserve(source_floor,proposed)
                    trial_components=component_count(trial[source])
                    if trial_components>before_components[source]:
                        # Reuse the existing local carrier cleanup. Every
                        # original member and all old widening outside this
                        # repair remain anchors; only detached optional skin
                        # inside the repair can be removed. The physical
                        # realization and net-gain checks below still apply.
                        anchors=polygonal(unary_union([source_floor,before[source].difference(domain)]))
                        trial[source]=retain_carriers(trial[source],anchors)
                        trial_components=component_count(trial[source])
                    if trial[source].equals(before[source]):trial[source]=before[source]
                    if trial_components>before_components[source]:
                        reasons.append('SOURCE_CARRIER_DISCONNECTED')
                    if source in attachments and trial[source].symmetric_difference(before[source]).intersection(attachments[source]).area>1e-12:
                        reasons.append('T05_SOURCE_ATTACHMENT_CHANGED')
                    if trial[source].symmetric_difference(before[source]).difference(clip).area>ERROR_MM**2:
                        reasons.append('SOURCE_CHANGE_OUTSIDE_PREPARED_WINDOW')
            except GEOSException as error:
                if not before[source].is_valid or not original[source].is_valid:raise
                # Only an uncommitted optional proposal failed. Keep the
                # valid admitted widening and try the next bounded variant.
                reasons.append('OPTIONAL_SOURCE_OVERLAY_FAILED')
                rejected_geometry=dict(source_id=source,kernel_error=str(error),
                    before_wkb_hex=to_wkb(before[source]).hex(),
                    original_floor_wkb_hex=to_wkb(original[source]).hex(),
                    **({}if domain is None else dict(domain_wkb_hex=to_wkb(domain).hex())),
                    **({}if owned is None else dict(owned_wkb_hex=to_wkb(owned).hex())))
                record.setdefault('rejected_generated_overlays',[]).append(rejected_geometry)
            except ValueError as error:
                if (str(error)=='SOURCE_FLOOR_REQUIRES_VALID_FINITE_COPPER'and
                        not source_floor.is_empty and source_floor.is_valid and
                        source_floor.geom_type in('Polygon','MultiPolygon')and not proposed.is_valid):
                    # This is a generated proposal, not an invalid input floor.
                    # Retain its exact rejection evidence and try the next
                    # already-bounded local construction, without repairing,
                    # snapping or accepting the invalid polygon.
                    from shapely import is_valid_reason
                    reasons.append('INVALID_GENERATED_SOURCE_COPPER')
                    rejected_geometry=dict(source_id=source,validity_reason=is_valid_reason(proposed),
                        original_floor_wkb_hex=to_wkb(source_floor).hex(),proposed_wkb_hex=to_wkb(proposed).hex())
                    record.setdefault('invalid_generated_proposals',[]).append(rejected_geometry)
                elif str(error)=='SOURCE_FLOOR_POSITIVE_COPPER_STILL_MISSING':reasons.append(str(error))
                else:raise
            if reasons:
                attempts.append(dict(reasons=reasons,**({}if rejected_geometry is None else dict(rejected_source_geometry=rejected_geometry))))
                continue
            clipped_trial={s:g.intersection(clip)for s,g in trial.items()}
            after_image=polygonal(unary_union([*clipped_trial.values(),context]))
            after_native=polygonal(unary_union([*clipped_trial.values(),native_context]))
            added=after_image.difference(before_image);removed=before_image.difference(after_image)
            if added.area+removed.area<=ERROR_MM**2:
                attempts.append(dict(reasons=['NO_VISIBLE_REBRIDGE_CHANGE'],verification='NOT_RUN_UNCHANGED_PROPOSAL'));continue
            if not ledger.allows(i,added.area-removed.area):
                attempts.append(dict(reasons=['LOCAL_GROWTH_BUDGET_EXHAUSTED'],added_mm2=added.area,removed_mm2=removed.area,
                    verification='NOT_RUN_UNAFFORDABLE_PROPOSAL; RECOMPUTE_AFTER_NEARBY_COMMITS'));continue
            if added.difference(plan['upper']).area>ERROR_MM**2:reasons.append('SHOULDER_ADJACENT_SECTION_WIDTH_BUDGET')
            if overlap_area(added,allowance['forbidden'])>1e-12:reasons.append('OUTSIDE_PREPARED_GROWTH_ALLOWANCE')
            if reasons:
                # A proposal outside an authenticated prepared allowance is
                # already rejected. Do not measure its rails or reconstruct
                # a second local outline merely to reject it again.
                attempts.append(dict(reasons=sorted(set(reasons)),added_mm2=added.area,removed_mm2=removed.area,
                    verification='NOT_RUN_OUTSIDE_PREPARED_ADDITION_ALLOWANCE'))
                continue
            headroom_overlap=0. if native_reference else overlap_area(added,barrier)
            candidate_probes=probes
            if headroom_overlap>1e-12:
                # The barrier reserves construction headroom with the old
                # opposite face fixed. It is not another scalar width limit.
                # Check the actual two-face result in the same dense original
                # frames instead of vetoing an otherwise admissible bridge.
                if dense_probes is None:
                    dense_probes=prepare_sections(rows,sources,caps,record,clip,plan['junction'],
                        plan['repair_domain'],before_native,spacing=.001)
                candidate_probes=dense_probes
            intended=variant['image'].intersection(clip)
            if intended.difference(after_image).area>ERROR_MM**2 or after_image.difference(intended).difference(before_image).area>ERROR_MM**2:
                reasons.append('REBRIDGE_NOT_REALIZED_BY_SERIALIZED_SOURCES')
            if removed.difference(plan['repair_domain']).area>1e-12:reasons.append('RECESSION_OUTSIDE_BRIDGE_WINDOW')
            if component_count(after_image)>component_count(before_image):reasons.append('SOURCE_CHAIN_DISCONNECTED')
            maximum_width=0.;width_failures=[];delta=added.union(removed)
            for probe in candidate_probes:
                center=probe['center'];normal=probe['normal'];reach=probe['reach'];size=probe['size']
                if delta.distance(Point(center))>reach:continue
                new=extent(after_native,center,normal,reach)
                if new is None:
                    if probe['old_present']:reasons.append('SOURCE_CENTERLINE_NOT_COVERED')
                    continue
                measured=sum(new)/size;maximum_width=max(maximum_width,measured)
                if probe['old_width']>probe['minimum']+4*ERROR_MM and measured<=probe['minimum']+2*ERROR_MM:
                    physical=extent(after_image,center,normal,reach)
                    if physical is None or sum(physical)/size<=probe['minimum']+2*ERROR_MM:reasons.append('NEW_NAKED_EXPOSED_SECTION')
                if measured>probe['budget']+2*ERROR_MM:
                    reasons.append('SHOULDER_EMITTED_SECTION_WIDTH_BUDGET')
                    width_failures.append(dict(source_id=probe['source_id'],point_mm=center.tolist(),width_mm=measured,budget_mm=probe['budget']))
            remaining=meaningful_shoulders(after_image,sharp_points(after_image,before_image,angle))
            if remaining:reasons.append('SERIALIZED_SHOULDER_INTERFACE_HAS_NEW_CORNER')
            target=Point(record['point_mm']).buffer(max(.03,2*record['height_mm']))
            target_corners=[p for p in meaningful_shoulders(after_image,sharp_points(after_image,floor_image,angle))if target.covers(Point(p))]
            if target_corners:reasons.append('TARGETED_SHOULDER_REMAINS')
            if new_pockets(before_image,before_image,after_image):reasons.append('NEW_POCKET')
            if not reasons:
                from .growth_bridge import affected_sections
                emitted_buffers={}
                for chain in plan['batch']['chains']:
                    if not set(chain['source_ids']).intersection(trial):continue
                    previous={s:working[s]for s in chain['source_ids']}
                    emitted={s:trial.get(s,working[s])for s in chain['source_ids']}
                    interior_nodes={point for point,edges in plan['batch']['nodes'].items()if len(edges)>=2}
                    # A certified local rebridge can change an optional end
                    # section at a side-contact or fill junction, too. Refresh
                    # only actual affected sections inside this repair window;
                    # genuine terminal attachment sections remain unchanged.
                    for source in set(chain['source_ids']).intersection(trial):
                        for point in (rows[source]['metadata']['route_points_mm'][0],rows[source]['metadata']['route_points_mm'][-1]):
                            if plan['repair_domain'].covers(Point(point))and not attachments.get(source,Polygon()).covers(Point(point)):
                                interior_nodes.add(tuple(point))
                    emitted_sections=affected_sections(rows,chain,previous,emitted,interior_nodes=interior_nodes,
                        frozen_sections=frozen)
                    for (source,_),section in emitted_sections.items():
                        line=LineString([section['lower_mm'],section['upper_mm']])
                        if source not in emitted_buffers:
                            emitted_buffers[source]=clipped_trial[source].buffer(ERROR_MM,quad_segs=128)
                        if line.difference(emitted_buffers[source]).length>ERROR_MM:
                            reasons.append('EMITTED_END_SECTION_NOT_REALIZED')
                    trial_sections.update(emitted_sections)
                # A qualified port can be completed by an adjoining member of
                # the maintained route. Refresh such an affected dependency
                # from that route's prepared LOCAL operands, never unrelated
                # same-owner copper or a new board/ownership search.
                affected_routes={route for source in trial for route in source_routes.get(source,())}
                for route in sorted(affected_routes):
                    obligations=[ob for ob in route_sections[route]
                        if plan['repair_domain'].covers(Point(ob['endpoint_mm']))and
                        not attachments.get(ob['source_id'],Polygon()).covers(Point(ob['endpoint_mm']))]
                    if not obligations:continue
                    members=[s for s in paths[route]if s in operands or s in trial]
                    old_route=polygonal(unary_union([before[s].intersection(clip)if s in before else operands[s]for s in members]))
                    new_route=polygonal(unary_union([clipped_trial[s]if s in trial else operands[s]for s in members]))
                    if old_route.equals(new_route):continue
                    old_buffer=None;new_buffer=None
                    for ob in obligations:
                        token=(ob['source_id'],tuple(round(v,10)for v in ob['endpoint_mm']))
                        if token in trial_sections:continue
                        section=sections.get(token,ob['section'])
                        line=LineString([section['lower_mm'],section['upper_mm']])
                        if new_buffer is None:new_buffer=new_route.buffer(ERROR_MM,quad_segs=128)
                        if line.difference(new_buffer).length<=ERROR_MM:continue
                        if old_buffer is None:old_buffer=old_route.buffer(ERROR_MM,quad_segs=128)
                        if line.difference(old_buffer).length>ERROR_MM:
                            reasons.append('INHERITED_ROUTE_SECTION_NOT_REALIZED');continue
                        lower=np.asarray(section['lower_mm']);upper=np.asarray(section['upper_mm'])
                        center=(lower+upper)/2;normal=unit(upper-lower)
                        size=extent(new_route,center,normal,line.length/2+.2)
                        if size is None:
                            reasons.append('EMITTED_ROUTE_SECTION_NOT_REALIZED');continue
                        replacement=dict(normal=normal.tolist(),lower_mm=(center-normal*size[1]).tolist(),
                            upper_mm=(center+normal*size[0]).tolist(),
                            policy='CERTIFIED_FLEXIBLE_MAINTAINED_ROUTE_DEPENDENCY; ORIGINAL_SECTION_FRAME')
                        actual=LineString([replacement['lower_mm'],replacement['upper_mm']])
                        if actual.length>line.length+2*ERROR_MM or actual.difference(new_buffer).length>ERROR_MM:
                            reasons.append('EMITTED_ROUTE_SECTION_NOT_REALIZED');continue
                        trial_sections[token]=replacement
            if reasons:
                attempts.append(dict(reasons=sorted(set(reasons)),added_mm2=added.area,removed_mm2=removed.area,
                    maximum_width_mm=maximum_width,width_budget_mm=record['interface_width_budget_mm'],width_failures=width_failures,target_corners_mm=target_corners,
                    new_corners_mm=remaining,
                    construction=variant['proof'].get('angle_proof','LOCAL_OUTLINE_COMPLETION')));continue
            accepted=trial
            sections.update(trial_sections)
            record['discovery_profile']=record['profile']
            record['profile']=dict(record['profile'],**variant['proof'])if 'angle_proof'not in variant['proof']else dict(variant['proof'])
            record['copper_budget']=ledger.commit(i,added.area-removed.area)
            record['physical_change']=dict(added_wkb_hex=to_wkb(added).hex(),removed_wkb_hex=to_wkb(removed).hex())
            record.update(status='BRIDGED',mode='ADDITIVE_EXPOSED_SHOULDER'if removed.area<=1e-12 else'LOCAL_RECESSION_WITH_GAP_GAIN',
                added_area_mm2=added.area,removed_area_mm2=removed.area,net_growth_area_mm2=added.area-removed.area,
                original_removed_area_mm2=0.,remaining_shoulders=0,baseline_preserved=removed.area<=1e-12,
                maximum_emitted_source_width_mm=maximum_width,prepared_native_sections=len(candidate_probes),
                construction_headroom_overlap_mm2=headroom_overlap,
                section_validation='DENSE_ORIGINAL_TWO_FACE_FRAMES'if headroom_overlap>1e-12 else'ORIGINAL_NATIVE_FRAMES')
            break
        if accepted is None:
            from collections import Counter
            rejected=Counter(reason for attempt in attempts for reason in attempt['reasons'])
            record['reason']=','.join(sorted(rejected))if rejected else'SHOULDER_NO_ADMITTED_COMPLETION'
            record['rejection_counts']=dict(sorted(rejected.items()))
            record['attempts']=attempts
        else:
            working.update(accepted)
            for source,g in accepted.items():changes[source]=polygonal(bodies[source].symmetric_difference(g))
            checks.append(dict(passed=True,remaining_shoulders=0,new_pockets=0,added_area_mm2=record['added_area_mm2'],
                removed_area_mm2=record['removed_area_mm2'],net_growth_area_mm2=record['net_growth_area_mm2'],original_removed_area_mm2=0.))
        reports.append(record)
        if progress:progress(dict(event='exposed_shoulder_bridge',point_mm=record['point_mm'],status=record['status'],
            rejection_counts=record.get('rejection_counts',{})))
    return working,changes,sections,dict(schema='t04-exposed-shoulder-bridges/1',reports=reports,
        repair_principle='FLEXIBLE_ENDS_PRIMARY',fixed_additive_seed_required=False,
        parameter_search=False,budget_retries=0,maximum_local_proposals_per_feature=14,
        finished_assembly_checks=checks,copper_budgets=ledger.receipt(),preparation=preparation,wall_s=perf_counter()-started,
        deferred_terminal_candidate_points_mm=deferred,terminal_owner='T05_SOURCE_LAND_WINDOW',
        scene_indexes_built=0,clearance_queries=0,owner_reconstructions=0,complete_board_unions=0,
        smoothed=sum(r['status']=='BRIDGED'for r in reports),unresolved=sum(r['status']=='UNRESOLVED'for r in reports))


def native_profile_variants(plan,rows,original,caps,image,native,required,forbidden,angle,*,bodies):
    """One local native C1 rebridge, using the qualified round materializer.

    The current adjacent end sections set the two face allocations. There is
    no reach grid, reserve sweep, allocation sweep or offset-profile fallback.
    The caller retains the normal source, allowance and emitted-width checks.
    """
    from .ribbon_profile import window_frame
    from .side_profile import extent,CAP_RESERVE
    from .growth_bridge import ribbon
    site=Point(plan['record']['point_mm']);primary=plan['record']['primary_source_id']
    chain=next((c for c in plan['batch']['chains']if not c['fixed']and primary in c['source_ids']),None)
    if chain is None:return
    width=chain['width']
    if chain['line'].distance(site)>width/2+.04:return
    station=source_station(chain,primary,site)
    reach=max(.05,min(.1,2*plan['record']['height_mm']/math.tan(math.radians(angle))))
    lo=max(0.,station-reach);hi=min(chain['line'].length,station+1.5*reach)
    if hi-lo<8*ERROR_MM:return
    try:p,n,_,_=window_frame(chain['points'],lo,hi)
    except ValueError as error:
        if str(error)not in('NONDEGENERATE_NATIVE_PROFILE_PATH_REQUIRED','RESIDUAL_REVERSAL_JOIN_UNSUPPORTED','RESIDUAL_MITER_OUTLIER'):raise
        return
    cap=interval_cap(chain,caps,lo,hi)
    if cap<=4*ERROR_MM:return
    old=[]
    for center,normal in zip(p[[0,-1]],n[[0,-1]]):
        size=float(np.linalg.norm(normal));section=extent(native,center,normal/size,width+.2)
        old.append([0.,0.]if section is None else[max(0.,v/size-width/2)for v in section[::-1]])
    old=np.asarray(old);midpoint=np.mean(old,axis=0);total=float(midpoint.sum())
    target=cap-min(2*CAP_RESERVE,3*cap/4)
    middle=midpoint*(target/total)if total>2*ERROR_MM else np.asarray([target/2]*2)
    try:
        left,left_proof,_=ribbon(chain,lo,(lo+hi)/2,old[0],middle,angle)
        right,right_proof,_=ribbon(chain,(lo+hi)/2,hi,middle,old[-1],angle)
    except ValueError as error:
        if not str(error).startswith('BRIDGE_'):raise
        plan['record']['native_local_rejection']=str(error);return
    line=substring(chain['line'],lo,hi)
    # Replace this native ribbon's skin, not another nearby arm of the same
    # shared carrier. The former width-plus-margin radius was over twice the
    # actual half-width and could cut neighbouring widening.
    radius=width/2+max(float(old.max()),float(middle.max()))+4*ERROR_MM
    domain=line.buffer(radius,quad_segs=128,cap_style=2).intersection(plan['repair_domain'])
    shape=polygonal(left.union(right))
    chain_required=polygonal(unary_union([required,*[g for s,g in bodies.items()if s not in chain['source_ids']]]))
    candidate=polygonal(unary_union([image.difference(domain),chain_required,shape.intersection(domain)]))
    added=polygonal(candidate.difference(image));removed=polygonal(image.difference(candidate))
    if added.area+removed.area<=ERROR_MM**2:return
    yield dict(image=candidate,added=added,removed=removed,reference=shape,reference_sources=chain['source_ids'],
        domain=domain,required=chain_required,net_mm2=added.area-removed.area,proof=dict(
        maximum_materialized_alignment_angle_degrees=max(left_proof['maximum_materialized_alignment_angle_degrees'],right_proof['maximum_materialized_alignment_angle_degrees']),
        angle_proof='EXISTING_NATIVE_TWO_FACE_MATERIALIZER; ROUND_APERTURE_C1_REBRIDGE',
        length_mm=hi-lo,endpoint_derivatives=[0.,0.],native_interval_mm=[lo,hi],
        left_reach_mm=station-lo,right_reach_mm=hi-station,allocation='COUPLED_RADIUS_AND_CENTER_SHIFT'))


def junction_profile_variants(plan,image,forbidden,angle):
    """Move the tangency ends together on a prepared, genuine junction.

    A round closing supplies C1 contact fillets on the joined arms. Only its
    positive local difference is used: all admitted widening is retained.
    The ten-degree width-alignment scope is outside the native junction mouth;
    every new outline junction is also checked by the common corner gate.
    """
    site=Point(plan['record']['point_mm']);mouth=plan['junction']
    if not mouth.covers(site):return
    height=plan['record']['height_mm']
    primary=plan['record']['primary_source_id']
    native=next((c['width']/2 for c in plan['batch']['chains']if primary in c['source_ids']),2*height)
    # The third construction follows the original neck radius. A junction's
    # contact span need not have the same scale as its small width step.
    for reach in dict.fromkeys((height*4/3,height*2,max(height*2,native))):
        closed=image.buffer(reach,quad_segs=128).buffer(-reach,quad_segs=128)
        added=polygonal(closed.difference(image).intersection(mouth).intersection(plan['repair_domain']).difference(forbidden))
        if added.area<=ERROR_MM**2:continue
        candidate=polygonal(image.union(added))
        yield dict(image=candidate,added=added,removed=Polygon(),domain=plan['repair_domain'],net_mm2=added.area,
            proof=dict(repair_principle='FLEXIBLE_ENDS_PRIMARY',angle_proof='SOURCE_QUALIFIED_JUNCTION; FLEXIBLE_C1_CONTACT_TANGENCIES',
                tangency_reach_mm=reach,maximum_materialized_alignment_angle_degrees=0.,
                angle_scope='WIDTH_ALIGNMENT_OUTSIDE_PREPARED_NATIVE_JUNCTION_MOUTH',admitted_widening_removed_mm2=0.))


def edge_profile_variants(plan,image,required,angle):
    """Existing local C1 families, with no Cartesian parameter sweep.

    Prefer retaining the wide edge, then allow independent ends to cut back and
    rebridge. At most two facets of the same physical step are considered.
    Each family computes one pair of tangencies and one pair of handles.
    """
    from .boundary_curve_bridge import variants
    site=Point(plan['record']['point_mm'])
    found=sorted(steps(image,plan.get('discovery_floor',required),angle),key=lambda s:Point(s['point_mm']).distance(site))
    # Prefer actual remaining boundary facets. A covered discovery hint can be
    # closer to the old site than the still-visible shoulder after a coupled
    # repair; it must not displace that real facet from the local selection.
    if 'step'in plan:found.append(plan['step'])
    unique={}
    for step in found:
        if Point(step['point_mm']).distance(site)>max(.03,2*plan['record']['height_mm']):continue
        key=(tuple(step['wide']),tuple(step['narrow'][0]))
        unique.setdefault(key,step)
    current=list(unique.values())
    facets=current if len(current)<3 else[current[0],max(current,key=lambda s:Point(s['point_mm']).distance(site))]
    for family in('RETAIN_WIDE_EDGE','ASYMMETRIC_TANGENCY','FLEXIBLE_ENDS','BALANCED_BEND','SHORT_JUNCTION'):
        for step in facets:
            reach=max(8*ERROR_MM,2*step['height_mm']/math.tan(math.radians(angle)))
            ends={'RETAIN_WIDE_EDGE':(0.,reach),'ASYMMETRIC_TANGENCY':(0.,reach),
                'FLEXIBLE_ENDS':(.5*reach,reach),'BALANCED_BEND':(2*reach,2*reach),
                'SHORT_JUNCTION':(.025,.05)}[family]
            selection=dict(left_reach_mm=ends[0],right_reach_mm=ends[1])
            if family=='ASYMMETRIC_TANGENCY':selection['tangent_fractions']=(.4,.8)
            if family=='SHORT_JUNCTION':selection['chord_scale']=.6 if step['height_mm']<.001 else .8
            for candidate,proof,domain in variants(image,step,angle,selection=selection,
                    native_axis=[c['line']for c in plan['batch']['chains']],junction=plan['junction']):
                added=polygonal(candidate.difference(image));removed=polygonal(image.difference(candidate))
                if added.area+removed.area<=ERROR_MM**2:continue
                yield dict(image=candidate,added=added,removed=removed,domain=domain,
                    proof=dict(proof,local_family=family),net_mm2=added.area-removed.area)
