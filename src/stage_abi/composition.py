"""Host-coordinated modular execution using only suite plan/run/verify calls.

No arbitrary callback/import/evaluator is accepted by the wire protocol. A
registered composition grant authorizes model-working scene handoff, not owner
acceptance or mutation/promotion of any frozen artifact.
"""
from . import ABI_VERSION
from .contracts import closed,fail
from .scene import validate_scene

STRATEGIES=dict(t01='round_class_growth',t02='whole_rectangle_growth',t03='obstacle_directed_single_or_bundle',t04='collective_uniform_width',t05='bounded_additive_spindle')

def execute_sequence(service,*,initial_scene_ref,qualification_ref,steps,grant_ref,idempotency_prefix):
 store=service.store;registry=service.registry;doc=registry.document
 if grant_ref not in doc.get('composition_refs',[]):fail('COMPOSITION_GRANT_NOT_REGISTERED','grant_ref')
 grant=store.get_json(grant_ref,kind='composition-grant');closed(grant,{'authority','initial_scene_ref','source_sha256','steps','output_scope_ref','max_steps'},'composition grant');scene=validate_scene(store,initial_scene_ref)
 if not grant['authority'] or initial_scene_ref!=grant['initial_scene_ref'] or scene['source_sha256']!=grant['source_sha256'] or type(grant['max_steps']) is not int or grant['max_steps']<len(steps) or grant['steps']!=steps or not steps:fail('COMPOSITION_SCOPE_MISMATCH','exact source/step grant')
 transcript=[];receipts=[];current=initial_scene_ref;qualification=qualification_ref
 for ordinal,step in enumerate(steps):
  closed(step,{'stage','profile_id','selection_template_ref','proof_scope_ref'},'composition step');stage=step['stage']
  if stage not in STRATEGIES:fail('STAGE_UNSUPPORTED',stage)
  profile=registry.profile(step['profile_id'],stage)
  # A working scene is admitted only from an actual passing prior verification.
  # The first scene must already be registered by the trusted host.
  if current not in profile['scene_refs']:
   q=store.get_json(qualification,kind='verification')
   if q.get('geometric_status')!='PASS' or q.get('output_scene_ref')!=current:fail('PREDECESSOR_NOT_QUALIFIED','composition handoff')
   profile['scene_refs'].append(current)
  def request(verb,payload,**extra):
   return dict(abi_version=ABI_VERSION,request_id=f'{idempotency_prefix}:{ordinal}:{verb}',operation=stage+'_'+verb,profile_id=step['profile_id'],scene_ref=current,policy_ref=profile['policy_ref'],plan_ref=extra.get('plan_ref'),authorization_ref=extra.get('authorization_ref'),idempotency_key=extra.get('idempotency_key'),payload=payload)
  def call(r):
   response=service.dispatch(r);transcript.append(dict(request=r,response=response))
   if response['status']!='OK':fail('COMPOSITION_OPERATION_FAILED',str(response['error']))
   return response['result']
  selection=store.get_json(step['selection_template_ref'],kind='selection-template')
  if 'scene_ref' in selection or 'stage' in selection:fail('SELECTION_TEMPLATE_INVALID','host coordinator binds scene/stage')
  ids=selection.get('source_ids')
  inspected=call(request('inspect',dict(source_ids=ids,finding_ids=[],page_size=100,cursor=None)))
  selected=store.put_json('selection',dict(selection,stage=stage,scene_ref=current));planned=call(request('plan',dict(inspection_ref=inspected['inspection_ref'],selection_ref=selected,predecessor_qualification_ref=qualification,bounds_ref=profile['bounds_ref'],strategy=STRATEGIES[stage])));plan=planned['plan_ref'];verb='search' if stage=='t03' else 'run'
  authority=store.put_json('authorization',dict(profile_id=step['profile_id'],scene_ref=current,policy_ref=profile['policy_ref'],plan_ref=plan,operations=[stage+'_'+verb,stage+'_verify'],authority=grant['authority'],output_scope_ref=grant['output_scope_ref']))
  if authority not in doc['authorization_refs']:doc['authorization_refs'].append(authority)
  result=call(request(verb,dict(output_scope_ref=grant['output_scope_ref']),plan_ref=plan,authorization_ref=authority,idempotency_key=f'{idempotency_prefix}:{ordinal}:construct'))
  if result['job']['status']!='COMPLETED' or result['result'] is None:fail('COMPOSITION_STAGE_NOT_COMPLETE',stage)
  candidate=result['result']['candidate_ref'];verified=call(request('verify',dict(candidate_ref=candidate,verifier_ref=profile['verifier_ref'],proof_scope_ref=step['proof_scope_ref']),plan_ref=plan,authorization_ref=authority,idempotency_key=f'{idempotency_prefix}:{ordinal}:verify'))
  if verified['job']['status']!='COMPLETED' or verified['result'] is None or verified['result']['verification']['geometric_status']!='PASS':
   return dict(status='FAIL_STAGE_VERIFICATION',failed_stage=stage,completed_steps=receipts,transcript=transcript,last_qualified_scene_ref=current,owner_acceptance='NOT_GRANTED')
  qualification=verified['result']['verification_ref'];current=verified['result']['verification']['output_scene_ref'];receipts.append(dict(stage=stage,candidate_ref=candidate,verification_ref=qualification,scene_ref=current))
 return dict(status='PASS_LOCAL_MODULAR_COMPOSITION',initial_scene_ref=initial_scene_ref,output_scene_ref=current,verification_ref=qualification,steps=receipts,transcript=transcript,owner_acceptance='NOT_GRANTED',independent_native_electrical_manufacturing='NOT_ESTABLISHED')
