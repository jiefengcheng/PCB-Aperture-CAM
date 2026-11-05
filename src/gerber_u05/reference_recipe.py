"""Regenerate the conservative reservation reference from fresh source stages.

This is a versioned legacy geometry recipe, never a saved-result input. Its
original contour, source, clearance, topology and corrupt-output checks remain.
"""
import math,collections,time,json,os,sys
from pathlib import Path
from . import pipeline as p,legacy_export as e
from .guard import verify_sources,install_read_fence
from src.growth_void_encoding import filled_surface
from src.growth_void_support import ContactSupport
from src.clearance_settings import read_snapshot
from src.growth_void_remedy_v09 import plan,parts,holes,joined,components,sha,RemedyContract
from src.pcb_data_abi.board_geometry import fidelity,export_reference
from src.indexed_hausdorff import distance as hausdorff
from shapely import set_precision,union_all,STRtree

def compute(run):
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
  return source,current,body,len(baseline.objects),proofs[0]

 def construct(store):
  guard();source,current,base,n,baseline_proof=context();start=time.monotonic()
  def progress(r):
   if r['component']%16==0:print(json.dumps(dict(operation='local_plan',progress=r)),flush=True)
  original_store=p.Store(legacy/'runtime');binding=p.load(legacy/'source.json');scene=original_store.get_json(binding['scene_ref'],kind='scene');source_support=ContactSupport([dict(id=r['source_id'],original=p.geometry(original_store,r['original_ref']),width_mm=r['metadata'].get('original_width_mm',0.))for r in scene['objects']],policy_snapshot['clearance_resolved']['contact_buffer_mm'])
  report,fills,raw_expected=plan(source,current,contract,checkpoint=progress,source_support=source_support);original_store.verify_reads();rows=[];blocks=[];owners=parts(current);native_references=[];reference_inventory=[]
  for i,row in enumerate(fills):
   patch=row['geometry'];owner=owners[row['owner']]
   # Duplicate a four-nanometre band of EXISTING owner copper to make the native
   # contour overlap robustly after 1 nm serialization. This is not added scope.
   support=owner.intersection(patch.buffer(2*contract.file_uncertainty_mm,quad_segs=32));region=filled_surface(patch.union(support));first=len(rows)
   normalized=set_precision(region,contract.grid_mm,mode='valid_output');normal_area=region.symmetric_difference(normalized).area;normal_bound=2*region.length*contract.grid_mm+math.pi*contract.grid_mm**2
   if normal_area>normal_bound:raise ValueError('NATIVE_MODEL_NORMALIZATION_AREA_FAILED')
   for piece in parts(normalized):
    reference,_=export_reference(piece);native_references.append(reference);reference_inventory.append(dict(owner=row['owner'],logical_patch_sha256=sha(patch),native_reference_sha256=sha(reference),normalization_area_mm2=normal_area,normalization_area_bound_mm2=normal_bound))
   e.append_regions(region,'inclusive_remedy','R-'+str(i),rows,blocks,store)
   for record in rows[first:]:record.update(owner=row['owner'],kind=row['kind'],logical_patch_ref=p.geomref(store,patch),encoded_support_mm=2*contract.file_uncertainty_mm)
  if not base.endswith(b'M02*\n') or base.count(b'M02*')!=1:raise ValueError('BASELINE_EOF_CHANGED')
  body=base[:-len(b'M02*\n')]+''.join(blocks).encode('ascii')+b'M02*\n'
  expected=union_all([current,*native_references],grid_size=contract.grid_mm)
  if len(native_references)!=len(rows):raise ValueError('NATIVE_MODEL_COMPONENT_COVERAGE_CHANGED')
  raw_reference=p.geomref(store,raw_expected)
  ledger=dict(raw_decision_image_ref=raw_reference,native_model_reference=dict(basis='Original qualified native predecessor plus independently compiled plan/support contours on the existing file grid; no output ledger or generated file used',reference_parts=len(native_references),inventory=reference_inventory,grid_mm=contract.grid_mm),producer_binding_sha256=p.digest((run/'PRODUCER_BINDING.json').read_bytes()),policy_snapshot_sha256=p.digest((run/'POLICY_SNAPSHOT.json').read_bytes()),schema='growth-void-addendum/1',baseline_generated_sha256=p.digest(base),original_source_sha256=baseline_proof['native_model_reference']['inventory'][0]['source_id'].split(':')[0],baseline_object_count=n,plan=report,records=rows,generated_sha256=p.digest(body),scope='Only additive source-component-bound local inclusive fills; original U05 prefix unchanged; no old gate relabeled')
  return body,ledger,source,current,expected

 def semantic(source,current,actual_shapes,ledger):
  originals,owners,mapping=components(source,current,contract);grouped=collections.defaultdict(list)
  for shape,row in zip(actual_shapes,ledger['records']):grouped[row['owner']].append(shape)
  checks=[];tree=STRtree(owners);effective={};inherited_kept=0
  for owner,j in enumerate(mapping):
   old_void=joined(holes(originals[j]));inherited=[h for h in holes(owners[owner])if h.intersection(old_void).area>contract.area_epsilon_mm2];inherited_kept+=len(inherited)
   added=joined(grouped[owner]).difference(owners[owner]);effective[owner]=added
   missing_owner=owners[owner].difference(owners[owner].union(joined(grouped[owner]))).area
   if missing_owner>contract.area_epsilon_mm2:raise ValueError('NATIVE_CORE_REMOVED')
   protected=joined(inherited).buffer(-contract.file_uncertainty_mm)
   changed_source_void=added.intersection(protected).area
   if changed_source_void>contract.area_epsilon_mm2:raise ValueError('NATIVE_INHERITED_VOID_FILLED')
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

 def check(body,ledger,source,current,expected,store):
  base=(legacy/'export/top.art.gbr').read_bytes();prefix=base[:-len(b'M02*\n')]
  if not body.startswith(prefix) or body.count(b'M02*')!=1:raise ValueError('PREDECESSOR_COMMAND_PREFIX_CHANGED')
  if p.digest(body)!=ledger['generated_sha256']:raise ValueError('REMEDY_OUTPUT_HASH_CHANGED')
  actual=e.parse(body);n=ledger['baseline_object_count']
  if len(actual.objects)!=n+len(ledger['records']):raise ValueError('REMEDY_NATIVE_INVENTORY_CHANGED')
  shapes=[];contours=[]
  for obj,row in zip(actual.objects[n:],ledger['records']):
   if not obj.polarity_dark or not isinstance(obj,p.go.Region):raise ValueError('REMEDY_NATIVE_ROLE_CHANGED')
   shape=p.affine_scale(p.source_profile.object_geometry(obj)[0],1,-1,origin=(0,0));reference=p.geometry(store,row['geometry_ref']);contours.append(fidelity(reference,shape));shapes.append(shape)
  addition_check=semantic(source,current,shapes,ledger);after=current.union(joined(shapes));native_grid=union_all([current,*shapes],grid_size=contract.grid_mm);expected_grid=union_all([expected],grid_size=contract.grid_mm)
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
  src,final_parts,mapping=components(source,after,contract);new_holes=[];subresolution=0
  for part,j in zip(final_parts,mapping):
   old_void=joined(holes(src[j]))
   for h in holes(part):
    if h.intersection(old_void).area>contract.area_epsilon_mm2:continue
    if h.buffer(-contract.file_uncertainty_mm).is_empty:subresolution+=1
    else:new_holes.append(dict(bounds_mm=list(h.bounds),area_mm2=h.area))
  if new_holes:raise ValueError('REMEDY_NEW_RESOLVABLE_TRAPPED_VOID:'+str(new_holes[:3]))
  store.verify_reads();guard();return dict(status='PASS',generated_sha256=p.digest(body),baseline_sha256=p.digest(base),plan_sha256=p.digest(p.canonical(ledger['plan'])),source_objects_preserved=p.load(legacy/'source.json')['source_objects'],baseline_objects_preserved=n,baseline_clear_operations_preserved=p.load(legacy/'source.json')['clear_operations'],appended_regions=len(shapes),decisions=dict(collections.Counter(r['kind']+':'+r['status']for r in ledger['plan']['records'])),actual_addition_check=addition_check,all_native_contours_pass=all(r['passed']for r in contours),contours=contours,hard_gap_mm=contract.hard_gap_mm,owner_allowance_consumed=False,components_preserved=len(after_parts),actual_predecessor_missing_area_mm2=current.difference(after).area,actual_original_source_missing_area_mm2=source.difference(after).area,auxiliary_file_grid_topology=auxiliary_topology,inherited_source_holes_retained=addition_check['inherited_source_holes_retained'],new_resolvable_holes=len(new_holes),subresolution_holes=subresolution,native_model_reference=ledger['native_model_reference'],raw_boolean_model_comparison=dict(symmetric_difference_mm2=raw_area,area_bound_mm2=raw_bound,role='Raw decision image; native boundary fidelity uses independent file-grid model reference'),whole_native_reference=dict(hausdorff_mm=gap,symmetric_difference_mm2=area,area_bound_mm2=bound,metric=metric),added_remedy_area_mm2=after.difference(current).area,original_area_mm2=source.area,final_area_mm2=after.area,limitations='Predecessor five geometry stages/two fresh export proofs retained unchanged. This is a new additive-stage export/reparse proof, not external independent or manufacturing review.')

 store=p.Store(run/'runtime');body,ledger,source,current,expected=construct(store)
 return body,ledger,check(body,ledger,source,current,expected,store)

def main():
 p.configure();run=Path(sys.argv[1]);mode=sys.argv[2];install_read_fence(run.parent);start=time.monotonic();body,ledger,proof=compute(run);folder=run/'export'
 if mode=='construct':
  folder.mkdir();(folder/'top.art.gbr').write_bytes(body);p.save(folder/'ledger.json',ledger)
 else:
  if body!=(folder/'top.art.gbr').read_bytes()or p.canonical(ledger)!=p.canonical(p.load(folder/'ledger.json')):raise ValueError('FRESH_REFERENCE_RECONSTRUCTION_CHANGED')
 p.save(folder/('proof_'+mode+'.json'),proof)
 print(json.dumps(dict(status='PASS',pid=os.getpid(),mode=mode,generated_sha256=p.digest(body),seconds=time.monotonic()-start)),flush=True)
if __name__=='__main__':main()
