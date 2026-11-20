"""Content-addressed snapshots with one atomic manifest; no PCB edits or gate changes."""
from pathlib import Path
import hashlib
import json
import math
import os
import uuid

from shapely import affinity
from src.catalogue_gerber import parse_source
from src.gerber_image import object_geometry, SAG


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def bounds(shape):
    a, b, c, d = shape.bounds
    return dict(x=a, y=b, width=max(c-a, 1e-6), height=max(d-b, 1e-6))


def path_data(shape):
    parts = []
    def ring(coords):
        xy = list(coords)
        if any(not math.isfinite(v) or abs(v) >= 1e7 for p in xy for v in p):
            raise ValueError('VIEWER_NONFINITE_GEOMETRY')
        parts.append('M ' + ' L '.join(f'{x:.9f} {y:.9f}' for x, y in xy) + ' Z')
    def visit(g):
        if g.is_empty:
            return
        if g.geom_type == 'Polygon':
            ring(g.exterior.coords)
            for hole in g.interiors:
                ring(hole.coords)
        elif g.geom_type in ('MultiPolygon', 'GeometryCollection'):
            for item in g.geoms:
                visit(item)
        else:
            raise ValueError('VIEWER_NONAREA_GEOMETRY')
    visit(shape)
    return ' '.join(parts)


def import_gerber(path):
    raw = Path(path).read_bytes()
    if len(raw) > 64 * 1024 * 1024:
        raise ValueError('VIEWER_SOURCE_RESOURCE_LIMIT')
    parsed, parser = parse_source(raw)
    function = parsed.file_attrs.get('.FileFunction', ())
    polarity = parsed.file_attrs.get('.FilePolarity', ())
    if function and function[0] == 'Copper':
        if polarity != ('Positive',):
            raise ValueError('VIEWER_COPPER_POSITIVE_FILE_REQUIRED')
        layer = '.'.join(function)
    elif function and function[0] == 'Soldermask':
        if polarity != ('Negative',):
            raise ValueError('VIEWER_MASK_OPENING_ROLE_REQUIRED')
        layer = '.'.join(function) + ' openings'
    else:
        raise ValueError('VIEWER_X2_COPPER_OR_MASK_ROLE_REQUIRED')
    if not parsed.objects or len(parsed.objects) > 200_000:
        raise ValueError('VIEWER_OBJECT_RESOURCE_LIMIT')
    # A positive-only display profile avoids selecting cleared/occluded artwork.
    if any(not obj.polarity_dark for obj in parsed.objects):
        raise ValueError('VIEWER_CLEAR_OPERATIONS_NOT_SUPPORTED')
    objects = []
    source_hash = digest(raw)
    for ordinal, obj in enumerate(parsed.objects):
        shape = affinity.scale(object_geometry(obj), 1, -1, origin=(0, 0))
        if shape.is_empty or not shape.is_valid or shape.area <= 0:
            raise ValueError('VIEWER_EMPTY_OR_INVALID_PLOTTING_OBJECT')
        span = parser.feature_spans.get(ordinal)
        objects.append(dict(id=f'{layer}:{ordinal}', sourceID=f'{source_hash}:object:{ordinal}',
                            layer=layer, kind=type(obj).__name__, path=path_data(shape),
                            bounds=bounds(shape), attributes={str(k): list(v) for k, v in (obj.attrs if isinstance(obj.attrs, dict) else {}).items()}))
    return dict(name=Path(path).name, sha256=source_hash, layer=layer), objects


def read_current(workspace):
    manifest_path = workspace / 'current.json'
    if not manifest_path.exists():
        return None, None
    manifest = json.loads(manifest_path.read_bytes())
    hash_value = manifest['sha256']
    if len(hash_value) != 64 or any(c not in '0123456789abcdef' for c in hash_value) or manifest['payload'] != hash_value + '.json':
        raise ValueError('VIEWER_INVALID_MANIFEST')
    payload = workspace / 'snapshots' / manifest['payload']
    if payload.resolve().parent != (workspace / 'snapshots').resolve():
        raise ValueError('VIEWER_PAYLOAD_ESCAPE')
    data = payload.read_bytes()
    if digest(data) != hash_value:
        raise ValueError('VIEWER_CURRENT_CHECKSUM_MISMATCH')
    return manifest, json.loads(data)


