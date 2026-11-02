"""T01-only extension schemas; existing five-suite schemas remain unchanged."""
import copy
from functools import lru_cache
from jsonschema import Draft202012Validator
from src.stage_abi import ABI_VERSION
from src.stage_abi.schema import request_schema as base_request
from src.stage_abi.responses import response_schema as base_response
from src.stage_abi.contracts import fail, finite_json
from . import STRATEGY

def closed(properties):
    return dict(type='object',additionalProperties=False,required=sorted(properties),properties=properties)

def request_schema():
    schema=base_request();schema['$id']='t01-interaction-abi/1.1/request'
    branches=[b for b in schema['oneOf'] if b['properties']['operation']['const'].startswith('t01_')]
    for b in branches:
        if b['properties']['operation']['const']=='t01_plan':
            b['properties']['payload']['properties']['strategy']={'const':STRATEGY}
        if b['properties']['operation']['const']=='t01_inspect':
            previous=copy.deepcopy(b['properties']['payload'])
            pp=previous['properties']
            b['properties']['payload']={'oneOf':[previous,closed(dict(selection_ref={'$ref':'#/$defs/ref'},page_size=pp['page_size'],cursor=pp['cursor']))]}
    template=copy.deepcopy(branches[0])
    for verb,payload in [('compile',dict(english={'type':'string','minLength':1,'maxLength':20000},binding_ref={'$ref':'#/$defs/ref'})),
                         ('discover',dict(bounds_ref={'$ref':'#/$defs/ref'}))]:
        b=copy.deepcopy(template);p=b['properties'];p['operation']={'const':'t01_'+verb};p['payload']=closed(payload)
        if verb=='compile':
            for k in ('profile_id','scene_ref','policy_ref'):p[k]={'type':'null'}
            p['payload']={'oneOf':[p['payload'],closed(dict(english_ref={'$ref':'#/$defs/ref'},binding_ref={'$ref':'#/$defs/ref'}))]}
        else:
            p['profile_id']={'type':'string','pattern':'^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$'}
            for k in ('scene_ref','policy_ref'):p[k]={'$ref':'#/$defs/ref'}
        branches.append(b)
    schema['oneOf']=branches
    return schema

def response_schema():
    schema=base_response();schema['$id']='t01-interaction-abi/1.1/response'
    branches=[b for b in schema['oneOf'] if b['properties']['status'].get('const')=='REJECTED' or b['properties']['operation'].get('const','').startswith('t01_')]
    for verb,properties in [('compile',dict(policy_ref={'$ref':'#/$defs/ref'},policy={'type':'object'},construction_status={'const':'NOT_RUN'})),
                            ('discover',dict(discovery_ref={'$ref':'#/$defs/ref'},selection_ref={'$ref':'#/$defs/ref'},discovery={'type':'object'},construction_status={'const':'NOT_RUN'}))]:
        branches.append(closed(dict(abi_version={'const':ABI_VERSION},request_id={'type':'string'},operation={'const':'t01_'+verb},status={'const':'OK'},result=closed(properties),error={'type':'null'})))
    schema['oneOf']=branches
    return schema

@lru_cache(maxsize=2)
def validator(kind):
    schema=request_schema() if kind=='request' else response_schema()
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)

def validate(value,kind):
    finite_json(value)
    if list(validator(kind).iter_errors(value)):
        fail('T01_WIRE_INVALID' if kind=='request' else 'T01_INTERNAL_RESPONSE_INVALID','Closed T01 interaction '+kind+' contract')
    return value
