#!/usr/bin/env python3
"""Focused C02 ORG -> compliant T01 -> compliant T02 demonstration.

Reads frozen historical data for target selection and rejected controls only.
No historical acceptance record or native source file is overwritten.
"""
import sys
sys.dont_write_bytecode = True
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import argparse, csv, hashlib, html, json, math, platform, re, shutil
from dataclasses import asdict
import shapely
from shapely import from_wkb, to_wkb
from shapely.affinity import scale
from shapely.geometry import Point, box
from shapely.ops import unary_union
from src.crop_circle_sources import verify_assets, path_for
from src.org_edit_target_map import _inventory_side
from src.crop_rect_t02 import rectangular_feature
from src.crop_stage_growth import GrowthContract, GrowthScene, check_proposal, fit_rectangle, fit_round_circle

BASE = ROOT / 'out/crop_dynamic_tasks'
SOURCE = ROOT / 'dataset/szu-comm_3020301113B_intake_ready_20261021_v2/raw/ORG/top.kicad_pcb'
SOURCE_SHA = '850c4c74d55717a721d4bbed7ec876ee086f475efd97f69bb5b5164ef77533a0'
HIST01 = BASE / 't01_owner_corrected_20261025_v11'
HIST02 = BASE / 't02_rectangles_crop_20261025_v69'
CAUSALITY = BASE / 't03_c2_growth_causality_20261027_95/evidence/growth_causality.csv'

def sha(b): return hashlib.sha256(b).hexdigest()
def save(p, d): p.write_text(json.dumps(d, indent=2, sort_keys=True) + '\n')

