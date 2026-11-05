"""Source-bound stages under the explicitly versioned component-clearance profile."""
from . import pipeline as p
from src import component_clearance as cc
from src.stage_abi.loaded_geometry import GeometryMemo
from src.growth_void_remedy_v09 import surface_parts
from shapely import STRtree

def initialize(store,binding,scene=None):
 if (store.root.parent/'LEGACY_REFERENCE_JOB.json').exists():
  cc.ACTIVE=None;return None
 original=store.get_json(binding['scene_ref'],kind='scene');rows,current,_=p.operands(store,original)
 raw=store.get(binding['source_ref'],kind='gerber-source');parsed,_,_=p.source_profile.parse_source(raw)
 source=p.affine_scale(p.source_profile.ordered((p.source_profile.object_geometry(o)[0],o.polarity_dark)for o in parsed.objects),1,-1,origin=(0,0));context=cc.bind(source,binding['source_ref']['sha256'],current)
 if scene is not None:
  context.register_scene(store,scene)
  if len(scene['lineage'])>1:reserve_prior(context,store)
 return context

def run_t01(store,scene,binding):
 if cc.ACTIVE is None:return p.legacy_run_t01(store,scene,binding)
 ctx=cc.ACTIVE;sites=p.t01_sites(store,scene);_,current,_=p.operands(store,scene);meta=binding['width_metadata_rows'];shapes=[current[r['id']]for r in meta];raw=store.get(binding['width_metadata_encoding_ref'],kind='kernel-width-data');spec=p.specification();policy=dict(canonical_t01=p.marker(),family=p.marker()['family'],settings=spec['settings'],diameter_classes_mm=spec['diameter_classes_mm'])
 legacy=p.legacy_run_t01(store,scene,binding);allocation=legacy['allocation'];targets={d['source_id']:d['proposed_radius_mm']for d in legacy['decisions']};settings=p.CropSettings(**spec['settings']);square=set()
 legacy_scene=store.get_json(legacy['output_scene_ref'],kind='scene');_,current,_=p.operands(store,legacy_scene);reserve_prior(ctx,store)
 after=dict(current);owners=ctx.project(current);memo=GeometryMemo(ctx.binding+'t01');decisions=[];priority=set(allocation['priorities_by_physical_component'].values());order=sorted(priority)+[s['source_id']for s in sites if s['source_id']not in priority];byid={s['source_id']:s for s in sites};gap=p.CONSTRUCTION_GAP_MM+.00002
 for sid in order:
  site=byid[sid];core=site['core'];floor=current[sid];radius=targets[sid];owner=ctx.owner(sid,core);cap=core.union(p.Point(*site['center']).buffer(radius,quad_segs=settings.qsegs));reason=None
  if radius==site['radius']:candidate=core
  else:
   ids=list(owners);tree=STRtree([owners[o]for o in ids]);foreign=[o for j in sorted(map(int,tree.query(cap.buffer(gap).envelope)))if(o:=ids[j])!=owner]
   foreign=[o for o in ctx.index.ids if o!=owner and (owners[o].intersects(cap.buffer(gap).envelope)or ctx.reserved[o].intersects(cap.buffer(gap).envelope))]
   foreign_bodies={o:owners[o].union(ctx.reserved[o])for o in foreign}
   forbidden=p.unary_union([memo.buffer(foreign_bodies[o],gap,quad_segs=128)for o in foreign])
   optional=cap.difference(core);existing=optional.intersection(ctx.cores[owner]);new=optional.difference(ctx.cores[owner]).difference(forbidden)
   pieces=[g for g in surface_parts(existing.union(new))if g.area>0 and g.distance(core)<=1e-9]
   candidate=p.unary_union([floor,core.buffer(1e-10,quad_segs=128),*pieces])
   if sid in priority and candidate.symmetric_difference(cap).area>settings.area_epsilon:candidate=floor;reason='COMPLETE_ROUND_REQUIRED'
   if not candidate.covers(core):candidate=floor;reason='EXACT_CORE_CONTAINMENT'
   if candidate.difference(cap).area>settings.area_epsilon:raise ValueError('T01_SELECTED_ENVELOPE_EXCEEDED')
   assembled=owners[owner].union(candidate);delta=assembled.difference(owners[owner]);bad=[o for o in foreign if not delta.is_empty and delta.distance(foreign_bodies[o])+1e-12<p.CONSTRUCTION_GAP_MM]
   if bad:candidate=floor;reason='FOREIGN_ORIGINAL_COMPONENT_GUARD'
  owners[owner]=owners[owner].union(candidate)
  for alias in site['aliases']:after[alias]=candidate
  decisions.append(dict(source_id=sid,aliases=site['aliases'],original_owner_id=owner,source_radius_mm=site['radius'],selected_radius_mm=radius,added_area_mm2=candidate.difference(core).area,decision='KEEP'if p.to_wkb(candidate)==p.to_wkb(core)else'GROW_CONNECTED_COPPER',reason=reason,source_core_preserved=candidate.covers(core),selected_cap_sha256=p.digest(p.to_wkb(cap))))
  if len(decisions)%64==0:print(p.canonical(dict(stage='t01',sites_done=len(decisions),sites=len(sites))).decode(),flush=True)
 lands=[dict(id=s['source_id'],original=s['core'],candidate=after[s['source_id']],native_source_kind='gr_circle',native_stroke_width_mm=0.)for s in sites];omit={a for s in sites for a in s['aliases']};fixed=[dict(id=s,geometry=g,trace_width_mm=next(r['trace_width_mm']for r in meta if r['id']==s))for s,g in current.items()if s not in omit]
 full=p.PreparedLandScene(lands,fixed).check(lands,materialize_scene=True)
 if not full['passed']:raise ValueError('T01_FULL_COMPONENT_SCENE_FAILED:'+str(full['failures'][:2]))
 for s in sites:
  if s['source_id']in allocation['contained_keep_source_ids']and p.to_wkb(after[s['source_id']])!=p.to_wkb(s['core']):raise ValueError('T01_CONTAINED_SOURCE_CHANGED')
 memo.close();ref=p.artifact_scene(store,scene,after,'t01-connected-copper')
 return dict(output_scene_ref=ref,legacy_geometry_compilation_sha256=p.digest(p.canonical(legacy)),legacy_reference_scene_ref=legacy['output_scene_ref'],allocation=allocation,allocation_basis='Fresh unchanged canonical source-wide allocation; a conservative selected-radius ceiling, not an assertion of legacy primitive-clearance construction parity.',construction_policy=cc.POLICY,ownership_sha256=ctx.index.fingerprint,decisions=decisions,full_surface_check=full,summary=dict(circle_sites=len(sites),circle_occurrences=sum(len(s['aliases'])for s in sites),grown=sum(d['added_area_mm2']>1e-10 for d in decisions),contained_keep=len(allocation['contained_keep_source_ids'])))

def run_t03(store,scene,binding,t01):
 if cc.ACTIVE is None:return p.legacy_run_t03(store,scene,binding,t01)
 ctx=cc.ACTIVE;original=store.get_json(binding['scene_ref'],kind='scene');rows,before,_=p.operands(store,original);_,current,_=p.operands(store,scene);records=[]
 for sid,row in sorted(rows.items()):
  if row['kind']!='stroke':continue
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
 whole=ctx.index.source.union(p.unary_union(pieces));groups=cc.OriginalOwners(whole);reserved={}
 for g in groups.owners:
  ids=ctx.index.membership(g)
  if len(ids)!=1 or ids[0]in reserved:raise ValueError('PRIOR_COPPER_OWNER_PARTITION_CHANGED')
  reserved[ids[0]]=g
 if set(reserved)!=set(ctx.index.ids):raise ValueError('PRIOR_COPPER_OWNERS_INCOMPLETE')
 ctx.reserved=reserved;ctx.reservation_sha256=p.digest(body);ctx.binding=p.digest(p.canonical([ctx.binding,ctx.reservation_sha256]))
 store.put('reserved-gerber',body)
