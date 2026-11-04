"""Retained U04 custody is explicit; its historical execution is never rerun."""
from pathlib import Path
from src.stage_abi.store import canonical,digest
from src.u05_board.store import ReadOnlyStore
from tools.t01_operator_host import ROOT,read,fresh
from tools.pcb_workspace import WORK,require_storage
from tools.t01_native_route import verify_attempt

CONTRACT=ROOT/'contracts/operator/u05_board.json'
T05=tuple('t05_'+s for s in ('inspect','admit','plan','run','verify','compare','review','controls'))
FILES=('pcb_kicad_write','pcb_kicad_verify','pcb_gerber_export','pcb_gerber_verify','pcb_export_controls')
STEPS=('u04_predecessor_verify',*T05,*FILES)

def local(path,exists=True):
    p=Path(path)
    if not p.is_absolute() or '..' in p.parts or not p.is_relative_to(WORK) or any(q.is_symlink() for q in (p,*p.parents) if q.is_relative_to(WORK)) or (exists and not p.exists()):raise ValueError('U05_LACIE_ABSOLUTE_PATH_REQUIRED:'+str(p))
    return p

def inventory(root):
    return {str(p.relative_to(root)):dict(sha256=digest(p.read_bytes()),bytes=p.stat().st_size,mtime_ns=p.stat().st_mtime_ns) for p in root.rglob('*') if p.is_file()}

def assert_inventory(root,expected):
    actual=inventory(root)
    if actual!=expected:raise ValueError('U05_PREDECESSOR_INVENTORY_CHANGED')
    return dict(passed=True,files=len(actual),sha256_bytes_mtime_and_inventory_unchanged=True)

def binding(job):
    require_storage();job=local(job);root=job/'native'
    receipt=read(root/'U04_RECEIPT.json');cp=root/'U04_EXPORT_CHECKPOINT.json';machine=root/'MACHINE_RECEIPT.json'
    from src.u04_board.custody import operation_steps
    if receipt['status']!='PASS_FRESH_U04_EXPORT' or receipt['operations']!=list(operation_steps(root)) or receipt['checkpoint_sha256']!=digest(cp.read_bytes()):raise ValueError('U05_COMPLETE_U04_REQUIRED')
    if read(job/'job.json')['task_scope']!='u04-board' or read(root/'operator_ui/current.json')['status']!='COMPLETE' or read(root/'adapter_stopped.json')['status']!='STOPPED':raise ValueError('U05_U04_NOT_TERMINAL')
    return dict(schema='u05-retained-u04-binding/1',job=str(job),root=str(root),receipt_sha256=digest((root/'U04_RECEIPT.json').read_bytes()),checkpoint_sha256=digest(cp.read_bytes()),machine_receipt_sha256=digest(machine.read_bytes()),retained_operations=receipt['operations'],source_sha256=read(root/'data_board/source_manifest.json')['source_sha256'],scene_ref=read(root/'u04_t02/t02_run.json')['candidate']['output_scene_ref'],kicad=str(root/'data_output/candidate/board.kicad_pcb'),kicad_sha256=digest((root/'data_output/candidate/board.kicad_pcb').read_bytes()))

def validate_binding(value):
    if binding(Path(value['job']))!=value:raise ValueError('U05_U04_BINDING_CHANGED')
    return Path(value['root'])

