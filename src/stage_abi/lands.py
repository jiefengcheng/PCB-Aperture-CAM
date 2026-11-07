"""T01 round-class and T02 rectangle/inclusive construction plus source replay."""
from src.clearance_policy import HARD_GAP_MM, CONSTRUCTION_GAP_MM, CONTACT_BUFFER_MM, LEGACY_CONSTRUCTION_MM, BARRIER_GAP_MM
from dataclasses import asdict
import hashlib
from pathlib import Path
from math import isfinite
from shapely import to_wkb
from shapely.geometry import Point,box
from shapely.affinity import scale
from shapely.ops import unary_union
from src.prepared_land_scene import PreparedLandScene
from src.trace_width_clearance import TraceWidthContract
from src.joint_rectangle_growth import fit_joint_rectangle
from src.crop_stage_growth import check_proposal,GrowthContract
from .contracts import closed,fail
from .journal import journalled
from .store import canonical
from .scene import geometry,composed
from .runtime import bounds_check,Budget,operands,output_scene,check_output
from src.stage_abi.preparation import prepared_buffer
from src.shape_containment import policy as containment_policy,records as containment_records
from src.t02_rectangle_exposure import capture as exposure_settings,records as exposure_records,eligible as exposure_eligible
from src import t02_shared_gaps as shared_gaps


def land_parameters(stage):
 value=dict(family='round-class/2' if stage=='t01' else 'whole-rectangle-inclusive/2',ceiling=1.5 if stage=='t01' else 1.25,quad_segs=128,search_steps=36,inclusive=stage=='t02',inclusive_shortage=.20 if stage=='t02' else None,original_circle_quad_limit=512 if stage=='t01' else None,surface_contract=asdict(TraceWidthContract()),contained_shape_keep=containment_policy())
 if stage=='t02':value.update(rectangle_exposure_settings=exposure_settings().snapshot(),shared_neighbor_gap_policy=shared_gaps.policy())
 return value

def aligned(core_a,core_b,axis):
 p,q=core_a.bounds,core_b.bounds;j=1-axis;t1,t2=p[j+2]-p[j],q[j+2]-q[j];overlap=min(p[j+2],q[j+2])-max(p[j],q[j]);dc=abs((p[j]+p[j+2]-q[j]-q[j+2])/2);gap=max(p[axis],q[axis])-min(p[axis+2],q[axis+2]);return overlap>=.75*min(t1,t2) and dc<=.15*max(t1,t2) and max(t1,t2)<=2*min(t1,t2) and 0<=gap<=2*max(p[axis+2]-p[axis],q[axis+2]-q[axis])

def merge_groups(ids,cores):
 groups=[]
 for axis in (0,1):
  remaining=set(ids)
  while remaining:
   seed=min(remaining);remaining.remove(seed);group={seed};pending=[seed]
   while pending:
    a=pending.pop();links={b for b in remaining if aligned(cores[a],cores[b],axis)};group.update(links);remaining-=links;pending.extend(sorted(links))
   if len(group)>1:
    members=sorted(group,key=lambda s:cores[s].bounds[axis])
    for first in range(len(members)-1):
     for last in range(first+2,len(members)+1):groups.append((axis,tuple(sorted(members[first:last]))))
 return sorted(set(groups),key=lambda x:(-len(x[1]),x[0],x[1]))

