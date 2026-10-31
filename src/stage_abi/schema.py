"""Machine-readable closed schema for the implemented request boundary."""
from . import ABI_VERSION
from .contracts import STAGES,PAYLOADS


def request_schema():
 identifier={'type':'string','pattern':r'^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$'}
 nullable_id={'anyOf':[identifier,{'type':'null'}]}
 reference={'$ref':'#/$defs/ref'}
 nullable_ref={'anyOf':[reference,{'type':'null'}]}
 types=['owner','independent','local']
 filters={'type':'object','additionalProperties':False,'required':['types','page_size','cursor'],'properties':{
  'types':{'type':'array','minItems':1,'maxItems':3,'uniqueItems':True,'items':{'enum':types}},
  'page_size':{'type':'integer','minimum':1,'maximum':100},'cursor':nullable_ref}}
 strategies=dict(t01='round_class_growth',t02='whole_rectangle_growth',t03='obstacle_directed_single_or_bundle',t04='collective_uniform_width',t05='bounded_additive_spindle')
 branches=[]
 for stage in STAGES:
  for verb in ['describe','inspect','plan','verify','compare','review','search' if stage=='t03' else 'run']:
   active=verb in ('run','search','verify')
   properties=dict(abi_version={'const':ABI_VERSION},request_id=identifier,operation={'const':stage+'_'+verb},profile_id=nullable_id if verb=='describe' else identifier,
    scene_ref={'type':'null'} if verb=='describe' else reference,policy_ref={'type':'null'} if verb=='describe' else reference,
    plan_ref=reference if active else {'type':'null'},authorization_ref=reference if active else {'type':'null'},
    idempotency_key=identifier if active else {'type':'null'})
   pp={k:reference for k in PAYLOADS[verb] if k.endswith('_ref')}
   if verb=='describe':pp=dict(requested_contract_version={'enum':[None,ABI_VERSION]})
   if verb=='inspect':
    ids={'type':'array','maxItems':1000,'uniqueItems':True,'items':{'type':'string','minLength':1,'maxLength':512}}
    pp=dict(source_ids=ids,finding_ids=ids,page_size={'type':'integer','minimum':1,'maximum':100},cursor=nullable_ref)
   if verb=='plan':pp['strategy']={'const':strategies[stage]}
   if verb=='review':pp.update(verification_ref=nullable_ref,decision_filters=filters)
   payload={'type':'object','additionalProperties':False,'required':sorted(PAYLOADS[verb]),'properties':pp}
   if verb=='inspect':payload['anyOf']=[{'properties':{'source_ids':{'minItems':1}}},{'properties':{'finding_ids':{'minItems':1}}}]
   properties['payload']=payload
   branches.append({'type':'object','additionalProperties':False,'required':sorted(properties),'properties':properties})
 return {'$schema':'https://json-schema.org/draft/2020-12/schema','$id':ABI_VERSION+'/request',
  '$defs':{'ref':{'type':'object','additionalProperties':False,'required':['artifact_id','sha256'],'properties':{
   'artifact_id':identifier,'sha256':{'type':'string','pattern':'^[0-9a-f]{64}$'}}}},'oneOf':branches}
