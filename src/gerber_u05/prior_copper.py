"""Carry qualified source-derived copper into T05 before new growth is chosen."""
from pathlib import Path
from shapely import to_wkb
from shapely.ops import unary_union
from src import component_clearance as cc
from src.u05_board.coverage import CoverageAdapter as BaseCoverageAdapter,CONTRACT
from src.stage_abi.store import canonical,digest
from src.pcb_data_abi.geometry import POLYGON_TOLERANCE_MM,GRID_MM
from src.growth_void_encoding import filled_surface


def protected_owners(current,prior):
 if set(current)!=set(prior):raise ValueError('PRIOR_ORIGINAL_OWNER_INVENTORY_CHANGED')
 return{o:unary_union([current[o],prior[o]])for o in current}

def require_shared_prior(material,*,native_floor=False):
 """A retained native floor cannot redefine an accepted T02 gap."""
 from src import t02_shared_gaps as shared_gaps
 if shared_gaps.ACTIVE is None:return None
 # A qualified Gerber floor already has native-grid coordinates. Its complete
 # adopted boundary uses the same existing fidelity bound as final reparse;
 # ordinary model proposals retain the exact predicate by default.
 tolerance=POLYGON_TOLERANCE_MM if native_floor else 0.
 return shared_gaps.complete(shared_gaps.ACTIVE,unary_union(list(material.values())),tolerance_mm=tolerance)


def local_floor(current,prior,*,tolerance_mm=POLYGON_TOLERANCE_MM,support_mm=.000004):
 if current.is_empty or prior.is_empty or not current.is_valid or not prior.is_valid:raise ValueError('PRIOR_FLOOR_INVALID_MATERIAL')
 if tolerance_mm!=POLYGON_TOLERANCE_MM or support_mm!=.000004:raise ValueError('PRIOR_FLOOR_EXISTING_NATIVE_TOLERANCE_REQUIRED')
 missing=prior.difference(current.buffer(GRID_MM))
 if missing.is_empty:return None,dict(required=False,missing_mm2=0.)
 # The window adds only already-existing material from either proved surface.
 # One region per original owner is retained, not one object per missing patch.
 allowed=unary_union([current,prior]);window=missing.buffer(tolerance_mm+support_mm,quad_segs=1,join_style='mitre');region=filled_surface(allowed.intersection(window))
 if region.difference(allowed).area>1e-12:raise ValueError('PRIOR_FLOOR_MATERIAL_SCOPE_CHANGED')
 after=unary_union([current,region]);remaining=prior.difference(after.buffer(tolerance_mm)).area
 if remaining>1e-12:raise ValueError('PRIOR_FLOOR_RECONSTRUCTION_MISSING')
 return region,dict(required=True,missing_mm2=missing.area,local_material_mm2=region.area,remaining_mm2=remaining,tolerance_mm=tolerance_mm,construction_containment_guard_mm=GRID_MM,support_mm=support_mm,basis='Only qualified prior or existing current copper; all source identities unchanged')


class CoverageAdapter(BaseCoverageAdapter):
 def describe(self):
  value=super().describe()
  if cc.ACTIVE is not None:value=dict(value,implementation=digest(canonical(value)+Path(__file__).read_bytes()),prior_positive_protection='CURRENT_AND_SOURCE_DERIVED_PRIOR_FOREIGN_COMPONENTS')
  return value
 def close(self):
  for name in('_prior_protected_owners','_prior_protected_key'):self.__dict__.pop(name,None)
  super().close()
 def _operands(self,store,scene,policy,details,row):
  owner,radius,domain,foreign=super()._operands(store,scene,policy,details,row)
  from src.u05_board.coverage import integral_context
  context=integral_context()
  if context is not None:
   own=self.owner_for_route(row['source_id']);query=domain.buffer(CONTRACT.barrier_gap_mm)
   foreign=[*foreign,*[('checking-envelope:'+o,g)for o,g in getattr(context,'checking_envelopes',{}).items()if o!=own and g.intersects(query)]]
  if cc.ACTIVE is None:return owner,radius,domain,foreign
  context=getattr(self,'_integral_context',cc.ACTIVE)
  if set(self._copper_owners)!=set(context.reserved):raise ValueError('PRIOR_ORIGINAL_OWNER_INVENTORY_CHANGED')
  own=self.owner_for_route(row['source_id']);query=domain.buffer(CONTRACT.barrier_gap_mm)
  # Separate operands give the same distance/barrier union while reusing the
  # already resident shapes. No second board-sized protected union is retained.
  foreign=[*foreign,*[('owner:'+o,g)for o,g in context.reserved.items()if o!=own and g.intersects(query)]]
  return owner,radius,domain,foreign


