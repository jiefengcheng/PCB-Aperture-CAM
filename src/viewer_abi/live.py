"""Explicit completed-slice queue. Reads engineering artifacts; writes viewer state only."""
from pathlib import Path
import json
import math
import os
import time
import uuid
from shapely import from_wkb
from .publisher import encode, digest, path_data, bounds, atomic_write, read_current


def read_bound(path, expected):
    data = Path(path).read_bytes()
    if digest(data) != expected:
        raise ValueError('LIVE_INPUT_CHANGED:' + str(path))
    return data


def load_connection(root):
    return json.loads((Path(root) / 'connection.json').read_bytes())


def display(shape):
    if shape.is_empty:
        return None, 0.
    if not shape.is_valid or shape.area <= 0:
        raise ValueError('LIVE_INVALID_AREA_GEOMETRY')
    tolerance = .00025
    for _ in range(8):
        result = shape.simplify(tolerance, preserve_topology=True)
        error = shape.hausdorff_distance(result)
        if error <= .000500001:
            return result, error
        tolerance /= 2
    raise ValueError('LIVE_DISPLAY_ERROR_LIMIT')


def area_bounds(objects):
    if not objects:
        raise ValueError('LIVE_EMPTY_SCENE')
    b = [o['bounds'] for o in objects]
    x = min(v['x'] for v in b); y = min(v['y'] for v in b)
    return dict(x=x, y=y, width=max(v['x']+v['width'] for v in b)-x,
                height=max(v['y']+v['height'] for v in b)-y)


def sealed_file(path):
    path = Path(path).resolve()
    return dict(path=str(path), sha256=digest(path.read_bytes()))


def artifact_reader(legacy):
    def read(ref):
        sha = ref['sha256']
        if len(sha) != 64 or any(c not in '0123456789abcdef' for c in sha):
            raise ValueError('LIVE_INVALID_ARTIFACT')
        folder = Path(legacy) / 'runtime/artifacts'
        p = folder / ref['artifact_id']
        if p.resolve().parent != folder.resolve():
            raise ValueError('LIVE_ARTIFACT_ESCAPE')
        return read_bound(p, sha)
    return read


def construction_map(stage, config):
    binding = stage['input_binding']
    source_only = config.get('context') == 'original'
    wrong_context = ((binding.get('context') != 'original' or binding.get('accepted_t03') is not False or
                      binding.get('original_scene_ref') != config['scene_ref'] or 't03_sha256' in binding)
                     if source_only else binding.get('t03_sha256') != config['t03_sha256'])
    if (binding.get('source_sha256') != config['source_sha256'] or wrong_context or
            binding.get('scene_ref') != config['scene_ref']):
        raise ValueError('LIVE_CONSTRUCTION_LINEAGE_MISMATCH')
    h = stage['hybrid_components']
    result = dict(h['continuous_source_bodies'])
    result.update(h['changed_bulk_copper'])
    return {sid: record['wkb_hex'] for sid, record in result.items()}


