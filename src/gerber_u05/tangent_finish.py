"""Subtractive tangent finishing of native route shoulders.

Reuse the rolling-disc treatment on each face independently. A deep interior
backing prevents a narrow trace from disappearing during opening. Only shallow
protrusions in the native joint window can be removed. Fixed group interiors,
nominal source cores and covered occurrences are immutable supports. Clearance
cannot decrease by removing copper; route connectivity is checked by assembly.
"""
from collections import defaultdict
from time import perf_counter
import numpy as np
from shapely.geometry import LineString,Point,Polygon
from shapely.ops import unary_union
from shapely import to_wkb
from .arc_membership import tangent
from .corner_transition import oriented,new_pocket_regions
from .finite_profile_union import polygonal,certified_union,difference_for_window
from .limiting_math import MARGIN
from src.native_inventory import ERROR_MM
from src.stage_abi.store import digest
from src.component_voids import parts,holes
from src.original_copper_owners import OriginalOwners


def trim_wider_ends(rows,paths,bodies,descriptors,*,covered=(),source_cores=None,sites=None):
    """Existing tangent cutter with optional wider shoulders released.

    Only nominal source cores and covered copper are fixed in the native end
    window. The old larger width is not an admission predicate. The mask is
    applied to every same-route alias, including shared maximal arc bodies;
    raw catalogue/group operands remain immutable construction evidence.
    """
    from .corner_transition import corners
    from shapely.errors import GEOSException
    started=perf_counter();covered=set(covered);working=dict(bodies);nodes=defaultdict(list)
    reports=[];cuts={};targets=[];subtraction_methods={};protected_by_route={}
    for route,sources in sorted(paths.items()):
        for s in sources:
            if s not in descriptors:continue
            pts=rows[s]['metadata']['route_points_mm']
            for end,pt in enumerate((pts[0],pts[-1])):
                key=route,tuple(round(v,10)for v in pt)
                if sites is not None and key not in sites:continue
                if descriptors[s].get('real_endpoints',[True,True])[end]:nodes[key].append((s,end))
    def subtract(s,mask):
        candidate=polygonal(working[s].difference(mask));method='DIFFERENCE'
        if not bodies[s].covers(candidate):
            for left,right in ((candidate,bodies[s]),(bodies[s],candidate)):
                clipped=polygonal(left.intersection(right))
                if bodies[s].covers(clipped):candidate=clipped;method='DIFFERENCE_THEN_ORIGINAL_INTERSECTION';break
        if not bodies[s].covers(candidate):raise ValueError('TRIM_SUBTRACTION_NOT_CONTAINED_IN_ORIGINAL')
        subtraction_methods[s]=method
        return candidate
    for (route,pt),ends in sorted(nodes.items()):
        if len(ends)!=2:continue
        (a,ae),(b,be)=ends
        if descriptors[a].get('member_id')is not None and descriptors[a].get('member_id')==descriptors[b].get('member_id'):continue
        sources=paths[route]
        if route not in protected_by_route:
            nominal=[(source_cores or {}).get(s,LineString(descriptors[s]['points']).buffer(descriptors[s]['source_width_mm']/2+MARGIN,quad_segs=128))for s in sources if s in descriptors]
            protected_by_route[route]=polygonal(unary_union([*nominal,*[bodies[s]for s in sources if s in covered]]))
        protected=protected_by_route[route]
        support=polygonal(unary_union([working[s]for s,_ in ends]))
        widths={s:float(np.linalg.norm(np.subtract(*corners(dict(descriptors[s],support=working[s]),end)[0])))for s,end in ends}
        narrow,ne=min(ends,key=lambda v:(widths[v[0]],v[0]));u=tangent(oriented(descriptors[narrow],ne),False)
        window=Point(pt).buffer(max(.04,max(descriptors[s]['source_width_mm']for s,_ in ends)),quad_segs=64)
        record=dict(route_id=route,endpoint_mm=list(pt),continuation_source_id=narrow,attempts=[])
        try:
            mask=face_cut(support,pt,u,window,protected)
            if mask.is_empty:record['status']='NO_TANGENT_PROTRUSION';reports.append(record);continue
            before=polygonal(unary_union([working[s]for s in sources]))
            changed={s:subtract(s,mask)for s in sources if s not in covered and working[s].intersects(mask)}
            after=polygonal(unary_union([changed.get(s,working[s])for s in sources]))
            # Reuse the optional-tip treatment, including point-attached
            # teeth. Never remove pre-existing islands or nominal material.
            prior=parts(before);attached=unary_union([g for g in prior if g.intersection(protected).area>ERROR_MM**2])
            tips=[g for g in parts(after)if g.intersection(protected).area<=ERROR_MM**2 and g.intersects(attached)]
            if tips and all(g.area<=.005**2 and window.buffer(ERROR_MM).covers(g)for g in tips):
                mask=polygonal(unary_union([mask,unary_union(tips).buffer(2*ERROR_MM,quad_segs=32).difference(protected)]))
                changed={s:subtract(s,mask)for s in sources if s not in covered and working[s].intersects(mask)}
                after=polygonal(unary_union([changed.get(s,working[s])for s in sources]))
            pockets=new_pocket_regions(before,after)
            passed=len(parts(after))<=len(parts(before))and len(OriginalOwners(after).owners)<=len(OriginalOwners(before).owners)and not pockets
            record.update(status='TRIMMED'if passed else'KEEP_ROUTE; CONNECTION_OR_POCKET_LIMIT',new_pockets=len(pockets),
                components_before=len(OriginalOwners(before).owners),components_after=len(OriginalOwners(after).owners))
            if passed:
                for s,g in changed.items():cuts[s]=polygonal(unary_union([cuts.get(s,Polygon()),mask]));working[s]=g
                target=dict(route_id=route,endpoint_mm=list(pt),continuation_source_id=narrow,
                    policy='EXISTING_FACE_TANGENT_OPENING; NO_OLD_LARGER_WIDTH_OBLIGATION',radius_mm=.05,maximum_depth_mm=.005)
                targets.append(target)
                record.update(removed_area_mm2=before.difference(after).area,cut_sha256=digest(to_wkb(mask)),cut_wkb_hex=to_wkb(mask).hex(),
                    detached_optional_tips_removed=len(tips))
        except (GEOSException,ValueError)as error:
            record.update(status='KEEP_ROUTE; NUMERICAL_CONSTRUCTION_LIMIT',error=repr(error))
        reports.append(record)
    return working,cuts,dict(schema='t04-wider-end-subtractive-transition/1',reports=reports,targets=targets,
        trimmed_joints=sum(r['status']=='TRIMMED'for r in reports),wall_s=perf_counter()-started,
        old_larger_endpoint_is_target=False,wider_shoulder_is_fixed=False,
        nominal_cores_protected=True,covered_copper_protected=True,group_interiors_outside_transition_unchanged=True,
        subtraction_methods=subtraction_methods,constructed_groups_audited=0)


