#!/usr/bin/env python3
"""Replay saved C01 T05 patches from frozen owners and source-bound route spans.

Same-assistant geometric replay, not independent or native qualification.
"""
import argparse, hashlib, json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from shapely import from_wkb,to_wkb,STRtree
from shapely.geometry import LineString
from shapely.ops import unary_union,substring
from src.crop_circle_sources import verify_assets
from src.trace_land_junctions import propose_taper,verify_taper,JunctionContract

def sha(b):return hashlib.sha256(b).hexdigest()
def read(p):return json.loads(p.read_text())
def main(freeze,width,definitions,cache,proposal,out):
    for p in [freeze,width,definitions,cache,proposal]:
        if not p.resolve().is_relative_to(ROOT):raise ValueError('PROJECT_LOCAL_INPUTS_REQUIRED')
    if out.exists() or not out.resolve().is_relative_to(ROOT/'out'):raise ValueError('FRESH_PROJECT_OUTPUT_REQUIRED')
    assets=verify_assets();f=read(freeze/'FREEZE_RECEIPT.json');P=freeze/'frozen'
    for name,h in f['file_bindings'].items():assert sha((P/name).read_bytes())==h
    result=read(proposal/'RESULT.json');wr=read(width/'RESULT.json')
    assert result['freeze_receipt_sha256']==sha((freeze/'FREEZE_RECEIPT.json').read_bytes())
    assert result['T04_result_sha256']==sha((width/'RESULT.json').read_bytes())
    assert result['contract']==JunctionContract().__dict__
    for name,h in result['implementation_sha256'].items():assert sha((ROOT/name).read_bytes())==h
    bank=read(cache/'source_manifest.json');assert bank['source_sha256']==f['source_sha256']==wr['source_sha256'];original={}
    for r in bank['objects']:
        b=(cache/'source_wkb'/f"{r['geometry_sha256']}.wkb").read_bytes();assert sha(b)==r['geometry_sha256'];original[r['id']]=from_wkb(b)
    current=dict(original);lands={}
    for r in read(P/'report.json')['decisions']:
        b=(P/r['geometry']['dynamic']).read_bytes();assert sha(b)==r['candidate_sha256'];g=from_wkb(b)
        for sid in r['aliases']:current[sid]=g
        lands[r['source_id']]=(g,r['aliases'])
    paths={r['path_id']:r for r in read(definitions/'UNIFORM_SOURCE_PATHS.json')['paths']};routes={r['component_id']:r for r in read(width/'CONSTRUCTION.json')};traces={};n=0
    for rid,r in routes.items():
        parts=[]
        for part in r['primitives']:
            sid=part['source_id'];b=(width/'nominal_source_parts'/f'{sha(sid.encode())}.wkb').read_bytes();assert sha(b)==part['nominal_candidate_wkb_sha256'];current[sid]=from_wkb(b);parts.append(current[sid]);n+=1
        traces[rid]=unary_union(parts)
    ids=sorted(current);tree=STRtree([current[s] for s in ids]);grown=[r for r in read(proposal/'DECISIONS.json') if r['status']=='GROWN'];patches={};checks=[]
    for r in grown:
        rid=r['route_id'];rr=routes[rid];line=LineString(paths[rid]['ordered_route_points_mm']);end=r['source_interval_end_arclength_mm']
        approach=substring(line,0 if r['direction']=='forward' else line.length,end)
        assert list(map(list,approach.coords))==r['route_toward_land']
        assert r['width_mm']==rr['uniform_nominal_width_mm'] and r['trace_part_ids']==rr['complete_source_ids']
        # Native rectangles use their unchanged source operands; circles use frozen T01.
        land,aliases=lands.get(r['land_source_id'],(current[r['land_source_id']],r['land_aliases']))
        assert aliases==r['land_aliases']
        assert unary_union([original[s] for s in rr['complete_source_ids']]).intersection(original[r['land_source_id']]).area>1e-12
        p=propose_taper(list(approach.coords),traces[rid],land,r['width_mm'],alpha=r['alpha'])
        for key,suffix in [('patch',''),('window','_window')]:
            b=(proposal/'patches'/f"{r['id']}{suffix}.wkb").read_bytes();assert sha(b)==r[key+'_sha256']==sha(to_wkb(p[key]))
        patches[r['id']]=(r,p,land)
    for cid,(r,p,land) in patches.items():
        allowed=set(r['trace_part_ids'])|set(r['land_aliases'])
        # Query the entire scene from the reconstructed window, independently of
        # the generator's approach-reach optimization.
        foreign=[dict(id=ids[int(i)],geometry=current[ids[int(i)]]) for i in tree.query(p['window'].buffer(JunctionContract().construction_gap_mm)) if ids[int(i)] not in allowed]
        foreign += [dict(id='T05:'+other,geometry=q['patch']) for other,(_,q,_) in patches.items() if other!=cid]
        check=verify_taper(p,traces[r['route_id']],land,foreign);assert check['passed'],(cid,check['failures']);checks.append(dict(id=cid,check=check))
    before_blob=(width/'after.wkb').read_bytes();assert sha(before_blob)==result['T04_predecessor_sha256']==wr['after_sha256'];before=from_wkb(before_blob)
    after=before.union(unary_union([p['patch'] for _,p,_ in patches.values()]));assert sha(to_wkb(after))==result['after_sha256']==sha((proposal/'after.wkb').read_bytes())
    assert before.difference(after).area<=1e-12
    for name,h in f['file_bindings'].items():assert sha((P/name).read_bytes())==h
    out.mkdir();(out/'FINAL_CHECKS.json').write_text(json.dumps(checks,indent=2)+'\n')
    receipt=dict(status='PASS_SAME_ASSISTANT_SOURCE_BOUND_T05_REPLAY',assets=assets,proposal_result_sha256=sha((proposal/'RESULT.json').read_bytes()),after_sha256=result['after_sha256'],reconstructed_patches=len(patches),frozen_files=len(f['file_bindings']),unchanged_T04_parts=n,foreign_scope='Entire current source scene queried from reconstructed window, plus every other accepted T05 patch',source_routes_and_widths='UNCHANGED',T02='NOT_APPLIED',limitations='Declared stations and robust eroded witness; no native, electrical, manufacturing or independent acceptance')
    (out/'REPLAY.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ['freeze','width','definitions','cache','proposal','out']:parser.add_argument(name,type=Path)
    main(**vars(parser.parse_args()))
