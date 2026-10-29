#!/usr/bin/env python3
"""Four fixed source-bound diagnostic witnesses; no search or production policy edit."""
import sys
sys.dont_write_bytecode=True
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import argparse, hashlib, json, shutil, subprocess
from dataclasses import asdict
from shapely import from_wkb,to_wkb
from shapely.affinity import scale
from shapely.geometry import box,Point
from src.crop_attachment_diagnostic import bind_circle_attachment,bind_overlapping_feed_attachment,check_attachment_diagnostic
from src.crop_stage_growth import GrowthContract,check_proposal,original_attachment_port
from tools.run_c02_r080_attachment_revision import compute as compute_r080

SITES=('R003','R005','R006','R012')
SOURCE_SPANS={'R003':('1650795:1650921',None),'R005':('1651778:1651902',None),
              'R006':('1652641:1652766',None),'R012':('408354:408443','408262:408351')}


def sha(data):return hashlib.sha256(data).hexdigest()


def compute(predecessor):
    p=Path(predecessor)
    _,base=compute_r080(p)  # unchanged accepted R080 replay, never rectangle search
    scene=base['scene'];raw=base['source'];prefix=sha(raw)+':bytes:'
    contract=GrowthContract();crop=box(*base['bounds'])
    decisions={d['key']:d for d in json.loads((p/'t02/decisions.json').read_text())}
    fixed={sid:sha(to_wkb(g)) for sid,g in scene.replacements.items()}
    bindings={};proposals={};reports=[]
    before=base['after'];after=before
    for site in SITES:
        d=decisions[site];sid=d['source_id'];ob,feed=SOURCE_SPANS[site]
        binding=(bind_circle_attachment(raw,sid,prefix+ob) if feed is None else
                 bind_overlapping_feed_attachment(raw,sid,prefix+ob,prefix+feed))
        bindings[sid]=binding
        core=scene.objects[sid]['geometry'];cap=scale(core,1.25,1.25,origin=core.centroid)
        assert sha(binding.target_wkb)==sha(to_wkb(core))
        assert sha(binding.obstacle_wkb)==sha(to_wkb(scene.objects[binding.obstacle_id]['geometry']))
        if feed is not None:assert sha(binding.feed_wkb)==sha(to_wkb(scene.objects[binding.feed_id]['geometry']))
        neighbors=scene.neighbors(sid,cap)
        checks=[]
        for name,factors in [('FULL_CAP',(1.25,1.25)),('X',(1.001,1.0)),('Y',(1.0,1.001))]:
            proposal=scale(core,*factors,origin=core.centroid)
            q=check_attachment_diagnostic(core,proposal,neighbors,binding,crop=crop,cap=cap,contract=contract)
            ordinary=check_proposal(core,proposal,neighbors,crop=crop,cap=cap,contract=contract)
            saved=d['full_1p25_cap_check'] if name=='FULL_CAP' else d['next_axis_increment_diagnostics'][name]
            checks.append(dict(name=name,axis_factors_xy=list(factors),proposal_sha256=sha(to_wkb(proposal)),
                               saved_REV05_check=saved,current_full_context_ordinary_check=ordinary,diagnostic_check=q))
        selected=next(q for q in checks if q['name']=='X')
        assert selected['diagnostic_check']['passed'],(site,selected)
        assert not checks[0]['diagnostic_check']['passed'],(site,'FULL_CAP_MUST_REMAIN_REJECTED')
        proposal=scale(core,1.001,1.,origin=core.centroid)
        exposed=proposal.difference(before)
        assert exposed.area>1e-10
        after=after.union(proposal.difference(core))
        proposals[sid]=proposal
        # Same original finite port as previously used for the source attachment.
        port=original_attachment_port(core,from_wkb(binding.obstacle_wkb) if feed is None else from_wkb(binding.feed_wkb),binding.width_mm,contract)
        original_port_neighbor=binding.obstacle_id if feed is None else binding.feed_id
        old_port=next(q for q in selected['current_full_context_ordinary_check']['pairs'] if q['neighbor_id']==original_port_neighbor)
        assert port.area==old_port['attachment_port_area_mm2']
        reports.append(dict(site=site,source_id=sid,obstacle_source_id=binding.obstacle_id,
            feed_source_id=binding.feed_id,mode=binding.mode,original_fragments_sha256=list(binding.fragments_sha256),
            source_sha256=binding.source_sha256,axis_factors_xy=[1.001,1.0],fixed_witness_basis='Retained isolated +0.001 X factor probe; no new search.',
            new_exposed_copper_mm2=exposed.area,target_added_area_mm2=proposal.difference(core).area,
            zoom_center_mm=list(exposed.representative_point().coords[0]),
            original_port_unchanged=True,port_wkb_sha256=sha(to_wkb(port)),probes=checks,
            status='PROPOSED_POSITIVE_GROWTH_PENDING_AUDIT'))
    for sid,g in proposals.items():scene.accept(sid,g)
    final=[]
    circle=json.loads((p/'t01/decision.json').read_text());cg=scene.replacements[circle['source_id']]
    center=tuple(cg.centroid.coords[0])
    for sid,g in sorted(scene.replacements.items()):
        core=scene.objects[sid]['geometry'];is_circle=sid==circle['source_id']
        cap=(Point(*center).buffer(1.5*circle['original_radius_mm'],quad_segs=128) if is_circle else scale(core,1.25,1.25,origin=core.centroid))
        neighbors=scene.neighbors(sid,cap,circle['aliases'] if is_circle else ())
        q=(check_attachment_diagnostic(core,g,neighbors,bindings[sid],crop=crop,cap=cap,contract=contract) if sid in bindings else
           check_proposal(core,g,neighbors,crop=crop,cap=cap,contract=contract,
               attachment_supports=[base['support']] if sid==base['support'].target_id else ()))
        assert q['passed'],(sid,q)
        final.append(dict(source_id=sid,check=q))
        if sid not in proposals:assert fixed[sid]==sha(to_wkb(g))
    assert before.difference(after).area<=1e-12
    report=dict(schema='four-attachment-fixed-diagnostic/1',source_sha256=sha(raw),contract=asdict(contract),
                predecessor='REV05 + REV08-qualified R080 WKB',predecessor_sha256=sha(to_wkb(before)),
                cumulative_sha256=sha(to_wkb(after)),new_exposed_area_mm2=after.difference(before).area,
                original_or_predecessor_copper_removed_mm2=before.difference(after).area,
                fixed_other_replacements=71,all_final_replacement_checks=75,all_final_checks='PASS_DIAGNOSTIC_MODEL_SPACE',
                previously_qualified_growth_witnesses=70,additional_proposed_witnesses=4,
                accepted_completion_count_unchanged=70,selected_denominator=74,status='PROPOSED_POSITIVE_GROWTH_PENDING_AUDIT',
                freeze_status='NOT_FROZEN',production_checker_changed=False,trace_geometry_or_width_changed=False,
                historical_ledger_changed=False,t03='DEFERRED_PENDING_FINAL_VALID_PREDECESSOR',t04='NOT_RUN',sites=reports,
                limitations=['Diagnostic visible-surface classification requires separate audit; not production acceptance.',
                    'Circle source geometry and its visible surface outside unchanged original ports are preserved.',
                    'Only the original finite ports qualify; no net/component exemptions, no new search.',
                    'No native export, electrical intent or manufacturing claim.'])
    return report,dict(base=base,before=before,after=after,exposed=after.difference(before),proposals=proposals,
                       bindings=bindings,scene=scene,final=final,decisions=decisions)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--predecessor',type=Path,required=True);ap.add_argument('--output',type=Path,required=True)
    a=ap.parse_args();out=a.output.resolve()
    if out.exists() or not out.is_relative_to(ROOT/'out'):raise ValueError('FRESH_PROJECT_OUTPUT_REQUIRED')
    from src.crop_circle_sources import verify_assets,path_for
    integrity=verify_assets()
    report,g=compute(a.predecessor)
    out.mkdir(parents=True)
    for name in ('geometry','visuals','source_fragments','implementation'):(out/name).mkdir()
    report['asset_integrity']=integrity
    for name,data in [('result.json',report),('final_scene_checks.json',g['final'])]:
        (out/name).write_text(json.dumps(data,indent=2,sort_keys=True)+'\n')
    for name in ('before','after','exposed'):(out/f'geometry/{name}.wkb').write_bytes(to_wkb(g[name]))
    from tools.run_c02_growth_coverage import render
    rows=g['base']['coverage'];cores={r['source_id']:g['scene'].objects[r['source_id']]['geometry'] for r in rows}
    notes=['70 previously qualified rectangle witnesses plus four fixed +0.001 X-factor diagnostic proposals.',
           'Red = fixed predecessor. Teal = exact new exposed copper. Gold = original selected rectangles.',
           'All 75 replacements checked cumulatively; 71 remain byte-identical. No trace path/width changes.',
           'Original ports and 20.00/20.10 µm floor/guard unchanged. No component-label exemptions.',
           'PROPOSED only; separate audit required. T02 NOT FROZEN. T03 deferred; T04 NOT_RUN.']
    render(out/'visuals/full_c02.svg','C02 / four source-attachment diagnostics — cumulative proposed scene',g['after'],g['exposed'],g['base']['bounds'],rows,cores,notes)
    for r in report['sites']:
        site=r['site'];sid=r['source_id'];b=g['bindings'][sid];core=cores[sid];proposal=g['proposals'][sid]
        (out/f'geometry/{site}_proposal.wkb').write_bytes(to_wkb(proposal))
        (out/f'geometry/{site}_port.wkb').write_bytes(to_wkb(original_attachment_port(core,from_wkb(b.obstacle_wkb) if b.feed_id is None else from_wkb(b.feed_wkb),b.width_mm,GrowthContract())))
        for label,oid in [('target',sid),('obstacle',b.obstacle_id),('feed',b.feed_id)]:
            if oid is not None:
                start,end=map(int,oid.rsplit(':',2)[1:]);(out/f'source_fragments/{site}_{label}.source').write_bytes(g['base']['source'][start:end])
        x0,y0,x1,y1=core.bounds
        local=[x0-.2,y0-.2,x1+.2,y1+.2]
        detailnotes=[f'{site}: fixed 1.001 × 1.000 centered rectangle; exact exposed addition {r["new_exposed_copper_mm2"]:.12f} mm².',
            'Gold = original rectangle; white = proposal; blue = original neighboring source boundary; teal = exposed addition.',
            'Original source geometry and finite attachment port unchanged. Outside-port guard remains 20.10 µm.',
            'Circle: guard uses its originally visible surface; originally internal primitive boundaries are distinguished.',
            'Feed: exact original local copper overlap fills raw gap; no shared endpoint/electrical-net claim.',
            'PROPOSED diagnostic only, pending designated audit. Not frozen or native-exported.']
        render(out/f'visuals/{site}_local.svg',f'C02 / {site} source-bound neighborhood',g['after'],g['exposed'],local,rows,cores,detailnotes,detail={'candidate':proposal})
        exposed=proposal.difference(g['before']);point=exposed.representative_point();r['zoom_center_mm']=[point.x,point.y]
        zoom=[point.x-.004,point.y-.004,point.x+.004,point.y+.004]
        render(out/f'visuals/{site}_boundary.svg',f'C02 / {site} exact boundary detail — 8 µm square',g['after'],g['exposed'],zoom,[],{},
            [f'Located at exact exposed-addition representative point ({point.x:.9f}, {point.y:.9f}) mm.',
             'Red = predecessor copper; teal = actual exposed addition. Same geometry, enlarged view; no exaggeration.',
             f'Full source identity: {sid}', 'PROPOSED fixed diagnostic; no accepted geometry overwritten.'])
        path=out/f'visuals/{site}_local.svg';text=path.read_text().replace('stroke-width="0.004"','stroke-width="0.00015"').replace('stroke-width="0.003"','stroke-width="0.00015"')
        overlay=f'<path d="{path_for(from_wkb(b.obstacle_wkb))}" fill="none" stroke="#68bdff" stroke-width="0.0003"/>'
        overlay+=f'<path d="M {point.x-.008} {point.y} H {point.x+.008} M {point.x} {point.y-.008} V {point.y+.008}" stroke="#ffffff" stroke-width="0.0005"/>'
        path.write_text(text.replace('</svg>',overlay+'</svg>',1))
    (out/'result.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    for svg in (out/'visuals').glob('*.svg'):
        subprocess.run(['sips','-s','format','png',str(svg),'--out',str(svg.with_suffix('.png'))],capture_output=True,check=True)
    page='<!doctype html><meta charset="utf-8"><title>C02 four diagnostics</title><style>body{font:18px system-ui;max-width:1800px;margin:auto}img{width:100%}</style><h1>C02: four fixed attachment diagnostics</h1><p>70 qualified witnesses remain unchanged; four additional proposed witnesses await audit. T02 NOT FROZEN. Actual geometry at full, local and boundary scales.</p><img src="visuals/full_c02.png">'
    for r in report['sites']:
        k=r['site'];page+=f'<h2>{k} — proposed only</h2><img src="visuals/{k}_local.png"><img src="visuals/{k}_boundary.png">'
    (out/'index.html').write_text(page+'<a href="result.json">Exact geometry/source/clearance evidence</a></body>')
    print(json.dumps(dict(output=str(out),sites=len(report['sites']),positive_proposals=4,checks=75,status=report['status'])))


if __name__=='__main__':main()
