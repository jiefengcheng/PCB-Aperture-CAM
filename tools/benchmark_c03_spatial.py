"""Stage C spatial candidates versus frozen Stage B; bounded replay, never a job."""
import argparse
import copy
import cProfile
import importlib.util
import json
import os
from pathlib import Path
import resource
import statistics
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.c03_catalogue_stage_a import (ReplayStore, canonical, digest, evidence_dir,
                                         inputs, profile_summary, read, require, write)


def frozen_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def worker(output, variant, number, profiled=False):
    verify_assets()
    from shapely import from_wkb
    from shapely.geometry import box
    from src.u03_board.selection import for_root, window
    cfg, job, native, start, get, scene, policy, old_plan, old_candidate = inputs(output)
    protocol = read(output / 'PROTOCOL.json')
    for name, h in protocol['reference_sources'].items():
        require(digest((output / 'reference' / name).read_bytes()) == h, 'REFERENCE_SOURCE_CHANGED')
    for name, h in read(output / 'CANDIDATE_SOURCES.json').items():
        require(digest((ROOT / name).read_bytes()) == h, 'CANDIDATE_SOURCE_CHANGED')
    if variant == 'reference':
        blend = frozen_module('stage_b_frozen_blend', output / 'reference/src/junction_spindle_blend.py')
        module = frozen_module('src.u05_board._stage_b_frozen_coverage', output / 'reference/src/u05_board/coverage.py')
        module.spindle_blend = blend.spindle_blend
        module.check_spindle = blend.check_spindle
        Adapter = module.CoverageAdapter
        plan = copy.deepcopy(old_plan)
    else:
        from src.u05_board.coverage import CoverageAdapter as Adapter
        plan = copy.deepcopy(old_plan)
    selection = for_root(native)
    profile = read(ROOT / 'contracts/operator/u05_attachment_profile.json')
    exceptions = {}
    if profile.get('scope_exception'):
        item = profile['scope_exception']
        body = (ROOT / item['path']).read_bytes()
        require(digest(body) == item['sha256'], 'SCOPE_EXCEPTION_CHANGED')
        exceptions[item['reference_id']] = from_wkb(body)
    adapter = Adapter(window(selection) if selection else box(*scene['viewport_mm']), exceptions)
    plan['implementation'] = adapter.describe()['implementation']
    if variant == 'reference':
        require(plan['implementation'] == read(Path(protocol['stage_b']) / 'STAGE_B_RECEIPT.json')['implementation'], 'STAGE_B_IMPLEMENTATION_MISMATCH')
    require(plan['implementation'] != old_plan['implementation'], 'NEW_IMPLEMENTATION_BINDING_REQUIRED')
    store = ReplayStore(output / f'{variant}_{number:02d}' / 'runtime',
                        [job / 'runtime', native / 'runtime'])
    plan_ref = store.put_json('plan', plan)
    samples = []
    last_candidate = None
    for state in ('cold_context', 'warm_context'):
        for operation in ('run', 'verify'):
            store.reset()
            profiler = cProfile.Profile() if profiled else None
            if profiler:
                profiler.enable()
            begin = time.perf_counter()
            if operation == 'run':
                result = adapter.run(store, scene, policy, plan, lambda _: None)
            else:
                result = adapter.verify(store, scene, policy, plan, last_candidate,
                                        {'scope': 'complete-source-and-all-patches'}, lambda _: None)
            elapsed = time.perf_counter() - begin
            if profiler:
                profiler.disable()
            rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1 if sys.platform == 'darwin' else 1024)
            if operation == 'run':
                old = {k: v for k, v in old_candidate.items()
                       if k not in ('plan_ref', 'scene_ref', 'policy_ref', 'profile_id', 'output_scene_ref')}
                require({k: v for k, v in result.items() if k != 'output_scene_ref'} == old,
                        'DECISIONS_WITNESSES_GEOMETRY_OR_COVERAGE_MISMATCH')
                last_candidate = dict(result, plan_ref=plan_ref, scene_ref=plan['scene_ref'],
                                      policy_ref=plan['policy_ref'], profile_id=plan['profile_id'])
            else:
                require(result == read(job / 'u05_t05/t05_verify.json')['check'], 'VERIFICATION_MISMATCH')
            sample = dict(variant=variant, number=number, state=state, operation=operation,
                          elapsed_seconds=elapsed, process_peak_rss_bytes=rss, io=dict(store.io),
                          exact_decisions_witnesses_geometry_and_outcomes=True)
            if hasattr(adapter, 'last_execution_statistics'):
                sample['geometry_service'] = adapter.last_execution_statistics
                require(adapter._geometry is None, 'OPERATION_CACHE_NOT_RELEASED')
            if profiler:
                sample['profile'] = profile_summary(profiler)
                profiler.dump_stats(str(output / f'{variant}_{number:02d}_{state}_{operation}.pstats'))
            samples.append(sample)
            write(output / f'{variant}_{number:02d}_{state}_{operation}.json', sample)
            print(json.dumps(dict(variant=variant, sample=number, state=state,
                                  operation=operation, seconds=round(elapsed, 3), rss_bytes=rss)), flush=True)
    # Complete structural parity is checked after the timed/RSS samples so that
    # parsing the two evidence scenes cannot inflate a later measured sample.
    original_output = json.loads(get(old_candidate['output_scene_ref']))
    current_output = store.get_json(last_candidate['output_scene_ref'], kind='scene')
    require({k: v for k, v in current_output.items() if k != 'lineage'} ==
            {k: v for k, v in original_output.items() if k != 'lineage'}, 'OUTPUT_SCENE_CONTENT_CHANGED')
    expected_lineage = copy.deepcopy(original_output['lineage'])
    expected_lineage[-1].update(implementation=plan['implementation'], plan_ref=plan_ref)
    require(current_output['lineage'] == expected_lineage, 'UNEXPLAINED_LINEAGE_CHANGE')
    close = getattr(adapter, 'close', None)
    if close:
        close()
        require(adapter._snapshot is None and adapter._geometry is None, 'GEOMETRY_SERVICE_NOT_RELEASED')
    write(output / f'{variant}_{number:02d}.json', dict(profiled=profiled, samples=samples,
          complete_output_scene_parity=True, allowed_difference='New implementation and plan lineage only',
          implementation=plan['implementation'], qualification='REPLAY_NOT_FRESH_NATIVE_QUALIFICATION'))