def face_cut(support,center,u,window,protected,*,radius=.05,maximum_depth=.005):
    """Two face-wise tangent openings, preserving the entire nominal carrier."""
    center=np.asarray(center);u=np.asarray(u);u=u/np.linalg.norm(u);n=np.array([-u[1],u[0]])
    prep=window.buffer(3*radius);scale=max(prep.bounds[2]-prep.bounds[0],prep.bounds[3]-prep.bounds[1])+4*radius
    cuts=[]
    for sign in (-1,1):
        normal=n*sign
        # Artificial backing lies inside this face. It is only a construction
        # operand and never emitted as copper or used as an attachment.
        backing=Polygon([center+u*x+normal*y for x,y in[(-scale,-scale),(scale,-scale),(scale,0),(-scale,0)]])
        padded=unary_union([support.intersection(prep),backing])
        opened=padded.buffer(-radius,quad_segs=64).buffer(radius,quad_segs=64)
        cut=polygonal(difference_for_window(support,opened,window).intersection(window).difference(protected))
        # Deep shape changes and thinning are outside a finishing operation.
        skin=difference_for_window(support,support.buffer(-maximum_depth,quad_segs=64),window)
        cut=polygonal(cut.intersection(skin))
        # Ignore overlay slivers below the source kernel's reliable depth.
        # They can otherwise mint tiny disconnected faces and trigger a slow
        # mixed-dimension distance fallback in the functional check.
        cuts.extend(g for g in parts(cut)if g.area>ERROR_MM**2 and not g.buffer(-2*ERROR_MM).is_empty)
    return polygonal(unary_union(cuts))


