from src.component_distance import distance as exact_distance
"""Additive local inclusive fills for growth-created holes and narrow notches.

This source-owner completion runs inside the owning growth stage. Source-component
identity, source voids, inherited notches and every foreign surface are protected.
T02's connected span and <=20% shortage rules also govern each local fill.
"""
from dataclasses import dataclass, asdict
import hashlib, math
from shapely import STRtree, normalize, to_wkb, set_precision, union_all
from shapely.geometry import Polygon, box


@dataclass(frozen=True)
class RemedyContract:
    hard_gap_mm: float = .040
    construction_gap_mm: float = .0401
    notch_radius_mm: float = .040
    maximum_notch_radius_mm: float = .320
    maximum_shortage: float = .20
    local_reach_factor: float = 1.
    minimum_notch_boundary_support: float = .5
    grid_mm: float = .000001
    file_uncertainty_mm: float = .000002
    area_epsilon_mm2: float = 1e-12

    def validate(self):
        values=asdict(self)
        if any(type(v) not in (float,int) or not math.isfinite(v) or v<=0 for v in values.values()):
            raise ValueError('INVALID_REMEDY_CONTRACT')
        if self.construction_gap_mm<self.hard_gap_mm or self.maximum_shortage>.20 or self.local_reach_factor>1 or self.grid_mm>self.file_uncertainty_mm or self.notch_radius_mm>self.maximum_notch_radius_mm or not .5<=self.minimum_notch_boundary_support<=1:
            raise ValueError('REMEDY_POLICY_OUT_OF_BOUND')
        if self.grid_mm!=.000001 or self.file_uncertainty_mm!=.000002 or self.area_epsilon_mm2!=1e-12:
            raise ValueError('REMEDY_FILE_POLICY_CHANGED')


def sha(g):return hashlib.sha256(to_wkb(normalize(g))).hexdigest()
def parts(g):
    if g.is_empty:return []
    if not g.is_valid or g.geom_type not in ('Polygon','MultiPolygon'):
        raise ValueError('VALID_POLYGONAL_COPPER_REQUIRED')
    if g.geom_type=='Polygon':return [g]
    return sorted(list(g.geoms),key=sha)
def surface_parts(g):
    """Areal candidate context; clipped zero-area boundaries are not copper."""
    if g.is_empty:return []
    if not g.is_valid:raise ValueError('INVALID_CANDIDATE_CONTEXT')
    if g.geom_type in ('Polygon','MultiPolygon'):return parts(g)
    if g.geom_type=='GeometryCollection':
        return sorted([p for child in g.geoms for p in surface_parts(child)],key=sha)
    if g.geom_type in ('Point','MultiPoint','LineString','LinearRing','MultiLineString') and g.area==0:return []
    raise ValueError('UNSUPPORTED_CANDIDATE_CONTEXT')

def _overlay_diagnostic(legacy,result):
    # This alternate union is never candidate material. Count every positive
    # surface using the existing areal-context rule; zero-area points/lines
    # produced by overlay are not additional copper components. Invalid
    # geometries and unsupported semantics still raise in surface_parts.
    surfaces=surface_parts(legacy)
    report=dict(legacy_global_overlay_components=len(surfaces),global_overlay_symmetric_difference_mm2=legacy.symmetric_difference(result).area)
    if legacy.geom_type=='GeometryCollection':
        report['legacy_global_overlay_representation']=dict(status='DIAGNOSTIC_AREAL_CONTEXT',raw_type=legacy.geom_type,raw_sha256=sha(legacy),areal_components=len(surfaces),basis='All positive surfaces retained; only supported zero-area points/lines excluded from diagnostic copper-component count. Checked owner material unchanged.')
    return report

def empty():return Polygon()
def joined(shapes):return union_all(shapes) if shapes else empty()
def holes(g):return [Polygon(r) for p in parts(g) for r in p.interiors]


def components(source,current,contract):
    originals=parts(source);grown=parts(current);tree=STRtree(originals);mapping=[]
    if source.difference(current).area>contract.area_epsilon_mm2:
        raise ValueError('PREDECESSOR_SOURCE_COPPER_REMOVED')
    for part in grown:
        hits=[int(j) for j in tree.query(part) if originals[int(j)].intersection(part).area>0]
        if len(hits)!=1:raise ValueError('SOURCE_COMPONENT_MERGED_OR_UNBOUND')
        mapping.append(hits[0])
    if len(mapping)!=len(originals) or len(set(mapping))!=len(mapping):
        raise ValueError('SOURCE_COMPONENT_SPLIT_OR_MISSING')
    return originals,grown,mapping


