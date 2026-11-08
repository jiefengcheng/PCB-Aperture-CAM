"""Additive local inclusive fills for growth-created holes and narrow notches.

This is a separate stage after the unchanged growth stages. Source-component
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
        if self.construction_gap_mm<self.hard_gap_mm or self.maximum_shortage>.20 or self.local_reach_factor>1 or self.grid_mm>self.file_uncertainty_mm or self.notch_radius_mm>self.hard_gap_mm or not .5<=self.minimum_notch_boundary_support<=1:
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

def empty():return Polygon()
def joined(shapes):return union_all(shapes) if shapes else empty()
def holes(g):return [Polygon(r) for p in parts(g) for r in p.interiors]


def components(source,current,contract):
    originals=parts(source);grown=parts(current);tree=STRtree(originals);mapping=[]
    if source.difference(current).area>contract.area_epsilon_mm2:
        raise ValueError('PREDECESSOR_SOURCE_COPPER_REMOVED')
    for part in grown:
        hits=[int(j) for j in tree.query(part) if originals[int(j)].intersection(part).area>contract.area_epsilon_mm2]
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


def proposal_check(patch,owner,original,foreign,contract,kind="hole",source_void=None,owner_void_context=None):
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
    if patch.intersection(source_void).area>contract.area_epsilon_mm2:reasons.append('INHERITED_SOURCE_VOID')
    gaps=[]
    for index,g in foreign:
        distance=patch.distance(g)
        if distance+1e-12<contract.construction_gap_mm:reasons.append('FOREIGN_CLEARANCE_FAILED')
        gaps.append(dict(component=index,gap_mm=distance))
    if not patch.is_valid or patch.is_empty:reasons.append('INVALID_FILL')
    assembled=owner.union(patch)
    if assembled.geom_type!='Polygon' or not assembled.is_valid:reasons.append('FILL_NOT_EXACTLY_CONNECTED')
    else:
        prior_holes,prior_index=(holes(owner),None) if owner_void_context is None else owner_void_context
        prior_index=STRtree(prior_holes) if prior_index is None else prior_index
        for h in (holes(assembled) if holes_required() else []):
            if any(h.intersection(prior_holes[int(k)]).area>contract.area_epsilon_mm2 for k in prior_index.query(h)):continue
            if not h.buffer(-contract.file_uncertainty_mm).is_empty:
                reasons.append('NEW_TRAPPED_VOID');break
    if patch.difference(cap).area>contract.area_epsilon_mm2:reasons.append('OUTSIDE_LOCAL_ENVELOPE')
    return dict(passed=not reasons,reasons=reasons,shortage=shortage,local_cap_bounds_mm=list(cap.bounds),connected_support_sha256=sha(carrier),foreign_gaps=gaps)


def plan(source,current,contract=RemedyContract(),checkpoint=lambda record:None,source_support=None,partial_strategy=None,clearance_only=None):
    contract.validate();originals,grown,mapping=components(source,current,contract)
    records=[];accepted=[];tree=STRtree(grown);partial_specs=[]
    clearance_only={}if clearance_only is None else clearance_only
    checking_ids=sorted(clearance_only);checking_tree=STRtree([clearance_only[j]for j in checking_ids])
    from src.partial_pocket_remedy import STRATEGY,propose,protected
    if partial_strategy not in(None,STRATEGY):raise ValueError('PARTIAL_POCKET_POLICY_UNSUPPORTED')
    for index,(owner,j) in enumerate(zip(grown,mapping)):
        checkpoint(dict(component=index,total_components=len(grown),proposals_so_far=len(records),fills_so_far=len(accepted)))
        from src.hole_acceptance import required as holes_required
        original=originals[j];oldvoid=joined(holes(original))if holes_required()else empty();ownerholes=holes(owner)
        owner_void_context=(ownerholes,STRtree(ownerholes))
        candidates=[]
        for hole in ownerholes:
            if not holes_required():
                records.append(dict(kind='hole',owner=index,source_component=j,patch_sha256=sha(hole),area_mm2=hole.area,status='KEEP_ACCEPTED_ORDINARY_HOLE',bounds_mm=list(hole.bounds)));continue
            if hole.intersection(oldvoid).area>contract.area_epsilon_mm2:
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
            checking=[('checking-envelope:'+str(checking_ids[int(k)]),clearance_only[checking_ids[int(k)]])for k in checking_tree.query(patch.buffer(contract.construction_gap_mm+.001))if checking_ids[int(k)]!=j]
            if any(patch.distance(g)+1e-12<contract.construction_gap_mm for _,g in checking):
                records.append(dict(kind=kind,owner=index,source_component=j,patch_sha256=sha(patch),area_mm2=patch.area,bounds_mm=list(patch.bounds),status='KEEP_ENTIRE_FILL_CHECKING_ENVELOPE',check=dict(passed=False,reasons=['T04_CHECKING_ENVELOPE_CLEARANCE'],role='CLEARANCE_ONLY_NOT_COPPER_NOT_MINIMUM_FLOOR')))
                continue
            from src.growth_remedy_constraints import remedy as pin_remedy
            pin_check=pin_remedy(patch,owner)
            if pin_check is not None and not pin_check['passed']:
                records.append(dict(kind=kind,owner=index,source_component=j,patch_sha256=sha(patch),area_mm2=patch.area,bounds_mm=list(patch.bounds),status='KEEP_PROTECTED_PIN_SEPARATION',check=pin_check))
                continue
            owned_specs=[s for s in partial_specs if s['owner']==index]
            if kind=='notch'and owned_specs:
                patch=joined(surface_parts(patch.difference(protected(owned_specs))))
                if patch.is_empty:continue
            nearby=[(int(k),grown[int(k)]) for k in tree.query(patch.buffer(contract.construction_gap_mm+.001)) if int(k)!=index]+checking
            check=proposal_check(patch,owner,original,nearby,contract,kind,oldvoid,owner_void_context)
            if partial_strategy==STRATEGY and kind=='hole'and check['reasons']==['SHORTAGE_ABOVE_20_PERCENT']:
                patch,check,spec=propose(patch,owner,contract,check);spec.update(owner=index,source_component=j);partial_specs.append(spec);kind='partial_rim'
            support_check=None if source_support is None else source_support.check(patch)
            if support_check is not None and kind=='notch' and not support_check['passed']:
                check['reasons'].append('OUTSIDE_ORIGINAL_CONTACT_SUPPORT');check['passed']=False
            check['source_contact_support']=dict(applicable=kind=='notch',basis='Original pair contact windows for open notches; fully enclosed holes use complete existing component-boundary support',diagnostic=support_check)
            row=dict(kind=kind,owner=index,source_component=j,patch_sha256=sha(patch),area_mm2=patch.area,bounds_mm=list(patch.bounds),status='FILL' if check['passed'] else 'KEEP_BLOCKED',check=check)
            records.append(row)
            if check['passed']:accepted.append(dict(owner=index,kind=kind,geometry=patch,record_sha256=sha(patch)))
    # Frozen proposals, one pass. Complete simultaneous cross-component proof.
    for i,a in enumerate(accepted):
        for b in accepted[:i]:
            if a['owner']!=b['owner'] and a['geometry'].distance(b['geometry'])+1e-12<contract.construction_gap_mm:
                raise ValueError('SIMULTANEOUS_FILL_CLEARANCE_FAILED')
    fills=joined([r['geometry'] for r in accepted]);result=current.union(fills)
    newparts=parts(result)
    if len(newparts)!=len(grown):raise ValueError('FILL_COMPONENT_TOPOLOGY_CHANGED')
    components(source,result,contract)
    if current.difference(result).area>contract.area_epsilon_mm2:raise ValueError('FILL_REMOVED_PREDECESSOR')
    report=dict(contract=asdict(contract),source_sha256=sha(source),predecessor_sha256=sha(current),records=records,fill_sha256=sha(fills),result_sha256=sha(result))
    if partial_strategy is not None:report.update(large_pocket_strategy=partial_strategy,approved_partial_pockets=partial_specs)
    return report,accepted,result
