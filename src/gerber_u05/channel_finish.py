"""Intra-step completion extends existing functional-channel material surfaces."""
import collections
from shapely import to_wkb,get_precision,set_precision
from . import pipeline as p
from src import component_clearance as cc
from src.component_voids import plan,parts,joined
from src.component_absorption import absorb
from src.growth_void_encoding import filled_surface
from src.native_grid_reference import reference as export_reference,normalize as native_grid
from src.source_channel_scope import physical_owner
from .channel_material import check_owned
from src.pin_separation import native_parent as profiled_parent
from src.pcb_data_abi.geometry import GRID_MM

def canonical_parent(reference,*,grid_mm):
 # Keep the existing pin-profile integer canonicalization, then remove only
 # GEOS precision metadata. A fixed-grid parent can otherwise make a mixed
 # union snap the unchanged analytic source. Native coordinates stay exact;
 # their serialization grid and every subsequent source/clearance check stay.
 value=profiled_parent(reference,grid_mm=grid_mm)
 if get_precision(value)==0:return value
 plain=set_precision(value,0)
 if to_wkb(value)!=to_wkb(plain):raise ValueError('NATIVE_PARENT_PRECISION_RESET_CHANGED_COORDINATES')
 return plain

def native_before_owned(store,scene,binding,junction_result=None):
 from .exporter import prepare_export_region
 scope=cc.ACTIVE.functional;scope.register_scene(store,scene);source_scene=store.get_json(binding['scene_ref'],kind='scene');source_rows={r['source_id']:r for r in source_scene['objects']};buckets={o:[g]for o,g in scope.cores.items()}
 for row in scene['objects']:
  sid=row['source_id']
  if row['kind']in('trace','junction_addition'):continue
  if sid in source_rows and row['geometry_ref']==source_rows[sid]['geometry_ref']:continue
  if sid in scope.frame_ids:raise ValueError('TEMPORARY_FRAME_NATIVE_CHANGE_NOT_ALLOWED')
  own=scope.owner(sid);g=p.geometry(store,row['geometry_ref'])
  for part in parts(native_grid(g)):buckets[own].append(canonical_parent(export_reference(part)[0],grid_mm=GRID_MM))
 if junction_result is not None:
  prepared=store.get_json(junction_result['plan']['scene_ref'],kind='scene');policy=store.get_json(junction_result['plan']['policy_ref'],kind='policy');adapter=p.CoverageAdapter(p.box(*scene['viewport_mm']))
  try:
   for decision in junction_result['candidate']['decisions']:
    if decision['status']!='GROWN':continue
    owner,_,domain,foreign=adapter._operands(store,prepared,policy,junction_result['plan']['details'],decision);region,_=prepare_export_region(store,junction_result,adapter,owner,domain,decision,foreign);own=scope.owner(decision['source_id'])
    for part in parts(native_grid(region)):buckets[own].append(canonical_parent(export_reference(part)[0],grid_mm=GRID_MM))
  finally:adapter.close()
 result={o:joined(v)for o,v in buckets.items()};check=check_owned(scope,result)
 if not check['passed']:raise ValueError('NATIVE_MODEL_FUNCTIONAL_PREDECESSOR_CLEARANCE_FAILED:'+str(check['failures'][:3]))
 return result

