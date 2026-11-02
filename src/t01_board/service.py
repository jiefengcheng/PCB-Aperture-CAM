"""Board-specific compiler/registry; common T01 runtime stays unchanged."""
from src.stage_abi import ABI_VERSION
from src.stage_abi.service import StageService
from src.stage_abi.registry import TrustedRegistry
from src.stage_abi.contracts import fail,StageABIError
from src.t01_crop.service import CropService
from src.t01_crop.protocol import validate
from . import PROFILE
from .adapter import BoardAdapter
from .policy import compile_policy,validate_binding

class BoardService(CropService):
    def __init__(self,store,host):
        if set(host)!={'schema','compiler_binding_refs','stage_registry'} or host['schema']!='t01-board-host/1':fail('T01_HOST_INVALID','Whole-board host')
        self.host=host;StageService.__init__(self,store,TrustedRegistry(store,host['stage_registry']),{PROFILE:BoardAdapter()})
    def dispatch(self,request):
        if type(request)is not dict or request.get('operation')!='t01_compile':return super().dispatch(request)
        try:
            validate(request,'request');p=request['payload']
            if p['binding_ref']not in self.host['compiler_binding_refs']:fail('T01_BINDING_NOT_REGISTERED','Whole-board source binding')
            validate_binding(self.store.get_json(p['binding_ref'],kind='t01-binding'))
            text=p['english']if'english'in p else self.store.get(p['english_ref'],kind='english-spec').decode();policy=compile_policy(text,p['binding_ref'])
            result=dict(policy_ref=self.store.put_json('policy',policy),policy=policy,construction_status='NOT_RUN');status='OK';error=None
        except (StageABIError,ValueError,TypeError,KeyError,IndexError,OSError)as e:
            result=None;status='REJECTED';error=dict(code=e.code if isinstance(e,StageABIError)else'T01_INPUT_OR_ARTIFACT_INVALID',message=str(e))
        return validate(dict(abi_version=ABI_VERSION,request_id=request.get('request_id'),operation=request.get('operation'),status=status,result=result,error=error),'response')
