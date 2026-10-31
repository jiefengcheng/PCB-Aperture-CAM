"""Trusted host catalogue; request data cannot add profiles or mint authority."""
from .contracts import closed,identifier,ref,fail,STAGES

class TrustedRegistry:
 def __init__(self, store, document):
  closed(document,{'schema','profiles','authorization_refs','decision_refs'}|({'composition_refs'} if 'composition_refs' in document else set()),'trusted registry')
  if document['schema']!='stage-agent-registry/1':fail('REGISTRY_UNSUPPORTED','schema')
  if type(document['profiles']) is not dict:fail('REGISTRY_INVALID','profiles')
  self.store=store;self.document=document
  for pid,p in document['profiles'].items():
   identifier(pid,'profile_id');closed(p,{'stage','adapter','policy_ref','scene_refs','bounds_ref','verifier_ref'},'profile')
   if p['stage'] not in STAGES:fail('REGISTRY_INVALID','stage')
   identifier(p['adapter'],'adapter')
   for name in ['policy_ref','bounds_ref','verifier_ref']:ref(p[name],name)
   if type(p['scene_refs']) is not list or not p['scene_refs']:fail('REGISTRY_INVALID','scene_refs')
   for r in p['scene_refs']:ref(r,'scene_ref')
  for key in ['authorization_refs','decision_refs']+(['composition_refs'] if 'composition_refs' in document else []):
   if type(document[key]) is not list:fail('REGISTRY_INVALID',key)
   for r in document[key]:ref(r,key)
 def profile(self, pid, stage):
  p=self.document['profiles'].get(pid)
  if p is None or p['stage']!=stage:fail('PROFILE_UNSUPPORTED',str(pid))
  return p
 def authorize(self, reference, *, profile_id, scene_ref, policy_ref, plan_ref, operation):
  if reference not in self.document['authorization_refs']:fail('AUTHORIZATION_NOT_REGISTERED','authorization_ref')
  a=self.store.get_json(reference,kind='authorization')
  closed(a,{'profile_id','scene_ref','policy_ref','plan_ref','operations','authority','output_scope_ref'},'authorization')
  if not a['authority'] or a['profile_id']!=profile_id or a['scene_ref']!=scene_ref or a['policy_ref']!=policy_ref or (a['plan_ref'] is not None and a['plan_ref']!=plan_ref) or operation not in a['operations']:fail('AUTHORIZATION_SCOPE_MISMATCH',operation)
  ref(a['output_scope_ref'],'output_scope_ref');return a
