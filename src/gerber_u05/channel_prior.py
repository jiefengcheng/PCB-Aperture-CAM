"""Apply the checked native floor to each frozen functional channel separately."""
from shapely import to_wkb
from . import pipeline as p
from .prior_copper import protected_owners,local_floor,require_shared_prior
from .native_component_checks_final import clearance
from .channel_material import check_owned
from src import component_clearance as cc
from src.source_channel_scope import physical_owner

def prepare(store,scene):
 from .stage_entry_prior import bind as bind_entry
 bind_entry(store)
 physical=cc.ACTIVE;scope=physical.functional;physical.register_scene(store,scene);scope.register_scene(store,scene)
 if not scope.reservation_sha256:raise ValueError('SOURCE_DERIVED_NATIVE_CHANNEL_PRIOR_REQUIRED')
 rows,current,_=p.operands(store,scene);owned=scope.project(current);protected=protected_owners(owned,scope.reserved)
 native_prior=check_owned(scope,scope.reserved);combined=check_owned(scope,protected)
 if not native_prior['passed']or not combined['passed']:raise ValueError('CHANNEL_PRIOR_OR_COMBINED_CLEARANCE_FAILED')
 if scope.partial_pocket_failures(protected):raise ValueError('PRIOR_POSITIVE_COPPER_CONFLICTS_WITH_FROZEN_CHANNEL_OPENING')
 physical_protected=protected_owners(physical.project(current),physical.reserved);physical_check=clearance(physical.cores,physical_protected)
 existing={r['metadata']['original_channel_id']:r for r in scene['objects']if r['kind']=='component_remedy'and 'original_channel_id'in r['metadata']};changes={};metadata={};additions=[];records=[]
 for channel in sorted(owned):
  material,proof=local_floor(owned[channel],scope.reserved[channel])
  if material is None:continue
  own=physical_owner(scope,channel,physical);sid='component-completion:channel:'+channel;old=existing.get(channel);aggregate=material if old is None else p.unary_union([p.geometry(store,old['geometry_ref']),material]);reference=p.geomref(store,aggregate)
  md=dict(origin='qualified-native-functional-channel-floor',original_owner_id=own,original_channel_id=channel,original_channel_witness_sha256=p.digest(to_wkb(scope.cores[channel])),original_source_sha256=physical.source_hash,stage='t05-prior-floor',kind='owner_surface_absorption',nominal_width_mm=0.,original_width_mm=0.,qualified_land=False,representation='EXISTING_CHANNEL_SURFACE_EXTENDED; no per-feature material objects',logical_patch_ref=reference,prior_generated_sha256=scope.reservation_sha256)
  if old is not None and old['metadata'].get('approved_partial_pockets'):md['approved_partial_pockets']=old['metadata']['approved_partial_pockets']
  if old is None:additions.append(dict(source_id=sid,kind='component_remedy',geometry_ref=reference,original_ref=p.geomref(store,physical.cores[own]),metadata=md))
  else:
   if old['source_id']!=sid:raise ValueError('PRIOR_FUNCTIONAL_OWNER_SURFACE_IDENTITY_CHANGED')
   changes[sid]=aggregate;metadata[sid]=md
  physical.assign(sid,aggregate,[own]);scope.assign(sid,None,[channel]);records.append(dict(source_id=sid,original_owner_id=own,original_channel_id=channel,geometry_ref=reference,proof=proof))
 output_ref=p.artifact_scene(store,scene,changes,'t05-native-channel-prior-floor',metadata=metadata,additions=additions);output=store.get_json(output_ref,kind='scene');physical.register_scene(store,output);scope.register_scene(store,output)
 # local_floor already omits redundant native-grid rounding within its fixed
 # containment guard. Check the complete material actually adopted, rather
 # than a hypothetical union of every reference contour, including unneeded
 # support that is never added to this scene. Qualified native boundaries use
 # the existing final-reparse fidelity bound; model proposals stay exact.
 _,adopted,_=p.operands(store,output)
 shared_gap_check=require_shared_prior(physical.project(adopted),native_floor=True)
 return output,dict(stage_entry_prior=getattr(physical,'stage_entry_prior',None),schema='qualified-native-functional-channel-floor/1',source_sha256=physical.source_hash,prior_generated_sha256=scope.reservation_sha256,input_scene_ref=store.put_json('scene',scene),output_scene_ref=output_ref,records=records,prior_current_policy_check=native_prior,combined_predecessor_policy_check=combined,physical_predecessor_check=physical_check,shared_neighbor_gaps=shared_gap_check,policy='Source-native minimum copper by frozen functional channel; full physical and all foreign-channel checks retained')
