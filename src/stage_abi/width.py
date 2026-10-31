"""T04 native complete-route collective width execution and direct replay."""
from dataclasses import asdict
import hashlib
from pathlib import Path
from shapely import to_wkb
from shapely.ops import unary_union
from src.source_offset_width import construct_source_offset_width,FAMILY
from src.trace_width_stage import SourceWidthStage,validate_width_partition
from src.bounded_width_solver import solve_width_scales
from src.prepared_width_scene import PreparedWidthScene
from src.trace_width_clearance import TraceWidthContract
from .contracts import closed,fail
from .journal import journalled
from .store import canonical,digest
from .scene import geometry,composed
from .runtime import Budget,bounds_check,operands,output_scene,check_output


def width_parameters():return dict(family=FAMILY,ceiling=1.5,scale_tolerance=1e-6,max_steps=36,surface_contract=asdict(TraceWidthContract()))

class WidthAdapter:
 def describe(self):
  files=[Path(__file__),Path(__file__).with_name('runtime.py')]+[Path(__file__).parents[1]/n for n in ['source_offset_width.py','trace_width_stage.py','bounded_width_solver.py','prepared_width_scene.py','trace_width_clearance.py','uniform_trace_width.py']]
  return dict(family=FAMILY,implementation=hashlib.sha256(b''.join(p.read_bytes() for p in files)).hexdigest(),operations=['plan','run','verify'],source_support='Source-bound native segments/arcs; explicit complete uniform routes and disjoint parallel groups/singletons; no route fitting or land edits')
 def _model(self,store,scene,policy,details):
  if policy.get('stage')!='t04' or canonical(policy.get('parameters'))!=canonical(width_parameters()):fail('POLICY_UNSUPPORTED','native collective width')
  rows,current,original=operands(store,scene);chains={};meta={};blobs={};raw={}
  for sid in details['targets']:
   row=rows[sid]
   if row['kind']!='trace' or row['metadata'].get('fixed_bulk',False):fail('TRACE_PREDECESSOR_UNSUPPORTED',sid)
   native=store.get_json(row['metadata']['native_route_ref'],kind='native-route');derived='generated_by_plan_ref' in native
   closed(native,{'source_ref','chain','manifest_rows','geometry_refs'}|({'parent_source_sha256','generated_by_plan_ref','geometry_family'} if derived else set()),'native route')
   source=store.get(native['source_ref'],kind='native-source')
   if derived:
    if native['parent_source_sha256']!=scene['source_sha256'] or native['geometry_family']!='bounded-parallel-polyline-miter/1' or not any(x.get('stage')=='t03' and x.get('plan_ref')==native['generated_by_plan_ref'] for x in scene['lineage']):fail('DERIVED_ROUTE_AUTHORITY_INVALID',sid)
   elif digest(source)!=scene['source_sha256'] or row['geometry_ref']!=row['original_ref']:fail('SOURCE_BINDING_MISMATCH','native source')
   raw[sid]=source;chain=dict(native['chain'],component_id=sid)
   for member in chain['source_ids']:
    if member in meta:fail('TRACE_SOURCE_PARTITION_INVALID',member)
    meta[member]=native['manifest_rows'][member];blobs[member]=store.get(native['geometry_refs'][member],kind='geometry')
   record,_,_,core,_,_=construct_source_offset_width(source,chain,meta,blobs,1.)
   if (not derived and not core.equals_exact(original[sid],0)) or not core.equals(current[sid]) or row['metadata'].get('nominal_width_mm')!=record['verified_original_width_mm']:fail('SOURCE_ROUTE_GEOMETRY_MISMATCH',sid)
   chains[sid]=chain
  model=SourceWidthStage(b'',chains,details['groups'],meta,blobs,sources=raw)
  baseline=model.build({gid:1. for gid in model.group_ids})[0];fixed=[dict(id=s,geometry=g,trace_width_mm=rows[s]['metadata'].get('nominal_width_mm',0.)) for s,g in current.items() if s not in chains];checker=PreparedWidthScene(baseline,fixed)
  return rows,current,model,checker,raw,chains,meta,blobs
 def plan(self,store,scene,policy,selection,bounds):
  closed(selection,{'stage','scene_ref','source_ids','groups'},'width selection');bounds_check(bounds,scene,selection)
  ids=sorted(selection['source_ids']);groups=selection['groups']
  if type(groups) is not list or any(type(g) is not dict or set(g)!={'group_id','members'} for g in groups):fail('TRACE_GROUP_PARTITION_INVALID','groups')
  details=dict(targets=ids,groups=groups,bounds=bounds,family=FAMILY)
  self._model(store,scene,policy,details);return details
 def run(self,store,scene,policy,plan,checkpoint):
  details=plan['details'];rows,current,model,checker,_,_,_,_=self._model(store,scene,policy,details);budget=Budget(details['bounds']);reports=[]
  def evaluate(scales):
   budget.evaluation();traces=model.build(scales)[0];q=journalled('width-search-check',scales,lambda:checker.check(traces,fail_fast=True));blob=canonical(dict(scales=scales,check=q));budget.output(blob);reports.append(store.put('width-check',blob));checkpoint(dict(evaluation=budget.evaluations,scales=scales,check_refs=reports));return q
  solution=solve_width_scales(sorted(model.group_ids),evaluate,geometry_family=FAMILY,scale_tolerance=1e-6,max_steps=36)
  if not solution['passed']:fail('WIDTH_CANDIDATE_REJECTED',solution['status'])
  scales=solution['selected_scales'];traces,records,envelopes,nominal=model.build(scales);budget.evaluation();envelope_check=journalled('width-final-envelope',scales,lambda:checker.check(traces,materialize_scene=True));nominal_traces=[];replacements={};metadata={};parts={}
  for sid in sorted(model.chains):
   record,np,ep,core,g,_=model.construct(sid,scales[model.assignment[sid]]);nominal_traces.append(dict(id=sid,original=core,candidate=g,verified_original_width_mm=record['verified_original_width_mm']));blob=to_wkb(g);budget.output(blob);replacements[sid]=rows[sid]['geometry_ref'] if scales[model.assignment[sid]]==1 else store.put('geometry',blob);metadata[sid]=dict(rows[sid]['metadata'],nominal_width_mm=record['uniform_nominal_width_mm'],width_scale=scales[model.assignment[sid]],width_family=FAMILY)
   for member,part in np.items():
    nb,eb=to_wkb(part),to_wkb(ep[member]);budget.output(nb);budget.output(eb);parts[member]=dict(nominal_ref=store.put('geometry',nb),envelope_ref=store.put('geometry',eb))
  budget.evaluation();nominal_check=journalled('width-final-nominal',scales,lambda:checker.check(nominal_traces,materialize_scene=True))
  if not envelope_check['passed'] or not nominal_check['passed']:fail('FINAL_WIDTH_SCENE_REJECTED','nominal/envelope')
  out_ref,out=output_scene(store,scene,plan,replacements=replacements,metadata=metadata)
  return dict(status='CONSTRUCTED',solution=solution,construction=records,parts=parts,replacement_refs=replacements,nominal_check=nominal_check,envelope_check=envelope_check,check_refs=reports,before_ref=store.put('geometry',to_wkb(composed(store,scene))),after_ref=store.put('geometry',to_wkb(composed(store,out))),output_scene_ref=out_ref,protected_source_refs={s:r['geometry_ref'] for s,r in rows.items() if s not in details['targets']})
 def verify(self,store,scene,policy,plan,candidate,proof_scope,checkpoint):
  if proof_scope!={'scope':'complete-source-nominal-envelope-and-upper-proofs'}:fail('PROOF_SCOPE_UNSUPPORTED','complete width replay required')
  details=plan['details'];rows,current,model,checker,raw,chains,meta,blobs=self._model(store,scene,policy,details);scales=candidate['solution']['selected_scales']
  if set(scales)!=model.group_ids or any(type(x) not in (int,float) or not 1<=x<=1.5 for x in scales.values()):fail('WIDTH_SCALE_OUT_OF_SCOPE','scale vector')
  if candidate['protected_source_refs']!={s:r['geometry_ref'] for s,r in rows.items() if s not in details['targets']}:fail('PREDECESSOR_CHANGED','width fixed copper')
  replacements={};metadata={};parts={};nominal=[];envelope=[];records=[]
  # Reconstruct each native route directly; never trust saved candidate width
  # blobs or a cached source-model callback as verification geometry.
  for sid in sorted(chains):
   factor=scales[model.assignment[sid]];record,np,ep,core,g,e=construct_source_offset_width(raw[sid],chains[sid],meta,blobs,factor);records.append(record);replacements[sid]=rows[sid]['geometry_ref'] if factor==1 else store.put('geometry',to_wkb(g));metadata[sid]=dict(rows[sid]['metadata'],nominal_width_mm=record['uniform_nominal_width_mm'],width_scale=factor,width_family=FAMILY)
   nominal.append(dict(id=sid,original=core,candidate=g,verified_original_width_mm=record['verified_original_width_mm']));envelope.append(dict(id=sid,original=core,candidate=e,verified_original_width_mm=record['verified_original_width_mm']))
   for member,part in np.items():parts[member]=dict(nominal_ref=store.put('geometry',to_wkb(part)),envelope_ref=store.put('geometry',to_wkb(ep[member])))
  if parts!=candidate['parts'] or replacements!=candidate['replacement_refs'] or records!=candidate['construction']:fail('WIDTH_RECONSTRUCTION_MISMATCH','native primitives/routes')
  budget=Budget(details['bounds']);budget.evaluation();q=journalled('verify-width-nominal',scales,lambda:checker.check(nominal,materialize_scene=True));budget.evaluation();qe=journalled('verify-width-envelope',scales,lambda:checker.check(envelope,materialize_scene=True));proofs=[];decisions=candidate['solution']['decisions']
  if {d['group_id'] for d in decisions}!=model.group_ids or len(decisions)!=len(model.group_ids):fail('WIDTH_PROOF_COVERAGE_MISMATCH','groups')
  for d in decisions:
   gid=d['group_id'];upper=d['upper_rejected_factor']
   if d['selected_factor']!=scales[gid]:fail('WIDTH_PROOF_BINDING_MISMATCH',gid)
   if upper is None:proved=scales[gid]==1.5
   else:
    if type(upper) not in (int,float) or not scales[gid]<upper<=1.5:fail('WIDTH_UPPER_PROOF_INVALID',gid)
    trial=dict(scales);trial[gid]=upper;budget.evaluation();rejected=journalled('verify-width-upper',trial,lambda:checker.check(model.build(trial)[0],fail_fast=True));proved=not rejected['passed'] and upper-scales[gid]<=1e-6
   proofs.append(dict(group_id=gid,proved=proved))
  if candidate['solution']['maximum_established'] is True and not all(p['proved'] for p in proofs):fail('MAXIMUM_NOT_ESTABLISHED','fresh final-neighbor upper proofs')
  check_output(store,scene,plan,candidate,replacements=replacements,metadata=metadata);checkpoint(dict(verified_native_parts=len(parts),upper_proofs=proofs))
  return dict(passed=q['passed'] and qe['passed'],failures=q['failures']+qe['failures'],nominal=q,envelope=qe,maximum_proofs=proofs,reconstructed_native_parts=len(parts),scope='Source-bound uniform nominal and conservative-envelope replay; coordinate-wise rather than global maximum, no electrical/manufacturing claim')
