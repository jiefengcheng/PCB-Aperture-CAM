"""Capture explicit source pin intent and reconstruct full local separation.

Geometry is not a universal pin-intent oracle. Source declarations bind native
occurrences and attachments; supported rooted slots derive their complete
finger/transition domain from original material, never a result image.
"""
import math
from pathlib import Path
from shapely import to_wkb
from shapely.geometry import box
from src import pin_separation as pin
from src.stage_abi.store import canonical,digest
from src.component_voids import surface_parts
from . import pipeline as p

def capture(run,inventory):
 registry=p.load(p.ROOT/'contracts/pin_separation/settings.json');raw_sha=inventory['files'][inventory['selected']]
 if registry['schema']!='source-pin-intent-registry/1':raise ValueError('PIN_INTENT_REGISTRY_SCHEMA_CHANGED')
 spec=registry['sources'].get(raw_sha)
 p.save(run/'PIN_SEPARATION_POLICY.json',dict(schema=pin.SCHEMA,raw_source_sha256=raw_sha,working_source_sha256=p.load(run/'source.json')['source_ref']['sha256'],registry_sha256=digest(canonical(registry)),declaration=spec,disposition='DECLARED_SOURCE_PIN_INTENT'if spec is not None else'NO_SOURCE_PIN_DECLARATION; pin-intent coverage NOT_ESTABLISHED'))

def rooted_slot(source,source_sha256,rows,store,spec,construction_gap,cache=None):
 seeds=[];source_ids=[]
 for branch in spec['branches']:
  matches=[r for r in rows if r['metadata'].get('source_span')==branch['source_span']]
  if len(matches)!=1:raise ValueError('PIN_ORIGINAL_OCCURRENCE_MISSING_OR_AMBIGUOUS')
  row=matches[0];blob=store.get(row['original_ref'],kind='geometry')
  if digest(blob)!=branch['geometry_sha256']:raise ValueError('PIN_ORIGINAL_OCCURRENCE_GEOMETRY_CHANGED')
  g=p.from_wkb(blob)
  if row['kind']!='stroke'or row['metadata'].get('route_kind')!='segment':raise ValueError('PIN_DECLARED_STRAIGHT_FINGER_REQUIRED')
  points=row['metadata']['route_points_mm']
  if points[0][0]!=points[1][0]:raise ValueError('PIN_ROOTED_VERTICAL_SOURCE_FAMILY_REQUIRED')
  seeds.append(g);source_ids.append(row['source_id'])
 # First qualified family: vertical original fingers entering a source-rooted
 # common attachment. An open transition requires an explicit declaration;
 # it cannot silently become a guessed short protection interval.
 x0,x1=sorted(g.centroid.x for g in seeds);tip=min(g.bounds[1]for g in seeds);uncertainty=.000002;gap=construction_gap
 cache={}if cache is None else cache
 if 'barrier'not in cache:cache['barrier']=source.buffer((gap+2*uncertainty)/2,quad_segs=256)
 if tip not in cache:
  window=box(source.bounds[0]-gap,tip+.000001,source.bounds[2]+gap,source.bounds[3]+gap)
  cache[tip]=(window,surface_parts(window.difference(cache['barrier'])),surface_parts(window.difference(source)))
 window,clear_parts,void_parts=cache[tip];mouth=p.Point((x0+x1)/2,tip+gap)
 channels=[g for g in clear_parts if g.covers(mouth)];voids=[g for g in void_parts if g.covers(mouth)]
 if len(channels)!=1 or len(voids)!=1:raise ValueError('PIN_SOURCE_SLOT_MOUTH_NOT_UNIQUE')
 channel=channels[0];void=voids[0]
 if channel.bounds[0]<=window.bounds[0]+uncertainty or channel.bounds[2]>=window.bounds[2]-uncertainty or channel.bounds[3]>=window.bounds[3]-uncertainty:raise ValueError('PIN_EXPLICIT_TRANSITION_END_REQUIRED')
 # Continue to the original source root, excluding only the exact common
 # attachment boundary. A clearance-offset cap would omit the last transition.
 end=math.nextafter(void.bounds[3],-math.inf)
 if end<max(g.bounds[3]for g in seeds):raise ValueError('PIN_DOMAIN_DOES_NOT_COVER_COMPLETE_FINGER')
 # Follow the full empty source slot into its transition. Do not cut a curved
 # transition at the original straight finger centreline strip.
 reach=(gap+2*uncertainty)/2+min(g.bounds[2]-g.bounds[0]for g in seeds)/4
 domain=void.buffer(reach,quad_segs=64).intersection(box(window.bounds[0],tip-gap,window.bounds[2],end))
 spacing=channel.buffer(reach,quad_segs=64).intersection(box(window.bounds[0],tip-gap,window.bounds[2],channel.bounds[3]-2*uncertainty)).intersection(domain)
 local=surface_parts(source.intersection(domain));attachments=[]
 for sid,seed in zip(source_ids,seeds):
  pieces=[g for g in local if g.intersection(seed).area>0]
  if len(pieces)!=1:raise ValueError('PIN_SOURCE_ATTACHMENT_NOT_UNIQUE')
  contacts=[]
  for row in rows:
   original=p.geometry(store,row['original_ref'])
   if original.intersection(pieces[0]).area>0:contacts.append(dict(source_id=row['source_id'],original_geometry_sha256=row['original_ref']['sha256']))
  attachments.append(dict(pin_source_id=sid,original_local_contacts=contacts))
 return pin.Slot(source_sha256,spec['slot_id'],tuple(source_ids),domain,source,tuple(seeds),tuple(attachments),protected_void=void,spacing_domain=spacing)

def initialize(store,binding,source,original,scene=None):
 pin.ACTIVE=None;run=store.root.parent;path=run/'PIN_SEPARATION_POLICY.json'
 if not path.exists():return None
 policy=p.load(path)
 if policy['schema']!=pin.SCHEMA or policy['working_source_sha256']!=binding['source_ref']['sha256']:raise ValueError('PIN_WORKING_SOURCE_BINDING_CHANGED')
 registry=p.load(p.ROOT/'contracts/pin_separation/settings.json')
 if policy['registry_sha256']!=digest(canonical(registry)) or policy['declaration']!=registry['sources'].get(policy['raw_source_sha256']):raise ValueError('PIN_ORIGINAL_INTENT_REGISTRY_CHANGED')
 spec=policy['declaration']
 if spec is None:return None
 if spec['raw_source_sha256']!=policy['raw_source_sha256']:raise ValueError('PIN_ORIGINAL_SOURCE_DECLARATION_CHANGED')
 cache={}
 slots=[rooted_slot(source,policy['raw_source_sha256'],original['objects'],store,s,p.CONSTRUCTION_GAP_MM,cache)for s in spec['slots']]
 rule=pin.Rule(slots,construction_gap=p.CONSTRUCTION_GAP_MM,finished_gap=p.HARD_GAP_MM)
 if scene is not None:
  for entry in reversed(scene['lineage']):
   if 'pin_separation_state'in entry:rule.restore(store,entry['pin_separation_state']);break
 if scene is not None:
  _,material,_=p.operands(store,scene);rule.require(p.unary_union(list(material.values())),scope='stage_entry')
 pin.ACTIVE=rule;return rule