def initialize(root, *, template, legacy, construction, thread, context='retained_t03'):
    import gzip
    root = Path(root)
    if root.exists():
        raise FileExistsError('LIVE_CONNECTION_ALREADY_EXISTS')
    if context not in ('retained_t03', 'original'):
        raise ValueError('LIVE_UNSUPPORTED_SOURCE_CONTEXT')
    template_raw = Path(template).read_bytes(); snapshot = json.loads(template_raw)
    source_raw = (Path(legacy) / 'source.json').read_bytes()
    source = json.loads(source_raw)
    read = artifact_reader(legacy)
    raw = read(source['source_ref']); source_sha = digest(raw)
    if context == 'original':
        scene_ref = source['scene_ref']
        scene = json.loads(read(scene_ref))
        if ([r.get('stage') for r in scene.get('lineage', [])] != ['gerber-source-intake'] or
                any(row['geometry_ref'] != row.get('original_ref') for row in scene['objects'])):
            raise ValueError('LIVE_ORIGINAL_SOURCE_SCENE_REQUIRED')
    else:
        t03_raw = (Path(legacy) / 't03.json').read_bytes()
        t03 = json.loads(t03_raw); scene_ref = t03['output_scene_ref']
        scene = json.loads(read(scene_ref))
    if (scene['source_sha256'] != source_sha or {s['sha256'] for s in snapshot['sources']} != {source_sha} or
            {o['id'] for o in snapshot['objects']} != {r['source_id'] for r in scene['objects']}):
        raise ValueError('LIVE_TEMPLATE_SOURCE_MISMATCH')
    config = dict(schema=1, connection_id=uuid.uuid4().hex, thread=thread, require_display_ack=True,
                  source_sha256=source_sha, scene_ref=scene_ref,
                  legacy=str(Path(legacy).resolve()), template=dict(path=str(Path(template).resolve()), sha256=digest(template_raw)),
                  construction=sealed_file(construction))
    if context == 'original':
        config.update(context='original', source_binding_sha256=digest(source_raw))
        # Rebuild every baseline object from original source bytes: a retained
        # template may contain T01-grown lands, even outside this bounded case.
        by_id = {o['id']: o for o in snapshot['objects']}
        for row in scene['objects']:
            shape, _ = display(from_wkb(read(row['geometry_ref'])))
            by_id[row['source_id']] = dict(by_id[row['source_id']], path=path_data(shape), bounds=bounds(shape))
        snapshot = dict(snapshot, objects=list(by_id.values()))
        template_raw = encode(snapshot)
        config['template'] = dict(path=str(root.resolve()/'source-template.json'), sha256=digest(template_raw))
    else:
        config['t03_sha256'] = digest(t03_raw)
    # Bind exact unsimplified WKB identities, separate from display derivatives.
    fingerprints = {row['source_id']: digest(read(row['geometry_ref'])) for row in scene['objects']}
    changes = construction_map(json.loads(gzip.decompress(read_bound(config['construction']['path'], config['construction']['sha256']))), config)
    objects = {o['id']: o for o in snapshot['objects']}
    template_objects = dict(objects)
    error = 0.
    for sid, hex_wkb in changes.items():
        if sid not in objects:
            raise ValueError('LIVE_UNKNOWN_SOURCE_ID')
        data = bytes.fromhex(hex_wkb); fingerprints[sid] = digest(data)
        shape, e = display(from_wkb(data)); error = max(error, e)
        if shape is None:
            del objects[sid]
        else:
            objects[sid] = dict(objects[sid], path=path_data(shape), bounds=bounds(shape))
    snapshot.update(job='live-t04-' + config['connection_id'], revision=uuid.uuid4().hex, parentRevision=None,
                    slice='T04 directly on original source · bounded diagnostic' if context == 'original' else 'T04 connected · retained diagnostic context', status='Preview', objects=list(objects.values()),
                    bounds=area_bounds(list(objects.values())), affected=area_bounds(list(objects.values())),
                    limitations=['Original-source bounded T04 only; no T01/T02/T03/T05 execution or full-board result.' if context == 'original' else 'Live viewer connection; retained diagnostic baseline, not completed T04.',
                                 'Display-only derivatives; maximum new-body Hausdorff error mm: ' + str(error),
                                 'Producer-reported completion and qualifications remain separate from viewer delivery.',
                                 'Client artwork stack identity NOT_ESTABLISHED; no inferred net intent.'],
                    evidence=[config['construction']['path']])
    root.mkdir(parents=True)
    if context == 'original':
        (root/'source-template.json').write_bytes(template_raw)
    for name in ['queue', 'receipts', 'feedback', 'session/snapshots']:
        (root / name).mkdir(parents=True)
    (root / 'connection.json').write_bytes(encode(config))
    (root / 'base-fingerprints.json').write_bytes(encode(fingerprints))
    (root / 'templates.json').write_bytes(encode(template_objects))
    save_revision(root, snapshot, fingerprints, event='initial')
    return config


def save_revision(root, snapshot, fingerprints, *, event):
    """Immutable payload/state first; atomic manifest is the authoritative commit point."""
    root = Path(root); session = root / 'session'
    previous_manifest, previous = read_current(session)
    snapshot['revision'] = uuid.uuid4().hex
    snapshot['parentRevision'] = previous['revision'] if previous else None
    data = encode(snapshot)
    if len(data) > 128*1024*1024:
        raise ValueError('LIVE_PAYLOAD_RESOURCE_LIMIT')
    h = digest(data)
    target = session / 'snapshots' / (h + '.json')
    with target.open('xb') as stream:
        stream.write(data); stream.flush(); os.fsync(stream.fileno())
    # Revision-bound state lets a restarted watcher recover exactly what was published.
    state = dict(revision=snapshot['revision'], event=event, fingerprints=fingerprints,
                 parent_sha256=previous_manifest['sha256'] if previous_manifest else None,
                 parent_state_sha256=previous_manifest['producerStateSHA256'] if previous_manifest else None)
    state_data = encode(state)
    (root / 'receipts' / (h + '.state.json')).write_bytes(state_data)
    manifest = dict(schema=1, payload=h+'.json', sha256=h, producerStateSHA256=digest(state_data),
                    previousPayload=previous_manifest['payload'] if previous_manifest else None,
                    previousSHA256=previous_manifest['sha256'] if previous_manifest else None)
    atomic_write(session / 'current.json', encode(manifest))
    return manifest, snapshot


