#!/usr/bin/env python3
"""Exact retained U03 solver replay with model setup; no native job or export."""
import argparse
import hashlib
import importlib
import json
import platform
import statistics
import sys
import time
import traceback
import types
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path.cwd()
sys.path.insert(0, str(ROOT))
import shapely
from shapely import to_wkb
from src.stage_abi.store import ArtifactStore, canonical, digest


class ReadOnlyStore(ArtifactStore):
    def __init__(self, root): self.root = root
    def put(self, *args, **kwargs): raise AssertionError('RETAINED_STORE_WRITE_FORBIDDEN')
    def _lock(self, *args, **kwargs): raise AssertionError('RETAINED_STORE_WRITE_FORBIDDEN')


def read(path): return json.loads(path.read_bytes())


def run(case, reference, candidate_code, output):
    # Both implementations run with identical shared kernels and retained inputs.
    store = ReadOnlyStore(case / 'runtime')
    admit = read(case / 'u03_t04/t04_admit.json')
    plan = read(case / 'u03_t04/t04_plan.json')
    retained = read(case / 'u03_t04/t04_run.json')['result']['candidate']
    profile = next(iter(admit['registry']['profiles'].values()))
    scene = store.get_json(admit['imported']['scene_ref'], kind='scene')
    policy = store.get_json(profile['policy_ref'], kind='policy')
    expected = [store.get_json(ref, kind='width-check') for ref in retained['check_refs']]
    packages = {}
    for name, directory in (('reference', reference), ('candidate', candidate_code)):
        package = types.ModuleType('route_template_' + name)
        package.__path__ = [str(directory)]
        sys.modules[package.__name__] = package
        packages[name] = tuple(importlib.import_module(package.__name__ + '.' + m) for m in ('width', 'assembly', 'solver'))
    results = []
    for mode in ('reference', 'candidate', 'candidate', 'reference'):
        width, assembly, solver = packages[mode]
        start = time.monotonic()
        rows, current, model, checker, raw, chains, meta, blobs = width.WholeBoardWidthAdapter()._model(store, scene, policy, plan['plan']['details'])
        setup = time.monotonic() - start
        try:
            if mode == 'candidate':
                from src.source_offset_width import construct_source_offset_width
                for sid in sorted(chains):
                    for factor in (1., 1.125, 1.5, retained['solution']['selected_scales'][model.assignment[sid]]):
                        actual = model.construct(sid, factor)
                        original = construct_source_offset_width(raw[sid], chains[sid], meta, blobs, factor)
                        assert actual[0] == original[0], 'CONSTRUCTION_RECORD_CHANGED'
                        assert all(to_wkb(actual[k]) == to_wkb(original[k]) for k in (3, 4, 5)), 'ROUTE_WKB_CHANGED'
                        for k in (1, 2):
                            assert actual[k].keys() == original[k].keys()
                            assert all(to_wkb(actual[k][s]) == to_wkb(original[k][s]) for s in actual[k]), 'PRIMITIVE_WKB_CHANGED'
                sid = min(chains)
                original = dict(chains[sid])
                model.construct(sid, 1.25)
                chains[sid]['component_id'] = 'tampered'
                try:
                    try: model.construct(sid, 1.25)
                    except ValueError as error: assert 'OPERANDS_CHANGED' in str(error)
                    else: raise AssertionError('MUTATION_ACCEPTED')
                finally:
                    chains[sid].clear(); chains[sid].update(original)
                model._construct.cache_clear()
            # Equal baseline priming; candidate-only equivalence controls are untimed.
            model.build(dict.fromkeys(model.group_ids, 1.))
            assembler = assembly.GroupCandidateAssembly(model)
            count = 0
            parity = assembly_time = checking_time = 0.
            def evaluate(vector):
                nonlocal count, parity, assembly_time, checking_time
                start = time.monotonic()
                traces = assembler.traces(vector)
                middle = time.monotonic()
                report = checker.check(traces, fail_fast=True)
                finish = time.monotonic()
                assembly_time += middle - start
                checking_time += finish - middle
                assert report == expected[count], ('REPORT_CHANGED', count)
                assert digest(canonical(report)) == retained['check_refs'][count]['sha256'], ('REPORT_HASH_CHANGED', count)
                count += 1
                parity += time.monotonic() - finish
                return report
            start = time.monotonic()
            solution = solver.solve(model.group_ids, evaluate)
            solver_time = time.monotonic() - start - parity
            assert solution == retained['solution'], 'SOLVER_LEDGER_CHANGED'
            assert count == len(expected), 'CHECK_COVERAGE_CHANGED'
            start = time.monotonic()
            scales = solution['selected_scales']
            traces, records, _, _ = model.build(scales)
            assert records == retained['construction'], 'FINAL_CONSTRUCTION_RECORDS_CHANGED'
            envelope = checker.check(traces, materialize_scene=True)
            nominal = []
            for sid in sorted(chains):
                record, np, ep, core, geometry, _ = model.construct(sid, scales[model.assignment[sid]])
                nominal.append(dict(id=sid, original=core, candidate=geometry, verified_original_width_mm=record['verified_original_width_mm']))
                for member in np:
                    assert digest(to_wkb(np[member])) == retained['parts'][member]['nominal_ref']['sha256']
                    assert digest(to_wkb(ep[member])) == retained['parts'][member]['envelope_ref']['sha256']
            assert envelope == retained['envelope_check'], 'FINAL_ENVELOPE_REPORT_CHANGED'
            assert checker.check(nominal, materialize_scene=True) == retained['nominal_check'], 'FINAL_NOMINAL_REPORT_CHANGED'
            final = time.monotonic() - start
            row = dict(mode=mode, model_setup_seconds=setup, solver_seconds=solver_time, assembly_seconds=assembly_time,
                       checking_seconds=checking_time, final_seconds=final, total_seconds=setup+solver_time+final,
                       evaluations=count, exact_report_hashes_ledger_and_final_parts=True, exact_final_construction_records=True)
            results.append(row)
            print(json.dumps(row), flush=True)
        finally:
            checker.close()
    keys = ('model_setup_seconds', 'solver_seconds', 'assembly_seconds', 'checking_seconds', 'final_seconds', 'total_seconds')
    medians = {m: {k: statistics.median(r[k] for r in results if r['mode'] == m) for k in keys} for m in packages}
    manifest = ROOT / 'contracts/asset_manifest.sha256'
    for line in manifest.read_text().splitlines():
        value, relative = line.split(maxsplit=1)
        assert digest((ROOT / relative.lstrip('*')).read_bytes()) == value, 'ASSET_HASH_CHANGED'
    result = dict(scope='REPLAY; no U03/native jobs, exports, rendering or acceptance changes', case=str(case), results=results, medians=medians,
                  source_files={m: {p.name: digest(p.read_bytes()) for p in sorted(directory.glob('*.py'))} for m, directory in (('reference', reference), ('candidate', candidate_code))},
                  input_files={str(p.relative_to(case)): digest(p.read_bytes()) for p in sorted((case/'u03_t04').glob('t04_*.json'))},
                  scene_ref=admit['imported']['scene_ref'], policy_ref=profile['policy_ref'],
                  versions=dict(python=platform.python_version(), shapely=shapely.__version__, geos=shapely.geos_version_string),
                  asset_manifest_sha256=digest(manifest.read_bytes()),
                  timing_limits='Full model preparation included; retained JSON loading and explicit equivalence controls excluded. Search report equality/hash comparisons excluded from solver time. Final comparisons included. Source-union threads may overlap untimed parity comparisons. Two samples per mode, same machine and process; this is not whole-command timing.')
    with output.open('x') as file: json.dump(result, file, indent=2); file.write('\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', type=Path, required=True)
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--candidate-code', type=Path, default=ROOT/'src/u03_board')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    from tools.pcb_workspace import configure
    work = configure().resolve()
    assert args.output.resolve().is_relative_to(work) and not args.output.exists(), 'FRESH_LACIE_OUTPUT_REQUIRED'
    assert not args.output.resolve().is_relative_to(args.case.resolve()), 'RETAINED_JOB_WRITE_FORBIDDEN'
    manifest = ROOT/'contracts/asset_manifest.sha256'
    for line in manifest.read_text().splitlines():
        value, relative = line.split(maxsplit=1)
        assert digest((ROOT/relative.lstrip('*')).read_bytes()) == value, 'ASSET_HASH_CHANGED'
    try: run(args.case.resolve(), args.reference.resolve(), args.candidate_code.resolve(), args.output.resolve())
    except BaseException as error:
        with args.output.with_suffix('.failure.json').open('x') as file:
            json.dump(dict(error=repr(error), traceback=traceback.format_exc(), scope='Retained replay failed; no U03 job ran'), file, indent=2)
        raise
