"""Independent checks on actual parsed positive contours, grouped by original copper."""
import math,collections
from . import pipeline as p
from src import component_clearance as cc
from src.growth_void_remedy_v09 import parts,holes,joined
from src.indexed_polygon_distance import distance as exact_distance
from shapely import STRtree

class NativeGroups(dict):
 """Physical material plus a separate source-ID-bound channel projection."""
 def __init__(self,physical,channels):super().__init__(physical);self.channels=channels

def project_groups(material):
 ctx=cc.ACTIVE;physical=ctx.project(material);scope=getattr(ctx,'functional',None)
 return physical if scope is None else NativeGroups(physical,scope.project(material))

def decoded_groups(source,observed):
 ctx=cc.ACTIVE;buckets={o:[]for o in ctx.index.ids}
 for g in parts(source):
  ids=ctx.index.membership(g)
  if len(ids)!=1:raise ValueError('NATIVE_ORIGINAL_OWNER_UNBOUND')
  buckets[ids[0]].append(g)
 for sid,pieces in observed.items():
  own=ctx.owner(sid)
  buckets[own].extend(pieces)
 physical={o:joined(values)for o,values in buckets.items()};scope=getattr(ctx,'functional',None)
 if scope is None:return physical
 channels={o:[g]for o,g in scope.cores.items()}
 for sid,pieces in observed.items():
  if sid in scope.frame_ids:raise ValueError('TEMPORARY_FRAME_NATIVE_ADDITION_NOT_ALLOWED')
  channels[scope.owner(sid)].extend(pieces)
 return NativeGroups(physical,{o:joined(values)for o,values in channels.items()})

def clearance(before,after,gap=None):
 if gap is None:gap=p.HARD_GAP_MM
 ids=list(after);tree=STRtree([after[o]for o in ids]);pairs=[]
 for own,g in after.items():
  added=g.difference(before[own])
  if added.is_empty:continue
  for j in sorted(map(int,tree.query(added.buffer(gap+.000002).envelope))):
   other=ids[j]
   if other==own:continue
   distance=exact_distance(added,after[other]);pairs.append(dict(owner=own,foreign_original_owner=other,gap_mm=distance))
   if not math.isfinite(distance)or distance+1e-12<gap:raise ValueError('NATIVE_FOREIGN_ORIGINAL_COMPONENT_CLEARANCE_FAILED:'+str(pairs[-1]))
 result=dict(passed=True,pairs=pairs,nominal_gap_mm=gap,internal_clearance='NOT_APPLICABLE_SAME_ORIGINAL_OWNER')
 if hasattr(after,'channels'):
  if not hasattr(before,'channels'):raise ValueError('NATIVE_FUNCTIONAL_PREDECESSOR_REQUIRED')
  result['functional_channels']=clearance(before.channels,after.channels,gap)
 return result

def completion(store,stage_result,observed,before,after):
 ctx=cc.ACTIVE;expected={r['source_id']:r for r in stage_result['intra']['fills']}
 if set(expected)!=set(observed):raise ValueError('NATIVE_COMPLETION_INVENTORY_CHANGED')
 records=[]
 for sid,row in expected.items():
  own=row['original_owner_id'];actual=joined(observed[sid]);logical=p.geometry(store,row['logical_patch_ref']);lineage_ctx=ctx;lineage_owner=own;lineage_before=before
  if getattr(ctx,'functional',None)is not None:
   lineage_ctx=ctx.functional;lineage_owner=row.get('original_channel_id')
   if lineage_owner not in lineage_ctx.cores or not hasattr(before,'channels'):raise ValueError('NATIVE_COMPLETION_FUNCTIONAL_BINDING_REQUIRED')
   lineage_before=before.channels
  from src.growth_remedy_constraints import require_remedy
  pin_check=require_remedy(actual,joined(list(lineage_before.values())),scope='actual_native_completion')
  added=actual.difference(lineage_before[lineage_owner])
  if logical.difference(actual.buffer(.000002)).area>1e-12:raise ValueError('NATIVE_REQUIRED_POCKET_OR_NOTCH_MISSING')
  from src.component_hole_lineage import classify as hole_lineage,identity as hole_identity
  source_lineage=hole_lineage(lineage_ctx.cores[lineage_owner],lineage_before[lineage_owner]);keepers=set(source_lineage['keeper_ids'])
  protected=joined([h for h in holes(lineage_before[lineage_owner])if hole_identity(h)in keepers]).buffer(-.000002)
  from src.hole_acceptance import required as holes_required
  if holes_required()and added.intersection(protected).area>1e-12:raise ValueError('NATIVE_INHERITED_SOURCE_VOID_FILLED')
  records.append(dict(source_id=sid,original_owner_id=own,kind=row['kind'],native_added_area_mm2=added.area,**({}if pin_check is None else{'pin_separation':pin_check})))
 return dict(passed=True,records=records,physical_clearance=clearance(before,after))

