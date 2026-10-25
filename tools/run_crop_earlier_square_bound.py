#!/usr/bin/env python3
"""Source-bound feasibility review of using A's square to bound B growth."""
import argparse,hashlib,html,json,math,platform,shutil,subprocess,sys
from dataclasses import replace
from pathlib import Path
import shapely
from shapely import from_wkb,to_wkb
from shapely.geometry import Point,LineString
from shapely.ops import unary_union
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools import run_crop_square_neighbor_experiment as base
from tools.run_crop_square_rotated_priority import verify_assets
from src.crop_square_neighbor_experiment import Settings,largest_feasible_round,construct,verify_addition,inscribed_square
from src.crop_square_bound_growth import square_bound_radius,outward_halfplane
sha,dump=base.sha,base.dump
POLICY=ROOT/'contracts/crop_earlier_square_envelope_bound_policy.json'
POLICY_SHA='2b2444328a4c42ac1aeac5c4d265e0c5b9b9525804b6e6aebba072890ed19566'
OUT=ROOT/'out/crop_dynamic_tasks/earlier_square_bound_review_20261024'
CHECKS={'round_a_preserved','source_cores_preserved','full_copper_constraints','envelopes_overlap',
        'final_copper_separated','b_envelope_clears_a_square_side','both_larger_than_previous',
        'unsafe_direct_square_stop_rejected','square_bound_changes_b','source_bytes_preserved'}


