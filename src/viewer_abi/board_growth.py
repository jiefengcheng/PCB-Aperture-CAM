"""Read-only whole-board display deltas for a committed construction revision."""
import base64
import gzip
import json
from pathlib import Path

from shapely import from_wkb, union_all

from .live import area_bounds, artifact_reader, construction_map, display, load_connection, read_bound
from .publisher import atomic_write, bounds, digest, encode, path_data, read_current


def partition(before, after):
    """Partition material images, so overlapping source objects cannot hide additions."""
    return [('source', before.intersection(after)), ('added', after.difference(before)),
            ('removed', before.difference(after))]


def publish_board_growth(root):
    root = Path(root)
    config = load_connection(root)
    manifest, snapshot = read_current(root / 'session')
    state = json.loads(read_bound(root / 'receipts' / (manifest['sha256'] + '.state.json'),
                                 manifest['producerStateSHA256']))
    matches = [json.loads(p.read_bytes()) for p in (root / 'queue').glob('*.ready.json')
               if json.loads(p.read_bytes()).get('event_id') == state['event']]
    if len(matches) != 1 or matches[0]['kind'] != 'construction':
        raise ValueError('BOARD_GROWTH_REQUIRES_COMMITTED_CONSTRUCTION')
    event = matches[0]
    if (event['connection_id'] != config['connection_id'] or state['revision'] != snapshot['revision'] or
            digest(encode(dict(connection=config['connection_id'], report=event['report'],
                               geometry=event['geometry'], status=event['display_status']))) != state['event']):
        raise ValueError('BOARD_GROWTH_EVENT_MISMATCH')
    read_bound(event['report']['path'], event['report']['sha256'])
    stage = json.loads(gzip.decompress(read_bound(event['geometry']['path'], event['geometry']['sha256'])))
    mapping = construction_map(stage, config)
    read = artifact_reader(config['legacy'])
    catalogue = json.loads(read(config['scene_ref']))
    rows = catalogue['objects']
    if set(state['fingerprints']) != {row['source_id'] for row in rows}:
        raise ValueError('BOARD_GROWTH_SOURCE_COVERAGE_MISMATCH')
    before, after = [], []
    originals = {}
    for row in rows:
        sid = row['source_id']; original = read(row['geometry_ref'])
        current = bytes.fromhex(mapping[sid]) if sid in mapping else original
        if digest(current) != state['fingerprints'][sid]:
            raise ValueError('BOARD_GROWTH_CURRENT_FINGERPRINT_MISMATCH')
        originals[sid]=from_wkb(original)
        before.append(originals[sid]); after.append(from_wkb(current))
    before, after = union_all(before), union_all(after)
    if not before.is_valid or not after.is_valid:
        raise ValueError('BOARD_GROWTH_INVALID_MATERIAL_IMAGE')
    layer = snapshot['sources'][0]['layer']
    if len(snapshot['sources']) != 1:
        raise ValueError('BOARD_GROWTH_REQUIRES_SINGLE_LAYER')
    parts, areas, display_error = [], {}, 0.
    for kind, shape in partition(before, after):
        areas[kind] = shape.area
        polygons = [] if shape.is_empty else [shape] if shape.geom_type == 'Polygon' else list(shape.geoms)
        for polygon in polygons:
            if polygon.geom_type != 'Polygon' or polygon.is_empty or polygon.area == 0:
                continue
            physical_area = polygon.area
            polygon, error = display(polygon)
            display_error = max(display_error, error)
            parts.append(dict(id=f'growth:{kind}:{len(parts)}',
                              sourceID=config['source_sha256'] + ':display-growth:' + str(len(parts)),
                              layer=layer, kind=kind, path=path_data(polygon), bounds=bounds(polygon),
                              attributes={'physical_area_mm2':[repr(physical_area)]}))
    value = dict(schema=1, job=snapshot['job'], revision=snapshot['revision'],
                 sceneSHA256=manifest['sha256'], sourceSHA256=config['source_sha256'],
                 predecessorSHA256=config['scene_ref']['sha256'] if config.get('context') == 'original' else config['t03_sha256'], constructionSHA256=event['geometry']['sha256'],
                 beforeWkbSHA256=digest(before.wkb), afterWkbSHA256=digest(after.wkb),
                 parts=parts, bounds=area_bounds(parts), addedAreaMM2=areas['added'], removedAreaMM2=areas['removed'], displayHausdorffMM=display_error,
                 summary=('Bounded T04 directly over original source' if config.get('context') == 'original' else 'T04 over accepted T03') + ' · grey copper · green added edges · pink removed areas',
                 note='REPLAY of saved diagnostic construction. Exact material-image differences; display Hausdorff <=0.0005 mm. '
                      'No growth execution or acceptance change. Source object picking remains separate.')
    from .copper_cleanup import cleanup_cases
    value['cleanup']=cleanup_cases(stage,{r['source_id']:r for r in rows},originals,
                                   before.difference(after),after.difference(before),display,layer=layer,source_image=before)
    if stage.get('operation')=='TRIM_ONLY':
        value['summary']='Trimming only directly over original source · grey copper · pink removed areas · no added copper'
        value['note']='Saved bounded trim-only construction. No widening, recess filling or positive-copper clearance search.'
    payload = encode(value)
    if len(payload) > 64 * 1024 * 1024:
        raise ValueError('BOARD_GROWTH_RESOURCE_LIMIT')
    # Recheck the authoritative commit before publishing a revision-bound display sidecar.
    if read_current(root / 'session')[0] != manifest:
        raise ValueError('BOARD_GROWTH_REVISION_CHANGED')
    folder = root / 'session/presentations'; folder.mkdir(exist_ok=True)
    target = folder / (manifest['sha256'] + '.json')
    atomic_write(target, encode(dict(schema=1, sha256=digest(payload),
                                    payloadBase64=base64.b64encode(payload).decode())))
    return dict(status='DISPLAY_ONLY', revision=snapshot['revision'], path=str(target.resolve()),
                sha256=digest(target.read_bytes()), parts=len(parts), addedAreaMM2=areas['added'],
                removedAreaMM2=areas['removed'], construction=event['geometry'],operation=value['cleanup']['operation'],
                cleanupPlaces=len(value['cleanup']['cases']))
