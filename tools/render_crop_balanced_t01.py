#!/usr/bin/env python3
"""Render the saved, freshly audited full crop; presentation controls only."""
import argparse,html,json,shutil,sys
from pathlib import Path
from shapely import from_wkb
from shapely.geometry import box
from shapely.ops import unary_union
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src import crop_circle_sources as base
sha,dump=base.sha,base.dump
POLICY_SHA='b7b2063cdeadac5ccb1fe44ab872a596428f7a2caaa7d2dacbcd72c392605f59'

def require_round_diagnostics(report,audit):
    expected={d['source_id']:d['size_class']['round_opportunity']['next_class_diameter_mm'] for d in report['decisions'] if d['priority'] and d['size_class']['round_opportunity']['next_class_diameter_mm'] is not None}
    controls=audit['round_next_class_controls']
    assert len(controls)==len(expected) and {c['source_id'] for c in controls}==set(expected)
    for control in controls:
        assert control['diameter_mm']==expected[control['source_id']]
        assert control['source_case']['violations'] or control['round_blockers'] or control['square_blockers']

def diameter_review(r,p,out,audit):
    comparison=r['previous_comparison'];marked=sorted([c for c in comparison['sites'] if c['annotation_number']],key=lambda c:c['annotation_number'])
    content='<h2>Common sizes, with explicit exceptions</h2><p>Proposed envelope diameters (mm): <strong>'+', '.join(f'{d:.4f}' for d in p['diameter_classes_mm'])+'</strong>. These are provisional geometric bands derived from ORG size ranges, not manufacturing standards or sizes traced from EDIT. Recessed contours can differ; grey sites retain exact original geometry.</p>'
    from collections import Counter
    counts=Counter(d['size_class']['category_mm'] for d in r['decisions'])
    colors=['#8bd3ff','#ffe08a','#60dba8','#d6a7ff','#ffb285','#f388a5','#a7deca']
    content+='<p>'+''.join(f'<span style="display:inline-block;margin:4px;padding:5px 9px;background:{colors[i]};color:#152b40;border-radius:5px">Ø {diameter:.4f} · {counts[diameter]} sites</span>' for i,diameter in enumerate(p['diameter_classes_mm']))+f'<span> · {counts[None]} exact source target KEEPs; {sum(d['size_class']['category_mm'] is not None and d['added_area_mm2']<=1e-10 for d in r['decisions'])} class proposals add no copper after clipping</span></p>'
    content+=f'<p>Added copper: {comparison["previous_effective_added_union_mm2"]:.6f} → {r["effective_added_union_mm2"]:.6f} mm². {comparison["sites_with_more_added_area"]} sites gain more than before; {comparison["sites_with_less_added_area"]} gain less. The trial prioritizes common sizes; it does not promise that every site grows more.</p>'
    improved=sum(c['net_area_change_mm2']>1e-8 for c in marked)
    if not p.get('owner_review_application'):
        content+=f'<p><strong>{improved} of your {len(marked)} marked sites now gain more copper. Any marked site with no area increase remains open; its full-round outline and protections are retained.</strong></p>'
    content+=f'<h2>Your {len(marked)} marked locations</h2><p>Each card uses the same local frame as its saved source-bound site view. “Diameter” describes the envelope before recessing.</p>'
    if p.get('owner_review_application'):
        content+='<p><strong>Owner review applied: S38 and S22 restored to their exact pre-promotion round contours; S08 grows with a square-guided recess toward S12.</strong> Reversions are requested corrections, not failed growth. Other target radii are frozen; related companion contours can readapt.</p>'
    controls={c['source_id']:c for c in audit.get('round_next_class_controls',[])}
    keyfor={d['source_id']:d['key'] for d in r['decisions']}
    for c in marked:
        d=next(d for d in r['decisions'] if d['source_id']==c['source_id'])
        reason='Square-guided recess; original core retained. Exception to full-round reservation.' if d['square_guided'] else 'Fully round priority at a verified physical size class; no new recess exception.' if d['priority'] else 'Independent shared-class target; no longer inherits a partner’s smaller growth factor.'
        if d['size_class'].get('round_opportunity'):
            opportunity=d['size_class']['round_opportunity']
            names=sorted({item['reason'].replace('_',' ').lower() for item in opportunity['blockers']})
            reason+=' Next class '+str(opportunity['next_class_diameter_mm'])+' mm: '+(', '.join(names) if names else 'desired class/cap reached')+'.'
        if d['square_guided']:
            control=next(control for control in r['square_disabled_controls'] if control['source_id']==d['source_id'])
            reason+=f' Square on/off changes {control["symmetric_difference_mm2"]:.6f} mm² with target size and input scene held fixed.'
        control=controls.get(c['source_id'])
        why=''
        if control:
            details=[]
            if control['source_case']['violations']:details.append('original copper / fixed source-port clearance')
            if control['round_blockers']:details.append('round reservations: '+', '.join(keyfor.get(b['source_id'],'source object')+f' (next-class gap {b["gap_mm"]:.6f} mm)' for b in control['round_blockers']))
            if control['square_blockers']:details.append('auxiliary square-side bounds: '+', '.join(b['group_id'] for b in control['square_blockers']))
            why=f'<h3>Why the next round size stops at Ø {control["diameter_mm"]:.4f} mm</h3><p>'+html.escape('; '.join(details))+f'.</p><img src="focus/{c["key"]}_next_round.svg" alt="Mark {c["annotation_number"]} rejected next round class"><p>Blue: rejected next circle. Green: selected round circle. Pink: new intrusion into the protected 0.020 mm gap. A square-side bound can reject a size without a visible copper collision. This is a rejected diagnostic, never accepted copper.</p>'
        expanded=c['annotation_number']==(3 if p.get('owner_review_application') else 1 if p.get('round_promotion') else 6)
        content+=f'<details id="mark-{c["annotation_number"]}" {"open" if expanded else ""}><summary>Mark {c["annotation_number"]} · {c["key"]} · Ø {c["old_diameter_mm"]:.4f} → {c["new_diameter_mm"]:.4f} mm · area change {c["net_area_change_mm2"]:+.6f} mm²</summary><p>{reason}</p><div class="grid"><article><h2>Previous result</h2><img src="focus/{c["key"]}_previous.svg" alt="Mark {c["annotation_number"]} previous result"></article><article><h2>Current result and construction</h2><img src="focus/{c["key"]}_final.svg" alt="Mark {c["annotation_number"]} revised result"></article></div><p><a href="report.json">Source identity, dimensions, limits and consumed square sides</a></p>{why}</details>'
    return content


