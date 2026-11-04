"""Stage A: read-only C03 representation audit and isolated unchanged T05 replay.

This diagnostic is not imported by any operator or treatment module. All writes
are additive under an explicitly supplied, mounted LaCie evidence directory.
"""
from __future__ import annotations

import argparse
from collections import Counter
import cProfile
import hashlib
import json
import os
from pathlib import Path
import platform
import resource
import statistics
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
CONTRACT = ROOT / 'contracts/catalogue/c03_u04_t05_v1.json'


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                      allow_nan=False).encode()


def digest(body):
    return hashlib.sha256(body).hexdigest()


def require(value, reason):
    if not value:
        raise ValueError(reason)


def read(path):
    return json.loads(Path(path).read_bytes())


def write(path, value):
    with Path(path).open('xb') as stream:
        stream.write(canonical(value) + b'\n')


def evidence_dir(path):
    from tools.pcb_workspace import require_storage, WORK
    require_storage()
    p = Path(path)
    require(p.is_absolute() and '..' not in p.parts and p.is_relative_to(WORK),
            'STAGE_A_LACIE_ABSOLUTE_OUTPUT_REQUIRED')
    require(not any(q.is_symlink() for q in (p, *p.parents) if q.is_relative_to(WORK)),
            'STAGE_A_OUTPUT_SYMLINK')
    require(p.is_dir(), 'STAGE_A_EXISTING_EVIDENCE_DIRECTORY_REQUIRED')
    return p


class ReplayStore:
    """Diagnostic I/O meter over unchanged ArtifactStore semantics.

    Retained layers use the existing atomic no-follow SHA-256 reader. Only the
    diagnostic layer may receive puts. No operand bytes or stat result is cached.
    The additional read-only lookup layer is reported as a measurement limitation.
    """
    def __init__(self, output, roots):
        from src.stage_abi.store import ArtifactStore
        from src.u05_board.store import ReadOnlyStore
        self.output = ArtifactStore(output)
        self.readers = [ReadOnlyStore(output), *(ReadOnlyStore(p) for p in roots)]
        self.locations = {}
        self.references = {}
        self.reset()

    def reset(self):
        self.io = Counter()

    def get(self, reference, *, kind=None):
        started = time.perf_counter()
        aid = reference['artifact_id']
        if aid not in self.locations:
            found = [r for r in self.readers if (r.root / 'artifacts' / aid).exists()
                     or (r.root / 'artifacts' / aid).is_symlink()]
            require(found, 'STAGE_A_ARTIFACT_MISSING:' + aid)
            self.locations[aid] = found[0]
        body = self.locations[aid].get(reference, kind=kind)
        self.references[aid] = dict(reference)
        self.io['read_calls'] += 1
        self.io['read_bytes'] += len(body)
        self.io['read_hash_seconds'] += time.perf_counter() - started
        return body

    def get_json(self, reference, *, kind=None):
        return json.loads(self.get(reference, kind=kind))

    def put(self, kind, body):
        started = time.perf_counter()
        result = self.output.put(kind, body)
        self.io['put_calls'] += 1
        self.io['put_payload_bytes'] += len(body)
        self.io['put_seconds'] += time.perf_counter() - started
        return result

    def put_json(self, kind, value):
        from src.stage_abi.store import canonical as stage_canonical
        return self.put(kind, stage_canonical(value))

    def verify_reads(self):
        self.io['verify_read_sweeps'] += 1
        for reference in list(self.references.values()):
            self.get(reference)


