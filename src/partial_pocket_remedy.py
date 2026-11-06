"""One bounded smooth inward rim; its intentional opening is frozen thereafter."""
import math
from shapely import from_wkb,to_wkb,normalize
from shapely.geometry import box,Polygon
import hashlib
STRATEGY='SMOOTH_INNER_RIM_ONCE_WITHIN_EXISTING_SHORTAGE_CAP'
def digest(shape):return hashlib.sha256(to_wkb(normalize(shape))).hexdigest()
def shape(spec,name):return from_wkb(bytes.fromhex(spec[name]))

def construct(pocket,carrier,contract,mandatory=None):
    from src.growth_remedy_constraints import remedy as pin_remedy
    pin_check=pin_remedy(pocket,carrier)
    if pin_check is not None and not pin_check['passed']:raise ValueError('PROTECTED_PIN_SEPARATION_COMPLETE_POCKET_REJECTED')
    contract.validate()
    if pocket.geom_type!='Polygon' or not pocket.is_valid or pocket.is_empty or pocket.interiors or carrier.is_empty or not carrier.is_valid:
        raise ValueError('VALID_SINGLE_POCKET_AND_CONNECTED_CARRIER_REQUIRED')
    if carrier.geom_type!='Polygon' or carrier.intersection(pocket).area>contract.area_epsilon_mm2:
        raise ValueError('POCKET_CARRIER_MUST_BE_ONE_SEPARATE_CONNECTED_SURFACE')
    cap=contract.maximum_shortage
    maximum_added=carrier.area*cap/(1-cap)
    if pocket.area<=maximum_added:raise ValueError('WHOLE_POCKET_ALREADY_WITHIN_CAP')
    mandatory=Polygon()if mandatory is None else mandatory.intersection(pocket)
    if mandatory.area==0:mandatory=Polygon()
    if not mandatory.is_valid or mandatory.area>maximum_added:raise ValueError('MANDATORY_PRIOR_COPPER_EXCEEDS_PARTIAL_POCKET_BUDGET')
    # Use identical coordinate operands without transient GEOS precision tags.
    pocket=from_wkb(to_wkb(pocket));carrier=from_wkb(to_wkb(carrier))
    def evaluate(inset):
        # Erode twice, then add one radius back. Net inward offset plus round
        # opening: the retained void has rounded transitions, not a rigid plug.
        angle=math.acos(max(-1.,1-contract.file_uncertainty_mm/(8*inset))) if inset else 1.
        segments=max(32,math.ceil(math.pi/(4*angle)))
        remaining=pocket.buffer(-2*inset,quad_segs=segments).buffer(inset,quad_segs=segments)
        if not mandatory.is_empty:
            remaining=remaining.difference(mandatory.buffer(contract.file_uncertainty_mm,quad_segs=segments))
            remaining=remaining.buffer(-inset,quad_segs=segments).buffer(inset,quad_segs=segments)
        if remaining.is_empty or remaining.geom_type!='Polygon' or not remaining.is_valid:return None
        remaining=remaining.intersection(pocket)
        if remaining.geom_type!='Polygon' or remaining.is_empty or not remaining.is_valid:return None
        ring=pocket.difference(remaining)
        if ring.is_empty or not ring.is_valid:return None
        # Reserve the unchanged file-grid area bound before native rounding.
        rounding_bound=2*ring.length*contract.grid_mm+math.pi*contract.grid_mm**2
        accepted=ring.area+rounding_bound<=maximum_added and mandatory.difference(ring).area<=contract.area_epsilon_mm2 and not remaining.buffer(-contract.file_uncertainty_mm).is_empty
        return dict(accepted=accepted,remaining=remaining,ring=ring,rounding_bound=rounding_bound,segments=segments)
    lo=0.;hi=max(pocket.bounds[2]-pocket.bounds[0],pocket.bounds[3]-pocket.bounds[1]);best=None
    for _ in range(64):
        middle=(lo+hi)/2
        trial=evaluate(middle)
        if trial is not None and trial['accepted']:lo=middle;best=trial
        else:hi=middle
        if hi-lo<contract.grid_mm/16:break
    if best is None:raise ValueError('NO_CONNECTED_SMOOTH_RIM_WITHIN_CAP')
    ring=best['ring'];remaining=best['remaining'];ratio=ring.area/carrier.union(ring).area
    if ratio>cap or ring.difference(pocket).area>contract.area_epsilon_mm2 or remaining.area<=0 or carrier.union(ring).geom_type!='Polygon':raise ValueError('SMOOTH_RIM_FINAL_CAP_OR_CONNECTIVITY_FAILED')
    return ring,remaining,dict(schema='bounded-smooth-inner-rim/1',maximum_share=cap,actual_share=ratio,existing_carrier_area_mm2=carrier.area,maximum_added_area_mm2=maximum_added,added_area_mm2=ring.area,retained_void_area_mm2=remaining.area,original_pocket_area_mm2=pocket.area,inward_offset_mm=lo,smoothing_radius_mm=lo,offset_bracket_mm=[lo,hi],circle_quad_segments=best['segments'],reserved_native_area_bound_mm2=best['rounding_bound'],ordering='One frozen pocket budget; later passes must not restart the 20% allowance')

