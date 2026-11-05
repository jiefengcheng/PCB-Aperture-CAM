from src.stage_abi.preparation import decode_geometry
"""Complete board selection is checked against native bytes, never an image."""
import json
from shapely import from_wkb
from src.stage_abi.store import digest
from src.stage_abi.contracts import fail
from src.t01_crop.paging import read_pages
from src.t01_crop.source import sites_from_cache
from .policy import validate_binding

def context(store,scene,policy):
    b=validate_binding(store.get_json(policy['binding_ref'],kind='t01-binding'))
    raw=store.get(b['source_ref'],kind='native-source');blob=store.get(b['manifest_ref'],kind='native-manifest');scope_blob=store.get(b['scope_ref'],kind='board-binding')
    if any(digest(data)!=b[key] for data,key in [(raw,'source_sha256'),(blob,'manifest_sha256'),(scope_blob,'scope_sha256')]):fail('T01_SOURCE_BINDING_MISMATCH','Whole-board native inputs')
    manifest=json.loads(blob);scope=json.loads(scope_blob)
    inventory,index=read_pages(store,b['source_inventory_ref'],binding=dict(source_sha256=b['source_sha256'],manifest_sha256=b['manifest_sha256']),kind='t01-source-inventory',identity=lambda r:r['source_id'])
    objects={o['source_id']:o for o in scene['objects']}
    if (inventory!=scene['objects'] or len(objects)!=b['source_objects'] or index['total_records']!=b['source_objects'] or
        manifest['source_sha256']!=b['source_sha256'] or len(manifest['objects'])!=b['source_objects'] or set(objects)!={r['id']for r in manifest['objects']} or
        scene['source_sha256']!=b['source_sha256'] or scene['viewport_mm']!=b['viewport_mm'] or scene['layer']!='F.Cu' or scene['units']!='mm' or
        scope.get('schema')!='pcb-board-scope-verified/1' or scope.get('facts',{}).get('complete_source_coverage') is not True or
        scope['bounds_mm']!=b['viewport_mm'] or scope['source_sha256']!=b['source_sha256'] or scope['manifest_sha256']!=b['manifest_sha256']):fail('T01_BOARD_SOURCE_COVERAGE_MISMATCH','All original source pages and board scope')
    directives={s for pair in b['reviewed_pairs'] for s in pair}|set(b['recess_source_ids'])
    if not directives<=objects.keys():fail('T01_BOARD_DIRECTIVE_NOT_FOUND','Source identity directives')
    shapes=[]
    for row in manifest['objects']:
        obj=objects[row['id']];data=store.get(obj['original_ref'],kind='geometry');start,end=row['source_span']
        if (obj['original_ref']!=obj['geometry_ref'] or digest(data)!=row['geometry_sha256'] or row['source_sha256']!=b['source_sha256'] or
            not 0<=start<end<=len(raw) or row['id']!=f'{b["source_sha256"]}:bytes:{start}:{end}' or 'F.Cu'not in row['layers']):fail('T01_ORIGINAL_SOURCE_REQUIRED',row['id'])
        shapes.append(decode_geometry(data))
    _,rows,sites=sites_from_cache(raw,manifest,shapes,b['viewport_mm'])
    aliases=sorted(a for s in sites for a in s['aliases'])
    if aliases!=scope['eligible_occurrence_ids'] or sorted(objects)!=scope['all_source_ids'] or len(sites)!=scope['canonical_sites']:fail('T01_BOARD_SELECTION_INCOMPLETE','Every source and eligible occurrence must be covered')
    return b,raw,rows,shapes,sites