def publish(out):
    assert out.resolve().is_relative_to(ROOT/'out')
    r=json.loads((out/'report.json').read_bytes());p=json.loads((out/'policy.json').read_bytes());a=json.loads((out/'fresh_audit.json').read_bytes())
    class_mode=p['schema'].startswith('diameter-class-t01-trial-policy/')
    expected={'diameter-class-t01-trial-policy/1':'c5605b67986dfb64a7cf1cf8400aa624547231e73145af0ea39e7fa1b9731397','diameter-class-t01-trial-policy/2':'b74681cec401ba54ca2e92fc0dc6d265a1373d21892be0e200993f7ca44d47be','diameter-class-t01-trial-policy/3':'1b084cb2366a08e356841ebe5b8890248ba0f75656280e174dee23af1f1fcf5f'}.get(p['schema'],POLICY_SHA)
    assert sha(out/'policy.json')==r['policy_sha256']==expected
    assert sha(ROOT/p['source'])==r['source_sha256']==p['source_sha256']
    assert sha(out/'selection.json')==r['selection_sha256']
    assert a['status']=='PASS_SCOPED_FRESH_CROP_AUDIT' and a['report_sha256']==sha(out/'report.json')
    if p.get('owner_review_application'):
        assert {row['key'] for row in a['owner_review_checks']}==set(p['marked_sites'])
    assert len(a['dynamic_cases'])==51 and all(not c['violations'] for c in a['dynamic_cases'])
    if p.get('round_promotion'):
        require_round_diagnostics(r,a)
        coverage=[]
        for d in r['decisions']:
            if not d['priority']:continue
            size=d['size_class'];next_class=size['round_opportunity']['next_class_diameter_mm']
            coverage.append({'key':d['key'],'source_id':d['source_id'],'allocated_diameter_mm':2*d['proposed_radius_mm'],
                'local_desired_diameter_mm':size['desired_diameter_mm'],'individual_cap_diameter_mm':size['hard_cap_diameter_mm'],
                'next_class_diameter_mm':next_class,'status':'NEXT_LOCAL_CLASS_TESTED_AND_REJECTED' if next_class is not None else 'AT_LOCAL_DESIRED_CLASS',
                'larger_palette_classes_outside_local_desired':[v for v in size['admissible_classes_mm'] if v>size['desired_diameter_mm']]})
        dump(out/'round_priority_coverage.json',{'report_sha256':sha(out/'report.json'),'audit_sha256':sha(out/'fresh_audit.json'),'total_round_priorities':len(coverage),
            'tested_next_class':len(a['round_next_class_controls']),'at_local_desired_class':sum(row['next_class_diameter_mm'] is None for row in coverage),'sites':coverage,
            'scope':'No feasible next-band promotion with existing other assignments, local desired classes and constraints held fixed. Not a global optimum or individual-cap maximality claim.'})
    assert r['same_policy_replay_equal'] is True and r['unique_sites']==51 and r['source_occurrences']==53
    g={}
    for name,h in r['geometry_sha256'].items():assert sha(out/(name+'.wkb'))==h;g[name+'.wkb']=from_wkb((out/(name+'.wkb')).read_bytes())
    decisions=r['decisions'];byid={d['source_id']:d for d in decisions};context=g['context.wkb'];frame=p['viewport_mm']
    def svg(bounds,content,title):
        x0,y0,x1,y1=bounds
        return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{x0} {-y1} {x1-x0} {y1-y0}" role="img" aria-label="{html.escape(title)}"><rect x="{x0}" y="{-y1}" width="{x1-x0}" height="{y1-y0}" fill="#111923"/><g transform="scale(1,-1)">{content}</g></svg>'
    s=base.shape
    whole={
        'original':s(g['original_effective.wkb'],'#ec5c62'),
        'dynamic':s(g['dynamic_effective.wkb'],'#ec5c62'),
        'overlay':s(g['original_effective.wkb'],'#b9c3ce',opacity=.75)+s(g['additions.wkb'],'#38d6a0'),
        'static':s(g['static_effective.wkb'],'#a68bfa'),
        'priorities':s(g['dynamic_effective.wkb'],'#697686',opacity=.7)+''.join(s(g[d['geometry']['dynamic']],'#ffd166' if d['priority'] else '#38d6a0',opacity=.85) for d in decisions),
    }
    if class_mode:
        whole['previous']=s(g['previous_effective.wkb'],'#ec5c62')
        colors=['#8bd3ff','#ffe08a','#60dba8','#d6a7ff','#ffb285','#f388a5','#a7deca']
        whole['classes']=s(context,'#697686',opacity=.7)+''.join(s(g[d['geometry']['dynamic']],colors[p['diameter_classes_mm'].index(d['size_class']['category_mm'])] if d['size_class']['category_mm'] is not None and d['added_area_mm2']>1e-10 else '#bdc7d2') for d in decisions)
    whole['sites']=whole['dynamic']+''.join(f'<text x="{d["center"][0]}" y="{-d["center"][1]}" transform="scale(1,-1)" fill="white" stroke="#111923" stroke-width=".008" paint-order="stroke" text-anchor="middle" dominant-baseline="middle" font-size=".065" font-family="system-ui">{d["key"]}</text>' for d in decisions)
    for name,content in whole.items():(out/f'crop_{name}.svg').write_text(svg(frame,content,name))
    # Explicitly show complete selected edge circles and any permitted writes outside V.
    x0,y0,x1,y1=g['write_domain_caps.wkb'].bounds;outside_frame=(x0-.05,y0-.05,x1+.05,y1+.05)
    (out/'crop_outside.svg').write_text(svg(outside_frame,whole['overlay']+s(box(*frame),'none','#ffd166',.008,dash='.02 .012'),'Full selected envelopes; gold is fixed display crop'))
    focus=out/'focus';focus.mkdir(exist_ok=True)
    site_ui={}
    for d in decisions:
        key=d['key'];cx,cy=d['center'];half=max(.13,1.5*d['source_radius_mm']+.10)
        bounds=(cx-half,cy-half,cx+half,cy+half)
        core=g[d['geometry']['core']];candidate=g[d['geometry']['dynamic']];envelope=g[d['geometry']['envelope']];square=g[d['geometry']['square']]
        others=unary_union([context,*[g[other['geometry']['dynamic']] for other in decisions if other['source_id']!=d['source_id']]])
        # Original panel uses only original copper; proposed panel uses the final
        # accepted scene. Gold envelopes/squares are diagnostic constructions.
        original=s(g['original_effective.wkb'],'#ec5c62')
        final=s(others,'#697686',opacity=.7)+s(candidate,'#38bfc5' if d['priority'] else '#38d6a0')+s(core,'none','#ff8179',.002)+s(envelope,'none','#69aafa',.002,dash='.007 .005')+s(square,'none','#ffd166',.002)
        (focus/f'{key}_original.svg').write_text(svg(bounds,original,key+' ORG'))
        (focus/f'{key}_final.svg').write_text(svg(bounds,final,key+' accepted'))
        if class_mode:(focus/f'{key}_previous.svg').write_text(svg(bounds,s(g['previous_effective.wkb'],'#ec5c62'),key+' previous result'))
        site_ui[key]={k:d[k] for k in ['source_id','factor','group_id','priority','decision','source_radius_mm','proposed_radius_mm','added_area_mm2','static_changed_area_mm2','center']}
        if class_mode:site_ui[key].update(class_mm=d['size_class']['category_mm'],square_guided=d['square_guided'],limits=d['size_class']['limits'])
        site_ui[key]['events']=sum(e['target_source_id']==d['source_id'] for e in r['events'])
    for control in a.get('round_next_class_controls',[]):
        d=byid[control['source_id']];cx,cy=d['center'];half=max(.13,1.5*d['source_radius_mm']+.10)
        bounds=(cx-half,cy-half,cx+half,cy+half)
        proof={}
        for kind,entry in control['geometry'].items():
            assert sha(out/entry['path'])==entry['sha256'];proof[kind]=from_wkb((out/entry['path']).read_bytes())
        round_context=unary_union([context,*[g[other['geometry']['dynamic' if other['priority'] else 'core']] for other in decisions if other['source_id']!=d['source_id']]])
        content=s(round_context,'#697686',opacity=.75)+s(proof['circle'],'#69aafa',opacity=.25)+s(g[d['geometry']['dynamic']],'#38d6a0',opacity=.8)+s(proof['circle'],'none','#69aafa',.003)+s(proof['intrusion'],'#f64cb6')
        (focus/f'{d["key"]}_next_round.svg').write_text(svg(bounds,content,d['key']+' rejected next full-round class'))
    diagnostic=''
    if r['events']:
        event=max(r['events'],key=lambda e:e['changed_area_mm2'])
        target=byid[event['target_source_id']];neighbor=byid[event['neighbor_source_id']]
        before_ids={d['source_id'] for d in decisions[:event['input_scene_revision']]}
        def event_context(restored):
            shapes=[context]
            for d in decisions:
                if d['source_id']==target['source_id']:continue
                kind='dynamic' if d['source_id'] in before_ids else 'core'
                if restored and d['source_id']==neighbor['source_id']:kind='core'
                shapes.append(g[d['geometry'][kind]])
            return unary_union(shapes)
        cx,cy=target['center'];half=max(.35,1.5*target['source_radius_mm']+.14)
        bounds=(cx-half,cy-half,cx+half,cy+half)
        for name,restored in [('event_with_priority',False),('event_restored_priority',True)]:
            candidate=g[event['counterfactual_wkb']] if restored else g[target['geometry']['dynamic']]
            content=s(event_context(restored),'#697686',opacity=.7)+s(candidate,'#38d6a0')+s(g[target['geometry']['core']],'none','#ff8179',.002)
            (out/(name+'.svg')).write_text(svg(bounds,content,name))
        diagnostic=f'<details><summary>Why reservation responses do not count as evolving-companion events</summary><p>Example: {target["key"]} responds to earlier round priority {neighbor["key"]}. Restoring only that priority to its ORG core changes the later land by {event["changed_area_mm2"]:.6f} mm² at the same radius. Those grown priority reservations also exist in the fair static comparator, so this is a reservation response, not evidence of evolving companion interaction.</p><div class="grid"><article><h2>With grown round priority</h2><img src="event_with_priority.svg" alt="Later land with earlier grown priority"></article><article><h2>Only that priority restored to ORG</h2><img src="event_restored_priority.svg" alt="Counterfactual later land with neighbor restored"></article></div></details>'
    options=''.join(f'<option value="{d["key"]}">{d["key"]} · {d["group_id"]} · {d["factor"]:.3f}× · {d["decision"].replace("_"," ").lower()}</option>' for d in sorted(decisions,key=lambda d:d['key']))
    default=next((d['key'] for d in decisions if d['active_earlier_neighbors']),next(d['key'] for d in decisions if d['source_id']==p['approved_pair'][0]))
    causal=r['t01_dynamic_adapted_later_sites'];criterion='met locally' if causal>=3 else 'not met'
    static_bad=a['static_comparator_violating_sites']
    matrix=[('Source coverage','51 sites / 53 source occurrences'),('Hard 1.5× ceiling','PASS on proposed radii and accepted contours'),('Local group balance',f'{len(r["groups"])} small groups; one factor per group'),('Round priorities',f'{r["priority_count"]} preserved; one per original physical component'),('Assembled source / gap checks','PASS · fresh-process full-source audit'),('Same-policy replay','Identical saved geometry hashes'),('Grown priority reservation responses',f'{r["reservation_response_later_sites"]} companions; reservations also exist in static comparator'),('Evolving companion adaptation',f'{causal} distinct later sites / target ≥3 — {criterion}'),('Static-neighbour comparison',f'{r["static_comparison"]["changed_sites"]} changed sites; {static_bad} static assembled violating sites'),('Owner decision','PENDING · pair approval was tentative')]
    if class_mode:
        matrix[2]=('Local size agreement','Shared physical diameter class per pair; clearance exceptions descend independently')
        matrix[3]=('Round priorities',f'{r["priority_count"]} round reservations; '+', '.join(p['square_guided_sites'])+' have owner-specific recess exceptions')
    desk='ChatGPT desk audit: NOT_RUN for this crop trial.'
    if (out/'chatgpt_desk_audit.json').exists():
        desk_audit=json.loads((out/'chatgpt_desk_audit.json').read_bytes());assert desk_audit['report_sha256']==sha(out/'report.json');desk='<a href="chatgpt_desk_audit.json">ChatGPT summary-only crop audit recorded</a>.'
    history=ROOT/'out/crop_dynamic_tasks/t01/t01_full_crop.svg'
    if history.exists():shutil.copy2(history,out/'historical_t01.svg')
    page='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>T01 crop · bounded copper growth</title><style>