def finish(store,scene,binding,stage,junction_result=None,mode='unit'):
 from .component_policy import read_job
 from .component_finish import overlap_region
 physical=cc.ACTIVE;scope=physical.functional;physical.register_scene(store,scene);scope.register_scene(store,scene);policy,contracts=read_job(store.root.parent);owned=native_before_owned(store,scene,binding,junction_result);before=dict(owned);source=scope.channels.analytic_source;source_parts=parts(source);source_channels=[scope.index.membership(g)[0]for g in source_parts];rounds=[];aggregates={};oldrows={};partials=[v['spec']for v in scope.approved_partial_pockets.values()];counts=collections.Counter();area=collections.Counter();absorptions=[]
 for row in scene['objects']:
  if row['kind']=='component_remedy':
   if 'original_channel_id'not in row['metadata']:raise ValueError('COMPONENT_COMPLETION_CHANNEL_CERTIFICATE_REQUIRED')
   own=row['metadata']['original_channel_id'];aggregates[own]=p.geometry(store,row['geometry_ref']);oldrows[own]=row;
   for spec in row['metadata'].get('approved_partial_pockets',[]):
    known={s['pocket_id']:s for s in partials}
    if spec['pocket_id']in known and p.canonical(known[spec['pocket_id']])!=p.canonical(spec):raise ValueError('FROZEN_PARTIAL_POCKET_BUDGET_CHANGED')
    if spec['pocket_id']not in known:partials.append(spec)
 for contract in contracts:
  current=joined(list(owned.values()));reserved={i:scope.reserved[o]for i,o in enumerate(source_channels)if o in scope.reserved}
  def progress(r):
   if r['component']%32==0:print(p.canonical(dict(stage=stage+'_channel_inclusive',radius_mm=contract.notch_radius_mm,**r)).decode(),flush=True)
  from .checking_envelopes import indexed
  report,fills,expected=plan(source,current,contract,checkpoint=progress,reserved=reserved,partial_strategy=policy['settings'].get('large_pocket_strategy'),approved_partials=partials,clearance_only=indexed(scope,source_parts));partials=report.get('approved_partial_pockets',partials);current_parts=parts(current);mapping=[scope.index.membership(g)for g in current_parts]
  if any(len(ids)!=1 for ids in mapping):raise ValueError('CURRENT_FUNCTIONAL_CHANNEL_PARTITION_CHANGED')
  channels=[ids[0]for ids in mapping]
  for spec in partials:
   channel=source_channels[spec['source_component']];own=physical_owner(scope,channel,physical)
   if spec.get('original_channel_id',channel)!=channel:raise ValueError('FROZEN_PARTIAL_FUNCTIONAL_OWNER_CHANGED')
   spec.update(original_channel_id=channel,original_owner_id=own,original_source_sha256=physical.source_hash)
  proposals=collections.defaultdict(list)
  for item in fills:
   channel=channels[item['owner']];patch=item['geometry']
   if patch.intersection(scope.channels.frame).area>contract.area_epsilon_mm2:raise ValueError('CHANNEL_COMPLETION_DEPENDS_ON_TEMPORARY_FRAME')
   region,mode_name=overlap_region(patch,owned[channel],contract);region=filled_surface(region)
   from src.growth_remedy_constraints import encoded_remedy
   encoded=joined([canonical_parent(export_reference(g)[0],grid_mm=GRID_MM)for g in parts(native_grid(region))]);pin_check=encoded_remedy(patch,encoded,owned[channel])
   if pin_check is not None and not pin_check['passed']:
    report.setdefault('native_pin_encoding_rejections',[]).append(dict(status='KEEP_PROTECTED_PIN_ENCODING',check=pin_check));continue
   proposals[channel].append(region);counts[item['kind']]+=1;area[channel]+=patch.area
  for channel,regions in sorted(proposals.items()):
   combined=joined([*([aggregates[channel]]if channel in aggregates else[]),*regions]);foreign=[('current:'+o,g)for o,g in owned.items()if o!=channel]+[('reserved:'+o,g)for o,g in scope.reserved.items()if o!=channel]+[('checking-envelope:'+o,g)for o,g in getattr(scope,'checking_envelopes',{}).items()if o!=channel];combined,receipt=absorb(combined,owned[channel],scope.cores[channel],foreign,contract);
   from src.growth_remedy_constraints import require_remedy
   require_remedy(combined,owned[channel],scope='absorbed_remedy')
   aggregates[channel]=combined;absorptions.append(dict(original_channel_id=channel,radius_mm=contract.notch_radius_mm,**receipt));native=[canonical_parent(export_reference(g)[0],grid_mm=GRID_MM)for g in parts(native_grid(combined))];owned[channel]=owned[channel].union(joined(native))
  from src.pin_separation import require as require_pin
  require_pin(joined(list(owned.values())),finished=True,scope='absorbed_encoded_round')
  checked=check_owned(scope,owned)
  if not checked['passed']:raise ValueError('NATIVE_CHANNEL_COMPLETION_SIMULTANEOUS_CLEARANCE_FAILED:'+str(checked['failures'][:3]))
  for spec in partials:
   from src.partial_pocket_remedy import validate
   initial,remaining,carrier,ring=validate(spec,contract);body=owned[spec['original_channel_id']]
   if body.intersection(initial).area>spec['decision']['maximum_added_area_mm2']or body.intersection(remaining.buffer(-contract.file_uncertainty_mm)).area>contract.area_epsilon_mm2:raise ValueError('FROZEN_PARTIAL_POCKET_CUMULATIVE_CAP_OR_OPENING_CHANGED')
  rounds.append(dict(radius_mm=contract.notch_radius_mm,plan=report,fills=len(fills),updated_channels=len(proposals),native_channel_check=checked))
  p.save(store.root.parent/'completion_checkpoints'/(stage+'_'+mode+'_'+str(contract.notch_radius_mm)+'.json'),dict(native_channel_refs={o:p.geomref(store,g)for o,g in owned.items()},owner_aggregate_refs={o:p.geomref(store,g)for o,g in aggregates.items()},policy='Successful complete channel round; not acceptance'))
 changes={};metadata={};additions=[];records=[]
 for channel,region in sorted(aggregates.items()):
  own=physical_owner(scope,channel,physical);sid='component-completion:channel:'+channel;ref=p.geomref(store,region);md=dict(origin='functional-channel-owner-surface-absorption',original_owner_id=own,original_channel_id=channel,original_channel_witness_sha256=p.digest(to_wkb(scope.cores[channel])),original_source_sha256=physical.source_hash,stage=stage,kind='owner_surface_absorption',nominal_width_mm=0.,original_width_mm=0.,qualified_land=False,representation='EXISTING_CHANNEL_SURFACE_EXTENDED; no per-feature material objects',logical_patch_ref=ref);specs=[s for s in partials if s['original_channel_id']==channel]
  if specs:md['approved_partial_pockets']=specs
  if channel in oldrows:
   if oldrows[channel]['source_id']!=sid:raise ValueError('FUNCTIONAL_COMPLETION_SURFACE_IDENTITY_CHANGED')
   changes[sid]=region;metadata[sid]=md
  else:additions.append(dict(source_id=sid,kind='component_remedy',geometry_ref=ref,original_ref=p.geomref(store,physical.cores[own]),metadata=md))
  physical.assign(sid,region,[own]);scope.assign(sid,None,[channel]);records.append(dict(source_id=sid,original_owner_id=own,original_channel_id=channel,kind='owner_surface_absorption',geometry_ref=ref,logical_patch_ref=ref,planned_fill_area_mm2=area[channel]))
 output=p.artifact_scene(store,scene,changes,stage+'-functional-channel-completion',metadata=metadata,additions=additions);whole_before=physical.index.source.union(joined(list(before.values())));whole_after=physical.index.source.union(joined(list(owned.values())))
 return dict(output_scene_ref=output,source_sha256=physical.source_hash,ownership_policy=scope.ownership_policy,representation='ABSORB_INTO_ORIGINAL_OWNER_SURFACE',rounds=rounds,fills=records,feature_counts=dict(counts),microscopic_absorptions=absorptions,before_native_ref=p.geomref(store,whole_before),after_native_ref=p.geomref(store,whole_after),before_channel_refs={o:p.geomref(store,g)for o,g in before.items()},native_channel_refs={o:p.geomref(store,g)for o,g in owned.items()},summary=dict(fills=sum(counts.values()),owner_surfaces_updated=len(records),holes=counts['hole'],notches=counts['notch'],microscopic_holes_absorbed=sum(r['holes_absorbed']for r in absorptions),added_area_mm2=whole_after.difference(whole_before).area),basis='Frozen functional source channels; actual frame retained. Original local support, source voids, 20% cap, both owner systems and native checks remain mandatory.')