def inputs(output):
    cfg = read(output / 'BOUND_INPUTS.json')
    job = Path(cfg['u05_job'])
    start = read(job / 'U05_START.json')
    native = Path(start['predecessor']['root'])
    require(native.parent == Path(cfg['u04_job']), 'STAGE_A_PREDECESSOR_JOB_MISMATCH')
    from src.u05_board.store import ReadOnlyStore
    stores = [ReadOnlyStore(job / 'runtime'), ReadOnlyStore(native / 'runtime')]

    def get(ref):
        for store in stores:
            p = store.root / 'artifacts' / ref['artifact_id']
            if p.exists() or p.is_symlink():
                return store.get(ref)
        raise ValueError('STAGE_A_ARTIFACT_MISSING:' + ref['artifact_id'])

    plan_file = read(job / 'u05_t05/t05_plan.json')
    plan = json.loads(get(plan_file['plan_ref']))
    require(plan == plan_file['plan'], 'STAGE_A_PLAN_CHANGED')
    candidate_file = read(job / 'u05_t05/t05_run.json')
    candidate = json.loads(get(candidate_file['candidate_ref']))
    require(candidate == candidate_file['candidate'], 'STAGE_A_CANDIDATE_CHANGED')
    scene = json.loads(get(plan['scene_ref']))
    policy = json.loads(get(plan['policy_ref']))
    return cfg, job, native, start, get, scene, policy, plan, candidate


def unique(rows, key, reason):
    result = {r[key]: r for r in rows}
    require(len(result) == len(rows), reason)
    return result


def validate_projection(model, expected=None):
    """Validate identity/permission/coverage links, independently of generator success."""
    source = unique(model['source_occurrences'], 'id', 'DUPLICATE_SOURCE_OCCURRENCE')
    objects = unique(model['objects'], 'id', 'DUPLICATE_ENGINEERING_OBJECT')
    paths = unique(model['complete_paths'], 'id', 'DUPLICATE_COMPLETE_PATH')
    groups = unique(model['width_groups'], 'id', 'DUPLICATE_WIDTH_GROUP')
    clusters = unique(model['clusters'], 'id', 'DUPLICATE_CLUSTER')
    attachments = unique(model['attachments'], 'id', 'DUPLICATE_ATTACHMENT')
    partition = [s for r in objects.values() for s in r['native_source_ids']]
    require(len(partition) == len(set(partition)) and set(partition) == set(source),
            'SOURCE_PARTITION_INCOMPLETE_OR_DUPLICATED')
    source_hash = model['source_sha256']
    for sid, row in source.items():
        a, b = row['source_span']
        require(row['source_sha256'] == source_hash and sid == f'{source_hash}:bytes:{a}:{b}'
                and 0 <= a < b, 'SOURCE_OCCURRENCE_REVISION_OR_SPAN')
        require(row['geometry_sha256'] and row['coverage'] == 'GEOMETRY_AVAILABLE',
                'UNQUALIFIED_SOURCE_GEOMETRY')
    path_members = [s for r in paths.values() for s in r['source_ids']]
    traces = {s for s, r in source.items() if r['kind'] in ('segment', 'arc')}
    require(len(path_members) == len(set(path_members)) and set(path_members) == traces,
            'COMPLETE_PATH_SOURCE_COVERAGE')
    for group in groups.values():
        require(group['members'] and all(p in paths for p in group['members']),
                'WIDTH_GROUP_PATH_UNRESOLVED')
    for row in objects.values():
        require(set(row['source_members']) <= source.keys(), 'OBJECT_SOURCE_UNRESOLVED')
        require(set(row['aliases']) <= objects.keys(), 'ALIAS_UNRESOLVED')
        for alias in row['aliases']:
            other = objects[alias]
            require(other['original_ref'] == row['original_ref'] and
                    other['geometry_ref'] == row['geometry_ref'], 'ALIAS_GEOMETRY_CONFLICT')
        require(row['preserve_existing'] is True, 'U04_PRESERVATION_PERMISSION_CHANGED')
        if row['kind'] == 'inclusive_rectangle':
            require(row['source_members'] and row['original_contact_support_ids'] == row['source_members'],
                    'INCLUSIVE_ORIGINAL_SUPPORT_LOST')
        if row['kind'] == 'trace':
            require(not row['native_source_ids'] and row['source_members'],
                    'CLUSTER_VIEW_DUPLICATES_SOURCE_OWNERSHIP')
    for row in clusters.values():
        require(row['id'] in objects and row['parent_path_id'] in paths,
                'CLUSTER_PARENT_UNRESOLVED')
        parent = paths[row['parent_path_id']]
        require(row['complete_parent_source_ids'] == parent['source_ids'] and
                set(row['source_ids']) <= set(parent['source_ids']),
                'CLUSTER_COMPLETE_PARENT_MEMBERSHIP_CHANGED')
        require(all(l in objects and objects[l]['qualified_land'] for l in row['land_ids']),
                'CLUSTER_LAND_UNRESOLVED')
        require(row['attachment_ids'] == [a['id'] for a in model['attachments']
                                        if a['cluster_id'] == row['id']],
                'CLUSTER_ATTACHMENT_MEMBERSHIP_CHANGED')
        require(row['land_ids'] == list(dict.fromkeys(attachments[a]['land_id']
                                                     for a in row['attachment_ids'])),
                'COVERED_OR_DECLARED_LAND_OMITTED')
        require(row['native_width_writable'] is False and row['local_additive_evaluation'] is True,
                'T04_T05_PERMISSION_COUPLING')
    for row in attachments.values():
        require(row['cluster_id'] in clusters and row['land_id'] in objects,
                'ATTACHMENT_ENDPOINT_UNRESOLVED')
        if row['required_reference']:
            require(row['status'] in ('TREATED_VERIFIED', 'ALREADY_SATISFIED_VERIFIED')
                    and row['actual_export_check']['passed'] is True,
                    'REQUIRED_ATTACHMENT_EXTENT_NOT_VERIFIED')
    counts = dict(source_occurrences=len(source), trace_occurrences=len(traces),
                  complete_paths=len(paths), t04_admitted_paths=sum(r['T04_disposition'] ==
                  'ADMIT_COMPLETE_NATIVE_ROUTE' for r in paths.values()), t04_admitted_groups=len(groups),
                  reference_clusters=sum(r['reference_status'] != 'ADDITIONAL' for r in clusters.values()),
                  reference_positive_clusters=sum(r['reference_status'] == 'GROWN' for r in clusters.values()),
                  required_reference_attachments=sum(r['required_reference'] for r in attachments.values()),
                  t05_clusters=len(clusters), attachment_records=len(attachments),
                  outside_write_context_contacts=len(model['context_contacts']),
                  blocked_nonreference_attachments=sum(not r['actual_export_check']['passed']
                                                       for r in attachments.values()))
    if expected is not None:
        require(counts == expected, 'INDEPENDENT_COVERAGE_DENOMINATOR_CHANGED')
    return counts