def verify_assets():
    rows = (ROOT / 'contracts/asset_manifest.sha256').read_text().splitlines()
    for row in rows:
        expected, name = row.split(None, 1)
        require(digest((ROOT / name.strip()).read_bytes()) == expected, 'IMMUTABLE_ASSET_CHANGED')
    return len(rows)


def spatial_worker(output, variant, number):
    """Actual C03 additions and rollback, not treatment or permission updates."""
    verify_assets()
    from shapely import STRtree, from_wkb, to_wkb
    from shapely.geometry import Polygon
    from src.stage_abi.spatial_queries import SpatialQueries
    from src.junction_spindle_stage import CONTRACT, prepare_spindle_context
    _, _, _, _, get, scene, _, plan, candidate = inputs(output)
    current = {r['source_id']: from_wkb(get(r['geometry_ref'])) for r in scene['objects']}
    original = {r['source_id']: current[r['source_id']] for r in scene['objects'] if r['kind'] != 'trace'}
    from shapely.geometry import box
    crop = box(*scene['viewport_mm'])
    queries = [prepare_spindle_context(current[r['source_id']], [current[s] for s in r['land_ids']], crop)[2].buffer(CONTRACT.barrier_gap_mm)
               for r in plan['details']['routes'] if r['land_ids']]
    updates = []
    for i, row in enumerate(d for d in candidate['decisions'] if d['status'] == 'GROWN'):
        sid, g = 't05:' + row['source_id'], from_wkb(get(row['patch_ref']))
        updates.append((sid, g))
        if i % 4 == 0:updates.extend([(sid, None), (sid, g)])
    workload = digest(canonical(dict(source=scene['source_sha256'],
        originals=[(s, digest(to_wkb(g))) for s, g in sorted(original.items())],
        queries=[digest(to_wkb(g)) for g in queries],
        updates=[(s, None if g is None else digest(to_wkb(g))) for s, g in updates])))
    # Retain all source/member/query bindings outside timing. No cache state or
    # expected answer from the reference is supplied to candidate execution.
    begin = time.perf_counter()
    shapes = dict(original)
    answers = []
    if variant == 'candidate':service = SpatialQueries(shapes, context=workload)
    else:
        ids = sorted(shapes);tree = STRtree([shapes[s] for s in ids])
    for sid, value in [(None, None), *updates]:
        if sid is not None:
            if value is None:shapes.pop(sid, None)
            else:shapes[sid] = value
            if variant == 'candidate':service.update(sid, value)
            else:
                ids = sorted(shapes);tree = STRtree([shapes[s] for s in ids])
        for query in queries:
            answer = service.query(query) if variant == 'candidate' else tuple(ids[int(i)] for i in sorted(tree.query(query)))
            answers.append(answer)
    elapsed = time.perf_counter() - begin
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1 if sys.platform == 'darwin' else 1024)
    record = dict(variant=variant, number=number, workload_sha256=workload,
                  elapsed_seconds=elapsed, peak_rss_bytes=rss, queries=len(answers),
                  source_records=len(original), transitions=len(updates),
                  answers_sha256=digest(canonical(answers)),
                  qualification='SPATIAL_REPLAY_ONLY_NO_NEW_TREATMENT_OR_NATIVE_QUALIFICATION')
    if variant == 'candidate':
        record['service'] = service.diagnostics()
        service.close()
    write(output / f'spatial_{variant}_{number:02d}.json', record)
    print(json.dumps({k:v for k,v in record.items() if k != 'service'}), flush=True)


