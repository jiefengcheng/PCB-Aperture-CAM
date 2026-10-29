#!/usr/bin/env python3
"""Cumulative round-only C03 T01 proposal for the supported source target scope."""
from pathlib import Path
import sys,json,hashlib,subprocess,math
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from shapely import from_wkb,STRtree,to_wkb
from shapely.geometry import Point,box
from shapely.ops import unary_union
from src.crop_circle_sources import verify_assets
from src.crop_stage_growth import GrowthScene,check_proposal
from src.prepared_land_scene import PreparedLandScene
from tools.render_c03_source_frame import render_source_frame as render


def main(pre,scope_path,baseline,out,*,surface_mode=False):
    if out.exists():raise ValueError('FRESH_OUTPUT_REQUIRED')
    integrity=verify_assets();scope=json.loads(scope_path.read_text());base=json.loads(baseline.read_text());raw=(pre/'inputs/ORG_source.kicad_pcb').read_bytes()
    if hashlib.sha256(raw).hexdigest()!=scope['source_sha256'] or scope['source_sha256']!=base['org_source_sha256']:raise ValueError('SOURCE_BINDING_MISMATCH')
    meta={r['id']:r for r in json.loads((pre/'inputs/source_manifest.json').read_text())['objects']};objects=[]
    for sid,row in meta.items():
        blob=(pre/f'inputs/source_wkb/{row["geometry_sha256"]}.wkb').read_bytes()
        if hashlib.sha256(blob).hexdigest()!=row['geometry_sha256']:raise ValueError('SOURCE_GEOMETRY_HASH_MISMATCH')
        objects.append(dict(source_id=sid,geometry=from_wkb(blob),trace_width_mm=row['trace_width_mm']))
    scene=GrowthScene(objects);crop=box(*scope['viewport_mm']);targets=sorted((r for r in scope['records'] if r['scope_disposition']=='T01_ROUND_CLASS_TARGET_PROPOSAL'),key=lambda r:(r['center_mm'][1],r['center_mm'][0],r['source_id']))
    prepared={}
    for r in targets:
        sid=r['source_id'];core=scene.objects[sid]['geometry'];aliases=sorted(k for k,v in meta.items() if v['kind']=='gr_circle' and v['geometry_sha256']==meta[sid]['geometry_sha256']);cap=Point(*r['center_mm']).buffer(r['original_radius_mm']*1.5,quad_segs=128)
        prepared[sid]=dict(row=r,core=core,aliases=aliases,cap=cap)
    land_ids=set(prepared)
    surface_checker=None
    if surface_mode:
        initial=[dict(id=s,original=p['core'],candidate=p['core'],native_source_kind='gr_circle',native_stroke_width_mm=0.) for s,p in prepared.items()]
        fixed=[dict(id=r['source_id'],geometry=r['geometry'],trace_width_mm=r['trace_width_mm']) for r in objects if r['source_id'] not in land_ids]
        surface_checker=PreparedLandScene(initial,fixed)
    def evaluate_all(overrides=None,materialize=False):
        overrides=overrides or {}
        parts=[dict(id=s,original=p['core'],candidate=overrides.get(s,accepted.get(s,p['core'])),native_source_kind='gr_circle',native_stroke_width_mm=0.) for s,p in prepared.items()]
        return surface_checker.check(parts,materialize_scene=materialize,fail_fast=not materialize)
    def verify(sid,candidate):
        if surface_mode:
            q=evaluate_all({sid:candidate})
            return dict(passed=q['passed'],failures=q['failures'],evaluation_complete=q['evaluation_complete'],checked_land_count=q['checked_land_count'],model=q['schema'])
        p=prepared[sid];return check_proposal(p['core'],candidate,scene.neighbors(sid,p['cap'],p['aliases']),crop=crop,cap=p['cap'])
    decisions=[];rejected=[];accepted={}
    for r in targets:
        sid=r['source_id'];p=prepared[sid];chosen=p['core'];diameter=2*r['original_radius_mm'];trial_results=[]
        for d in sorted((d for d in r['admissible_diameters_mm'] if d<=r['desired_diameter_mm']),reverse=True):
            candidate=Point(*r['center_mm']).buffer(d/2,quad_segs=128)
            if not candidate.covers(p['core']):raise ValueError('ROUND_CLASS_SOURCE_CORE_NOT_RETAINED')
            check=verify(sid,candidate);global_failures=[]
            if check['passed']:
                for alias in p['aliases']:scene.accept(alias,candidate)
                for previous,geometry in ([] if surface_mode else accepted.items()):
                    previous_check=verify(previous,geometry)
                    if not previous_check['passed']:global_failures.append(dict(source_id=previous,check=previous_check))
                if global_failures:
                    for alias in p['aliases']:scene.replacements.pop(alias,None)
            trial=dict(diameter_mm=d,check=check,prior_candidate_failures=global_failures)
            trial_results.append(trial)
            if check['passed'] and not global_failures:chosen=candidate;diameter=d;accepted[sid]=candidate;break
            rejected.append(dict(source_id=sid,**trial))
        final=verify(sid,chosen)
        if not final['passed']:raise ValueError('NO_VALID_SOURCE_KEEP_OR_CLASS')
        decisions.append(dict(source_id=sid,key=r['key'],aliases=p['aliases'],original_radius_mm=r['original_radius_mm'],desired_diameter_mm=r['desired_diameter_mm'],selected_diameter_mm=diameter,radius_factor=diameter/(2*r['original_radius_mm']),positive_growth=sid in accepted,round_shape_retained=True,strict_source_core_retained=chosen.covers(p['core']),candidate_sha256=hashlib.sha256(to_wkb(chosen)).hexdigest(),trials=trial_results,final_check=final))
    final_checks=[];surface_final=None
    if surface_mode:
        surface_final=evaluate_all(materialize=True)
        if not surface_final['passed']:raise ValueError('FINAL_CUMULATIVE_VISIBLE_SCENE_REJECTED')
        final_checks=[dict(source_id=r['source_id'],check=r) for r in surface_final['lands']]
    else:
        for r in decisions:
            sid=r['source_id'];candidate=accepted.get(sid,prepared[sid]['core']);check=verify(sid,candidate)
            if not check['passed']:raise ValueError('FINAL_CUMULATIVE_SCENE_REJECTED')
            final_checks.append(dict(source_id=sid,check=check))
    all_geoms=[r['geometry'] for r in objects];tree=STRtree(all_geoms);indices=sorted(int(i) for i in tree.query(crop,predicate='intersects'));before=unary_union([all_geoms[i] for i in indices]).intersection(crop);after=unary_union([scene.replacements.get(objects[i]['source_id'],all_geoms[i]) for i in indices]).intersection(crop);added=after.difference(before)
    if before.difference(after).area>1e-12:raise ValueError('CUMULATIVE_SOURCE_COPPER_REMOVED')
    out.mkdir();(out/'candidates').mkdir()
    for r in decisions:
        sid=r['source_id'];(out/'candidates'/f'{r["key"]}.wkb').write_bytes(to_wkb(accepted.get(sid,prepared[sid]['core'])))
    for name,g in [('before',before),('after',after),('added',added)]:(out/f'{name}.wkb').write_bytes(to_wkb(g))
    if surface_mode:(out/'SOURCE_VISIBLE_FINAL_CHECK.json').write_text(json.dumps(surface_final,indent=2,sort_keys=True)+'\n')
    result=dict(geometry_check_model='SOURCE_VISIBLE_SURFACES' if surface_mode else 'RAW_SOURCE_PAIR_CONSERVATIVE',status='C03_SUPPORTED_ROUND_CLASS_T01_PROPOSAL_LOCAL_PASS_NOT_FROZEN',source_sha256=scope['source_sha256'],scope_sha256=hashlib.sha256(scope_path.read_bytes()).hexdigest(),target_count=len(targets),positive_targets=len(accepted),keep_targets=len(targets)-len(accepted),final_joint_checks=len(final_checks),rejected_trials=len(rejected),unresolved_class_source_count=scope['unresolved_existing_class_count'],added_crop_area_mm2=added.area,removed_crop_area_mm2=before.difference(after).area,after_sha256=hashlib.sha256(to_wkb(after)).hexdigest(),round_shape='ALL_RETAINED',T02='NOT_RUN',T03='NOT_RUN',T04='NOT_RUN',registration=scope['screenshot_registration'],scope_limit='Supported source-circle scope only; complete C03 land-stage acceptance/T02 not established; no C02 acceptance inheritance',asset_integrity=integrity)
    for name,value in [('RESULT.json',result),('DECISIONS.json',decisions),('FINAL_JOINT_CHECKS.json',final_checks),('REJECTED_TRIALS.json',rejected)]: (out/name).write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')
    for field,bounds in [('full',scope['viewport_mm']),('neighborhood',base['closeup_bounds_mm'])]:
        for stage,copper in [('before',before),('after',after)]:
            svg=out/f'{field}_{stage}.svg';render(svg,f'C03 / supported round-class T01 proposal / {field} {stage}',copper,added if stage=='after' else added.difference(added),bounds,[],{},[
                f'{len(targets)} supported targets;{len(accepted)}positive class growth;{len(targets)-len(accepted)}KEEP; all{len(final_checks)}final cumulative checks pass.',
                'All grown circles stay round; source cores and attachments retained. Exact added copper shown once in teal.',
                'Existing physical diameter palette and local target groups;1.5cap. No arbitrary non-round circle growth.',
                f'{scope["unresolved_existing_class_count"]}source circle outside existing class range remains unresolved; T02not run; this is not a complete frozen C03stage.',
                'Source-only construction; screenshot registration remains provisional; no EDIT geometry or C02land scene inherited.'])
            subprocess.run(['sips','-s','format','png',str(svg),'--out',str(svg.with_suffix('.png'))],check=True,capture_output=True)
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>C03 round-class proposals</title><style>body{font:18px system-ui;margin:24px}img{max-width:100%}</style><h1>C03 supported round-class T01 proposals</h1><p>Actual cumulative proposal, not a complete or frozen C03stage.</p><h2>Source before</h2><img src="full_before.png"><h2>Cumulative after</h2><img src="full_after.png"><h2>Neighborhood before / after</h2><img src="neighborhood_before.png"><img src="neighborhood_after.png"><a href="RESULT.json">Coverage and limits</a> · <a href="DECISIONS.json">Every source decision</a> · <a href="FINAL_JOINT_CHECKS.json">Every final cumulative check</a>')
    print(json.dumps(result))

if __name__=='__main__':
    mode='--visible-surfaces' in sys.argv
    args=[a for a in sys.argv[1:] if a!='--visible-surfaces']
    main(*map(Path,args),surface_mode=mode)