def enqueue(root, *, label, report, shapes=None, construction=None, display_status='Preview'):
    root = Path(root); config = load_connection(root)
    if (shapes is None) == (construction is None) or display_status not in ('Preview', 'Failed'):
        raise ValueError('LIVE_EXACTLY_ONE_GEOMETRY_ARTIFACT_REQUIRED')
    report_ref, geometry_ref = sealed_file(report), sealed_file(shapes or construction)
    event_id = digest(encode(dict(connection=config['connection_id'], report=report_ref, geometry=geometry_ref, status=display_status)))
    for path in (root / 'queue').glob('*.ready.json'):
        existing = json.loads(path.read_bytes())
        if existing.get('event_id') == event_id:
            return existing
    event = dict(schema=1, connection_id=config['connection_id'], event_id=event_id,
                 created_ns=time.time_ns(), label=label, report=report_ref,
                 kind='shape-patch' if shapes else 'construction',
                 geometry=geometry_ref, display_status=display_status,
                 completion='PRODUCER_SEALED_AFTER_SLICE_COMPLETION')
    atomic_write(root / 'queue' / (str(event['created_ns'])+'-'+event['event_id']+'.ready.json'), encode(event))
    return event


def source_focus(config, report, objects):
    """Read-only camera bounds at an authenticated original native point."""
    focus=report.get('viewer_source_focus')
    if focus is None:return None
    if set(focus)!={'source_id','route_point_index','radius_mm'}:
        raise ValueError('LIVE_SOURCE_FOCUS_SCHEMA')
    sid=focus['source_id'];index=focus['route_point_index'];radius=focus['radius_mm']
    if (sid not in objects or type(index)is not int or index<0 or
            type(radius)not in(int,float)or not math.isfinite(radius)or not .05<=radius<=1):
        raise ValueError('LIVE_SOURCE_FOCUS_REQUIRED')
    catalogue=json.loads(artifact_reader(config['legacy'])(config['scene_ref']))
    matches=[r for r in catalogue['objects'] if r['source_id']==sid]
    if len(matches)!=1:raise ValueError('LIVE_SOURCE_FOCUS_UNKNOWN')
    points=matches[0]['metadata'].get('route_points_mm',[])
    if index>=len(points):raise ValueError('LIVE_SOURCE_FOCUS_POINT_REQUIRED')
    x,y=points[index]
    return dict(x=x-radius,y=y-radius,width=2*radius,height=2*radius)


