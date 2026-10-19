"""Explicit diagnostic selections, never implicit edit authorization."""
import copy
import math
import time
from collections import Counter
from shapely import from_wkb
from shapely.geometry import box
from .revision_catalog import CatalogError,canonical,digest

def region_query(catalog,revision,bounds_mm,layer,*,limit=1000,work_limit=100000):
    if len(bounds_mm)!=4 or not all(isinstance(v,(int,float)) and math.isfinite(v) for v in bounds_mm) or bounds_mm[0]>bounds_mm[2] or bounds_mm[1]>bounds_mm[3]:raise CatalogError('INVALID_REGION_BOUNDS')
    if bounds_mm[0]==bounds_mm[2] or bounds_mm[1]==bounds_mm[3]:raise CatalogError('DEGENERATE_REGION_UNSUPPORTED')
    if not isinstance(limit,int) or not 0<=limit<=100000 or not isinstance(work_limit,int) or not 0<=work_limit<=100000:raise CatalogError('INVALID_REGION_BUDGET')
    start=time.perf_counter();manifest=catalog._validated_snapshot(revision);region=box(*bounds_mm)
    rows=[];container_exclusions=0;omissions=Counter();omission_sample=[];work=0;candidates=0;returned_bytes=0;status='COMPLETE'
    for record in manifest['objects']:
        if work>=work_limit:status='WORK_BUDGET_EXCEEDED';break
        work+=1
        if layer not in record.get('layers',[]):continue
        if str(record.get('unsupported_reason','')).startswith('CONTAINER_ONLY'):
            container_exclusions+=1;continue
        key=record.get('geometry_sha256');bounds=record.get('bounds_mm')
        if layer not in record.get('geometry_layers',record.get('layers',[])):
            omissions['LAYER_GEOMETRY_UNAVAILABLE']+=1
            if len(omission_sample)<20:omission_sample.append(record['id'])
            continue
        if not key or bounds is None:
            omissions[record.get('unsupported_reason') or 'GEOMETRY_UNAVAILABLE']+=1
            if len(omission_sample)<20:omission_sample.append(record['id'])
            continue
        a,b,c,d=bounds;x,y,z,w=bounds_mm
        if c<x or a>z or d<y or b>w:continue
        candidates+=1;shape=from_wkb(catalog.read_payload(key))
        if not shape.intersects(region):continue
        if len(rows)>=limit:status='TRUNCATED';break
        encoded_size=len(canonical(record))
        if returned_bytes+encoded_size>32*1024*1024:status='TRUNCATED_BYTE_BUDGET';break
        returned_bytes+=encoded_size;rows.append(copy.deepcopy(record))
    rows.sort(key=lambda r:r['id'])
    return {'revision':revision,'backend':'catalog bbox broad phase + GEOS exact region','status':status,'complete':status=='COMPLETE','engineering_complete':status=='COMPLETE' and not omissions,'records':rows,'result_sha256':digest(canonical(rows)),'query':{'bounds_mm':list(bounds_mm),'layer':layer,'limit':limit,'work_limit':work_limit},'returned_json_bytes':returned_bytes,'result_byte_limit':32*1024*1024,'objects_examined':work,'bbox_candidates':candidates,'non_geometric_container_exclusions':container_exclusions,'unsupported_counts':dict(omissions),'unsupported_sample':omission_sample,'unsupported_sample_limit':20,'scope':'Available nominal geometry on the named layer. Unsupported geometry remains unknown; no no-obstacle acceptance follows.','elapsed_seconds':time.perf_counter()-start}

