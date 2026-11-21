"""Read-only route display from maintained membership and saved source bodies.

No grouping, growth, snapping, trimming or repair occurs here. The union is a
presentation of existing copper. Every member is resolved against the displayed
revision, including covered context and lineage patches. Native centerlines are
reference polylines only; they never substitute for copper hit-test geometry.
"""
import json
import math
from pathlib import Path

from shapely import from_wkb, to_wkb
from shapely.geometry import LineString
from shapely.ops import unary_union

from .publisher import atomic_write, bounds, digest, encode, path_data
from .live import artifact_reader, display


def bind_catalogue(root, preparation):
    """Project already-recorded native membership into a compact viewer artifact.

    Reads the maintained admission and recorded bulk roles. It does not run the
    classifier or T04. The large whole-board construction is not decompressed
    merely to obtain route names and member identities.
    """
    import gzip
    from .live import read_bound
    root, preparation = Path(root), Path(preparation)
    config = json.loads((root/'connection.json').read_bytes())
    raw = (preparation/'BINDING.json').read_bytes();binding = json.loads(raw)
    if (binding.get('schema') != 't04-source-role-preparation/1' or
            binding['source_sha256'] != config['source_sha256'] or binding['scene_sha256'] != config['scene_ref']['sha256']):
        raise ValueError('VIEWER_CATALOGUE_SOURCE_BINDING_MISMATCH')
    admission = json.loads(gzip.decompress(read_bound(preparation/'admission.json.gz', binding['files']['admission.json.gz'])))
    roles = json.loads(gzip.decompress(read_bound(preparation/'ROLES.json.gz', binding['files']['ROLES.json.gz'])))
    routes = {}
    for path in admission['admitted']:
        members = [s for s in path['source_ids'] if s not in roles['roles']]
        if not members:continue
        if path['path_id'] in routes or len(members) != len(set(members)):
            raise ValueError('VIEWER_CATALOGUE_DUPLICATE_MEMBERSHIP')
        routes[path['path_id']] = members
    value = dict(schema='viewer-native-route-catalogue/1', source_sha256=config['source_sha256'], scene_ref=config['scene_ref'],
                 preparationSHA256=digest(raw), preparation=str(preparation.resolve()), files=binding['files'], routes=routes)
    data=encode(value);sha=digest(data);folder=root/'route-catalogue';folder.mkdir(exist_ok=True)
    target=folder/(sha+'.json')
    if target.exists():read_bound(target,sha)
    else:atomic_write(target,data)
    config['route_catalogue']=dict(path=str(target.resolve()),sha256=sha)
    atomic_write(root/'connection.json',encode(config))
    return dict(routes=len(routes),members=sum(map(len,routes.values())),catalogue=config['route_catalogue'])


def maintained_routes(config, cache):
    from .live import read_bound
    from .trace_selection import construction_context
    ref=config.get('route_catalogue')
    if ref is None:
        stage,_=construction_context(config['construction'],config,cache)
        return stage.get('native_trace_source_ids_by_route',{}),config['construction'],stage
    key=('route-catalogue',ref['path'],ref['sha256'])
    if key not in cache:
        value=json.loads(read_bound(ref['path'],ref['sha256']))
        if (value.get('schema')!='viewer-native-route-catalogue/1' or value['source_sha256']!=config['source_sha256'] or value['scene_ref']!=config['scene_ref']):
            raise ValueError('VIEWER_CATALOGUE_BINDING_CHANGED')
        cache[key]=value['routes']
    return cache[key],ref,{}