def publish(out):
    r=json.loads((out/'report.json').read_bytes()); p=json.loads((out/'policy.json').read_bytes())
    audit=json.loads((out/'local_audit.json').read_bytes())
    assert sha(out/'policy.json')==r['policy_sha256']==POLICY_SHA
    assert sha(ROOT/p['source'])==p['source_sha256']==r['source_sha256']
    assert set(r['checks'])==CHECKS and all(v is True for v in r['checks'].values())
    assert audit['status']=='PASS_SCOPED_FEASIBILITY_AUDIT' and audit['report_sha256']==sha(out/'report.json')
    assert len(audit['cases'])==4
    g={}
    for key,expected in r['geometry_sha256'].items():
        assert sha(out/(key+'.wkb'))==expected
        g[key]=from_wkb((out/(key+'.wkb')).read_bytes())
    s=base.shape
    context=s(g['context'],'#697686',opacity=.45)
    cores=s(g['a_core'],'none','#ff8179',.0025)+s(g['b_core'],'none','#ff8179',.0025)
    ar=s(g['a_round'],'#38bfc5',opacity=.85)
    envelopes=s(g['a_round'],'none','#69aafa',.0025,dash='.008 .005')+s(g['b_envelope'],'none','#69aafa',.0025,dash='.008 .005')
    squares=s(g['a_square'],'none','#ffd166',.003)+s(g['b_square'],'none','#a99b6d',.0015)
    side=r['a_square_bound']['side']; x,y=side['vertices']
    stop=f'<path d="M {x[0]} {x[1]} L {y[0]} {y[1]}" stroke="#fff0ab" stroke-width=".007"/>'
    added=s(g['b_final'],'#38d6a0')
    images=[
      ('1 · Same ORG pair','Red outlines are the original cores. Grey copper remains fixed.',context+s(g['a_core'],'#ef6a60')+s(g['b_core'],'#ef6a60')),
      ('2 · Both grow; envelopes now overlap',f'A stays round. Its bright square side facing B limits B’s proposed circular envelope. Magenta is the permitted overlap of the proposed envelopes, not final copper. B-envelope to A-square-side gap: {r["b_envelope_to_a_square_side_gap_mm"]:.5f} mm.',context+ar+s(g['b_core'],'#ef6a60')+envelopes+squares+stop+s(g['envelope_overlap'],'#fa65c0',opacity=.75)+cores),
      ('3 · B recesses around actual round A',f'B’s final green contour clears the actual round A. A’s square controls B’s proposed radius; it cannot replace copper clearance. Final A–B gap: {r["final_pair_gap_mm"]:.5f} mm.',context+ar+s(g['b_removed'],'#ffd166',opacity=.6)+added+envelopes+squares+stop+cores),
      ('4 · What limits A’s round growth?',f'The highlighted grey source circle limits A. A radius: {r["a_radius_mm"]:.6f} mm, previously {r["previous_a_radius_mm"]:.6f} mm. The construction buffer is explicitly reduced from 0.025 to 0.02002 mm; the hard minimum remains 0.020 mm.',context+s(g['a_blocker'],'#f1a36b',opacity=.7)+ar+s(g['old_a'],'none','#c7d4e4',.003,dash='.006 .004')+s(g['b_core'],'#ef6a60')+cores),
      ('5 · Why a direct square-edge stop fails',f'Red is the collision if B stopped only at A’s inner square side plus the gap. The square side lies inside retained round A. This negative control is rejected: {r["unsafe_direct_stop_overlap_mm2"]:.6f} mm² actual copper overlap.',context+ar+s(g['b_direct_unsafe'],'#a68bfa',opacity=.7)+s(g['unsafe_overlap'],'#ff354f')+s(g['a_square'],'none','#ffd166',.003)+stop+cores),
      ('6 · Checked proposal for review','A stays round; B has a round-envelope growth with a curved recess around A. All other source copper stays fixed. This is a proposed interpretation of your clarification, awaiting your conceptual review.',context+ar+added+cores),
    ]
    bounds=unary_union([g['a_round'],g['b_envelope']]).bounds; x0,y0,x1,y1=bounds;pad=.05
    cards=[]
    for i,(title,caption,content) in enumerate(images,1):
        svg=(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{x0-pad} {-y1-pad} {x1-x0+2*pad} {y1-y0+2*pad}" role="img" aria-label="{html.escape(title)}"><rect x="{x0-pad}" y="{-y1-pad}" width="{x1-x0+2*pad}" height="{y1-y0+2*pad}" fill="#111923"/><g transform="scale(1,-1)">{content}</g></svg>')
        (out/f'step_{i}.svg').write_text(svg)
        cards.append(f'<article id="case-{i}"><h2>{title}</h2><img src="step_{i}.svg" alt="{html.escape(title)}"><p>{caption}</p></article>')
    desk='ChatGPT audit: NOT_RUN for this revision.'
    if (out/'chatgpt_desk_audit.json').exists():
        d=json.loads((out/'chatgpt_desk_audit.json').read_bytes()); assert d['report_sha256']==sha(out/'report.json')
        desk='<a href="chatgpt_desk_audit.json">ChatGPT summary-only desk audit recorded</a>.'
    page='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>A-square bound · overlapping envelopes, separated copper</title><style>body{font:16px/1.5 system-ui;background:#eaf0f5;color:#152b40;margin:0}main{max-width:1500px;margin:auto;padding:24px}h1{font-size:29px}.notice{background:#fff0cc;padding:14px;border-left:5px solid #d99a15}.numbers{background:white;padding:14px;border-radius:8px}section{display:grid;grid-template-columns:1fr 1fr;gap:18px}article{background:white;padding:18px;border-radius:12px;border:1px solid #d0dae3}h2{font-size:21px;margin:0 0 12px}img{width:100%;height:350px;background:#111923;border-radius:8px}details{background:white;padding:16px;margin-top:20px}code{overflow-wrap:anywhere}a{color:#086f80}@media(max-width:850px){main{padding:12px}section{grid-template-columns:1fr}img{height:auto;aspect-ratio:1/1}}</style><main><h1>A’s square bounds growth; actual A copper controls clearance</h1><p>Lower-left A stays round. Upper-right B grows into the overlapping-envelope region, then recesses around A.</p><p class="notice"><strong>Proposed interpretation for your review</strong><br>You clarified A’s square side facing B. That side is inside round A, so it bounds B’s proposed envelope here—not B’s final copper edge. Final copper still clears the actual round A. This replaces the previous B-own-square stop experiment only in this new review.</p>'''
    page+=f'<p class="numbers">A radius: {r["previous_a_radius_mm"]:.6f} → <strong>{r["a_radius_mm"]:.6f} mm</strong><br>B proposed radius: {r["previous_b_radius_mm"]:.6f} → <strong>{r["b_radius_mm"]:.6f} mm</strong><br>Proposed-envelope overlap: {r["envelope_overlap_mm2"]:.6f} mm² · actual copper overlap: 0 mm²<br>Hard gap: 0.020 mm · construction buffer: 0.02002 mm, previously 0.025 mm.</p>'
    page+='<p>Blue: proposed envelopes · bright gold: A’s governing square side · teal: round A · green: final B · magenta: envelope overlap only</p><section>'+''.join(cards)+'</section>'
    page+=f'<details><summary>Checks, controls and exact evidence</summary><p>{desk}</p><p>All four saved live/control variants were checked by a fresh process against 17,849 original F.Cu records each. The unsafe straight-side control must fail. Same-author verification, shared parser/kernel; no independent execution claimed.</p>'
    page+=f'<p>At fixed round A and all other copper, bounding B by A’s square instead of A’s whole round envelope changes final B by {r["square_vs_round_bound_changed_area_mm2"]:.6f} mm². This is a bound-selection comparison, not the previous fixed-radius lobe-recession causal test.</p>'
    page+='<p>Source-existing trace ports remain fixed at the previous 1.5× reference, which is no longer a growth cap. Unselected source objects are never rewritten. No EDIT construction input.</p><p><a href="report.json">Receipt</a> · <a href="policy.json">Predeclared policy</a> · <a href="local_audit.json">Full source audit</a> · <a href="SHA256SUMS">Checksums</a></p><p>SIZE_NOT_QUALIFIED · owner review pending · zero T01 acceptance credit. No electrical, native-export or manufacturing qualification.</p></details></main></html>'
    pending=out/'.index.html.next';pending.write_text(page);pending.replace(out/'index.html')


def main(out):
    out=out.resolve(); assert out.is_relative_to(ROOT/'out') and not out.exists()
    assert sha(POLICY)==POLICY_SHA
    p=json.loads(POLICY.read_bytes()); assets=verify_assets(); source_path=ROOT/p['source']
    assert sha(source_path)==p['source_sha256']; source=source_path.read_bytes()
    out.mkdir(parents=True);shutil.copy2(POLICY,out/'policy.json');dump(out/'assets.json',assets)
    inv,rows,shapes,tree,sites=base.source_scene(source,p)
    a=next(s for s in sites if s['source_id']==p['round_priority_source_id']);b=next(s for s in sites if s['source_id']==p['recess_source_id'])
    st=Settings(construction_gap_mm=p['construction_exclusion_mm'],hard_gap_mm=p['hard_experimental_gap_mm'],orientation_degrees=-45)
    def obs(site,bound,accepted=None):
        # Retrieval is deliberately wider than both construction and audit
        # distance bands. It does not change the .02002 construction exclusion.
        retrieval=replace(st,construction_gap_mm=.030)
        found=base.obstacles_for({**site,'enlarged_radius':bound},rows,shapes,tree,source,retrieval,accepted)
        fixed=base.obstacles_for(site,rows,shapes,tree,source,st,accepted)
        ports={r['source_id']:r['port_zone'] for r in fixed if r['port_zone'] is not None}
        for r in found:r['port_zone']=ports.get(r['source_id'])
        return found
    bound=math.dist(a['center'],b['center'])-b['radius']-st.construction_gap_mm
    oa=obs(a,bound)
    ar=largest_feasible_round(a['core'],a['center'],a['radius'],bound,oa,settings=st,safety_mm=p['safety_mm'])
    a['candidate']=ar['candidate']
    br=square_bound_radius(a['center'],ar['radius_mm'],b['center'],st.construction_gap_mm,safety_mm=p['safety_mm'])
    rb=br['radius_mm']; assert rb>=b['radius']
    ob=obs(b,rb,a)
    live=construct(b['core'],b['center'],rb,ob,square_enabled=False,settings=st)
    # Hold A and the complete scene fixed; change only the growth bound.
    circle_cap=math.dist(a['center'],b['center'])-ar['radius_mm']-st.construction_gap_mm-p['safety_mm']
    control=construct(b['core'],b['center'],circle_cap,ob,square_enabled=False,settings=st)
    unsafe=live['envelope'].intersection(outward_halfplane(br['side'],st.construction_gap_mm))
    unsafe_overlap=unsafe.intersection(a['candidate'])
    assembled_oa=obs(a,bound,{**b,'candidate':live['candidate']})
    va=verify_addition(a['core'],a['candidate'],a['candidate'],assembled_oa,settings=st)
    vb=verify_addition(b['core'],live['candidate'],live['envelope'],ob,settings=st)
    vc=verify_addition(b['core'],control['candidate'],control['envelope'],ob,settings=st)
    vbad=verify_addition(b['core'],unsafe,live['envelope'],ob,settings=st)
    closest=min((a['candidate'].distance(r['geometry']),r['source_id'],r['geometry']) for r in oa if r['port_zone'] is None)
    previous=ROOT/p['prior_report'];pr=json.loads(previous.read_bytes());old_a=from_wkb((previous.parent/'a_accepted.wkb').read_bytes())
    linegap=live['envelope'].distance(LineString(br['side']['vertices']))
    pairgap=a['candidate'].distance(live['candidate'])
    changed=live['candidate'].symmetric_difference(control['candidate']).area
    checks={'round_a_preserved':ar['roundness_residual_mm']<=1e-12,
        'source_cores_preserved':va['checks']['source_core_preserved'] and vb['checks']['source_core_preserved'],
        'full_copper_constraints':va['passed'] and vb['passed'] and vc['passed'],
        'envelopes_overlap':a['candidate'].intersection(live['envelope']).area>1e-8,
        'final_copper_separated':pairgap>=st.hard_gap_mm and a['candidate'].intersection(live['candidate']).area<=1e-10,
        'b_envelope_clears_a_square_side':linegap>=st.hard_gap_mm,
        'both_larger_than_previous':ar['radius_mm']>pr['round_priority']['radius_mm'] and rb>pr['b']['enlarged_radius'],
        'unsafe_direct_square_stop_rejected':not vbad['passed'] and unsafe_overlap.area>1e-8,
        'square_bound_changes_b':changed>1e-8,'source_bytes_preserved':sha(source_path)==p['source_sha256']}
    geometry={'a_core':a['core'],'b_core':b['core'],'a_round':a['candidate'],'a_square':br['square'],
        'b_envelope':live['envelope'],'b_square':inscribed_square(b['center'],rb,orientation_degrees=-45),
        'b_final':live['candidate'],'b_round_bound_control':control['candidate'],'b_control_envelope':control['envelope'],
        'b_direct_unsafe':unsafe,'unsafe_overlap':unsafe_overlap,'b_removed':live['envelope'].difference(live['candidate']),
        'envelope_overlap':a['candidate'].intersection(live['envelope']),'a_blocker':closest[2],'old_a':old_a,
        'context':unary_union([r['geometry'] for r in ob if r['source_id']!=a['source_id']])}
    hashes={}
    for name,g in geometry.items():(out/(name+'.wkb')).write_bytes(to_wkb(g,byte_order=1));hashes[name]=sha(out/(name+'.wkb'))
    dump(out/'obstacle_bindings.json',{'a':base.obstacle_records(assembled_oa),'b':base.obstacle_records(ob)})
    r={'schema':'earlier-square-bound-feasibility/1','status':'PROPOSED_INTERPRETATION_PENDING_OWNER_REVIEW' if all(checks.values()) else 'NOT_ESTABLISHED',
        'checks':checks,'policy_sha256':POLICY_SHA,'source_sha256':sha(source_path),'prior_report_sha256':sha(previous),
        'a':base.site_record(a),'b':base.site_record(b),'a_radius_mm':ar['radius_mm'],'b_radius_mm':rb,
        'round_search':{k:v for k,v in ar.items() if k!='candidate'},'a_square_bound':{k:v for k,v in br.items() if k!='square'},
        'b_round_bound_control_radius_mm':circle_cap,'previous_a_radius_mm':pr['round_priority']['radius_mm'],'previous_b_radius_mm':pr['b']['enlarged_radius'],
        'a_active_obstacle':{'source_id':closest[1],'gap_mm':closest[0]},'a_added_area_mm2':a['candidate'].difference(a['core']).area,
        'b_added_area_mm2':live['candidate'].difference(b['core']).area,'envelope_overlap_mm2':geometry['envelope_overlap'].area,
        'b_envelope_to_a_square_side_gap_mm':linegap,'final_pair_gap_mm':pairgap,'unsafe_direct_stop_overlap_mm2':unsafe_overlap.area,
        'square_vs_round_bound_changed_area_mm2':changed,'verification':{'a':va,'b':vb,'control':vc,'unsafe_expected_fail':vbad},
        'geometry_sha256':hashes,'obstacle_bindings_sha256':sha(out/'obstacle_bindings.json'),
        'code_sha256':{name:sha(ROOT/name) for name in ['src/crop_square_bound_growth.py','src/crop_square_neighbor_experiment.py','src/native_inventory.py','tools/run_crop_earlier_square_bound.py','tools/run_crop_square_neighbor_experiment.py','tools/audit_crop_earlier_square_bound.py']},
        'runtime':{'python':platform.python_version(),'shapely':shapely.__version__,'geos':shapely.geos_version_string},
        'size_status':'SIZE_NOT_QUALIFIED','owner_status':'PENDING_USER_PROPOSED_INTERPRETATION','t01_acceptance_event_credit':0,'cursor_review':'NOT_RUN: CHANNEL_UNAVAILABLE'}
    dump(out/'report.json',r)
    for name in r['code_sha256']:
        target=out/'review_source'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/name,target)
    print(json.dumps({k:r[k] for k in ['status','checks','a_radius_mm','b_radius_mm','a_active_obstacle','envelope_overlap_mm2','final_pair_gap_mm','unsafe_direct_stop_overlap_mm2']},indent=2),flush=True)
    assert all(checks.values())
    with (out/'audit.log').open('w') as log:
        subprocess.run([sys.executable,str(ROOT/'tools/audit_crop_earlier_square_bound.py'),str(out)],stdout=log,stderr=subprocess.STDOUT,check=True)
    publish(out)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,default=OUT);parser.add_argument('--publish-only',type=Path)
    args=parser.parse_args()
    if args.publish_only:publish(args.publish_only.resolve())
    else:main(args.output)
