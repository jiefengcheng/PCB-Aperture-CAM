#!/usr/bin/env python3
"""One R080 positive-control proposal; all other REV05 replacements stay fixed."""
import sys
sys.dont_write_bytecode = True
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import argparse, hashlib, json, shutil, subprocess
from dataclasses import asdict
from shapely import from_wkb,to_wkb
from shapely.affinity import scale
from shapely.geometry import box,Point
from src.crop_attachment_support import bind_original_trace_attachment
from src.crop_stage_growth import GrowthContract,GrowthScene,check_proposal

PREDECESSOR_ZIP_SHA='0b5ab41c6abc3b1bf3d914f4e3d32fbaa4616e38b430cc0d7f10e648aa5b5824'


def sha(blob):return hashlib.sha256(blob).hexdigest()


def compute(predecessor):
    p=Path(predecessor)
    result=json.loads((p/'result.json').read_text())
    raw=(p/'inputs/ORG_source.kicad_pcb').read_bytes()
    assert sha(raw)==result['source_sha256']
    bank_bytes=(p/'inputs/source_manifest.json').read_bytes()
    bank=json.loads(bank_bytes);objects=[]
    for r in bank['objects']:
        b=(p/'inputs/source_wkb'/f'{r["geometry_sha256"]}.wkb').read_bytes()
        assert sha(b)==r['geometry_sha256']
        objects.append({'source_id':r['id'],'geometry':from_wkb(b),'trace_width_mm':r['trace_width_mm']})
    contract=GrowthContract(**result['contract']);scene=GrowthScene(objects,contract)
    circle=json.loads((p/'t01/decision.json').read_text())
    circle_geom=from_wkb((p/'t01/candidate.wkb').read_bytes())
    scene.accept(circle['source_id'],circle_geom)
    decisions=json.loads((p/'t02/decisions.json').read_text());assert len(decisions)==74
    unchanged_hashes={circle['source_id']:sha(to_wkb(circle_geom))}
    for d in decisions:
        b=(p/f't02/{d["key"]}_candidate.wkb').read_bytes();assert sha(b)==d['candidate_sha256']
        scene.accept(d['source_id'],from_wkb(b));unchanged_hashes[d['source_id']]=sha(b)
    target=next(d for d in decisions if d['key']=='R080')
    sid=target['source_id'];prefix=result['source_sha256']+':bytes:'
    assert sid==prefix+'1958147:1958328'
    assert not target['objective_completed']
    support=bind_original_trace_attachment(raw,sid,prefix+'1492399:1492516',prefix+'1492213:1492303')
    core=scene.objects[sid]['geometry'];crop=box(*result['viewport_mm'])
    proposal=scale(core,1.01,1.01,origin=core.centroid)
    cap=scale(core,1.25,1.25,origin=core.centroid)
    neighbors=scene.neighbors(sid,cap)
    old_check=check_proposal(core,proposal,neighbors,crop=crop,cap=cap,contract=contract)
    check=check_proposal(core,proposal,neighbors,crop=crop,cap=cap,contract=contract,attachment_supports=[support])
    assert not old_check['passed'] and check['passed']
    negative=check_proposal(core,cap,neighbors,crop=crop,cap=cap,contract=contract,attachment_supports=[support])
    assert not negative['passed'] and any(f['reason']=='NEW_SOURCE_CONTACT' for f in negative['failures'])
    before=from_wkb((p/'t02/cumulative.wkb').read_bytes())
    t01=from_wkb((p/'t01/cumulative.wkb').read_bytes())
    after=before.union(proposal.difference(core));exposed=after.difference(before)
    assert exposed.area>1e-10 and before.difference(after).area<=1e-12
    scene.accept(sid,proposal)
    finalchecks=[]
    center=tuple(circle_geom.centroid.coords[0])
    for rid,g in sorted(scene.replacements.items()):
        original=scene.objects[rid]['geometry'];is_circle=rid==circle['source_id']
        bound=Point(*center).buffer(circle['original_radius_mm']*1.5,quad_segs=128) if is_circle else scale(original,1.25,1.25,origin=original.centroid)
        q=check_proposal(original,g,scene.neighbors(rid,bound,circle['aliases'] if is_circle else ()),
                         crop=crop,cap=bound,contract=contract,attachment_supports=[support] if rid==sid else ())
        assert q['passed'],(rid,q)
        finalchecks.append({'source_id':rid,'check':q})
        if rid!=sid:assert sha(to_wkb(g))==unchanged_hashes[rid]
    report={'schema':'r080-original-attachment-revision/1','predecessor_zip_sha256':PREDECESSOR_ZIP_SHA,
        'source_sha256':sha(raw),'source_manifest_sha256':sha(bank_bytes),'predecessor_cumulative_sha256':sha(to_wkb(before)),
        'target_source_id':sid,'supporting_feed_source_id':support.feed_id,'adjacent_arc_source_id':support.obstacle_id,
        'source_object_count':len(objects),'fixed_other_replacements':len(scene.replacements)-1,
        'contract':asdict(contract),'axis_factors_xy':[1.01,1.01],
        'proposal_sha256':sha(to_wkb(proposal)),'cumulative_sha256':sha(to_wkb(after)),
        'target_added_area_mm2':proposal.difference(core).area,'new_exposed_added_area_mm2':exposed.area,
        'source_core_removed_mm2':core.difference(proposal).area,'predecessor_removed_mm2':before.difference(after).area,
        't01_removed_mm2':t01.difference(after).area,'other_replacements_unchanged':True,
        'literal_primitive_pair_check':old_check,'qualified_local_attachment_check':check,
        'full_1p25_new_contact_negative_control':negative,
        'all_75_final_replacement_checks':'PASS_MODEL_SPACE',
        'proposed_positive_growth_count':result['t02_completed_targets']+1,
        'still_unchanged_sites':[d['key'] for d in decisions if not d['objective_completed'] and d['key']!='R080'],
        'status':'PROPOSED_POSITIVE_GROWTH_PENDING_DESIGNATED_AUDIT','freeze_status':'NOT_FROZEN',
        'trace_source_geometry_changed':False,'historical_ledger_changed':False,'t03':'NOT_RUN','t04':'NOT_RUN',
        'scope':'Only R080 changes from REV05. Other four unchanged targets and six context sources are not reopened.',
        'limitations':['Source-bound local geometry only; no component/net exemption.',
                      '1.01 positive control, not maximal-area optimization.',
                      'No native export, electrical intent or manufacturing acceptance.']}
    return report,{'before':before,'after':after,'exposed':exposed,'core':core,'proposal':proposal,
                   'scene':scene,'coverage':json.loads((p/'coverage.json').read_text()),'finalchecks':finalchecks,
                   'bounds':result['viewport_mm'],'source':raw,'support':support}


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--predecessor',type=Path,required=True);ap.add_argument('--output',type=Path,required=True)
    a=ap.parse_args();out=a.output.resolve()
    if out.exists() or not out.is_relative_to(ROOT/'out'):raise ValueError('FRESH_PROJECT_OUTPUT_REQUIRED')
    from src.crop_circle_sources import verify_assets,path_for
    integrity=verify_assets()
    report,g=compute(a.predecessor)
    out.mkdir(parents=True)
    for d in ('inputs','geometry','visuals','implementation'):(out/d).mkdir()
    report['asset_integrity']=integrity
    (out/'result.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    (out/'final_scene_checks.json').write_text(json.dumps(g['finalchecks'],indent=2,sort_keys=True)+'\n')
    (out/'inputs/ORG_source.kicad_pcb').write_bytes(g['source'])
    for name in ('before','after','exposed','core','proposal'):(out/f'geometry/{name}.wkb').write_bytes(to_wkb(g[name]))
    for name,sid in [('target',g['support'].target_id),('arc',g['support'].obstacle_id),('feed',g['support'].feed_id)]:
        start,end=map(int,sid.rsplit(':',2)[1:]);(out/f'inputs/{name}.source').write_bytes(g['source'][start:end])
    from tools.run_c02_growth_coverage import render
    cores={r['source_id']:g['scene'].objects[r['source_id']]['geometry'] for r in g['coverage']}
    notes=['All 74 selected sites retained. Only R080 differs from the audited REV05 scene; 74 other replacements fixed.',
           'Red = predecessor copper. Teal = exact new R080 exposed copper. Gold = original selected rectangle contours.',
           'R080: 1.01 × 1.01 complete centered rectangle. Original port unchanged; no new rectangle/arc contact.',
           'Outside-port floor 20.00 µm; actual exposed-addition guard 20.10 µm. No component-label exemption.',
           'PROPOSED result pending separate audit. T02 NOT FROZEN; no revised T03/T04 or ledger change.']
    render(out/'visuals/full_c02_proposed.svg','C02 / R080 attachment correction — one proposed change',g['after'],g['exposed'],g['bounds'],g['coverage'],cores,notes)
    x0,y0,x1,y1=g['core'].bounds;detail_bounds=[x0-.22,y0-.22,x1+.22,y1+.22]
    detailnotes=['Gold = original R080; white = proposal; teal = new copper; blue = original feed and arc boundaries.',
        'Original feed overlaps R080 and exactly shares the neighboring arc endpoint and 0.10008 mm width.',
        'Raw primitive gap: 11.499 → 9.199 µm, within the original feed; it is not an exposed conductor gap.',
        'New exposed copper to full arc: 69.667 µm. Proposal to arc outside the same original port: 117.793 µm.',
        'No new arc contact. 1.25×1.25 negative control still rejects new contact. No enlarged port permission.',
        'Proposed positive-growth witness only; separate audit required before completion credit or freezing.']
    render(out/'visuals/R080_detail.svg','C02 / R080 — bounded source-supported original attachment',g['after'],g['exposed'],detail_bounds,g['coverage'],cores,detailnotes,detail={'candidate':g['proposal']})
    # Thin source outlines must not obscure this deliberately small 1% addition.
    detail_path=out/'visuals/R080_detail.svg'
    text=detail_path.read_text().replace('stroke-width="0.004"','stroke-width="0.0004"').replace('stroke-width="0.003"','stroke-width="0.0004"')
    overlay=''
    for blob in (g['support'].feed_wkb,g['support'].obstacle_wkb):
        overlay+=f'<path d="{path_for(from_wkb(blob))}" fill="none" stroke="#68bdff" stroke-width="0.0004"/>'
    text=text.replace('</svg>',overlay+'</svg>',1)
    detail_path.write_text(text)
    for svg in (out/'visuals').glob('*.svg'):
        subprocess.run(['sips','-s','format','png',str(svg),'--out',str(svg.with_suffix('.png'))],capture_output=True,check=True)
    for name in ('src/crop_stage_growth.py','src/crop_attachment_support.py','src/native_inventory.py','src/source_locators.py','src/native_reference.py','src/revision_catalog.py','tests/test_crop_stage_growth.py','tests/test_crop_growth_coverage.py','tests/test_crop_attachment_support.py','src/crop_growth_coverage.py','tools/run_c02_r080_attachment_revision.py'):
        dest=out/'implementation'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/name,dest)
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>R080 bounded correction</title><style>body{font:18px system-ui;background:#edf3f7;color:#142a3f;margin:32px}img{width:100%}</style><h1>C02 — proposed R080 attachment correction</h1><p>Only R080 changes from the audited 74-candidate scene. Other 74 replacements remain byte-identical. T02 NOT FROZEN; proposed geometry awaits audit.</p><p><a href="../c02_focused_growth_coverage_20261028_05/index.html">Full 80-source coverage index and all 74 prior close-ups</a></p><img src="visuals/full_c02_proposed.png"><img src="visuals/R080_detail.png"><p>See result.json and final_scene_checks.json for exact source IDs and all resulting scene checks.</p>')
    print(json.dumps({'output':str(out),'new_exposed_area_mm2':report['new_exposed_added_area_mm2'],'other_replacements_unchanged':True,'final_checks':'PASS_MODEL_SPACE'}))


if __name__=='__main__':main()