def process_event(root, event):
    import gzip
    root = Path(root); config = load_connection(root)
    if event.get('schema') != 1 or event.get('connection_id') != config['connection_id'] or event.get('completion') != 'PRODUCER_SEALED_AFTER_SLICE_COMPLETION':
        raise ValueError('LIVE_EVENT_BINDING_MISMATCH')
    report = json.loads(read_bound(event['report']['path'], event['report']['sha256']))
    raw = read_bound(event['geometry']['path'], event['geometry']['sha256'])
    report_source = report.get('input_binding', {}).get('source_sha256')
    if report_source is not None and report_source != config['source_sha256']:
        raise ValueError('LIVE_REPORT_SOURCE_MISMATCH')
    manifest, current = read_current(root / 'session')
    state = json.loads(read_bound(root / 'receipts' / (manifest['sha256']+'.state.json'), manifest['producerStateSHA256']))
    if state['revision'] != current['revision']:
        raise ValueError('LIVE_STATE_REVISION_MISMATCH')
    fingerprints = dict(state['fingerprints']); objects = {o['id']: o for o in current['objects']}
    templates = json.loads((root / 'templates.json').read_bytes())
    if event['kind'] == 'shape-patch':
        records = json.loads(raw)
        updates = {}
        for sid, record in records.items():
            if sid not in fingerprints or digest(bytes.fromhex(record['before_wkb_hex'])) != fingerprints[sid]:
                raise ValueError('LIVE_PATCH_PREDECESSOR_MISMATCH:' + sid)
            updates[sid] = record['after_wkb_hex']
    elif event['kind'] == 'construction':
        stage = json.loads(gzip.decompress(raw))
        updates = construction_map(stage, config)
        # Independent cohort results start from the same exact T03 template, not a prior experiment.
        template_raw = read_bound(config['template']['path'], config['template']['sha256'])
        objects = {o['id']: o for o in json.loads(template_raw)['objects']}
        # Restore original T03 fingerprints for this complete construction replacement.
        read = artifact_reader(config['legacy'])
        scene = json.loads(read(config['scene_ref']))
        fingerprints = {row['source_id']: row['geometry_ref']['sha256'] for row in scene['objects']}
    else:
        raise ValueError('LIVE_UNSUPPORTED_EVENT_KIND')
    max_error = 0.
    for sid, hex_wkb in updates.items():
        if sid not in fingerprints or sid not in templates:
            raise ValueError('LIVE_UNKNOWN_SOURCE_ID:' + sid)
        data = bytes.fromhex(hex_wkb); shape, error = display(from_wkb(data)); max_error = max(max_error, error)
        fingerprints[sid] = digest(data)
        if shape is None:
            objects.pop(sid, None)
        else:
            objects[sid] = dict(templates[sid], path=path_data(shape), bounds=bounds(shape))
    before = {o['id']: o for o in current['objects']}
    changed = [o for items, other in [(list(objects.values()), before), (current['objects'], objects)]
               for o in items if o['id'] not in other or o['path'] != other[o['id']]['path']]
    status = event['display_status']
    if status not in ('Preview', 'Failed'):
        raise ValueError('LIVE_STATUS_PROMOTION_FORBIDDEN')
    snapshot = dict(current, objects=list(objects.values()), bounds=area_bounds(list(objects.values())),
                    affected=source_focus(config,report,objects) or (area_bounds(changed) if changed else current['affected']), status=status,
                    slice=event['label'] + ('' if changed else ' · no geometry changes'),
                    evidence=[event['report']['path'], event['geometry']['path']],
                    limitations=['Completed slice sealed by producer; display delivery is not engineering acceptance.',
                                 'Report qualification/status: '+str(report.get('status', report.get('schema', 'see bound report'))),
                                 'Display-only new-body Hausdorff error mm: '+str(max_error),
                                 'Source Gerbers and engineering artifacts are read-only.'])
    manifest, snapshot = save_revision(root, snapshot, fingerprints, event=event['event_id'])
    return dict(status='PUBLISHED', event_id=event['event_id'], revision=snapshot['revision'],
                payload_sha256=manifest['sha256'], changed_objects=len({o['id'] for o in changed}),
                report=event['report'], geometry=event['geometry'])


def feedback(root):
    root = Path(root); path = root / 'session/outbox/selection.json'
    if not path.exists():
        return None
    selection = json.loads(path.read_bytes()); manifest, current = read_current(root / 'session')
    known = {current['revision']}
    if manifest.get('previousPayload'):
        previous = json.loads(read_bound(root / 'session/snapshots' / manifest['previousPayload'], manifest['previousSHA256']))
        known.add(previous['revision'])
    if selection.get('job') != current['job'] or selection.get('revision') not in known:
        return dict(status='STALE_SELECTION', selection=selection)
    scene = current if selection['revision'] == current['revision'] else previous
    if selection.get('object') is None:
        return dict(status='SELECTION_CLEARED', selection=selection)
    source = next((o for o in scene['objects'] if o['id'] == selection.get('object', {}).get('id')), None)
    if source != selection.get('object'):
        raise ValueError('LIVE_SELECTION_BINDING_MISMATCH')
    from .route_presentation import validate_route_feedback
    validate_route_feedback(root, selection, scene)
    return dict(status='CURRENT_SELECTION' if scene is current else 'PREVIOUS_REVISION_SELECTION', selection=selection)


def attach_benchmark(root, *, log, qualification, script):
    root = Path(root); config = load_connection(root)
    if config.get('benchmark_feed'):
        raise ValueError('LIVE_FEED_ALREADY_ATTACHED')
    config['benchmark_feed'] = dict(log=str(Path(log).resolve()), qualification=str(Path(qualification).resolve()), script=sealed_file(script))
    atomic_write(root / 'connection.json', encode(config))
    return config['benchmark_feed']


