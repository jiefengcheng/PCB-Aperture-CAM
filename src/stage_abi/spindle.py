"""Real T05 adapter: source-contact admission, spindle construction and replay."""
from dataclasses import asdict
import hashlib
import math
from pathlib import Path
import time
from shapely import to_wkb,from_wkb
from shapely.geometry import box
from shapely.ops import unary_union
from src.junction_spindle_stage import CONTRACT,prepare_spindle_context,fit_spindle_blend,verify_spindle_batch,assemble_spindle_scene
from src.junction_spindle_blend import spindle_blend,check_spindle
from .contracts import closed,fail
from .journal import journalled
from .scene import geometry
from .store import canonical
from .runtime import Budget
from .journal import ACTIVE

from src.stage_abi.preparation import prepared_tree as STRtree,decode_geometry as from_wkb,prepared_buffer

def filled_circle(core):
 """Admit a regular filled source-circle tessellation, never a ring or box."""
 if core.geom_type!='Polygon' or core.interiors:return False
 coordinates=list(core.exterior.coords)[:-1]
 if len(coordinates)<16 or len(coordinates)%4:return False
 x0,y0,x1,y1=core.bounds;cx,cy=(x0+x1)/2,(y0+y1)/2;radius=(x1-x0)/2
 if radius<=0 or abs((y1-y0)/2-radius)>1e-10:return False
 if any(abs(math.hypot(x-cx,y-cy)-radius)>1e-10 for x,y in coordinates):return False
 angles=[math.atan2(y-cy,x-cx) for x,y in coordinates];steps=[(b-a)%(2*math.pi) for a,b in zip(angles,angles[1:]+angles[:1])];target=2*math.pi/len(coordinates)
 return all(abs(v-target)<1e-7 for v in steps) or all(abs(v-(2*math.pi-target))<1e-7 for v in steps)