def run(rows,paths,bodies,descriptors,fixed_groups,*,covered=(),source_cores=None):
    started=perf_counter();covered=set(covered);nodes=defaultdict(list);cuts={};reports=[]
    for route,sources in sorted(paths.items()):
        for s in sources:
            if s in covered or s not in descriptors:continue
            pts=rows[s]['metadata']['route_points_mm']
            for end,pt in enumerate((pts[0],pts[-1])):
                if descriptors[s].get('real_endpoints',[True,True])[end]:nodes[route,tuple(round(v,10)for v in pt)].append((s,end))
    for (route,pt),ends in sorted(nodes.items()):
        if len(ends)!=2:continue
        (a,ae),(b,be)=ends
        if descriptors[a].get('member_id')is not None and descriptors[a].get('member_id')==descriptors[b].get('member_id'):continue
        ta=tangent(oriented(descriptors[a],ae),False);tb=tangent(oriented(descriptors[b],be),False);u=ta-tb
        if np.linalg.norm(u)<1e-12:continue
        u/=np.linalg.norm(u)
        support=polygonal(unary_union([bodies[s].difference(cuts[s])if s in cuts else bodies[s]for s in(a,b)]))
        width=max(descriptors[s]['source_width_mm']for s,_ in ends)
        window=Point(pt).buffer(max(.04,width),quad_segs=64)
        nominal=unary_union([LineString(descriptors[s]['points']).buffer(descriptors[s]['source_width_mm']/2+MARGIN,quad_segs=128)for s,_ in ends])
        protected=unary_union([nominal,*[descriptors[s].get('support',Polygon())for s,_ in ends],
            *[(source_cores or {}).get(s,Polygon())for s,_ in ends],*[g for ss,g in fixed_groups if a in ss or b in ss]])
        cut=face_cut(support,pt,u,window,protected)
        if cut.is_empty:continue
        # An opening can leave a detached optional tooth tip. Remove that tip
        # in the same shallow window, or keep this joint unchanged if a fixed
        # support would be separated. Never publish a new copper island.
        candidate=polygonal(support.difference(cut));components=parts(candidate)
        detached=[g for g in components if g.intersection(protected).area<=ERROR_MM**2]
        if any(g.area>.005**2 or not window.buffer(ERROR_MM).covers(g)for g in detached):continue
        if detached:cut=polygonal(unary_union([cut,*detached]));candidate=polygonal(support.difference(cut))
        if len(parts(candidate))>len(parts(support)):continue
        old_holes=unary_union(holes(support));new_holes=unary_union(holes(candidate)).difference(old_holes)
        if new_holes.area>ERROR_MM**2:continue
        # Apply one mask to both adjacent source operands and all their joint
        # additions. Otherwise a redundant operand would restore the bump.
        for s,_ in ends:cuts[s]=polygonal(unary_union([cuts.get(s,Polygon()),cut]))
        reports.append(dict(route_id=route,endpoint_mm=list(pt),source_ids=[a,b],removed_area_mm2=cut.area,
            cut_sha256=digest(to_wkb(cut)),maximum_depth_mm=.005,radius_mm=.05,
            policy='SUBTRACTIVE_TANGENT_OPENING; NOMINAL_CORE_AND_GROUP_INTERIOR_PROTECTED',constructed_groups_audited=0))
    return cuts,dict(schema='t04-native-joint-tangent-finish/1',reports=reports,wall_s=perf_counter()-started,
        trimmed_joints=len(reports),removed_area_sum_mm2=sum(v['removed_area_mm2']for v in reports),constructed_groups_audited=0)


