"""Bounded additive T05 joint profiles; whole proposals pass existing guards.

Windows require source/contact declarations. They are not inferred from net or
component membership. Unsupported or blocked proposals leave copper unchanged.
"""
import math
from shapely.geometry import box
from shapely import to_wkb
from src.component_voids import proposal_check,surface_parts
from src import pin_separation as pin


def propose(owner,original,window,foreign,contract,*,radius_fraction=.25,pin_rule=None,allowed=None):
 if (not math.isfinite(radius_fraction)or not 0<radius_fraction<=.5
     or owner.is_empty or not owner.is_valid or not original.is_valid
     or window.is_empty or not window.is_valid):raise ValueError('T05_JOINT_PROFILE_INPUT_INVALID')
 if allowed is not None and window.difference(allowed).area>contract.area_epsilon_mm2:
  return None,dict(status='KEEP',reasons=['OUTSIDE_SOURCE_CONTACT_WINDOW'])
 support=owner.intersection(window)
 if len(surface_parts(support))!=1:return None,dict(status='KEEP',reasons=['LOCAL_JOINT_SUPPORT_NOT_ONE_SURFACE'])
 envelope=support.convex_hull
 radius=min(window.bounds[2]-window.bounds[0],window.bounds[3]-window.bounds[1])*radius_fraction
 if radius>contract.maximum_notch_radius_mm:return None,dict(status='KEEP',reasons=['LOCAL_RADIUS_LIMIT'])
 # Extend the existing local boundary by a bounded round offset, inside the
 # declared convex transition envelope. This is candidate construction, never
 # clipping against a foreign/pin barrier to turn a rejection into acceptance.
 rounded=support.buffer(radius,quad_segs=256).intersection(envelope)
 patch=rounded.difference(owner)
 if patch.is_empty or patch.area<=1e-8:return None,dict(status='KEEP',reasons=['NO_VISIBLE_PROFILE_ADDITION'])
 from src.growth_remedy_constraints import remedy
 constraints=remedy(patch,owner,pin_rule=pin_rule)
 pin_check=None if constraints is None else constraints.get('pin_separation',constraints)
 if constraints is not None and not constraints['passed']:
  reason='PROTECTED_PIN_SEPARATION'if pin_check is not None and not pin_check['passed']else'T04_FROZEN_WIDENING_DECISION'
  return None,dict(status='KEEP',reasons=[reason],pin_separation=pin_check,growth_constraints=constraints)
 check=proposal_check(patch,owner,original,foreign,contract,kind='notch')
 reasons=list(check['reasons'])
 if patch.difference(window).area>contract.area_epsilon_mm2:reasons.append('OUTSIDE_DECLARED_LOCAL_WINDOW')
 if reasons:return None,dict(status='KEEP',reasons=reasons,check=check)
 region=support.union(patch)
 if not region.is_valid or len(surface_parts(region))!=1:
  return None,dict(status='KEEP',reasons=['LOCAL_PROFILE_NOT_ONE_SURFACE'])
 return dict(addition=patch,region=region),dict(status='GROWN',reasons=[],radius_mm=radius,added_area_mm2=patch.area,check=check,pin_separation=pin_check,growth_constraints=constraints,representation='ONE_LOCAL_JOINT_SURFACE; existing support is redundant copper only')