def ingest_benchmark(root):
    root = Path(root); config = load_connection(root); feed = config.get('benchmark_feed')
    if not feed:
        return
    read_bound(feed['script']['path'], feed['script']['sha256'])
    raw = Path(feed['log']).read_bytes()
    cursor_path = root / 'feed-cursor.json'
    cursor = json.loads(cursor_path.read_bytes()) if cursor_path.exists() else dict(offset=0, prefix_sha256=digest(b''))
    offset = cursor['offset']
    if len(raw) < offset or digest(raw[:offset]) != cursor['prefix_sha256']:
        raise ValueError('LIVE_COMPLETION_LOG_REWRITTEN')
    end = raw.rfind(b'\n') + 1
    if end <= offset:
        return
    for line in raw[offset:end].splitlines():
        try:
            marker = json.loads(line)
        except (ValueError, UnicodeDecodeError):
            continue  # Progress/warnings cannot qualify a completed slice.
        if not isinstance(marker, dict) or marker.get('event') != 'CASE_DONE':
            continue
        kind, enabled = marker.get('kind'), marker.get('enabled')
        if kind not in ('hard', 'five', '64') or type(enabled) is not bool:
            raise ValueError('LIVE_COMPLETION_MARKER_INVALID')
        case = Path(feed['qualification']) / (kind + ('_match' if enabled else '_baseline'))
        report_path = case / 'CASE.json'; report = json.loads(report_path.read_bytes())
        construction = case / 'construction.json.gz'
        if (report['kind'] != kind or report['enabled'] != enabled or
                report['stage_wall_s'] != marker['stage_wall_s'] or
                report['checks']['native_connections'] != marker['connections'] or
                Path(report['stage']['path']).resolve() != construction.resolve()):
            raise ValueError('LIVE_COMPLETION_REPORT_MISMATCH')
        read_bound(construction, report['stage']['sha256'])
        enqueue(root, label='T04 ' + kind + (' matching' if enabled else ' baseline') + ' · completed caller slice',
                report=report_path, construction=construction)
    atomic_write(cursor_path, encode(dict(offset=end, prefix_sha256=digest(raw[:end]))))


def tick(root):
    root = Path(root); published = []
    ingest_benchmark(root)
    # An event committed immediately before a crash is deduplicated using immutable revision state.
    pending = []
    for path in sorted((root / 'queue').glob('*.ready.json')):
        event_hash = digest(path.read_bytes()); receipt = root / 'receipts' / (event_hash + '.json')
        if not receipt.exists():
            pending.append((path, receipt))
    config = load_connection(root)
    if pending and config.get('require_display_ack'):
        manifest = json.loads((root / 'session/current.json').read_bytes())
        ack_path = root / 'session/outbox/display.json'
        if not ack_path.exists() or json.loads(ack_path.read_bytes()).get('payloadSHA256') != manifest['sha256']:
            pending = []
    done = set()
    if pending:
        manifest = json.loads((root / 'session/current.json').read_bytes())
        current_hash, state_hash = manifest['sha256'], manifest['producerStateSHA256']
        while current_hash:
            state = json.loads(read_bound(root / 'receipts' / (current_hash+'.state.json'), state_hash))
            done.add(state['event']); current_hash, state_hash = state['parent_sha256'], state['parent_state_sha256']
    for path, receipt in pending:
        try:
            event = json.loads(path.read_bytes())
            if event['event_id'] in done:
                result = dict(status='ALREADY_PUBLISHED', event_id=event['event_id'])
            else:
                result = process_event(root, event)
        except Exception as error:
            result = dict(status='REJECTED', event_path=str(path), error=repr(error))
        receipt.write_bytes(encode(result)); published.append(result)
        if config.get('require_display_ack') and result['status'] == 'PUBLISHED':
            break  # Let the native canvas acknowledge this revision before advancing.
    selection_path = root / 'session/outbox/selection.json'
    if selection_path.exists():
        key = digest(selection_path.read_bytes() + (root / 'session/current.json').read_bytes())
        marker = root / 'feedback/latest-inputs.sha256'
        if not marker.exists() or marker.read_text() != key:
            try:
                selected = feedback(root)
            except Exception as error:
                selected = dict(status='REJECTED_SELECTION', error=repr(error))
            atomic_write(root / 'feedback/latest.json', encode(selected))
            atomic_write(marker, key.encode())
    return published
