"""C1 bridges between admitted boundary edges, using local operands only.

The exact old ring supplies end positions and tangents. A bridge can trim an
optional tip while filling a naked transition. Original source floors, width
budgets, neighbors and physical change accounting are verified by the caller.
No board index, ownership operation or clearance API is available here.
"""
import math
import numpy as np
from shapely.geometry import LineString,Point,Polygon
from shapely.geometry.polygon import orient
from shapely.ops import substring
from src.native_inventory import ERROR_MM
from .boundary_finish import polygons
from .smooth_transition import value,tessellate


def alignment(curve,old,step_span,*,native=False,edge_mask=None):
    """Measure every emitted chord against the admitted longitudinal edges.

    The short transverse shoulder is not a longitudinal tangent witness. The
    reference keeps the old native bend, rather than imposing one global axis.
    """
    references=list(old)if isinstance(old,(list,tuple))else[old]
    if len(references)>1 and not native:raise ValueError('ORDERED_SINGLE_BOUNDARY_REFERENCE_REQUIRED')
    starts=np.vstack([np.asarray(r.coords)[:-1]for r in references])
    vectors=np.vstack([np.diff(np.asarray(r.coords),axis=0)for r in references])
    lengths=np.linalg.norm(vectors,axis=1)
    stations=np.r_[0.,np.cumsum(lengths)];mids=(stations[:-1]+stations[1:])/2
    progress=curve[-1]-curve[0]
    keep=(lengths>(1e-14 if native else 2*ERROR_MM))
    if not native:
        keep&=((mids<step_span[0]-1e-12)|(mids>step_span[1]+1e-12))&(vectors@progress>0)
    starts,vectors,lengths=starts[keep],vectors[keep],lengths[keep]
    if not len(starts):raise ValueError('CURVE_BRIDGE_LONGITUDINAL_REFERENCE_REQUIRED')
    edges=np.diff(curve,axis=0);mids=(curve[:-1]+curve[1:])/2;maximum=0.
    if edge_mask is not None:edges,mids=edges[edge_mask],mids[edge_mask]
    for first in range(0,len(edges),128):
        p=mids[first:first+128];edge=edges[first:first+128]
        delta=p[:,None,:]-starts[None,:,:]
        f=np.clip(np.sum(delta*vectors[None,:,:],axis=2)/lengths[None,:]**2,0.,1.)
        distances=np.sum((delta-f[:,:,None]*vectors[None,:,:])**2,axis=2)
        witnesses=vectors[np.argmin(distances,axis=1)]
        dot=np.sum(edge*witnesses,axis=1)
        if native:dot=abs(dot)
        angles=np.degrees(np.arctan2(abs(edge[:,0]*witnesses[:,1]-edge[:,1]*witnesses[:,0]),dot))
        maximum=max(maximum,float(angles.max()))
    return maximum


def emitted_alignment(image,before,axis,*,junction=Polygon()):
    """Measure actual new rail chords; inherited edges retain their witnesses."""
    from shapely import points,distance,covers
    maximum=0.
    for face in polygons(image):
        for ring in[face.exterior,*face.interiors]:
            curve=np.asarray(ring.coords);midpoints=points((curve[:-1]+curve[1:])/2)
            selected=(distance(before.boundary,midpoints)>ERROR_MM/10)&~covers(junction,midpoints)
            selected&=np.linalg.norm(np.diff(curve,axis=0),axis=1)>1e-14
            maximum=max(maximum,alignment(curve,axis,(0,0),native=True,edge_mask=selected))
    return maximum