def audit(output):
    started = time.perf_counter()
    contract = read(CONTRACT)
    cfg, job, native, start, get, scene, policy, plan, candidate = inputs(output)
    manifest = read(native / 'data_board/source_manifest.json')
    native_input = read(native / 'data_board/inputs.json')['inputs']['kicad']
    raw = Path(native_input['path']).read_bytes()
    require(digest(raw) == native_input['sha256'] == scene['source_sha256'] ==
            manifest['source_sha256'], 'SOURCE_REVISION_CHANGED')
    require(digest(Path(start['predecessor']['kicad']).read_bytes()) ==
            start['predecessor']['kicad_sha256'], 'RETAINED_U04_NATIVE_CHANGED')
    require(digest((native / 'U04_RECEIPT.json').read_bytes()) ==
            start['predecessor']['receipt_sha256'], 'RETAINED_U04_RECEIPT_CHANGED')
    prior = read(Path(cfg['prior_evidence']) / 'FINAL_AUDIT.json')
    require(digest((job / 'U05_RECEIPT.json').read_bytes()) == prior['job_receipt_sha256'],
            'RETAINED_U05_RECEIPT_CHANGED')
    frozen = read(Path(cfg['prior_evidence']) / 'SOURCE_FINAL_V2.json')
    for name, h in frozen['files'].items():
        require(digest((ROOT / name).read_bytes()) == h, 'PRODUCER_SOURCE_CHANGED:' + name)
    for name, h in start['reference']['files'].items():
        require(digest((Path(start['reference']['root']) / name).read_bytes()) == h,
                'REFERENCE_INPUT_CHANGED:' + name)
    source = []
    for row in manifest['objects']:
        a, b = row['source_span']
        item = dict(row, source_bytes_sha256=digest(raw[a:b]))
        body = (native / 'data_board/source_wkb' / (row['geometry_sha256'] + '.wkb')).read_bytes()
        require(digest(body) == row['geometry_sha256'], 'SOURCE_GEOMETRY_CHANGED')
        source.append(item)
    objects = []
    clusters = []
    decisions = {d['source_id']: d for d in candidate['decisions']}
    for row in scene['objects']:
        md = row['metadata']
        members = md.get('reference_source_ids', md.get('members', md.get('native_source_ids', [])))
        objects.append(dict(id=row['source_id'], kind=row['kind'], native_source_ids=md['native_source_ids'],
                            source_members=members, aliases=md.get('alias_source_ids', []),
                            original_ref=row['original_ref'], geometry_ref=row['geometry_ref'],
                            qualified_land=bool(md.get('qualified_land')), preserve_existing=True,
                            original_contact_support_ids=md.get('original_contact_support_ids', [])))
        if row['kind'] == 'trace':
            qualification = json.loads(get(md['native_route_ref']))
            require(qualification['source_ids'] == members and
                    qualification['parent_path']['source_ids'] == md['parent_source_ids'],
                    'CLUSTER_SOURCE_QUALIFICATION_CHANGED')
            d = decisions[row['source_id']]
            require(d['land_ids'] == md['land_ids'] and d['attachments'] == md['attachments'],
                    'PLAN_OR_CANDIDATE_MEMBERSHIP_CHANGED')
            clusters.append(dict(id=row['source_id'], reference_id=md['reference_id'],
                                 reference_status=md['reference_status'], source_ids=members,
                                 parent_path_id='route:' + md['parent_path_id'],
                                 complete_parent_source_ids=md['parent_source_ids'],
                                 land_ids=md['land_ids'], attachment_ids=[a['id'] for a in md['attachments']],
                                 T04_disposition=md['T04_disposition'], outcome=d['status'],
                                 selected_scale=d.get('scale'), native_width_writable=False,
                                 local_additive_evaluation=True, qualification_ref=md['native_route_ref']))
    inspect = read(native / 'u03_t04/t04_inspect.json')
    paths = [dict(id='route:' + r['path']['path_id'], source_ids=r['path']['source_ids'],
                  T04_disposition=r['disposition'], complete_path=r['path'])
             for r in inspect['path_records']]
    groups = [dict(id=g['group_id'], members=g['members'])
              for g in read(native / 'u03_t04/t04_plan.json')['plan']['details']['groups']]
    exported = read(job / 'data_output/pcb_gerber_verify.json')['verification']['attachment_coverage']
    attachments = [dict(a, cluster_id=a['source_id']) for a in exported['records']]
    require([a for d in candidate['decisions'] for a in d['attachment_outcomes']] ==
            [{k: a[k] for k in next(d['attachment_outcomes'][0] for d in candidate['decisions']
                                    if d['attachment_outcomes'])} for a in exported['records']],
            'MODEL_EXPORT_ATTACHMENT_LEDGER_CHANGED')
    plan_rows = plan['details']['routes']
    require([r['source_id'] for r in plan_rows] == [r['id'] for r in clusters], 'PLAN_CLUSTER_ORDER_CHANGED')
    context = read(job / 'u05_t05/t05_inspect.json')['facts']['context_contacts']
    model = dict(schema=contract['schema'], source_sha256=scene['source_sha256'],
                 scene_revision=plan['scene_ref']['sha256'], source_occurrences=source,
                 objects=objects, complete_paths=paths, width_groups=groups, clusters=clusters,
                 attachments=attachments, context_contacts=context,
                 parallel_relationships=inspect['relation_records'],
                 frame=dict(id=scene['frame'], units=scene['units'], layer=scene['layer'],
                            export_transform='Gerber X=x, Y=-y; retained export layer coordinates'),
                 source_artifacts=read(native / 'data_board/inputs.json')['inputs'],
                 bindings=dict(u04=start['predecessor'], u05_receipt_sha256=prior['job_receipt_sha256'],
                               scene_ref=plan['scene_ref'], policy_ref=plan['policy_ref'],
                               contract_sha256=digest(CONTRACT.read_bytes()),
                               producer_fingerprint=cfg['producer_fingerprint']))
    counts = validate_projection(model, contract['coverage'])
    # Independently re-read every referenced geometry; the projection stores
    # immutable references, not another anonymous merged copper representation.
    refs = {r[k]['artifact_id']: r[k] for r in scene['objects'] for k in ('geometry_ref', 'original_ref')}
    for ref in refs.values():
        get(ref)
    write(output / 'CATALOGUE.json', model)
    write(output / 'AUDIT.json', dict(status='PASS_STAGE_A_RETAINED_MAPPING', counts=counts,
          scene_objects=len(objects), scene_kinds=dict(Counter(r['kind'] for r in objects)),
          unique_geometry_operands=len(refs), geometry_operand_bytes=sum(len(get(r)) for r in refs.values()),
          parallel_relation_records=len(model['parallel_relationships']),
          catalogue_sha256=digest((output / 'CATALOGUE.json').read_bytes()),
          catalogue_bytes=(output / 'CATALOGUE.json').stat().st_size,
          seconds=time.perf_counter() - started, treatment_changes=0, native_operations=0,
          stage_b='NOT_STARTED', owner='PENDING_USER', independent='NOT_RUN: CHANNEL_UNAVAILABLE',
          electrical_manufacturing='NOT_ESTABLISHED'))


