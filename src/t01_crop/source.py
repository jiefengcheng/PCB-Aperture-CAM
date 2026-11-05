from src.native_preparation import native_loads
"""Dynamic ROI coverage from native bytes and the PCB data ABI source cache."""
from collections import defaultdict
import hashlib
import json
import sexpdata
from shapely import STRtree,from_wkb
from shapely.geometry import box
from src.native_reference import one
from src.crop_circle_sources import _raw_filled_circle_scan
from src.stage_abi.store import digest
from src.stage_abi.contracts import fail
from .policy import validate_binding
from .paging import read_pages
from src.stage_abi.preparation import prepared_tree as STRtree

def sites_from_cache(raw,manifest,shapes,bounds):
    rows=manifest['objects'];viewport=box(*bounds);occurrences=defaultdict(list)
    for i,(r,g) in enumerate(zip(rows,shapes,strict=True)):
        if r['kind']!='gr_circle' or not g.intersects(viewport):continue
        node=native_loads(raw[slice(*r['source_span'])].decode())
        if str(one(node,'fill',['none'])[0]) not in ('yes','solid'):continue
        if float(one(one(node,'stroke'),'width')[0])!=0:fail('T01_SOURCE_CIRCLE_FORM_UNSUPPORTED',r['id'])
        occurrences[r['geometry_sha256']].append(i)
    sites=[]
    for h,indices in occurrences.items():
        g=shapes[indices[0]];aliases=sorted(rows[i]['id'] for i in indices)
        sites.append(dict(source_id=aliases[0],aliases=aliases,core=g,center=[g.centroid.x,g.centroid.y],
            radius=(g.bounds[2]-g.bounds[0]+g.bounds[3]-g.bounds[1])/4,geometry_sha256=h,indexes=indices))
    sites.sort(key=lambda s:(s['center'][1],s['center'][0],s['source_id']))
    raw_ids,_=_raw_filled_circle_scan(raw,viewport,128)
    if sorted(raw_ids)!=sorted(a for s in sites for a in s['aliases']):fail('T01_RAW_CIRCLE_COVERAGE_MISMATCH','Independent native span scan')
    if not sites:fail('T01_ROI_NO_SUPPORTED_CIRCLES','No filled zero-stroke graphic circles in ROI')
    tree=STRtree(shapes);components={}
    for s in sites:
        seed=s['indexes'][0]
        if seed not in components:
            seen={seed};todo=[seed]
            while todo:
                i=todo.pop()
                for j in tree.query(shapes[i],predicate='intersects'):
                    j=int(j)
                    if j not in seen:seen.add(j);todo.append(j)
            key=hashlib.sha256('\n'.join(sorted(rows[i]['id'] for i in seen)).encode()).hexdigest()
            components.update({i:key for i in seen})
        s['physical_contact_group']=components[seed];s['enlarged_radius']=1.5*s['radius']
    return raw,rows,sites

def context(store,scene,policy):
    b=validate_binding(store.get_json(policy['binding_ref'],kind='t01-binding'))
    raw=store.get(b['source_ref'],kind='native-source');blob=store.get(b['manifest_ref'],kind='native-manifest')
    roi_blob=store.get(b['roi_ref'],kind='roi-binding')
    if digest(raw)!=b['source_sha256'] or digest(blob)!=b['manifest_sha256'] or digest(roi_blob)!=b['roi_sha256']:
        fail('T01_SOURCE_BINDING_MISMATCH','Native source, data manifest or ROI')
    manifest=store.get_json(b['manifest_ref'],kind='native-manifest');objects={o['source_id']:o for o in scene['objects']}
    if b['schema']=='t01-crop-binding/2':
        inventory,index=read_pages(store,b['source_inventory_ref'],binding=dict(source_sha256=b['source_sha256'],manifest_sha256=b['manifest_sha256']),kind='t01-source-inventory',identity=lambda r:r['source_id'])
        if inventory!=scene['objects'] or index['total_records']!=b['source_objects']:fail('T01_SOURCE_PAGE_COVERAGE_MISMATCH','Complete original source pages')
    roi=json.loads(roi_blob)
    if (roi.get('facts',{}).get('location_verified') is not True or roi.get('bounds_mm')!=b['viewport_mm']
        or roi.get('uncertainty_mm')!=b['location_uncertainty_mm']):fail('T01_VERIFIED_ROI_BINDING_MISMATCH','Data-ABI receipt bounds/uncertainty')
    directives={s for pair in b['reviewed_pairs'] for s in pair}|set(b['recess_source_ids'])
    if (manifest['source_sha256']!=b['source_sha256'] or len(manifest['objects'])!=b['source_objects'] or
        len(scene['objects'])!=len(objects) or not directives<=objects.keys() or
        scene['source_sha256']!=b['source_sha256'] or scene['viewport_mm']!=b['viewport_mm'] or
        scene['layer']!='F.Cu' or scene['units']!='mm' or len(objects)!=b['source_objects'] or
        set(objects)!={r['id'] for r in manifest['objects']}):fail('T01_SOURCE_COVERAGE_MISMATCH','Complete source/ROI scene')
    shapes=[]
    for r in manifest['objects']:
        o=objects[r['id']];data=store.get(o['original_ref'],kind='geometry');start,end=r['source_span']
        if (o['original_ref']!=o['geometry_ref'] or digest(data)!=r['geometry_sha256'] or
            r['source_sha256']!=b['source_sha256'] or not 0<=start<end<=len(raw) or
            r['id']!=f'{b["source_sha256"]}:bytes:{start}:{end}' or 'F.Cu' not in r['layers']):fail('T01_ORIGINAL_SOURCE_REQUIRED',r['id'])
        shapes.append(from_wkb(data))
    from src.t01_canonical import full_bounds
    _,rows,sites=sites_from_cache(raw,manifest,shapes,full_bounds(shapes))
    return b,raw,rows,shapes,sites
