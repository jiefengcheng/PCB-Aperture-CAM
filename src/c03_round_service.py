"""Closed C03 transport; existing crop and generic U02 schemas stay unchanged."""
from functools import lru_cache
from jsonschema import Draft202012Validator

from src.c03_input_family import specification
from src.c03_round_adapter import (PROFILE, STRATEGY, NativeRoundAdapter,
                                   compile_policy)
from src.stage_abi import ABI_VERSION
from src.stage_abi.contracts import fail, finite_json, validate_request, StageABIError
from src.stage_abi.registry import TrustedRegistry
from src.stage_abi.service import StageService
from src.t01_board.policy import validate_binding
from src.t01_crop.protocol import request_schema, response_schema
from src.t01_crop.service import CropService
from src.u03_board.selection import validate as validate_selection


@lru_cache(maxsize=2)
def validator(kind):
    schema = request_schema() if kind == 'request' else response_schema()
    if kind == 'request':
        branch = next(b for b in schema['oneOf'] if b['properties']['operation'].get('const') == 't01_plan')
        branch['properties']['payload']['properties']['strategy'] = {'const':STRATEGY}
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def wire(value, kind):
    finite_json(value)
    if list(validator(kind).iter_errors(value)):
        fail('C03_CLOSED_WIRE_INVALID',kind)
    return value


class C03RoundService(CropService):
    def __init__(self,store,host):
        fail('T01_C03_SUBSTITUTE_RETIRED','Use canonical complete-source T01; old C03 receipts stay read-only')
        if (set(host) != {'schema','compiler_binding_refs','stage_registry','crop_selection_ref'} or
                host['schema'] != 'c03-round-recovery-host/1'):
            fail('T01_HOST_INVALID','Explicit C03 host required')
        self.host = host
        spec,_,_ = specification()
        selection = validate_selection(store.get_json(host['crop_selection_ref'],kind='u03-crop-selection'))
        if selection['source_sha256'] != spec['source_sha256'] or selection['crop_sha256'] != spec['crop_sha256']:
            fail('C03_EXPLICIT_INPUT_PROFILE_REQUIRED','Source/crop hash')
        StageService.__init__(self,store,TrustedRegistry(store,host['stage_registry']),
                              {PROFILE:NativeRoundAdapter()})

    def dispatch(self,request):
        try:
            wire(request,'request')
            verb = request['operation'].split('_',1)[1]
            if verb == 'compile':
                p = request['payload']
                if p['binding_ref'] not in self.host['compiler_binding_refs']:
                    fail('T01_BINDING_NOT_REGISTERED','C03 source binding')
                b = validate_binding(self.store.get_json(p['binding_ref'],kind='t01-binding'))
                selection = validate_selection(self.store.get_json(self.host['crop_selection_ref'],
                    kind='u03-crop-selection'),b['source_sha256'])
                text = p['english'] if 'english' in p else self.store.get(p['english_ref'],kind='english-spec').decode()
                policy = compile_policy(text,p['binding_ref'],self.host['crop_selection_ref'])
                result = dict(policy_ref=self.store.put_json('policy',policy),policy=policy,
                              construction_status='NOT_RUN')
            elif verb == 'discover':
                p,scene,policy,adapter = self._context(request,'t01')
                if request['payload']['bounds_ref'] != p['bounds_ref']:
                    fail('BOUNDS_NOT_REGISTERED','C03 source discovery')
                discovery = adapter.discovery(self.store,scene,policy,
                    self.store.get_json(p['bounds_ref'],kind='bounds'))
                selection = dict(stage='t01',scene_ref=request['scene_ref'],source_ids=discovery['source_ids'])
                result = dict(discovery_ref=self.store.put_json('t01-discovery',discovery),
                    selection_ref=self.store.put_json('selection',selection),discovery=discovery,
                    construction_status='NOT_RUN')
            elif verb in ('inspect_all','compare_all'):
                _,scene,_,_ = self._context(request,'t01')
                result = self._inspect_all(request,scene) if verb=='inspect_all' else self._compare_all(request,scene)
            else:
                mapped = request
                if verb == 'plan':
                    mapped = dict(request,payload=dict(request['payload'],strategy='round_class_growth'))
                if verb == 'inspect' and 'selection_ref' in request['payload']:
                    p = request['payload']
                    selection = self.store.get_json(p['selection_ref'],kind='selection')
                    if selection['stage']!='t01' or selection['scene_ref']!=request['scene_ref']:
                        fail('T01_SELECTION_BINDING_MISMATCH','C03 inspection')
                    mapped = dict(request,payload=dict(source_ids=selection['source_ids'],finding_ids=[],
                        page_size=p['page_size'],cursor=p['cursor']))
                validate_request(mapped)
                result = self._dispatch(request if verb=='plan' else mapped,'t01',verb)
            response = dict(abi_version=ABI_VERSION,request_id=request['request_id'],
                operation=request['operation'],status='OK',result=result,error=None)
        except (StageABIError,ValueError,TypeError,KeyError,IndexError,OSError) as error:
            request = request if type(request) is dict else {}
            response = dict(abi_version=ABI_VERSION,request_id=request.get('request_id'),
                operation=request.get('operation'),status='REJECTED',result=None,
                error=dict(code=error.code if isinstance(error,StageABIError) else 'C03_INPUT_INVALID',
                           message=str(error)))
        return wire(response,'response')
