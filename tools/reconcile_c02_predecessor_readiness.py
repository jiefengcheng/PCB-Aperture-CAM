#!/usr/bin/env python3
"""Source-bound cumulative land-stage reconciliation, never self-acceptance."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import hashlib,json,subprocess
from shapely import STRtree,from_wkb,to_wkb
from shapely.geometry import box
from shapely.ops import unary_union
from src.crop_circle_sources import verify_assets
from tools.run_c02_four_attachment_diagnostic_v2 import compute,SITES
from tools.run_c02_growth_coverage import render


def sha(data):return hashlib.sha256(data).hexdigest()


def main():
    no_render='--no-render' in sys.argv
    if no_render:sys.argv.remove('--no-render')
    pre,proposed,out=map(Path,sys.argv[1:]);assert not out.exists()
    integrity=verify_assets();assert integrity['status']=='PASS'
    report,g=compute(pre);scene=g['scene']
    coverage=json.loads((pre/'coverage.json').read_text())
    manifest=json.loads((pre/'inputs/source_manifest.json').read_text())
    rows={r['id']:r for r in manifest['objects']}
    selected=[r for r in coverage if r['selected']];context=[r for r in coverage if not r['selected']]
    assert len(selected)==74 and len(context)==6 and len(scene.replacements)==75
    current={sid:scene.replacements.get(sid,r['geometry']) for sid,r in scene.objects.items()}
    ids=sorted(current);tree=STRtree([current[sid] for sid in ids])
    rectangles=[]
    for row in selected:
        sid=row['source_id'];original=scene.objects[sid]['geometry'];candidate=current[sid]
        assert candidate.equals(box(*candidate.bounds)),row['key']
        assert candidate.covers(original),row['key']
        x0,y0,x1,y1=original.bounds;u0,v0,u1,v1=candidate.bounds
        factors=[(u1-u0)/(x1-x0),(v1-v0)/(y1-y0)]
        assert all(1-1e-12<=f<=1.25+1e-12 for f in factors),row['key']
        nearby=[current[ids[int(i)]] for i in tree.query(candidate.envelope) if ids[int(i)]!=sid]
        visible_added=candidate.difference(unary_union([original,*nearby]))
        assert visible_added.area>1e-10,(row['key'],'NO_INDEPENDENT_EXPOSED_GROWTH')
        rectangles.append(dict(key=row['key'],source_id=sid,original_sha256=rows[sid]['geometry_sha256'],
            candidate_sha256=sha(to_wkb(candidate)),axis_factors_xy=factors,
            core_removed_mm2=original.difference(candidate).area,
            exposed_growth_in_final_scene_mm2=visible_added.area,
            geometry_status='LOCAL_PASS_PENDING_BATCH_AUDIT' if row['key'] in SITES else 'PREVIOUSLY_ACCEPTED_WITNESS'))
    for row in context:
        sid=row['source_id'];assert sid not in scene.replacements
        assert sha(to_wkb(current[sid]))==rows[sid]['geometry_sha256']
    untouched=[];trace_count=0
    for sid,r in sorted(scene.objects.items()):
        if sid in scene.replacements:continue
        assert sha(to_wkb(current[sid]))==rows[sid]['geometry_sha256']
        untouched.append(sid)
        if r['trace_width_mm']>0:trace_count+=1
    circle=json.loads((pre/'t01/decision.json').read_text())
    assert to_wkb(current[circle['source_id']])==(pre/'t01/candidate.wkb').read_bytes()
    for name in ('before','after','exposed'):
        assert to_wkb(g[name])==(proposed/f'geometry/{name}.wkb').read_bytes()
    bounds=g['base']['bounds'];crop=box(*bounds)
    reconstructed=unary_union([current[ids[int(i)]] for i in tree.query(crop,predicate='intersects')]).intersection(crop)
    union_difference=reconstructed.symmetric_difference(g['after']).area
    assert union_difference<=1e-12,union_difference
    out.mkdir(parents=True);(out/'visuals').mkdir()
    record=dict(schema='c02-cumulative-predecessor-readiness/1',source_sha256=manifest['source_sha256'],
        source_manifest_sha256=sha((pre/'inputs/source_manifest.json').read_bytes()),asset_integrity=integrity,
        viewport_mm=bounds,source_objects=len(scene.objects),unchanged_source_objects=len(untouched),
        unchanged_original_trace_primitives=trace_count,selected_rectangles=len(selected),context_rectangles=len(context),
        positive_exposed_rectangle_witnesses=len(rectangles),all_final_replacement_checks=len(g['final']),
        t01_candidate_wkb_exact=True,t01_candidate_sha256=sha((pre/'t01/candidate.wkb').read_bytes()),
        saved_proposed_wkb_exact=3,cumulative_sha256=sha(to_wkb(g['after'])),
        rebuilt_source_union_symmetric_difference_mm2=union_difference,
        union_diagnostic_area_limit_mm2=1e-12,union_diagnostic_not_byte_identity=True,
        accepted_witnesses=70,pending_audit_targets=list(SITES),rectangles=rectangles,
        T02='NOT_FROZEN_PENDING_BATCH_AUDIT',T03='DEFERRED',T04='SOURCE_WIDTH_GROWTH_NOT_RUN',
        construction='NONE; read-only reconstruction of saved proposed land geometry',
        engineering_scope='Geometric growth obligations only; not electrical or manufacturing acceptance')
    (out/'READINESS.json').write_text(json.dumps(record,indent=2,sort_keys=True)+'\n')
    (out/'ALL_75_FINAL_CHECKS.json').write_text(json.dumps(g['final'],indent=2,sort_keys=True)+'\n')
    (out/'UNCHANGED_SOURCE_IDS.json').write_text(json.dumps(untouched,indent=2)+'\n')
    (out/'SOURCE_BINDINGS.json').write_text(json.dumps(g['source_binding_evidence'],indent=2,sort_keys=True)+'\n')
    if no_render:
        print(json.dumps({k:v for k,v in record.items() if k!='rectangles'}))
        return
    cores={r['source_id']:scene.objects[r['source_id']]['geometry'] for r in coverage}
    render(out/'visuals/readiness.svg','C02 cumulative T01 + T02 / source-bound freeze-readiness',g['after'],
        g['after'].difference(from_wkb((pre/'t01/cumulative.wkb').read_bytes())),bounds,coverage,cores,
        ['Actual saved cumulative land scene; original source hash 850c4c74d55717a7. No new construction.',
         '74 selected rectangles have positive exposed growth in the final scene; six context rectangles unchanged.',
         f'{trace_count} original trace primitives unchanged; T01 candidate exact; all 75 cumulative checks pass locally.',
         'Red = cumulative copper union; teal = T02 added copper; gold = exact source rectangle locations.',
         '70 accepted witnesses + R003/R005/R006/R012 locally passing proposals pending batched audit.',
         'NOT FROZEN. No source trace width growth, route change, native export or electrical acceptance.'])
    subprocess.run(['sips','-s','format','png',str(out/'visuals/readiness.svg'),'--out',str(out/'visuals/readiness.png')],check=True,capture_output=True)
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>C02 predecessor readiness</title><style>body{font:18px system-ui;max-width:1400px;margin:24px auto;color:#142a3f}img{width:100%}</style><h1>C02 cumulative predecessor readiness — pending audit</h1><img src="visuals/readiness.png"><p><a href="READINESS.json">Source identities, final-scene exposed growth, exact hashes and scope</a> · <a href="ALL_75_FINAL_CHECKS.json">All 75 cumulative geometric checks</a></p>')
    print(json.dumps({k:v for k,v in record.items() if k not in ('rectangles',)}))


if __name__=='__main__':main()
