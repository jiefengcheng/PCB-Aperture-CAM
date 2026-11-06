"""Inclusive completion directly updates one reusable material surface per owner."""
import collections
from . import pipeline as p
from src import component_clearance as cc
from src.component_voids import plan,parts,holes,joined
from src.component_absorption import absorb
from src.growth_void_encoding import filled_surface
from src.pin_separation import native_parent as canonical_parent
from src.pcb_data_abi.geometry import GRID_MM
from src.native_grid_reference import reference as export_reference,normalize as native_grid

def overlap_region(patch,owner,contract=None):
 from shapely.errors import GEOSException
 if patch.is_empty or owner.is_empty or not patch.is_valid or not owner.is_valid or patch.geom_type not in('Polygon','MultiPolygon')or owner.geom_type not in('Polygon','MultiPolygon'):raise ValueError('VALID_FILLED_OVERLAP_OPERANDS_REQUIRED')
 try:return patch.union(owner.intersection(patch.buffer(.000004,quad_segs=32))),'ORIGINAL_REDUNDANT_OWNER_OVERLAP'
 except GEOSException as original_error:
  # A grid-tagged proposal and an untagged owner can make GEOS apply different
  # precision rules to identical coordinates. Remove only transient metadata;
  # WKB retains every coordinate, ring and positive surface.
  from shapely import from_wkb,to_wkb
  plain_patch=from_wkb(to_wkb(patch));plain_owner=from_wkb(to_wkb(owner))
  try:
   support=plain_owner.intersection(plain_patch.buffer(.000004,quad_segs=32));region=plain_patch.union(support)
   target=plain_owner.union(plain_patch)
   if contract is None:
    from src.component_voids import RemedyContract
    contract=RemedyContract()
   epsilon=contract.area_epsilon_mm2
   if region.is_valid and plain_patch.difference(region).area<=epsilon and support.difference(plain_owner).area<=epsilon and plain_owner.union(region).symmetric_difference(target).area<=epsilon:return region,'IDENTICAL_COORDINATES_WITHOUT_TRANSIENT_PRECISION_TAGS'
  except GEOSException:raise original_error
  raise ValueError('ENCODING_OVERLAP_CHANGES_QUALIFIED_OWNER_COPPER')

def prepare_region(store,region,owner,owner_id=None,contract=None,foreign=()):
 from src.u05_board.coverage import integral_context
 ctx=integral_context()
 if ctx is None:return region,dict(status="LEGACY_PROFILE_UNCHANGED")
 if contract is None:
  from .component_policy import read_job
  contract=read_job(store.root.parent)[1][0]
 if owner_id is None:owner_id=ctx.index.membership(owner)[0]
 # Original source features and all actual/reserved foreign copper participate.
 foreign=[*foreign,*[('source:'+o,g)for o,g in ctx.cores.items()if o!=owner_id],*[('reserved:'+o,g)for o,g in ctx.reserved.items()if o!=owner_id],*[('checking-envelope:'+o,g)for o,g in getattr(ctx,'checking_envelopes',{}).items()if o!=owner_id]]
 return absorb(region,owner,ctx.cores[owner_id],foreign,contract)

def native_before(store,scene,binding,junction_result=None):
 from .export_absorption import prepare_export_region
 from .component_policy import read_job
 contract=read_job(store.root.parent)[1][0];context=cc.ACTIVE;source_scene=store.get_json(binding['scene_ref'],kind='scene');source_rows={r['source_id']:r for r in source_scene['objects']};references=[]
 for row in scene['objects']:
  sid=row['source_id']
  if row['kind']in('trace','junction_addition'):continue
  if sid in source_rows and row['geometry_ref']==source_rows[sid]['geometry_ref']:continue
  g=p.geometry(store,row['geometry_ref'])
  for part in parts(native_grid(g)):
   ref,_=export_reference(part);references.append(canonical_parent(ref,grid_mm=GRID_MM))
 if junction_result is not None:
  prepared=store.get_json(junction_result['plan']['scene_ref'],kind='scene');policy=store.get_json(junction_result['plan']['policy_ref'],kind='policy');adapter=p.CoverageAdapter(p.box(*scene['viewport_mm']))
  try:
   for decision in junction_result['candidate']['decisions']:
    if decision['status']!='GROWN':continue
    owner,_,domain,foreign=adapter._operands(store,prepared,policy,junction_result['plan']['details'],decision);region,_=prepare_export_region(store,junction_result,adapter,owner,domain,decision,foreign)
    for part in parts(native_grid(region)):
     ref,_=export_reference(part);references.append(canonical_parent(ref,grid_mm=GRID_MM))
  finally:adapter.close()
 return context.index.source.union(joined(references))

