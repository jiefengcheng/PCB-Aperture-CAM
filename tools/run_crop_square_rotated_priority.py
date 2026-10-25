#!/usr/bin/env python3
"""Fresh, source-bound 45-degree square and complete-round-priority review."""
from __future__ import annotations
import argparse
import html
import json
import math
import platform
import shutil
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
import shapely
from shapely import from_wkb, to_wkb
from shapely.geometry import Point
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools import run_crop_square_neighbor_experiment as base
from src.crop_square_neighbor_experiment import (
    Settings, construct, facing_square_side, geometry_hash, inscribed_square,
    largest_feasible_round, verify_addition,
)
sha, dump = base.sha, base.dump
POLICY = ROOT/'contracts/crop_square_rot45_round_priority_policy.json'
POLICY_SHA = 'feee5ac1f75e3cca0065927628fedaa70ff7387f7f58ba17ed565566b650b839'
DEFAULT_OUT = ROOT/'out/crop_dynamic_tasks/square_neighbor_rot45_round_priority_20261024'
REQUIRED_CHECKS = frozenset({
    'original_cores_preserved', 'all_assembled_and_control_constraints',
    'a_is_complete_round_envelope', 'both_squares_on_their_pre_recess_circles',
    'requested_rotation_changes_b_contour', 'earlier_addition_changes_later_copper',
    'square_rule_changes_later_copper', 'square_has_no_effect_without_earlier_addition',
    'square_consumed_only_on_actual_conflict', 'deterministic_replay', 'sealed_source_unchanged',
})


def verify_assets():
    lines = (ROOT/'contracts/asset_manifest.sha256').read_text().splitlines()
    for line in lines:
        expected, relative = line.split(maxsplit=1)
        assert sha(ROOT/relative.lstrip('*')) == expected, relative
    return {'status':'PASS', 'files':len(lines),
            'manifest_sha256':sha(ROOT/'contracts/asset_manifest.sha256')}


