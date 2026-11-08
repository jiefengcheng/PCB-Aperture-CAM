"""Source-bound stages under the explicitly versioned component-clearance profile."""
from . import pipeline as p
from src import component_clearance as cc
from src.stage_abi.loaded_geometry import GeometryMemo
from src.growth_void_remedy_v09 import surface_parts
from shapely import STRtree
from .checking_envelopes import constraint

def initialize(store,binding,scene=None):
 from src.t04_width_fence import restore as restore_width_fence
 restore_width_fence(store,scene)
 from src.t02_shared_gaps import restore as restore_shared_gaps
 restore_shared_gaps(store,scene)
 original=store.get_json(binding['scene_ref'],kind='scene');rows,current,_=p.operands(store,original)
 raw=store.get(binding['source_ref'],kind='gerber-source');parsed,_,_=p.source_profile.parse_source(raw)
 source=p.affine_scale(p.source_profile.ordered((p.source_profile.object_geometry(o)[0],o.polarity_dark)for o in parsed.objects),1,-1,origin=(0,0))
 from .pin_policy import initialize as initialize_pin
 initialize_pin(store,binding,source,original,scene)
 from src import source_channel_scope
 functional=source_channel_scope.bind(source,binding['source_ref']['sha256'],original,store,integral=(store.root.parent/'SOURCE_ASSEMBLY_BINDING.json').exists())
 if (store.root.parent/'LEGACY_REFERENCE_JOB.json').exists():
  from .checking_envelopes import initialize as initialize_checking
  initialize_checking(store,binding,scene,functional=functional)
  cc.ACTIVE=None;return None
 context=cc.bind(source,binding['source_ref']['sha256'],current);context.functional=functional
 if functional is not None:functional.physical_context=context
 if scene is not None:
  context.register_scene(store,scene)
  if functional is not None:functional.register_scene(store,scene)
  if len(scene['lineage'])>1:reserve_prior(context,store)
 from .checking_envelopes import initialize as initialize_checking
 initialize_checking(store,binding,scene,physical=context,functional=functional)
 return context


def guard_legacy_floor(core,floor,owner_core,foreign,complete_round):
 """Recheck only inherited new copper; original source is never trimmed."""
 delta=floor.difference(owner_core)
 distances=[delta.distance(g)for g in foreign]if not delta.is_empty else[]
 if not distances or min(distances)+1e-12>=p.CONSTRUCTION_GAP_MM:return floor,None
 gap=p.CONSTRUCTION_GAP_MM+.00002
 if complete_round:
  corrected=core
  mode='KEEP_SOURCE_CORE_WHEN_INHERITED_COMPLETE_ROUND_IS_UNSAFE'
 else:
  forbidden=p.unary_union([g.buffer(gap,quad_segs=128)for g in foreign])
  material=floor.difference(forbidden)
  pieces=[g for g in surface_parts(material)if g.area>0 and g.distance(core)<=1e-9]
  corrected=p.unary_union([core,*pieces])
  mode='RECLIP_ONLY_UNSAFE_INHERITED_NEW_COPPER'
 if not corrected.is_valid or not corrected.covers(core)or corrected.difference(floor).area>p.EPS:raise ValueError('T01_INHERITED_FLOOR_SOURCE_OR_SCOPE_CHANGED')
 added=corrected.difference(owner_core)
 remaining=[added.distance(g)for g in foreign]if not added.is_empty else[]
 if remaining and min(remaining)+1e-12<p.CONSTRUCTION_GAP_MM:raise ValueError('T01_CORRECTED_FLOOR_FOREIGN_GUARD_FAILED')
 return corrected,dict(mode=mode,original_new_copper_gap_mm=min(distances),corrected_new_copper_gap_mm=min(remaining)if remaining else None,removed_optional_area_mm2=floor.difference(corrected).area,source_core_preserved=True,construction_gap_mm=p.CONSTRUCTION_GAP_MM)

def t01_land_checker(lands,fixed):
 """Use exact positive proposals, not numerical spurs on re-unioned old copper."""
 checker=p.PreparedLandScene(lands,fixed)
 checker.owner_added_material=checker._source_width_added_material
 return checker


