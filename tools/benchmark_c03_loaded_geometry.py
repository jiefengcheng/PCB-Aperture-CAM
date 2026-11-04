"""Paired Stage A reference / Stage B geometry-reuse diagnostic, never a job."""
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
    from shapely import from_wkb
    from shapely.geometry import box
    from src.u03_board.selection import for_root, window
    cfg, job, native, start, get, scene, policy, old_plan, old_candidate = inputs(output)
    protocol = read(output / 'PROTOCOL.json')
    for name, h in protocol['reference_sources'].items():
        require(digest((output / 'reference' / name).read_bytes()) == h, 'REFERENCE_SOURCE_CHANGED')
    if variant == 'reference':
        blend = frozen_module('stage_b_frozen_blend', output / 'reference/src/junction_spindle_blend.py')
        module = frozen_module('src.u05_board._stage_b_frozen_coverage', output / 'reference/src/u05_board/coverage.py')
        module.spindle_blend = blend.spindle_blend
        module.check_spindle = blend.check_spindle
        Adapter = module.CoverageAdapter
        plan = old_plan
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
    if variant == 'candidate':
        plan['implementation'] = adapter.describe()['implementation']
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
                if variant == 'reference':
                    require(result['output_scene_ref'] == old_candidate['output_scene_ref'],
                            'FROZEN_REFERENCE_OUTPUT_SCENE_CHANGED')
            else:
                require(result == read(job / 'u05_t05/t05_verify.json')['check'], 'VERIFICATION_MISMATCH')
            sample = dict(variant=variant, number=number, state=state, operation=operation,
                          elapsed_seconds=elapsed, process_peak_rss_bytes=rss, io=dict(store.io),
                          exact_decisions_witnesses_geometry_and_outcomes=True)
            if variant == 'candidate':
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


def benchmark(output, repeats):
    require(repeats >= 3, 'THREE_PAIRED_REPETITIONS_REQUIRED')
    for number in range(repeats):
        order = ('reference', 'candidate') if number % 2 == 0 else ('candidate', 'reference')
        for variant in order:
            subprocess.run([sys.executable, '-B', __file__, 'worker', '--output', str(output),
                            '--variant', variant, '--number', str(number)], cwd=ROOT, check=True,
                           env=dict(os.environ, TMPDIR=str(output), PYTHONDONTWRITEBYTECODE='1'))
    subprocess.run([sys.executable, '-B', __file__, 'worker', '--output', str(output),
                    '--variant', 'candidate', '--number', str(repeats), '--profile'], cwd=ROOT, check=True,
                   env=dict(os.environ, TMPDIR=str(output), PYTHONDONTWRITEBYTECODE='1'))
    workers = [read(output / f'{variant}_{i:02d}.json') for i in range(repeats)
               for variant in ('reference', 'candidate')]
    summary = {}
    for variant in ('reference', 'candidate'):
        selected = [w for w in workers if w['samples'][0]['variant'] == variant]
        for state in ('cold_context', 'warm_context'):
            pairs = [sum(r['elapsed_seconds'] for r in w['samples'] if r['state'] == state) for w in selected]
            summary[variant + '_' + state] = dict(median_pair_seconds=statistics.median(pairs),
                   minimum_pair_seconds=min(pairs), maximum_pair_seconds=max(pairs))
        summary[variant + '_peak_rss_bytes'] = max(r['process_peak_rss_bytes'] for w in selected for r in w['samples'])
    protocol = read(output / 'PROTOCOL.json')
    stage_a = read(Path(protocol['stage_a']) / 'BASELINE.json')
    stage_a_pairs = read(Path(protocol['stage_a']) / 'PAIR_TIMINGS.json')
    comparisons = {}
    target = protocol['targets']['pair_median_improvement_fraction']
    for state in ('cold_context', 'warm_context'):
        c = summary['candidate_' + state]['median_pair_seconds']
        r = summary['reference_' + state]['median_pair_seconds']
        a = stage_a_pairs[state]['median_seconds']
        comparisons[state] = dict(candidate_vs_fresh_reference=1-c/r,
                                  candidate_vs_stage_a=1-c/a,
                                  target_met=(1-c/r >= target and 1-c/a >= target))
    stage_a_rss = max(r['peak_rss_bytes'] for r in stage_a['summary'].values())
    c = summary['candidate_peak_rss_bytes']; r = summary['reference_peak_rss_bytes']
    mem_target = protocol['targets']['peak_process_rss_improvement_fraction']
    comparisons['peak_rss'] = dict(candidate_vs_fresh_reference=1-c/r,
                                   candidate_vs_stage_a=1-c/stage_a_rss,
                                   target_met=(1-c/r >= mem_target and 1-c/stage_a_rss >= mem_target))
    write(output / 'BENCHMARK.json', dict(status='PASS_TARGETS' if all(x['target_met'] for x in comparisons.values())
          else 'PARITY_PASS_PERFORMANCE_TARGET_NOT_MET', summary=summary, comparisons=comparisons,
          workers=workers, profiled_candidate=read(output / f'candidate_{repeats:02d}.json'),
          qualification='BOUNDED_REPLAY_NOT_FRESH_NATIVE_QUALIFICATION',
          historical_custody=protocol['historical_custody']))


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('mode', choices=['worker', 'benchmark'])
    ap.add_argument('--output', required=True, type=Path)
    ap.add_argument('--variant', choices=['reference', 'candidate'], default='candidate')
    ap.add_argument('--number', type=int, default=0)
    ap.add_argument('--profile', action='store_true')
    ap.add_argument('--repeats', type=int, default=3)
    args = ap.parse_args()
    out = evidence_dir(args.output)
    if args.mode == 'worker': worker(out, args.variant, args.number, args.profile)
    else: benchmark(out, args.repeats)
