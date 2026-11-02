"""Closed, hash-bound handoffs for fresh C01 results, never arbitrary inputs."""
import json
from pathlib import Path
from src.stage_abi.store import canonical, digest

ROOT = Path(__file__).resolve().parents[2]
T01 = ('t01_compile', 't01_discover', 't01_inspect', 't01_plan', 't01_run',
       't01_verify', 't01_compare', 't01_review', 't01_negative_compile')
ORACLE = 'c01_reproduction_check'
FILES = ('pcb_kicad_write', 'pcb_kicad_verify', 'pcb_gerber_export',
         'pcb_gerber_verify', 'pcb_export_controls')
RENDER = ('render_c01_compare', 'render_c01_verify', 'render_c01_controls')
STEPS = (*T01, ORACLE, *FILES, *RENDER)

def read(path):
    return json.loads(Path(path).read_bytes())

def local(path):
    path = Path(path).absolute()
    if ('..' in path.parts or not path.is_relative_to(ROOT/'out') or
            any(p.is_symlink() for p in (path, *path.parents) if p.is_relative_to(ROOT))):
        raise ValueError('C01_PIPELINE_OUTPUT_SCOPE_REQUIRED')
    return path

def accepted(root, expected, *, prefix=False):
    """Independently match actual attempts to all accepted native observations."""
    from tools.t01_native_route import verify_attempt
    root = local(root)
    attempts = sorted([(read(p), p.parent) for p in (root/'attempts').glob('*/receipt.json')],
                      key=lambda item: item[0]['completed_at'])
    names = [r['tool'] for r,p in attempts]
    if prefix and names == list(STEPS[:len(names)]) and names[:len(expected)] == list(expected):
        attempts = attempts[:len(expected)]
    elif names != list(expected):
        raise ValueError('C01_PIPELINE_SEQUENCE_INCOMPLETE')
    audits = {}
    for path in (root/'audits').glob('*/request.json'):
        req, decision = read(path)['arguments'], read(path.parent/'decision.json')
        if prefix and req['attempt_id'] not in {r['attempt_id'] for r,p in attempts}:
            continue
        if decision['status'] != 'PASS_SLICE_OBSERVATION_AUDIT' or req['attempt_id'] in audits:
            raise ValueError('C01_PIPELINE_AUDIT_INVALID')
        audits[req['attempt_id']] = (req['audit'], decision['accepted_operation'])
    if len(audits) != len(expected):
        raise ValueError('C01_PIPELINE_AUDIT_INCOMPLETE')
    responses = {}
    for receipt, path in attempts:
        verify_attempt(path)
        result = read(path/'result.json')
        if result['error'] is not None or receipt['status'] == 'FAIL':
            raise ValueError('C01_PIPELINE_FAILED_ATTEMPT')
        audit, operation = audits[receipt['attempt_id']]
        raw = path/'abi/stdout.json'
        if (operation != receipt['tool'] or audit['verdict'] != 'PASS' or
                audit['response_sha256'] != digest(raw.read_bytes()) or
                audit['observed'] != result['result']['facts'] or
                not isinstance(audit['note'], str) or not 1 <= len(audit['note']) <= 300):
            raise ValueError('C01_PIPELINE_AUDIT_MISMATCH')
        responses[operation] = read(raw)
    return responses

def checkpoint(root, name, operations, extras):
    root = local(root)
    accepted(root, operations)
    paths = [p for sub in ('attempts','audits') for p in (root/sub).rglob('*') if p.is_file()]
    paths.extend(local(p) for p in extras)
    files = {str(p.relative_to(root)): digest(p.read_bytes()) for p in paths}
    value = dict(schema='pcb-c01-pipeline-checkpoint/1', operations=list(operations), files=files)
    path = root/name
    with path.open('xb') as f: f.write(canonical(value))
    return dict(checkpoint=str(path), checkpoint_sha256=digest(path.read_bytes()))

def verify_checkpoint(path, sha, operations):
    path = local(path); root = path.parent
    if digest(path.read_bytes()) != sha:
        raise ValueError('C01_PIPELINE_CHECKPOINT_CHANGED')
    value = read(path)
    if (set(value) != {'schema','operations','files'} or
            value['schema'] != 'pcb-c01-pipeline-checkpoint/1' or value['operations'] != list(operations)):
        raise ValueError('C01_PIPELINE_CHECKPOINT_INVALID')
    for name, expected in value['files'].items():
        file = local(root/name)
        if not file.is_relative_to(root) or digest(file.read_bytes()) != expected:
            raise ValueError('C01_PIPELINE_EVIDENCE_CHANGED')
    accepted(root, operations, prefix=True)
    return root

def validate_data_host(host):
    keys = {'schema','predecessor','predecessor_receipt_sha256','source_sha256',
            'edit_reference','edit_sha256','output','authority','checkpoint','checkpoint_sha256'}
    if set(host) != keys or host['schema'] != 'pcb-c01-file-host/2':
        raise ValueError('C01_PIPELINE_DATA_HOST_INVALID')
    root = verify_checkpoint(host['checkpoint'], host['checkpoint_sha256'], (*T01, ORACLE))
    contract = read(ROOT/'contracts/t01/c01_files.json')
    receipt = root/'RECEIPT.json'
    if (local(host['predecessor']) != root or local(host['output']) != root/'data_output' or
            digest(receipt.read_bytes()) != host['predecessor_receipt_sha256'] or
            read(host['checkpoint'])['files'].get('RECEIPT.json') != host['predecessor_receipt_sha256'] or
            host['source_sha256'] != contract['source_sha256'] or host['edit_sha256'] != contract['edit_sha256'] or
            Path(host['edit_reference']) != ROOT/'dataset/szu-comm_3020301113B_intake_ready_20261021_v1/raw/EDIT/top_layer.kicad_pcb'):
        raise ValueError('C01_PIPELINE_DATA_BINDING_FAILED')
    return root

def validate_render_host(host):
    keys = {'schema','contract_path','contract_sha256','output','checkpoint','checkpoint_sha256'}
    if set(host) != keys or host['schema'] != 'pcb-c01-render-host/2':
        raise ValueError('C01_PIPELINE_RENDER_HOST_INVALID')
    root = verify_checkpoint(host['checkpoint'], host['checkpoint_sha256'], (*T01, ORACLE, *FILES))
    path = local(host['contract_path'])
    if path != root/'pipeline_render_contract.json' or local(host['output']) != root/'render_output':
        raise ValueError('C01_PIPELINE_RENDER_BINDING_FAILED')
    blob = path.read_bytes()
    if digest(blob) != host['contract_sha256']:
        raise ValueError('C01_PIPELINE_RENDER_CONTRACT_CHANGED')
    contract, template = json.loads(blob), read(ROOT/'contracts/render/c01.json')
    inputs = contract.pop('inputs'); contract.pop('authority')
    template.pop('inputs'); template.pop('authority')
    if contract != template:
        raise ValueError('C01_PIPELINE_RENDER_POLICY_CHANGED')
    paths = dict(kicad=root/'data_output/candidate/board.kicad_pcb',
                 gerber=root/'data_output/candidate/gerbers/board-F_Cu.gbr')
    cp = read(host['checkpoint'])['files']
    expected = {k:dict(path=str(p.relative_to(ROOT)),sha256=digest(p.read_bytes())) for k,p in paths.items()}
    if inputs != expected or any(cp.get(str(p.relative_to(root))) != expected[k]['sha256'] for k,p in paths.items()):
        raise ValueError('C01_PIPELINE_RENDER_INPUT_CHANGED')
    return path
