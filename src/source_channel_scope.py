"""Frozen functional-channel surfaces for incremental construction checks."""
from shapely import to_wkb,from_wkb
from src import component_clearance as cc
from src.stage_abi.store import canonical,digest
from src.source_common_frame import discover
from src.source_channel_guard import SourceChannels,POLICY
ACTIVE=None

class Scope:
 def __init__(self,channels,certificate,source_objects):
  self.channels=channels;self.certificate=certificate;self.index=channels.index;self.cores=channels.original;self.source_hash=channels.source_sha256
  self.frame_ids=frozenset(s for row in certificate['frame_source_rows']for s in row['source_ids']);self.source_objects=dict(source_objects);self.originals={s:g for s,g in source_objects.items()if s not in self.frame_ids};self.ids={s:tuple(self.index.membership(g))for s,g in self.originals.items()};self.ids.update({s:()for s in self.frame_ids})
  if any(len(self.ids[s])!=1 for s in self.originals):raise ValueError('FUNCTIONAL_SOURCE_OCCURRENCE_NOT_ONE_CHANNEL')
  self.reserved={};self.reservation_sha256=None;self.approved_partial_pockets={};self.binding=digest(canonical(certificate));self.ownership_policy=dict(schema='functional-source-channels/1',policy=certificate['policy'],internal_clearance='NOT_APPLICABLE_WITHIN_ONE_FUNCTIONAL_CHANNEL',foreign_clearance='ALL_CURRENT_AND_RESERVED_OTHER_SOURCE_CHANNELS',ownership='FROZEN_NON_FRAME_SOURCE_OCCURRENCES',source_ports='Source pad and trace remain integral; remote frame ties grant no exemption')
 def assign(self,sid,g,owners=None):
  selected=tuple(self.index.membership(g)if owners is None else owners)
  if not selected or any(o not in self.cores for o in selected):raise ValueError('FUNCTIONAL_DERIVED_CHANNEL_UNBOUND:'+sid)
  if sid in self.ids and self.ids[sid]!=selected:raise ValueError('FROZEN_FUNCTIONAL_CHANNEL_CHANGED:'+sid)
  self.ids[sid]=selected;return selected
 def owner(self,sid,g=None):
  ids=self.ids.get(sid)
  if ids is None:ids=self.assign(sid,g)
  if len(ids)!=1:raise ValueError('ONE_FUNCTIONAL_CHANNEL_REQUIRED:'+sid)
  return ids[0]
 def iter_project(self,material):
  buckets={o:[g]for o,g in self.cores.items()}
  for sid,g in material.items():
   if sid in self.frame_ids:
    if to_wkb(g)!=to_wkb(self.source_objects[sid]):raise ValueError('TEMPORARY_FRAME_GROWTH_NOT_ALLOWED:'+sid)
    continue
   if sid in self.originals and to_wkb(g)==to_wkb(self.originals[sid]):continue
   ids=self.ids.get(sid)
   if ids is None:ids=self.assign(sid,g)
   if len(ids)!=1:raise ValueError('DERIVED_MATERIAL_NOT_ONE_FUNCTIONAL_CHANNEL:'+sid)
   buckets[ids[0]].append(g)
  for own,values in buckets.items():yield own,cc.joined(values)
 def project(self,material):return dict(self.iter_project(material))
 def partial_pocket_failures(self,after):
  failures=[]
  for key,value in sorted(self.approved_partial_pockets.items()):
   spec=value['spec'];own=spec['original_channel_id'];body=after[own];amount=body.intersection(value['initial']).area;occupied=body.intersection(value['protected_core']).area
   if amount>spec['decision']['maximum_added_area_mm2']or occupied>value['contract'].area_epsilon_mm2:failures.append(dict(owner=own,pocket_id=key,reason='FROZEN_FUNCTIONAL_PARTIAL_BUDGET_OR_OPENING_CHANGED',added_area_mm2=amount))
  return failures
 def register_scene(self,store,scene):
  for row in scene['objects']:
   sid=row['source_id'];md=row['metadata']
   if sid in self.source_objects:
    if row['original_ref']['sha256']!=digest(to_wkb(self.source_objects[sid])):raise ValueError('FUNCTIONAL_SOURCE_REFERENCE_CHANGED')
    if sid in self.frame_ids and row['geometry_ref']!=row['original_ref']:raise ValueError('TEMPORARY_FRAME_GROWTH_NOT_ALLOWED:'+sid)
    continue
   members=md.get('reference_source_ids')if row['kind']=='trace'else md.get('members')if row['kind']=='inclusive_rectangle'else None
   if members is not None:
    ids={o for m in members for o in self.ids[m]}
    if not ids and all(m in self.frame_ids for m in members):self.ids[sid]=();continue
    if len(ids)!=1:raise ValueError('DERIVED_ROUTE_OR_RECTANGLE_CROSSES_FUNCTIONAL_CHANNELS')
    selected=next(iter(ids))
    if md.get('original_channel_id',selected)!=selected:raise ValueError('DERIVED_FUNCTIONAL_CHANNEL_BINDING_CHANGED')
    if md.get('original_channel_witness_sha256',digest(to_wkb(self.cores[selected])))!=digest(to_wkb(self.cores[selected])):raise ValueError('DERIVED_FUNCTIONAL_SOURCE_WITNESS_CHANGED')
    self.assign(sid,None,sorted(ids))
   elif row['kind']=='junction_addition':self.assign(sid,None,self.ids[md['owner_trace']])
   elif 'original_channel_id'in md:
    own=md['original_channel_id']
    if md.get('original_source_sha256')!=self.source_hash or own not in self.cores:raise ValueError('DERIVED_FUNCTIONAL_CHANNEL_BINDING_CHANGED')
    self.assign(sid,None,[own])
   else:raise ValueError('DERIVED_FUNCTIONAL_CHANNEL_CERTIFICATE_REQUIRED:'+sid)
   for spec in md.get('approved_partial_pockets',[]):
    own=self.owner(sid)
    if spec.get('original_channel_id')!=own or spec.get('original_source_sha256')!=self.source_hash:raise ValueError('PARTIAL_FUNCTIONAL_CHANNEL_BINDING_CHANGED')
    physical=getattr(self,'physical_context',None);known=None if physical is None else physical.approved_partial_pockets.get(spec['pocket_id'])
    if known is None or canonical(known['spec'])!=canonical(spec):raise ValueError('PARTIAL_FUNCTIONAL_PHYSICAL_PROOF_REQUIRED')
    self.approved_partial_pockets[spec['pocket_id']]=known
 def reserve(self,actual,generated_sha256):
  check=self.channels.check(actual)
  if not check['passed']:raise ValueError('PRIOR_REFERENCE_VIOLATES_FUNCTIONAL_CHANNELS:'+str(check['failures'][:3]))
  functional=cc.joined([self.channels.analytic_source,*cc.surfaces(actual.difference(self.channels.source).difference(self.channels.frame))]);from src.original_copper_owners import OriginalOwners
  grouped=OriginalOwners(functional);reserved={}
  for g in grouped.owners:
   ids=self.index.membership(g)
   if len(ids)!=1 or ids[0]in reserved:raise ValueError('PRIOR_FUNCTIONAL_CHANNEL_PARTITION_CHANGED')
   reserved[ids[0]]=g
  if set(reserved)!=set(self.cores):raise ValueError('PRIOR_FUNCTIONAL_CHANNEL_MISSING')
  self.reserved=reserved;self.reservation_sha256=generated_sha256;self.binding=digest(canonical([self.certificate,generated_sha256]));return check