def publish(out):
    """Render only saved, hash-bound geometry after the fresh-process audit."""
    assert out.resolve().is_relative_to(ROOT/'out')
    report = json.loads((out/'report.json').read_bytes())
    policy = json.loads((out/'policy.json').read_bytes())
    audit = json.loads((out/'local_full_inventory_audit.json').read_bytes())
    assert report['schema'] == 'square-rot45-round-priority-result/1'
    assert sha(out/'policy.json') == POLICY_SHA == report['policy_sha256']
    assert sha(ROOT/policy['source']) == policy['source_sha256'] == report['source_sha256']
    assert set(report['checks']) == REQUIRED_CHECKS
    assert all(v is True for v in report['checks'].values())
    assert type(report['causal_actual_source_events']) is int and report['causal_actual_source_events'] == 1
    assert report['status'] == 'MECHANISM_DEMONSTRATION_SIZE_NOT_QUALIFIED'
    assert audit['status'] == 'PASS_SCOPED_LOCAL_FULL_INVENTORY_AUDIT'
    assert audit['report_sha256'] == sha(out/'report.json')
    assert len(audit['cases']) == 7 and all(c['full_source_records_scanned'] == 17849 for c in audit['cases'])
    for filename,key in [('selection.json','selection_sha256'),('obstacle_bindings.json','obstacle_bindings_sha256')]:
        assert sha(out/filename) == report[key]
    required = {'a_core','b_core','a_accepted','b_accepted','a_envelope','b_envelope',
                'a_square','b_square','b_square_zero','b_zero_degrees','context',
                'b_without_a_addition','b_without_square','b_without_a_addition_and_square',
                'b_square_removed_optional','b_live_conflict','b_zero_removed_optional'}
    assert set(report['geometry_sha256']) == required
    g = {}
    for key,expected in report['geometry_sha256'].items():
        assert sha(out/(key+'.wkb')) == expected
        g[key] = from_wkb((out/(key+'.wkb')).read_bytes())
    dump(out/'construction_clarification.json', {
        'report_sha256':sha(out/'report.json'),
        'square_owner_source_id':report['b']['source_id'],
        'consumed_square_sha256':report['geometry_sha256']['b_square'],
        'stopping_side':report['square_supporting_line'],
        'interpretation':'B uses its own rotated square side facing round A; A square is shown but does not supply B stopping line.',
        'round_radius_scope':'Source-feasible radius from a 40-step search with 0.00002 mm safety backoff; not a proof of an analytic global maximum.',
    })
    s = base.shape
    common = s(g['context'],'#697686',opacity=.45)
    cores = s(g['a_core'],'#ef6a60')+s(g['b_core'],'#ef6a60')
    core_lines = s(g['a_core'],'none','#ff8179',.002)+s(g['b_core'],'none','#ff8179',.002)
    a_live = s(g['a_accepted'],'#38bfc5',opacity=.85)
    envelopes = ''.join(s(g[key],'none','#69aafa',.0025,dash='.008 .005') for key in ['a_envelope','b_envelope'])
    squares = ''.join(s(g[key],'none','#ffd166',.0025) for key in ['a_square','b_square'])
    line = report['square_supporting_line']['vertices']
    stop = f'<path d="M {line[0][0]} {line[0][1]} L {line[1][0]} {line[1][1]}" fill="none" stroke="#fff0ab" stroke-width=".006"/>'
    da = g['b_accepted'].symmetric_difference(g['b_without_a_addition'])
    ds = g['b_accepted'].symmetric_difference(g['b_without_square'])
    rot = report['rotation_comparison']
    panels = [
      ('1 · ORG source pair','The same two original circles and surrounding copper. A is lower-left; B is upper-right.',common+cores),
      ('2 · 45° squares → actual conflict',
       'A stays completely round at its source-constrained radius. Both gold squares rotate 45°. Blue is the pre-recess circular envelope; magenta marks B’s conflict with A’s clearance exclusion.',
       common+a_live+s(g['b_core'],'#ef6a60')+envelopes+squares+s(g['b_live_conflict'],'#fa65c0',opacity=.85)+core_lines),
      ('3 · Round A → facing-side stop for B',
       'Teal A remains round. B uses its own square’s bright diagonal side facing A as its stop line. Gold is optional copper removed by that side; green is B after all surrounding constraints.',
       common+a_live+s(g['b_square_removed_optional'],'#ffd166',opacity=.65)+s(g['b_accepted'],'#38d6a0')+envelopes+squares+stop+core_lines),
      ('4 · Control: remove only A’s growth',
       f'Purple: B recomputed with A restored to ORG, still at 45°. Green: live B. Pink: changed copper ({report["check_a_symmetric_difference_mm2"]:.6f} mm²). Other settings stay fixed.',
       common+s(g['a_core'],'#ef6a60')+s(g['b_without_a_addition'],'#a68bfa',opacity=.7)+s(g['b_accepted'],'#38d6a0',opacity=.8)+s(da,'#fa65c0')+core_lines),
      ('5 · Control: disable the square stop',
       f'Purple: ordinary clearance clipping with the same round A. Green: square-aware B. Gold: the square’s measured effect ({report["check_b_symmetric_difference_mm2"]:.6f} mm²).',
       common+a_live+s(g['b_without_square'],'#a68bfa',opacity=.8)+s(g['b_accepted'],'#38d6a0',opacity=.8)+s(ds,'#ffd166')+core_lines),
      ('6 · Assembled revised copper',
       f'Teal A is completely round; green B yields to its facing square side. The measured pair gap is {report["a_b_final_copper_gap_mm"]:.5f} mm; the experimental hard minimum is 0.020 mm.',
       common+a_live+s(g['b_accepted'],'#38d6a0')+core_lines),
    ]
    x0,y0,x1,y1 = unary_union([g['a_envelope'],g['b_envelope']]).bounds
    pad=.06
    def svg(title,content):
        return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{x0-pad} {-y1-pad} {x1-x0+2*pad} {y1-y0+2*pad}" role="img" aria-label="{html.escape(title)}">'
                f'<rect x="{x0-pad}" y="{-y1-pad}" width="{x1-x0+2*pad}" height="{y1-y0+2*pad}" fill="#111923"/>'
                f'<g transform="scale(1,-1)">{content}</g></svg>')
    zero_squares = s(inscribed_square(report['a']['center'],report['round_priority']['radius_mm']),'none','#ffd166',.0025)+s(g['b_square_zero'],'none','#ffd166',.0025)
    zero = common+a_live+s(g['b_zero_removed_optional'],'#ffd166',opacity=.65)+s(g['b_zero_degrees'],'#38d6a0')+envelopes+zero_squares+core_lines
    (out/'step_3_zero.svg').write_text(svg('0° comparison; same round A and B radius',zero))
    cards=[]
    for i,(title,caption,content) in enumerate(panels,1):
        (out/f'step_{i}.svg').write_text(svg(title,content))
        controls = ('<div class="switch"><button onclick="setAngle(45)">45° revision</button> <button onclick="setAngle(0)">0° comparison</button> <span id="angle">45° revision</span></div>' if i==3 else '')
        cards.append(f'<article id="case-{i}"><h2>{title}</h2>{controls}<img id="image-{i}" src="step_{i}.svg" alt="{html.escape(title)}"><p>{caption}</p></article>')
    delta=rot['net_retained_area_change_mm2']
    finding = (f'B retains {abs(delta):.6f} mm² {"more" if delta>0 else "less"} copper at 45° than at 0°, with the same round A, B radius and obstacles.')
    audit_extra = 'ChatGPT desk audit: NOT_RUN for this revised execution.'
    if (out/'chatgpt_desk_audit.json').exists():
        desk=json.loads((out/'chatgpt_desk_audit.json').read_bytes())
        assert desk['audited_report_sha256']==sha(out/'report.json')
        audit_extra='<a href="chatgpt_desk_audit.json">ChatGPT desk audit recorded</a>; summary-only, no independent local execution.'
    page='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>45° square revision · round A / recessed B</title><style>
