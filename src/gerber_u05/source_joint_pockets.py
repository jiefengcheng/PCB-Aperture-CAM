"""Complete newly enclosed joint voids against the original source baseline."""
from shapely import to_wkb
from shapely.geometry import Point,LineString
from shapely.ops import unary_union
from .corner_transition import new_pocket_regions
from .finite_profile_union import polygonal
from .source_trace_floor import preserve
from .normalized_additions import verify_patch
from src.bulk_edge_restore import topology
from src.native_inventory import ERROR_MM
from src.stage_abi.store import digest


def complete(rows,original,current,paths,patches,owner,*,covered=(),protected_domains=(),copper=None,baseline_revision=None):
    from src.shared_copper_context import ACTIVE,for_board
    shared=copper or ACTIVE.get()
    if shared is not None:
        return _complete(rows,original,current,paths,patches,owner,covered=covered,protected_domains=protected_domains,copper=shared,baseline_revision=baseline_revision)
    with for_board(original) as shared:
        return _complete(rows,original,current,paths,patches,owner,covered=covered,protected_domains=protected_domains,copper=shared,baseline_revision=baseline_revision)


def _complete(rows,original,current,paths,patches,owner,*,covered,protected_domains,copper,baseline_revision=None):
    """Keep input groups fixed; add only internal voids within admitted caps.

    The source baseline precedes arc/default construction. Comparing only the
    later corner floor misses pockets already enclosed by those earlier skins.
    Entire old source holes and voids outside native joint windows stay intact.
    """
    from src.shared_copper_context import geometry_key
    baseline=copper.source if baseline_revision is None else baseline_revision
    if baseline.context is not copper or tuple(original)!=tuple(baseline.values) or any(geometry_key(g)!=geometry_key(baseline.values[s]) for s,g in original.items()):
        raise ValueError('JOINT_CLEANUP_SHARED_SOURCE_MISMATCH')
    # This is an unaccepted validation candidate. Query exact source overlays
    # without persisting duplicate full-board owner/delta snapshots. The final
    # material/contact/topology checks below still run on the assembled image.
    revision=copper.query_view(current)
    before=baseline.image();image=polygonal(unary_union(list(current.values())))
    copper.stats['joint_candidate_validation_unions']+=1
    working=dict(current);output=[];records=[];outside=0;covered=set(covered);staged=[]
    holes=new_pocket_regions(before,image)
    neighbours=[revision.sources(h.envelope.buffer(.05)) for h in holes]
    for hole,near_sources in zip(holes,neighbours):
        near=[]
        for patch in patches:
            recipe=patch.get('recipe',{});radius=recipe.get('input_face_envelope_radius_mm')
            if radius is None or not 0<radius<=.2:continue
            if not Point(patch['endpoint_mm']).buffer(radius+.11,quad_segs=128).covers(hole):continue
            near.append(patch)
        if not near:outside+=1;continue
        caps=[]
        for patch in near:
            recipe=patch['recipe'];sources=recipe.get('joint_receiver_source_ids',[])
            point=tuple(patch['endpoint_mm'])
            if not sources:
                sources=[s for s in paths[patch['route_id']] if point in
                         (tuple(rows[s]['metadata']['route_points_mm'][0]),
                          tuple(rows[s]['metadata']['route_points_mm'][-1]))]
            caps.extend(LineString(rows[s]['metadata']['route_points_mm']).buffer(
                        recipe['input_face_envelope_radius_mm']+ERROR_MM,quad_segs=128)for s in sources)
        cap=polygonal(unary_union(caps));record=dict(pocket_sha256=digest(to_wkb(hole)),area_mm2=hole.area,
            bounds_mm=list(hole.bounds),status='KEEP_UNQUALIFIED')
        if not hole.difference(cap).is_empty:
            record['reason']='OUTSIDE_ADMITTED_JOINT_CAPS';records.append(record);continue
        route=near[0]['route_id'];own=owner(near[0]['source_id'])
        carriers=[s for s in paths[route] if s not in covered and owner(s)==own
                  and working[s].distance(hole)<=2*ERROR_MM]
        if not carriers:
            record['reason']='COVERED_SOURCE_FIXED';records.append(record);continue
        # Store a local joint addition on a local native occurrence. Replacing
        # a distant, shared long-member contour needlessly recomputes unrelated
        # coincident boundaries during serialization.
        target=min(carriers,key=lambda s:(working[s].envelope.area,working[s].area,s))
        fixed=[dict(id=s,geometry=current[s])for s in near_sources
               if owner(s)!=own and current[s].distance(hole)<.05]
        check=verify_patch(hole,fixed)
        if not check['passed'] or any(hole.intersects(g)for g in protected_domains):
            record.update(reason='CLEARANCE_OR_PROTECTED_DOMAIN',check=check);records.append(record);continue
        backing=polygonal(unary_union([hole,image.intersection(hole.buffer(2*ERROR_MM,quad_segs=128))]))
        body=polygonal(unary_union([working[target],backing]))
        body,floor_proof=preserve(working[target],body)
        method='UNARY_UNION; NATIVE_AREA_AND_COORDINATE_FLOOR_PROOF'
        # Check the local carrier now; assemble the complete board only once
        # after all independently bounded joint additions have been staged.
        added=polygonal(body.difference(working[target]).difference(image))
        lost=polygonal(working[target].difference(body))
        record['material_checks']=dict(original_loss_mm2=lost.area,
            positive_delta_mismatch_mm2=added.symmetric_difference(hole).area,
            carrier_source_id=target)
        if lost.area>1e-12 or added.symmetric_difference(hole).area>1e-12:
            record['reason']='MATERIAL_OR_ATTACHMENT_MISMATCH';records.append(record);continue
        working[target]=body;staged.append(hole)
        recipe=dict(schema='t04-original-baseline-joint-pocket/1',
            input_face_envelope_radius_mm=max(p['recipe']['input_face_envelope_radius_mm']for p in near),
            source_void_policy='NEW_ENCLOSURES_ONLY; ORIGINAL_SOURCE_BASELINE',
            native_outer_width_unchanged=True,source_path_changed=False,group_copper_changed=False,
            geometry_audit=False,assembly_overlap_mm=2*ERROR_MM)
        output.append(dict(source_id=target,route_id=near[0]['route_id'],endpoint_mm=near[0]['endpoint_mm'],
                           geometry=backing,recipe=recipe,side='SOURCE_BASELINE_JOINT_POCKET'))
        record.update(status='FILLED',source_id=target,check=check,union_method=method,
                      retained_floor=floor_proof,
                      actual_added_mm2=added.area,original_source_copper_removed_mm2=lost.area)
        records.append(record)
    if staged:
        candidate=polygonal(unary_union(list(working.values())))
        copper.stats['joint_batch_board_unions']+=1
        added=polygonal(candidate.difference(image));lost=polygonal(image.difference(candidate))
        wanted=polygonal(unary_union(staged))
        if lost.area>1e-12 or topology(candidate)[0]!=topology(image)[0] or added.symmetric_difference(wanted).area>1e-12:
            raise ValueError('JOINT_BATCH_MATERIAL_OR_ATTACHMENT_MISMATCH')
        for record in records:
            if record['status']=='FILLED':
                record['material_checks'].update(components_before=topology(image)[0],components_after=topology(candidate)[0])
    return working,output,dict(schema='t04-source-baseline-joint-pockets/1',
        passed=all(r['status']=='FILLED' for r in records),records=records,
        filled=sum(r['status']=='FILLED' for r in records),
        voids_outside_joint_qualification=outside,original_holes_preserved=True,
        constructed_group_bytes_changed=False)