def profile_summary(profile):
    result = []
    categories = Counter()
    for entry in profile.getstats():
        code = entry.code
        if not hasattr(code, 'co_filename'):
            continue
        filename, name = code.co_filename, code.co_name
        key = None
        if '/shapely/' in filename:
            if name == 'from_wkb': key = 'wkb_decodes'
            elif name == 'to_wkb': key = 'wkb_serializations'
            elif name == 'query' and 'strtree' in filename: key = 'spatial_queries'
            elif name == '__init__' and 'strtree' in filename: key = 'spatial_index_builds'
            elif name in ('intersection', 'difference', 'union', 'union_all', 'symmetric_difference', 'buffer') and Path(filename).name in ('set_operations.py', 'constructive.py'):
                key = 'geometry_constructions'
            elif name in ('distance', 'intersects', 'covers', 'contains', 'equals', 'within') and Path(filename).name in ('predicates.py', 'measurement.py'):
                key = 'geometry_predicates_and_distances'
        elif filename.endswith('/src/stage_abi/store.py') and name == 'canonical':
            key = 'canonical_serializations'
        if key:
            categories[key] += entry.callcount
            result.append(dict(category=key, function=name, file=filename, calls=entry.callcount,
                               self_seconds=entry.inlinetime, cumulative_seconds=entry.totaltime))
    return dict(counts=dict(categories), functions=result,
                time_note='Cumulative function times overlap and must not be summed')