body{font:16px/1.5 system-ui;background:#eaf0f5;color:#152b40;margin:0}main{max-width:1500px;margin:auto;padding:24px}h1{font-size:29px;margin-bottom:6px}h2{font-size:21px}.notice{background:#fff0cc;padding:14px;border-left:5px solid #d99a15}.stats{display:flex;gap:12px;flex-wrap:wrap;margin:18px 0}.stats div{background:white;padding:12px 18px;border-radius:8px}.stats strong{display:block;font-size:25px}.grid{display:grid;grid-template-columns:1fr 1fr;gap:18px}article{background:white;padding:16px;border-radius:12px;border:1px solid #d0dae3}img{width:100%;background:#111923;border-radius:8px}button,select{padding:9px;border:1px solid #aabac7;border-radius:5px;background:white;color:#152b40;max-width:100%}.controls{display:flex;gap:8px;flex-wrap:wrap;margin:12px 0}table{border-collapse:collapse;background:white;width:100%}td,th{padding:10px;border-bottom:1px solid #d8e0e5;text-align:left}details{background:white;padding:16px;margin:18px 0}a{color:#086f80}code{overflow-wrap:anywhere}#site-info{background:white;padding:14px;border-radius:8px}@media(max-width:800px){main{padding:12px}.grid{grid-template-columns:1fr}h1{font-size:25px}}</style><main><h1>T01 crop: balanced, capped circle growth</h1><p>Recorded execution (REPLAY) · same frozen crop and ORG source · no native board writes.</p>'''
    page+=f'<p class="notice"><strong>{'T01 remains PARTIAL'}</strong><br>Geometry passes; crop approval remains yours. The hard 1.5× ceiling holds. Evolving-companion effects: {causal} / target ≥3. The {r['reservation_response_later_sites']} round-reservation responses are counted separately below.</p>'
    page+=f'<div class="stats"><div><strong>{r["grown_sites"]} / 51</strong>sites gained copper</div><div><strong>{r["unchanged_sites"]}</strong>sites kept unchanged</div><div><strong>{r["priority_count"]}</strong>round priorities</div><div><strong>{causal}</strong>later sites affected by companion updates</div></div>'
    page+='<div class="grid"><article><h2>Before · original ORG copper</h2><img src="crop_original.svg" alt="Full frozen T01 crop before processing"><p>Original circles, pads and traces at the fixed crop coordinates.</p></article><article><h2>After · balanced capped result</h2><img id="whole-result" src="crop_dynamic.svg" alt="Full frozen T01 crop after balanced capped processing"><div class="controls"><button onclick="mode(\'dynamic\')">Effective copper</button><button onclick="mode(\'overlay\')">Show additions</button><button onclick="mode(\'priorities\')">Round priorities</button><button onclick="mode(\'sites\')">Site IDs</button><button onclick="mode(\'static\')">Frozen-neighbour control</button></div><p id="whole-caption">Single-colour effective copper. All source cores and traces remain; only admitted land additions change.</p></article></div>'
    if class_mode:
        page+=diameter_review(r,p,out,a)
        if p.get('round_promotion'):
            stops=[row for row in coverage if row['next_class_diameter_mm'] is None]
            page+=f'<p><strong>Round-priority coverage: {len(coverage)} = {len(a["round_next_class_controls"])} tested next-size rejections + {len(stops)} local-target stop.</strong> '+''.join(f'{row["key"]} is already at its shared local target Ø {row["allocated_diameter_mm"]:.4f} mm; its individual ceiling is Ø {row["individual_cap_diameter_mm"]:.5f} mm. ' for row in stops)+'This does not claim a global optimum or growth to every individual cap. <a href="round_priority_coverage.json">Inspect all priority dispositions</a>.</p>'
    page+='<h2>Review one site</h2><p>Choose any of the 51 source-bound sites. Blue is its proposed circular envelope; gold is its derived square; red is the original core. The final contour may be clipped by local source or accepted copper.</p><select id="site" onchange="showSite(this.value)">'+options+'</select><p id="site-info"></p><div class="grid"><article><h2>Site · original</h2><img id="site-original" alt="Selected site original copper"></article><article><h2>Site · accepted scene</h2><img id="site-final" alt="Selected site accepted copper and construction"></article></div>'
    page+='<h2>Where this stands against T01</h2><table><tbody>'+''.join(f'<tr><th>{html.escape(k)}</th><td>{html.escape(v)}</td></tr>' for k,v in matrix)+'</tbody></table>'
    page+=diagnostic
    page+=f'<p>The balance groups are small disjoint neighbouring pairs plus singletons, not a transitive chain across the whole crop. Original physical components are tracked separately for round-priority ownership. The reviewed pair is retained; crop-wide component reservations add constraints beyond that two-site illustration.</p><p>Measured effective added copper: {r["effective_added_union_mm2"]:.6f} mm². Complete edge-circle additions outside the display frame: {r["outside_viewport_added_area_mm2"]:.6f} mm². <a href="crop_outside.svg">Inspect outside-frame scope</a>.</p>'
    page+=f'<details><summary>Evidence, limitations and historical comparison</summary><p>{desk}</p><p>Fresh same-author verification reopens all 17,849 original F.Cu records. Every grown candidate and counterfactual is checked against the full source; unchanged source sites have no new-copper gap test. It shares the native parser and geometry kernel. Source-derived trace-port exceptions are bounded and checked; physical contact is not a recovered electrical net.</p><p><a href="report.json">Execution receipt / every site and event</a> · <a href="fresh_audit.json">Fresh audit</a> · <a href="selection.json">Frozen groups and priorities</a> · <a href="policy.json">Predeclared policy</a> · <a href="SHA256SUMS">Checksums</a> · <a href="historical_t01.svg">Historical T01, different policy</a></p><p>No EDIT contours or calibration enter construction. Tentative visual approval does not establish full T01 acceptance, expert equivalence, native export, electrical or manufacturing qualification. Frozen T01/R1 evidence is preserved. No T02+ processing is run.</p></details>'
    if class_mode:
        page=page.replace('balanced, capped circle growth','shared diameter classes').replace('After · balanced capped result','After · shared diameter classes')
        page=page.replace('round priorities</div>', f'round reservations + {len(p["square_guided_sites"])} recess exceptions</div>')
        page=page.replace('The balance groups are small disjoint neighbouring pairs plus singletons, not a transitive chain across the whole crop.', 'The size groups are small neighbouring pairs and singletons; common diameter is a preference, with explicit clearance exceptions.')
        page=page.replace('Original physical components are tracked separately for round-priority ownership.', 'Original components are tracked separately; owner-specific recess exceptions: '+', '.join(p['square_guided_sites'])+'.')
        page=page.replace('The reviewed pair is retained; crop-wide component reservations add constraints beyond that two-site illustration.', 'This is a new experimental sizing policy, not a fitted EDIT rule.')
        page=page.replace('<button onclick="mode(\'sites\')">Site IDs</button>', '<button onclick="mode(\'classes\')">Size classes</button><button onclick="mode(\'previous\')">Previous result</button><button onclick="mode(\'sites\')">Site IDs</button>')
    js=json.dumps(site_ui).replace('<','\\u003c')
    page+='<script>const sites='+js+';function mode(name){document.getElementById("whole-result").src="crop_"+name+".svg";document.getElementById("whole-caption").textContent={classes:"Envelope classes by colour; grey means exact source KEEP. A clipped land is not a circle of that diameter.",previous:"Previous continuous-factor result, same source and crop frame; different sizing policy.",dynamic:"Single-colour effective copper.",sites:"Site IDs correspond to the 51-site selector below.",overlay:"Grey: original copper. Green: actual added union, excluding overlap already occupied by original traces.",priorities:"Gold: designated round priorities. Green: companions. Grey: other source copper.",static:"Same policy and grown priority reservations, but companion neighbours frozen at ORG. This diagnostic can have assembled violations; see the audit."}[name]}function showSite(key){let s=sites[key];document.getElementById("site-original").src="focus/"+key+"_original.svg";document.getElementById("site-final").src="focus/"+key+"_final.svg";document.getElementById("site-info").textContent=key+(s.class_mm ? " · class Ø "+s.class_mm.toFixed(4)+" mm" : "")+(s.square_guided ? " · square-guided recess exception" : "")+" · "+s.group_id+" · "+s.decision+" · factor "+s.factor.toFixed(6)+"× · radius "+s.source_radius_mm.toFixed(6)+" → "+s.proposed_radius_mm.toFixed(6)+" mm · added "+s.added_area_mm2.toFixed(6)+" mm² · "+s.events+" verified earlier-neighbour effects"}document.getElementById("site").value="'+default+'";showSite("'+default+'");</script></main></html>'
    annotation_source=ROOT/'src/review_image_annotations.js'
    shutil.copy2(annotation_source,out/'review_image_annotations.js')
    page=page.replace('</main></html>',f'<script src="review_image_annotations.js" data-report="{sha(out/"report.json")}"></script></main></html>')
    pending=out/'.index.html.next';pending.write_text(page);pending.replace(out/'index.html')
    views={str(path.relative_to(out)):sha(path) for path in out.rglob('*.svg')}
    dump(out/'publication_receipt.json',{'report_sha256':sha(out/'report.json'),'audit_sha256':sha(out/'fresh_audit.json'),'selection_sha256':sha(out/'selection.json'),'renderer_sha256':sha(Path(__file__)),'annotation_script_sha256':sha(annotation_source),'index_sha256':sha(out/'index.html'),'svg_sha256':views,'owner_review':'PENDING','presentation':'Read-only REPLAY; controls do not execute editing.'})
    if p.get('round_promotion'):
        receipt=json.loads((out/'publication_receipt.json').read_bytes());receipt['round_priority_coverage_sha256']=sha(out/'round_priority_coverage.json');dump(out/'publication_receipt.json',receipt)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('bundle',type=Path);publish(parser.parse_args().bundle.resolve())
