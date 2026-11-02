"""T01-only facade over the unchanged stage runtime and trusted host catalogue."""
from src.stage_abi import ABI_VERSION
from src.stage_abi.service import StageService
from src.stage_abi.registry import TrustedRegistry
from src.stage_abi.contracts import closed, fail, StageABIError, validate_request
from .adapter import InteractionAdapter
from .contract import compile_english, validate_binding
from .protocol import validate

ADAPTER = 'c01-interaction-v1'

class InteractionService(StageService):
    def __init__(self,store,host):
        closed(host,{'schema','compiler_binding_refs','stage_registry'},'T01 trusted host')
        if host['schema']!='t01-interaction-host/1' or type(host['compiler_binding_refs']) is not list:
            fail('T01_HOST_INVALID','schema or registered binding refs')
        self.host=host
        super().__init__(store,TrustedRegistry(store,host['stage_registry']),{ADAPTER:InteractionAdapter()})

    def dispatch(self,request):
        try:
            validate(request,'request');verb=request['operation'].split('_',1)[1]
            if verb=='compile':
                p=request['payload']
                if p['binding_ref'] not in self.host['compiler_binding_refs']:
                    fail('T01_BINDING_NOT_REGISTERED','Only host-bound source cases may be compiled')
                validate_binding(self.store.get_json(p['binding_ref'],kind='t01-binding'))
                english=p['english'] if 'english' in p else self.store.get(p['english_ref'],kind='english-spec').decode('utf-8')
                policy=compile_english(english,p['binding_ref'])
                result=dict(policy_ref=self.store.put_json('policy',policy),policy=policy,construction_status='NOT_RUN')
            elif verb=='discover':
                p,scene,policy,adapter=self._context(request,'t01')
                if adapter is None:fail('ADAPTER_NOT_IMPLEMENTED',p['adapter'])
                if request['payload']['bounds_ref']!=p['bounds_ref']:fail('BOUNDS_NOT_REGISTERED','bounds_ref')
                bounds=self.store.get_json(p['bounds_ref'],kind='bounds')
                discovery=adapter.discovery(self.store,scene,policy,bounds)
                selection=dict(stage='t01',scene_ref=request['scene_ref'],source_ids=discovery['source_ids'])
                result=dict(discovery_ref=self.store.put_json('t01-discovery',discovery),selection_ref=self.store.put_json('selection',selection),discovery=discovery,construction_status='NOT_RUN')
            else:
                # Validate the common envelope with its legacy strategy token,
                # while retaining the new, explicitly validated T01 strategy in
                # the actual plan, execution binding and transcript.
                mapped=request
                if verb=='plan':mapped=dict(request,payload=dict(request['payload'],strategy='round_class_growth'))
                if verb=='inspect' and 'selection_ref' in request['payload']:
                    payload=request['payload'];selection=self.store.get_json(payload['selection_ref'],kind='selection')
                    closed(selection,{'stage','scene_ref','source_ids'},'T01 inspection selection')
                    if selection['stage']!='t01' or selection['scene_ref']!=request['scene_ref']:
                        fail('T01_SELECTION_BINDING_MISMATCH','Inspection selection belongs to another stage or scene')
                    mapped=dict(request,payload=dict(source_ids=selection['source_ids'],finding_ids=[],page_size=payload['page_size'],cursor=payload['cursor']))
                validate_request(mapped)
                result=self._dispatch(request if verb=='plan' else mapped,'t01',verb)
            response=dict(abi_version=ABI_VERSION,request_id=request['request_id'],operation=request['operation'],status='OK',result=result,error=None)
        except (StageABIError,ValueError,TypeError,KeyError,IndexError,OSError) as e:
            rid=request.get('request_id') if type(request) is dict else None
            operation=request.get('operation') if type(request) is dict else None
            response=dict(abi_version=ABI_VERSION,request_id=rid if type(rid) is str else None,operation=operation if type(operation) is str else None,status='REJECTED',result=None,error=dict(code=e.code if isinstance(e,StageABIError) else 'T01_INPUT_OR_ARTIFACT_INVALID',message=str(e)))
        return validate(response,'response')