def catalogue_index(root, config, scene, *, cache):
    """Compact object-index membership for picking, never geometric regrouping."""
    catalogue_ref=config.get('route_catalogue',config['construction'])
    encoded = [o['id'].encode() for o in scene['objects']]
    objects_sha = digest(b''.join(len(v).to_bytes(8, 'big') + v for v in encoded))
    binding = dict(schema='viewer-route-index/1', job=scene['job'], revision=scene['revision'],
                   catalogueSHA256=catalogue_ref['sha256'], objectsSHA256=objects_sha)
    key = digest(encode(binding));folder = Path(root)/'route-cache';target = folder/('index-'+key+'.json')
    if target.exists():
        envelope = json.loads(target.read_bytes())
        if envelope.get('binding') != key or digest(encode(envelope['index'])) != envelope.get('sha256'):
            raise ValueError('VIEWER_ROUTE_INDEX_CACHE_CHANGED')
        return envelope['index']
    routes,_,_=maintained_routes(config,cache)
    lookup = {}
    for i,o in enumerate(scene['objects']):lookup.setdefault(o['sourceID'], []).append(i)
    entries, assigned = [], set()
    for route_id, sources in sorted(routes.items()):
        indices = [i for source in sources for i in lookup.get(source, [])]
        if len(sources) != len(set(sources)) or any(i in assigned for i in indices):
            raise ValueError('VIEWER_ROUTE_INDEX_AMBIGUOUS')
        assigned.update(indices)
        if indices:entries.append(dict(routeID=route_id, objectIndices=indices))
    value = dict(schema=1, job=scene['job'], revision=scene['revision'], catalogueSHA256=catalogue_ref['sha256'],
                 objectsSHA256=objects_sha, entries=entries)
    if len(encode(value)) > 512*1024:
        return None
    folder.mkdir(exist_ok=True)
    atomic_write(target, encode(dict(binding=key, sha256=digest(encode(value)), index=value)))
    return value


def group_references(stage, sid):
    refs = []
    for group in stage.get('groups', []):
        if any(sid in lane.get('source_ids', []) for lane in group['lanes']):
            refs.append(dict(kind='straight', id=group.get('maximal_group_id') or group['catalogue_band_index']))
    arc = stage.get('hybrid_components', {}).get('arc_core_shapes', {}).get(sid)
    if arc:
        refs.append(dict(kind='arc', id=arc['group_id']))
    return sorted({(r['kind'], r['id']): r for r in refs}.values(), key=lambda r: (r['kind'], r['id']))


