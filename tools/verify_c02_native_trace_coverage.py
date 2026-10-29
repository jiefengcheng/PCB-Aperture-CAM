#!/usr/bin/env python3
"""Re-derive crop seeds and complete same-width source closure from raw inputs.

This verifier does not consume the earlier endpoint-component inventory or its
grouping routines. It makes native trace coverage a source-derived assertion.
"""
import sys,json,hashlib,re
from pathlib import Path
from decimal import Decimal
from collections import defaultdict,deque
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from shapely import from_wkb
from shapely.geometry import box
from src.crop_circle_sources import verify_assets


def main():
    pre,definitions,group_dir,out=map(Path,sys.argv[1:]);assert not out.exists()
    integrity=verify_assets();raw=(pre/'inputs/ORG_source.kicad_pcb').read_bytes();source_sha=hashlib.sha256(raw).hexdigest()
    bank=json.loads((pre/'inputs/source_manifest.json').read_text());d=json.loads((definitions/'UNIFORM_SOURCE_PATHS.json').read_text());groups=json.loads((group_dir/'PARALLEL_MEMBERSHIP.json').read_text())
    assert bank['source_sha256']==d['source_sha256']==source_sha
    crop=box(*d['viewport_mm']);objects={};nodes=defaultdict(set);seeds=set();unqualified=[]
    for r in bank['objects']:
        if r['layers']!=['F.Cu'] or r['coverage']!='GEOMETRY_AVAILABLE':continue
        if r['kind'] not in ('segment','arc'):
            if r['kind']=='gr_poly' and box(*r['bounds_mm']).intersects(crop):unqualified.append(r['id'])
            continue
        lo,hi=r['source_span'];assert r['id']==f'{source_sha}:bytes:{lo}:{hi}'
        fragment=raw[lo:hi];width=re.search(rb'\(width\s+([^\s()]+)\)',fragment);assert width
        w=Decimal(width[1].decode());assert float(w)==r['trace_width_mm'] and w>0
        endpoints=[]
        for field in ['start','end']:
            m=re.search(rb'\('+field.encode()+rb'\s+([^\s()]+)\s+([^\s()]+)\)',fragment);assert m
            endpoints.append(tuple(Decimal(v.decode()) for v in m.groups()))
        objects[r['id']]=dict(width=w,endpoints=endpoints,geometry_sha256=r['geometry_sha256'])
        for p in endpoints:nodes[(w,p)].add(r['id'])
        if box(*r['bounds_mm']).intersects(crop):
            blob=(pre/f'inputs/source_wkb/{r["geometry_sha256"]}.wkb').read_bytes()
            assert hashlib.sha256(blob).hexdigest()==r['geometry_sha256']
            if from_wkb(blob).intersects(crop):seeds.add(r['id'])
    queue=deque(sorted(seeds));closure=set()
    while queue:
        sid=queue.popleft()
        if sid in closure:continue
        closure.add(sid);r=objects[sid]
        for p in r['endpoints']:queue.extend(sorted(nodes[(r['width'],p)]-closure))
    assigned=[sid for r in d['paths'] for sid in r['source_ids']]
    if len(assigned)!=len(set(assigned)):raise ValueError('SOURCE_PRIMITIVE_ASSIGNED_MULTIPLE_TIMES')
    if set(assigned)!=closure:raise ValueError('DECLARED_ROUTES_DO_NOT_EQUAL_COMPLETE_NATIVE_SOURCE_CLOSURE')
    assert seeds<=closure and len(seeds)==d['crop_seed_count']
    route_checks=[]
    for r in d['paths']:
        source_ids=set(r['source_ids']);edges=r['ordered_source_edges']
        walked=[sid for e in edges for sid in e['source_alias_ids']]
        assert len(walked)==len(set(walked)) and set(walked)==source_ids
        previous=None;start=None
        for edge in edges:
            a=tuple(Decimal(v) for v in edge['start_decimal_mm']);b=tuple(Decimal(v) for v in edge['end_decimal_mm'])
            if previous is not None:assert previous==a
            if start is None:start=a
            previous=b
            hashes=set()
            for sid in edge['source_alias_ids']:
                o=objects[sid];assert sorted(o['endpoints'])==sorted([a,b])
                if float(o['width'])!=r['uniform_original_width_mm']:raise ValueError('DECLARED_ROUTE_WIDTH_DIFFERS_FROM_NATIVE_SOURCE')
                hashes.add(o['geometry_sha256'])
            assert len(hashes)==1,'NONEXACT_SOURCE_ALIAS'
        if r['route_type']=='CLOSED_UNIFORM_SOURCE_ROUTE':assert previous==start
        route_checks.append(dict(path_id=r['path_id'],source_count=len(source_ids),ordered_edge_count=len(edges),status='PASS_NATIVE_IDENTITIES_WIDTHS_ALIASES_CONTINUITY'))
    visible={r['path_id'] for r in d['paths'] if r['definition_status']=='VISIBLE_COMPLETE_UNIFORM_PATH_PROPOSAL_CONTACT_CHECKS_RETAINED'}
    grouped=[cid for r in groups['groups'] for cid in r['members']]
    assert len(grouped)==len(set(grouped)) and set(grouped)==visible
    result=dict(status='PASS_RAW_SOURCE_NATIVE_TRACE_COVERAGE_AND_ROUTE_CONTINUITY',asset_integrity=integrity,source_sha256=source_sha,
        whole_source_native_traces=len(objects),crop_seeds=len(seeds),complete_same_width_source_closure=len(closure),defined_routes=len(d['paths']),visible_routes=len(visible),groups=len(groups['groups']),
        missing_crop_source_ids=sorted(seeds-set(assigned)),extra_or_missing_closure_source_ids=sorted(closure^set(assigned)),
        trace_like_polygon_context_source_ids=sorted(unqualified),polygon_scope='No verified native trace width/route asserted for polygon copper; context remains fixed. Rectangles are handled in frozen T02.',
        native_route_checks=route_checks,limitation='Coverage and declared geometric continuity, not electrical connectivity or parallel-group qualification; no copper edits')
    out.mkdir();(out/'NATIVE_COVERAGE.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n');print(json.dumps({k:v for k,v in result.items() if k not in ('native_route_checks','trace_like_polygon_context_source_ids')}))


if __name__=='__main__':main()
