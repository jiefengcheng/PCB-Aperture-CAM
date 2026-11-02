"""Native data/ROI lineage checkpoints for the crop-driven operator."""
from pathlib import Path
from src.stage_abi.store import canonical,digest
from .roi import local,read

ROI=('pcb_inputs_verify','pcb_roi_locate','pcb_roi_verify')
T01=('t01_compile','t01_discover','t01_inspect','t01_plan','t01_run','t01_verify','t01_compare','t01_review','t01_negative_compile')
CHECK='crop_candidate_check'
FILES=('pcb_kicad_write','pcb_kicad_verify','pcb_gerber_export','pcb_gerber_verify','pcb_export_controls')
RENDER=('render_compare','render_verify','render_controls')
STEPS=(*ROI,*T01,CHECK,*FILES,*RENDER)

def accepted(root,expected,prefix=False):
    from tools.t01_native_route import verify_attempt
    root=local(root,True);attempts=sorted([(read(p),p.parent) for p in (root/'attempts').glob('*/receipt.json')],key=lambda r:r[0]['completed_at'])
    names=[r['tool'] for r,p in attempts]
    if prefix:
        if names!=list(STEPS[:len(names)]) or names[:len(expected)]!=list(expected):raise ValueError('CROP_SEQUENCE_INCOMPLETE')
        attempts=attempts[:len(expected)]
    elif names!=list(expected):raise ValueError('CROP_SEQUENCE_INCOMPLETE')
    selected={r['attempt_id'] for r,p in attempts};audits={}
    for p in (root/'audits').glob('*/request.json'):
        req=read(p)['arguments'];decision=read(p.parent/'decision.json')
        if prefix and req['attempt_id'] not in selected:continue
        if decision['status']!='PASS_SLICE_OBSERVATION_AUDIT' or req['attempt_id'] in audits:raise ValueError('CROP_AUDIT_INVALID')
        audits[req['attempt_id']]=(req['audit'],decision['accepted_operation'])
    if len(audits)!=len(expected):raise ValueError('CROP_AUDIT_INCOMPLETE')
    responses={}
    for receipt,path in attempts:
        verify_attempt(path);result=read(path/'result.json');audit,operation=audits[receipt['attempt_id']]
        if (result['error'] is not None or receipt['status']=='FAIL' or operation!=receipt['tool'] or
            audit['verdict']!='PASS' or audit['response_sha256']!=digest((path/'abi/stdout.json').read_bytes()) or
            audit['observed']!=result['result']['facts'] or not isinstance(audit['note'],str) or not 1<=len(audit['note'])<=300):raise ValueError('CROP_AUDIT_MISMATCH')
        responses[operation]=read(path/'abi/stdout.json')
    return responses

def checkpoint(root,name,ops,extras):
    root=local(root,True);accepted(root,ops)
    paths=[p for d in ('attempts','audits') for p in (root/d).rglob('*') if p.is_file()]+list(extras)
    files={str(local(p).relative_to(root)):digest(p.read_bytes()) for p in paths}
    p=root/name
    with p.open('xb') as f:f.write(canonical(dict(schema='pcb-crop-checkpoint/1',operations=list(ops),files=files)))
    return dict(checkpoint=str(p),checkpoint_sha256=digest(p.read_bytes()))

def verify_checkpoint(path,sha,ops):
    path=local(path,True);root=path.parent
    if digest(path.read_bytes())!=sha:raise ValueError('CROP_CHECKPOINT_CHANGED')
    value=read(path)
    if set(value)!={'schema','operations','files'} or value['schema']!='pcb-crop-checkpoint/1' or value['operations']!=list(ops):raise ValueError('CROP_CHECKPOINT_INVALID')
    required={'RECEIPT.json','data_roi/roi_verified.json'}
    if ops[-1]==CHECK:required|={'crop_inputs.json','data_roi/location.json'}
    else:required|={'T01_CHECKPOINT.json','data_output/pcb_gerber_export.json','data_output/pcb_gerber_verify.json','data_output/pcb_export_controls.json','data_output/candidate/board.kicad_pcb','data_output/candidate/gerbers/board-F_Cu.gbr'}
    if not required<=value['files'].keys():raise ValueError('CROP_CHECKPOINT_REQUIRED_EVIDENCE_MISSING')
    for name,h in value['files'].items():
        p=local(root/name,True)
        if not p.is_relative_to(root) or digest(p.read_bytes())!=h:raise ValueError('CROP_CHECKPOINT_EVIDENCE_CHANGED')
    accepted(root,ops,prefix=True);return root

def validate_host(host,phase):
    keys={'schema','checkpoint','checkpoint_sha256','output'}
    if phase=='render':keys|={'contract_path','contract_sha256'}
    if set(host)!=keys or host['schema']!=f'pcb-crop-{phase}-host/1':raise ValueError('CROP_HOST_INVALID')
    ops=(*ROI,*T01,CHECK) if phase=='data' else (*ROI,*T01,CHECK,*FILES)
    root=verify_checkpoint(host['checkpoint'],host['checkpoint_sha256'],ops)
    receipt=read(root/'RECEIPT.json');roi=read(root/'data_roi/roi_verified.json')
    if receipt.get('status')!='PASS_CROP_T01_VERIFIED' or receipt.get('roi_sha256')!=digest((root/'data_roi/roi_verified.json').read_bytes()) or roi.get('facts',{}).get('location_verified') is not True:raise ValueError('CROP_VERIFIED_ROI_RECEIPT_REQUIRED')
    folder='data_output' if phase=='data' else 'render_output'
    if local(host['output'],True)!=root/folder:raise ValueError('CROP_OUTPUT_BINDING_INVALID')
    return root
