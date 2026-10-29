#!/usr/bin/env python3
"""Retain solver controls and deterministic geometric visual evidence.

These artificial routes are controls, never source C02 growth proposals.
"""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import hashlib,json,subprocess
from shapely.geometry import box
from shapely.ops import unary_union
from shapely import to_wkb
from src.bounded_width_solver import solve_width_scales
from src.uniform_trace_width_v2 import construct_uniform_width,FAMILY
from src.trace_width_clearance import verify_width_scene
from tests.test_uniform_trace_width import fixture
from tools.run_c02_growth_coverage import render


def main():
    out=Path(sys.argv[1]);assert not out.exists();out.mkdir(parents=True)
    summaries=[]
    for name,ys,members,remote,budget in [
        ('SINGLETON_CEILING',[0],{'g':['0']},False,36),
        ('SINGLETON_REMOTE_LIMIT',[0],{'g':['0']},True,36),
        ('PARALLEL_COMMON_SCALE',[0,.17],{'g':['0','1']},False,36),
        ('BUDGET_DOES_NOT_PROVE_MAXIMUM',[0],{'g':['0']},True,2)]:
        folder=out/name;folder.mkdir()
        parts=[f'(segment (start 0 {y}) (end 30 {y}) (width 0.1) (layer F.Cu) (net 0))' for y in ys]
        source,record,rows,blobs=fixture(parts)
        chains={str(i):dict(component_id=str(i),source_ids=[sid]) for i,sid in enumerate(record['source_ids'])}
        fixed=[dict(id='remote',geometry=box(29,.09,31,.2))] if remote else []
        def build(scales):
            traces=[];construction=[]
            for gid,cids in members.items():
                for cid in cids:
                    r,_,original,candidate=construct_uniform_width(source,chains[cid],rows,blobs,scales[gid])
                    construction.append(r)
                    traces.append(dict(id=cid,original=original,candidate=candidate,verified_original_width_mm=.1))
            return traces,construction
        def evaluate(scales):
            traces,_=build(scales)
            return verify_width_scene(traces,fixed)
        result=solve_width_scales(list(members),evaluate,geometry_family=FAMILY,max_steps=budget)
        traces,construction=build(result['selected_scales'])
        check=evaluate(result['selected_scales'])
        assert check['passed'] and result['passed']
        assert result['maximum_established']==(budget==36)
        before=unary_union([r['original'] for r in traces]+[r['geometry'] for r in fixed])
        after=unary_union([r['candidate'] for r in traces]+[r['geometry'] for r in fixed])
        for label,g in [('before',before),('after',after)]:
            (folder/f'{label}.wkb').write_bytes(to_wkb(g))
        for label,obj in [('SOLVER',result),('FINAL_CHECK',check),('CONSTRUCTION',construction)]:
            (folder/f'{label}.json').write_text(json.dumps(obj,indent=2,sort_keys=True)+'\n')
        (folder/'SOURCE.txt').write_bytes(source)
        bounds=[28.5,-.12,30.25,.3] if remote else [14,-.12,16,.3]
        for label,g in [('before',before),('after',after)]:
            svg=folder/f'{label}.svg'
            notes=[f'SYNTHETIC CONTROL — not source PCB. {name}; {label}.',
                f'Common nominal scale {result["selected_scales"]["g"]:.9f}; ceiling 1.5; verified model maximum: {result["maximum_established"]}.',
                'Entire 30 mm fixed route checked. Remote obstacle, where present, lies at x=29 mm.',
                'One nominal width on the complete trace. Positive geometry includes a 10 nm conservative verification margin.',
                f'Finite-surface construction guard 20.10 micrometres; {result["evaluation_count"]} full-scene evaluations.',
                'Red = synthetic copper union; teal = added verification envelope. No C02 source width changed.']
            render(svg,f'SYNTHETIC width solver / {name} / {label}',g,g.difference(before),bounds,[],{},notes)
            caption='Actual ORG finite-width copper · 850c4c74d55717a7 · source-bound geometric candidate'
            text=svg.read_text();assert text.count(caption)==1
            svg.write_text(text.replace(caption,'SYNTHETIC finite-width solver control · generated test geometry · not source PCB'))
            subprocess.run(['sips','-s','format','png',str(svg),'--out',str(folder/f'{label}.png')],check=True,capture_output=True)
        summaries.append(dict(name=name,scope='SYNTHETIC_ONLY',selected_scales=result['selected_scales'],
            passed=result['passed'],maximum_established=result['maximum_established'],evaluations=result['evaluation_count'],
            after_sha256=hashlib.sha256(to_wkb(after)).hexdigest()))
    (out/'CONTROL_RECEIPTS.json').write_text(json.dumps(summaries,indent=2,sort_keys=True)+'\n')
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Width solver controls</title><style>body{font:18px system-ui;margin:24px;color:#142a3f}img{width:100%}</style><h1>Synthetic width solver controls — no source PCB growth</h1>'+''.join(f'<h2>{r["name"]}</h2><img src="{r["name"]}/before.png"><img src="{r["name"]}/after.png">' for r in summaries))
    print(json.dumps(summaries))


if __name__=='__main__':main()