def run_t01(store,scene,binding):
 if cc.ACTIVE is None:return p.legacy_run_t01(store,scene,binding)
 ctx=cc.ACTIVE;sites=p.t01_sites(store,scene);_,current,_=p.operands(store,scene);meta=binding['width_metadata_rows'];shapes=[current[r['id']]for r in meta];raw=store.get(binding['width_metadata_encoding_ref'],kind='kernel-width-data');spec=p.specification();policy=dict(canonical_t01=p.marker(),family=p.marker()['family'],settings=spec['settings'],diameter_classes_mm=spec['diameter_classes_mm'])
 legacy=p.legacy_run_t01(store,scene,binding);allocation=legacy['allocation'];targets={d['source_id']:d['proposed_radius_mm']for d in legacy['decisions']};settings=p.CropSettings(**spec['settings']);square=set()
 legacy_scene=store.get_json(legacy['output_scene_ref'],kind='scene');_,current,_=p.operands(store,legacy_scene);reserve_prior(ctx,store)
 functional=getattr(ctx,'functional',None);functional_owned=functional.project(current)if functional is not None else{}
 floor_repairs=[]
 owners=ctx.project(current);ids=list(owners);constraints={o:constraint(ctx,o,owners[o])for o in ids};tree=STRtree([constraints[o]for o in ids])
 for site in sites:
  sid=site['source_id'];core=site['core'];floor=current[sid];own=ctx.owner(sid,core)
  foreign=[constraints[ids[j]]for j in sorted(map(int,tree.query(floor.buffer(p.CONSTRUCTION_GAP_MM+.00002).envelope)))if ids[j]!=own]
  integral_core=ctx.cores[own]
  if functional is not None:
   channel=functional.owner(sid,core);integral_core=functional.cores[channel]
   foreign.extend(constraint(functional,o,g) for o,g in functional_owned.items()if o!=channel and g.intersects(floor.buffer(p.CONSTRUCTION_GAP_MM+.00002).envelope))
  corrected,proof=guard_legacy_floor(core,floor,integral_core,foreign,sid in set(allocation['priorities_by_physical_component'].values()))
  if proof is not None:
   for alias in site['aliases']:current[alias]=corrected
   if functional is not None:functional_owned=functional.project(current)
   owners[own]=ctx.project(current)[own];constraints[own]=constraint(ctx,own,owners[own]);tree=STRtree([constraints[o]for o in ids]);floor_repairs.append(dict(source_id=sid,**proof))
 after=dict(current);owners=ctx.project(current);memo=GeometryMemo(ctx.binding+'t01');decisions=[];priority=set(allocation['priorities_by_physical_component'].values());order=sorted(priority)+[s['source_id']for s in sites if s['source_id']not in priority];byid={s['source_id']:s for s in sites};gap=p.CONSTRUCTION_GAP_MM+.00002
 for sid in order:
  site=byid[sid];core=site['core'];floor=current[sid];radius=targets[sid];owner=ctx.owner(sid,core);cap=core.union(p.Point(*site['center']).buffer(radius,quad_segs=settings.qsegs));reason=None
  if radius==site['radius']:candidate=core
  else:
   ids=list(owners);tree=STRtree([owners[o]for o in ids]);foreign=[o for j in sorted(map(int,tree.query(cap.buffer(gap).envelope)))if(o:=ids[j])!=owner]
   foreign=[o for o in ctx.index.ids if o!=owner and (constraint(ctx,o,owners[o]).intersects(cap.buffer(gap).envelope))]
   foreign_bodies={o:constraint(ctx,o,owners[o])for o in foreign}
   integral_core=ctx.cores[owner]
   if functional is not None:
    channel=functional.owner(sid,core);integral_core=functional.cores[channel]
    for o,g in functional_owned.items():
     if o==channel:continue
     body=constraint(functional,o,g)
     if body.intersects(cap.buffer(gap).envelope):foreign_bodies['functional:'+o]=body
   forbidden=p.unary_union([memo.buffer(g,gap,quad_segs=128)for g in foreign_bodies.values()])
   optional=cap.difference(core);existing=optional.intersection(integral_core);new=optional.difference(integral_core).difference(forbidden)
   pieces=[g for g in surface_parts(existing.union(new))if g.area>0 and g.distance(core)<=1e-9]
   candidate=p.unary_union([floor,core.buffer(1e-10,quad_segs=128),*pieces])
   if sid in priority and candidate.symmetric_difference(cap).area>settings.area_epsilon:candidate=floor;reason='COMPLETE_ROUND_REQUIRED'
   if not candidate.covers(core):candidate=floor;reason='EXACT_CORE_CONTAINMENT'
   if candidate.difference(cap).area>settings.area_epsilon:raise ValueError('T01_SELECTED_ENVELOPE_EXCEEDED')
   assembled=owners[owner].union(candidate);delta=assembled.difference(owners[owner]);bad=[o for o in foreign if not delta.is_empty and delta.distance(foreign_bodies[o])+1e-12<p.CONSTRUCTION_GAP_MM]
   if functional is not None:
    functional_delta=candidate.difference(functional_owned[channel]);bad.extend(o for o,g in foreign_bodies.items()if o.startswith('functional:')and not functional_delta.is_empty and functional_delta.distance(g)+1e-12<p.CONSTRUCTION_GAP_MM)
   if bad:candidate=floor;reason='FOREIGN_ORIGINAL_COMPONENT_GUARD'
  from src import pin_separation as pin
  if pin.ACTIVE is not None:
   pin_proof=pin.ACTIVE.growth_parts(after.values(),[g for s,g in after.items()if s not in site['aliases']]+[candidate])
   if not pin_proof['passed']:candidate=floor;reason='PROTECTED_PIN_SEPARATION_GROWTH'
  if functional is not None:
   channel=functional.owner(sid,core);functional_owned[channel]=functional_owned[channel].union(candidate)
  owners[owner]=owners[owner].union(candidate)
  for alias in site['aliases']:after[alias]=candidate
  decisions.append(dict(source_id=sid,aliases=site['aliases'],original_owner_id=owner,source_radius_mm=site['radius'],selected_radius_mm=radius,added_area_mm2=candidate.difference(core).area,decision='KEEP'if p.to_wkb(candidate)==p.to_wkb(core)else'GROW_CONNECTED_COPPER',reason=reason,source_core_preserved=candidate.covers(core),selected_cap_sha256=p.digest(p.to_wkb(cap))))
  if len(decisions)%64==0:print(p.canonical(dict(stage='t01',sites_done=len(decisions),sites=len(sites))).decode(),flush=True)
 lands=[dict(id=s['source_id'],original=s['core'],candidate=after[s['source_id']],native_source_kind='gr_circle',native_stroke_width_mm=0.)for s in sites];omit={a for s in sites for a in s['aliases']};fixed=[dict(id=s,geometry=g,trace_width_mm=next(r['trace_width_mm']for r in meta if r['id']==s))for s,g in current.items()if s not in omit]
 checker=t01_land_checker(lands,fixed)
 from src.t01_region_contacts import install_prepared_ports
 region_ports=install_prepared_ports(checker,meta)
 full=checker.check(lands,materialize_scene=True)
 if region_ports:full['original_region_attachment_ports']=region_ports
 if not full['passed']:raise ValueError('T01_FULL_COMPONENT_SCENE_FAILED:'+str(full['failures'][:2]))
 for s in sites:
  if s['source_id']in allocation['contained_keep_source_ids']and p.to_wkb(after[s['source_id']])!=p.to_wkb(s['core']):raise ValueError('T01_CONTAINED_SOURCE_CHANGED')
  if s['source_id']in allocation['circle_overlap_keep_source_ids']and p.to_wkb(after[s['source_id']])!=p.to_wkb(s['core']):raise ValueError('T01_OVERLAP_KEEP_SOURCE_CHANGED')
 memo.close();ref=p.artifact_scene(store,scene,after,'t01-connected-copper')
 return dict(output_scene_ref=ref,legacy_geometry_compilation_sha256=p.digest(p.canonical(legacy)),legacy_floor_foreign_guard_repairs=floor_repairs,legacy_reference_scene_ref=legacy['output_scene_ref'],allocation=allocation,allocation_basis='Fresh unchanged canonical source-wide allocation; a conservative selected-radius ceiling, not an assertion of legacy primitive-clearance construction parity.',construction_policy=cc.POLICY,ownership_sha256=ctx.index.fingerprint,decisions=decisions,full_surface_check=full,summary=dict(circle_sites=len(sites),circle_occurrences=sum(len(s['aliases'])for s in sites),grown=sum(d['added_area_mm2']>1e-10 for d in decisions),contained_keep=len(allocation['contained_keep_source_ids'])))

