"""T03 obstacle-directed adaptive single/bundle polyline route generator.

A versioned polyline/miter family, not an alias for the historical fixed-width
C2 launcher. Native curved families must be separately admitted, never coerced.
"""
import hashlib,math
from pathlib import Path
from shapely import to_wkb
from shapely.geometry import LineString,Point,box
from shapely.ops import nearest_points
from src.parallel_route_geometry import points,parallel_points,displaced_reference,extension_distance,route_copper
from .contracts import closed,fail
from .journal import journalled
from .store import canonical
from .scene import geometry,composed
from .runtime import Budget,bounds_check,operands,output_scene,check_output
from .derived_routes import route_authorities


def route_parameters():return dict(family='bounded-parallel-polyline-miter/1',construction_gap_mm=.02010,hard_gap_mm=.02000,epsilon_mm=1e-12,quad_segs=128,max_source_quad_segs=512,miter_limit=4.,displacement_multipliers=[1.,1.5,2.,4.])
EXTRA={'max_displacement_um','max_members','max_extension_um','max_extension_steps','max_recursion_depth'}

class RouteAdapter:
 def describe(self):
  files=[Path(__file__),Path(__file__).with_name('runtime.py'),Path(__file__).parents[1]/'parallel_route_geometry.py']
  return dict(family=route_parameters()['family'],implementation=hashlib.sha256(b''.join(p.read_bytes() for p in files)).hexdigest(),operations=['plan','search','verify'],source_support='Exact polygonal constant-width polyline footprints; shared reference offsets with analytic segment/miter joins, fixed endpoint tangents; no sampled-only parallel proof or inferred net intent')
 def _context(self,store,scene,policy,details):
  if policy.get('stage')!='t03' or canonical(policy.get('parameters'))!=canonical(route_parameters()):fail('POLICY_UNSUPPORTED','bounded route family')
  rows,current,original=operands(store,scene);reference=details['bundle']['reference_points_mm'];members=details['bundle']['members'];ids=set()
  for member in members:
   sid=member['source_id'];row=rows.get(sid)
   if row is None or sid in ids or row['kind']!='trace' or row['metadata'].get('fixed_bulk',False):fail('MOVABLE_ROUTE_INVALID',sid)
   ids.add(sid);width=row['metadata'].get('nominal_width_mm')
   if type(width) not in (int,float) or not math.isfinite(width) or width<=0:fail('ORIGINAL_WIDTH_UNRESOLVED',sid)
   quad=row['metadata'].get('route_quad_segs',128)
   if type(quad) is not int or not 1<=quad<=512:fail('SOURCE_TESSELLATION_UNSUPPORTED',sid)
   p=parallel_points(reference,member['offset_mm']);g=route_copper(p,width,quad_segs=quad)
   if p!=row['metadata'].get('route_points_mm') or not g.equals(current[sid]):fail('SOURCE_ROUTE_GEOMETRY_MISMATCH',sid)
  return rows,current,original
 def plan(self,store,scene,policy,selection,bounds):
  closed(selection,{'stage','scene_ref','source_ids','seed_ids','obstacle_ids','bundle_ref','corridor_ref','initial_indices','objective'},'route selection');bounds_check(bounds,scene,selection,extra=EXTRA)
  if any(type(bounds[k]) is not int or bounds[k]<=0 for k in EXTRA):fail('FINITE_POSITIVE_BOUNDS_REQUIRED','adaptive route limits')
  bundle=store.get_json(selection['bundle_ref'],kind='parallel-bundle');closed(bundle,{'reference_points_mm','members'},'parallel bundle');reference=points(bundle['reference_points_mm'])
  if type(bundle['members']) is not list or not bundle['members']:fail('PARALLEL_BUNDLE_REQUIRED','members')
  for row in bundle['members']:
   closed(row,{'source_id','offset_mm'},'bundle member')
   if type(row['offset_mm']) not in (int,float) or not math.isfinite(row['offset_mm']):fail('FINITE_OFFSET_REQUIRED','member')
  member_ids=[r['source_id'] for r in bundle['members']]
  if set(member_ids)!=set(selection['source_ids']) or len(member_ids)!=len(set(member_ids)) or len({m['offset_mm'] for m in bundle['members']})!=len(member_ids):fail('PARALLEL_BUNDLE_PARTITION_INVALID','source IDs/offsets')
  seed=selection['seed_ids'];obstacles=selection['obstacle_ids']
  if type(seed) is not list or not seed or len(set(seed))!=len(seed) or not set(seed)<=set(member_ids) or len(seed)>bounds['max_members'] or type(obstacles) is not list or not obstacles or set(obstacles)&set(member_ids):fail('ROUTE_SELECTION_INVALID','seed/obstacles')
  indices=selection['initial_indices']
  if type(indices) is not list or len(indices)!=2 or any(type(i) is not int for i in indices) or not 2<=indices[0]<=indices[1]<=len(reference)-3:fail('BOUND_PATCH_PORTS_REQUIRED','initial indices')
  if selection['objective'] not in ('growth-clearance','explicit-clearance'):fail('ROUTE_OBJECTIVE_UNSUPPORTED','explicit objective required')
  corridor=geometry(store,selection['corridor_ref']);details=dict(bundle=bundle,seed_ids=sorted(seed),obstacle_ids=sorted(obstacles),initial_indices=indices,corridor_ref=selection['corridor_ref'],bounds=bounds,objective=selection['objective'])
  rows,current,original=self._context(store,scene,policy,details)
  if not set(obstacles)<=set(rows) or any(rows[s]['kind']=='trace' for s in obstacles):fail('FIXED_OBSTACLE_REQUIRED','primary obstacles')
  if selection['objective']=='growth-clearance' and all(current[s].equals(original[s]) for s in [*seed,*obstacles]):fail('NO_GROWTH_CAUSED_OBJECTIVE','unchanged inherited relationships need explicit authority')
  for sid in member_ids:
   width=rows[sid]['metadata']['nominal_width_mm'];p=rows[sid]['metadata']['route_points_mm'];ports=Point(p[0]).buffer(width+.02002).union(Point(p[-1]).buffer(width+.02002))
   for other,g in current.items():
    if other==sid or rows[other]['kind']!='trace':continue
    contact=current[sid].intersection(g)
    if not contact.is_empty and contact.difference(ports).area>1e-12:fail('UNQUALIFIED_BRANCH_OR_MIDROUTE_CONTACT',sid+':'+other)
  return details
 def _check(self,store,scene,details,paths,moving,*,require_objective=True):
  q=journalled('route-candidate-check',dict(paths=paths,moving=sorted(moving),require_objective=require_objective),lambda:self._check_impl(store,scene,details,paths,moving,require_objective=require_objective)[0])
  return q,None
 def _check_impl(self,store,scene,details,paths,moving,*,require_objective=True):
  rows,current,original=operands(store,scene);updated=dict(current);failures=[];pairs=[];corridor=geometry(store,details['corridor_ref']);gap=.0201;epsilon=1e-12
  for sid in moving:
   p=paths[sid];old=rows[sid]['metadata']['route_points_mm'];width=rows[sid]['metadata']['nominal_width_mm']
   if p[0]!=old[0] or p[-1]!=old[-1]:failures.append(dict(source_id=sid,reason='CUT_PORT_CHANGED'))
   candidate=route_copper(p,width,quad_segs=rows[sid]['metadata'].get('route_quad_segs',128));updated[sid]=candidate
   if not LineString(p).is_simple or not candidate.is_valid or candidate.geom_type!='Polygon':failures.append(dict(source_id=sid,reason='INVALID_ROUTE_OR_COPPER'))
   if candidate.symmetric_difference(current[sid]).difference(corridor).area>epsilon:failures.append(dict(source_id=sid,reason='OUTSIDE_WRITABLE_CORRIDOR'))
  for sid in sorted(moving):
   candidate=updated[sid];old=current[sid];added=candidate.difference(old)
   for other in sorted(updated):
    if other==sid:continue
    g=updated[other];contact=original[sid].intersection(original[other]);d0=old.distance(current[other]);d=candidate.distance(g);port=None if contact.is_empty else contact.buffer(rows[sid]['metadata']['nominal_width_mm']+.02002,quad_segs=128);exposed=added if port is None else added.difference(port);dg=None if exposed.is_empty else exposed.distance(g);reasons=[]
    if not contact.is_empty and candidate.intersection(g).is_empty:reasons.append('REQUIRED_ATTACHMENT_LOST')
    if contact.is_empty and candidate.intersects(g) and not old.intersects(current[other]):reasons.append('NEW_COPPER_CONTACT')
    if contact.is_empty and ((d0>=.02 and d+epsilon<.02) or (d0<.02 and d+epsilon<d0)):reasons.append('CLEARANCE_WORSENED')
    if dg is not None and dg+epsilon<gap:reasons.append('ADDED_ROUTE_COPPER_BELOW_GAP')
    if other in details['obstacle_ids'] and require_objective and d+epsilon<gap:reasons.append('OBJECTIVE_NOT_MET')
    if reasons:failures.append(dict(source_id=sid,neighbor_id=other,reasons=reasons))
    pairs.append(dict(source_id=sid,neighbor_id=other,gap_mm=d,added_gap_mm=dg,failures=reasons))
  return dict(passed=not failures,failures=failures,pairs=pairs),updated
 def _candidates(self,details,rows,current):
  gap=.0201;seed=details['seed_ids'];obstacles=details['obstacle_ids'];sid,oid=min(((s,o) for s in seed for o in obstacles),key=lambda pair:current[pair[0]].distance(current[pair[1]]));a,b=nearest_points(current[sid],current[oid]);dx,dy=a.x-b.x,a.y-b.y
  if math.hypot(dx,dy)<1e-15:dx,dy=current[sid].centroid.x-current[oid].centroid.x,current[sid].centroid.y-current[oid].centroid.y
  length=math.hypot(dx,dy)
  if length<1e-15:fail('DISPLACEMENT_DIRECTION_UNRESOLVED','coincident obstacle/route')
  vector=[dx/length,dy/length];distance=max(gap-current[s].distance(current[o]) for s in seed for o in obstacles)+1e-6;distance=max(distance,1e-6);start,end=details['initial_indices'];reference=details['bundle']['reference_points_mm'];bounds=details['bounds'];domains=[]
  for level in range(bounds['max_extension_steps']+1):
   i,j=max(2,start-level),min(len(reference)-3,end+level);ext=extension_distance(reference,[start,end],[i,j])
   if ext<=bounds['max_extension_um']/1000 and (i,j) not in domains:domains.append((i,j))
  for i,j in domains:
   for multiplier in route_parameters()['displacement_multipliers']:
    d=distance*multiplier
    if d<=bounds['max_displacement_um']/1000:yield dict(initial_indices=[start,end],expanded_indices=[i,j],extension_mm=extension_distance(reference,[start,end],[i,j]),vector=vector,distance_mm=d)
 def run(self,store,scene,policy,plan,checkpoint):
  details=plan['details'];rows,current,_=self._context(store,scene,policy,details);budget=Budget(details['bounds']);members={m['source_id']:m['offset_mm'] for m in details['bundle']['members']};attempts=[];chosen=None;chosen_paths={};chosen_moving=[]
  already=all(current[s].distance(current[o])>=.0201 for s in details['seed_ids'] for o in details['obstacle_ids'])
  if not already:
   for spec in self._candidates(details,rows,current):
    try:reference=displaced_reference(details['bundle']['reference_points_mm'],*spec['expanded_indices'],spec['vector'],spec['distance_mm'])
    except ValueError:continue
    moving=set(details['seed_ids'])
    for depth in range(details['bounds']['max_recursion_depth']+1):
     budget.evaluation()
     try:paths={sid:parallel_points(reference,members[sid]) for sid in moving}
     except ValueError as error:attempts.append(dict(spec=spec,moving=sorted(moving),passed=False,reason=str(error)));break
     q,_=self._check(store,scene,details,paths,moving);record=dict(spec=spec,moving=sorted(moving),depth=depth,check=q);attempts.append(record);checkpoint(dict(next_candidate=len(attempts),evaluations=budget.evaluations,attempts=attempts))
     if q['passed']:chosen=dict(spec,reference_points_mm=reference,moving=sorted(moving),recursion_depth=depth);chosen_paths=paths;chosen_moving=sorted(moving);break
     blockers=sorted({f['neighbor_id'] for f in q['failures'] if f.get('neighbor_id') in members and f['neighbor_id'] not in moving})
     if not blockers or depth==details['bounds']['max_recursion_depth'] or len(moving|set(blockers))>details['bounds']['max_members']:break
     moving.update(blockers)
    if chosen is not None:break
  replacements={};metadata={}
  for sid in chosen_moving:
   width=rows[sid]['metadata']['nominal_width_mm'];blob=to_wkb(route_copper(chosen_paths[sid],width,quad_segs=rows[sid]['metadata'].get('route_quad_segs',128)));budget.output(blob);replacements[sid]=store.put('geometry',blob);metadata[sid]=dict(rows[sid]['metadata'],route_points_mm=chosen_paths[sid],route_family=route_parameters()['family'])
  metadata=route_authorities(store,scene,plan,chosen_paths,rows) if chosen_paths else {}
  out_ref,out=output_scene(store,scene,plan,replacements=replacements,metadata=metadata)
  return dict(status='NO_CHANGE_REQUIRED' if already else 'CONSTRUCTED' if chosen else 'NO_IMPROVEMENT_FOUND',objective_satisfied=already or chosen is not None,chosen=chosen,attempts=attempts,replacement_refs=replacements,protected_source_refs={s:r['geometry_ref'] for s,r in rows.items() if s not in chosen_moving},before_ref=store.put('geometry',to_wkb(composed(store,scene))),after_ref=store.put('geometry',to_wkb(composed(store,out))),output_scene_ref=out_ref)
 def verify(self,store,scene,policy,plan,candidate,proof_scope,checkpoint):
  if proof_scope!={'scope':'complete-source-parallel-route-and-attachments'}:fail('PROOF_SCOPE_UNSUPPORTED','full route proof required')
  details=plan['details'];rows,current,_=self._context(store,scene,policy,details);chosen=candidate['chosen'];replacements={};metadata={};q=dict(passed=True,failures=[],pairs=[]);proof=[]
  if chosen is not None:
   valid_specs=list(self._candidates(details,rows,current));spec={k:chosen[k] for k in ['initial_indices','expanded_indices','extension_mm','vector','distance_mm']}
   if spec not in valid_specs or not set(details['seed_ids'])<=set(chosen['moving']) or not set(chosen['moving'])<={m['source_id'] for m in details['bundle']['members']} or len(chosen['moving'])>details['bounds']['max_members'] or chosen['recursion_depth']>details['bounds']['max_recursion_depth']:fail('ADAPTIVE_SCOPE_EXCEEDED','selected proposal')
   reference=displaced_reference(details['bundle']['reference_points_mm'],*chosen['expanded_indices'],chosen['vector'],chosen['distance_mm'])
   if reference!=chosen['reference_points_mm']:fail('PARALLEL_REFERENCE_MISMATCH','shared reference')
   offsets={m['source_id']:m['offset_mm'] for m in details['bundle']['members']};paths={s:parallel_points(reference,offsets[s]) for s in chosen['moving']};q,_=self._check(store,scene,details,paths,set(chosen['moving']))
   for sid in chosen['moving']:
    g=route_copper(paths[sid],rows[sid]['metadata']['nominal_width_mm'],quad_segs=rows[sid]['metadata'].get('route_quad_segs',128));replacements[sid]=store.put('geometry',to_wkb(g));metadata[sid]=dict(rows[sid]['metadata'],route_points_mm=paths[sid],route_family=route_parameters()['family'])
   for sid,p in paths.items():proof.append(dict(source_id=sid,offset_mm=offsets[sid],reference='ONE_SHARED_DISPLACED_REFERENCE',proof='Analytic constant normal offsets on every segment with common bounded miter joins; full finite copper checked, not sampled alignment'))
  else:
   met=all(current[s].distance(current[o])>=.0201 for s in details['seed_ids'] for o in details['obstacle_ids'])
   if not met:q=dict(passed=False,failures=[dict(reason='NO_IMPROVEMENT_OBJECTIVE_UNRESOLVED')],pairs=[])
  if replacements!=candidate['replacement_refs'] or candidate['protected_source_refs']!={s:r['geometry_ref'] for s,r in rows.items() if s not in replacements}:fail('ROUTE_RECONSTRUCTION_MISMATCH','selected replacement/fixed partitions')
  if candidate['objective_satisfied']!=q['passed']:fail('OBJECTIVE_CLAIM_MISMATCH','candidate status')
  metadata=route_authorities(store,scene,plan,paths,rows) if chosen is not None else {}
  check_output(store,scene,plan,candidate,replacements=replacements,metadata=metadata);checkpoint(dict(verified_routes=len(replacements),parallel_proof=proof))
  return dict(passed=q['passed'],failures=q['failures'],clearance=q,parallel_proof=proof,reconstructed_routes=len(replacements),scope='Versioned exact polyline normal-offset/miter family; fixed endpoints/widths, bounded connected control-chain extension and authorized recursive member expansion. Curved native families/electrical/manufacturing are not inferred.')