def prepare(store,scene):
 if cc.ACTIVE is None:return scene,None
 from .stage_entry_prior import bind as bind_entry
 bind_entry(store)
 if getattr(cc.ACTIVE,'functional',None)is not None:
  from .channel_prior import prepare
  return prepare(store,scene)
 from . import pipeline as p
 from .native_component_checks_final import clearance
 context=cc.ACTIVE
 if not context.reservation_sha256:raise ValueError('SOURCE_DERIVED_PRIOR_BINDING_REQUIRED')
 rows,current,_=p.operands(store,scene);owned=context.project(current);protected=protected_owners(owned,context.reserved)
 # The prior and combined predecessor must obey the same finished-copper floor.
 # New T05 growth still uses the unchanged, larger construction guard.
 prior_check=clearance(context.cores,context.reserved);combined_check=clearance(context.cores,protected)
 if context.partial_pocket_failures(protected):raise ValueError('PRIOR_POSITIVE_COPPER_CONFLICTS_WITH_FROZEN_PARTIAL_OPENING')
 existing={row['metadata']['original_owner_id']:row for row in scene['objects']if row['kind']=='component_remedy'};changes={};metadata={};additions=[];records=[]
 for own in sorted(owned):
  material,proof=local_floor(owned[own],context.reserved[own])
  if material is None:continue
  sid='component-completion:'+own;old=existing.get(own);aggregate=material if old is None else unary_union([p.geometry(store,old['geometry_ref']),material]);reference=p.geomref(store,aggregate)
  md=dict(origin='qualified-source-derived-prior-floor',original_owner_id=own,original_source_sha256=context.source_hash,stage='t05-prior-floor',kind='owner_surface_absorption',nominal_width_mm=0.,original_width_mm=0.,qualified_land=False,representation='EXISTING_COMPONENT_SURFACE_EXTENDED; no per-feature material objects',logical_patch_ref=reference,prior_generated_sha256=context.reservation_sha256)
  if old is not None and old['metadata'].get('approved_partial_pockets'):md['approved_partial_pockets']=old['metadata']['approved_partial_pockets']
  if old is None:additions.append(dict(source_id=sid,kind='component_remedy',geometry_ref=reference,original_ref=p.geomref(store,context.cores[own]),metadata=md))
  else:
   if old['source_id']!=sid:raise ValueError('PRIOR_OWNER_SURFACE_IDENTITY_CHANGED')
   changes[sid]=aggregate;metadata[sid]=md
  context.assign(sid,aggregate,[own]);records.append(dict(source_id=sid,original_owner_id=own,geometry_ref=reference,prior_owner_sha256=digest(to_wkb(context.reserved[own])),proof=proof))
 output_ref=p.artifact_scene(store,scene,changes,'t05-qualified-prior-floor',metadata=metadata,additions=additions);output=store.get_json(output_ref,kind='scene');context.register_scene(store,output)
 # Enforce the frozen gaps on the complete selected floor. Sub-grid reference
 # support skipped by local_floor is not part of the adopted candidate.
 _,adopted,_=p.operands(store,output)
 shared_gap_check=require_shared_prior(context.project(adopted),native_floor=True)
 receipt=dict(stage_entry_prior=getattr(context,'stage_entry_prior',None),schema='qualified-source-derived-prior-floor/1',source_sha256=context.source_hash,prior_generated_sha256=context.reservation_sha256,input_scene_ref=store.put_json('scene',scene),output_scene_ref=output_ref,records=records,prior_current_policy_check=prior_check,combined_predecessor_policy_check=combined_check,shared_neighbor_gaps=shared_gap_check,policy='The source-only generated prior is minimum physical copper, present before T05 planning. All original owners stay frozen; current and prior foreign material constrain every new spindle. Source void, scope, native export and final retention checks remain mandatory.')
 return output,receipt