def propose(pocket,owner,contract,full_check,mandatory=None):
    if full_check['passed']or full_check['reasons']!=['SHORTAGE_ABOVE_20_PERCENT']:
        raise ValueError('PARTIAL_RIM_REQUIRES_ONLY_THE_SIZE_LIMIT_TO_BLOCK_FULL_FILL')
    from src.growth_void_remedy_v09 import surface_parts
    cap=box(*full_check['local_cap_bounds_mm'])
    support=[g for g in surface_parts(owner.intersection(cap))if digest(g)==full_check['connected_support_sha256']]
    if len(support)!=1:raise ValueError('PARTIAL_RIM_FROZEN_LOCAL_CARRIER_CHANGED')
    ring,remaining,decision=construct(pocket,support[0],contract,mandatory)
    combined=owner.union(ring)
    if not combined.is_valid or combined.geom_type!='Polygon':raise ValueError('PARTIAL_RIM_OWNER_NOT_CONNECTED')
    spec=dict(schema='approved-partial-pocket/1',strategy=STRATEGY,pocket_id=digest(pocket),initial_pocket_hex=to_wkb(pocket).hex(),remaining_hex=to_wkb(remaining).hex(),carrier_hex=to_wkb(support[0]).hex(),selected_rim_hex=to_wkb(ring).hex(),decision=decision)
    check=dict(full_check,passed=True,reasons=[],shortage=decision['actual_share'],full_pocket_check=full_check,partial_pocket=spec)
    return ring,check,spec

def validate(spec,contract):
    if spec['schema']!='approved-partial-pocket/1'or spec['strategy']!=STRATEGY:raise ValueError('PARTIAL_POCKET_POLICY_UNSUPPORTED')
    initial,remaining,carrier,ring=[shape(spec,k)for k in('initial_pocket_hex','remaining_hex','carrier_hex','selected_rim_hex')]
    if any(g.is_empty or not g.is_valid or g.geom_type!='Polygon'for g in(initial,remaining,carrier,ring)):
        raise ValueError('PARTIAL_POCKET_GEOMETRY_INVALID')
    if digest(initial)!=spec['pocket_id']or spec['decision']['maximum_share']!=contract.maximum_shortage:raise ValueError('PARTIAL_POCKET_BUDGET_CHANGED')
    maximum=carrier.area*contract.maximum_shortage/(1-contract.maximum_shortage)
    fields=('maximum_added_area_mm2','added_area_mm2','existing_carrier_area_mm2','actual_share','maximum_share')
    if any(type(spec['decision'][key])not in(float,int)or not math.isfinite(spec['decision'][key])for key in fields):raise ValueError('PARTIAL_POCKET_NONFINITE_BUDGET')
    if abs(maximum-spec['decision']['maximum_added_area_mm2'])>contract.area_epsilon_mm2 or remaining.difference(initial).area>contract.area_epsilon_mm2 or ring.difference(initial).area>contract.area_epsilon_mm2 or initial.difference(ring.union(remaining)).area>contract.area_epsilon_mm2 or ring.intersection(remaining).area>contract.area_epsilon_mm2 or ring.area>maximum:
        raise ValueError('PARTIAL_POCKET_SCOPE_OR_BUDGET_INVALID')
    if abs(ring.area-spec['decision']['added_area_mm2'])>contract.area_epsilon_mm2 or abs(carrier.area-spec['decision']['existing_carrier_area_mm2'])>contract.area_epsilon_mm2:raise ValueError('PARTIAL_POCKET_REPORTED_AREA_CHANGED')
    return initial,remaining,carrier,ring

def protected(specs):
    from shapely import union_all
    return union_all([shape(s,'remaining_hex')for s in specs])if specs else Polygon()

def corresponds(hole,spec,contract):
    """Only the declared remaining opening may pass the retained-cavity gate."""
    _,expected,_,_=validate(spec,contract)
    from src.indexed_hausdorff import distance
    gap,_=distance(hole,expected,tolerance=contract.file_uncertainty_mm)
    area=hole.symmetric_difference(expected).area
    return math.isfinite(gap)and gap<=contract.file_uncertainty_mm and area<=2*expected.length*contract.file_uncertainty_mm
