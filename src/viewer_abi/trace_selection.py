"""Resolve any selected source against committed viewer lineage; no T04 execution."""
import base64
import gzip
import json
from pathlib import Path

from .publisher import atomic_write, digest, encode, read_current
from .live import artifact_reader, construction_map, read_bound
from .explanation import growth_comparison


def selection_context(root, selection):
    root = Path(root)
    manifest, scene = read_current(root / 'session')
    state = json.loads(read_bound(root / 'receipts' / (manifest['sha256'] + '.state.json'),
                                 manifest['producerStateSHA256']))
    if selection['revision'] != scene['revision']:
        if not manifest.get('previousPayload'):
            raise ValueError('TRACE_SELECTION_STALE')
        scene = json.loads(read_bound(root / 'session/snapshots' / manifest['previousPayload'],
                                      manifest['previousSHA256']))
        state = json.loads(read_bound(root / 'receipts' / (manifest['previousSHA256'] + '.state.json'),
                                     state['parent_state_sha256']))
    if (selection['job'] != scene['job'] or selection['revision'] != scene['revision'] or
            state['revision'] != scene['revision'] or selection['object'] not in scene['objects']):
        raise ValueError('TRACE_SELECTION_BINDING_MISMATCH')
    return scene, state


def construction_context(ref, config, cache):
    """Decode each hash-bound construction once within a selection request."""
    key = ('construction', ref['path'], ref['sha256'])
    if key not in cache:
        stage = json.loads(gzip.decompress(read_bound(ref['path'], ref['sha256'])))
        cache[key] = stage, construction_map(stage, config)
    return cache[key]


def resolve_body(root, config, state, row, *, cache=None):
    """Construction replaces the cohort; patches inherit only through hash-bound parents."""
    root = Path(root); sid = row['source_id']; expected = state['fingerprints'][sid]
    cache = {} if cache is None else cache
    visited = set()
    for _ in range(4096):
        event_id = state['event']
        if state['revision'] in visited:
            raise ValueError('TRACE_LINEAGE_CYCLE')
        visited.add(state['revision'])
        if event_id == 'initial':
            ref = config['construction']; kind = 'construction'
        else:
            matches = [json.loads(p.read_bytes()) for p in (root / 'queue').glob('*.ready.json')
                       if json.loads(p.read_bytes()).get('event_id') == event_id]
            if len(matches) != 1:
                raise ValueError('TRACE_COMPLETION_EVENT_MISSING_OR_AMBIGUOUS')
            event = matches[0]
            identity = digest(encode(dict(connection=config['connection_id'], report=event['report'],
                                          geometry=event['geometry'], status=event['display_status'])))
            if identity != event_id or event['connection_id'] != config['connection_id']:
                raise ValueError('TRACE_COMPLETION_IDENTITY_MISMATCH')
            read_bound(event['report']['path'], event['report']['sha256'])
            ref, kind = event['geometry'], event['kind']
        stage = None
        if kind == 'construction':
            stage, mapping = construction_context(ref, config, cache)
            if sid in mapping:
                body = bytes.fromhex(mapping[sid])
                treatment = ('Editable bulk copper' if sid in stage['hybrid_components']['changed_bulk_copper']
                             else 'Constructed T04 trace')
            else:
                body = artifact_reader(config['legacy'])(row['geometry_ref'])
                treatment = 'Retained context; no constructed T04 body in this slice'
        elif kind == 'shape-patch':
            key = ('patch', ref['path'], ref['sha256'])
            if key not in cache:
                cache[key] = json.loads(read_bound(ref['path'], ref['sha256']))
            record = cache[key].get(sid)
            if record is None:
                if not state.get('parent_sha256'):
                    raise ValueError('TRACE_PATCH_PARENT_MISSING')
                state = json.loads(read_bound(root / 'receipts' / (state['parent_sha256'] + '.state.json'),
                                             state['parent_state_sha256']))
                continue
            body = bytes.fromhex(record['after_wkb_hex']); treatment = 'Completed source-bound geometry patch'
        else:
            raise ValueError('TRACE_EVENT_KIND_UNSUPPORTED')
        if digest(body) != expected:
            raise ValueError('TRACE_BODY_FINGERPRINT_MISMATCH')
        return body, stage, treatment, ref
    raise ValueError('TRACE_LINEAGE_RESOURCE_LIMIT')


