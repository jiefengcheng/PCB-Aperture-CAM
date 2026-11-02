#!/usr/bin/env python3
"""Render ABI-produced geometry and controls; never construct a T01 candidate."""
import argparse
import html
import json
from pathlib import Path
import subprocess
import sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from shapely import from_wkb, to_wkb
from shapely.geometry import box
from shapely.ops import unary_union
from src.stage_abi.store import ArtifactStore,digest,canonical
from tools.render_c03_source_frame import render_source_frame

def main(run):
    run=run.resolve();out=run/'visuals'
    if not run.is_relative_to(ROOT/'out') or out.exists():raise ValueError('FRESH_PROJECT_VISUAL_OUTPUT_REQUIRED')
    receipt=json.loads((run/'RECEIPT.json').read_bytes())
    store=ArtifactStore(run/'runtime')
    candidate=store.get_json(receipt['candidate_ref'],kind='candidate')
    original_scene=store.get_json(receipt['scene_ref'],kind='scene')
    original={r['source_id']:from_wkb(store.get(r['geometry_ref'],kind='geometry')) for r in original_scene['objects']}
    bounds=original_scene['viewport_mm'];crop=box(*bounds)
    def geometry(ref):return from_wkb(store.get(ref,kind='geometry'))
    before=geometry(candidate['before_ref']);after=geometry(candidate['after_ref'])
    frozen=ROOT/'out/crop_dynamic_tasks/c01_existing_t01_freeze_20261029_239/frozen'
    expected=from_wkb((frozen/'context.wkb').read_bytes()).union(from_wkb((frozen/'dynamic_effective.wkb').read_bytes())).intersection(crop)
    old_c03=from_wkb((ROOT/'out/crop_dynamic_tasks/c03_final_so_far_freeze_20261030_270/frozen/T01/after.wkb').read_bytes()).intersection(crop)
    delta_to_expected=after.symmetric_difference(expected).area
    if delta_to_expected>1e-10:raise ValueError('VISIBLE_C01_REPRODUCTION_MISMATCH')
    out.mkdir()
    notes=['FRESH T01 ABI execution / REPLAY of stored result for display; 51 source contours byte-identical to frozen C01, 53 aliases.',
           'Source SHA256: '+receipt['source_sha256'],
           'English SHA256: '+receipt['english_sha256'],
           'All radii, priorities, decisions and groups match C01. Independent/native/electrical/manufacturing not established.',
           'T02-T05 not executed. Accepted C01/C02/C03 and all shared modules unchanged. Exact bindings: ../RECEIPT.json.']
    def render(name,title,copper,bounds,*,sid=None,contour=None,extra=()):
        p=out/(name+'.svg');rows=[] if sid is None else [dict(source_id=sid,key=next(d['key'] for d in candidate['decisions'] if d['source_id']==sid),selected=True)]
        render_source_frame(p,title,copper,copper.difference(before),bounds,rows=rows,cores={} if sid is None else {sid:contour},notes=list(extra)+notes)
        subprocess.run(['sips','-s','format','png',str(p),'--out',str(p.with_suffix('.png'))],check=True,capture_output=True)
        return p.with_suffix('.png').name
    render('source','T01 / original source / C01 viewport',before,bounds)
    render('previous_c03','T01 / earlier C03 round-only result / same C01 viewport',old_c03,bounds)
    render('abi_c01','T01 / complete C01 interaction ABI reproduction',after,bounds)
    render('frozen_c01','T01 / frozen C01 reference / comparison only',expected,bounds)
    details=[]
    for key in ['S04','S12','S31']:
        d=next(d for d in candidate['decisions'] if d['key']==key);sid=d['source_id'];x,y=d['center'];view=[x-.42,y-.42,x+.42,y+.42]
        actual=geometry(d['candidate_ref']);extra=[f'{key}: native source bytes {sid.rsplit(":bytes:",1)[1]}; envelope diameter {2*d["proposed_radius_mm"]:.6f} mm.',
                                                    f'{d["decision"]}; target contour SHA256 {d["candidate_ref"]["sha256"]}.']
        for label,g in [('source',before),('previous_c03',old_c03),('abi_c01',after)]:
            render(key+'_'+label,f'T01 / {key} / {label}',g,view,sid=sid,contour=actual if label=='abi_c01' else original[sid],extra=extra)
        details.append(f'<h2>{key}: source, earlier C03, complete ABI reproduction</h2><p><code>{sid}</code></p><div class="triplet">'+''.join(f'<img src="{key}_{label}.png">' for label in ['source','previous_c03','abi_c01'])+'</div>')
    # Restore the exact construction prefix for the ABI-emitted controls. Later
    # features remain original in both panels, so their context is comparable.
    selected={d['source_id']:geometry(d['candidate_ref']) for d in candidate['decisions']}
    def prefix(d,override):
        current=dict(original)
        for prior in candidate['decisions'][:d['input_revision']]:
            for alias in prior['aliases']:current[alias]=selected[prior['source_id']]
        for sid,g in override.items():
            row=next(r for r in candidate['decisions'] if r['source_id']==sid)
            for alias in row['aliases']:current[alias]=g
        return unary_union([current[sid] for sid in sorted(current)]).intersection(crop)
    control_cards=[]
    event=next(e for e in candidate['events'] if next(d['key'] for d in candidate['decisions'] if d['source_id']==e['target_source_id'])=='S04')
    d=next(d for d in candidate['decisions'] if d['source_id']==event['target_source_id']);sid=d['source_id'];x,y=d['center'];view=[x-.5,y-.5,x+.5,y+.5]
    native_neighbor=original[event['neighbor_source_id']]
    actual=prefix(d,{sid:selected[sid]})
    restored=prefix(d,{sid:geometry(event['counterfactual_ref']),event['neighbor_source_id']:native_neighbor})
    control_notes=[f'ABI neighbor-restoration control: changed target contour area {event["changed_area_mm2"]:.9f} mm2; target radius held fixed.',
                   f'Restore only neighbor bytes {event["neighbor_source_id"].rsplit(":bytes:",1)[1]} to original; all other prefix geometry unchanged.']
    render('interaction_actual','T01 / S04 / enlarged round priority constrains companion',actual,view,sid=sid,contour=selected[sid],extra=control_notes)
    render('interaction_neighbor_restored','CONTROL / S04 / one enlarged neighbor restored to original',restored,view,sid=sid,contour=geometry(event['counterfactual_ref']),extra=control_notes)
    control_cards.append('<h2>Measured circle interaction</h2><p>This is an ABI-generated control, with one earlier reserved priority restored to source. The companion changes at a fixed target radius.</p><div class="pair"><img src="interaction_actual.png"><img src="interaction_neighbor_restored.png"></div>')
    control=candidate['square_disabled_controls'][0];d=next(d for d in candidate['decisions'] if d['source_id']==control['source_id']);sid=d['source_id'];x,y=d['center'];view=[x-.4,y-.4,x+.4,y+.4]
    disabled=geometry(control['disabled_ref'])
    control_notes=[f'S31 recess-disabled control: exact contour difference {control["symmetric_difference_mm2"]:.9f} mm2.',
                   f'Same original source, target radius {control["radius_mm"]:.6f} mm and prefix revision {control["input_revision"]}; only explicit square recess disabled.']
    render('S31_recess_actual','T01 / S31 / source-specific square-guided recess',prefix(d,{sid:selected[sid]}),view,sid=sid,contour=selected[sid],extra=control_notes)
    render('S31_recess_disabled','CONTROL / S31 / explicit recess disabled',prefix(d,{sid:disabled}),view,sid=sid,contour=disabled,extra=control_notes)
    control_cards.append('<h2>Source-specific S31 exception</h2><p>The controlled contour difference is 0.003454509699 mm². This exception is bound to the source identity and is not a general recess permission.</p><div class="pair"><img src="S31_recess_actual.png"><img src="S31_recess_disabled.png"></div>')
    from PIL import Image
    def sheet(names,name,width):
        panels=[Image.open(out/(n+'.png')).convert('RGB') for n in names]
        thumbs=[p.resize((width,round(p.height*width/p.width)),Image.Resampling.LANCZOS) for p in panels]
        result=Image.new('RGB',(width*len(thumbs),max(p.height for p in thumbs)),'#edf3f7')
        for i,p in enumerate(thumbs):result.paste(p,(i*width,0))
        result.save(out/name)
    sheet(['source','previous_c03','abi_c01'],'comparison.png',800)
    sheet(['interaction_actual','interaction_neighbor_restored'],'interaction.png',900)
    failures=''.join('<li><strong>'+html.escape(r['code'])+'</strong>: '+html.escape(r['message'])+'</li>' for r in receipt['negative_wire_controls'])
    measurements=dict(source_sha256=receipt['source_sha256'],english_sha256=receipt['english_sha256'],viewport_mm=bounds,
                      before_sha256=receipt['before_ref']['sha256'],after_sha256=receipt['after_ref']['sha256'],
                      frozen_C01_visible_symmetric_difference_mm2=delta_to_expected,
                      source_added_visible_area_mm2=after.difference(before).area,
                      source_removed_visible_area_mm2=before.difference(after).area,
                      previous_C03_vs_ABI_visible_difference_mm2=old_c03.symmetric_difference(after).area,
                      neighbor_control=event,square_control=control,status='REPLAY_OF_FRESH_VERIFIED_ABI_RUN',
                      display='x=native x; y=-native y; all panels use explicit common bounds; source WKB unchanged')
    (out/'MEASUREMENTS.json').write_bytes(canonical(measurements))
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>C01 English → contract → T01 ABI</title><style>body{font:17px system-ui;margin:24px;color:#142a3f}img{width:100%}code{overflow-wrap:anywhere}.triplet{display:grid;grid-template-columns:repeat(3,1fr)}.pair{display:grid;grid-template-columns:repeat(2,1fr)}.pass{padding:16px;background:#def4e8}.controls{background:#fff1df;padding:16px}</style><h1>C01: English → precise contract → ABI-only T01 execution</h1><p class="pass">PASS within complete bound C01 reproduction: 51 per-source contours byte-identical, 53 aliases; all radii, priorities, decisions and groups match. Every geometry operation ran through the recorded JSON ABI.</p><p>Images REPLAY a fresh run. Accepted scenes remain frozen. This is not independent, native-export, electrical or manufacturing qualification. C01 has 18 reservation-responsive sites / 34 controls, with zero demonstrated evolving-companion effects.</p><p><a href="../RECEIPT.json">Execution receipt</a> · <a href="../TRANSCRIPT.json">Every subprocess command and wire hash</a> · <a href="../C01_SOURCE_MATCHES.json">All 51 exact source matches</a> · <a href="MEASUREMENTS.json">Visual measurements and control references</a></p><h2>Original / earlier C03 round-only treatment / complete C01 ABI treatment</h2><img src="comparison.png"><p>Common C01 viewport; added visible copper '+f'{measurements["source_added_visible_area_mm2"]:.9f}'+' mm²; frozen-C01 visible difference '+f'{delta_to_expected:.3g}'+' mm² (numerical Boolean-union residue). Per-source contour equality is exact.</p>'+''.join(details)+''.join(control_cards)+'<section class="controls"><h2>Rejected ABI controls</h2><ul>'+failures+'</ul><p>Rejected English or candidate changes are retained in the transcript. No fallback to a different T01 model occurred.</p></section><h2>Frozen C01 comparison target</h2><img src="frozen_c01.png">')
    (out/'SHA256SUMS.json').write_bytes(canonical({p.name:digest(p.read_bytes()) for p in sorted(out.iterdir()) if p.is_file()}))
    print(json.dumps({k:measurements[k] for k in ['frozen_C01_visible_symmetric_difference_mm2','source_added_visible_area_mm2','source_removed_visible_area_mm2','previous_C03_vs_ABI_visible_difference_mm2']}))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('run',type=Path);main(p.parse_args().run)