class SpindleAdapter:
 def describe(self):
  files=[Path(__file__),Path(__file__).parents[1]/'junction_spindle_stage.py',Path(__file__).parents[1]/'junction_spindle_blend.py']
  return dict(family=CONTRACT.family,implementation=hashlib.sha256(b''.join(p.read_bytes() for p in files)).hexdigest(),operations=['plan','run','verify'],source_support='Explicit trace objects and source-qualified circle/rectangle contacts; no inferred net intent')
 def _context(self,store,scene,policy,details):
  if policy.get('stage')!='t05' or canonical(policy.get('parameters'))!=canonical(dict(asdict(CONTRACT),radius_scales=list(CONTRACT.radius_scales))):fail('POLICY_UNSUPPORTED','fixed spindle family parameters')
  objects={r['source_id']:r for r in scene['objects']};current={s:geometry(store,r['geometry_ref']) for s,r in objects.items()};original={s:geometry(store,r['original_ref']) for s,r in objects.items()};return objects,current,original,box(*scene['viewport_mm'])
 def plan(self,store,scene,policy,selection,bounds):
  closed(selection,{'stage','scene_ref','source_ids'},'spindle selection')
  closed(bounds,{'max_source_objects','max_targets','max_evaluations','max_output_bytes','max_seconds'},'spindle bounds')
  if any(type(v) is not int or v<=0 for v in bounds.values()):fail('FINITE_POSITIVE_BOUNDS_REQUIRED','spindle bounds')
  ids=selection['source_ids']
  if type(ids) is not list or not ids or len(set(ids))!=len(ids) or len(ids)>bounds['max_targets'] or len(scene['objects'])>bounds['max_source_objects']:fail('SCOPE_LIMIT_REACHED','spindle selection')
  objects,current,original,crop=self._context(store,scene,policy,None);routes=[]
  for sid in sorted(ids):
   if sid not in objects or objects[sid]['kind']!='trace':fail('TRACE_SOURCE_REQUIRED',sid)
   declared=objects[sid]['metadata'].get('land_ids')
   if type(declared) is not list or len(set(declared))!=len(declared):fail('EXPLICIT_CONTACT_SELECTION_REQUIRED',sid)
   lands=[];skipped=[]
   for lid in declared:
    if lid not in objects or objects[lid]['kind'] not in ('circle','rectangle','inclusive_rectangle'):fail('LAND_FAMILY_UNSUPPORTED',str(lid))
    core=original[lid];g=current[lid]
    if original[sid].intersection(core).area<=1e-12 or current[sid].intersection(g).area<=1e-12:fail('SOURCE_CONTACT_NOT_ESTABLISHED',sid+':'+lid)
    if objects[lid]['kind']=='circle' and not filled_circle(core):fail('LAND_FAMILY_UNSUPPORTED',lid)
    if any(other!=lid and core.equals(original[other]) and not g.equals(current[other]) for other in objects):fail('LAND_ALIAS_CONFLICT',lid)
    if objects[lid]['kind'] in ('rectangle','inclusive_rectangle') and not g.equals(box(*g.bounds)):fail('LAND_FAMILY_UNSUPPORTED',lid)
    others=[v for k,v in current.items() if k!=lid]
    if g.difference(unary_union(others)).area<=1e-12:skipped.append(lid)
    else:lands.append(lid)
   routes.append(dict(source_id=sid,land_ids=lands,covered_lands=skipped))
  return dict(routes=routes,bounds=bounds,protected_source_ids=sorted(objects),family=CONTRACT.family)
 def _operands(self,store,scene,policy,details,row):
  objects,current,original,crop=self._context(store,scene,policy,details);sid=row['source_id'];lands=[current[k] for k in row['land_ids']]
  # Recheck actual source contacts at execution and replay, not stored booleans.
  for lid in row['land_ids']:
   if original[sid].intersection(original[lid]).area<=1e-12 or current[sid].intersection(current[lid]).area<=1e-12:fail('SOURCE_CONTACT_NOT_ESTABLISHED',lid)
  owner,radius,window=prepare_spindle_context(current[sid],lands,crop);allowed={sid,*row['land_ids']}
  # Complete source vector; envelope preselection retains the original exact
  # intersects test and sorted witness order. Added patches remain separate.
  ordered=list(current);tree=STRtree([current[k] for k in ordered]);query=prepared_buffer(window,CONTRACT.barrier_gap_mm)
  neighbors={ordered[int(i)] for i in tree.query(query.envelope)}
  foreign=[(k,current[k]) for k in sorted(neighbors) if k not in allowed and current[k].intersects(query)]
  return owner,radius,window,foreign
 def run(self,store,scene,policy,plan,checkpoint):
  details=plan['details'];bounds=details['bounds'];objects,current,_,crop=self._context(store,scene,policy,details);before=unary_union([current[k] for k in sorted(current)]).intersection(crop);accepted=[];decisions=[];used=0;started=time.monotonic();output_bytes=0;meter=Budget(bounds)
  for ordinal,row in enumerate(details['routes']):
   if (ACTIVE.get().elapsed() if ACTIVE.get() is not None else time.monotonic()-started)>bounds['max_seconds']:fail('BUDGET_EXHAUSTED','time budget')
   if not row['land_ids']:decisions.append(dict(**row,status='KEEP',reason='NO_EXPOSED_QUALIFIED_CONTACT'));continue
   if used+len(CONTRACT.radius_scales)>bounds['max_evaluations']:fail('BUDGET_EXHAUSTED','radius evaluations')
   owner,radius,window,foreign=self._operands(store,scene,policy,details,row)
   def fit():
    best,attempts=fit_spindle_blend(owner,radius,window,foreign+[(x['id'],x['addition']) for x in accepted])
    return dict(best=None if best is None else dict(scale=best['scale'],check=best['check'],addition_hex=to_wkb(best['addition']).hex()),attempts=attempts)
   fitted=journalled('spindle-fit',dict(row=row,prior_patch_ids=[x['id'] for x in accepted]),fit);attempts=fitted['attempts'];best=fitted['best']
   if best is not None:best=dict(best,addition=from_wkb(bytes.fromhex(best['addition_hex'])))
   used+=len(attempts)
   if best is None:decisions.append(dict(**row,status='KEEP',reason='NO_VALID_BOUNDED_ADDITIVE_BLEND',attempts=attempts))
   else:
    blob=to_wkb(best['addition']);output_bytes+=len(blob)
    if output_bytes>bounds['max_output_bytes']:fail('BUDGET_EXHAUSTED','output bytes')
    patch_ref=store.put('geometry',blob);decisions.append(dict(**row,status='GROWN',scale=best['scale'],patch_ref=patch_ref,attempts=attempts));accepted.append(dict(id=row['source_id'],owner=owner,window=window,addition=best['addition'],foreign=foreign))
   checkpoint(dict(next_ordinal=ordinal+1,evaluations_used=used,decisions=decisions))
  checks=journalled('spindle-batch-final',[dict(id=x['id'],addition_sha256=hashlib.sha256(to_wkb(x['addition'])).hexdigest()) for x in accepted],lambda:verify_spindle_batch(accepted));after=assemble_spindle_scene(before,accepted)
  output_scene=dict(scene,objects=list(scene['objects']),lineage=scene['lineage']+[dict(stage='t05',predecessor_ref=plan['scene_ref'],policy_ref=plan['policy_ref'],implementation=plan['implementation'],plan_ref=store.put_json('plan',plan))],acceptance=dict(owner='PENDING',independent='NOT_RUN',native_electrical_manufacturing='NOT_ESTABLISHED'))
  for d in decisions:
   if d['status']=='GROWN':
    sid='t05-addition:'+d['patch_ref']['sha256']
    if sid in objects:fail('DERIVED_SOURCE_ID_CONFLICT',sid)
    output_scene['objects'].append(dict(source_id=sid,kind='junction_addition',geometry_ref=d['patch_ref'],original_ref=d['patch_ref'],metadata=dict(origin='t05-derived-addition',owner_trace=d['source_id'],predecessor_ref=plan['scene_ref'])))
  return dict(status='CONSTRUCTED',before_ref=store.put('geometry',to_wkb(before)),after_ref=store.put('geometry',to_wkb(after)),output_scene_ref=store.put_json('scene',output_scene),decisions=decisions,checks=checks,protected_source_refs={k:r['geometry_ref'] for k,r in objects.items()},evaluations=used,coverage=dict(targets=len(details['routes']),grown=len(accepted)))
 def verify(self,store,scene,policy,plan,candidate,proof_scope,checkpoint):
  if proof_scope!={'scope':'complete-source-and-all-patches'}:fail('PROOF_SCOPE_UNSUPPORTED','T05 full source replay required')
  details=plan['details'];objects,current,_,crop=self._context(store,scene,policy,details)
  if candidate['protected_source_refs']!={k:r['geometry_ref'] for k,r in objects.items()}:fail('PREDECESSOR_CHANGED','source contribution map')
  before=unary_union([current[k] for k in sorted(current)]).intersection(crop)
  if store.get(candidate['before_ref'],kind='geometry')!=to_wkb(before):fail('SOURCE_RECONSTRUCTION_MISMATCH','before')
  if [r['source_id'] for r in candidate['decisions']]!=[r['source_id'] for r in details['routes']]:fail('COVERAGE_MISMATCH','route decisions')
  patches=[];failures=[];meter=Budget(details['bounds'])
  for row,decision in zip(details['routes'],candidate['decisions']):
   if decision['land_ids']!=row['land_ids'] or decision['covered_lands']!=row['covered_lands']:fail('COVERAGE_MISMATCH','land contacts')
   if decision['status']=='KEEP':continue
   if decision['status']!='GROWN' or decision['scale'] not in CONTRACT.radius_scales:fail('CANDIDATE_INVALID','decision')
   owner,radius,window,foreign=self._operands(store,scene,policy,details,row)
   # Direct construction replay, separate from fit_spindle_blend and its search.
   _,addition=spindle_blend(owner,radius*decision['scale'],window)
   all_foreign=foreign+[(x['id'],x['addition']) for x in patches];barriers=unary_union([g.buffer(CONTRACT.barrier_gap_mm,quad_segs=64) for _,g in all_foreign if not g.difference(owner).is_empty]);addition=addition.difference(barriers)
   if store.get(decision['patch_ref'],kind='geometry')!=to_wkb(addition):fail('PATCH_RECONSTRUCTION_MISMATCH',row['source_id'])
   patches.append(dict(id=row['source_id'],owner=owner,window=window,addition=addition,foreign=foreign))
  checks=[]
  for p in patches:
   meter.evaluation()
   q=journalled('verify-spindle-patch',dict(id=p['id'],addition_sha256=hashlib.sha256(to_wkb(p['addition'])).hexdigest()),lambda:check_spindle(p['owner'],p['owner'].union(p['addition']),p['addition'],p['window'],p['foreign']+[(x['id'],x['addition']) for x in patches if x['id']!=p['id']]));checks.append(q)
   if not q['passed']:failures.extend(q['failures'])
  after=before.union(unary_union([p['addition'] for p in patches]))
  if store.get(candidate['after_ref'],kind='geometry')!=to_wkb(after):fail('SOURCE_RECONSTRUCTION_MISMATCH','after')
  from .scene import validate_scene,composed
  output_scene=validate_scene(store,candidate['output_scene_ref'])
  expected_sources=dict(objects)
  for d in candidate['decisions']:
   if d['status']=='GROWN':
    sid='t05-addition:'+d['patch_ref']['sha256'];expected_sources[sid]=dict(source_id=sid,kind='junction_addition',geometry_ref=d['patch_ref'],original_ref=d['patch_ref'],metadata=dict(origin='t05-derived-addition',owner_trace=d['source_id'],predecessor_ref=plan['scene_ref']))
  expected_lineage=scene['lineage']+[dict(stage='t05',predecessor_ref=plan['scene_ref'],policy_ref=plan['policy_ref'],implementation=plan['implementation'],plan_ref=store.put_json('plan',plan))]
  if output_scene['objects']!=list(expected_sources.values()) or output_scene['lineage']!=expected_lineage or any(output_scene[k]!=scene[k] for k in ['source_sha256','frame','units','layer','viewport_mm','findings']):fail('OUTPUT_SCENE_BINDING_MISMATCH','source map/lineage/frame')
  if composed(store,output_scene).symmetric_difference(after).area>CONTRACT.area_epsilon_mm2:fail('OUTPUT_SCENE_BINDING_MISMATCH','cumulative copper')
  checkpoint(dict(verified_patches=len(patches),coverage='COMPLETE'))
  return dict(passed=not failures,failures=failures,checks=checks,reconstructed_patches=len(patches),removed_area_mm2=before.difference(after).area,proof='Exact original contributions/contact/selected patch replay and simultaneous finite-copper checks; not electrical/native/manufacturing qualification')