def treatment_details(stage, sid):
    if not stage:
        return []
    details = []
    routes = [rid for rid, sources in stage.get('native_trace_source_ids_by_route', {}).items() if sid in sources]
    if routes:
        details.append('Native route: ' + ', '.join(routes) + '.')
    for group in stage.get('groups', []):
        for lane in group['lanes']:
            if sid not in lane['source_ids']:
                continue
            details.append(f"Straight group: {group['catalogue_band_index']}. "
                           f"Recorded span width {lane['source_width_mm']*1000:.3f} → {lane['width_mm']*1000:.3f} µm.")
            faces = lane.get('face_growth_mm', {})
            if 'left' in faces and 'right' in faces:
                details.append(f"Group-axis side growth: left {faces['left']*1000:.3f} µm; right {faces['right']*1000:.3f} µm. "
                               'These are span allocations; joints may have a different local width.')
    h = stage['hybrid_components']
    arc = h.get('arc_core_shapes', {}).get(sid)
    if arc:
        details.append('Constructed arc-group member: ' + arc['group_id'] + '.')
    for report in h.get('residual', {}).get('reports', []):
        if report.get('source_id') == sid:
            factor = report.get('selected_factor')
            details.append('Stored residual record: ' + str(report.get('status', 'see retained attempts')) +
                           (f'; selected profile ceiling {factor:.6g}×.' if factor is not None else '.'))
    return details


def trace_response(root, selection):
    root = Path(root); config = json.loads((root / 'connection.json').read_bytes())
    scene, state = selection_context(root, selection)
    obj = selection['object']; sid = obj['sourceID']
    read = artifact_reader(config['legacy'])
    catalogue = json.loads(read(config['scene_ref']))
    rows = [r for r in catalogue['objects'] if r['source_id'] == sid]
    if len(rows) != 1:
        raise ValueError('TRACE_SOURCE_OCCURRENCE_NOT_UNIQUE')
    row = rows[0]
    if 'original_ref' not in row:
        raise ValueError('TRACE_ORIGINAL_GEOMETRY_UNAVAILABLE')
    original = read(row['original_ref'])
    cache = {}
    body, stage, treatment, ref = resolve_body(root, config, state, row, cache=cache)
    note = ('Bound to displayed ' + scene['slice'] + ' · revision ' + scene['revision'][:12] +
            '. This is not a claim that the whole snapshot is the latest T04 result.')
    response = dict(schema=1, job=scene['job'], revision=scene['revision'], objectID=obj['id'], sourceID=sid,
                    author='Retained T04 geometry', evidence=[ref['path'], config['scene_ref']['artifact_id'],
                                                               row['original_ref']['artifact_id']])
    details = treatment_details(stage, sid)
    try:
        comparison = growth_comparison(original, body, obj, summary=treatment, snapshot_note=note)
        added, removed = comparison['addedAreaMM2'], comparison['removedAreaMM2']
        summary = ('Unchanged from original source' if added == 0 and removed == 0 else
                   f'Added {added:.6g} mm² · removed {removed:.6g} mm²')
        comparison['summary'] = summary
        response['comparison'] = comparison
        text = [treatment + '.', summary + '.', *details,
                'Blue = original source; green = added copper; pink = removed copper. '
                'This is one source occurrence, not the assembled route. Geometric differences do not establish '
                'net intent, clearance approval or manufacturing acceptance. No geometry was changed.']
    except ValueError as error:
        # A differently derived context path is not silently replaced with another body's overlay.
        if str(error) != 'EXPLANATION_CURRENT_BODY_NOT_DISPLAYED':
            raise
        text = [treatment + '.', *details, 'Comparison unavailable: the original retained context uses a different display derivative. '
                'No T04 body or source growth has been substituted.']
    response['text'] = '\n\n'.join(text)
    from .route_presentation import route_presentation, catalogue_index
    index = catalogue_index(root, config, scene, cache=cache)
    if index is not None:
        response['routeIndex'] = index
    route, unavailable = route_presentation(root, config, scene, state, row, catalogue,
                                            stage, ref, cache=cache)
    if route is not None:
        response['route'] = route
        ordinal = (obj.get('attributes', {}).get('ordinal') or [''])[0]
        response['text'] = 'Clicked segment: ' + obj['kind'] + (' ' + ordinal if ordinal else '') + '.\n\n' + response['text']
        response['text'] = response['text'].replace(
            'This is one source occurrence, not the assembled route.',
            'The area figures describe the clicked segment. Route mode displays the complete maintained route with dotted original centerlines.')
    elif unavailable:
        response['routeUnavailable'] = unavailable
    return response


def write_trace_response(root, selection, target):
    value = trace_response(root, selection)
    payload = encode(value)
    if (len(payload) > 1024 * 1024 or any(len(a['path']) > 1024 * 1024 for a in
            (value.get('comparison', {}).get(k) for k in ('original', 'added', 'removed')) if a)):
        value.pop('comparison', None)
        value['text'] += '\n\nSegment comparison unavailable: exact contours exceed the per-selection display resource limit.'
        payload = encode(value)
    if len(payload) > 1024 * 1024:
        value.pop('route', None)
        value['routeUnavailable'] = 'Complete route response exceeds the display resource limit; no members were truncated.'
        payload = encode(value)
    atomic_write(Path(target), encode(dict(schema=1, sha256=digest(payload),
                                          payloadBase64=base64.b64encode(payload).decode())))
    return value