def verify_u04(value):
    root=validate_binding(value);job=root.parent;cp=read(root/'U04_EXPORT_CHECKPOINT.json');receipt=read(root/'U04_RECEIPT.json')
    for name,h in cp['files'].items():
        p=local(root/name)
        if not p.is_relative_to(root) or digest(p.read_bytes())!=h:raise ValueError('U05_U04_CHECKPOINT_EVIDENCE_CHANGED:'+name)
    from src.u04_board.custody import verify_prefix
    verify_prefix(root,tuple(value['retained_operations']))
    machine=read(root/'MACHINE_RECEIPT.json');ops=value['retained_operations']
    if machine['operations']!=ops or machine['checkpoint_sha256']!=value['checkpoint_sha256'] or machine['human_or_agent_observations']!='NOT_RUN' or list((root/'operator_ui').glob('review-*.json')):raise ValueError('U05_U04_MACHINE_MODE_REQUIRED')
    if len(machine['proofs'])!=len(ops):raise ValueError('U05_U04_PROOF_COVERAGE_MISSING')
    accepted_notes={read(p)['arguments']['attempt_id']:read(p)['arguments']['audit']['note'] for p in (root/'audits').glob('*/request.json')}
    predicates=0
    for ordinal,(name,h) in enumerate(sorted(machine['proofs'].items())):
        p=local(root/name);proof=read(p)
        if digest(p.read_bytes())!=h or proof['status']!='PASS' or proof['operation']!=ops[ordinal] or not all(c['passed'] is True for c in proof['checks']):raise ValueError('U05_U04_MACHINE_PROOF_INVALID')
        request=read(root/'audits'/f'machine-{ordinal+1:03d}'/'proof.json')
        if request!=proof:raise ValueError('U05_U04_PROOF_BINDING_INVALID')
        from src.pcb_data_abi.machine_audit import proof_note
        if accepted_notes.get(proof['attempt_id'])!=proof_note(h):raise ValueError('U05_U04_ACCEPTED_PROOF_HASH_MISMATCH')
        predicates+=len(proof['checks'])
    terminal=read(job/'TERMINAL_RUN.json');journal=local(terminal['journal']);result=read(journal/'result.json')
    if result['job']!=str(job) or result['machine_audits']!=len(ops) or result['observation_audits']!=0 or result['render_operations']!=0:raise ValueError('U05_U04_FINAL_DELIVERY_INVALID')
    for row in result['files']:
        p=local(row['path'])
        if not p.is_relative_to(job):raise ValueError('U05_U04_DELIVERY_PATH_ESCAPES')
        blob=p.read_bytes()
        if digest(blob)!=row['sha256'] or len(blob)!=row['bytes']:raise ValueError('U05_U04_FINAL_ARTIFACT_CHANGED:'+str(p))
    saved=read(root/'u04_t02/t02_run.json');verified=read(root/'u04_t02/t02_verify.json');store=ReadOnlyStore(root/'runtime')
    if saved['candidate']!=store.get_json(saved['candidate_ref'],kind='candidate') or verified['candidate_ref']!=saved['candidate_ref'] or not verified['facts']['passed']:raise ValueError('U05_VERIFIED_T02_REQUIRED')
    return dict(passed=True,retained_U04_gates=len(ops),retained_machine_audits=len(ops),retained_machine_predicates=predicates,verified_final_files=len(result['files']),predecessor_scene_ref=value['scene_ref'],source_sha256=value['source_sha256'],prefix_execution='RETAINED_VERIFIED_NOT_REEXECUTED',rendering='NOT_REQUESTED',owner='PENDING_USER')

def session(root):
    root=local(root);start=read(root/'U05_START.json')
    for name,h in start['producer_files'].items():
        if digest((ROOT/name).read_bytes())!=h:raise ValueError('U05_PRODUCER_CHANGED:'+name)
    validate_binding(start['predecessor'])
    if start.get('reference'):
        from .reference import verify_reference
        verify_reference(start['reference'],start['predecessor'])
    return start

def require_operation(root,operation):
    state=read(Path(root)/'U05_SEQUENCE.json');accepted=state['accepted']
    if state['operations']!=list(STEPS) or len(accepted)>=len(STEPS) or operation!=STEPS[len(accepted)]:raise ValueError('U05_AUDITED_OPERATION_ORDER_REQUIRED')
    for i,row in enumerate(accepted):
        folder=Path(root)/'attempts'/row['attempt'];verify_attempt(folder);proof_path=Path(root)/'audits'/row['proof'];proof=read(proof_path)
        if row['operation']!=STEPS[i] or proof['attempt_id']!=row['attempt'] or read(folder/'receipt.json')['tool']!=STEPS[i] or digest(proof_path.read_bytes())!=row['proof_sha256'] or proof['status']!='PASS' or proof['operation']!=STEPS[i] or not all(c['passed'] for c in proof['checks']):raise ValueError('U05_PRIOR_AUDIT_CHANGED')
