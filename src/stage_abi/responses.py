"""Closed operation-specific public response shapes and runtime validation."""
from functools import lru_cache
from jsonschema import Draft202012Validator
from . import ABI_VERSION
from .schema import request_schema
from .contracts import StageABIError,finite_json


def response_schema():
 refs=request_schema()['$defs'];ref={'$ref':'#/$defs/ref'};nullable={'anyOf':[ref,{'type':'null'}]};obj={'type':'object'};string={'type':'string'};integer={'type':'integer','minimum':0}
 def closed(properties):return dict(type='object',additionalProperties=False,required=sorted(properties),properties=properties)
 evidence=closed(dict(mode={'enum':['FRESH_EXECUTION','OWN_ATTEMPT_PREFIX_REPLAY']},replayed_events=integer,fresh_events=integer,total_events=integer,logical_output_bytes=integer,elapsed_seconds={'type':'number','minimum':0}))
 job=closed(dict(job_id={'type':'string','pattern':'^[0-9a-f]{64}$'},binding_sha256={'type':'string','pattern':'^[0-9a-f]{64}$'},status={'enum':['RUNNING','COMPLETED','FAILED']},request_binding_ref=ref,result_ref=nullable,checkpoint_ref=nullable,owner={'anyOf':[closed(dict(host=string,pid={'type':'integer','minimum':1},start=string)),{'type':'null'}]},created_epoch={'type':'number','minimum':0},created_monotonic={'type':'number','minimum':0},resume_count=integer))
 error=closed(dict(code={'type':'string','pattern':'^[A-Z][A-Z0-9_]*$'},message=string))
 executed={'oneOf':[closed(dict(candidate_ref=ref,candidate=obj,execution_evidence=evidence)),closed(dict(verification_ref=ref,verification=obj,execution_evidence=evidence)),closed(dict(status={'const':'FAIL'},error=error))]}
 shapes={
 'describe':closed(dict(stage={'enum':['t01','t02','t03','t04','t05']},profiles=obj,execution=string,owner_acceptance={'const':'NOT_GRANTED_BY_ABI'})),
 'inspect':closed(dict(inspection_ref=ref,scene_ref=ref,policy_ref=ref,profile_id=string,records={'type':'array'},selected_source_ids={'type':'array','items':string},selected_finding_ids={'type':'array','items':string},next_cursor=nullable,total_records=integer,acceptance=obj)),
 'plan':closed(dict(plan_ref=ref,plan=obj,construction_status={'const':'NOT_RUN'})),
 'compare':closed(dict(comparison_ref=ref,left_ref=ref,right_ref=ref,viewport_ref=ref,source_changes={'type':'array'},added_area_mm2={'type':'number','minimum':0},removed_area_mm2={'type':'number','minimum':0},added_ref=ref,removed_ref=ref,visuals=closed(dict(before=ref,after=ref)))),
 'review':closed(dict(records={'type':'array'},next_cursor=nullable,owner_status=string,independent_status=string)),
 }
 for v in ['run','search','verify']:shapes[v]=closed(dict(job=job,reused={'type':'boolean'},result={'anyOf':[executed,{'type':'null'}]}))
 branches=[]
 for stage in ['t01','t02','t03','t04','t05']:
  for verb in ['describe','inspect','plan','verify','compare','review','search' if stage=='t03' else 'run']:
   branches.append(closed(dict(abi_version={'const':ABI_VERSION},request_id=string,operation={'const':stage+'_'+verb},status={'const':'OK'},result=shapes[verb],error={'type':'null'})))
 branches.append(closed(dict(abi_version={'const':ABI_VERSION},request_id={'type':['string','null']},operation={'type':['string','null']},status={'const':'REJECTED'},result={'type':'null'},error=error)))
 return {'$schema':'https://json-schema.org/draft/2020-12/schema','$id':ABI_VERSION+'/response','$defs':refs,'oneOf':branches}

@lru_cache(maxsize=1)
def validator():
 schema=response_schema();Draft202012Validator.check_schema(schema);return Draft202012Validator(schema)

def validate_response(response):
 finite_json(response)
 errors=list(validator().iter_errors(response))
 if errors:raise StageABIError('INTERNAL_RESPONSE_INVALID','Operation response does not match the closed public contract')
 return response
