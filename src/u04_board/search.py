"""U04 T02 search: unchanged finite predicates, full final materialization."""
import hashlib
from pathlib import Path
from shapely import to_wkb,from_wkb,STRtree
from shapely.geometry import box
from shapely.affinity import scale
from shapely.ops import unary_union
from src.stage_abi.lands import LandAdapter,merge_groups
from src.stage_abi.runtime import Budget,output_scene,operands
from src.stage_abi.scene import composed
from src.stage_abi.store import digest,canonical
from src.stage_abi.contracts import fail
from src.stage_abi.journal import journalled
from src.joint_rectangle_growth import fit_joint_rectangle
from src.crop_stage_growth import check_proposal,GrowthContract

class FastRectangleAdapter(LandAdapter):
 def describe(self):
  value=super().describe()
  value['implementation']=digest(canonical(value)+Path(__file__).read_bytes())
  return value
 def plan(self,store,scene,policy,selection,bounds):
  details=super().plan(store,scene,policy,selection,bounds)
  _,_,original=operands(store,scene)
  details['targets']=sorted(details['targets'],key=lambda s:(original[s].centroid.y,original[s].centroid.x,s))
  return details
 def _context(self,store,scene,policy,details):
  key=(id(store),digest(canonical(dict(scene=scene,policy=policy,targets=sorted(details['targets'])))))
  if getattr(self,'_prepared_key',None)==key:
   # Re-read every content-addressed operand. Reuse only immutable source
   # preparation inside this invocation; every candidate predicate still runs.
   operands(store,scene)
   return self._prepared_context
  rows,current,original,checker,crop=super()._context(store,scene,policy,details)
  # Port permission remains bound to original native source widths, even
  # though the finite obstacle surface is the widened current predecessor.
  for oid,row in rows.items():checker.widths[oid]=row['metadata'].get('original_width_mm',checker.widths[oid])
  for sid in details['targets']:
   for oid in checker.ids:
    if oid==sid:continue
    width=max(checker.widths[sid],checker.widths[oid])+checker.contract.original_port_buffer_gap_mm
    contact=original[sid].intersects(original[oid]);overlap=original[sid].intersection(original[oid]) if contact else None
    checker.ports[(sid,oid)]=(overlap.buffer(width,quad_segs=checker.contract.port_quad_segs) if contact else None,contact,original[sid].distance(original[oid]))
  self._prepared_key=key;self._prepared_context=(rows,current,original,checker,crop)
  return self._prepared_context
 def _trial_check(self,checker,current,selected,ids):
  # Only derived full-scene diagnostics are deferred. Every finite pair,
  # visibility, attachment, growth and failure witness is still evaluated.
  return journalled('land-simultaneous-check',{s:hashlib.sha256(to_wkb(selected[s])).hexdigest() for s in ids},lambda:checker.check([dict(id=s,original=current[s],candidate=selected[s],native_source_kind='gr_poly',native_stroke_width_mm=0.) for s in ids],materialize_scene=False))
 @staticmethod
 def covered(core,sid,current,ids,tree,aliases):
  # A positive-area interior square with no foreign intersection proves
  # NOT covered. No union operand is removed. Ambiguity uses the complete
  # reference union in its original order.
  x0,y0,x1,y1=core.bounds;half=min(x1-x0,y1-y0)*.001
  if (2*half)**2>1e-10:
   for fx in (.125,.375,.625,.875):
    for fy in (.125,.375,.625,.875):
     x=x0+fx*(x1-x0);y=y0+fy*(y1-y0);square=box(x-half,y-half,x+half,y+half)
     if core.covers(square) and not any(ids[int(i)] not in aliases for i in tree.query(square,predicate='intersects')):return False
  return core.difference(unary_union([g for s,g in current.items() if s not in aliases])).area<=1e-12
 def run(self,store,scene,policy,plan,checkpoint):
  details=plan['details'];rows,current,original,checker,crop=self._context(store,scene,policy,details);ids=details['targets'];selected={s:current[s] for s in ids};budget=Budget(details['bounds']);decisions=[];source_ids=list(current);tree=STRtree([current[s] for s in source_ids])
  for ordinal,sid in enumerate(ids):
   core=current[sid];aliases={s for s in ids if original[s].equals(original[sid])};covered=self.covered(core,sid,current,source_ids,tree,aliases);attempts=[]
   def feasible(candidate):
    budget.evaluation();trial=dict(selected,**{sid:candidate});q=self._trial_check(checker,current,trial,ids);cap_ok=self.stage!='t02' or scale(original[sid],1.25,1.25,origin=original[sid].centroid).covers(candidate);passed=q['passed'] and candidate.covers(core) and cap_ok and candidate.difference(crop).area<=1e-12;attempts.append(dict(candidate_sha256=hashlib.sha256(to_wkb(candidate)).hexdigest(),passed=passed,failures=q['failures']+([] if cap_ok else [dict(reason='ORIGINAL_RECTANGLE_CEILING_EXCEEDED')])));return passed
   candidate=core;shape={}
   if not covered and self.stage=='t01':
    p=details['parameters'][sid]
    for d in p['diameters']:
     trial=Point(*p['center_mm']).buffer(d/2,quad_segs=128)
     if not trial.covers(core):continue
     if feasible(trial):candidate=trial;shape=dict(diameter_mm=d);break
   elif not covered:
    candidate,factors=fit_joint_rectangle(core,feasible,max_factor=1.25,steps=36);shape=dict(factors=list(factors))
   if not feasible(candidate):fail('LAND_KEEP_OR_CANDIDATE_INVALID',sid)
   selected[sid]=candidate;blob=to_wkb(candidate);budget.output(blob);decisions.append(dict(source_id=sid,status='COVERED_SKIP' if covered else 'GROWN' if candidate.difference(core).area>1e-12 else 'KEEP',shape=shape,candidate_ref=store.put('geometry',blob),attempts=attempts));checkpoint(dict(next_ordinal=ordinal+1,evaluations=budget.evaluations,decisions=decisions))
  final=self._check(checker,current,selected,ids)
  if not final['passed']:fail('SIMULTANEOUS_LAND_CHECK_FAILED','final')
  current_after=dict(current,**selected);merges=[];additions=[]
  if self.stage=='t02':merges,additions=self._merges(store,scene,plan,rows,current_after,budget)
  replacements={r['source_id']:r['candidate_ref'] for r in decisions};out_ref,out=output_scene(store,scene,plan,replacements=replacements,additions=additions)
  return dict(status='CONSTRUCTED',before_ref=store.put('geometry',to_wkb(composed(store,scene))),after_ref=store.put('geometry',to_wkb(composed(store,out))),output_scene_ref=out_ref,decisions=decisions,inclusive_candidates=merges,checks=final,evaluations=budget.evaluations,protected_source_refs={s:r['geometry_ref'] for s,r in rows.items() if s not in ids})
 def _merges(self,store,scene,plan,rows,current,budget):
  crop=box(*scene['viewport_mm']);ids=plan['details']['targets'];groups=merge_groups(ids,{s:from_wkb(store.get(rows[s]['original_ref'],kind='geometry')) for s in ids});before=unary_union([current[s] for s in sorted(current)]).intersection(crop);claimed=set();accepted=[];decisions=[];additions=[];source_ids=list(current);tree=STRtree([current[s] for s in source_ids])
  for ordinal,(axis,members) in enumerate(groups):
   budget.evaluation();rect=box(*unary_union([current[s] for s in members]).bounds);span=before.intersection(rect);shortage=rect.difference(span).area/rect.area;near=[source_ids[i] for i in sorted(map(int,tree.query(rect.buffer(.021),predicate='intersects')))];supports=set(members)|{s for s in near if rows[s]['kind']=='trace' and current[s].intersection(span).area>0};support_union=unary_union([current[s] for s in supports]);covered={s for s in near if s not in supports and current[s].difference(support_union).is_empty};neighbors=[dict(source_id=s,original=current[s],geometry=current[s],trace_width_mm=rows[s]['metadata'].get('original_width_mm',rows[s]['metadata'].get('nominal_width_mm',0.))) for s in near if s not in supports|covered];q=journalled('inclusive-land-check',dict(axis=axis,members=list(members),span_sha256=hashlib.sha256(to_wkb(span)).hexdigest(),rectangle_sha256=hashlib.sha256(to_wkb(rect)).hexdigest()),lambda:check_proposal(span,rect,neighbors,crop=crop,cap=rect,contract=GrowthContract()));delta=rect.difference(before);reasons=[]
   if shortage>.20:reasons.append('SHORTAGE_ABOVE_20_PERCENT')
   if span.geom_type!='Polygon':reasons.append('SPAN_NOT_ONE_CONNECTED_SURFACE')
   if claimed.intersection(members):reasons.append('SOURCE_ALREADY_MERGED')
   if not q['passed']:reasons.append('FOREIGN_CLEARANCE_FAILED')
   if delta.area<=1e-12:reasons.append('NO_VISIBLE_ADDITION')
   if any(not old.difference(span).is_empty and delta.distance(old.difference(span))<.0201 for old in accepted):reasons.append('PRIOR_MERGE_CLEARANCE_FAILED')
   record=dict(ordinal=ordinal,members=list(members),axis=axis,shortage=shortage,status='REJECTED' if reasons else 'MERGED',reasons=reasons,check=q)
   if not reasons:
    blob=to_wkb(rect);budget.output(blob);reference=store.put('geometry',blob);sid='t02-inclusive:'+reference['sha256'];additions.append(dict(source_id=sid,kind='inclusive_rectangle',original_ref=reference,geometry_ref=reference,metadata=dict(origin='t02-inclusive-fill',members=list(members))));record['candidate_ref']=reference;accepted.append(rect);before=before.union(rect);claimed.update(members)
   decisions.append(record)
  return decisions,additions
