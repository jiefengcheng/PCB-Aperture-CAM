"""Strict closed request contracts shared by T01/T02/T03/T04/T05."""
import math
import re
from . import ABI_VERSION

STAGES = ('t01', 't02', 't03', 't04', 't05')
FIELDS = {'abi_version','request_id','operation','profile_id','scene_ref','policy_ref',
          'plan_ref','authorization_ref','idempotency_key','payload'}
PAYLOADS = {
 'describe': {'requested_contract_version'},
 'inspect': {'source_ids','finding_ids','page_size','cursor'},
 'plan': {'inspection_ref','selection_ref','predecessor_qualification_ref','bounds_ref','strategy'},
 'run': {'output_scope_ref'}, 'search': {'output_scope_ref'},
 'verify': {'candidate_ref','verifier_ref','proof_scope_ref'},
 'compare': {'left_ref','right_ref','viewport_ref','evidence_selection_ref'},
 'review': {'candidate_ref','verification_ref','decision_filters'},
}

class StageABIError(ValueError):
 def __init__(self, code, message):
  self.code=code;super().__init__(message)

def fail(code, message):raise StageABIError(code,message)
def closed(value, keys, label):
 if type(value) is not dict or set(value)!=set(keys):fail('CLOSED_OBJECT_REQUIRED',label)

def finite_json(value):
 if value is None or type(value) in (str,bool,int):return
 if type(value) is float:
  if not math.isfinite(value):fail('NONFINITE_NUMBER','JSON numbers must be finite')
 elif type(value) is list:
  for v in value:finite_json(v)
 elif type(value) is dict:
  if any(type(k) is not str for k in value):fail('STRING_KEYS_REQUIRED','JSON keys')
  for v in value.values():finite_json(v)
 else:fail('PLAIN_JSON_REQUIRED','No executable or Python values')

def identifier(value,label):
 if type(value) is not str or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}',value):fail('INVALID_IDENTIFIER',label)

def ref(value,label):
 closed(value,{'artifact_id','sha256'},label);identifier(value['artifact_id'],label)
 if type(value['sha256']) is not str or not re.fullmatch('[0-9a-f]{64}',value['sha256']):fail('INVALID_ARTIFACT_REF',label)

def validate_request(request):
 finite_json(request);closed(request,FIELDS,'request')
 if request['abi_version']!=ABI_VERSION:fail('ABI_VERSION_UNSUPPORTED','abi_version')
 identifier(request['request_id'],'request_id');operation=request['operation']
 if type(operation) is not str or '_' not in operation:fail('OPERATION_UNSUPPORTED','operation')
 stage,verb=operation.split('_',1)
 allowed={'describe','inspect','plan','verify','compare','review','search' if stage=='t03' else 'run'}
 if stage not in STAGES or verb not in allowed:fail('OPERATION_UNSUPPORTED',operation)
 if request['profile_id'] is not None:identifier(request['profile_id'],'profile_id')
 if verb!='describe' and request['profile_id'] is None:fail('PROFILE_REQUIRED','profile_id')
 payload=request['payload'];closed(payload,PAYLOADS[verb],'payload')
 required=set() if verb=='describe' else {'scene_ref','policy_ref'}
 if verb in ('run','search','verify'):required.add('plan_ref')
 if verb in ('run','search','verify'):required.add('authorization_ref')
 for field in ('scene_ref','policy_ref','plan_ref','authorization_ref'):
  if field in required:ref(request[field],field)
  elif request[field] is not None:fail('IRRELEVANT_SELECTOR',field)
 if verb in ('run','search','verify'):identifier(request['idempotency_key'],'idempotency_key')
 elif request['idempotency_key'] is not None:fail('IRRELEVANT_SELECTOR','idempotency_key')
 for key,value in payload.items():
  if key.endswith('_ref'):
   if key=='verification_ref' and value is None:continue
   ref(value,key)
 if verb=='describe':
  if payload['requested_contract_version'] not in (None,ABI_VERSION):fail('ABI_VERSION_UNSUPPORTED','requested_contract_version')
 if verb=='inspect':
  for key in ('source_ids','finding_ids'):
   values=payload[key]
   if type(values) is not list or len(values)>1000 or any(type(v) is not str or not v or len(v)>512 for v in values) or len(values)!=len(set(values)):fail('EXPLICIT_BOUNDED_SELECTION_REQUIRED',key)
  if not payload['source_ids'] and not payload['finding_ids']:fail('EXPLICIT_BOUNDED_SELECTION_REQUIRED','empty selection is not everything')
  if type(payload['page_size']) is not int or not 1<=payload['page_size']<=100:fail('PAGE_LIMIT_INVALID','page_size')
  if payload['cursor'] is not None:ref(payload['cursor'],'cursor')
 if verb=='plan':
  strategies={'t01':'round_class_growth','t02':'whole_rectangle_growth','t03':'obstacle_directed_single_or_bundle','t04':'collective_uniform_width','t05':'bounded_additive_spindle'}
  if payload['strategy']!=strategies[stage]:fail('STRATEGY_UNSUPPORTED',stage)
 if verb=='review':
  filters=payload['decision_filters'];closed(filters,{'types','page_size','cursor'},'decision_filters')
  if type(filters['types']) is not list or not filters['types'] or any(x not in ('owner','independent','local') for x in filters['types']) or len(set(filters['types']))!=len(filters['types']):fail('DECISION_FILTER_INVALID','types')
  if type(filters['page_size']) is not int or not 1<=filters['page_size']<=100:fail('PAGE_LIMIT_INVALID','page_size')
  if filters['cursor'] is not None:ref(filters['cursor'],'cursor')
 return stage,verb