def render(path, title, scene, delta, bounds, labels, notes, color='#21bda8'):
    x0,y0,x1,y1 = bounds; width=x1-x0; height=y1-y0
    pw=1720; ph=pw*height/width
    paths = f'<path d="{path_for(scene)}" fill="#ed4260" fill-rule="evenodd"/>'
    if not delta.is_empty: paths += f'<path d="{path_for(delta)}" fill="{color}" fill-rule="evenodd"/>'
    for key,geom in labels:
        c=geom.centroid
        paths+=f'<circle cx="{c.x}" cy="{c.y}" r=".025" fill="#ffd74b"/><text x="{c.x+.04}" y="{c.y-.03}" font-size=".095" font-family="Arial" fill="#ffe463">{html.escape(key)}</text>'
    s=f'<svg xmlns="http://www.w3.org/2000/svg" width="1800" height="{int(ph+320)}" viewBox="0 0 1800 {int(ph+320)}"><rect width="1800" height="{int(ph+320)}" fill="#f0f4f7"/><text x="40" y="52" font-family="Arial" font-size="30" font-weight="bold" fill="#142a3f">{html.escape(title)}</text><text x="40" y="84" font-family="Arial" font-size="17" fill="#354d61">C02 full source viewport · ORG {SOURCE_SHA[:16]} · F.Cu geometric experiment</text><svg x="40" y="110" width="1720" height="{ph}" viewBox="{x0} {y0} {width} {height}"><rect x="{x0}" y="{y0}" width="{width}" height="{height}" fill="#071621"/>{paths}</svg>'
    for i,n in enumerate(notes):
        s+=f'<text x="40" y="{ph+155+i*28}" font-family="Arial" font-size="18" fill="#243b50">{html.escape(n)}</text>'
    path.write_text(s+'</svg>')

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--output',type=Path,required=True); args=ap.parse_args()
    out=args.output.resolve()
    if out.exists() or not out.is_relative_to(ROOT/'out'): raise ValueError('FRESH_PROJECT_OUT_REQUIRED')
    assets=verify_assets(); raw=SOURCE.read_bytes()
    if sha(raw)!=SOURCE_SHA: raise ValueError('ORG_HASH_MISMATCH')
    policy=json.loads((HIST01/'policy.json').read_text()); bounds=policy['viewport_mm']; crop=box(*bounds)
    historical_t01=json.loads((HIST01/'report.json').read_text())
    c013=next(d for d in historical_t01['decisions'] if d['key']=='C013')
    if c013['decision']!='ROUND_GROW_PRIORITY' or abs(c013['proposed_radius_mm']-.1687)>1e-10:
        raise ValueError('FOCUSED_T01_SOURCE_BINDING_CHANGED')
    witnesses=list(csv.DictReader(CAUSALITY.open()))
    focus=[r for r in witnesses if r['causality_classification'] in ('GROWTH_INTRODUCED','GROWTH_WORSENED')]
    rect_ids=sorted({r['land_source_id'] for r in focus})
    if len(focus)!=15 or len(rect_ids)!=11: raise ValueError('FOCUS_SET_CHANGED')
    side=_inventory_side(raw,SOURCE_SHA)
    fcu=[r for r in side['rows'] if 'F.Cu' in r['layers']]
    unsupported=[r['id'] for r in fcu if not r.get('geometry_sha256')]
    if unsupported: raise ValueError('UNSUPPORTED_FCU:'+str(unsupported))
    out.mkdir(parents=True)
    for d in ('inputs/source_wkb','source_baseline','t01','t02','rejected_proposals','implementation'):
        (out/d).mkdir(parents=True)
    shutil.copyfile(SOURCE,out/'inputs/ORG_source.kicad_pcb')
    shutil.copyfile(CAUSALITY,out/'inputs/historical_growth_causality.csv')
    shutil.copyfile(HIST01/'report.json',out/'inputs/historical_t01_report.json')
    shutil.copyfile(HIST01/'policy.json',out/'inputs/historical_t01_policy.json')
    shutil.copyfile(HIST02/'t02_policy.json',out/'inputs/historical_t02_policy_v15.json')
    for p in ('src/crop_stage_growth.py','tools/run_c02_valid_stage_growth.py','tests/test_crop_stage_growth.py'):
        target=out/'implementation'/p;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/p,target)
    contract=GrowthContract(); objects=[]; manifest=[]
    for r in fcu:
        blob=side['payloads'][r['geometry_sha256']];geom=from_wkb(blob)
        if sha(blob)!=r['geometry_sha256']: raise ValueError('SOURCE_WKB_HASH_MISMATCH')
        width=0.0
        if r['kind'] in ('segment','arc'):
            w=re.search(rb'\(width\s+([-+0-9.eE]+)\)',raw[slice(*r['source_span'])])
            if not w: raise ValueError('MISSING_TRACE_WIDTH')
            width=float(w.group(1))
        objects.append({'source_id':r['id'],'geometry':geom,'trace_width_mm':width})
        manifest.append({**r,'trace_width_mm':width})
        p=out/'inputs/source_wkb'/f"{r['geometry_sha256']}.wkb"
        if not p.exists():p.write_bytes(blob)
    save(out/'inputs/source_manifest.json',{'source_sha256':SOURCE_SHA,'objects':manifest,
         'inventory_version':side['inventory_version'],'per_curve_approximation_error_mm':side['per_curve_approximation_error_mm']})
    byid={r['source_id']:r for r in objects}; rows={r['id']:r for r in fcu}
    scene=GrowthScene(objects,contract)
    source_union=unary_union([r['geometry'].intersection(crop) for r in objects if r['geometry'].intersects(crop)])
    (out/'source_baseline/copper.wkb').write_bytes(to_wkb(source_union))
    # Only the exact historically growth-eligible C013 target is reconstructed.
    sid=c013['source_id'];core=byid[sid]['geometry'];center=tuple(c013['center']);radius=c013['source_radius_mm']
    if any(from_wkb(side['payloads'][r['geometry_sha256']]).covers(core)
           for r in fcu if r['id'] not in c013['aliases']): raise ValueError('FOCUSED_CIRCLE_COVERED')
    cap=Point(*center).buffer(radius*1.5,quad_segs=contract.quad_segs)
    n=scene.neighbors(sid,cap,c013['aliases'])
    t01,r1,check1=fit_round_circle(core,center,radius,c013['proposed_radius_mm'],n,crop,contract=contract)
    if not check1['passed']:raise ValueError('T01_PROPOSAL_FAILED')
    scene.accept(sid,t01);delta1=t01.difference(core);union1=source_union.union(delta1)
    save(out/'t01/decision.json',{'source_id':sid,'key':'C013','aliases':c013['aliases'],
         'original_radius_mm':radius,'desired_radius_mm':c013['proposed_radius_mm'],'actual_radius_mm':r1,
         'objective':'positive safe round growth up to the historically admitted diameter class, at most 1.5x source radius',
         'objective_completed':delta1.area>1e-10,'check':check1})
    for name,g in [('candidate',t01),('added_copper',delta1),('cumulative',union1)]: (out/f't01/{name}.wkb').write_bytes(to_wkb(g))
    decisions=[];rejected=[];labels=[('C013',core)];fullbad=[]
    for i,rid in enumerate(rect_ids,1):
        r=rows[rid];f=rectangular_feature(r,side['payloads'],crop,max_axis_factor=1.25)
        if f is None or not f['geometry'].equals(box(*f['geometry'].bounds)): raise ValueError('TARGET_NOT_AXIS_ALIGNED_RECTANGLE')
        core=f['geometry'];cap=scale(core,1.25,1.25,origin=core.centroid);neighbors=scene.neighbors(rid,cap)
        oldbytes=(HIST02/'t02_candidates'/(sha(rid.encode())+'.wkb')).read_bytes();old=from_wkb(oldbytes)
        oldcheck=check_proposal(core,old,neighbors,crop=crop,cap=cap,contract=contract)
        (out/f'rejected_proposals/R{i:02d}_historical_v69.wkb').write_bytes(oldbytes)
        rejected.append({'key':f'R{i:02d}','source_id':rid,'historical_v69_hash':sha(oldbytes),'check':oldcheck})
        fullbad.append(old.difference(core))
        candidate,factors,checks=fit_rectangle(core,neighbors,crop,contract=contract)
        if not checks['passed']:raise ValueError('T02_PROPOSAL_FAILED')
        scene.accept(rid,candidate)
        for name,g in [('candidate',candidate),('added',candidate.difference(core))]:
            (out/f't02/R{i:02d}_{name}.wkb').write_bytes(to_wkb(g))
        decisions.append({'key':f'R{i:02d}','source_id':rid,'source_span':r['source_span'],
             'source_geometry_sha256':r['geometry_sha256'],'candidate_sha256':sha(to_wkb(candidate)),
             'source_bounds_mm':list(core.bounds),'candidate_bounds_mm':list(candidate.bounds),
             'axis_factors_xy':list(factors),'objective':'positive safe rectangle growth; per-axis cap 1.25, no recess',
             'objective_completed':candidate.difference(core).area>1e-10,'check':checks,
             'historical_witness_rows':[int(x['ledger_row_ordinal']) for x in focus if x['land_source_id']==rid]})
        labels.append((f'R{i:02d}',core))
    # Verify every replacement again against the complete final cumulative scene.
    finalchecks=[]
    for rid,g in sorted(scene.replacements.items()):
        core=byid[rid]['geometry'];is_circle=rid==sid
        cap=Point(*center).buffer(radius*1.5,quad_segs=128) if is_circle else scale(core,1.25,1.25,origin=core.centroid)
        check=check_proposal(core,g,scene.neighbors(rid,cap,c013['aliases'] if is_circle else ()),crop=crop,cap=cap,contract=contract)
        finalchecks.append({'source_id':rid,'check':check})
    if not all(x['check']['passed'] for x in finalchecks):raise ValueError('FINAL_CUMULATIVE_SCENE_REJECTED')
    delta2=unary_union([g.difference(byid[rid]['geometry']) for rid,g in scene.replacements.items() if rid!=sid])
    union2=union1.union(delta2);historical_added=unary_union(fullbad)
    save(out/'t02/decisions.json',decisions);save(out/'t02/final_scene_checks.json',finalchecks)
    save(out/'rejected_proposals/decisions.json',rejected)
    for name,g in [('added_copper',delta2),('cumulative',union2)]: (out/f't02/{name}.wkb').write_bytes(to_wkb(g))
    relationships=[]
    for x in witnesses:
        rid=x['land_source_id'];tr=x['trace_source_id'];orig=byid[rid]['geometry'];final=scene.replacements.get(rid,orig)
        relationships.append({'historical_row':int(x['ledger_row_ordinal']),'classification':x['causality_classification'],
            'trace_source_id':tr,'land_source_id':rid,'ORG_gap_mm':orig.distance(byid[tr]['geometry']),
            'historical_v69_gap_mm':float(x['accepted_T02_surface_distance_mm']),
            'revised_gap_mm':final.distance(byid[tr]['geometry']),
            'inherited_unchanged_excluded':x['causality_classification']=='PRE_EXISTING_UNCHANGED'})
    save(out/'t02/historical_19_row_comparison.json',relationships)
    report={'schema':'valid-stage-focused-growth/1','source_sha256':SOURCE_SHA,'viewport_mm':bounds,
         'contract':asdict(contract),'asset_integrity':assets,'source_object_count':len(objects),
         'focused_circle_count':1,'focused_rectangle_count':11,'historical_growth_caused_witness_count':15,
         't01_added_area_mm2':delta1.area,'t02_added_area_mm2':delta2.area,
         't01_objective_completed':delta1.area>1e-10,'t02_completed_targets':sum(d['objective_completed'] for d in decisions),
         't02_uncompleted_targets':[d['key'] for d in decisions if not d['objective_completed']],
         'historical_proposals_rejected_under_revised_contract':sum(not r['check']['passed'] for r in rejected),
         'cumulative_geometric_checks':'PASS_MODEL_SPACE',
         'freeze_status':('NOT_FROZEN_TARGET_OBJECTIVE_UNMET' if any(not d['objective_completed'] for d in decisions) else 'PENDING_DESIGNATED_AUDIT'),
         'source_core_loss_mm2':source_union.difference(union2).area,
         't01_changed_in_t02_mm2':union1.difference(union2).area,
         'trace_geometry_changed':False,'t03':'NOT_RUN_REVISED_LADDER','t04':'NOT_RUN',
         'historical_ledger_dispositions_changed':False,'electrical':'NOT_ESTABLISHED','manufacturing':'NOT_ESTABLISHED',
         'environment':{'python':platform.python_version(),'shapely':shapely.__version__,'geos':shapely.geos_version_string},
         'selection_basis':'11 exact source rectangles behind 15 growth-caused/worsened historical witnesses, plus C013: sole actually grown C02 T01 circle. All other sources fixed.',
         'inherited_exclusion':'Four original unchanged below-floor witness relations recorded, excluded from growth remediation; no original source repair.',
         'limitations':['Finite-width polygonal model, no native export or electrical net inference.',
             'Source curve approximation bound retained. 100nm construction margin exceeds the combined 20nm pair allowance; no manufacturing qualification.',
             'Rectangle search is bounded two-axis coordinate search, not a proof of global maximal area.']}
    save(out/'result.json',report)
    notes=[f"Focused targets: C013 and 11 source rectangles; all other source objects fixed. ORG objects: {len(objects)}.",
        'Red = predecessor/source copper. Teal = exact added copper. Gold labels locate exact focused source objects.',
        '20.00 µm hard surface floor; 20.10 µm construction guard on added copper outside explicit original attachment ports.',
        'Model-space candidate pending designated audit. Electrical/manufacturing NOT_ESTABLISHED. No T03/T04 execution.']
    render(out/'source_baseline/full_crop.svg','C02 / 00 — actual ORG copper baseline',source_union,source_union.difference(source_union),bounds,labels,notes)
    render(out/'t01/full_crop.svg',f'C02 / 01 — focused T01 round growth · {delta1.area:.6f} mm² added',union1,delta1,bounds,labels,notes)
    t02notes=[f"NOT FROZEN: {', '.join(report['t02_uncompleted_targets']) or 'designated audit pending'} — safe geometry and growth-objective completion are separate."]+notes[:3]
    render(out/'t02/full_crop.svg',f'C02 / 02 — safe cumulative T01 + T02 · {report["t02_completed_targets"]}/11 growth objectives met',union2,delta2,bounds,labels,t02notes)
    render(out/'rejected_proposals/full_crop.svg','C02 / control — historical v69 proposals evaluated separately',source_union.union(historical_added),historical_added,bounds,labels,
         [f"{report['historical_proposals_rejected_under_revised_contract']}/11 historical focused proposals fail the revised own-stage checks.",
          'Orange = historical added copper, retained as rejected-control evidence. This panel is excluded from the revised cumulative candidate.',
          'Historical receipts and geometry remain preserved; no ledger disposition or past visual acceptance is overwritten.',
          'Complete C02 viewport matches the three stage panels.'],color='#ffb34b')
    page='<html><head><meta charset="utf-8"><title>C02 valid stage growth</title><style>body{font:18px system-ui;background:#eaf0f4;margin:30px;color:#142a3f}img{width:100%;border:1px solid #abc}section{margin:36px 0}code{font-size:14px}</style></head><body><h1>C02 — source → safe T01 → safe cumulative T02</h1><p>Focused geometric reconstruction. Each stage owns its growth; no corner obligation is deferred to T03. T02 is NOT FROZEN while a required growth objective is unmet. Pending designated audit.</p>'
    for key,label in [('source_baseline','00 / source'),('t01','01 / T01'),('t02','02 / cumulative T02'),('rejected_proposals','control / rejected historical proposals')]:
        page+=f'<section><h2>{label}</h2><a href="{key}/full_crop.png"><img src="{key}/full_crop.png"></a></section>'
    page+='<p>See <a href="result.json">result.json</a> and per-stage decisions for exact source identities, added copper and unresolved target objectives.</p></body></html>'
    (out/'index.html').write_text(page)
    print(json.dumps({'output':str(out),**{k:report[k] for k in ['t01_added_area_mm2','t02_added_area_mm2','t02_completed_targets','t02_uncompleted_targets','historical_proposals_rejected_under_revised_contract','cumulative_geometric_checks']}}))

if __name__=='__main__':main()