def measure_worker(output, number, profiled):
    from shapely import from_wkb, __version__ as shapely_version, geos_version_string
    from shapely.geometry import box
    from src.u05_board.coverage import CoverageAdapter
    from src.u03_board.selection import for_root, window
    cfg, job, native, start, get, scene, policy, plan, candidate = inputs(output)
    profile_cfg = read(ROOT / 'contracts/operator/u05_attachment_profile.json')
    exceptions = {}
    if profile_cfg.get('scope_exception'):
        ex = profile_cfg['scope_exception']
        blob = (ROOT / ex['path']).read_bytes()
        require(digest(blob) == ex['sha256'], 'SCOPE_EXCEPTION_CHANGED')
        exceptions[ex['reference_id']] = from_wkb(blob)
    selection = for_root(native)
    store = ReplayStore(output / f'replay_{number:02d}' / 'runtime',
                        [job / 'runtime', native / 'runtime'])
    adapter = CoverageAdapter(window(selection) if selection else box(*scene['viewport_mm']), exceptions)
    require(adapter.describe()['implementation'] == plan['implementation'], 'REPLAY_IMPLEMENTATION_CHANGED')
    rows = []
    for state in ('cold_context', 'warm_context'):
        for operation in ('run', 'verify'):
            store.reset()
            profiler = cProfile.Profile() if profiled else None
            started = time.perf_counter()
            if profiler:
                profiler.enable()
            if operation == 'run':
                result = adapter.run(store, scene, policy, plan, lambda value: None)
            else:
                result = adapter.verify(store, scene, policy, plan, candidate,
                                        {'scope': 'complete-source-and-all-patches'}, lambda value: None)
            if profiler:
                profiler.disable()
            elapsed = time.perf_counter() - started
            if operation == 'run':
                expected = {k: v for k, v in candidate.items()
                            if k not in ('plan_ref', 'scene_ref', 'policy_ref', 'profile_id')}
                require(result == expected, 'REPLAY_FULL_CANDIDATE_MISMATCH')
            else:
                expected = read(job / 'u05_t05/t05_verify.json')['check']
                require(result == expected, 'REPLAY_VERIFICATION_MISMATCH')
            row = dict(state=state, operation=operation, elapsed_seconds=elapsed,
                       io=dict(store.io), result_sha256=digest(canonical(result)),
                       exact_retained_result_match=True,
                       process_peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss *
                       (1 if sys.platform == 'darwin' else 1024))
            if profiler:
                row['profile'] = profile_summary(profiler)
                profiler.dump_stats(str(output / f'profile_{number:02d}_{state}_{operation}.pstats'))
            rows.append(row)
            write(output / f'sample_{number:02d}_{state}_{operation}.json', row)
            print(json.dumps(dict(sample=number, state=state, operation=operation,
                                  seconds=round(elapsed, 3), exact_match=True)), flush=True)
    write(output / f'worker_{number:02d}.json', dict(profiled=profiled, rows=rows,
          python=platform.python_version(), shapely=shapely_version, geos=geos_version_string))


