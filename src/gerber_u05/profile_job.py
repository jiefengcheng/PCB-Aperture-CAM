"""Explicit T04-only operation from an accepted T03 job. No replay/export."""
import argparse
import gzip
import json
from pathlib import Path
import time
import traceback
from . import pipeline as p, profile_intake as intake
from .profile_stage import run
from .translated_profile import SCHEMA
from src import hole_acceptance


def external(path):
    path = Path(path).absolute()
    workspace = (p.ROOT/'out/lacie_work').resolve()
    if not path.resolve().is_relative_to(workspace):
        raise ValueError('T04_PROFILE_JOB_REQUIRES_LACIE_WORKSPACE')
    return path


def prepare(source, output, algorithm='checked-profile'):
    if algorithm not in ('checked-profile', 'parallel-groups'):
        raise ValueError('T04_PROFILE_ALGORITHM_UNKNOWN')
    _, _, _, _, inputs = intake.read(source)
    output = external(output)
    output.mkdir(exist_ok=False)
    job = dict(schema='t04-source-built-profile-job/1', accepted_t03=str(Path(source).resolve()),
               inputs=inputs, source_files=intake.source_inventory(), full_board_run=False,
               status='PREPARED_NOT_EXECUTED', algorithm=algorithm,
               phase_order=(['DIRECT_GROUP_INTERIORS'] if algorithm == 'parallel-groups' else
                            ['SOURCE_BUILT_25', 'ADDITIVE_SIDE_GROWTH']),
               replay=False, export=False)
    (output/'JOB.json').write_bytes(p.canonical(job))
    return dict(status=job['status'], job=str(output), full_board_run=False)


