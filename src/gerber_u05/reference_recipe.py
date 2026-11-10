"""Regenerate the conservative reservation reference from fresh source stages.

This is a versioned legacy geometry recipe, never a saved-result input. Its
original contour, source, clearance, topology and corrupt-output checks remain.
"""
import math,collections,time,json,os,sys
from src.hole_acceptance import required as holes_required
from pathlib import Path
from . import pipeline as p,legacy_export as e
from .guard import verify_sources,install_read_fence
from src.growth_void_encoding import filled_surface
from src.growth_void_support import ContactSupport
from src.clearance_settings import read_snapshot
from src.growth_void_remedy_v09 import plan,parts,holes,joined,components,sha,RemedyContract
from src.native_grid_reference import fidelity,reference as export_reference,normalize as native_grid
from src.pcb_data_abi.geometry import GRID_MM
from .exporter import append_regions as append_native_regions
from .native_assembly import weld as weld_native_material,assemble as assemble_native_material,key as native_parent_key
from src.indexed_hausdorff import distance as hausdorff
from shapely import set_precision,union_all,STRtree

def initialize_reference_constraints(store,binding,source,original,predecessor):
 """Future reference repairs retain the already qualified T04 no-bypass rule."""
 from src import t04_width_fence as width
 width.restore(store,predecessor)
 if width.ACTIVE is None:raise ValueError('REFERENCE_FROZEN_T04_WIDTH_RULE_REQUIRED')
 from src import t02_shared_gaps as shared_gaps
 # Check each full slot from all its local contributors. The board-wide
 # overlay can introduce spurious edges from unrelated T05 additions.
 shared_gaps.restore(store,predecessor,project_parts=True)
 from .pin_policy import initialize as initialize_pin
 initialize_pin(store,binding,source,original,predecessor)
 return dict(schema='reference-inherited-growth-constraints/2',
             frozen_t04_width_binding=width.ACTIVE.binding,
             frozen_shared_gap_state_sha256=None if shared_gaps.ACTIVE is None else p.digest(p.canonical(shared_gaps.ACTIVE)),
             source_sha256=binding['source_ref']['sha256'],
             scope='Complete logical reference fills and actual parsed parents; qualified existing pad/joint predecessor remains integral')

def append_reference_region(region,stage,sid,records,blocks,store):
 """Compile the model independently, then prove exact serialized parent coverage."""
 normalized=native_grid(region)
 refs=[export_reference(piece)[0]for piece in sorted(parts(normalized),key=p.to_wkb)]
 first=len(records);parents=append_native_regions(region,stage,sid,records,blocks,store)
 if len(parents)!=len(refs):raise ValueError('NATIVE_REFERENCE_PARENT_COVERAGE_CHANGED')
 from .native_material import equality
 for actual,expected in zip(parents,refs):equality(expected,actual,grid_mm=GRID_MM)
 expected={p.digest(p.to_wkb(ref))for ref in refs}
 if not records[first:]or any(row['component_reference_proof']['partition_parent_reference_proof']['export_reference_sha256']not in expected for row in records[first:]):
  raise ValueError('NATIVE_REFERENCE_SERIALIZATION_PARENT_CHANGED')
 return refs

def reconstruct_reference_material(current,shapes,records,parents,owners,*,grid_mm):
 """Validate every parsed face before assembling its exact integer-grid parent."""
 identities=[identity for identity,_ in parents]
 if len(set(identities))!=len(identities)or set(identities)!=set(owners):raise ValueError('REFERENCE_NATIVE_PARENT_INVENTORY_CHANGED')
 for row in records:
  identity=native_parent_key(row)
  if identity not in owners or row['owner']!=owners[identity]:raise ValueError('REFERENCE_NATIVE_OWNER_CHANGED')
 welded,proofs=weld_native_material(records,shapes,parents,grid_mm=grid_mm)
 material=[shape for _,shape in welded];owner_rows=[dict(owner=owners[identity])for identity,_ in welded]
 after=current.union(joined(material));image=assemble_native_material(current,material,grid_mm=grid_mm)
 proof=dict(status='EXACT_PARSED_NATIVE_MATERIAL',parents=len(welded),serialized_regions=len(shapes),partitions=proofs,basis='Every actual parsed positive face is bound by exact integer boundary/area or exact native cut-in equality before parent assembly; source predecessor is unchanged')
 return after,image,material,owner_rows,proof

