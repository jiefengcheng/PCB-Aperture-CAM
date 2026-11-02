"""Crop-only complete-pagination verbs; legacy and shared wire schemas stay frozen."""
import copy
from functools import lru_cache
from jsonschema import Draft202012Validator
from src.t01_abi.protocol import request_schema as old_request,response_schema as old_response,closed
from src.stage_abi.contracts import finite_json,fail

VERBS={'t01_inspect_all':'t01_inspect','t01_compare_all':'t01_compare'}


def request_schema():
    schema=old_request();schema['$id']='t01-crop-abi/2/request'
    for verb,old in VERBS.items():
        branch=copy.deepcopy(next(b for b in schema['oneOf'] if b['properties']['operation'].get('const')==old))
        branch['properties']['operation']={'const':verb}
        properties=dict(selection_ref={'$ref':'#/$defs/ref'}) if verb=='t01_inspect_all' else copy.deepcopy(branch['properties']['payload']['properties'])
        properties['page_size']=dict(type='integer',minimum=1,maximum=100)
        branch['properties']['payload']=closed(properties);schema['oneOf'].append(branch)
    return schema


def response_schema():
    schema=old_response();schema['$id']='t01-crop-abi/2/response'
    for verb,old in VERBS.items():
        branch=copy.deepcopy(next(b for b in schema['oneOf'] if b['properties']['operation'].get('const')==old))
        branch['properties']['operation']={'const':verb}
        props=branch['properties']['result']['properties']
        props.update(pagination_ref={'$ref':'#/$defs/ref'},page_count=dict(type='integer',minimum=1))
        branch['properties']['result']['required']=sorted(props)
        schema['oneOf'].append(branch)
    return schema


@lru_cache(maxsize=2)
def validator(kind):
    schema=request_schema() if kind=='request' else response_schema()
    Draft202012Validator.check_schema(schema);return Draft202012Validator(schema)


def validate(value,kind):
    finite_json(value)
    if list(validator(kind).iter_errors(value)):fail('T01_CROP_WIRE_INVALID','Closed crop '+kind+' contract')
    return value
