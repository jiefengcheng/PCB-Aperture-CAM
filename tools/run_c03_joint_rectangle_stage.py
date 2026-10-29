#!/usr/bin/env python3
"""C03 cumulative T02 proposal with fixed round-circle predecessor geometry."""
from pathlib import Path
import sys,json,hashlib,subprocess
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from shapely import from_wkb,to_wkb,STRtree
from shapely.geometry import Point,box
from shapely.affinity import scale
from shapely.ops import unary_union
from src.crop_circle_sources import verify_assets
from src.crop_stage_growth import GrowthScene,check_proposal
from src.joint_rectangle_growth import fit_joint_rectangle
from src.prepared_land_scene import PreparedLandScene
from tools.render_c03_source_frame import render_source_frame as render


def main(pre,scope_path,circle_stage,baseline,out,*,surface_mode=False):
    if out.exists():raise ValueError('FRESH_OUTPUT_REQUIRED')
    integrity=verify_assets();scope=json.loads(scope_path.read_text());base=json.loads(baseline.read_text());prior=json.loads((circle_stage/'RESULT.json').read_text());raw=(pre/'inputs/ORG_source.kicad_pcb').read_bytes()
    if hashlib.sha256(raw).hexdigest()!=scope['source_sha256'] or prior['scope_sha256']!=hashlib.sha256(scope_path.read_bytes()).hexdigest():raise ValueError('PREDECESSOR_SCOPE_BINDING_MISMATCH')
    if prior['after_sha256']!=hashlib.sha256((circle_stage/'after.wkb').read_bytes()).hexdigest():raise ValueError('PREDECESSOR_SCENE_HASH_MISMATCH')
    meta={r['id']:r for r in json.loads((pre/'inputs/source_manifest.json').read_text())['objects']};objects=[]
    for sid,row in meta.items():
        blob=(pre/f'inputs/source_wkb/{row["geometry_sha256"]}.wkb').read_bytes()
        if hashlib.sha256(blob).hexdigest()!=row['geometry_sha256']:raise ValueError('SOURCE_GEOMETRY_HASH_MISMATCH')
        objects.append(dict(source_id=sid,geometry=from_wkb(blob),trace_width_mm=row['trace_width_mm']))
    scene=GrowthScene(objects);crop=box(*scope['viewport_mm']);scope_rows={r['source_id']:r for r in scope['records']};prepared={};current={};circle_blobs={}
    for r in json.loads((circle_stage/'DECISIONS.json').read_text()):
        sid=r['source_id'];blob=(circle_stage/'candidates'/f'{r["key"]}.wkb').read_bytes()
        if hashlib.sha256(blob).hexdigest()!=r['candidate_sha256']:raise ValueError('PREDECESSOR_CIRCLE_PART_HASH_MISMATCH')
        candidate=from_wkb(blob);row=scope_rows[sid];core=scene.objects[sid]['geometry']
        if not candidate.covers(core):raise ValueError('PREDECESSOR_CIRCLE_CORE_NOT_RETAINED')
        cap=Point(*row['center_mm']).buffer(row['original_radius_mm']*1.5,quad_segs=128)
        prepared[sid]=dict(core=core,cap=cap,aliases=r['aliases']);current[sid]=candidate;circle_blobs[sid]=blob
        for alias in r['aliases']:scene.accept(alias,candidate)
    def check(sid,candidate):
        p=prepared[sid];return check_proposal(p['core'],candidate,scene.neighbors(sid,p['cap'],p['aliases']),crop=crop,cap=p['cap'])
    predecessor_recheck=None
    if surface_mode:
        circles=[dict(id=s,original=prepared[s]['core'],candidate=g,native_source_kind='gr_circle',native_stroke_width_mm=0.) for s,g in current.items()]
        fixed=[dict(id=r['source_id'],geometry=r['geometry'],trace_width_mm=r['trace_width_mm']) for r in objects if r['source_id'] not in current]
        predecessor_recheck=PreparedLandScene(circles,fixed).check(circles,materialize_scene=True)
        if not predecessor_recheck['passed']:raise ValueError('CIRCLE_VISIBLE_PREDECESSOR_REPLAY_FAILED')
    elif not all(check(s,g)['passed'] for s,g in current.items()):raise ValueError('CIRCLE_PREDECESSOR_JOINT_CHECK_FAILED')
    rectangles=sorted((r for r in scope['records'] if r['scope_disposition']=='T02_RECTANGLE_TARGET_PROPOSAL'),key=lambda r:(scene.objects[r['source_id']]['geometry'].centroid.y,scene.objects[r['source_id']]['geometry'].centroid.x,r['source_id']))
    land_ids={r['source_id'] for r in rectangles};surface_checker=None;port_bindings=[]
    if surface_mode:
        for r in rectangles:
            sid=r['source_id'];core=scene.objects[sid]['geometry'];aliases=sorted(s for s,m in meta.items() if m['kind']=='gr_poly' and m['geometry_sha256']==meta[sid]['geometry_sha256'])
            prepared[sid]=dict(core=core,cap=scale(core,1.25,1.25,origin=core.centroid),aliases=aliases)
        initial=[dict(id=s,original=prepared[s]['core'],candidate=prepared[s]['core'],native_source_kind='gr_poly',native_stroke_width_mm=0.) for s in sorted(land_ids)]
        fixed=[dict(id=r['source_id'],geometry=scene.replacements.get(r['source_id'],r['geometry']),trace_width_mm=r['trace_width_mm']) for r in objects if r['source_id'] not in land_ids]
        surface_checker=PreparedLandScene(initial,fixed)
        # T01 is the visibility predecessor, but must not enlarge ORG ports.
        for sid in sorted(land_ids):
            core=prepared[sid]['core']
            for i in surface_checker.tree.query(core,predicate='intersects'):
                oid=surface_checker.ids[int(i)]
                if oid==sid:continue
                original=scene.objects[oid]['geometry'];overlap=core.intersection(original);contact=not overlap.is_empty
                width=max(surface_checker.widths[sid],surface_checker.widths[oid])+surface_checker.contract.original_port_buffer_gap_mm
                port=None if not contact else overlap.buffer(width,quad_segs=surface_checker.contract.port_quad_segs)
                surface_checker.ports[(sid,oid)]=(port,contact,core.distance(original))
                port_bindings.append(dict(source_id=sid,neighbor_id=oid,ORG_contact=contact,ORG_neighbor_sha256=hashlib.sha256(to_wkb(original)).hexdigest(),port_sha256=None if port is None else hashlib.sha256(to_wkb(port)).hexdigest()))
    def surface_evaluate(sid=None,candidate=None,materialize=False):
        parts=[dict(id=s,original=prepared[s]['core'],candidate=candidate if s==sid else current.get(s,prepared[s]['core']),native_source_kind='gr_poly',native_stroke_width_mm=0.) for s in sorted(land_ids)]
        return surface_checker.check(parts,materialize_scene=materialize,fail_fast=not materialize)
    decisions=[]
    for row in rectangles:
        sid=row['source_id'];core=scene.objects[sid]['geometry'];cap=scale(core,1.25,1.25,origin=core.centroid);aliases=sorted(s for s,r in meta.items() if r['kind']=='gr_poly' and r['geometry_sha256']==meta[sid]['geometry_sha256'])
        prepared[sid]=dict(core=core,cap=cap,aliases=aliases)
        affected=[s for s,g in current.items() if g.distance(cap)<=scene.contract.construction_gap_mm]
        counters=dict(evaluations=0,own_rejections=0,joint_rejections=0);failures={}
        def feasible(candidate):
            counters['evaluations']+=1
            if surface_mode:
                q=surface_evaluate(sid,candidate)
                if not q['passed']:
                    for f in q['failures']:
                        direction='RECTANGLE_TO_CURRENT_SCENE' if f.get('source_id')==sid else 'EXISTING_TARGET_TO_RECTANGLE'
                        counters['own_rejections' if direction=='RECTANGLE_TO_CURRENT_SCENE' else 'joint_rejections']+=1
                        key=json.dumps(f,sort_keys=True)
                        if key not in failures and len(failures)<48:failures[key]=dict(direction=direction,**f)
                return q['passed']
            own=check(sid,candidate)
            if not own['passed']:
                counters['own_rejections']+=1
                for f in own['failures']:
                    key=json.dumps(f,sort_keys=True)
                    if key not in failures and len(failures)<48:failures[key]=dict(direction='RECTANGLE_TO_CURRENT_SCENE',**f)
                return False
            old={a:scene.replacements.get(a) for a in aliases}
            try:
                for a in aliases:scene.accept(a,candidate)
                for other in affected:
                    joint=check(other,current[other])
                    if not joint['passed']:
                        counters['joint_rejections']+=1
                        for f in joint['failures']:
                            key=json.dumps([other,f],sort_keys=True)
                            if key not in failures and len(failures)<48:failures[key]=dict(direction='EXISTING_TARGET_TO_RECTANGLE',existing_target=other,**f)
                        return False
                return True
            finally:
                for a,g in old.items():
                    if g is None:scene.replacements.pop(a,None)
                    else:scene.accept(a,g)
        candidate,factors=fit_joint_rectangle(core,feasible)
        if candidate.difference(core).area<=1e-12:candidate=core;factors=(1.,1.)
        if not feasible(candidate) or not candidate.covers(core):raise ValueError('FINAL_RECTANGLE_PROPOSAL_REJECTED')
        for a in aliases:scene.accept(a,candidate)
        current[sid]=candidate
        decisions.append(dict(key=row['key'],source_id=sid,aliases=aliases,factors=list(factors),positive_growth=candidate.wkb!=core.wkb,strict_source_core_retained=True,no_recess=len(candidate.exterior.coords)==5 and not candidate.interiors,candidate_sha256=hashlib.sha256(to_wkb(candidate)).hexdigest(),affected_prior_target_ids=affected,search=counters,recorded_rejection_witnesses=list(failures.values()),final_check=(next(r for r in surface_evaluate()['lands'] if r['source_id']==sid) if surface_mode else check(sid,candidate))))
    final=[];surface_final=None
    if surface_mode:
        surface_final=surface_evaluate(materialize=True)
        if not surface_final['passed']:raise ValueError('FINAL_VISIBLE_CUMULATIVE_SCENE_REJECTED')
        final=[dict(source_id=r['source_id'],check=r) for r in surface_final['lands']]
    else:
        for sid,g in current.items():
            q=check(sid,g)
            if not q['passed']:raise ValueError('FINAL_CUMULATIVE_SCENE_REJECTED')
            final.append(dict(source_id=sid,check=q))
    for sid,blob in circle_blobs.items():
        if to_wkb(current[sid])!=blob:raise ValueError('FROZEN_CIRCLE_PART_CHANGED')
    all_geoms=[r['geometry'] for r in objects];tree=STRtree(all_geoms);local=sorted(int(i) for i in tree.query(crop,predicate='intersects'));after=unary_union([scene.replacements.get(objects[i]['source_id'],all_geoms[i]) for i in local]).intersection(crop);before=from_wkb((circle_stage/'after.wkb').read_bytes());added=after.difference(before)
    if before.difference(after).area>1e-12:raise ValueError('PREDECESSOR_COPPER_REMOVED')
    out.mkdir();(out/'rectangle_candidates').mkdir()
    for r in decisions:(out/'rectangle_candidates'/f'{r["key"]}.wkb').write_bytes(to_wkb(current[r['source_id']]))
    for name,g in [('before',before),('after',after),('added',added)]:(out/f'{name}.wkb').write_bytes(to_wkb(g))
    if surface_mode:
        (out/'PREDECESSOR_VISIBLE_RECHECK.json').write_text(json.dumps(predecessor_recheck,indent=2,sort_keys=True)+'\n')
        (out/'SOURCE_VISIBLE_FINAL_CHECK.json').write_text(json.dumps(surface_final,indent=2,sort_keys=True)+'\n')
        (out/'ORG_PORT_BINDINGS.json').write_text(json.dumps(port_bindings,indent=2,sort_keys=True)+'\n')
    result=dict(geometry_check_model='SOURCE_VISIBLE_SURFACES' if surface_mode else 'RAW_SOURCE_PAIR_CONSERVATIVE',source_contact_basis='ORG_SOURCE_CONTACTS_NOT_GROWN_T01_OVERLAP' if surface_mode else 'ORG_SOURCE_CONTACTS',status='C03_CUMULATIVE_T01_T02_PROPOSAL_LOCAL_PASS_NOT_FROZEN',source_sha256=scope['source_sha256'],scope_sha256=hashlib.sha256(scope_path.read_bytes()).hexdigest(),predecessor_result_sha256=hashlib.sha256((circle_stage/'RESULT.json').read_bytes()).hexdigest(),predecessor_cumulative_sha256=prior['after_sha256'],source_circle_targets=len(circle_blobs),circle_parts_unchanged='ALL_EXACT_WKB',rectangle_targets=len(decisions),positive_rectangles=sum(r['positive_growth'] for r in decisions),keep_rectangles=sum(not r['positive_growth'] for r in decisions),final_joint_checks=len(final),added_crop_area_mm2=added.area,removed_predecessor_area_mm2=before.difference(after).area,after_sha256=hashlib.sha256(to_wkb(after)).hexdigest(),rectangle_ceiling=1.25,geometry_family='Full axis-aligned rectangles; bounded two-axis/two-order search with joint predecessor feasibility; no recess',maximum_claim='Best of declared bounded axis orders; no global optimum claim',registration=scope['screenshot_registration'],T03='NOT_RUN',T04='NOT_RUN',scope='C03 source-derived proposal only; no earlier accepted C02 land scene inherited; no native/owner/manufacturing acceptance',asset_integrity=integrity)
    for name,data in [('RESULT.json',result),('RECTANGLE_DECISIONS.json',decisions),('FINAL_JOINT_CHECKS.json',final)]: (out/name).write_text(json.dumps(data,indent=2,sort_keys=True)+'\n')
    # Same native coordinates and source-baseline display transform for all panels.
    for name,bounds in [('full',scope['viewport_mm']),('neighborhood',base['closeup_bounds_mm'])]:
        for stage,copper in [('before',before),('after',after)]:
            svg=out/f'{name}_{stage}.svg';render(svg,f'C03 / cumulative T01+T02 proposal / {name} {stage}',copper,added if stage=='after' else added.difference(added),bounds,notes=[
                f'{len(decisions)}rectangle targets;{result["positive_rectangles"]}positive;{result["keep_rectangles"]}KEEP; ceiling1.25 per axis; full rectangles, no recess.',
                f'All{len(circle_blobs)}round-circle predecessor parts remain byte-identical; all{len(final)}final joint source checks pass.',
                'Red = cumulative copper; teal = exact T02 addition only. Trace routes and widths unchanged.',
                'T01 and T02 changes checked jointly against source-bound full-scene neighbors; no deferred T03 legalization.',
                'Provisional C03 source-derived proposal, not accepted/frozen; screenshot localization still provisional.'])
            subprocess.run(['sips','-s','format','png',str(svg),'--out',str(svg.with_suffix('.png'))],check=True,capture_output=True)
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>C03 cumulative T01+T02</title><style>body{font:18px system-ui;margin:24px}img{max-width:100%}</style><h1>C03 cumulative T01+T02 proposal</h1><p>All supported source targets accounted for; local model proposal, not accepted/frozen.</p><h2>T01 predecessor</h2><img src="full_before.png"><h2>Cumulative T01+T02</h2><img src="full_after.png"><h2>Source neighborhood before / after</h2><img src="neighborhood_before.png"><img src="neighborhood_after.png"><a href="RESULT.json">Coverage and limits</a> · <a href="RECTANGLE_DECISIONS.json">Every rectangle decision</a> · <a href="FINAL_JOINT_CHECKS.json">Every final joint check</a>')
    print(json.dumps(result))

if __name__=='__main__':
    mode='--visible-surfaces' in sys.argv
    args=[a for a in sys.argv[1:] if a!='--visible-surfaces']
    main(*map(Path,args),surface_mode=mode)