def variants(image,step,angle,*,diagnostics=None,native_axis=None,junction=Polygon(),selection=None):
    """Construct one local C1 join with independently selected bridge ends.

    Selected marked-feature parameters are construction settings, not accepted
    geometry. Current ring tangencies and all emitted chords are checked anew.
    There is no end-pair or handle search.
    """
    original_wide=np.asarray(step['wide']);original_narrow=np.asarray(step['narrow'][0]);height=step['height_mm']
    diagnostics={}if diagnostics is None else diagnostics
    diagnostics.update(matching_rings=0,curves=0,minimum_alignment_degrees=None,invalid_polygons=0)
    for face in polygons(image):
        face=orient(face)
        rings=[face.exterior,*face.interiors]
        for ring_index,ring in enumerate(rings):
            # A prior coupled bridge can have covered the old narrow vertex.
            # Select actual points on the current ring within this feature's
            # local span; the original vertices are location hints, not fixed
            # construction ends. No retained source coordinate is rounded.
            if max(Point(original_wide).distance(ring),Point(original_narrow).distance(ring))>max(.03,2*height):continue
            diagnostics['matching_rings']+=1
            coords=np.asarray(ring.coords)[:-1];line=LineString(ring.coords);length=line.length
            wi=int(np.argmin(np.linalg.norm(coords-original_wide,axis=1)))
            ni=int(np.argmin(np.linalg.norm(coords-original_narrow,axis=1)))
            wide=coords[wi].copy();narrow=coords[ni].copy()
            forward=(line.project(Point(narrow))-line.project(Point(wide)))%length
            reverse=forward>length/2
            if wi==ni:
                # A coupled repair may cover the old transverse edge so
                # both feature hints now select one surviving corner. Ends
                # can still move to either side of that corner. Requiring
                # two distinct anchor vertices would silently freeze them.
                incoming=coords[wi]-coords[wi-1]
                backward=coords[wi]-coords[(wi+1)%len(coords)]
                hint=np.asarray(step['wide_tangent'])
                reverse=float(backward@hint)/np.linalg.norm(backward)>float(incoming@hint)/np.linalg.norm(incoming)
            if reverse:coords=coords[::-1]
            i=int(np.argmin(np.linalg.norm(coords-wide,axis=1)))
            if np.linalg.norm(coords[i]-wide)>ERROR_MM:continue
            coords=np.vstack([coords[i:],coords[:i]])
            extended=np.vstack([coords,coords,coords,coords[:1]])
            path=LineString(extended);stations=np.r_[0.,np.cumsum(np.linalg.norm(np.diff(extended,axis=0),axis=1))]
            # The transverse edge can contain collinear overlay vertices.
            narrow_station=LineString(np.vstack([coords,coords[:1]])).project(Point(narrow))
            diagnostics.update(forward_station_mm=forward,step_height_mm=height,narrow_station_mm=narrow_station,ring_length_mm=length)
            # Previously coupled repairs can already round part of this
            # feature. Do not require its current boundary span to remain
            # the original straight transverse edge before trying new ends.
            if narrow_station>max(.03,10*height):continue
            reach=max(8*ERROR_MM,2*height/math.tan(math.radians(angle)))
            # Prefer endpoint pairs that retain the previous wide edge in
            # full. Either end may then move when a joint needs cut/rebridge.
            pairs=[(0.,reach)]if selection is None else[(selection['left_reach_mm'],selection['right_reach_mm'])]
            for left,right in pairs:
                if left+right+height>=length/2:continue
                first=length-left;last=length+narrow_station+right
                old=substring(path,first,last);a=np.asarray(old.coords[0]);b=np.asarray(old.coords[-1])
                ai=max(0,int(np.searchsorted(stations,first,side='left')-1))
                bi=min(len(extended)-2,int(np.searchsorted(stations,last,side='right')-1))
                ta=extended[ai+1]-extended[ai];tb=extended[bi+1]-extended[bi]
                ta/=np.linalg.norm(ta);tb/=np.linalg.norm(tb)
                if left==0. and np.linalg.norm(wide-original_wide)<=ERROR_MM/10:
                    a=wide.copy();ta=np.asarray(step['wide_tangent']).copy()
                chord=float(np.linalg.norm(b-a))
                if chord<=4*ERROR_MM:continue
                retained=substring(path,last,first+length)
                handles=[]
                matrix=np.column_stack([ta,tb])
                if abs(float(np.linalg.det(matrix)))>1e-8:
                    alpha,beta=np.linalg.solve(matrix,b-a)
                    if min(alpha,beta)>0 and max(alpha,beta)<3*old.length:
                        handles=[(float(alpha*2/3),float(beta*2/3))]
                if selection is not None and 'handles_mm'in selection:handles=[tuple(selection['handles_mm'])]
                elif selection is not None and 'chord_scale'in selection:
                    handles=[(chord*selection['chord_scale']/3,)*2]
                elif selection is not None and 'tangent_fractions'in selection:
                    # Parallel tangents, or an intersection behind an end,
                    # do not define positive forward tangent handles. Use the
                    # existing short-chord C1 construction directly instead.
                    handles=([tuple(float(v*f)for v,f in zip((alpha,beta),selection['tangent_fractions']))]
                        if handles else[(.8*chord/3,.8*chord/3)])
                elif not handles:handles=[(chord/3,chord/3)]
                for left_handle,right_handle in handles:
                    controls=np.asarray([a,a+ta*left_handle,b-tb*right_handle,b])
                    knots=sorted({t/chord for axis in(0,1)for t,_ in tessellate(controls[:,axis].tolist(),chord,error_mm=ERROR_MM/10)})
                    curve=np.asarray([[value(controls[:,axis],t)for axis in(0,1)]for t in knots])
                    curve[0]=a;curve[-1]=b
                    from shapely import points,covers
                    outside=~covers(junction,points((curve[:-1]+curve[1:])/2))
                    maximum=alignment(curve,old if native_axis is None else native_axis,
                                      (left,left+narrow_station),native=native_axis is not None,edge_mask=outside)
                    diagnostics['curves']+=1
                    diagnostics.setdefault('alignment_trials',[]).append(dict(ends_mm=[left,right],handles_mm=[left_handle,right_handle],angle_degrees=maximum,first_mm=a.tolist(),last_mm=b.tolist(),tangents=[ta.tolist(),tb.tolist()]))
                    previous=diagnostics['minimum_alignment_degrees']
                    if previous is None or maximum<previous:diagnostics.update(minimum_alignment_degrees=maximum,best_ends_mm=[left,right],best_handles_mm=[left_handle,right_handle],
                        best_curve_mm=curve.tolist(),best_reference_mm=list(old.coords),step_span_mm=[left,left+narrow_station])
                    if maximum>angle+1e-6:continue
                    replacement=np.vstack([curve,np.asarray(retained.coords)[1:]])
                    # Both substrings share the same selected original edge
                    # endpoints. Independent arclength interpolation can
                    # differ by an ULP and create a self-crossing closure.
                    # Reuse the selected endpoint, not a geometry repair or
                    # coordinate rounding of the retained ring.
                    replacement[-1]=replacement[0]
                    if reverse:replacement=replacement[::-1]
                    boundary=[list(r.coords)for r in rings];boundary[ring_index]=replacement.tolist()
                    candidate=Polygon(boundary[0],boundary[1:])
                    if not candidate.is_valid or candidate.is_empty:
                        diagnostics['invalid_polygons']+=1;continue
                    # Retain every other local polygon and every other ring.
                    from shapely.ops import unary_union
                    result=unary_union([candidate,*[p for p in polygons(image)if not p.equals(face)]])
                    domain=old.union(LineString(curve)).envelope.buffer(4*ERROR_MM)
                    yield result,dict(maximum_materialized_alignment_angle_degrees=maximum,
                        repair_principle='FLEXIBLE_ENDS_PRIMARY',
                        endpoint_selection='CURRENT_ORDERED_BOUNDARY; INDEPENDENT_TANGENCIES',
                        feature_hint_points_mm=[original_wide.tolist(),original_narrow.tolist()],
                        current_feature_points_mm=[wide.tolist(),narrow.tolist()],
                        angle_scope='WIDTH_ALIGNMENT_OUTSIDE_PREPARED_NATIVE_JUNCTION_MOUTH'if not junction.is_empty else'ALL_EMITTED_CHORDS',
                        angle_proof='C1_ADMITTED_BOUNDARY_HERMITE; EMITTED_CHORDS_AGAINST_'+('ORIGINAL_NATIVE_AXIS'if native_axis is not None else'ADMITTED_LONGITUDINAL_EDGES'),
                        length_mm=last-first,left_reach_mm=left,right_reach_mm=right,
                        endpoint_tangents=[ta.tolist(),tb.tolist()],controls_mm=controls.tolist(),
                        source_path_changed=False,handles_mm=[left_handle,right_handle],
                        reference_policy='ORDERED_ADMITTED_RING; EXCLUDE_TRANSVERSE_STEP_AND_REVERSED_PROGRESSION'),domain
                    return