def _inventory(source,actual,ctx,owner_key):
 from src.hole_acceptance import required as holes_required
 whole=joined(list(actual.values()));groups=cc.OriginalOwners(whole);mapping=[];new=[];inherited=[];partial_checks=[];matched_partials=[]
 from src.partial_pocket_remedy import corresponds
 for key,value in sorted(ctx.approved_partial_pockets.items()):
  spec=value['spec'];amount=whole.intersection(value['initial']).area;occupied=whole.intersection(value['protected_core']).area
  if amount>spec['decision']['maximum_added_area_mm2']or occupied>value['contract'].area_epsilon_mm2:raise ValueError('NATIVE_PARTIAL_POCKET_CUMULATIVE_CAP_OR_OPENING_CHANGED')
  partial_checks.append(dict(pocket_id=key,owner=spec[owner_key],actual_added_area_mm2=amount,maximum_added_area_mm2=spec['decision']['maximum_added_area_mm2'],actual_share=amount/(value['carrier'].area+amount),maximum_share=value['contract'].maximum_shortage,status='DELIBERATELY_RETAINED_BOUNDED_RIM_OPENING'))
 for g in groups.owners:
  ids=ctx.index.membership(g)
  if len(ids)!=1:raise ValueError('NATIVE_ORIGINAL_COMPONENT_MERGED_OR_UNBOUND')
  mapping.append(ids[0])
  from src.component_hole_lineage import classify as hole_lineage,identity as hole_identity
  lineage=hole_lineage(ctx.cores[ids[0]],g);keeper_ids=set(lineage['keeper_ids'])
  for h in holes(g):
   if hole_identity(h)in keeper_ids:inherited.append(dict(owner=ids[0],bounds_mm=list(h.bounds),area_mm2=h.area));continue
   approved=[key for key,value in ctx.approved_partial_pockets.items()if value['spec'][owner_key]==ids[0]and corresponds(h,value['spec'],value['contract'])]
   if approved:
    if len(approved)!=1:raise ValueError('NATIVE_PARTIAL_POCKET_REMAINDER_AMBIGUOUS')
    matched_partials.extend(approved);new.append(dict(owner=ids[0],status='APPROVED_SMOOTH_RIM_RETAINED_OPENING',pocket_id=approved[0],bounds_mm=list(h.bounds),area_mm2=h.area));continue
   if not holes_required():
    new.append(dict(owner=ids[0],status='ACCEPTED_ORDINARY_HOLE_WITHOUT_SOURCE_ANCESTRY',bounds_mm=list(h.bounds),area_mm2=h.area));continue
   foreign=[o for o,v in actual.items()if o!=ids[0]and h.intersection(v).area>0]
   if foreign:
    new.append(dict(owner=ids[0],status='PROTECTED_FOREIGN_CLEARANCE_CAVITY',foreign_original_owners=foreign,bounds_mm=list(h.bounds),area_mm2=h.area));continue
   if h.buffer(-.000002).is_empty:
    new.append(dict(owner=ids[0],status='SUBRESOLUTION_GEOMETRY_DIAGNOSTIC',bounds_mm=list(h.bounds),area_mm2=h.area));continue
   raise ValueError('NATIVE_UNREPAIRED_GROWTH_CREATED_EMPTY_POCKET:'+str(dict(bounds_mm=list(h.bounds),area_mm2=h.area)))
 if len(mapping)!=len(ctx.index.ids)or set(mapping)!=set(ctx.index.ids):raise ValueError('NATIVE_ORIGINAL_COPPER_PARTITION_CHANGED')
 if sorted(matched_partials)!=sorted(ctx.approved_partial_pockets):raise ValueError('NATIVE_PARTIAL_POCKET_REMAINDER_MISSING')
 survival=[]
 for own,g in (ctx.cores.items()if holes_required()else []):
  for hole in holes(g):
   raw_empty=hole.difference(source)
   if raw_empty.is_empty:continue
   protected=raw_empty.buffer(-.000002)
   empty=raw_empty if protected.is_empty else protected
   remaining=empty.difference(whole)
   if remaining.is_empty or remaining.area<=0:raise ValueError('NATIVE_INHERITED_SOURCE_HOLE_REMOVED')
   survival.append(dict(owner=own,bounds_mm=list(hole.bounds),protected_source_empty_area_mm2=empty.area,remaining_empty_area_mm2=remaining.area))
 result=dict(passed=True,original_components_preserved=len(mapping),inherited_holes=len(inherited),source_hole_survival=survival,new_resolvable_empty_pockets=0,remaining_cavities=new,source_missing_overlay_diagnostic_mm2=source.difference(whole).area,source_preservation_authority='Verified original plotting command prefix plus exclusively positive appended native regions')
 if partial_checks:result['approved_partial_pocket_remainders']=partial_checks
 if not holes_required():result.update(ordinary_holes='ACCEPT_WITHOUT_SOURCE_ANCESTRY',new_resolvable_empty_pockets='NOT_REQUIRED')
 return result