def run_t03(store,scene,binding,t01):
 if cc.ACTIVE is None:return p.legacy_run_t03(store,scene,binding,t01)
 ctx=cc.ACTIVE;original=store.get_json(binding['scene_ref'],kind='scene');rows,before,_=p.operands(store,original);_,current,_=p.operands(store,scene);records=[]
 for sid,row in sorted(rows.items()):
  if not p.native_draw(row):continue
  if p.to_wkb(before[sid])!=p.to_wkb(current[sid]):raise ValueError('T03_SOURCE_TRACE_CHANGED')
  records.append(dict(source_id=sid,original_owner_id=ctx.owner(sid,before[sid]),original_geometry_ref=row['original_ref'],movement='NONE'))
 # Whole-source new-copper clearance is re-evaluated; internal trace/land ports
 # cannot turn a continuous original conductor into a foreign obstacle.
 owners=ctx.project(current);proof=ctx.complete_clearance(current,p.CONSTRUCTION_GAP_MM)
 if not proof['passed']:raise ValueError('T03_COMPONENT_CLEARANCE_FAILED:'+str(proof['failures'][:2]))
 return dict(output_scene_ref=store.put_json('scene',scene),records=records,full_source_clearance=proof,summary=dict(trace_occurrences=len(records),pairs=len(proof['pairs']),moved=0,disposition='NO_CHANGE_REQUIRED'))


