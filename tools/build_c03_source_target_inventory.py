#!/usr/bin/env python3
"""Read-only C03 source candidates. Never inherits C02 land acceptance."""
from pathlib import Path
import sys,json,hashlib,subprocess
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from shapely import STRtree,from_wkb
from shapely.geometry import box
from shapely.ops import unary_union
from src.crop_circle_sources import verify_assets
from tools.render_c03_source_frame import render_source_frame as render


def main(pre,baseline,out):
    if out.exists():raise ValueError('FRESH_OUTPUT_REQUIRED')
    integrity=verify_assets();b=json.loads(baseline.read_text());source=(pre/'inputs/ORG_source.kicad_pcb').read_bytes()
    if hashlib.sha256(source).hexdigest()!=b['org_source_sha256']:raise ValueError('SOURCE_BOARD_BINDING_MISMATCH')
    meta=json.loads((pre/'inputs/source_manifest.json').read_text())['objects'];ids=[];geoms=[];rows={}
    for row in meta:
        sid=row['id'];blob=(pre/f'inputs/source_wkb/{row["geometry_sha256"]}.wkb').read_bytes()
        if hashlib.sha256(blob).hexdigest()!=row['geometry_sha256']:raise ValueError('SOURCE_GEOMETRY_HASH_MISMATCH')
        ids.append(sid);geoms.append(from_wkb(blob));rows[sid]=row
    tree=STRtree(geoms);bounds=b['native_crop_bounds_mm'];crop=box(*bounds);local=sorted(int(i) for i in tree.query(crop,predicate='intersects'))
    copper=unary_union([geoms[i] for i in local]).intersection(crop);candidates=[];cores={}
    for i in local:
        sid=ids[i];row=rows[sid];core=geoms[i]
        if row['kind']=='gr_circle':shape='CIRCLE_SOURCE'
        elif row['kind']=='gr_poly' and core.equals(box(*core.bounds)):shape='AXIS_ALIGNED_RECTANGLE_SOURCE'
        else:continue
        others=[geoms[int(j)] for j in tree.query(core,predicate='intersects') if int(j)!=i and not (rows[ids[int(j)]]['kind']==row['kind'] and geoms[int(j)].equals(core))]
        covered=unary_union(others).covers(core);key=('C' if shape.startswith('CIRCLE') else 'R')+f'{len(candidates)+1:03d}'
        candidates.append(dict(key=key,source_id=sid,source_shape=shape,selected=not covered,fully_covered=covered,reason='SKIP_FULLY_COVERED_SOURCE_SHAPE' if covered else 'EXPOSED_SOURCE_CANDIDATE_NOT_GROWTH_AUTHORITY',source_geometry_sha256=row['geometry_sha256'],bounds_mm=list(core.bounds)))
        cores[sid]=core
    out.mkdir();(out/'source_union.wkb').write_bytes(copper.wkb)
    result=dict(status='READ_ONLY_C03_SOURCE_TARGET_INVENTORY_NO_GROWTH',source_sha256=b['org_source_sha256'],asset_integrity=integrity,viewport_mm=bounds,source_objects_in_crop=len(local),original_baseline_source_objects=b['source_member_count'],registration_status=b['c3_screenshot_location_status'],screenshot_iou=b['c3_screenshot_to_org_iou'],required_iou=b['predeclared_min_iou'],accepted_T01_T02='NONE_INHERITED_FROM_C02',candidate_count=len(candidates),exposed_candidates=sum(r['selected'] for r in candidates),covered_skipped=sum(not r['selected'] for r in candidates),candidates=candidates,limitations='Exact source objects and source-derived viewport only. Provisional screenshot localization; no EDIT target geometry, land construction or electrical connectivity claim.')
    (out/'SOURCE_TARGETS.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    for name,field,marked in [('full_source',bounds,False),('full_candidates',bounds,True),('neighborhood_candidates',b['closeup_bounds_mm'],True)]:
        svg=out/f'{name}.svg'
        render(svg,'C03 / source candidates only / '+name,copper,copper.difference(copper),field,candidates if marked else [],cores,[
            f'{len(local)} source objects; {result["exposed_candidates"]} exposed circle/rectangle candidates; {result["covered_skipped"]} fully covered shapes skipped.',
            'Gold = exact exposed source contour; gray = covered source contour. No copper growth performed.',
            'C03 has no accepted T01/T02 scene. C02 acceptance and transformations are not inherited.',
            f'Screenshot localization remains provisional: IoU {result["screenshot_iou"]:.6f} < {result["required_iou"]:.6f}.',
            'Candidate identity inventory only. Other gr_poly shapes remain source context; no trace-width selection or electrical claim.'])
        subprocess.run(['sips','-s','format','png',str(svg),'--out',str(svg.with_suffix('.png'))],check=True,capture_output=True)
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>C03 source targets</title><style>body{font:18px system-ui;margin:24px}img{max-width:100%}</style><h1>C03 source geometry and candidate inventory</h1><p>Read-only source preparation. Provisional screenshot localization. No C02 land acceptance inherited.</p><h2>Combined source copper</h2><img src="full_source.png"><h2>Exact candidate contours</h2><img src="full_candidates.png"><h2>Located source neighborhood</h2><img src="neighborhood_candidates.png"><p><a href="SOURCE_TARGETS.json">Source identities and exclusions</a></p>')
    print(json.dumps({k:result[k] for k in ('status','source_objects_in_crop','candidate_count','exposed_candidates','covered_skipped')}))

if __name__=='__main__':main(*map(Path,sys.argv[1:]))