def atomic_write(path, data):
    temporary = path.with_name('.' + path.name + '.' + uuid.uuid4().hex)
    try:
        with temporary.open('xb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def publish(workspace, paths, *, slice_name='Gerber import', job='manual-import'):
    workspace = Path(workspace)
    sources, objects = [], []
    for path in paths:
        source, items = import_gerber(path)
        if any(s['layer'] == source['layer'] for s in sources):
            raise ValueError('VIEWER_DUPLICATE_LAYER')
        sources.append(source)
        objects.extend(items)
    if not objects:
        raise ValueError('VIEWER_NO_OBJECTS')
    a = min(o['bounds']['x'] for o in objects)
    b = min(o['bounds']['y'] for o in objects)
    c = max(o['bounds']['x'] + o['bounds']['width'] for o in objects)
    d = max(o['bounds']['y'] + o['bounds']['height'] for o in objects)
    board_bounds = dict(x=a, y=b, width=c-a, height=d-b)
    workspace.mkdir(parents=True, exist_ok=True)
    # Serialize publishers, reject rather than silently race a revision parent.
    lock = workspace / '.publish.lock'
    with lock.open('x'):
        try:
            prior_manifest, previous = read_current(workspace)
            if previous and previous['job'] != job:
                previous = prior_manifest = None
            changed = []
            old = {o['id']: o for o in previous['objects']} if previous else {}
            new = {o['id']: o for o in objects}
            for items, other in ((objects, old), (list(old.values()), new)):
                changed.extend(o['bounds'] for o in items if o['id'] not in other or o['path'] != other[o['id']]['path'])
            affected = board_bounds
            if changed:
                x = min(v['x'] for v in changed); y = min(v['y'] for v in changed)
                affected = dict(x=x, y=y, width=max(v['x']+v['width'] for v in changed)-x,
                                height=max(v['y']+v['height'] for v in changed)-y)
            snapshot = dict(schema=1, job=job, revision=uuid.uuid4().hex,
                            parentRevision=previous['revision'] if previous else None,
                            slice=slice_name, status='Preview', bounds=board_bounds, affected=affected,
                            objects=objects, sources=sources, evidence=[], limitations=[
                                'Display derivative only; electrical/manufacturing acceptance NOT_ESTABLISHED.',
                                f'Polygon approximation uses existing geometry kernel SAG={SAG} mm; no new fidelity qualification.',
                                'X right, Y down in millimetres. Mask geometry represents openings.',
                                'Importer IDs use layer + parser ordinal; not semantic identity across reordered source commands.',
                                'X2 attributes exposed by the parser are source annotations, not independent net intent; unavailable attributes remain empty.',
                                'Strict absolute MM 4.6 positive primitive profile; clear operations are rejected.'
                            ])
            data = encode(snapshot)
            if len(data) > 128 * 1024 * 1024:
                raise ValueError('VIEWER_PAYLOAD_RESOURCE_LIMIT')
            hash_value = digest(data)
            folder = workspace / 'snapshots'; folder.mkdir(exist_ok=True)
            target = folder / (hash_value + '.json')
            with target.open('xb') as stream:
                stream.write(data)
                stream.flush(); os.fsync(stream.fileno())
            manifest = dict(schema=1, payload=target.name, sha256=hash_value,
                            previousPayload=prior_manifest['payload'] if prior_manifest else None,
                            previousSHA256=prior_manifest['sha256'] if prior_manifest else None)
            atomic_write(workspace / 'current.json', encode(manifest))
            return manifest, snapshot
        finally:
            lock.unlink()