def final_inventory(source,actual):
 from src.pin_separation import require as require_pin
 pin_proof=require_pin(joined(list(actual.values())),finished=True,scope='reparsed_gerber')
 ctx=cc.ACTIVE;scope=getattr(ctx,'functional',None)
 if scope is None:
  result=_inventory(source,actual,ctx,'original_owner_id')
  if pin_proof is not None:result['pin_separation']=pin_proof
  return result
 if not hasattr(actual,'channels'):raise ValueError('NATIVE_FUNCTIONAL_MATERIAL_INVENTORY_REQUIRED')
 # The retained bar still participates in the physical partition predicate.
 # Void lineage belongs to the separately frozen functional source, so the
 # frame's board-sized interior cannot stand for a trace/pad source void.
 whole=joined(list(actual.values()));groups=cc.OriginalOwners(whole);mapping=[]
 for g in groups.owners:
  ids=ctx.index.membership(g)
  if len(ids)!=1:raise ValueError('NATIVE_ORIGINAL_COMPONENT_MERGED_OR_UNBOUND')
  mapping.append(ids[0])
 if len(mapping)!=len(ctx.index.ids)or set(mapping)!=set(ctx.index.ids):raise ValueError('NATIVE_ORIGINAL_COPPER_PARTITION_CHANGED')
 result=_inventory(scope.channels.analytic_source,actual.channels,scope,'original_channel_id')
 result['functional_channels_preserved']=result['original_components_preserved'];result['original_components_preserved']=len(mapping)
 result['void_inventory_basis']='Original non-frame source occurrences; preserved frame/end bar supply no local growth or source-void exemption'
 result['physical_source_missing_overlay_diagnostic_mm2']=source.difference(whole).area
 if pin_proof is not None:result['pin_separation']=pin_proof
 return result
