#!/usr/bin/env python3
"""Balanced source-bound pair with an unconditional 1.5x radius ceiling."""
import argparse,html,json,math,platform,shutil,subprocess,sys
from pathlib import Path
import shapely
from shapely import from_wkb,to_wkb
from shapely.geometry import Point
from shapely.ops import unary_union
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools import run_crop_square_neighbor_experiment as base
from tools.run_crop_square_rotated_priority import verify_assets
from src.crop_square_neighbor_experiment import Settings,largest_feasible_round,construct,verify_addition,inscribed_square,facing_square_side
from src.crop_balanced_capped_growth import shared_factor,require_radius_cap
sha,dump=base.sha,base.dump
POLICY=ROOT/'contracts/crop_balanced_hard_cap_policy.json'
POLICY_SHA='d98a1a1d9ed706eb6a4b84e50b98c645255cee1831aac970589d5d2f6422941d'
OUT=ROOT/'out/crop_dynamic_tasks/balanced_capped_pair_20261024'
CHECKS={'hard_radius_caps','shared_scale','round_a','cores_preserved','source_constraints','a_square_gap','over_cap_rejected','source_unchanged'}


def publish(out):
    assert out.resolve().is_relative_to(ROOT/'out')
    r=json.loads((out/'report.json').read_bytes());p=json.loads((out/'policy.json').read_bytes());audit=json.loads((out/'local_audit.json').read_bytes())
    assert sha(out/'policy.json')==r['policy_sha256']==POLICY_SHA
    assert sha(ROOT/p['source'])==p['source_sha256']==r['source_sha256']
    assert r['status']=='BALANCED_HARD_CAPPED_PAIR_FOR_OWNER_REVIEW' and set(r['checks'])==CHECKS and all(v is True for v in r['checks'].values())
    assert audit['report_sha256']==sha(out/'report.json') and audit['status']=='PASS_BALANCED_CAPPED_LOCAL_AUDIT'
    g={}
    for key,h in r['geometry_sha256'].items():assert sha(out/(key+'.wkb'))==h;g[key]=from_wkb((out/(key+'.wkb')).read_bytes())
    s=base.shape;context=s(g['context'],'#697686',opacity=.45)
    cores=s(g['a_core'],'none','#ff8179',.0025)+s(g['b_core'],'none','#ff8179',.0025)
    ar=s(g['a_round'],'#38bfc5',opacity=.85)
    envelopes=s(g['a_round'],'none','#69aafa',.0025,dash='.008 .005')+s(g['b_envelope'],'none','#69aafa',.0025,dash='.008 .005')
    squares=s(g['a_square'],'none','#ffd166',.0025)+s(g['b_square'],'none','#ffd166',.0025)
    final=context+ar+s(g['b_final'],'#38d6a0')+cores
    panels=[
      ('1 · Same source circles','Both original ORG circles have the same source radius. Grey source copper stays fixed.',context+s(g['a_core'],'#ef6a60')+s(g['b_core'],'#ef6a60')),
      ('2 · Same enlargement factor for both',f'Both proposed radii use {r["shared_factor"]:.6f}× the source radius, always ≤1.5×. Both 45° squares derive from these enlarged circles.',context+ar+s(g['b_core'],'#ef6a60')+envelopes+squares+cores),
      ('3 · Balanced result under local clearance',f'A remains round; B receives the same proposed growth factor and is clipped only where existing source copper requires clearance. Pair gap: {r["pair_gap_mm"]:.6f} mm.',final+envelopes+squares),
      ('4 · Why the shared factor stops here',f'Orange is A’s limiting source neighbour. The faint blue circle is the 1.5× cap; red shows why A cannot reach that cap while remaining round. Both sites use A’s smaller feasible factor.',context+s(g['a_blocker'],'#f1a36b',opacity=.7)+ar+s(g['a_cap'],'none','#9aafc5',.003,dash='.006 .004')+s(g['a_cap_intrusion'],'#ff354f')+s(g['b_core'],'#ef6a60')+cores),
      ('5 · Hard ceiling: larger proposals rejected','Blue is the allowed 1.5× boundary. The red 2× diagnostic is rejected before editing; extra space cannot override the cap. It is a negative control, never accepted copper.',context+ar+s(g['b_core'],'#ef6a60')+s(g['b_cap'],'none','#69aafa',.003)+s(g['over_cap_negative'],'none','#ff354f',.004,dash='.008 .005')+cores),
      ('6 · Final balanced copper','Same proposed growth factor, protected source cores, fixed surrounding copper. Square-driven interaction is inactive for this pair at the balanced capped radii; no interaction event is claimed.',final),
    ]
    x0,y0,x1,y1=unary_union([g['a_round'],g['over_cap_negative']]).bounds;pad=.04
    cards=[]
    for i,(title,caption,content) in enumerate(panels,1):
        svg=f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{x0-pad} {-y1-pad} {x1-x0+2*pad} {y1-y0+2*pad}" role="img" aria-label="{html.escape(title)}"><rect x="{x0-pad}" y="{-y1-pad}" width="{x1-x0+2*pad}" height="{y1-y0+2*pad}" fill="#111923"/><g transform="scale(1,-1)">{content}</g></svg>'
        (out/f'step_{i}.svg').write_text(svg);cards.append(f'<article id="case-{i}"><h2>{title}</h2><img src="step_{i}.svg" alt="{html.escape(title)}"><p>{caption}</p></article>')
    desk='ChatGPT audit: NOT_RUN for this balanced revision.'
    if (out/'chatgpt_desk_audit.json').exists():
        d=json.loads((out/'chatgpt_desk_audit.json').read_bytes());assert d['report_sha256']==sha(out/'report.json');desk='<a href="chatgpt_desk_audit.json">ChatGPT summary-only audit recorded</a>.'
    page='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Balanced growth · hard 1.5× ceiling</title><style>body{font:16px/1.5 system-ui;background:#eaf0f5;color:#152b40;margin:0}main{max-width:1500px;margin:auto;padding:24px}h1{font-size:29px}.notice{background:#fff0cc;padding:14px;border-left:5px solid #d99a15}.numbers{background:white;padding:14px;border-radius:8px}section{display:grid;grid-template-columns:1fr 1fr;gap:18px}article{background:white;padding:18px;border-radius:12px;border:1px solid #d0dae3}h2{font-size:21px;margin:0 0 12px}img{width:100%;height:350px;background:#111923;border-radius:8px}details{background:white;padding:16px;margin-top:20px}a{color:#086f80}@media(max-width:850px){main{padding:12px}section{grid-template-columns:1fr}img{height:auto;aspect-ratio:1/1}}</style><main><h1>Balanced growth, with a hard 1.5× ceiling</h1><p>One shared enlargement factor for A and B. A stays round; surrounding copper remains protected.</p><p class="notice"><strong>Owner-requested balance and hard-cap revision · review pending</strong><br>The earlier over-cap proposal is rejected under your clarified rule and retained only as historical evidence. No proposed radius can exceed 1.5× its own source radius.</p>'''
    page+=f'<p class="numbers"><strong>A: {r["shared_factor"]:.6f}× → {r["a_radius_mm"]:.6f} mm</strong><br><strong>B: {r["shared_factor"]:.6f}× → {r["b_radius_mm"]:.6f} mm</strong><br>Hard ceiling for each: {r["a"]["radius"]*1.5:.6f} mm (1.5×)<br>Shared factor is limited by A’s source neighbour. Proposed circles do not overlap at this factor; no square-mediated event is claimed.</p>'
    page+='<p>Blue: proposed envelopes / cap · gold: derived 45° squares · teal: round A · green: B after local constraints · red outlines: original cores</p><section>'+''.join(cards)+'</section>'
    page+=f'<details><summary>Recorded checks and source evidence</summary><p>{desk}</p><p>“Same scale” means the same radius multiplier before clipping. Final areas can differ because surrounding source copper differs.</p><p>Hard copper minimum remains 0.020 mm. Construction buffer is 0.02002 mm. Source-derived attachment ports stay fixed. A’s square remains a proposed-envelope bound, but the shared factor and source constraints stop growth first.</p><p>Fresh-process full-source audit, hard-cap negative control, saved source/geometry hashes. Same-author checks, shared parser/kernel; not independent engineering qualification.</p><p><a href="report.json">Receipt</a> · <a href="policy.json">Policy</a> · <a href="local_audit.json">Source/cap audit</a> · <a href="SHA256SUMS">Checksums</a></p><p>SIZE_NOT_QUALIFIED · owner review pending · zero T01 credit. No manufacturing or electrical acceptance.</p></details></main></html>'
    pending=out/'.index.html.next';pending.write_text(page);pending.replace(out/'index.html')


