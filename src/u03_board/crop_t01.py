"""Image-window selection over the unchanged T01 kernel and full-board cache."""
from pathlib import Path
from src.stage_abi import ABI_VERSION
from src.stage_abi.store import canonical,digest
from src.stage_abi.contracts import fail,ref,StageABIError
from src.stage_abi.service import StageService
from src.stage_abi.registry import TrustedRegistry
from src.t01_crop.policy import RULES as BASE_RULES,compile_policy as base_compile,english as base_english
from src.t01_crop.protocol import validate as wire
from src.t01_crop.adapter import CropAdapter
from src.t01_crop.paging import store_pages,read_pages
from src.t01_board.source import context as board_context
from src.t01_board.policy import validate_binding
from src.t01_board.adapter import BoardAdapter,PORT_STORE
from src.t01_crop.service import CropService
from .selection import validate as validate_selection,select_sites

PROFILE='u03-image-crop-t01-v1'
HEADER='T01 U03 image-crop controlled English version 1.'
RULES=[*BASE_RULES[:-1],('R16','Use every original F.Cu source as context. Select only complete circle growth envelopes inside the hash-bound verified image window, inset by its recorded edge uncertainty. Preserve all other source features. Keep a selected reviewed-pair member unchanged if its partner is outside the selection. Actual crop image bytes locate the source window; geometry and clearance rules remain unchanged.','roi_scope','complete-growth-envelope-image-window-full-source-context')]


def english():return HEADER+'\n'+'\n'.join(k+': '+t for k,t,_,_ in RULES)+'\n'


def compile_policy(text,binding_ref,selection_ref):
    ref(selection_ref,'selection_ref')
    if type(text) is not str or text.replace('\r\n','\n').strip()!=english().strip():
        fail('T01_ENGLISH_UNSUPPORTED','Complete U03 image-crop normative wording required')
    policy=base_compile(base_english(),binding_ref)
    policy.update(dialect=HEADER,english=english(),english_sha256=digest(english().encode()),
                  u03_selection_ref=selection_ref,rules={f:v for _,_,f,v in RULES},
                  clause_trace=[dict(clause=k,english=t,contract_field=f,value=v) for k,t,f,v in RULES])
    return policy


def validate_policy(policy):
    if canonical(policy)!=canonical(compile_policy(policy['english'],policy['binding_ref'],policy['u03_selection_ref'])):
        fail('T01_CONTRACT_DERIVATION_MISMATCH','U03 image crop')


def context(store,scene,policy):
    validate_policy(policy)
    binding,raw,rows,shapes,sites=board_context(store,scene,policy)
    selection=validate_selection(store.get_json(policy['u03_selection_ref'],kind='u03-crop-selection'),digest(raw))
    selected=sites
    records=[dict(source_id=s['source_id'],disposition='CANONICAL_FULL_SOURCE_ANALYSIS',aliases=s['aliases'])for s in sites]
    return dict(binding,u03_selection=selection,u03_site_inventory=records),raw,rows,shapes,selected


class ImageCropAdapter(BoardAdapter):
    def describe(self):
        value=super().describe()
        value.update(implementation=digest(canonical(dict(base=value['implementation'],sources={p.name:digest(p.read_bytes()) for p in Path(__file__).parent.glob('*.py')}))),english_dialect=HEADER,
                     source_support='Hash-bound verified image window; complete features only; all original F.Cu remains context')
        return value

    def _context(self,store,scene,policy):return context(store,scene,policy)

    def _allocate(self,raw,rows,shapes,sites,policy,binding):
        return BoardAdapter._allocate(self,raw,rows,shapes,sites,policy,binding)


class ImageCropService(CropService):
    def __init__(self,store,host):
        fail('T01_CROP_WRITE_RETIRED','Use canonical complete-source T01; crops are read-only presentation')
        if set(host)!={'schema','compiler_binding_refs','stage_registry','crop_selection_ref'} or host['schema']!='u03-image-crop-t01-host/1':
            fail('T01_HOST_INVALID','U03 image crop host')
        self.host=host
        validate_selection(store.get_json(host['crop_selection_ref'],kind='u03-crop-selection'))
        StageService.__init__(self,store,TrustedRegistry(store,host['stage_registry']),{PROFILE:ImageCropAdapter()})

    def dispatch(self,request):
        if type(request) is not dict or request.get('operation')!='t01_compile':return super().dispatch(request)
        try:
            wire(request,'request');p=request['payload']
            if p['binding_ref'] not in self.host['compiler_binding_refs']:fail('T01_BINDING_NOT_REGISTERED','U03 native source binding')
            b=validate_binding(self.store.get_json(p['binding_ref'],kind='t01-binding'))
            validate_selection(self.store.get_json(self.host['crop_selection_ref'],kind='u03-crop-selection'),b['source_sha256'])
            text=p['english'] if 'english' in p else self.store.get(p['english_ref'],kind='english-spec').decode()
            policy=compile_policy(text,p['binding_ref'],self.host['crop_selection_ref'])
            result=dict(policy_ref=self.store.put_json('policy',policy),policy=policy,construction_status='NOT_RUN');status='OK';error=None
        except (StageABIError,ValueError,TypeError,KeyError,IndexError,OSError) as e:
            result=None;status='REJECTED';error=dict(code=e.code if isinstance(e,StageABIError) else 'T01_INPUT_OR_ARTIFACT_INVALID',message=str(e))
        return wire(dict(abi_version=ABI_VERSION,request_id=request.get('request_id'),operation=request.get('operation'),status=status,result=result,error=error),'response')