body{font:16px/1.5 system-ui;background:#eaf0f5;color:#152b40;margin:0}main{max-width:1500px;margin:auto;padding:24px}h1{font-size:30px;margin-bottom:6px}.status{padding:12px 18px;background:#fff0cc;border-left:5px solid #d99a15}.finding{padding:14px 18px;background:#fff;border:1px solid #c9d9e4;border-radius:8px}section{display:grid;grid-template-columns:1fr 1fr;gap:18px}article{background:white;border-radius:12px;padding:18px;border:1px solid #d0dae3}h2{font-size:21px;margin:0 0 12px}img{width:100%;height:350px;border-radius:8px;background:#111923}article p{min-height:72px}button{padding:7px 10px;border:1px solid #a2b6c6;border-radius:5px;background:#f5f9fc;cursor:pointer}.switch{margin:0 0 8px;font-size:13px}code{font-size:13px;overflow-wrap:anywhere}details{background:white;padding:16px;margin:16px 0}a{color:#086f80}li{margin:7px 0}@media(max-width:850px){section{grid-template-columns:1fr}main{padding:12px}img{height:auto;aspect-ratio:1/1}} </style><main>
<h1>45° squares: keep A round, let B yield</h1>
<p>Same ORG pair · six regenerated cases · lower-left A stays round; upper-right B uses its facing square side.</p>
<p class="status"><strong>Experimental mechanism · size not qualified · owner review pending</strong><br>Rotation is your requested construction parameter. The 1.5× radius ceiling is retained for this comparison. EDIT supplies no construction geometry. Frozen T01-R1 is unchanged.</p>'''
    page+=f'<p class="finding"><strong>Measured result:</strong> {finding}<br>A’s complete-round radius: {report["round_priority"]["radius_mm"]:.6f} mm. B’s proposed circular radius: {report["b"]["enlarged_radius"]:.6f} mm. Rotation changes the stop direction; it does not increase either proposed radius.</p>'
    page+='<p>Blue: circular envelopes · gold: inscribed squares / removed lobe · teal: round A · green: recessed B · red: original cores</p><section>'+''.join(cards)+'</section>'
    page+='<details><summary>Verification and exact evidence</summary><p>19 geometry and original-publication tests plus 3 revised-publication tests; fresh-process full-inventory audit of 17,849 F.Cu records in each of seven saved variants. This is same-author local verification, not external engineering qualification.</p><ul>'
    page+=''.join(f'<li>{html.escape(k.replace("_"," "))}: {"PASS" if v else "FAIL"}</li>' for k,v in report['checks'].items())
    page+='</ul><p>Source-existing trace contacts are preserved inside the fixed source-derived attachment ports. Other copper remains protected. Contact groups are not verified electrical nets.</p>'
    page+=f'<p>{audit_extra}</p><p><a href="report.json">Execution receipt</a> · <a href="local_full_inventory_audit.json">Full inventory audit</a> · <a href="policy.json">Predeclared policy</a> · <a href="selection.json">Source pair</a> · <a href="SHA256SUMS">Checksums</a></p>'
    page+='<p>B’s own square supplies the facing stop line. A’s round radius is a source-feasible search result with a safety backoff, not a proven mathematical maximum. <a href="construction_clarification.json">Bound construction clarification</a>.</p><p>One mechanism pair; zero frozen T01 event credit. No native export, EDIT equivalence, manufacturing or owner acceptance is claimed.</p></details></main><script>function setAngle(a){document.getElementById("image-3").src=a===45?"step_3.svg":"step_3_zero.svg";document.getElementById("angle").textContent=a===45?"45° revision":"0° comparison (same round A)"}</script></html>'
    pending=out/'.index.html.next'
    pending.write_text(page)
    pending.replace(out/'index.html')


def main(output):
    out=Path(output).resolve()
    if not out.is_relative_to(ROOT/'out') or out.exists():
        raise ValueError('FRESH_PROJECT_OUT_DIRECTORY_REQUIRED')
    assert sha(POLICY)==POLICY_SHA
    policy=json.loads(POLICY.read_bytes())
    assets=verify_assets()
    source_path=ROOT/policy['source']
    assert sha(source_path)==policy['source_sha256']
    previous=ROOT/'out/crop_dynamic_tasks/square_neighbor_mechanism_20261024/report.json'
    assert sha(previous)==policy['source_pair_report_sha256']
    out.mkdir(parents=True)
    shutil.copy2(POLICY,out/'policy.json')
    dump(out/'asset_integrity.json',assets)
    (out/'owner_revision.md').write_text('Owner requested approximately 45-degree rotation of both squares, one fully round priority circle and a facing-square-side stop for the other. All six cases regenerated. Original review and frozen T01 evidence are retained.\n')
    source=source_path.read_bytes()
    settings=Settings(orientation_degrees=policy['orientation_degrees'],
                      construction_gap_mm=policy['construction_exclusion_mm'],
                      hard_gap_mm=policy['hard_experimental_gap_mm'],
                      quad_segs=policy['curve_quadrant_segments'])
    inv,rows,shapes,tree,sites=base.source_scene(source,policy)
    a=next(s for s in sites if s['source_id']==policy['round_priority_source_id'])
    b=next(s for s in sites if s['source_id']==policy['recess_source_id'])
    assert a['physical_contact_group']!=b['physical_contact_group']
    dump(out/'selection.json',{'policy_sha256':POLICY_SHA,'source_sha256':sha(source_path),
        'all_circle_sites':len(sites),'selected_pair':[base.site_record(a),base.site_record(b)],
        'selection_rule':'Same pair as previous source-bound experiment; A retained as round priority per owner revision.'})
    obs_a=base.obstacles_for(a,rows,shapes,tree,source,settings)
    round_a=largest_feasible_round(a['core'],a['center'],a['radius'],a['enlarged_radius'],obs_a,
        settings=settings,search_steps=policy['round_radius_search_steps'],safety_mm=policy['round_radius_safety_mm'])
    a['candidate']=round_a['candidate']
    obs_b=base.obstacles_for(b,rows,shapes,tree,source,settings,a)
    original_obs_b=base.obstacles_for(b,rows,shapes,tree,source,settings)
    for row in original_obs_b:
        if row['source_id'] in a['aliases']:
            row['source_id']=a['source_id']
    kwargs={'earlier_neighbor_id':a['source_id'],'earlier_neighbor_center':a['center'],'settings':settings}
    def candidate(obs,enabled=True,angle=None):
        return construct(b['core'],b['center'],b['enlarged_radius'],obs,square_enabled=enabled,
                         **{**kwargs,'settings':settings if angle is None else replace(settings,orientation_degrees=angle)})
    live=candidate(obs_b)
    no_add=candidate(original_obs_b)
    no_square=candidate(obs_b,False)
    neither=candidate(original_obs_b,False)
    zero=candidate(obs_b,angle=0)
    replay=candidate(obs_b)
    final_obs_a=base.obstacles_for(a,rows,shapes,tree,source,settings,{**b,'candidate':live['candidate']})
    va=verify_addition(a['core'],a['candidate'],a['candidate'],final_obs_a,settings=settings)
    variants={'live':(live,obs_b),'no_add':(no_add,original_obs_b),
              'no_square':(no_square,obs_b),'neither':(neither,original_obs_b),'zero':(zero,obs_b)}
    verifications={k:verify_addition(b['core'],v['candidate'],v['envelope'],obs,settings=settings)
                   for k,(v,obs) in variants.items()}
    dump(out/'obstacle_bindings.json',{
        'a_source_scene':base.obstacle_records(obs_a),'b_live_scene':base.obstacle_records(obs_b),
        'b_source_scene':base.obstacle_records(original_obs_b),'a_assembled_scene':base.obstacle_records(final_obs_a)})
    a_square=inscribed_square(a['center'],round_a['radius_mm'],orientation_degrees=settings.orientation_degrees)
    squares=[(a_square,a['center'],round_a['radius_mm']),(live['square'],b['center'],b['enlarged_radius'])]
    vertex_error=max(abs(math.dist(c,p)-r) for sq,c,r in squares for p in list(sq.exterior.coords)[:4])
    da=live['candidate'].symmetric_difference(no_add['candidate']).area
    ds=live['candidate'].symmetric_difference(no_square['candidate']).area
    baseline=no_add['candidate'].symmetric_difference(neither['candidate']).area
    changed=live['candidate'].symmetric_difference(zero['candidate']).area
    checks={'original_cores_preserved':va['checks']['source_core_preserved'] and verifications['live']['checks']['source_core_preserved'],
        'all_assembled_and_control_constraints':va['passed'] and all(v['passed'] for v in verifications.values()),
        'a_is_complete_round_envelope':a['candidate'].geom_type=='Polygon' and round_a['roundness_residual_mm']<=.00002,
        'both_squares_on_their_pre_recess_circles':vertex_error<=1e-12,
        'requested_rotation_changes_b_contour':changed>settings.event_epsilon_mm2,
        'earlier_addition_changes_later_copper':da>settings.event_epsilon_mm2,
        'square_rule_changes_later_copper':ds>settings.event_epsilon_mm2,
        'square_has_no_effect_without_earlier_addition':baseline<=settings.area_epsilon_mm2,
        'square_consumed_only_on_actual_conflict':live['square_consumed'] and not no_add['square_consumed'],
        'deterministic_replay':geometry_hash(live['candidate'])==geometry_hash(replay['candidate']),
        'sealed_source_unchanged':sha(source_path)==policy['source_sha256']}
    geometries={'a_core':a['core'],'b_core':b['core'],'a_accepted':a['candidate'],'a_envelope':a['candidate'],
        'a_square':a_square,'b_accepted':live['candidate'],'b_envelope':live['envelope'],'b_square':live['square'],
        'b_without_a_addition':no_add['candidate'],'b_without_square':no_square['candidate'],
        'b_without_a_addition_and_square':neither['candidate'],'b_square_removed_optional':live['square_removed_optional'],
        'b_live_conflict':live['neighbor_conflict'],'b_zero_degrees':zero['candidate'],'b_square_zero':zero['square'],
        'b_zero_removed_optional':zero['square_removed_optional'],
        'context':unary_union([r['geometry'] for r in obs_b if r['source_id']!=a['source_id']])}
    hashes={}
    for key,geometry in geometries.items():
        (out/(key+'.wkb')).write_bytes(to_wkb(geometry,byte_order=1))
        hashes[key]=sha(out/(key+'.wkb'))
    report={'schema':'square-rot45-round-priority-result/1',
        'status':'MECHANISM_DEMONSTRATION_SIZE_NOT_QUALIFIED' if all(checks.values()) else 'MECHANISM_NOT_ESTABLISHED',
        'checks':checks,'policy_sha256':POLICY_SHA,'source_sha256':sha(source_path),
        'selection_sha256':sha(out/'selection.json'),'obstacle_bindings_sha256':sha(out/'obstacle_bindings.json'),
        'implementation_sha256':sha(ROOT/'src/crop_square_neighbor_experiment.py'),
        'runner_sha256':sha(Path(__file__)),'helper_sha256':sha(Path(base.__file__)),
        'inventory_sha256':sha(ROOT/'src/native_inventory.py'),
        'runtime':{'python':platform.python_version(),'shapely':shapely.__version__,'geos':shapely.geos_version_string},
        'a':base.site_record(a),'b':base.site_record(b),'source_fcu_objects':len(rows),'unsupported_fcu_objects':0,
        'round_priority':{k:v for k,v in round_a.items() if k!='candidate'},
        'square_vertex_max_error_mm':vertex_error,
        'square_supporting_line':facing_square_side(live['square'],b['center'],a['center']),
        'check_a_symmetric_difference_mm2':da,'check_b_symmetric_difference_mm2':ds,
        'four_condition_control':{'square_effect_with_a_addition_mm2':ds,'square_effect_without_a_addition_mm2':baseline},
        'rotation_comparison':{'baseline_degrees':0,'revised_degrees':-45,'changed_area_mm2':changed,
            'zero_degrees_added_area_mm2':zero['candidate'].difference(b['core']).area,
            'revised_added_area_mm2':live['candidate'].difference(b['core']).area,
            'gained_area_mm2':live['candidate'].difference(zero['candidate']).area,
            'lost_area_mm2':zero['candidate'].difference(live['candidate']).area,
            'net_retained_area_change_mm2':live['candidate'].area-zero['candidate'].area,
            'invariants':'Same round A, B radius, source-derived ports and all source obstacles. No EDIT input.'},
        'a_added_area_mm2':a['candidate'].difference(a['core']).area,
        'b_added_area_mm2':live['candidate'].difference(b['core']).area,
        'a_b_final_copper_gap_mm':a['candidate'].distance(live['candidate']),
        'verification_a_assembled':va,'verification_b_variants':verifications,'geometry_sha256':hashes,
        'causal_actual_source_events':1 if all(checks.values()) else 0,'t01_acceptance_event_credit':0,
        'owner_acceptance':'PENDING_USER_REVISED_VIEW','cursor_review':'NOT_RUN: CHANNEL_UNAVAILABLE',
        'limitations':['1.5x experimental radius ceiling remains unqualified; orientation requested by owner, not inferred from EDIT.',
                       'One mechanism pair, not the unchanged three-event T01 criterion.',
                       'No native export, electrical, manufacturing or owner acceptance.']}
    dump(out/'report.json',report)
    for relative in ['src/crop_square_neighbor_experiment.py','src/native_inventory.py','src/native_reference.py',
                     'tools/run_crop_square_rotated_priority.py','tools/run_crop_square_neighbor_experiment.py',
                     'tools/audit_crop_square_neighbor_experiment.py']:
        target=out/'review_source'/relative
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(ROOT/relative,target)
    print(json.dumps({'status':report['status'],'checks':checks,'round_priority':report['round_priority'],
                      'rotation_comparison':report['rotation_comparison'],'pair_gap_mm':report['a_b_final_copper_gap_mm']},indent=2),flush=True)
    if not all(checks.values()):
        (out/'index.html').write_text('<h1>Revised mechanism not established</h1><a href="report.json">Execution evidence</a>')
        raise SystemExit(1)
    with (out/'local_audit.log').open('w') as log:
        subprocess.run([sys.executable,str(ROOT/'tools/audit_crop_square_neighbor_experiment.py'),
                        '--bundle',str(out)],stdout=log,stderr=subprocess.STDOUT,check=True,cwd=ROOT)
    publish(out)
    print('Published saved six-case review:',out,flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=DEFAULT_OUT)
    parser.add_argument('--publish-only',type=Path,help='Re-render an existing fully bound audited execution.')
    args=parser.parse_args()
    if args.publish_only:
        publish(args.publish_only.resolve())
    else:
        main(args.output)