def finish(store,scene,binding,stage,junction_result=None,mode='unit'):
 if getattr(cc.ACTIVE,'functional',None)is not None:
  from .channel_finish import finish
  return finish(store,scene,binding,stage,junction_result,mode)
 from .component_policy import read_job
 context=cc.ACTIVE;context.register_scene(store,scene);source=context.index.source;before=native_before(store,scene,binding,junction_result);current=before;rounds=[];feature_counts=collections.Counter();absorptions=[];support_modes=collections.Counter()
 policy,contracts=read_job(store.root.parent)
 if policy['settings']['representation']!='ABSORB_INTO_ORIGINAL_OWNER_SURFACE':raise ValueError('OWNER_ABSORPTION_DEFAULT_REQUIRED')
 source_parts=parts(source);reservations={i:context.reserved[context.index.membership(g)[0]]for i,g in enumerate(source_parts)if context.index.membership(g)[0]in context.reserved}
 aggregates={};oldrows={};updated=set();new_area=collections.Counter();partials=[]
 for row in scene['objects']:
  if row['kind']=='component_remedy':
   own=row['metadata']['original_owner_id'];aggregates[own]=p.geometry(store,row['geometry_ref']);oldrows[own]=row
   partials.extend(row['metadata'].get('approved_partial_pockets',[]))
 prefix=None
 if stage=='t04'and (store.root.parent/'REPAIR_PREFIX.json').exists():
  prefix=p.load(store.root.parent/'REPAIR_PREFIX.json');current=p.geometry(store,prefix['current_native_ref']);aggregates={o:p.geometry(store,r)for o,r in prefix['owner_aggregate_refs'].items()};updated.update(aggregates)
  from .native_component_checks_final import clearance
  native_owned={context.index.membership(g)[0]:g for g in parts(current)}
  if len(native_owned)!=len(context.index.ids)or set(native_owned)!=set(context.index.ids):raise ValueError('RETAINED_REPAIR_PREFIX_PARTITION_CHANGED')
  base_owned={context.index.membership(g)[0]:g for g in parts(before)}
  checked=clearance(base_owned,native_owned)
  p.save(store.root.parent/'repair_prefix_audits'/(mode+'.json'),dict(status='PASS',source_sha256=context.source_hash,prefix_sha256=p.digest((store.root.parent/'REPAIR_PREFIX.json').read_bytes()),physical_clearance=checked,components=len(native_owned),source='Retained successful whole-round construction checkpoints; failed full T04 outcome unchanged'))
  rounds.append(dict(status='RETAINED_SUCCESSFUL_CONSTRUCTION_PREFIX',radii_mm=[.04,.08],feature_count='NOT_RECORDED_BY_OLD_CHECKPOINT',owner_surfaces=len(aggregates)))
 for contract in contracts:
  radius=contract.notch_radius_mm
  if prefix is not None and radius<=.08:continue
  def progress(r):
   if r['component']%32==0:print(p.canonical(dict(stage=stage+'_inclusive',radius_mm=radius,**r)).decode(),flush=True)
  from .checking_envelopes import indexed
  report,fills,expected=plan(source,current,contract,checkpoint=progress,reserved=reservations,partial_strategy=policy['settings'].get('large_pocket_strategy'),approved_partials=partials,clearance_only=indexed(context,source_parts))
  partials=report.get('approved_partial_pockets',partials)
  for spec in partials:
   own=context.index.membership(source_parts[spec['source_component']])[0]
   if spec.get('original_owner_id',own)!=own or spec.get('original_source_sha256',context.source_hash)!=context.source_hash:raise ValueError('FROZEN_PARTIAL_POCKET_SOURCE_OWNER_CHANGED')
   spec.update(original_owner_id=own,original_source_sha256=context.source_hash)
  owners=parts(current);mapping=[context.index.membership(g)[0]for g in owners];proposals=collections.defaultdict(list)
  physical={context.index.membership(g)[0]:g for g in parts(expected)}
  for item in fills:
   patch=item['geometry'];owner=owners[item['owner']];own=mapping[item['owner']]
   raw_region,support_mode=overlap_region(patch,owner,contract);support_modes[support_mode]+=1
   try:region=filled_surface(raw_region)
   except ValueError:
    p.save(store.root.parent/'encoding_failure'/(stage+'_'+mode+'.json'),dict(raw_region_ref=p.geomref(store,raw_region),logical_patch_ref=p.geomref(store,patch),owner_ref=p.geomref(store,owner),original_owner_id=own,radius_mm=radius))
    raise
   from src.growth_remedy_constraints import encoded_remedy
   encoded=joined([canonical_parent(export_reference(g)[0],grid_mm=GRID_MM)for g in parts(native_grid(region))]);pin_check=encoded_remedy(patch,encoded,owner)
   if pin_check is not None and not pin_check['passed']:
    report.setdefault('native_pin_encoding_rejections',[]).append(dict(status='KEEP_PROTECTED_PIN_ENCODING',check=pin_check));continue
   proposals[own].append(region);feature_counts[item['kind']]+=1;new_area[own]+=patch.area
  encoded_by_owner={}
  for own,regions in sorted(proposals.items()):
   combined=joined([*([aggregates[own]]if own in aggregates else[]),*regions]);foreign=[('current:'+o,g)for o,g in physical.items()if o!=own]+[('reserved:'+o,g)for o,g in context.reserved.items()if o!=own]+[('checking-envelope:'+o,g)for o,g in getattr(context,'checking_envelopes',{}).items()if o!=own]
   combined,receipt=absorb(combined,physical[own],context.cores[own],foreign,contract);
   from src.growth_remedy_constraints import require_remedy
   require_remedy(combined,physical[own],scope='absorbed_remedy')
   aggregates[own]=combined;updated.add(own)
   absorptions.append(dict(original_owner_id=own,radius_mm=radius,**receipt))
   encoded_by_owner[own]=[]
   for piece in parts(native_grid(combined)):
    ref,_=export_reference(piece);encoded_by_owner[own].append(canonical_parent(ref,grid_mm=GRID_MM))
  owned_current={context.index.membership(g)[0]:g for g in parts(current)}
  for own,values in encoded_by_owner.items():owned_current[own]=owned_current[own].union(joined(values))
  current=joined(list(owned_current.values()))
  from src.pin_separation import require as require_pin
  require_pin(current,finished=True,scope='absorbed_encoded_round')
  if partials:
   from src.partial_pocket_remedy import validate as validate_partial
   for spec in partials:
    initial,remaining,carrier,ring=validate_partial(spec,contract);amount=current.intersection(initial).area
    if amount>spec['decision']['maximum_added_area_mm2']or current.intersection(remaining.buffer(-contract.file_uncertainty_mm)).area>contract.area_epsilon_mm2:raise ValueError('FROZEN_PARTIAL_POCKET_CUMULATIVE_CAP_OR_OPENING_CHANGED')
  checkpoint=store.root.parent/'completion_checkpoints'/(stage+'_'+mode+'_'+str(radius)+'.json')
  p.save(checkpoint,dict(current_native_ref=p.geomref(store,current),owner_aggregate_refs={o:p.geomref(store,g)for o,g in aggregates.items()},round_index=len(rounds),policy='Successful whole-round construction checkpoint, not a final acceptance'))
  rounds.append(dict(radius_mm=radius,plan=report,fills=len(fills),owner_surfaces_updated=len(proposals),added_native_area_mm2=current.difference(before).area))
 additions=[];changes={};metadata={};records=[]
 for own in sorted(updated):
  sid='component-completion:'+own;region=aggregates[own];ref=p.geomref(store,region);md=dict(origin='original-component-owner-surface-absorption',original_owner_id=own,original_source_sha256=context.source_hash,stage=stage,kind='owner_surface_absorption',nominal_width_mm=0.,original_width_mm=0.,qualified_land=False,representation='EXISTING_COMPONENT_SURFACE_EXTENDED; no per-feature material objects',logical_patch_ref=ref)
  owned_partials=[s for s in partials if s['original_owner_id']==own]
  if owned_partials:md['approved_partial_pockets']=owned_partials
  if own in oldrows:
   if oldrows[own]['source_id']!=sid:raise ValueError('COMPONENT_SURFACE_IDENTITY_CHANGED')
   changes[sid]=region;metadata[sid]=md
  else:additions.append(dict(source_id=sid,kind='component_remedy',geometry_ref=ref,original_ref=p.geomref(store,context.cores[own]),metadata=md))
  context.assign(sid,region,[own]);records.append(dict(source_id=sid,original_owner_id=own,kind='owner_surface_absorption',geometry_ref=ref,logical_patch_ref=ref,planned_fill_area_mm2=new_area[own]))
 scene_ref=p.artifact_scene(store,scene,changes,stage+'-owner-surface-absorption',metadata=metadata,additions=additions)
 return dict(output_scene_ref=scene_ref,source_sha256=context.source_hash,ownership_policy=cc.POLICY,representation='ABSORB_INTO_ORIGINAL_OWNER_SURFACE',rounds=rounds,fills=records,feature_counts=dict(feature_counts),encoding_support_assembly=dict(support_modes),microscopic_absorptions=absorptions,before_native_ref=p.geomref(store,before),after_native_ref=p.geomref(store,current),retained_repair_prefix=None if prefix is None else dict(radii_mm=[.04,.08],owner_surfaces=len(prefix['owner_aggregate_refs']),feature_counts='NOT_RECORDED_IN_OLD_CHECKPOINT'),summary=dict(fills=sum(feature_counts.values()),owner_surfaces_updated=len(updated),holes=feature_counts['hole'],notches=feature_counts['notch'],microscopic_holes_absorbed=sum(r['holes_absorbed']for r in absorptions),added_area_mm2=current.difference(before).area),basis='Frozen original owners; source voids, all foreign copper, local connected spans, <=20% shortage and native checks retained. Default extends one reusable owner surface, with no per-feature geometry artifact.')