def bind(source,source_sha256,scene,store,*,integral=False):
 global ACTIVE
 ACTIVE=None;frame,certificate=discover(source,source_sha256,scene,store)
 if integral:
  if frame is not None:raise ValueError('ASSEMBLED_SOURCE_STILL_HAS_CONFIRMED_OUTER_ENCLOSURE')
  from shapely.geometry import Polygon
  from src.source_channel_guard import ASSEMBLED_POLICY
  frame=Polygon();certificate=dict(status='INTEGRAL_ASSEMBLED_SOURCE_CHANNELS',policy=ASSEMBLED_POLICY,source_sha256=source_sha256,source_geometry_sha256=digest(to_wkb(source)),frame_geometry_sha256=digest(to_wkb(frame)),frame_source_rows=[],material_edit=False)
 elif frame is None:return None
 channels=SourceChannels(source,source_sha256,frame,certificate,store=store);objects={r['source_id']:from_wkb(store.get(r['original_ref'],kind='geometry'))for r in scene['objects']};ACTIVE=Scope(channels,certificate,objects);return ACTIVE

def physical_owner(scope,channel,physical):
 owners={o for sid in scope.originals if channel in scope.ids[sid]for o in physical.ids[sid]}
 if len(owners)!=1:raise ValueError('FUNCTIONAL_CHANNEL_PHYSICAL_OWNER_NOT_UNIQUE')
 return next(iter(owners))

def install_reserved(scope,store,sidecar,generated_sha256):
 from src.gerber_u05.channel_material import check_owned
 if sidecar['schema']!='actual-native-channel-reservation/1'or sidecar['source_sha256']!=scope.source_hash or sidecar['generated_sha256']!=generated_sha256 or sidecar['channel_certificate_sha256']!=digest(canonical(scope.certificate)):raise ValueError('NATIVE_CHANNEL_RESERVATION_BINDING_CHANGED')
 if sidecar.get('status')!='PASS':raise ValueError('NATIVE_CHANNEL_RESERVATION_NOT_PASSED')
 owned={o:from_wkb(store.get(ref,kind='geometry'))for o,ref in sidecar['owned_geometry_refs'].items()};check=check_owned(scope,owned)
 if not check['passed']:raise ValueError('PRIOR_NATIVE_FUNCTIONAL_CLEARANCE_FAILED:'+str(check['failures'][:3]))
 scope.reserved=owned;scope.reservation_sha256=generated_sha256;scope.binding=digest(canonical([scope.certificate,generated_sha256,sidecar['owned_geometry_refs']]));return check