def select(catalog,revision,*,object_ids=(),native_ids=(),named_groups=(),regions=(),all_objects=False,context_ids=(),writable_ids=(),include_dependencies=True,limit=100000):
    started=time.perf_counter()
    if not isinstance(limit,int) or not 0<=limit<=100000:raise CatalogError('INVALID_SELECTION_LIMIT')
    manifest=catalog._validated_snapshot(revision);by_id={r['id']:r for r in manifest['objects']}
    selected=set(object_ids);context=set(context_ids);native_ids=sorted(set(native_ids));named_groups=sorted(set(named_groups));regions=list(regions)
    if len(selected|context)>limit or len(native_ids)>100000 or len(named_groups)>1000 or len(regions)>1000:raise CatalogError('SELECTION_WORK_BUDGET_EXCEEDED')
    queries=[];expansion=[];native_cache={};expanded_groups=set()
    def unique(native_id):
        if native_id in native_cache:return native_cache[native_id]
        if len(native_cache)>=100000:raise CatalogError('SELECTION_WORK_BUDGET_EXCEEDED')
        q=catalog.query(revision,native_id=native_id,limit=2);queries.append(q)
        if not q['records']:raise CatalogError('MISSING_NATIVE_REFERENCE')
        if not q['complete'] or len(q['records'])!=1:raise CatalogError('AMBIGUOUS_NATIVE_REFERENCE')
        native_cache[native_id]=q['records'][0];return native_cache[native_id]
    if all_objects:
        if len(by_id)>limit:raise CatalogError('INCOMPLETE_SELECTION')
        selected.update(by_id)
    for native_id in native_ids:selected.add(unique(native_id)['id'])
    def expand_group(group,visiting):
        if group['id'] in visiting:raise CatalogError('GROUP_REFERENCE_CYCLE')
        if len(visiting)>=100:raise CatalogError('GROUP_DEPTH_BUDGET_EXCEEDED')
        if group['id'] in expanded_groups:return
        if len(expanded_groups)>=1000:raise CatalogError('SELECTION_WORK_BUDGET_EXCEEDED')
        selected.add(group['id']);visiting=visiting|{group['id']}
        for member in group.get('native_group_members',[]):
            if len(expansion)>=100000:raise CatalogError('SELECTION_WORK_BUDGET_EXCEEDED')
            record=unique(member);selected.add(record['id'])
            expansion.append({'selector_group':group['id'],'member':record['id'],'grant_write':False})
            if record.get('kind')=='group':expand_group(record,visiting)
        expanded_groups.add(group['id'])
    for name in named_groups:
        matches=[r for r in manifest['objects'] if r.get('kind')=='group' and r.get('group_name')==name]
        if not matches:raise CatalogError('MISSING_GROUP_REFERENCE')
        if len(matches)!=1:raise CatalogError('AMBIGUOUS_GROUP_REFERENCE')
        expand_group(matches[0],set())
    for request in regions:
        q=region_query(catalog,revision,request['bounds_mm'],request['layer'],limit=limit,work_limit=request.get('work_limit',100000));queries.append(q)
        if not q['complete']:raise CatalogError('INCOMPLETE_REGION_SELECTION')
        selected.update(r['id'] for r in q['records'])
    if not selected|context<=by_id.keys():raise CatalogError('MISSING_OBJECT_REFERENCE')
    dependencies=set()
    if include_dependencies:
        for uid in sorted(selected|context):
            visited={uid};parent=by_id[uid].get('parent_id')
            while parent is not None:
                if parent in visited:raise CatalogError('PARENT_REFERENCE_CYCLE')
                if parent not in by_id:raise CatalogError('MISSING_PARENT')
                if len(expansion)>=100000:raise CatalogError('SELECTION_WORK_BUDGET_EXCEEDED')
                visited.add(parent);dependencies.add(parent)
                expansion.append({'source_object':uid,'requires':parent,'role':'retained_container_dependency','grant_write':False})
                parent=by_id[parent].get('parent_id')
    requested=selected|context|dependencies
    if len(requested)>limit:raise CatalogError('INCOMPLETE_SELECTION')
    writable=set(writable_ids)
    if not writable<=selected:raise CatalogError('POLICY_WRITE_OUTSIDE_SELECTION')
    rows=[]
    # Bounded batches avoid SQLite parameter limits for explicit all/large groups.
    ordered=sorted(requested)
    for offset in range(0,len(ordered),512):
        q=catalog.query(revision,ids=ordered[offset:offset+512],limit=512);queries.append({k:v for k,v in q.items() if k!='records'})
        if not q['complete']:raise CatalogError('INCOMPLETE_SELECTION')
        rows.extend(q['records'])
    if {r['id'] for r in rows}!=requested:raise CatalogError('MISSING_OBJECT_REFERENCE')
    unsupported=[{'id':r['id'],'reason':r.get('unsupported_reason') or 'GEOMETRY_UNAVAILABLE'} for r in rows if not r.get('geometry_sha256') and r.get('kind') not in ('footprint','module','group') and not str(r.get('unsupported_reason','')).startswith('CONTAINER_ONLY')]
    return {'selection_contract':'pcb-selection/2','permission_basis':'Caller-supplied allowlist; requires the separately bound operation contract before execution.','geometry_coverage':{'unsupported_count':len(unsupported),'unsupported_sample':unsupported[:20],'scope':'Selected diagnostic records; containers have separately inventoried children.'},'revision':revision,'status':'COMPLETE','complete':True,'records':rows,'result_sha256':digest(canonical(rows)),'selected_ids':sorted(selected),'context_ids':sorted(context-selected),'dependency_ids':sorted(dependencies-selected-context),'writable_ids':sorted(writable),'expansion':expansion,'query_receipts':queries,'native_export':'UNSUPPORTED: preserved-source diagnostic bundle only','diagnostic_only':True,'elapsed_seconds':time.perf_counter()-started,'query_elapsed_seconds_total':sum(q.get('elapsed_seconds',0) for q in queries),'engineering_complete':not unsupported and all(q.get('engineering_complete',True) for q in queries)}
