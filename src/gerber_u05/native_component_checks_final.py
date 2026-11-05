"""Independent checks on actual parsed positive contours, grouped by original copper."""
import math,collections
from . import pipeline as p
from src import component_clearance as cc
from src.growth_void_remedy_v09 import parts,holes,joined
from src.indexed_polygon_distance import distance as exact_distance
from shapely import STRtree

def decoded_groups(source,observed):
 ctx=cc.ACTIVE;buckets={o:[]for o in ctx.index.ids}
 for g in parts(source):
  ids=ctx.index.membership(g)
  if len(ids)!=1:raise ValueError('NATIVE_ORIGINAL_OWNER_UNBOUND')
  buckets[ids[0]].append(g)
 for sid,pieces in observed.items():
  own=ctx.owner(sid)
  buckets[own].extend(pieces)
 return {o:joined(values)for o,values in buckets.items()}

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
 return dict(passed=True,pairs=pairs,nominal_gap_mm=gap,internal_clearance='NOT_APPLICABLE_SAME_ORIGINAL_OWNER')

def completion(store,stage_result,observed,before,after):
 ctx=cc.ACTIVE;expected={r['source_id']:r for r in stage_result['intra']['fills']}
 if set(expected)!=set(observed):raise ValueError('NATIVE_COMPLETION_INVENTORY_CHANGED')
 records=[]
 for sid,row in expected.items():
  own=row['original_owner_id'];actual=joined(observed[sid]);logical=p.geometry(store,row['logical_patch_ref']);added=actual.difference(before[own])
  if logical.difference(actual.buffer(.000002)).area>1e-12:raise ValueError('NATIVE_REQUIRED_POCKET_OR_NOTCH_MISSING')
  protected=joined(holes(ctx.cores[own])).buffer(-.000002)
  if added.intersection(protected).area>1e-12:raise ValueError('NATIVE_INHERITED_SOURCE_VOID_FILLED')
  records.append(dict(source_id=sid,original_owner_id=own,kind=row['kind'],native_added_area_mm2=added.area))
 return dict(passed=True,records=records,physical_clearance=clearance(before,after))

def final_inventory(source,actual):
 ctx=cc.ACTIVE;whole=joined(list(actual.values()));groups=cc.OriginalOwners(whole);mapping=[];new=[];inherited=[]
 for g in groups.owners:
  ids=ctx.index.membership(g)
  if len(ids)!=1:raise ValueError('NATIVE_ORIGINAL_COMPONENT_MERGED_OR_UNBOUND')
  mapping.append(ids[0])
  oldholes=joined(holes(ctx.cores[ids[0]]))
  for h in holes(g):
   if h.intersection(oldholes).area>1e-12:inherited.append(dict(owner=ids[0],bounds_mm=list(h.bounds),area_mm2=h.area));continue
   foreign=[o for o,v in actual.items()if o!=ids[0]and h.intersection(v).area>1e-12]
   if foreign:
    new.append(dict(owner=ids[0],status='PROTECTED_FOREIGN_CLEARANCE_CAVITY',foreign_original_owners=foreign,bounds_mm=list(h.bounds),area_mm2=h.area));continue
   if h.buffer(-.000002).is_empty:
    new.append(dict(owner=ids[0],status='SUBRESOLUTION_GEOMETRY_DIAGNOSTIC',bounds_mm=list(h.bounds),area_mm2=h.area));continue
   raise ValueError('NATIVE_UNREPAIRED_GROWTH_CREATED_EMPTY_POCKET:'+str(dict(bounds_mm=list(h.bounds),area_mm2=h.area)))
 if len(mapping)!=len(ctx.index.ids)or set(mapping)!=set(ctx.index.ids):raise ValueError('NATIVE_ORIGINAL_COPPER_PARTITION_CHANGED')
 survival=[]
 for own,g in ctx.cores.items():
  for hole in holes(g):
   raw_empty=hole.difference(source)
   if raw_empty.is_empty:continue
   protected=raw_empty.buffer(-.000002)
   empty=raw_empty if protected.is_empty else protected
   remaining=empty.difference(whole)
   if remaining.is_empty or remaining.area<=0:raise ValueError('NATIVE_INHERITED_SOURCE_HOLE_REMOVED')
   survival.append(dict(owner=own,bounds_mm=list(hole.bounds),protected_source_empty_area_mm2=empty.area,remaining_empty_area_mm2=remaining.area))
 return dict(passed=True,original_components_preserved=len(mapping),inherited_holes=len(inherited),source_hole_survival=survival,new_resolvable_empty_pockets=0,remaining_cavities=new,source_missing_overlay_diagnostic_mm2=source.difference(whole).area,source_preservation_authority='Verified original plotting command prefix plus exclusively positive appended native regions')