class LandAdapter:
 def __init__(self,stage):
  if stage not in ('t01','t02'):raise ValueError('T01_OR_T02_REQUIRED')
  self.stage=stage
 def describe(self):
  files=[Path(__file__),Path(__file__).with_name('runtime.py'),Path(__file__).parents[1]/'prepared_land_scene.py',Path(__file__).parents[1]/'joint_rectangle_growth.py',Path(__file__).parents[1]/'prepared_width_scene.py',Path(__file__).parents[1]/'crop_stage_growth.py',Path(__file__).parents[1]/'shape_containment.py']
  if self.stage=='t02':files.extend([Path(shared_gaps.__file__),Path(__file__).parents[1]/'t02_rectangle_exposure.py',Path(__file__).parents[1]/'t02_gap_settings.py'])
  return dict(family=land_parameters(self.stage)['family'],implementation=hashlib.sha256(b''.join(p.read_bytes() for p in files)).hexdigest(),operations=['plan','run','verify'],source_support='Filled circles with explicit diameter classes' if self.stage=='t01' else 'Axis-aligned filled rectangles and connected inclusive fills; no trace/junction edits')
 def _context(self,store,scene,policy,details):
  if policy.get('stage')!=self.stage or canonical(policy.get('parameters'))!=canonical(land_parameters(self.stage)):fail('POLICY_UNSUPPORTED','land family')
  rows,current,original=operands(store,scene);ids=details['targets']
  if details.get('containment')!=containment_records(current,ids):fail('CONTAINMENT_PLAN_CHANGED','Reconstruct stage-entry copper and aliases')
  if self.stage=='t02'and details.get('rectangle_exposure')!=exposure_records(scene,original,ids,exposure_settings()):fail('RECTANGLE_EXPOSURE_PLAN_CHANGED','Reconstruct original perimeter eligibility')
  if self.stage=='t02'and details.get('shared_neighbor_gaps')!=shared_gaps.records(scene,original,current):fail('SHARED_GAP_PLAN_CHANGED','Reconstruct complete original neighbor faces')
  kind='gr_circle' if self.stage=='t01' else 'gr_poly';parts=[dict(id=s,original=current[s],candidate=current[s],native_source_kind=kind,native_stroke_width_mm=0.) for s in ids];fixed=[dict(id=s,geometry=g,trace_width_mm=rows[s]['metadata'].get('nominal_width_mm',0.)) for s,g in current.items() if s not in ids];checker=PreparedLandScene(parts,fixed)
  # Current predecessor geometry provides visibility; only original contacts may
  # authorize land-to-trace attachment ports after earlier route/width changes.
  for sid in ids:
   for oid in checker.ids:
    if oid==sid:continue
    if not original[sid].intersects(original[oid]):
     checker.ports[(sid,oid)]=(None,False,original[sid].distance(original[oid]));continue
    overlap=original[sid].intersection(original[oid]);width=max(checker.widths[sid],checker.widths[oid])+checker.contract.original_port_buffer_gap_mm;checker.ports[(sid,oid)]=(prepared_buffer(overlap,width,quad_segs=checker.contract.port_quad_segs),True,original[sid].distance(original[oid]))
  return rows,current,original,checker,box(*scene['viewport_mm'])
 def plan(self,store,scene,policy,selection,bounds):
  closed(selection,{'stage','scene_ref','source_ids'},'land selection');bounds_check(bounds,scene,selection);rows,current,original=operands(store,scene);targets=sorted(selection['source_ids']);parameters={}
  for sid in targets:
   r=rows[sid];g=current[sid]
   if r['kind']!=('circle' if self.stage=='t01' else 'rectangle'):fail('LAND_FAMILY_UNSUPPORTED',sid)
   if r['metadata'].get('fixed_bulk',False):fail('PROTECTED_SOURCE_SELECTED',sid)
   if self.stage=='t01':
    meta=r['metadata'];center=meta.get('center_mm');radius=meta.get('original_radius_mm');diameters=meta.get('admissible_diameters_mm');desired=meta.get('desired_diameter_mm')
    if type(center) is not list or len(center)!=2 or any(type(v) not in (int,float) or not isfinite(v) for v in center) or type(radius) not in (int,float) or radius<=0 or not isfinite(radius) or type(diameters) is not list or not diameters or any(type(v) not in (int,float) or not isfinite(v) or v<=0 for v in diameters) or type(desired) not in (int,float) or not isfinite(desired) or desired<=0:fail('SOURCE_CIRCLE_CLASSES_REQUIRED',sid)
    original_quad=meta.get('original_quad_segs',128)
    if type(original_quad) is not int or not 4<=original_quad<=512:fail('SOURCE_CIRCLE_TESSELLATION_UNSUPPORTED',sid)
    source=Point(*center).buffer(radius,quad_segs=original_quad)
    if not source.equals(original[sid]):fail('SOURCE_CIRCLE_BINDING_MISMATCH',sid)
    if not Point(*center).buffer(1.5*radius,quad_segs=128).covers(g):fail('PREDECESSOR_OUTSIDE_CIRCLE_CAP',sid)
    parameters[sid]=dict(center_mm=center,radius_mm=radius,diameters=sorted({d for d in diameters if d<=min(desired,3*radius)},reverse=True))
   else:
    core=original[sid]
    if not core.equals(box(*core.bounds)) or not g.equals(box(*g.bounds)):fail('WHOLE_RECTANGLE_REQUIRED',sid)
    cap=scale(core,1.25,1.25,origin=core.centroid)
    if not g.covers(core) or not cap.covers(g) or g.centroid.distance(core.centroid)>1e-12:fail('PREDECESSOR_OUTSIDE_RECTANGLE_CAP',sid)
  details=dict(targets=targets,bounds=bounds,parameters=parameters,family=land_parameters(self.stage)['family'],containment=containment_records(current,targets))
  if self.stage=='t02':details['rectangle_exposure']=exposure_records(scene,original,targets,exposure_settings())
  if self.stage=='t02':details['shared_neighbor_gaps']=shared_gaps.records(scene,original,current)
  self._context(store,scene,policy,details);return details
 def _check(self,checker,current,selected,ids):
  kind='gr_circle' if self.stage=='t01' else 'gr_poly'
  return journalled('land-simultaneous-check',{s:hashlib.sha256(to_wkb(selected[s])).hexdigest() for s in ids},lambda:checker.check([dict(id=s,original=current[s],candidate=selected[s],native_source_kind=kind,native_stroke_width_mm=0.) for s in ids],materialize_scene=True))
 def _shared_project(self,store,details,rows,current,original,selected,decisions,budget):
  factors={d['source_id']:d['shape'].get('factors',[1.,1.])for d in decisions}
  selected,proof=shared_gaps.project(details['shared_neighbor_gaps'],original,current,selected,factor_rows=factors)
  for d in decisions:
   sid=d['source_id'];g=selected[sid];d['pre_shared_factors']=factors[sid]
   d['shape']={'factors':proof['factors'][sid]}if not g.equals(current[sid])else{}
   if d['status']!='COVERED_SKIP':d['status']='GROWN'if g.difference(current[sid]).area>1e-12 else'KEEP'
   blob=to_wkb(g);budget.output(blob);d['candidate_ref']=rows[sid]['geometry_ref']if g.equals(current[sid])else store.put('geometry',blob)
  shared_gaps.complete(proof,unary_union(list(dict(current,**selected).values())))
  return selected,proof
 def run(self,store,scene,policy,plan,checkpoint):
  details=plan['details'];rows,current,original,checker,crop=self._context(store,scene,policy,details);ids=details['targets'];selected={s:current[s] for s in ids};budget=Budget(details['bounds']);decisions=[]
  for ordinal,sid in enumerate(ids):
   core=current[sid];covered=details['containment'][sid]['contained'];attempts=[]
   def feasible(candidate):
    budget.evaluation();trial=dict(selected,**{sid:candidate});q=self._check(checker,current,trial,ids);cap_ok=self.stage!='t02' or scale(original[sid],1.25,1.25,origin=original[sid].centroid).covers(candidate);passed=q['passed'] and candidate.covers(core) and cap_ok and candidate.difference(crop).area<=1e-12;attempts.append(dict(candidate_sha256=hashlib.sha256(to_wkb(candidate)).hexdigest(),passed=passed,failures=q['failures']+([] if cap_ok else [dict(reason='ORIGINAL_RECTANGLE_CEILING_EXCEEDED')])));return passed
   candidate=core;shape={}
   if not covered and self.stage=='t01':
    p=details['parameters'][sid]
    for d in p['diameters']:
     trial=Point(*p['center_mm']).buffer(d/2,quad_segs=128)
     if not trial.covers(core):continue
     if feasible(trial):candidate=trial;shape=dict(diameter_mm=d);break
   elif not covered and exposure_eligible(details,sid):
    candidate,factors=fit_joint_rectangle(core,feasible,max_factor=1.25,steps=36);shape=dict(factors=list(factors))
   if not feasible(candidate):fail('LAND_KEEP_OR_CANDIDATE_INVALID',sid)
   held=self.stage=='t02'and not exposure_eligible(details,sid)
   selected[sid]=candidate;blob=to_wkb(candidate);budget.output(blob);decisions.append(dict(source_id=sid,status='COVERED_SKIP' if covered else 'GROWN' if candidate.difference(core).area>1e-12 else 'KEEP',shape=shape,candidate_ref=rows[sid]['geometry_ref']if covered or held else store.put('geometry',blob),attempts=attempts,**({'keep_reason':'EXPOSED_PERIMETER_BELOW_LIMIT'}if held and not covered else{})));checkpoint(dict(next_ordinal=ordinal+1,evaluations=budget.evaluations,decisions=decisions))
  shared=None
  if self.stage=='t02':selected,shared=self._shared_project(store,details,rows,current,original,selected,decisions,budget)
  final=self._check(checker,current,selected,ids)
  if not final['passed']:fail('SIMULTANEOUS_LAND_CHECK_FAILED','final')
  current_after=dict(current,**selected);merges=[];additions=[]
  if self.stage=='t02':merges,additions=self._merges(store,scene,plan,rows,current_after,budget)
  replacements={r['source_id']:r['candidate_ref'] for r in decisions};out_ref,out=output_scene(store,scene,plan,replacements=replacements,additions=additions,shared_gap_state_ref=store.put_json('shared-gap-state',shared)if shared is not None else None)
  if shared is not None:shared_gaps.complete(shared,composed(store,out))
  return dict(status='CONSTRUCTED',before_ref=store.put('geometry',to_wkb(composed(store,scene))),after_ref=store.put('geometry',to_wkb(composed(store,out))),output_scene_ref=out_ref,decisions=decisions,inclusive_candidates=merges,checks=final,evaluations=budget.evaluations,protected_source_refs={s:r['geometry_ref'] for s,r in rows.items() if s not in ids},**({'shared_neighbor_gaps':shared}if shared is not None else{}))
 def _merges(self,store,scene,plan,rows,current,budget):
  crop=box(*scene['viewport_mm']);ids=[s for s in plan['details']['targets']if not plan['details']['containment'][s]['contained']and exposure_eligible(plan['details'],s)];groups=merge_groups(ids,current);before=unary_union([current[s] for s in sorted(current)]).intersection(crop);claimed=set();accepted=[];decisions=[];additions=[]
  for ordinal,(axis,members) in enumerate(groups):
   budget.evaluation();rect=box(*unary_union([current[s] for s in members]).bounds);span=before.intersection(rect);shortage=rect.difference(span).area/rect.area;near=[s for s,g in current.items() if g.intersects(rect.buffer(HARD_GAP_MM+.001))];supports=set(members)|{s for s in near if rows[s]['kind']=='trace' and current[s].intersection(span).area>0};support_union=unary_union([current[s] for s in supports]);covered={s for s in near if s not in supports and current[s].difference(support_union).is_empty};neighbors=[dict(source_id=s,original=current[s],geometry=current[s],trace_width_mm=rows[s]['metadata'].get('nominal_width_mm',0.)) for s in near if s not in supports|covered];q=journalled('inclusive-land-check',dict(axis=axis,members=list(members),span_sha256=hashlib.sha256(to_wkb(span)).hexdigest(),rectangle_sha256=hashlib.sha256(to_wkb(rect)).hexdigest()),lambda:check_proposal(span,rect,neighbors,crop=crop,cap=rect,contract=GrowthContract()));delta=rect.difference(before);reasons=[]
   from src.growth_remedy_constraints import remedy as pin_remedy
   pin_check=pin_remedy(rect,before)
   shared_check=shared_gaps.fill_check(plan['details'],current,rect)
   if shared_check is not None and not shared_check['passed']:reasons.append('SHARED_NEIGHBOR_GAP_ENTIRE_FILL')
   if pin_check is not None and not pin_check['passed']:reasons.append('PROTECTED_PIN_SEPARATION_ENTIRE_FILL')
   if shortage>.20:reasons.append('SHORTAGE_ABOVE_20_PERCENT')
   if span.geom_type!='Polygon':reasons.append('SPAN_NOT_ONE_CONNECTED_SURFACE')
   if claimed.intersection(members):reasons.append('SOURCE_ALREADY_MERGED')
   if not q['passed']:reasons.append('FOREIGN_CLEARANCE_FAILED')
   if delta.area<=1e-12:reasons.append('NO_VISIBLE_ADDITION')
   if any(not old.difference(span).is_empty and delta.distance(old.difference(span))<CONSTRUCTION_GAP_MM for old in accepted):reasons.append('PRIOR_MERGE_CLEARANCE_FAILED')
   record=dict(ordinal=ordinal,members=list(members),axis=axis,shortage=shortage,status='REJECTED' if reasons else 'MERGED',reasons=reasons,check=q)
   if pin_check is not None:record['pin_separation']=pin_check
   if shared_check is not None:record['shared_neighbor_gaps']=shared_check
   if not reasons:
    blob=to_wkb(rect);budget.output(blob);reference=store.put('geometry',blob);sid='t02-inclusive:'+reference['sha256'];additions.append(dict(source_id=sid,kind='inclusive_rectangle',original_ref=reference,geometry_ref=reference,metadata=dict(origin='t02-inclusive-fill',members=list(members))));record['candidate_ref']=reference;accepted.append(rect);before=before.union(rect);claimed.update(members)
   decisions.append(record)
  return decisions,additions
 def verify(self,store,scene,policy,plan,candidate,proof_scope,checkpoint):
  if proof_scope!={'scope':'complete-source-land-and-inclusive'}:fail('PROOF_SCOPE_UNSUPPORTED','complete land replay required')
  details=plan['details'];rows,current,original,checker,crop=self._context(store,scene,policy,details);ids=details['targets'];selected={};replacements={}
  if [r['source_id'] for r in candidate['decisions']]!=ids:fail('COVERAGE_MISMATCH','target decisions')
  if candidate['protected_source_refs']!={s:r['geometry_ref'] for s,r in rows.items() if s not in ids}:fail('PREDECESSOR_CHANGED','protected contributions')
  for row in candidate['decisions']:
   sid=row['source_id'];core=current[sid];shape=row['shape'];status=row['status'];g=core
   contained=details['containment'][sid]['contained']
   if self.stage=='t02'and not exposure_eligible(details,sid)and(status not in('KEEP','COVERED_SKIP')or row['candidate_ref']!=rows[sid]['geometry_ref']):fail('RECTANGLE_EXPOSURE_KEEP_CHANGED',sid)
   if contained and (status!='COVERED_SKIP' or row['candidate_ref']!=rows[sid]['geometry_ref']):fail('CONTAINED_SHAPE_CHANGED',sid)
   if not contained and status=='COVERED_SKIP':fail('FALSE_COVERED_SKIP',sid)
   if status=='GROWN':
    if self.stage=='t01':
     p=details['parameters'][sid];d=shape['diameter_mm']
     if d not in p['diameters']:fail('CIRCLE_CLASS_OUT_OF_SCOPE',sid)
     g=Point(*p['center_mm']).buffer(d/2,quad_segs=128)
    else:
     sx,sy=shape['factors']
     if not 1<=sx<=1.25 or not 1<=sy<=1.25:fail('RECTANGLE_SCALE_OUT_OF_SCOPE',sid)
     g=scale(core,sx,sy,origin=core.centroid)
   elif status not in ('KEEP','COVERED_SKIP'):fail('LAND_DECISION_INVALID',sid)
   if self.stage=='t02' and not scale(original[sid],1.25,1.25,origin=original[sid].centroid).covers(g):fail('RECTANGLE_SCALE_OUT_OF_SCOPE',sid)
   if not g.covers(core) or g.difference(crop).area>1e-12 or (not contained and store.get(row['candidate_ref'],kind='geometry')!=to_wkb(g)):fail('LAND_RECONSTRUCTION_MISMATCH',sid)
   selected[sid]=g;replacements[sid]=row['candidate_ref']
  final=self._check(checker,current,selected,ids)
  if self.stage=='t02':
   factors={d['source_id']:d.get('pre_shared_factors')for d in candidate['decisions']}
   if any(type(v)is not list or len(v)!=2 or any(type(f)not in(int,float)or not isfinite(f)or not 1<=f<=1.25 for f in v)for v in factors.values()):fail('SHARED_GAP_PROPOSAL_CHANGED','Bounded pre-projection factors required')
   proposed={s:current[s]if factors[s]==[1.,1.]else scale(current[s],*factors[s],origin=current[s].centroid)for s in ids}
   projected,shared=shared_gaps.project(details['shared_neighbor_gaps'],original,current,proposed,factor_rows=factors)
   if shared!=candidate.get('shared_neighbor_gaps')or any(to_wkb(projected[s])!=to_wkb(selected[s])for s in ids):fail('SHARED_GAP_RECONSTRUCTION_CHANGED','Source-bound bank projection')
   shared_gaps.complete(shared,unary_union(list(dict(current,**selected).values())))
  additions=[]
  if self.stage=='t02':
   # Re-evaluate connected span, shortage and all foreign/prior-fill relations
   # from the reconstructed ordinary scene, not stored acceptance booleans.
   merged,additions=self._merges(store,scene,plan,rows,dict(current,**selected),Budget(details['bounds']))
   if merged!=candidate['inclusive_candidates']:fail('INCLUSIVE_RECONSTRUCTION_MISMATCH','complete merge ledger')
  elif candidate['inclusive_candidates']:fail('T02_SCOPE_LEAK','T01 cannot merge rectangles')
  out=check_output(store,scene,plan,candidate,replacements=replacements,additions=additions,shared_gap_state_ref=store.put_json('shared-gap-state',shared)if self.stage=='t02'else None)
  if self.stage=='t02':shared_gaps.complete(shared,composed(store,out))
  checkpoint(dict(reconstructed_targets=len(ids),inclusive_fills=len(additions)))
  return dict(passed=final['passed'],failures=final['failures'],check=final,reconstructed_targets=len(ids),inclusive_fills=len(additions),scope='Complete selected land source replay and current simultaneous finite-surface geometry; no electrical/manufacturing claim')