def main(out):
    out=out.resolve();assert out.is_relative_to(ROOT/'out') and not out.exists();assert sha(POLICY)==POLICY_SHA
    p=json.loads(POLICY.read_bytes());assets=verify_assets();source_path=ROOT/p['source'];assert sha(source_path)==p['source_sha256'];source=source_path.read_bytes()
    out.mkdir(parents=True);shutil.copy2(POLICY,out/'policy.json');dump(out/'assets.json',assets)
    inv,rows,shapes,tree,sites=base.source_scene(source,p)
    a=next(s for s in sites if s['source_id']==p['round_priority_source_id']);b=next(s for s in sites if s['source_id']==p['recess_source_id'])
    st=Settings(construction_gap_mm=.02002,hard_gap_mm=.020,orientation_degrees=-45)
    # All retrieval extents use the fixed 1.5x cap; cap cannot be expanded by a search.
    oa=base.obstacles_for(a,rows,shapes,tree,source,st)
    ar=largest_feasible_round(a['core'],a['center'],a['radius'],1.5*a['radius'],oa,settings=st)
    side=facing_square_side(inscribed_square(a['center'],ar['radius_mm'],orientation_degrees=-45),a['center'],b['center'])
    projection=sum(side['normal'][i]*(b['center'][i]-a['center'][i]) for i in range(2))
    square_factor=(projection-st.construction_gap_mm-p['safety_mm'])/(b['radius']+a['radius']/math.sqrt(2))
    factor,(ra,rb)=shared_factor([a['radius'],b['radius']],source_feasible_factor=ar['radius_mm']/a['radius'],square_pair_factor=square_factor)
    require_radius_cap(a['radius'],ra);require_radius_cap(b['radius'],rb)
    a['candidate']=Point(*a['center']).buffer(ra,quad_segs=128)
    ob=base.obstacles_for(b,rows,shapes,tree,source,st,a)
    live=construct(b['core'],b['center'],rb,ob,square_enabled=False,settings=st)
    at_cap=construct(b['core'],b['center'],1.5*b['radius'],ob,square_enabled=False,settings=st)
    oa_final=base.obstacles_for(a,rows,shapes,tree,source,st,{**b,'candidate':live['candidate']})
    va=verify_addition(a['core'],a['candidate'],a['candidate'],oa_final,settings=st)
    vb=verify_addition(b['core'],live['candidate'],live['envelope'],ob,settings=st)
    vc=verify_addition(b['core'],at_cap['candidate'],at_cap['envelope'],ob,settings=st)
    negative_radius=2*b['radius'];negative_rejected=False
    try:require_radius_cap(b['radius'],negative_radius)
    except ValueError as exc:negative_rejected=str(exc)=='HARD_1_5X_CEILING_EXCEEDED'
    closest=min((a['candidate'].distance(r['geometry']),r['source_id'],r['geometry']) for r in oa if r['port_zone'] is None)
    a_cap=Point(*a['center']).buffer(1.5*a['radius'],quad_segs=128)
    a_sq=inscribed_square(a['center'],ra,orientation_degrees=-45)
    side=facing_square_side(a_sq,a['center'],b['center'])
    side_distance=sum(side['normal'][i]*(b['center'][i]-side['midpoint'][i]) for i in range(2))-rb
    checks={'hard_radius_caps':ra<=1.5*a['radius'] and rb<=1.5*b['radius'],
        'shared_scale':abs(ra/a['radius']-rb/b['radius'])<=1e-12,
        'round_a':max(abs(math.dist(a['center'],v)-ra) for v in a['candidate'].exterior.coords)<=1e-12,
        'cores_preserved':va['checks']['source_core_preserved'] and vb['checks']['source_core_preserved'],
        'source_constraints':va['passed'] and vb['passed'] and vc['passed'],
        'a_square_gap':side_distance>=st.hard_gap_mm,'over_cap_rejected':negative_rejected,
        'source_unchanged':sha(source_path)==p['source_sha256']}
    geometry={'a_core':a['core'],'b_core':b['core'],'a_round':a['candidate'],'b_final':live['candidate'],'b_envelope':live['envelope'],
        'a_square':a_sq,'b_square':live['square'],'a_blocker':closest[2],'a_cap':a_cap,
        'a_cap_intrusion':a_cap.intersection(closest[2].buffer(st.construction_gap_mm,quad_segs=128)),
        'b_cap':at_cap['envelope'],'b_at_cap_control':at_cap['candidate'],
        'over_cap_negative':Point(*b['center']).buffer(negative_radius,quad_segs=128),
        'context':unary_union([r['geometry'] for r in ob if r['source_id']!=a['source_id']])}
    hashes={}
    for name,g in geometry.items():(out/(name+'.wkb')).write_bytes(to_wkb(g,byte_order=1));hashes[name]=sha(out/(name+'.wkb'))
    dump(out/'obstacle_bindings.json',{'a':base.obstacle_records(oa_final),'b':base.obstacle_records(ob)})
    report={'schema':'balanced-capped-pair/1','status':'BALANCED_HARD_CAPPED_PAIR_FOR_OWNER_REVIEW' if all(checks.values()) else 'NOT_ESTABLISHED',
        'checks':checks,'policy_sha256':POLICY_SHA,'source_sha256':sha(source_path),'a':base.site_record(a),'b':base.site_record(b),
        'shared_factor':factor,'a_radius_mm':ra,'b_radius_mm':rb,'hard_factor_ceiling':1.5,'square_pair_factor_bound':square_factor,
        'a_square_side':side,'b_envelope_to_a_square_supporting_line_gap_mm':side_distance,'pair_gap_mm':a['candidate'].distance(live['candidate']),
        'proposed_envelope_overlap_mm2':a['candidate'].intersection(live['envelope']).area,'square_interaction_status':'NOT_EXERCISED_AT_BALANCED_CAPPED_RADII',
        'a_added_area_mm2':a['candidate'].difference(a['core']).area,'b_added_area_mm2':live['candidate'].difference(b['core']).area,
        'a_active_obstacle_source_id':closest[1],'a_active_obstacle_gap_mm':closest[0],
        'negative':{'proposed_factor':2,'radius_mm':negative_radius,'rejected':negative_rejected,'reason':'HARD_1_5X_CEILING_EXCEEDED'},
        'verification':{'a':va,'b':vb,'at_cap_control':vc},'geometry_sha256':hashes,'obstacle_bindings_sha256':sha(out/'obstacle_bindings.json'),
        'code_sha256':{name:sha(ROOT/name) for name in ['src/crop_balanced_capped_growth.py','src/crop_square_neighbor_experiment.py','src/native_inventory.py','tools/run_crop_balanced_capped_pair.py','tools/run_crop_square_neighbor_experiment.py','tools/audit_crop_balanced_capped_pair.py']},
        'runtime':{'python':platform.python_version(),'shapely':shapely.__version__,'geos':shapely.geos_version_string},
        'owner_status':'PENDING_USER_BALANCED_CAPPED_REVIEW','size_status':'SIZE_NOT_QUALIFIED','t01_acceptance_event_credit':0,'cursor_review':'NOT_RUN: CHANNEL_UNAVAILABLE'}
    dump(out/'report.json',report)
    for name in report['code_sha256']:
        dest=out/'review_source'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/name,dest)
    print(json.dumps({key:report[key] for key in ['status','checks','shared_factor','a_radius_mm','b_radius_mm','pair_gap_mm','proposed_envelope_overlap_mm2']},indent=2),flush=True)
    assert all(checks.values())
    with (out/'audit.log').open('w') as log:subprocess.run([sys.executable,str(ROOT/'tools/audit_crop_balanced_capped_pair.py'),str(out)],stdout=log,stderr=subprocess.STDOUT,check=True)
    publish(out)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,default=OUT);parser.add_argument('--publish-only',type=Path);args=parser.parse_args()
    if args.publish_only:publish(args.publish_only.resolve())
    else:main(args.output)