def apply(store,scene,binding,result,stage,junction_result):
 if stage!='t05':return result
 from . import pipeline as p
 from src import component_clearance as cc
 from .component_policy import read_job
 policy,contracts=read_job(store.root.parent);settings=policy.get('t05_joint_profiles')
 if settings is None:return result
 inventory=store.root.parent/'input_inventory.json'
 identity=binding['source_ref']['sha256']
 if inventory.exists():
  intake=p.load(inventory);identity=intake['files'][intake['selected']]
 specs=settings['sources'].get(identity,[])
 if not specs:return result
 physical=cc.ACTIVE;scope=getattr(physical,'functional',None)or physical
 final=store.get_json(result['output_scene_ref'],kind='scene')
 # The caller supplies the completed stage scene. Original contacts are read
 # from the independently admitted T05 plan, never from new geometric contact.
 t05=junction_result
 admitted=store.get_json(t05['plan']['scene_ref'],kind='scene');rows={r['source_id']:r for r in admitted['objects']}
 current=p.geometry(store,result['after_native_ref'])
 if scope is not physical:
  if 'native_channel_refs'not in result:raise ValueError('T05_JOINT_FUNCTIONAL_CHANNELS_REQUIRED')
  owned={o:p.geometry(store,ref)for o,ref in result['native_channel_refs'].items()}
 else:
  owned={}
  for g in surface_parts(current):
   owners=scope.index.membership(g)
   if len(owners)!=1 or owners[0]in owned:raise ValueError('T05_JOINT_ORIGINAL_OWNER_PARTITION_CHANGED')
   owned[owners[0]]=g
 changes=[];records=[];proofs=[]
 for spec in specs:
  matches=[r for r in admitted['objects']if r['kind']=='circle'and r['metadata']['center_mm']==spec['center_mm']and r['original_ref']['sha256']==spec['source_geometry_sha256']]
  if len(matches)!=1:raise ValueError('T05_JOINT_SOURCE_WITNESS_CHANGED')
  land=matches[0];sid=land['source_id'];own=scope.owner(sid);owner=owned[own];contact_windows=[]
  for d in t05['candidate']['decisions']:
   if sid not in d['land_ids']:continue
   lands=[p.geometry(store,rows[l]['geometry_ref'])for l in d['land_ids']]
   radius=min(min(g.bounds[2]-g.bounds[0],g.bounds[3]-g.bounds[1])/2 for g in lands)
   contact_windows.extend(g.buffer(2*radius,quad_segs=64)for g in lands)
  allowed=p.unary_union(contact_windows)
  foreign=[(o,g)for o,g in owned.items()if o!=own]+[('reserved:'+o,g)for o,g in scope.reserved.items()if o!=own]
  proposal,proof=propose(owner,scope.cores[own],box(*spec['window_mm']),foreign,contracts[0],radius_fraction=settings['radius_fraction'],allowed=allowed)
  proof=dict(proof,id=spec['id'],source_circle=sid);proofs.append(proof)
  if proposal is None:continue
  region=proposal['region'];old_owner=owner;next_owner=owner.union(region)
  from src.native_grid_reference import normalize,reference
  from .native_assembly import canonical_parent
  encoded=p.unary_union([canonical_parent(reference(g)[0],grid_mm=1e-6)for g in surface_parts(normalize(region))])
  encoded_check=proposal_check(encoded.difference(owner),owner,scope.cores[own],foreign,contracts[0],kind='notch')
  if not encoded_check['passed']:proof.update(status='KEEP_NATIVE_GEOMETRY',native_check=encoded_check);continue
  partials=getattr(scope,'approved_partial_pockets',{}).values()
  if any(encoded.difference(owner).intersection(v['remaining']).area>contracts[0].area_epsilon_mm2 for v in partials):
   proof.update(status='KEEP_PROTECTED_PARTIAL_POCKET');continue
  from src.growth_remedy_constraints import encoded_remedy
  pin_check=encoded_remedy(proposal['addition'],encoded,old_owner)
  if pin_check is not None and not pin_check['passed']:proof.update(status='KEEP_NATIVE_PIN_ENCODING',pin_separation=pin_check);continue
  owned[own]=owner.union(encoded);current=physical.index.source.union(p.unary_union(list(owned.values())))if scope is not physical else p.unary_union(list(owned.values()));pin.require(current,scope='t05_joint_profile')
  physical_owner=physical.owner(sid);name='t05-joint-profile:'+p.digest(p.canonical([sid,spec['id']]))
  md=dict(origin='t05-local-joint-profile',original_owner_id=physical_owner,original_source_sha256=physical.source_hash,stage='t05',kind='owner_surface_absorption',nominal_width_mm=0.,original_width_mm=0.,qualified_land=False,logical_patch_ref=p.geomref(store,region),source_circle=sid)
  if scope is not physical:md.update(original_channel_id=own,original_channel_witness_sha256=p.digest(to_wkb(scope.cores[own])))
  ref=p.geomref(store,region);changes.append(dict(source_id=name,kind='component_remedy',original_ref=p.geomref(store,physical.cores[physical_owner]),geometry_ref=ref,metadata=md));physical.assign(name,region,[physical_owner])
  if scope is not physical:scope.assign(name,None,[own])
  records.append(dict(source_id=name,original_owner_id=physical_owner,**({'original_channel_id':own}if scope is not physical else{}),kind='owner_surface_absorption',geometry_ref=ref,logical_patch_ref=ref,planned_fill_area_mm2=proposal['addition'].area))
 output=p.artifact_scene(store,final,{},'t05-local-joint-profiles',additions=changes)
 result=dict(result,output_scene_ref=output,after_native_ref=p.geomref(store,current),fills=[*result['fills'],*records],joint_profiles=proofs)
 if 'native_channel_refs'in result:result['native_channel_refs']={o:p.geomref(store,g)for o,g in owned.items()}
 result['feature_counts']=dict(result['feature_counts'],joint_profile=len(records))
 result['summary']=dict(result['summary'],joint_profiles_grown=len(records),fills=result['summary']['fills']+len(records),added_area_mm2=current.difference(p.geometry(store,result['before_native_ref'])).area)
 return result