def execute(directory, route_file=None, qualification=None, whole_board=False, group_construction=False, hybrid_components=False):
    if hybrid_components and not group_construction:
        raise ValueError('T04_COMPONENTS_REQUIRE_BOUNDED_GROUP_ENTRY')
    directory = external(directory)
    if (route_file is None) == (not whole_board):
        raise ValueError('T04_PROFILE_EXPLICIT_BOUND_OR_WHOLE_BOARD_REQUIRED')
    if any((directory/n).exists() for n in ('RUNNING.json', 'FAILED.json', 'RESULT.json')):
        raise ValueError('T04_PROFILE_JOB_ALREADY_ATTEMPTED_NO_RESUME')
    job = p.load(directory/'JOB.json')
    if job['schema'] != 't04-source-built-profile-job/1' or job['status'] != 'PREPARED_NOT_EXECUTED':
        raise ValueError('T04_PROFILE_PREPARED_JOB_REQUIRED')
    if (job.get('algorithm', 'checked-profile') == 'parallel-groups') != group_construction:
        raise ValueError('T04_PROFILE_PREPARED_ALGORITHM_CHANGED')
    if group_construction and whole_board:
        raise ValueError('T04_GROUP_INCREMENT_BOUNDED_ONLY')
    if job['source_files'] != intake.source_inventory():
        raise ValueError('T04_PROFILE_PREPARED_CODE_CHANGED')
    started = time.perf_counter()
    reader, binding, scene, settings, inputs = intake.read(job['accepted_t03'], job['inputs'])
    if inputs != job['inputs']:
        raise ValueError('T04_PROFILE_PREPARED_INPUT_CHANGED')
    routes = None if whole_board else json.loads(Path(route_file).read_bytes())['routes']
    if routes is not None and (not routes or len(routes) > 128 or len(routes) != len(set(routes))):
        raise ValueError('T04_PROFILE_BOUNDED_ROUTES_INVALID')
    rule = dict(schema=SCHEMA, scope='FULL_BOARD' if whole_board else 'BOUNDED',
                input_binding=inputs, policy_sha256=inputs['policy_sha256'],
                source_preparation=str(directory/'source_roles'), group_cache=str(directory/'parallel_groups'),
                width_variation_limit=.25, maximum_translation_mm=.025, transition_length_mm=.05,
                coupled_allocation=True, group_construction=group_construction, hybrid_components=hybrid_components)
    if whole_board:
        from .profile_readiness import require
        if qualification is None:
            raise ValueError('T04_PROFILE_FULL_BOARD_QUALIFICATION_REQUIRED')
        rule['qualification_manifest'] = str(Path(qualification).resolve())
        require(qualification, rule)
    # Exclusive publication is the attempt latch. Any later failure is retained.
    with (directory/'RUNNING.json').open('xb') as f:
        f.write(p.canonical(dict(source_files=job['source_files'], scope=rule['scope'], route_ids=routes)))
    try:
        intake.prepare(directory, job['accepted_t03'])
        hole_acceptance.bind(directory)
        store = intake.BoundStore(directory/'runtime', reader)
        def progress(event):
            value = dict(event, elapsed_s=time.perf_counter()-started)
            with (directory/'PROGRESS.jsonl').open('a') as f:
                f.write(json.dumps(value)+'\n')
            if event.get('event') not in ('motion_plan', 'proposal_start'):
                print(json.dumps(value), flush=True)
        rule['progress'] = progress
        tick = time.perf_counter()
        p.initialize_t04(store, binding, scene)
        initialize_wall = time.perf_counter()-tick
        stage = run(store, scene, route_ids=routes, settings=settings, rule=rule)
        if intake.source_inventory() != job['source_files']:
            raise ValueError('T04_PROFILE_EXECUTION_CODE_CHANGED')
        store.verify_reads()
        raw = p.canonical(stage)
        (directory/('construction.json.gz' if group_construction else 't04.json.gz')).write_bytes(gzip.compress(raw, mtime=0))
        receipt = dict(status='GROUP_INTERIORS_CONSTRUCTED; HYBRID_ASSEMBLY_PENDING' if group_construction else 'PASS',
                       algorithm=job.get('algorithm', 'checked-profile'), source_files=job['source_files'], inputs=inputs,
                       scope=rule['scope'], stage_wall_s=time.perf_counter()-started,
                       initialize_wall_s=initialize_wall, stage_sha256=p.digest(raw),
                       output_scene_ref=stage.get('output_scene_ref'),
                       route_count=stage['summary']['routes'],
                       full_board_run=whole_board, replay=False, export=False)
        if group_construction:
            receipt.update(publication_ready=False, native_final_audit='NOT_RUN_BY_DESIGN',
                           summary=stage['summary'], pending=stage['pending'])
            if hybrid_components:receipt['component_status']=stage['hybrid_components']['status']
        else:receipt['source_built_profile']=stage['source_built_profile']
        (directory/'RESULT.json').write_bytes(p.canonical(receipt))
        return receipt
    except Exception as error:
        (directory/'FAILED.json').write_bytes(p.canonical(dict(status='FAIL', error=repr(error),
            traceback=traceback.format_exc(), elapsed_s=time.perf_counter()-started,
            full_board_run=whole_board, replay=False, export=False)))
        raise


def main():
    p.configure()
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    prep = sub.add_parser('prepare')
    prep.add_argument('--accepted-t03', required=True)
    prep.add_argument('--output', required=True)
    prep.add_argument('--algorithm', choices=('checked-profile', 'parallel-groups'), default='checked-profile')
    work = sub.add_parser('run')
    work.add_argument('--job', required=True)
    scope = work.add_mutually_exclusive_group(required=True)
    scope.add_argument('--route-ids')
    scope.add_argument('--whole-board', action='store_true')
    work.add_argument('--qualification')
    group = sub.add_parser('construct-groups', help='Bounded direct group interiors; no completed T04 scene')
    group.add_argument('--job', required=True)
    group.add_argument('--route-ids', required=True)
    group.add_argument('--components',action='store_true',help='Run bounded joint/bulk/residual component diagnostics')
    args = parser.parse_args()
    if args.action == 'prepare':result=prepare(args.accepted_t03, args.output, args.algorithm)
    elif args.action == 'construct-groups':result=execute(args.job, args.route_ids, group_construction=True,hybrid_components=args.components)
    else:result=execute(args.job, args.route_ids, args.qualification, args.whole_board)
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