def _close(shape,radius,contract):
    # Circular offset approximation error below 1/8 of existing file uncertainty.
    angle=math.acos(max(-1.,1-contract.file_uncertainty_mm/(8*radius)))
    steps=max(16,math.ceil(math.pi/(4*angle)))
    # Construction context uses the existing native file grid only; raw source
    # geometry and every proposal/foreign guard remain unchanged.
    native=set_precision(shape,contract.grid_mm,mode='valid_output')
    return native.buffer(radius,quad_segs=steps).buffer(-radius,quad_segs=steps)


def proposal_check(patch,owner,original,foreign,contract,kind="hole",source_void=None,owner_void_context=None,assembly_out=None):
    reasons=[];reach=max(patch.bounds[2]-patch.bounds[0],patch.bounds[3]-patch.bounds[1])*contract.local_reach_factor
    cap=box(*patch.bounds).buffer(reach,join_style=2)
    span=owner.intersection(cap)
    # Ignore unrelated branches clipped into the window; a single connected
    # support must cover the COMPLETE new patch boundary, not just one endpoint.
    clipped=surface_parts(span)
    support=[g for g in clipped if (patch.boundary.difference(g.buffer(contract.file_uncertainty_mm)).length<=contract.file_uncertainty_mm if kind=='hole' else patch.boundary.intersection(g.buffer(contract.file_uncertainty_mm)).length>=contract.minimum_notch_boundary_support*patch.length)]
    if len(support)!=1:reasons.append('LOCAL_SPAN_NOT_ONE_CONNECTED_SURFACE');carrier=empty()
    else:carrier=support[0]
    envelope=carrier.union(patch);shortage=patch.difference(owner).area/envelope.area if envelope.area else 1.
    if shortage>contract.maximum_shortage:reasons.append('SHORTAGE_ABOVE_20_PERCENT')
    from src.hole_acceptance import required as holes_required
    source_void=(joined(holes(original)) if source_void is None else source_void) if holes_required() else empty()
    if patch.intersection(source_void).area>0:reasons.append('INHERITED_SOURCE_VOID')
    gaps=[]
    for index,g in foreign:
        distance=exact_distance(patch,g)
        if distance+1e-12<contract.construction_gap_mm:reasons.append('FOREIGN_CLEARANCE_FAILED')
        gaps.append(dict(component=index,gap_mm=distance))
    if not patch.is_valid or patch.is_empty:reasons.append('INVALID_FILL')
    assembled=owner.union(patch)
    if assembled.geom_type!='Polygon' or not assembled.is_valid:reasons.append('FILL_NOT_EXACTLY_CONNECTED')
    else:
        prior_holes,prior_index=(holes(owner),None) if owner_void_context is None else owner_void_context
        prior_index=STRtree(prior_holes) if prior_index is None else prior_index
        assembled_holes=holes(assembled)
        if assembly_out is not None:assembly_out.append((assembled,assembled_holes))
        for h in (assembled_holes if holes_required() else []):
            if any(h.intersection(prior_holes[int(k)]).area>contract.area_epsilon_mm2 for k in prior_index.query(h)):continue
            if not h.buffer(-contract.file_uncertainty_mm).is_empty:
                reasons.append('NEW_TRAPPED_VOID');break
    if patch.difference(cap).area>contract.area_epsilon_mm2:reasons.append('OUTSIDE_LOCAL_ENVELOPE')
    return dict(passed=not reasons,reasons=reasons,shortage=shortage,local_cap_bounds_mm=list(cap.bounds),connected_support_sha256=sha(carrier),foreign_gaps=gaps)