def compute(run):
 functional_state={}
 legacy=run.parent/'legacy';policy_snapshot=p.load(run/'POLICY_SNAPSHOT.json');contract=RemedyContract(**policy_snapshot['resolved_parameters'])
 def guard():
  seal=verify_sources(run);verify_sources(legacy)
  captured=read_snapshot(run/'CLEARANCE_SNAPSHOT.json')
  if captured.resolved()!=policy_snapshot['clearance_resolved']or captured.nominal_mm!=contract.hard_gap_mm or captured.construction_gap_mm!=contract.construction_gap_mm:raise ValueError('CAPTURED_POLICY_BINDING_CHANGED')
  return seal
 def context():
  original_bytes=(legacy/'source_snapshot/top.art.gbr').read_bytes();original,_,_=p.source_profile.parse_source(original_bytes);source=p.affine_scale(p.source_profile.ordered((p.source_profile.object_geometry(o)[0],o.polarity_dark)for o in original.objects),1,-1,origin=(0,0));body=(legacy/'export/top.art.gbr').read_bytes();baseline=e.parse(body);n=len(original.objects);regions=[p.affine_scale(p.source_profile.object_geometry(o)[0],1,-1,origin=(0,0))for o in baseline.objects[n:]];current=source.union(joined(regions))
  proofs=[p.load(legacy/'export'/('proof_'+str(i)+'.json'))for i in(1,2)]
  if p.canonical(proofs[0])!=p.canonical(proofs[1]) or proofs[0]['status']!='PASS' or proofs[0]['generated_sha256']!=p.digest(body):raise ValueError('BASELINE_PROOFS_CHANGED')
  if proofs[0]['actual_hard_gap_mm']!=contract.hard_gap_mm:raise ValueError('PREDECESSOR_CLEARANCE_POLICY_MISMATCH')
  legacy_store=p.Store(legacy/'runtime');binding=p.load(legacy/'source.json');source_scene=legacy_store.get_json(binding['scene_ref'],kind='scene')
  constraint_receipt=initialize_reference_constraints(legacy_store,binding,source,source_scene,legacy_store.get_json(p.load(legacy/'t05.json')['output_scene_ref'],kind='scene'))
  functional_state['inherited_constraints']=constraint_receipt
  if 'functional_channels'in proofs[0]:
   from src import source_channel_scope
   from .channel_material import check_owned
   scope=source_channel_scope.bind(source,binding['source_ref']['sha256'],source_scene,legacy_store,integral=(legacy/'SOURCE_ASSEMBLY_BINDING.json').exists());native=proofs[0]['functional_channels']
   if scope is None or native['status']!='PASS'or native['channel_certificate_sha256']!=p.digest(p.canonical(scope.certificate)):raise ValueError('REFERENCE_NATIVE_CHANNEL_BASELINE_CHANGED')
   owned={o:p.geometry(legacy_store,ref)for o,ref in native['owned_geometry_refs'].items()};q=check_owned(scope,owned)
   if not q['passed']:raise ValueError('REFERENCE_BASELINE_FUNCTIONAL_CLEARANCE_FAILED')
   functional_state.update(scope=scope,owned=owned)
  from .checking_envelopes import install
  if 'scope'in functional_state:checking_context=functional_state['scope']
  else:
   from src.component_clearance import Context
   _,original_material,_=p.operands(legacy_store,source_scene)
   checking_context=Context(source,binding['source_ref']['sha256'],original_material)
  install(checking_context,legacy_store,binding,legacy)
  functional_state['checking_context']=checking_context
  return source,current,body,len(baseline.objects),proofs[0]

 def construct(store):
  guard();source,current,base,n,baseline_proof=context();start=time.monotonic()
  def progress(r):
   if r['component']%16==0:print(json.dumps(dict(operation='local_plan',progress=r)),flush=True)
  original_store=p.Store(legacy/'runtime');binding=p.load(legacy/'source.json');scene=original_store.get_json(binding['scene_ref'],kind='scene');source_support=ContactSupport([dict(id=r['source_id'],original=p.geometry(original_store,r['original_ref']),width_mm=r['metadata'].get('original_width_mm',0.))for r in scene['objects']],policy_snapshot['clearance_resolved']['contact_buffer_mm'])
  planning_source=source;planning_current=current
  if 'scope'in functional_state:
   scope=functional_state['scope'];planning_source=scope.channels.analytic_source;planning_current=joined(list(functional_state['owned'].values()))
  from .checking_envelopes import indexed
  report,fills,raw_expected=plan(planning_source,planning_current,contract,checkpoint=progress,source_support=source_support,partial_strategy=policy_snapshot.get('large_pocket_strategy'),clearance_only=indexed(functional_state['checking_context'],parts(planning_source)))
  if 'scope'in functional_state:
   scope=functional_state['scope'];source_channels=[scope.index.membership(g)[0]for g in parts(planning_source)];current_channels=[scope.index.membership(g)[0]for g in parts(planning_current)];functional_state.update(source_channels=source_channels,current_channels=current_channels)
   from src import component_clearance
   from src.source_channel_scope import physical_owner
   _,original_material,_=p.operands(original_store,scene);physical=component_clearance.Context(source,scope.source_hash,original_material)
   for spec in report.get('approved_partial_pockets',[]):
    channel=source_channels[spec['source_component']];spec.update(original_channel_id=channel,original_owner_id=physical_owner(scope,channel,physical),original_source_sha256=scope.source_hash)
   raw_expected=current.union(joined([r['geometry']for r in fills]))
  original_store.verify_reads();rows=[];blocks=[];owners=parts(planning_current);native_references=[];reference_inventory=[];native_parents=[];native_parent_owners={}
  approved_logical=[]
  for i,row in enumerate(fills):
   patch=row['geometry'];owner=owners[row['owner']]
   # Duplicate a four-nanometre band of EXISTING owner copper to make the native
   # contour overlap robustly after 1 nm serialization. This is not added scope.
   from .component_finish import overlap_region
   supported,_support_mode=overlap_region(patch,owner,contract);region=filled_surface(supported);first=len(rows)
   from src.growth_remedy_constraints import encoded_remedy
   from .native_assembly import canonical_parent
   encoded=joined([canonical_parent(export_reference(g)[0],grid_mm=GRID_MM)for g in parts(native_grid(region))]);pin_check=encoded_remedy(patch,encoded,current)
   if pin_check is not None and not pin_check['passed']:
    report.setdefault('native_pin_encoding_rejections',[]).append(dict(status='KEEP_PROTECTED_PIN_ENCODING',check=pin_check));continue
   approved_logical.append(patch)
   normalized=native_grid(region);normal_area=region.symmetric_difference(normalized).area;normal_bound=2*region.length*contract.grid_mm+math.pi*contract.grid_mm**2
   if normal_area>normal_bound:raise ValueError('NATIVE_MODEL_NORMALIZATION_AREA_FAILED')
   references=append_reference_region(region,'inclusive_remedy','R-'+str(i),rows,blocks,store)
   for reference in references:
    identity=('inclusive_remedy','R-'+str(i),p.digest(p.to_wkb(reference)))
    if identity in native_parent_owners:raise ValueError('REFERENCE_NATIVE_PARENT_DUPLICATED')
    native_parents.append((identity,reference));native_parent_owners[identity]=row['owner']
    native_references.append(reference);reference_inventory.append(dict(owner=row['owner'],logical_patch_sha256=sha(patch),native_reference_sha256=sha(reference),normalization_area_mm2=normal_area,normalization_area_bound_mm2=normal_bound))
   for record in rows[first:]:record.update(owner=row['owner'],kind=row['kind'],logical_patch_ref=p.geomref(store,patch),encoded_support_mm=2*contract.file_uncertainty_mm)
  if not base.endswith(b'M02*\n') or base.count(b'M02*')!=1:raise ValueError('BASELINE_EOF_CHANGED')
  body=base[:-len(b'M02*\n')]+''.join(blocks).encode('ascii')+b'M02*\n'
  expected=assemble_native_material(current,native_references,grid_mm=contract.grid_mm)
  if len(native_references)!=len(reference_inventory):raise ValueError('NATIVE_MODEL_COMPONENT_COVERAGE_CHANGED')
  raw_expected=current.union(joined(approved_logical))
  raw_reference=p.geomref(store,raw_expected)
  ledger=dict(raw_decision_image_ref=raw_reference,native_model_reference=dict(basis='Original qualified native predecessor plus independently compiled plan/support contours on the existing file grid; no output ledger or generated file used',reference_parts=len(native_references),inventory=reference_inventory,grid_mm=contract.grid_mm),producer_binding_sha256=p.digest((run/'PRODUCER_BINDING.json').read_bytes()),policy_snapshot_sha256=p.digest((run/'POLICY_SNAPSHOT.json').read_bytes()),schema='growth-void-addendum/1',baseline_generated_sha256=p.digest(base),original_source_sha256=baseline_proof['native_model_reference']['inventory'][0]['source_id'].split(':')[0],baseline_object_count=n,plan=report,records=rows,generated_sha256=p.digest(body),scope='Only additive source-component-bound local inclusive fills; original U05 prefix unchanged; no old gate relabeled')
  return body,ledger,source,current,expected,native_parents,native_parent_owners

 def semantic(source,current,actual_shapes,ledger):
  if 'scope'in functional_state:source=functional_state['scope'].channels.analytic_source;current=joined(list(functional_state['owned'].values()))
  originals,owners,mapping=components(source,current,contract);grouped=collections.defaultdict(list)
  for shape,row in zip(actual_shapes,ledger['records']):grouped[row['owner']].append(shape)
  checks=[];tree=STRtree(owners);effective={};inherited_kept=0
  for owner,j in enumerate(mapping):
   old_void=joined(holes(originals[j]))if holes_required()else p.Polygon();inherited=[h for h in holes(owners[owner])if h.intersection(old_void).area>contract.area_epsilon_mm2];inherited_kept+=len(inherited)
   added=joined(grouped[owner]).difference(owners[owner]);effective[owner]=added
   missing_owner=owners[owner].difference(owners[owner].union(joined(grouped[owner]))).area
   if missing_owner>contract.area_epsilon_mm2:raise ValueError('NATIVE_CORE_REMOVED')
   protected=joined(inherited).buffer(-contract.file_uncertainty_mm)
   changed_source_void=added.intersection(protected).area
   if holes_required()and changed_source_void>contract.area_epsilon_mm2:raise ValueError('NATIVE_INHERITED_VOID_FILLED')
   gaps=[]
   if not added.is_empty and added.area>contract.area_epsilon_mm2:
    for other in sorted(map(int,tree.query(added.buffer(contract.hard_gap_mm+.001)))):
     if other==owner:continue
     gap=added.distance(owners[other]);gaps.append(dict(component=other,gap_mm=gap))
     if not math.isfinite(gap)or gap+1e-12<contract.hard_gap_mm:raise ValueError('NATIVE_FOREIGN_CLEARANCE_FAILED')
   checks.append(dict(owner=owner,inherited_holes=len(inherited),source_void_changed_mm2=changed_source_void,added_area_mm2=added.area,foreign_gaps=gaps))
  for owner,added in effective.items():
   if added.is_empty:continue
   for other,other_added in effective.items():
    if other<=owner or other_added.is_empty:continue
    if added.distance(other_added)+1e-12<contract.hard_gap_mm:raise ValueError('NATIVE_SIMULTANEOUS_FILL_CLEARANCE_FAILED')
  return dict(passed=True,owners=checks,inherited_source_holes_retained=inherited_kept)

 def check(body,ledger,source,current,expected,native_parents,native_parent_owners,store):
  base=(legacy/'export/top.art.gbr').read_bytes();prefix=base[:-len(b'M02*\n')]
  if not body.startswith(prefix) or body.count(b'M02*')!=1:raise ValueError('PREDECESSOR_COMMAND_PREFIX_CHANGED')
  if p.digest(body)!=ledger['generated_sha256']:raise ValueError('REMEDY_OUTPUT_HASH_CHANGED')
  actual=e.parse(body);n=ledger['baseline_object_count']
  if len(actual.objects)!=n+len(ledger['records']):raise ValueError('REMEDY_NATIVE_INVENTORY_CHANGED')
  shapes=[];contours=[]
  for obj,row in zip(actual.objects[n:],ledger['records']):
   if not obj.polarity_dark or not isinstance(obj,p.go.Region):raise ValueError('REMEDY_NATIVE_ROLE_CHANGED')
   shape=p.affine_scale(p.source_profile.object_geometry(obj)[0],1,-1,origin=(0,0));reference=p.geometry(store,row['geometry_ref']);contours.append(fidelity(reference,shape));shapes.append(shape)
  after,native_grid,material,owner_rows,material_proof=reconstruct_reference_material(current,shapes,ledger['records'],native_parents,native_parent_owners,grid_mm=contract.grid_mm)
  from src.growth_remedy_constraints import require_remedy
  for actual_parent in material:require_remedy(actual_parent,current,scope='actual_native_reference_remedy')
  addition_check=semantic(source,current,material,dict(records=owner_rows));expected_grid=expected
  gap,metric=hausdorff(native_grid,expected_grid,tolerance=contract.file_uncertainty_mm);area=native_grid.symmetric_difference(expected_grid).area;bound=2*expected_grid.length*contract.file_uncertainty_mm
  if not math.isfinite(gap)or gap>contract.file_uncertainty_mm or area>bound:raise ValueError('REMEDY_WHOLE_IMAGE_FIDELITY_FAILED')
  raw_expected=p.from_wkb(store.get(ledger['raw_decision_image_ref'],kind='geometry'));raw_area=after.symmetric_difference(raw_expected).area;raw_bound=2*raw_expected.length*contract.file_uncertainty_mm
  if not raw_expected.is_valid or not math.isfinite(raw_area) or raw_area>raw_bound:raise ValueError('RAW_BOOLEAN_MODEL_AREA_FIDELITY_FAILED')
  # Physical partition and source preservation use actual parsed copper. The
  # normalized measurement image is separately retained for native fidelity;
  # its sub-grid topology cannot replace the physical source predicate.
  before_grid=set_precision(current,contract.grid_mm);_,after_parts,_=components(current,after,contract)
  auxiliary_topology=dict(before_components=len(parts(before_grid)),after_components=len(parts(native_grid)),normalized_overlay_difference_mm2=before_grid.difference(native_grid).area,role='Auxiliary measurement image only. Actual plotted copper is the source-preservation and physical partition authority; every positive-area source triangle is retained.')
  missing=[];coverage_surface=after.buffer(contract.file_uncertainty_mm)
  for row in ledger['records']:
   patch=p.geometry(store,row['logical_patch_ref']);loss=patch.difference(coverage_surface).area
   if loss>contract.area_epsilon_mm2:missing.append(dict(patch=sha(patch),area_mm2=loss))
  if missing:raise ValueError('REMEDY_REQUIRED_POCKET_MISSING')
  # No new resolvable cavity may be trapped by a partial-notch fill.
  from src.partial_pocket_remedy import corresponds,validate as validate_partial
  partials=ledger['plan'].get('approved_partial_pockets',[]);partial_checks=[]
  for spec in partials:
   initial,remaining,carrier,ring=validate_partial(spec,contract)
   physical_added=after.intersection(initial).area;share=physical_added/(carrier.area+physical_added)
   if share>contract.maximum_shortage:raise ValueError('NATIVE_PARTIAL_POCKET_CUMULATIVE_CAP_EXCEEDED')
   partial_checks.append(dict(pocket_id=spec['pocket_id'],native_added_area_mm2=physical_added,native_share=share,maximum_share=contract.maximum_shortage))
  functional_sidecar=None
  if 'scope'in functional_state:
   from .channel_material import check_owned
   scope=functional_state['scope'];owned=dict(functional_state['owned'])
   for g,row in zip(material,owner_rows):
    channel=functional_state['current_channels'][row['owner']];owned[channel]=owned[channel].union(g)
   channel_check=check_owned(scope,owned)
   if not channel_check['passed']:raise ValueError('REFERENCE_NATIVE_FUNCTIONAL_CLEARANCE_FAILED:'+str(channel_check['failures'][:3]))
   functional_sidecar=dict(schema='actual-native-channel-reservation/1',status='PASS',source_sha256=scope.source_hash,generated_sha256=p.digest(body),channel_certificate_sha256=p.digest(p.canonical(scope.certificate)),owned_geometry_refs={o:p.geomref(store,g)for o,g in owned.items()},approved_partial_pockets=partials,native_channel_check=channel_check,native_material_proof_sha256=p.digest(p.canonical(material_proof)))
  else:
   checking_context=functional_state['checking_context']
   owned={checking_context.index.membership(g)[0]:g for g in parts(after)}
  from .checking_envelopes import check_native
  checking_proof=check_native(functional_state['checking_context'],owned,contract.construction_gap_mm)
  from src import pin_separation as pin
  if pin.ACTIVE is not None:
   pin.ACTIVE.require(after,finished=True,scope='reference_native')
   if functional_sidecar is not None:functional_sidecar['pin_separation_state']=pin.ACTIVE.state(store)
  src,final_parts,mapping=components(source,after,contract);new_holes=[];accepted_holes=[];subresolution=0;retained_partial=[]
  inventory_parts=final_parts;inventory_sources=src;inventory_mapping=mapping
  if 'scope'in functional_state:
   inventory_sources=parts(functional_state['scope'].channels.analytic_source);inventory_parts=parts(joined(list(owned.values())));_,_,inventory_mapping=components(joined(inventory_sources),joined(inventory_parts),contract)
  for part,j in zip(inventory_parts,inventory_mapping):
   old_void=joined(holes(inventory_sources[j]))if holes_required()else p.Polygon()
   for h in holes(part):
    if h.intersection(old_void).area>contract.area_epsilon_mm2:continue
    matched=[s for s in partials if s['source_component']==j and corresponds(h,s,contract)]
    if matched:
     if len(matched)!=1:raise ValueError('NATIVE_PARTIAL_POCKET_REMAINDER_AMBIGUOUS')
     retained_partial.append(matched[0]['pocket_id']);continue
    if not holes_required():accepted_holes.append(dict(bounds_mm=list(h.bounds),area_mm2=h.area));continue
    if h.buffer(-contract.file_uncertainty_mm).is_empty:subresolution+=1
    else:new_holes.append(dict(bounds_mm=list(h.bounds),area_mm2=h.area))
  if new_holes:raise ValueError('REMEDY_NEW_RESOLVABLE_TRAPPED_VOID:'+str(new_holes[:3]))
  if sorted(retained_partial)!=sorted(s['pocket_id']for s in partials):raise ValueError('NATIVE_PARTIAL_POCKET_REMAINDER_MISSING')
  store.verify_reads();guard();result=dict(status='PASS',generated_sha256=p.digest(body),baseline_sha256=p.digest(base),plan_sha256=p.digest(p.canonical(ledger['plan'])),source_objects_preserved=p.load(legacy/'source.json')['source_objects'],baseline_objects_preserved=n,baseline_clear_operations_preserved=p.load(legacy/'source.json')['clear_operations'],appended_regions=len(shapes),decisions=dict(collections.Counter(r['kind']+':'+r['status']for r in ledger['plan']['records'])),actual_addition_check=addition_check,all_native_contours_pass=all(r['passed']for r in contours),contours=contours,hard_gap_mm=contract.hard_gap_mm,owner_allowance_consumed=False,components_preserved=len(after_parts),actual_predecessor_missing_area_mm2=current.difference(after).area,actual_original_source_missing_area_mm2=source.difference(after).area,auxiliary_file_grid_topology=auxiliary_topology,inherited_source_holes_retained=addition_check['inherited_source_holes_retained'],new_resolvable_holes=len(new_holes),subresolution_holes=subresolution,approved_partial_pocket_remainders=partial_checks,native_model_reference=ledger['native_model_reference'],native_material_assembly=material_proof,raw_boolean_model_comparison=dict(symmetric_difference_mm2=raw_area,area_bound_mm2=raw_bound,role='Raw decision image; native boundary fidelity uses independent file-grid model reference'),whole_native_reference=dict(hausdorff_mm=gap,symmetric_difference_mm2=area,area_bound_mm2=bound,metric=metric),added_remedy_area_mm2=after.difference(current).area,original_area_mm2=source.area,final_area_mm2=after.area,limitations='Predecessor five geometry stages/two fresh export proofs retained unchanged. This is a new additive-stage export/reparse proof, not external independent or manufacturing review.')

  result['checking_envelope_clearance']=checking_proof
  result['inherited_growth_constraints']=functional_state['inherited_constraints']
  if not holes_required():result.update(ordinary_holes='ACCEPT_WITHOUT_SOURCE_ANCESTRY',accepted_ordinary_holes=accepted_holes)
  if functional_sidecar is not None:result['functional_channels']=functional_sidecar
  return result

 store=p.Store(run/'runtime');body,ledger,source,current,expected,native_parents,native_parent_owners=construct(store)
 return body,ledger,check(body,ledger,source,current,expected,native_parents,native_parent_owners,store)

def main():
 p.configure();run=Path(sys.argv[1]);mode=sys.argv[2];install_read_fence(run.parent);start=time.monotonic();body,ledger,proof=compute(run);folder=run/'export'
 if mode=='construct':
  folder.mkdir();(folder/'top.art.gbr').write_bytes(body);p.save(folder/'ledger.json',ledger)
 else:
  if body!=(folder/'top.art.gbr').read_bytes()or p.canonical(ledger)!=p.canonical(p.load(folder/'ledger.json')):raise ValueError('FRESH_REFERENCE_RECONSTRUCTION_CHANGED')
 p.save(folder/('proof_'+mode+'.json'),proof)
 print(json.dumps(dict(status='PASS',pid=os.getpid(),mode=mode,generated_sha256=p.digest(body),seconds=time.monotonic()-start)),flush=True)
if __name__=='__main__':main()
