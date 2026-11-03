"""U03's own sequence and checkpoint authority; original T01 custody unchanged."""
from pathlib import Path
from src.stage_abi.store import digest,canonical
from src.pcb_data_abi.board_custody import checkpoint
from tools.t01_operator_host import ROOT,read

CONTRACT=ROOT/'contracts/operator/u03_board.json'
STEPS=tuple(read(CONTRACT)['operations'])
T03=tuple(op for op in STEPS if op.startswith('t03_'))
T04=tuple(op for op in STEPS if op.startswith('t04_'))
PREFIX=STEPS[:13]
THROUGH_T04=STEPS[:-5]
THROUGH_T03=STEPS[:STEPS.index(T04[0])]
CROP=('pcb_crop_locate','pcb_crop_verify')


def operation_steps(root=None,*,cropped=False):
    if root is not None:
        path=Path(root).parent/'job.json'
        cropped=path.exists() and read(path).get('crop') is not None
    return (*STEPS[:3],*CROP,*STEPS[3:]) if cropped else STEPS


def through(root,operation):
    steps=operation_steps(root)
    return steps[:steps.index(operation)+1]


def verify_prefix(root,expected):
    root=Path(root)
    receipts=sorted(((read(p),p.parent) for p in(root/'attempts').glob('*/receipt.json')),key=lambda r:r[0]['completed_at'])
    names=[r['tool'] for r,p in receipts]
    steps=operation_steps(root)
    if names!=list(steps[:len(names)]) or names[:len(expected)]!=list(expected):raise ValueError('U03_SEQUENCE_INCOMPLETE')
    # Validate only the accepted predecessor. The current native operation has
    # a receipt while its machine audit is pending and is not this prefix.
    # Keep the pinned T01 custody helper and its sequence byte-for-byte intact.
    receipts=receipts[:len(expected)];selected={r['attempt_id'] for r,p in receipts};audits={}
    for p in (root/'audits').glob('*/request.json'):
        req=read(p)['arguments']
        if req['attempt_id'] not in selected:continue
        decision=read(p.parent/'decision.json')
        if decision['status']!='PASS_SLICE_OBSERVATION_AUDIT' or req['attempt_id'] in audits:raise ValueError('U03_AUDIT_INVALID')
        audits[req['attempt_id']]=(req['audit'],decision['accepted_operation'])
    if len(audits)!=len(expected):raise ValueError('U03_AUDIT_INCOMPLETE')
    from tools.t01_native_route import verify_attempt
    responses={}
    for receipt,path in receipts:
        verify_attempt(path);result=read(path/'result.json');audit,operation=audits[receipt['attempt_id']]
        if (result['error'] is not None or receipt['status']=='FAIL' or operation!=receipt['tool'] or
            audit['verdict']!='PASS' or audit['response_sha256']!=digest((path/'abi/stdout.json').read_bytes()) or
            audit['observed']!=result['result']['facts'] or type(audit['note']) is not str or not 1<=len(audit['note'])<=300):raise ValueError('U03_AUDIT_MISMATCH')
        responses[operation]=read(path/'abi/stdout.json')
    return responses


def width_root(root):
    root=Path(root);value=read(root/'U03_T03_CHECKPOINT.json')
    expected=through(root,T03[-1])
    if value['operations']!=list(expected):raise ValueError('U03_AUDITED_T03_PREFIX_REQUIRED')
    from src.pcb_data_abi.roi import local
    for name,h in value['files'].items():
        path=local(root/name,True)
        if not path.is_relative_to(root) or digest(path.read_bytes())!=h:raise ValueError('U03_T03_CHECKPOINT_EVIDENCE_CHANGED:'+name)
    verify_prefix(root,expected)
    if read(root.parent/'job.json')['task_scope']!='u03-board':raise ValueError('U03_JOB_REQUIRED')
    return root


def export_root(host):
    if set(host)!={'schema','checkpoint','checkpoint_sha256','output'} or host['schema']!='pcb-u03-data-host/1':raise ValueError('U03_DATA_HOST_REQUIRED')
    path=Path(host['checkpoint']);root=path.parent
    if digest(path.read_bytes())!=host['checkpoint_sha256'] or path!=root/'U03_CHECKPOINT.json':raise ValueError('U03_CHECKPOINT_CHANGED')
    value=read(path)
    expected=through(root,T04[-1])
    if value['operations']!=list(expected):raise ValueError('U03_T03_CHECKPOINT_REQUIRED')
    required={'RECEIPT.json','T01_CHECKPOINT.json','u02_t03/t03_inspect.json','u02_t03/t03_search.json','u02_t03/t03_verify.json','u02_t03/t03_controls.json','U03_START.json','u03_t04/t04_run.json','u03_t04/t04_verify.json','u03_t04/t04_controls.json','U03_T03_CHECKPOINT.json'}
    if not required<=value['files'].keys():raise ValueError('U03_CHECKPOINT_EVIDENCE_MISSING')
    from src.pcb_data_abi.roi import local
    for name,h in value['files'].items():
        p=local(root/name,True)
        if not p.is_relative_to(root) or digest(p.read_bytes())!=h:raise ValueError('U03_CHECKPOINT_EVIDENCE_CHANGED:'+name)
    verify_prefix(root,expected)
    if read(root.parent/'job.json')['task_scope']!='u03-board' or Path(host['output'])!=root/'data_output':raise ValueError('U03_EXPORT_SCOPE_CHANGED')
    from src.u02_board.adapter import verify_candidate
    from .selection import retain_paths
    adapter=retain_paths(root)
    candidate=read(root/'u02_t03/t03_search.json')['candidate']
    verify_candidate(candidate,read(root/'u02_t03/t03_plan.json')['plan'],adapter.scene_ref)
    verified=read(root/'u02_t03/t03_verify.json')
    if verified['binding']!=adapter.binding or verified['candidate_sha256']!=digest(canonical(candidate)) or verified['facts']['passed'] is not True:raise ValueError('U03_T03_VERIFICATION_REQUIRED')
    from .adapter import WidthGates
    gates=WidthGates(root);verification=read(root/'u03_t04/t04_verify.json');run=read(root/'u03_t04/t04_run.json')
    if verification['binding']!=gates.binding or verification['result']['verification']['candidate_ref']!=run['result']['candidate_ref'] or verification['result']['verification']['geometric_status']!='PASS':raise ValueError('U03_T04_VERIFICATION_REQUIRED')
    return root
