"""Local suite dispatcher with trusted adapters, not request-supplied callables."""
import hashlib
import sys
import shapely
from pathlib import Path
from shapely import to_wkb
from shapely.geometry import box
from . import ABI_VERSION
from .contracts import validate_request,StageABIError,fail,closed,ref
from .store import canonical
from .journal import execution_journal
from .scene import validate_scene,composed,compatible
from .visuals import comparison_svg
from .responses import validate_response

def runtime_fingerprint():
 root=Path(__file__).resolve().parents[1];files=sorted([*root.glob('*.py'),*Path(__file__).parent.glob('*.py')])
 body=b''.join(str(p.relative_to(root)).encode()+p.read_bytes() for p in files)+sys.version.encode()+shapely.__version__.encode()+shapely.geos_version_string.encode()
 return hashlib.sha256(body).hexdigest()

class StageService:
 def __init__(self,store,registry,adapters):
  self.store=store;self.registry=registry;self.adapters=dict(adapters);self.runtime=runtime_fingerprint()
 def dispatch(self,request):
  response=self._dispatch_response(request)
  try:return validate_response(response)
  except StageABIError:
   return dict(abi_version=ABI_VERSION,request_id=response.get('request_id') if type(response.get('request_id')) is str else None,operation=response.get('operation') if type(response.get('operation')) is str else None,status='REJECTED',result=None,error=dict(code='INTERNAL_RESPONSE_INVALID',message='Closed operation response contract failed'))
 def _dispatch_response(self,request):
  try:
   stage,verb=validate_request(request);result=self._dispatch(request,stage,verb)
   return dict(abi_version=ABI_VERSION,request_id=request['request_id'],operation=request['operation'],status='OK',result=result,error=None)
  except StageABIError as error:
   return dict(abi_version=ABI_VERSION,request_id=request.get('request_id') if type(request) is dict and type(request.get('request_id')) is str else None,operation=request.get('operation') if type(request) is dict and type(request.get('operation')) is str else None,status='REJECTED',result=None,error=dict(code=error.code,message=str(error)))
  except (KeyError,TypeError,ValueError,IndexError) as error:
   return dict(abi_version=ABI_VERSION,request_id=request.get('request_id') if type(request) is dict and type(request.get('request_id')) is str else None,operation=request.get('operation') if type(request) is dict and type(request.get('operation')) is str else None,status='REJECTED',result=None,error=dict(code='ARTIFACT_STRUCTURE_INVALID',message=str(error)))
 def _context(self,r,stage):
  p=self.registry.profile(r['profile_id'],stage)
  if r['policy_ref']!=p['policy_ref']:fail('POLICY_BINDING_MISMATCH','policy_ref')
  if r['scene_ref'] not in p['scene_refs']:fail('SCENE_NOT_REGISTERED','scene_ref')
  scene=validate_scene(self.store,r['scene_ref']);policy=self.store.get_json(r['policy_ref'],kind='policy')
  if policy.get('stage')!=stage:fail('POLICY_BINDING_MISMATCH','stage')
  adapter=self.adapters.get(p['adapter'])
  return p,scene,policy,adapter
 def _dispatch(self,r,stage,verb):
  if verb=='describe':return self._describe(r,stage)
  p,scene,policy,adapter=self._context(r,stage);payload=r['payload']
  if verb=='inspect':return self._inspect(r,scene)
  if verb=='plan':return self._plan(r,stage,p,scene,policy,adapter)
  if verb=='compare':return self._compare(r,scene)
  if verb=='review':return self._review(r)
  if adapter is None:fail('ADAPTER_NOT_IMPLEMENTED',p['adapter'])
  return self._execute(r,stage,verb,p,scene,policy,adapter)
 def _describe(self,r,stage):
  profiles={k:p for k,p in self.registry.document['profiles'].items() if p['stage']==stage and (r['profile_id'] is None or k==r['profile_id'])}
  if r['profile_id'] is not None and not profiles:fail('PROFILE_UNSUPPORTED',r['profile_id'])
  result={}
  for pid,p in profiles.items():
   adapter=self.adapters.get(p['adapter']);result[pid]=dict(adapter=p['adapter'],support=None if adapter is None else adapter.describe(),policy_ref=p['policy_ref'],scene_refs=p['scene_refs'],bounds_ref=p['bounds_ref'],verifier_ref=p['verifier_ref'])
  return dict(stage=stage,profiles=result,execution='AVAILABLE_ONLY_WHEN_ACTUAL_ADAPTER_IS_REGISTERED',owner_acceptance='NOT_GRANTED_BY_ABI')
 def _inspect(self,r,scene):
  p=r['payload'];sids=set(p['source_ids']);fids=set(p['finding_ids']);records=[dict(record_type='source',record=x) for x in scene['objects'] if x['source_id'] in sids]+[dict(record_type='finding',record=x) for x in scene['findings'] if x['finding_id'] in fids]
  if sids-{x['source_id'] for x in scene['objects']} or fids-{x['finding_id'] for x in scene['findings']}:fail('SELECTION_NOT_FOUND','explicit selection')
  records.sort(key=lambda x:(x['record_type'],canonical(x['record'])));binding=dict(scene_ref=r['scene_ref'],policy_ref=r['policy_ref'],source_ids=p['source_ids'],finding_ids=p['finding_ids'],page_size=p['page_size'],profile_id=r['profile_id']);offset=self._offset(p['cursor'],binding,len(records));page=records[offset:offset+p['page_size']]
  cursor=self._cursor(binding,offset+len(page),len(records));report=dict(scene_ref=r['scene_ref'],policy_ref=r['policy_ref'],profile_id=r['profile_id'],records=page,selected_source_ids=p['source_ids'],selected_finding_ids=p['finding_ids'],next_cursor=cursor,total_records=len(records),acceptance=scene['acceptance'])
  return dict(inspection_ref=self.store.put_json('inspection',report),**report)
 def _offset(self,cursor,binding,total):
  if cursor is None:return 0
  c=self.store.get_json(cursor,kind='cursor');closed(c,{'binding','offset'},'cursor')
  if c['binding']!=binding or type(c['offset']) is not int or not 0<=c['offset']<total:fail('STALE_CURSOR','cursor binding/offset')
  return c['offset']
 def _cursor(self,binding,offset,total):return None if offset>=total else self.store.put_json('cursor',dict(binding=binding,offset=offset))
 def _plan(self,r,stage,p,scene,policy,adapter):
  if adapter is None:fail('ADAPTER_NOT_IMPLEMENTED',p['adapter'])
  payload=r['payload'];inspection=self.store.get_json(payload['inspection_ref'],kind='inspection')
  if any(inspection[k]!=r[k] for k in ['scene_ref','policy_ref','profile_id']):fail('STALE_INSPECTION','inspection_ref')
  if payload['bounds_ref']!=p['bounds_ref']:fail('BOUNDS_NOT_REGISTERED','bounds_ref')
  bounds=self.store.get_json(payload['bounds_ref'],kind='bounds');selection=self.store.get_json(payload['selection_ref'],kind='selection');qualification=self.store.get_json(payload['predecessor_qualification_ref'],kind='verification')
  if r['scene_ref'] not in (qualification.get('scene_ref'),qualification.get('output_scene_ref')) or qualification.get('geometric_status')!='PASS':fail('PREDECESSOR_NOT_QUALIFIED','qualification receipt')
  if selection.get('scene_ref')!=r['scene_ref'] or selection.get('stage')!=stage:fail('SELECTION_BINDING_MISMATCH','selection_ref')
  inspected=set(inspection['selected_source_ids'])
  if not set(selection.get('source_ids',[]))<=inspected:fail('SELECTION_NOT_INSPECTED','inspect the whole selected source set')
  detail=adapter.plan(self.store,scene,policy,selection,bounds)
  plan=dict(stage=stage,profile_id=r['profile_id'],scene_ref=r['scene_ref'],policy_ref=r['policy_ref'],bounds_ref=payload['bounds_ref'],selection_ref=payload['selection_ref'],qualification_ref=payload['predecessor_qualification_ref'],strategy=payload['strategy'],implementation=adapter.describe()['implementation'],runtime=self.runtime,details=detail)
  return dict(plan_ref=self.store.put_json('plan',plan),plan=plan,construction_status='NOT_RUN')
 def _compare(self,r,scene):
  p=r['payload'];left=validate_scene(self.store,p['left_ref']);right=validate_scene(self.store,p['right_ref']);compatible(left,right);compatible(scene,left)
  view=self.store.get_json(p['viewport_ref'],kind='viewport');selection=self.store.get_json(p['evidence_selection_ref'],kind='evidence-selection')
  closed(view,{'frame','bounds_mm'},'viewport');closed(selection,{'source_ids'},'evidence selection')
  if view['frame']!=scene['frame'] or len(view['bounds_mm'])!=4:fail('VIEWPORT_INVALID','frame/bounds')
  crop=box(*view['bounds_mm'])
  if not box(*left['viewport_mm']).covers(crop) or not box(*right['viewport_mm']).covers(crop):fail('VIEWPORT_SCOPE_EXCEEDED','common viewport must be covered by both scenes')
  a=composed(self.store,left).intersection(crop);b=composed(self.store,right).intersection(crop)
  changes=[];lm={x['source_id']:x for x in left['objects']};rm={x['source_id']:x for x in right['objects']}
  ids=selection['source_ids']
  if type(ids) is not list or not ids or len(ids)>1000 or any(type(x) is not str for x in ids):fail('EXPLICIT_BOUNDED_SELECTION_REQUIRED','comparison')
  for sid in sorted(set(ids)):
   if sid not in lm and sid not in rm:fail('SELECTION_NOT_FOUND',sid)
   changes.append(dict(source_id=sid,left_ref=lm.get(sid,{}).get('geometry_ref'),right_ref=rm.get(sid,{}).get('geometry_ref')))
  result=dict(left_ref=p['left_ref'],right_ref=p['right_ref'],viewport_ref=p['viewport_ref'],source_changes=changes,added_area_mm2=b.difference(a).area,removed_area_mm2=a.difference(b).area,added_ref=self.store.put('delta',to_wkb(b.difference(a))),removed_ref=self.store.put('delta',to_wkb(a.difference(b))))
  result['visuals']={name:self.store.put('visual',comparison_svg(g,d,view['bounds_mm'],title='ABI comparison '+name)) for name,g,d in [('before',a,a.difference(b)),('after',b,b.difference(a))]}
  return dict(comparison_ref=self.store.put_json('comparison',result),**result)
 def _review(self,r):
  p=r['payload'];candidate=self.store.get_json(p['candidate_ref'],kind='candidate')
  if candidate['profile_id']!=r['profile_id'] or candidate['scene_ref']!=r['scene_ref'] or candidate['policy_ref']!=r['policy_ref']:fail('CANDIDATE_BINDING_MISMATCH','review')
  if p['verification_ref'] is not None:
   v=self.store.get_json(p['verification_ref'],kind='verification')
   if v.get('candidate_ref')!=p['candidate_ref']:fail('VERIFICATION_BINDING_MISMATCH','review')
  rows=[]
  for reference in self.registry.document['decision_refs']:
   d=self.store.get_json(reference,kind='decision')
   if d.get('candidate_ref')==p['candidate_ref'] and d.get('type') in p['decision_filters']['types']:rows.append(dict(decision_ref=reference,decision=d))
  rows.sort(key=lambda x:canonical(x));f=p['decision_filters'];binding=dict(profile_id=r['profile_id'],candidate_ref=p['candidate_ref'],verification_ref=p['verification_ref'],types=f['types'],page_size=f['page_size'],decision_refs=self.registry.document['decision_refs']);offset=self._offset(f['cursor'],binding,len(rows));page=rows[offset:offset+f['page_size']]
  return dict(records=page,next_cursor=self._cursor(binding,offset+len(page),len(rows)),owner_status='PENDING' if not any(x['decision']['type']=='owner' for x in rows) else 'RECORDED_SEE_EXACT_SCOPE',independent_status='NOT_RUN' if not any(x['decision']['type']=='independent' for x in rows) else 'RECORDED_SEE_EXACT_SCOPE')
 def _execute(self,r,stage,verb,p,scene,policy,adapter):
  plan=self.store.get_json(r['plan_ref'],kind='plan')
  if any(plan[k]!=r[k] for k in ['profile_id','scene_ref','policy_ref']) or plan['stage']!=stage or plan['implementation']!=adapter.describe()['implementation'] or plan.get('runtime')!=self.runtime or plan['bounds_ref']!=p['bounds_ref']:fail('STALE_PLAN','plan identity/implementation')
  a=self.registry.authorize(r['authorization_ref'],profile_id=r['profile_id'],scene_ref=r['scene_ref'],policy_ref=r['policy_ref'],plan_ref=r['plan_ref'],operation=r['operation'])
  if verb!='verify' and r['payload']['output_scope_ref']!=a['output_scope_ref']:fail('OUTPUT_SCOPE_MISMATCH','output_scope_ref')
  scope=self.store.get_json(a['output_scope_ref'],kind='output-scope')
  if scope!={'kind':'immutable-local-artifacts'}:fail('OUTPUT_SCOPE_UNSUPPORTED','only local store outputs')
  key=dict(profile_id=r['profile_id'],operation=r['operation'],idempotency_key=r['idempotency_key']);binding=dict(request={k:v for k,v in r.items() if k!='request_id'},implementation=plan['implementation']);won,job=self.store.begin(key,binding)
  if not won:return dict(job=job,reused=True,result=None if job['result_ref'] is None else self.store.get_json(job['result_ref'],kind='result'))
  def checkpoint(data):self.store.checkpoint(key,binding,self.store.put_json('checkpoint',data))
  try:
   with execution_journal(self.store,key,binding,job,bounds=plan['details']['bounds']) as journal:
    if verb=='verify':
     candidate=self.store.get_json(r['payload']['candidate_ref'],kind='candidate')
     if candidate.get('plan_ref')!=r['plan_ref'] or candidate.get('scene_ref')!=r['scene_ref'] or candidate.get('profile_id')!=r['profile_id'] or candidate.get('policy_ref')!=r['policy_ref']:fail('CANDIDATE_BINDING_MISMATCH','verify')
     if r['payload']['verifier_ref']!=p['verifier_ref']:fail('VERIFIER_NOT_REGISTERED','verifier_ref')
     proof_scope=self.store.get_json(r['payload']['proof_scope_ref'],kind='proof-scope')
     check=adapter.verify(self.store,scene,policy,plan,candidate,proof_scope,checkpoint)
     if type(check.get('passed')) is not bool:fail('EXPLICIT_GEOMETRY_VERDICT_REQUIRED','verifier')
     value=dict(stage=stage,profile_id=r['profile_id'],scene_ref=r['scene_ref'],candidate_ref=r['payload']['candidate_ref'],plan_ref=r['plan_ref'],output_scene_ref=candidate['output_scene_ref'],geometric_status='PASS' if check['passed'] else 'FAIL',check=check,owner_status='PENDING',independent_status='NOT_RUN',native_electrical_manufacturing='NOT_ESTABLISHED')
     result=dict(verification_ref=self.store.put_json('verification',value),verification=value)
    else:
     value=adapter.run(self.store,scene,policy,plan,checkpoint)
     value.update(stage=stage,profile_id=r['profile_id'],scene_ref=r['scene_ref'],policy_ref=r['policy_ref'],plan_ref=r['plan_ref'],owner_status='PENDING',independent_status='NOT_RUN',native_electrical_manufacturing='NOT_ESTABLISHED')
     result=dict(candidate_ref=self.store.put_json('candidate',value),candidate=value)
    journal.assert_consumed();result['execution_evidence']=journal.report()
    result_ref=self.store.put_json('result',result);job=self.store.finish(key,binding,result_ref);return dict(job=job,reused=False,result=result)
  except Exception as error:
   result_ref=self.store.put_json('result',dict(status='FAIL',error=dict(code=error.code if isinstance(error,StageABIError) else 'ADAPTER_EXECUTION_FAILED',message=str(error))))
   self.store.finish(key,binding,result_ref,failed=True)
   if isinstance(error,StageABIError):raise
   fail('ADAPTER_EXECUTION_FAILED',str(error))
