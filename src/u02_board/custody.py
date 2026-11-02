"""U02's own sequence and checkpoint authority; original T01 custody unchanged."""
from pathlib import Path
from src.stage_abi.store import digest,canonical
from src.pcb_data_abi.board_custody import accepted,checkpoint
from tools.t01_operator_host import ROOT,read

CONTRACT=ROOT/'contracts/operator/u02_board.json'
STEPS=tuple(read(CONTRACT)['operations'])
T03=tuple(op for op in STEPS if op.startswith('t03_'))
PREFIX=STEPS[:13]
THROUGH_T03=STEPS[:-5]


def verify_prefix(root,expected):
    root=Path(root)
    receipts=sorted((read(p) for p in(root/'attempts').glob('*/receipt.json')),key=lambda r:r['completed_at'])
    names=[r['tool'] for r in receipts]
    if names!=list(STEPS[:len(names)]) or names[:len(expected)]!=list(expected):raise ValueError('U02_SEQUENCE_INCOMPLETE')
    return accepted(root,names)


def export_root(host):
    if set(host)!={'schema','checkpoint','checkpoint_sha256','output'} or host['schema']!='pcb-u02-data-host/1':raise ValueError('U02_DATA_HOST_REQUIRED')
    path=Path(host['checkpoint']);root=path.parent
    if digest(path.read_bytes())!=host['checkpoint_sha256'] or path!=root/'U02_CHECKPOINT.json':raise ValueError('U02_CHECKPOINT_CHANGED')
    value=read(path)
    if value['operations']!=list(THROUGH_T03):raise ValueError('U02_T03_CHECKPOINT_REQUIRED')
    required={'RECEIPT.json','T01_CHECKPOINT.json','u02_t03/t03_inspect.json','u02_t03/t03_search.json','u02_t03/t03_verify.json','u02_t03/t03_controls.json','U02_START.json'}
    if not required<=value['files'].keys():raise ValueError('U02_CHECKPOINT_EVIDENCE_MISSING')
    from src.pcb_data_abi.roi import local
    for name,h in value['files'].items():
        p=local(root/name,True)
        if not p.is_relative_to(root) or digest(p.read_bytes())!=h:raise ValueError('U02_CHECKPOINT_EVIDENCE_CHANGED:'+name)
    verify_prefix(root,THROUGH_T03)
    if read(root.parent/'job.json')['task_scope']!='u02-board' or Path(host['output'])!=root/'data_output':raise ValueError('U02_EXPORT_SCOPE_CHANGED')
    from .adapter import RetainPathsAdapter,verify_candidate
    adapter=RetainPathsAdapter(root)
    candidate=read(root/'u02_t03/t03_search.json')['candidate']
    verify_candidate(candidate,read(root/'u02_t03/t03_plan.json')['plan'],adapter.scene_ref)
    verified=read(root/'u02_t03/t03_verify.json')
    if verified['binding']!=adapter.binding or verified['candidate_sha256']!=digest(canonical(candidate)) or verified['facts']['passed'] is not True:raise ValueError('U02_T03_VERIFICATION_REQUIRED')
    return root