def route_presentation(root, config, scene, state, selected_row, catalogue, stage, ref, *, cache):
    from .trace_selection import resolve_body
    sid = selected_row['source_id']
    catalogue_stage, catalogue_ref = stage, ref
    routes = [] if stage is None else [r for r, ss in stage.get('native_trace_source_ids_by_route', {}).items() if sid in ss]
    if not routes:
        membership,catalogue_ref,catalogue_stage=maintained_routes(config,cache)
        routes = [r for r,ss in membership.items()if sid in ss]
    else:
        membership=catalogue_stage['native_trace_source_ids_by_route']
    if not routes:
        return None, 'No maintained route is bound to this source; segment inspection remains available.'
    if len(routes) != 1:
        raise ValueError('VIEWER_ROUTE_MEMBERSHIP_AMBIGUOUS')
    route_id = routes[0]
    sources = membership[route_id]
    if not sources or len(sources) != len(set(sources)):
        raise ValueError('VIEWER_ROUTE_MEMBERSHIP_INVALID')
    if len(sources) > 2048:
        return None, 'Route display exceeds the member resource limit; no members were truncated.'
    rows = {r['source_id']: r for r in catalogue['objects']}
    objects = {o['sourceID']: o for o in scene['objects']}
    if any(s not in rows or s not in objects for s in sources):
        return None, 'A complete route is not present in this displayed snapshot; no partial route was substituted.'
    read = artifact_reader(config['legacy'])
    members, bodies, evidence = [], [], []
    point_count = 0
    for source in sources:
        row, obj = rows[source], objects[source]
        points = row.get('metadata', {}).get('route_points_mm')
        if not points or len(points) < 2:
            return None, 'Original native centerlines are unavailable; segment inspection remains available.'
        if any(len(p) != 2 or any(not math.isfinite(v) or abs(v) >= 1e7 for v in p) for p in points):
            raise ValueError('VIEWER_ROUTE_CENTERLINE_INVALID')
        point_count += len(points)
        if point_count > 100000:
            return None, 'Route centerlines exceed the display resource limit; no points were truncated.'
        original = read(row['original_ref'])
        body, member_stage, _, member_ref = resolve_body(root, config, state, row, cache=cache)
        # The source display is already validated by the native snapshot reader.
        # Reproduce it here before allowing an assembled-route overlay to hide it.
        derivative, _ = display(from_wkb(body))
        if derivative is None or path_data(derivative) != obj['path']:
            return None, 'Route comparison unavailable: a member has a different display derivative.'
        groups = group_references(member_stage or catalogue_stage, source)
        members.append(dict(objectID=obj['id'], sourceID=source,
                            currentPathSHA256=digest(obj['path'].encode()), currentWkbSHA256=digest(body),
                            originalWkbSHA256=digest(original), points=points, groups=groups))
        bodies.append(body)
        evidence.append([source, member_ref['sha256'], digest(encode(row.get('metadata', {})))])
    binding = dict(schema='viewer-maintained-route-display/1', job=scene['job'], revision=scene['revision'],
                   routeID=route_id, catalogueSHA256=catalogue_ref['sha256'], sceneRef=config['scene_ref'],
                   members=members, evidence=evidence,
                   implementationSHA256=digest(Path(__file__).read_bytes()))
    key = digest(encode(binding))
    folder = Path(root)/'route-cache'
    target = folder/(key+'.json')
    if target.exists():
        envelope = json.loads(target.read_bytes())
        if envelope.get('binding') != key or digest(encode(envelope['route'])) != envelope.get('sha256'):
            raise ValueError('VIEWER_ROUTE_CACHE_CHANGED')
        return envelope['route'], None
    # Preserve the maintained native membership order used by the saved assembler.
    current = unary_union([from_wkb(body) for body in bodies])
    derivative, error = display(current)
    if derivative is None:
        return None, 'The maintained route has no visible copper in this snapshot.'
    groups = sorted({(g['kind'], g['id']) for m in members for g in m['groups']})
    fit_geometry = unary_union([current, *[LineString(m['points']) for m in members]])
    route = dict(schema=1, job=scene['job'], revision=scene['revision'], routeID=route_id, catalogueSHA256=catalogue_ref['sha256'], bindingSHA256=key,
                 currentWkbSHA256=digest(to_wkb(current)), displayHausdorffMM=error,
                 assembled=dict(path=path_data(derivative), bounds=bounds(derivative)), bounds=bounds(fit_geometry),
                 members=members, groups=[dict(kind=k, id=v) for k,v in groups])
    if len(encode(route)) > 768*1024:
        return None, 'Complete route contours exceed the display resource limit; no geometry was truncated.'
    folder.mkdir(exist_ok=True)
    atomic_write(target, encode(dict(binding=key, sha256=digest(encode(route)), route=route)))
    return route, None


def validate_route_feedback(root, selection, scene):
    """Reject a forged/stale route context without interpreting it as authority."""
    if selection.get('selectionMode', 'segment') not in ('route', 'segment'):
        raise ValueError('VIEWER_SELECTION_MODE_INVALID')
    route = selection.get('route')
    if route is None:
        return
    key = route.get('bindingSHA256', '')
    if len(key) != 64 or any(c not in '0123456789abcdef' for c in key):
        raise ValueError('VIEWER_ROUTE_FEEDBACK_BINDING_INVALID')
    envelope = json.loads((Path(root)/'route-cache'/(key+'.json')).read_bytes())
    value = envelope['route']
    expected = dict(routeID=value['routeID'], bindingSHA256=value['bindingSHA256'],
                    catalogueSHA256=value['catalogueSHA256'],
                    memberSourceIDs=[m['sourceID'] for m in value['members']])
    if (envelope.get('binding') != key or digest(encode(value)) != envelope.get('sha256') or
            value['job'] != scene['job'] or value['revision'] != scene['revision'] or route != expected):
        raise ValueError('VIEWER_ROUTE_FEEDBACK_MISMATCH')
    objects = {o['id']: o for o in scene['objects']}
    if not any(m['objectID'] == selection['object']['id'] for m in value['members']):
        raise ValueError('VIEWER_ROUTE_FEEDBACK_SOURCE_MISMATCH')
    for member in value['members']:
        obj = objects.get(member['objectID'])
        if obj is None or obj['sourceID'] != member['sourceID'] or digest(obj['path'].encode()) != member['currentPathSHA256']:
            raise ValueError('VIEWER_ROUTE_FEEDBACK_MEMBER_CHANGED')