def foreign_bounded_pocket(parent,owner,original,foreign,contract,parent_check,protected,owner_void_context):
    """Complete a new pocket outside proven foreign-copper clearance envelopes."""
    if set(parent_check['reasons'])!={'FOREIGN_CLEARANCE_FAILED'}:return None
    reach=contract.construction_gap_mm+contract.file_uncertainty_mm
    window=parent.buffer(reach).envelope
    barriers=joined([g.buffer(reach,quad_segs=128)for _,g in foreign if g.intersects(window)])
    candidate=joined(surface_parts(parent.difference(barriers).difference(owner)))
    if candidate.is_empty:return None
    assembled=[]
    check=proposal_check(candidate,owner,original,foreign,contract,'notch',protected,owner_void_context,assembly_out=assembled)
    if check['passed']:
        for remaining in assembled[0][1]:
            if remaining.intersection(parent).area<=contract.area_epsilon_mm2:continue
            if any(remaining.intersection(g).area>0 for _,g in foreign):continue
            if not remaining.buffer(-contract.file_uncertainty_mm).is_empty:
                check['passed']=False;check['reasons'].append('NEW_UNPROTECTED_REMAINDER_AFTER_FOREIGN_CLIP');break
    check['complete_parent_pocket_check']=parent_check
    check['foreign_boundary_policy']='Complete parent support retained; only its frozen foreign clearance envelopes remain empty'
    return candidate,check,assembled