def materialize(patches,cuts,floors):
    """Remove newly detached optional tips after overlapping trims combine.

    Local face cuts can overlap on a short source. Their aggregate must retain
    attachment to the unchanged native-route floor. This is a joint-constructor
    topology condition, not a clearance audit of constructed group copper.
    """
    started=perf_counter();finished=list(patches);reports=[]
    for route,floor in sorted(floors.items()):
        indices=[i for i,p in enumerate(patches)if p['route_id']==route]
        if not indices or not any(patches[i]['source_id']in cuts for i in indices):continue
        before=polygonal(unary_union([floor,*[patches[i]['geometry']for i in indices]]))
        for i in indices:
            p=patches[i]
            if p['source_id']in cuts:finished[i]=dict(p,geometry=polygonal(p['geometry'].difference(cuts[p['source_id']])))
        after=polygonal(unary_union([floor,*[finished[i]['geometry']for i in indices]]))
        prior_components=OriginalOwners(before).owners;before_count=len(prior_components);components=OriginalOwners(after).owners
        previously_attached=unary_union([g for g in prior_components if g.intersects(floor)])
        detached=[g for g in components if g.intersection(floor).is_empty and g.intersects(previously_attached)]
        removed=Polygon()
        if detached and all(g.area<=.005**2 for g in detached):
            # Every surviving positive face is accounted for. The mask acts
            # only on joint additions, including their redundant overlaps;
            # no tiny fragment is silently ignored by the connection counter.
            removed=unary_union(detached).buffer(2*ERROR_MM,quad_segs=32)
            for i in indices:finished[i]=dict(finished[i],geometry=polygonal(finished[i]['geometry'].difference(removed)))
            after=polygonal(unary_union([floor,*[finished[i]['geometry']for i in indices]]))
        pockets=new_pocket_regions(before,after)
        if pockets:
            restore=unary_union(pockets).buffer(2*ERROR_MM,quad_segs=32)
            for i in indices:
                # Restore only copper from that exact original joint operand.
                # No old void or newly invented clearance claim is filled.
                addition=polygonal(patches[i]['geometry'].intersection(restore))
                retained=finished[i]['geometry']
                finished[i]=dict(finished[i],geometry=addition if retained.is_empty else certified_union(retained,addition)[0])
            after=polygonal(unary_union([floor,*[finished[i]['geometry']for i in indices]]))
        passed=len(OriginalOwners(after).owners)<=before_count and not new_pocket_regions(before,after)
        if not passed:
            for i in indices:finished[i]=patches[i]
        reports.append(dict(route_id=route,status='FINISHED'if passed else'KEEP_ORIGINAL_JOINTS; SUPPORT_ATTACHMENT_LIMIT',
            detached_optional_tips_removed=len(detached)if passed else 0,removed_optional_tip_area_mm2=sum(g.area for g in detached)if passed else 0.,
            new_trim_pockets_restored=len(pockets)if passed else 0,restored_from_original_joint_operands_only=True,
            frozen_floor_changed=False,constructed_groups_audited=0))
    return finished,dict(reports=reports,wall_s=perf_counter()-started,
        support_limited_routes=[r['route_id']for r in reports if r['status']!='FINISHED'],
        detached_optional_tips_removed=sum(r['detached_optional_tips_removed']for r in reports),constructed_groups_audited=0)