def reserve_prior(ctx,store):
 if ctx.reservation_sha256 is not None:return
 from pathlib import Path
 from . import legacy_export as e
 run=store.root.parent;reference=p.load(run/'REFERENCE_BINDING.json');path=run/'reference/top.art.gbr';body=path.read_bytes()
 if p.digest(body)!=reference['generated_sha256']or reference['source_sha256']!=p.load(run/'source.json')['source_ref']['sha256']:raise ValueError('FRESH_REFERENCE_BINDING_CHANGED')
 parsed=e.parse(body);source_objects=p.load(run/'source.json')['source_objects']
 pieces=[p.affine_scale(p.source_profile.object_geometry(o)[0],1,-1,origin=(0,0))for o in parsed.objects[source_objects:]]
 whole=ctx.index.source.union(p.unary_union(pieces))
 from src.pin_separation import require as require_pin
 require_pin(whole,finished=True,scope='retained_prior')
 from src import pin_separation as pin
 if pin.ACTIVE is not None:pin.ACTIVE.reserve([whole],p.digest(body))
 groups=cc.OriginalOwners(whole);reserved={}
 for g in groups.owners:
  ids=ctx.index.membership(g)
  if len(ids)!=1 or ids[0]in reserved:raise ValueError('PRIOR_COPPER_OWNER_PARTITION_CHANGED')
  reserved[ids[0]]=g
 if set(reserved)!=set(ctx.index.ids):raise ValueError('PRIOR_COPPER_OWNERS_INCOMPLETE')
 ctx.reserved=reserved;ctx.reservation_sha256=p.digest(body);ctx.binding=p.digest(p.canonical([ctx.binding,ctx.reservation_sha256]))
 if getattr(ctx,'functional',None)is not None:
  from src.source_channel_scope import install_reserved
  sidecar=p.load(run/'REFERENCE_CHANNELS.json')
  from src import pin_separation as pin
  if pin.ACTIVE is not None and 'pin_separation_state'in sidecar:
   state=sidecar['pin_separation_state']
   if state['binding']!=pin.ACTIVE.binding:raise ValueError('PIN_REFERENCE_SOURCE_BINDING_CHANGED')
   prior=p.from_wkb(store.get(state['rejected_ref'],kind='geometry'));pin.ACTIVE.rejected=pin.ACTIVE.rejected.union(prior);pin.ACTIVE.rejected_count=max(pin.ACTIVE.rejected_count,state['rejected_count'])
  if reference.get('functional_channel_sidecar_sha256')!=p.digest(p.canonical(sidecar)):raise ValueError('NATIVE_CHANNEL_RESERVATION_SIDECAR_CHANGED')
  install_reserved(ctx.functional,store,sidecar,ctx.reservation_sha256)
  rows=[]
  for spec in sidecar.get('approved_partial_pockets',[]):
   channel=spec['original_channel_id'];own=spec['original_owner_id']
   from src.source_channel_scope import physical_owner
   if physical_owner(ctx.functional,channel,ctx)!=own:raise ValueError('REFERENCE_PARTIAL_PHYSICAL_CHANNEL_BINDING_CHANGED')
   ref=p.geomref(store,ctx.functional.reserved[channel]);rows.append(dict(source_id='reference-partial:'+channel,kind='component_remedy',original_ref=p.geomref(store,ctx.cores[own]),geometry_ref=ref,metadata=dict(original_owner_id=own,original_channel_id=channel,original_channel_witness_sha256=p.digest(p.to_wkb(ctx.functional.cores[channel])),original_source_sha256=ctx.source_hash,approved_partial_pockets=[spec])))
  if rows:ctx.register_scene(store,dict(objects=rows))
 for value in ctx.approved_partial_pockets.values():
  if value['protected_core'].intersection(reserved[value['spec']['original_owner_id']]).area>value['contract'].area_epsilon_mm2:raise ValueError('PROTECTED_PARTIAL_POCKET_CONFLICTS_WITH_PRIOR_POSITIVE_COPPER')
 store.put('reserved-gerber',body)