def plan(source,current,contract=RemedyContract(),checkpoint=lambda record:None,source_support=None,reserved=None,partial_strategy=None,approved_partials=None,clearance_only=None):
    contract.validate();originals,grown,mapping=components(source,current,contract)
    records=[];accepted=[];frozen=list(grown);tree=STRtree(grown);partial_specs=list(approved_partials or [])
    from src.partial_pocket_remedy import STRATEGY,propose,protected,corresponds
    if partial_strategy not in(None,STRATEGY):raise ValueError('PARTIAL_POCKET_POLICY_UNSUPPORTED')
    if partial_specs and partial_strategy!=STRATEGY:raise ValueError('PARTIAL_POCKET_POLICY_REQUIRED_FOR_FROZEN_OPENINGS')
    reserved={}if reserved is None else reserved
    reserve_ids=sorted(reserved);reserve_tree=STRtree([reserved[j]for j in reserve_ids])
    clearance_only={}if clearance_only is None else clearance_only
    checking_ids=sorted(clearance_only);checking_tree=STRtree([clearance_only[j]for j in checking_ids])
    from src.stage_abi.loaded_geometry import GeometryMemo
    memo=GeometryMemo(sha(source)+sha(current)+repr(contract))
    for index,(owner,j) in enumerate(zip(grown,mapping)):
        checkpoint(dict(component=index,total_components=len(grown),proposals_so_far=len(records),fills_so_far=len(accepted)))
        from src.hole_acceptance import required as holes_required
        original=originals[j];oldvoid=joined(holes(original))if holes_required()else empty();ownerholes=holes(owner)
        owner_void_context=(ownerholes,STRtree(ownerholes))
        context_owner=owner
        from src.component_hole_lineage import classify as hole_lineage
        lineage=hole_lineage(original,owner);keeper_ids=set(lineage['keeper_ids']);protected_source_voids=joined([h for h in ownerholes if sha(h)in keeper_ids])
        candidates=[]
        for hole in ownerholes:
            matching=[s for s in partial_specs if s['source_component']==j and corresponds(hole,s,contract)]
            if matching:
                if len(matching)!=1:raise ValueError('FROZEN_PARTIAL_OPENING_AMBIGUOUS')
                records.append(dict(kind='hole',owner=index,source_component=j,patch_sha256=sha(hole),area_mm2=hole.area,status='KEEP_APPROVED_PARTIAL_OPENING',pocket_id=matching[0]['pocket_id'],bounds_mm=list(hole.bounds)));continue
            owned_specs=[s for s in partial_specs if s['source_component']==j]
            if owned_specs and hole.intersection(protected(owned_specs)).area>contract.area_epsilon_mm2:raise ValueError('FROZEN_PARTIAL_OPENING_CHANGED')
            if not holes_required():
                records.append(dict(kind='hole',owner=index,source_component=j,patch_sha256=sha(hole),area_mm2=hole.area,status='KEEP_ACCEPTED_ORDINARY_HOLE',bounds_mm=list(hole.bounds)));continue
            if sha(hole)in keeper_ids:
                records.append(dict(kind='hole',owner=index,source_component=j,patch_sha256=sha(hole),area_mm2=hole.area,status='KEEP_SOURCE_VOID',bounds_mm=list(hole.bounds)))
            else:candidates.append(('hole',hole))
        if not owner.equals(original):
            # Closing at radius r depends only on inputs within 2r. Cover all
            # changed copper by safe windows padded 2r; each context has a
            # further 2r halo. Frozen windows are processed once and deduplicated.
            delta=owner.difference(original);r=contract.notch_radius_mm
            boxes=[]
            for d in surface_parts(delta):
                x,y,x1,y1=d.bounds;boxes.append(box(x-2*r,y-2*r,x1+2*r,y1+2*r))
            newpieces=[];oldpieces=[];current_void=joined(ownerholes)
            for window in parts(joined(boxes)):
                x,y,x1,y1=window.bounds;context=box(x-2*r,y-2*r,x1+2*r,y1+2*r)
                previous=_close(original.intersection(context),r,contract)
                closed=_close(owner.intersection(context),r,contract).buffer(-contract.file_uncertainty_mm,quad_segs=16)
                newly_trapped=[h for h in holes(closed) if h.intersection(current_void).area<=contract.area_epsilon_mm2]
                closed=closed.union(joined(newly_trapped))
                newpieces.append(closed.difference(owner).intersection(window))
                oldpieces.append(previous.difference(original).intersection(window))
            new=joined(newpieces).difference(oldvoid).difference(current_void)
            inherited_notches=joined(oldpieces).buffer(contract.file_uncertainty_mm,quad_segs=16)
            for patch in surface_parts(new):
                if patch.area<=contract.area_epsilon_mm2 or patch.buffer(-contract.file_uncertainty_mm).is_empty:continue
                if patch.difference(inherited_notches).area<=contract.area_epsilon_mm2:continue
                candidates.append(('notch',patch))
        for kind,patch in sorted(candidates,key=lambda x:(x[0],sha(x[1]))):
            tree=STRtree(frozen)
            owner=frozen[index]
            nearby=[(int(k),frozen[int(k)])for k in tree.query(patch.buffer(contract.construction_gap_mm+contract.file_uncertainty_mm+.001))if int(k)!=index]
            nearby.extend(('reserved:'+str(reserve_ids[int(k)]),reserved[reserve_ids[int(k)]])for k in reserve_tree.query(patch.buffer(contract.construction_gap_mm+contract.file_uncertainty_mm+.001))if reserve_ids[int(k)]!=j)
            raw_patch=patch
            checking=[('checking-envelope:'+str(checking_ids[int(k)]),clearance_only[checking_ids[int(k)]])for k in checking_tree.query(raw_patch.buffer(contract.construction_gap_mm+contract.file_uncertainty_mm+.001))if checking_ids[int(k)]!=j]
            if any(exact_distance(raw_patch,g)+1e-12<contract.construction_gap_mm for _,g in checking):
                records.append(dict(kind=kind,owner=index,source_component=j,patch_sha256=sha(raw_patch),area_mm2=raw_patch.area,bounds_mm=list(raw_patch.bounds),status='KEEP_ENTIRE_FILL_CHECKING_ENVELOPE',check=dict(passed=False,reasons=['T04_CHECKING_ENVELOPE_CLEARANCE'],role='CLEARANCE_ONLY_NOT_COPPER_NOT_MINIMUM_FLOOR')))
                continue
            nearby.extend(checking)
            from src.growth_remedy_constraints import remedy as pin_remedy
            pin_check=pin_remedy(raw_patch,owner)
            if pin_check is not None and not pin_check['passed']:
                records.append(dict(kind=kind,owner=index,source_component=j,patch_sha256=sha(raw_patch),area_mm2=raw_patch.area,bounds_mm=list(raw_patch.bounds),status='KEEP_PROTECTED_PIN_SEPARATION',check=pin_check))
                continue
            if kind=='notch':
                buffered=[memo.buffer(g,contract.construction_gap_mm+contract.file_uncertainty_mm,quad_segs=128)for _,g in nearby]
                barriers=memo.construct('ordered-foreign-barrier-union',buffered,(),lambda:joined(buffered))
                patch=joined(surface_parts(patch.difference(barriers).difference(owner)))
                if partial_specs:patch=joined(surface_parts(patch.difference(protected(partial_specs))))
                if patch.is_empty:
                    records.append(dict(kind=kind,owner=index,source_component=j,patch_sha256=sha(raw_patch),area_mm2=raw_patch.area,bounds_mm=list(raw_patch.bounds),status='KEEP_FOREIGN_CLEARANCE',check=dict(passed=False,reasons=['FROZEN_FOREIGN_COMPONENT_CLEARANCE'])))
                    continue
            if owner is not context_owner:
                ownerholes=holes(owner);owner_void_context=(ownerholes,STRtree(ownerholes));context_owner=owner
            assembled_result=[]
            check=proposal_check(patch,owner,original,nearby,contract,kind,protected_source_voids if kind=='hole'else oldvoid,owner_void_context,assembly_out=assembled_result)
            if kind=='hole':
                pocket_lineage=dict(candidate_sha256=sha(patch),source_ancestors=lineage['ancestry'].get(sha(patch),[]),principal_surviving_source_holes=lineage['keeper_ids'])
                bounded=foreign_bounded_pocket(patch,owner,original,nearby,contract,check,protected_source_voids,owner_void_context)
                if bounded is not None:
                    records.append(dict(kind='hole',owner=index,source_component=j,patch_sha256=sha(patch),area_mm2=patch.area,bounds_mm=list(patch.bounds),status='KEEP_BLOCKED_FULL_POCKET',check=dict(check,source_hole_lineage=pocket_lineage)))
                    patch,check,assembled_result=bounded;kind='foreign_bounded_pocket'
                check['source_hole_lineage']=pocket_lineage
            if partial_strategy==STRATEGY and kind=='hole'and check['reasons']==['SHORTAGE_ABOVE_20_PERCENT']:
                patch,check,spec=propose(patch,owner,contract,check,mandatory=reserved.get(j));spec.update(owner=index,source_component=j);partial_specs.append(spec);kind='partial_rim'
            support_check=None
            if support_check is not None and kind=='notch' and not support_check['passed']:
                check['reasons'].append('OUTSIDE_ORIGINAL_CONTACT_SUPPORT');check['passed']=False
            check['source_contact_support']=dict(applicable=False,status='NOT_APPLICABLE_INTERNAL_ORIGINAL_COMPONENT',basis='Frozen original connected copper; complete local boundary support remains mandatory')
            row=dict(kind=kind,owner=index,source_component=j,patch_sha256=sha(patch),area_mm2=patch.area,bounds_mm=list(patch.bounds),status='FILL' if check['passed'] else 'KEEP_BLOCKED',check=check)
            records.append(row)
            if check['passed']:
                accepted.append(dict(owner=index,source_component=j,kind=kind,geometry=patch,record_sha256=sha(patch)))
                if kind=='partial_rim':
                    frozen[index]=owner.union(patch);ownerholes=holes(frozen[index])
                else:frozen[index],ownerholes=assembled_result[0]
                context_owner=frozen[index];owner_void_context=(ownerholes,STRtree(ownerholes))
    # Frozen proposals, one pass. Complete simultaneous cross-component proof.
    for i,a in enumerate(accepted):
        for b in accepted[:i]:
            if a['owner']!=b['owner'] and exact_distance(a['geometry'],b['geometry'])+1e-12<contract.construction_gap_mm:
                raise ValueError('SIMULTANEOUS_FILL_CLEARANCE_FAILED')
    fills=joined([r['geometry'] for r in accepted]);legacy=current.union(fills);result=joined(frozen)
    newparts=parts(result)
    if len(newparts)!=len(grown):raise ValueError('FILL_COMPONENT_TOPOLOGY_CHANGED:'+str(dict(before=len(grown),checked_owner_assembly=len(newparts),legacy_global_overlay=len(surface_parts(legacy)))))
    components(source,result,contract)
    if current.difference(result).area>contract.area_epsilon_mm2:raise ValueError('FILL_REMOVED_PREDECESSOR')
    memo.close()
    report=dict(contract=asdict(contract),source_sha256=sha(source),predecessor_sha256=sha(current),records=records,fill_sha256=sha(fills),result_sha256=sha(result),assembly=dict(policy='Union the already individually checked original-owner bodies',components_before=len(grown),checked_owner_components=len(newparts),**_overlay_diagnostic(legacy,result)))
    if partial_strategy is not None:report.update(large_pocket_strategy=partial_strategy,approved_partial_pockets=partial_specs)
    return report,accepted,result
