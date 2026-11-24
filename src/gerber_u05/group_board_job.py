"""Explicit full-board construction diagnostic for the qualified group caller.

This does not invoke the older checked-profile algorithm or publish a scene.
Fresh, code-bound five/64 results gate execution. Groups are never audited;
the existing residual, connection, pocket and preservation conditions remain.
"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import time
import traceback

from . import pipeline as p, profile_intake as intake, group_stage
from src import hole_acceptance
from src.stage_abi.contracts import finite_json

SCHEMA='t04-group-board-diagnostic-readiness/1'


def file_sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb')as stream:
        for block in iter(lambda:stream.read(1024**2),b''):h.update(block)
    return h.hexdigest()


def checked(stage):
    """Re-evaluate existing component dispositions; no group geometry audit."""
    h=stage['hybrid_components'];failures=[]
    for name in('reference_checks','functional_checks'):
        if not h.get(name,{}).get('passed'):failures.append(name)
    if h.get('bulk',{}).get('error')is not None:failures.append('bulk')
    connections=h.get('joint_connections',{}).get('reports')
    if connections is None or not all(r['passed']for r in connections):failures.append('native_connections')
    pocket=h.get('corner_smoothing',{}).get('pocket_completion',{})
    if not pocket.get('passed'):failures.append('pockets')
    if h.get('constructed_groups_audited')!=0:failures.append('constructed_group_audit')
    for name in('constructed_group_bytes_preserved','covered_trace_copper_preserved'):
        if h.get(name)is not True:failures.append(name)
    if stage.get('publication_ready')is not False or stage.get('output_scene_ref')is not None:
        failures.append('diagnostic_publication_boundary')
    if failures:raise ValueError('T04_GROUP_DIAGNOSTIC_COMPONENT_FAILURE:'+','.join(failures))
    return dict(reference=True,functional=True,pockets=True,
        native_connections=len(connections),constructed_groups_audited=0,
        frozen_endpoint_obligations=h['frozen_endpoint_obligations'],
        unresolved_corner_records=h['corner_smoothing']['unresolved'])


def write_stage(path,stage):
    """Exact canonical encoding streamed to avoid a second full-board blob."""
    finite_json(stage);h=hashlib.sha256()
    encoder=json.JSONEncoder(sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)
    with Path(path).open('xb')as raw:
        with gzip.GzipFile(filename='',mode='wb',fileobj=raw,mtime=0)as zipped:
            parts=[];size=0
            for part in encoder.iterencode(stage):
                parts.append(part);size+=len(part)
                if size>=1024**2:
                    data=''.join(parts).encode();h.update(data);zipped.write(data);parts=[];size=0
            if parts:
                data=''.join(parts).encode();h.update(data);zipped.write(data)
    return dict(path=str(Path(path).resolve()),sha256=file_sha(path),stage_sha256=h.hexdigest())


def failure_operands(error,directory):
    """Preserve numerical failure inputs once, without re-running geometry."""
    from shapely import to_wkb,get_precision,get_srid
    from shapely.geometry.base import BaseGeometry
    frames=[];tb=error.__traceback__;site={}
    while tb is not None:
        frame=tb.tb_frame;values=frame.f_locals
        if frame.f_code.co_name=='run'and 'route'in values:
            site={k:values[k]for k in('route','pt','ends')if k in values}
        if frame.f_code.co_name in('skin_fill','face_cut','spindle_addition','difference_for_window'):
            shapes={k:v for k,v in values.items()if k in('support','path','window','protected','opened','closed','padded','left','right')and isinstance(v,BaseGeometry)}
            if shapes:frames.append((frame.f_code.co_name,shapes))
        tb=tb.tb_next
    if not frames:return None
    root=Path(directory)/'failure_operands';root.mkdir(exist_ok=False);records=[]
    for i,(function,shapes)in enumerate(frames):
        operands={}
        for name,shape in shapes.items():
            path=root/f'{i:02d}_{name}.wkb';raw=to_wkb(shape,include_srid=True)
            with path.open('xb')as stream:stream.write(raw)
            operands[name]=dict(path=str(path),sha256=p.digest(raw),precision_mm=float(get_precision(shape)),srid=int(get_srid(shape)))
        records.append(dict(function=function,operands=operands))
    def plain(value):
        if hasattr(value,'tolist'):return plain(value.tolist())
        if isinstance(value,dict):return {k:plain(v)for k,v in value.items()}
        if isinstance(value,(tuple,list)):return [plain(v)for v in value]
        return value
    p.save(root/'INPUTS.json',dict(site=plain(site),frames=records))
    return dict(path=str(root/'INPUTS.json'),sha256=file_sha(root/'INPUTS.json'))


def require(path,inputs):
    ready=p.load(path);code=intake.source_inventory()
    if (ready.get('schema')!=SCHEMA or ready.get('status')!='READY_FOR_BOARD_CONSTRUCTION_DIAGNOSTIC'
            or ready['source_files']!=code or ready['inputs']!=inputs):
        raise ValueError('T04_GROUP_BOARD_READINESS_CODE_OR_INPUT_CHANGED')
    tests=ready['tests']
    if tests['source_files']!=code or tests['exit_code']!=0 or file_sha(tests['log'])!=tests['log_sha256']:
        raise ValueError('T04_GROUP_BOARD_READINESS_TESTS_CHANGED')
    kinds=set()
    for case in ready['cases']:
        if file_sha(case['receipt'])!=case['receipt_sha256']:
            raise ValueError('T04_GROUP_BOARD_READINESS_CASE_CHANGED')
        receipt=p.load(case['receipt']);artifact=receipt['stage']
        if (receipt['source_files']!=code or receipt['inputs']!=inputs or receipt['full_board_run']
                or receipt['kind']not in('five','64')or file_sha(artifact['path'])!=artifact['sha256']):
            raise ValueError('T04_GROUP_BOARD_READINESS_BOUND_CASE_REQUIRED')
        raw=gzip.decompress(Path(artifact['path']).read_bytes())
        if p.digest(raw)!=artifact['stage_sha256']:
            raise ValueError('T04_GROUP_BOARD_READINESS_STAGE_CHANGED')
        stage=json.loads(raw);summary=checked(stage)
        if summary!=receipt['checks']or stage['input_binding']!=inputs or stage.get('full_board_run'):
            raise ValueError('T04_GROUP_BOARD_READINESS_COMPONENTS_CHANGED')
        parity=receipt['parity']
        if not parity['passed']or not parity['copper_bytes_identical']or not parity['proof_and_report_fields_identical']:
            raise ValueError('T04_GROUP_BOARD_READINESS_PARITY_REQUIRED')
        # The actual bounded stage and cohort inventory are retained, not a
        # generic success string or an inherited checked-profile qualification.
        count=len(stage['requested_routes'])
        if len(set(stage['requested_routes']))!=count or count!=(30 if receipt['kind']=='five'else 64):
            raise ValueError('T04_GROUP_BOARD_READINESS_COHORT_CHANGED')
        kinds.add(receipt['kind'])
    if kinds!={'five','64'}or len(ready['cases'])!=2:
        raise ValueError('T04_GROUP_BOARD_READINESS_BOTH_COHORTS_REQUIRED')
    return ready


def execute(source,directory,qualification):
    p.configure();directory=Path(directory).absolute()
    if not directory.resolve().is_relative_to((p.ROOT/'out/lacie_work').resolve()):
        raise ValueError('T04_GROUP_BOARD_REQUIRES_LACIE')
    started=time.perf_counter();reader,binding,scene,settings,inputs=intake.read(source)
    ready=require(qualification,inputs);code=intake.source_inventory()
    # The new job is exclusive. A failed attempt is never resumed or resealed.
    directory.mkdir(exist_ok=False)
    p.save(directory/'JOB.json',dict(schema='t04-group-board-diagnostic-job/1',accepted_t03=str(source),
        source_files=code,inputs=inputs,qualification=str(qualification),qualification_sha256=file_sha(qualification),
        scope='FULL_BOARD_DIAGNOSTIC',full_board_run=True,replay=False,export=False))
    p.save(directory/'RUNNING.json',dict(status='RUNNING',scope='FULL_BOARD_DIAGNOSTIC'))
    def progress(event):
        value=dict(event,elapsed_s=time.perf_counter()-started)
        with (directory/'PROGRESS.jsonl').open('a')as stream:stream.write(json.dumps(value)+'\n')
        print(json.dumps(value),flush=True)
    try:
        progress(dict(event='readiness_passed',cohorts=['five','64'],constructed_groups_audited=0))
        intake.prepare(directory,source);hole_acceptance.bind(directory)
        store=intake.BoundStore(directory/'runtime',reader)
        tick=time.perf_counter();p.initialize_t04(store,binding,scene);initialization=time.perf_counter()-tick
        rule=dict(ready['preparation'],scope='FULL_BOARD_DIAGNOSTIC',full_board_diagnostic=True,
                  input_binding=inputs,hybrid_components=True,progress=progress)
        progress(dict(event='initialization_complete',wall_s=initialization))
        stage=group_stage.run(store,scene,route_ids=None,settings=settings,rule=rule)
        if intake.source_inventory()!=code:raise ValueError('T04_GROUP_BOARD_EXECUTION_CODE_CHANGED')
        store.verify_reads();artifact=write_stage(directory/'construction.json.gz',stage)
        checks=checked(stage)
        receipt=dict(status='FULL_BOARD_CONSTRUCTION_DIAGNOSTIC; NOT_COMPLETE_T04',
            scope='FULL_BOARD_DIAGNOSTIC',full_board_run=True,replay=False,export=False,
            source_files=code,inputs=inputs,stage=artifact,checks=checks,output_scene_ref=None,
            publication_ready=False,complete_t04=False,summary=stage['summary'],
            requested_admitted_routes=len(stage['requested_routes']),
            accounted_native_routes=len(stage['native_route_dispositions']),
            initialize_wall_s=initialization,complete_operation_wall_s=time.perf_counter()-started)
        p.save(directory/'RESULT.json',receipt)
        progress(dict(event='diagnostic_complete',summary=stage['summary'],checks=checks))
        return receipt
    except BaseException as error:
        try:operands=failure_operands(error,directory)
        except Exception as capture_error:operands=dict(capture_error=repr(capture_error))
        p.save(directory/'FAILED.json',dict(status='FAIL',error=repr(error),traceback=traceback.format_exc(),
            elapsed_s=time.perf_counter()-started,full_board_run=True,replay=False,export=False,
            failure_operands=operands))
        raise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--accepted-t03',required=True)
    parser.add_argument('--output',required=True)
    parser.add_argument('--qualification',required=True)
    args=parser.parse_args()
    print(json.dumps(execute(args.accepted_t03,args.output,args.qualification)),flush=True)


if __name__=='__main__':main()