def benchmark(output, repeats):
    require(repeats >= 3, 'THREE_PAIRED_REPETITIONS_REQUIRED')
    for number in range(repeats):
        order = ('reference', 'candidate') if number % 2 == 0 else ('candidate', 'reference')
        for variant in order:
            for mode in ('worker', 'spatial'):
                subprocess.run([sys.executable, '-B', __file__, mode, '--output', str(output),
                    '--variant', variant, '--number', str(number)], cwd=ROOT, check=True,
                    env=dict(os.environ, TMPDIR=str(output), PYTHONDONTWRITEBYTECODE='1'))
    for variant in ('reference', 'candidate'):
        subprocess.run([sys.executable, '-B', __file__, 'worker', '--output', str(output),
                    '--variant', variant, '--number', str(repeats), '--profile'], cwd=ROOT, check=True,
                    env=dict(os.environ, TMPDIR=str(output), PYTHONDONTWRITEBYTECODE='1'))
    workers = {v:[read(output / f'{v}_{i:02d}.json') for i in range(repeats)] for v in ('reference', 'candidate')}
    spatial = {v:[read(output / f'spatial_{v}_{i:02d}.json') for i in range(repeats)] for v in workers}
    require(len({r['answers_sha256'] for rows in spatial.values() for r in rows}) == 1, 'DYNAMIC_NEIGHBORHOODS_MISMATCH')
    require(len({r['workload_sha256'] for rows in spatial.values() for r in rows}) == 1, 'DYNAMIC_WORKLOAD_MISMATCH')
    protocol = read(output / 'PROTOCOL.json')
    b = read(Path(protocol['stage_b']) / 'FINAL_BENCHMARK.json')['summary']
    summary = {}
    for state in ('cold_context', 'warm_context'):
        record = {}
        for variant in workers:
            times = [sum(s['elapsed_seconds'] for s in w['samples'] if s['state'] == state) for w in workers[variant]]
            record[variant] = dict(median_seconds=statistics.median(times), range_seconds=[min(times), max(times)])
        c, r = record['candidate']['median_seconds'], record['reference']['median_seconds']
        summary[state] = dict(record, retained_stage_b_seconds=b[state]['median_pair_seconds'],
            change_vs_fresh_stage_b=c/r-1, change_vs_retained_stage_b=c/b[state]['median_pair_seconds']-1,
            no_regression_target_met=c/r-1 <= protocol['targets']['maximum_pair_time_regression_fraction'])
    peaks = {v:max(s['process_peak_rss_bytes'] for w in workers[v] for s in w['samples']) for v in workers}
    summary['memory'] = dict(peaks, retained_stage_b_bytes=b['rss']['candidate_peak_bytes'],
                            no_regression_target_met=peaks['candidate']/peaks['reference']-1 <= protocol['targets']['maximum_rss_regression_fraction'])
    times = {v:statistics.median(r['elapsed_seconds'] for r in spatial[v]) for v in workers}
    improvement = 1-times['candidate']/times['reference']
    summary['dynamic_spatial'] = dict(times, improvement_fraction=improvement,
                                    target_met=improvement >= protocol['targets']['spatial_update_improvement_fraction'])
    targets = all(summary[k]['no_regression_target_met'] for k in ('cold_context', 'warm_context', 'memory')) and summary['dynamic_spatial']['target_met']
    write(output / 'BENCHMARK.json', dict(status='PASS_PARITY_AND_BOUNDED_TARGETS' if targets else 'PARITY_PASS_PERFORMANCE_TARGET_NOT_MET',
        summary=summary, workers=workers, spatial=spatial, profiles={v:read(output/f'{v}_{repeats:02d}.json') for v in workers},
        historical_custody=protocol['historical_custody'], t04='DEFERRED_UNCHANGED', qualification='BOUNDED_REPLAY_NOT_NATIVE_QUALIFICATION'))


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('mode', choices=['worker', 'benchmark', 'spatial'])
    ap.add_argument('--output', required=True, type=Path)
    ap.add_argument('--variant', choices=['reference', 'candidate'], default='candidate')
    ap.add_argument('--number', type=int, default=0)
    ap.add_argument('--profile', action='store_true')
    ap.add_argument('--repeats', type=int, default=3)
    args = ap.parse_args()
    out = evidence_dir(args.output)
    if args.mode == 'worker': worker(out, args.variant, args.number, args.profile)
    elif args.mode == 'spatial': spatial_worker(out, args.variant, args.number)
    else: benchmark(out, args.repeats)