def baseline(output, repeats):
    require(repeats >= 3, 'THREE_UNPROFILED_REPETITIONS_REQUIRED')
    for number in range(repeats + 1):
        cmd = [sys.executable, '-B', str(Path(__file__).resolve()), 'worker', '--output', str(output),
               '--number', str(number)]
        if number == repeats:
            cmd.append('--profile')
        env = dict(os.environ, TMPDIR=str(output), PYTHONDONTWRITEBYTECODE='1')
        subprocess.run(cmd, cwd=ROOT, env=env, check=True)
    workers = [read(output / f'worker_{n:02d}.json') for n in range(repeats + 1)]
    summary = {}
    for state in ('cold_context', 'warm_context'):
        for op in ('run', 'verify'):
            samples = [r for w in workers if not w['profiled'] for r in w['rows']
                       if r['state'] == state and r['operation'] == op]
            values = [r['elapsed_seconds'] for r in samples]
            summary[state + '_' + op] = dict(samples=len(values), median_seconds=statistics.median(values),
                  minimum_seconds=min(values), maximum_seconds=max(values),
                  peak_rss_bytes=max(r['process_peak_rss_bytes'] for r in samples),
                  io_samples=[r['io'] for r in samples])
    receipt = read(Path(read(output / 'BOUND_INPUTS.json')['u05_job']) / 'U05_RECEIPT.json')
    write(output / 'BASELINE.json', dict(status='PASS_EXACT_RETAINED_REPLAY_BASELINE',
          qualification='REPLAY_NOT_FRESH_NATIVE_QUALIFICATION', summary=summary,
          workers=workers, retained_managed_u05_performance=receipt['performance'],
          retained_u04_prefix='43 gates RETAINED_VERIFIED_NOT_REEXECUTED',
          limits=['Cold means new process and adapter context; OS/filesystem caches were not flushed',
                  'run initializes the cold context; the following verify shares it',
                  'profiled samples are separate and excluded from latency medians',
                  'ReplayStore adds diagnostic counters and a retained lookup layer; not operator wall time',
                  'RSS is process high-water memory including input load, not a per-operation allocation delta',
                  'No fresh native export, machine-gate execution or whole-board timing'],
          stage_b='NOT_STARTED'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['audit', 'baseline', 'worker'])
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--repeats', default=3, type=int)
    parser.add_argument('--number', type=int, default=0)
    parser.add_argument('--profile', action='store_true')
    args = parser.parse_args()
    output = evidence_dir(args.output)
    if args.mode == 'audit':
        audit(output)
    elif args.mode == 'baseline':
        baseline(output, args.repeats)
    else:
        measure_worker(output, args.number, args.profile)


if __name__ == '__main__':
    main()
