"""Discover C01 operands from bound original bytes/cache, never saved decisions."""
import hashlib
from collections import defaultdict
import sexpdata
from shapely import STRtree, from_wkb
from shapely.geometry import box
from src.native_reference import one
from src.crop_circle_sources import _raw_filled_circle_scan
from src.stage_abi.contracts import fail
from src.stage_abi.store import digest
from .contract import validate_binding

def discover(store, scene, binding):
    validate_binding(binding)
    raw = store.get(binding['source_ref'], kind='native-source')
    manifest_raw = store.get(binding['manifest_ref'], kind='native-manifest')
    manifest = store.get_json(binding['manifest_ref'], kind='native-manifest')
    if digest(raw)!=binding['source_sha256'] or digest(manifest_raw)!=binding['manifest_sha256'] or scene['source_sha256']!=binding['source_sha256'] or manifest['source_sha256']!=binding['source_sha256']:
        fail('T01_SOURCE_BINDING_MISMATCH','source or manifest bytes')
    rows = manifest['objects']
    objects={r['source_id']:r for r in scene['objects']}
    if len(rows)!=binding['source_objects'] or len(objects)!=len(rows) or len({r['id'] for r in rows})!=len(rows) or set(objects)!={r['id'] for r in rows}:
        fail('T01_SOURCE_COVERAGE_MISMATCH','Complete original F.Cu cache required')
    if scene['viewport_mm']!=binding['viewport_mm'] or scene['units']!='mm' or scene['layer']!='F.Cu':
        fail('T01_SOURCE_FRAME_MISMATCH','bound viewport/mm/F.Cu')
    shapes=[]
    for r in rows:
        sid=r['id'];o=objects[sid]
        blob=store.get(o['original_ref'],kind='geometry')
        if o['original_ref']!=o['geometry_ref'] or digest(blob)!=r['geometry_sha256'] or r.get('source_sha256')!=binding['source_sha256'] or 'F.Cu' not in r['layers']:
            fail('T01_ORIGINAL_SOURCE_REQUIRED',sid)
        start,end=r['source_span']
        if sid!=f'{binding["source_sha256"]}:bytes:{start}:{end}' or not 0<=start<end<=len(raw):
            fail('T01_SOURCE_SPAN_MISMATCH',sid)
        shapes.append(from_wkb(blob))
    tree=STRtree(shapes);crop=box(*binding['viewport_mm']);occurrences=defaultdict(list)
    for i,(r,g) in enumerate(zip(rows,shapes,strict=True)):
        if r['kind']!='gr_circle' or not g.intersects(crop):continue
        node=sexpdata.loads(raw[slice(*r['source_span'])].decode())
        if str(one(node,'fill',['none'])[0]) not in ('yes','solid'):continue
        if float(one(one(node,'stroke'),'width')[0])!=0:
            fail('T01_SOURCE_CIRCLE_FORM_UNSUPPORTED',r['id'])
        occurrences[r['geometry_sha256']].append(i)
    sites=[]
    for h,indexes in occurrences.items():
        g=shapes[indexes[0]];aliases=sorted(rows[i]['id'] for i in indexes)
        sites.append(dict(source_id=aliases[0],aliases=aliases,core=g,center=[g.centroid.x,g.centroid.y],
                          radius=(g.bounds[2]-g.bounds[0]+g.bounds[3]-g.bounds[1])/4,
                          geometry_sha256=h,indexes=indexes))
    sites.sort(key=lambda s:(s['center'][1],s['center'][0],s['source_id']))
    raw_ids,_=_raw_filled_circle_scan(raw,crop,128)
    if sorted(raw_ids)!=sorted(sid for s in sites for sid in s['aliases']):
        fail('T01_RAW_CIRCLE_COVERAGE_MISMATCH','raw source/cache circle occurrences')
    if len(sites)!=binding['unique_sites'] or sum(len(s['aliases']) for s in sites)!=binding['occurrences']:
        fail('T01_TARGET_COVERAGE_MISMATCH','site/alias counts')
    components={}
    for s in sites:
        seed=s['indexes'][0]
        if seed not in components:
            seen={seed};pending=[seed]
            while pending:
                i=pending.pop()
                for j in tree.query(shapes[i],predicate='intersects'):
                    j=int(j)
                    if j not in seen:seen.add(j);pending.append(j)
            component=hashlib.sha256('\n'.join(sorted(rows[i]['id'] for i in seen)).encode()).hexdigest()
            components.update({i:component for i in seen})
        s['physical_contact_group']=components[seed];s['enlarged_radius']=1.5*s['radius']
    siteids={s['source_id'] for s in sites}
    if not set(binding['reviewed_pair']+binding['recess_source_ids'])<=siteids:
        fail('T01_BOUND_EXCEPTION_OR_PAIR_MISSING','source identities')
    return raw,rows,shapes,sites
