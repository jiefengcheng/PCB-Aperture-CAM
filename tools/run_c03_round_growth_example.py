#!/usr/bin/env python3
"""First C03 source-grounded round-growth proposal; no accepted scene inherited."""
from pathlib import Path
import sys,json,hashlib,subprocess,math
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from shapely import from_wkb,STRtree,to_wkb
from shapely.geometry import box,Point
from shapely.ops import unary_union
from sexpdata import loads
from src.native_reference import one
from src.crop_circle_sources import verify_assets
from src.crop_stage_growth import GrowthScene,GrowthContract,fit_round_circle,check_proposal
from tools.render_c03_source_frame import render_source_frame as render


def main(pre,baseline,inventory,out):
    if out.exists():raise ValueError('FRESH_OUTPUT_REQUIRED')
    integrity=verify_assets();b=json.loads(baseline.read_text());source=(pre/'inputs/ORG_source.kicad_pcb').read_bytes();sha=hashlib.sha256(source).hexdigest()
    if sha!=b['org_source_sha256']:raise ValueError('SOURCE_BOARD_BINDING_MISMATCH')
    sid=b['c03_source_object']['source_id'];target=next(r for r in json.loads(inventory.read_text())['candidates'] if r['source_id']==sid)
    if target['fully_covered']:raise ValueError('COVERED_CIRCLE_INELIGIBLE')
    rows=json.loads((pre/'inputs/source_manifest.json').read_text())['objects'];objects=[];meta={r['id']:r for r in rows}
    for row in rows:
        blob=(pre/f'inputs/source_wkb/{row["geometry_sha256"]}.wkb').read_bytes()
        if hashlib.sha256(blob).hexdigest()!=row['geometry_sha256']:raise ValueError('SOURCE_GEOMETRY_HASH_MISMATCH')
        objects.append(dict(source_id=row['id'],geometry=from_wkb(blob),trace_width_mm=row['trace_width_mm']))
    scene=GrowthScene(objects);core=scene.objects[sid]['geometry'];node=loads(source[slice(*meta[sid]['source_span'])].decode());center=[float(x) for x in one(node,'center')];end=[float(x) for x in one(node,'end')];radius=math.dist(center,end)
    if str(one(node,'fill')[0]) not in ('yes','solid') or float(one(one(node,'stroke'),'width')[0])!=0:raise ValueError('SUPPORTED_FILLED_ZERO_STROKE_CIRCLE_REQUIRED')
    aliases=[r['source_id'] for r in objects if meta[r['source_id']]['kind']=='gr_circle' and r['geometry'].equals(core)]
    crop=box(*b['native_crop_bounds_mm']);cap=Point(*center).buffer(radius*1.5,quad_segs=128);neighbors=scene.neighbors(sid,cap,aliases)
    cap_check=check_proposal(core,cap,neighbors,crop=crop,cap=cap)
    candidate,fitted,check=fit_round_circle(core,center,radius,radius*1.5,neighbors,crop)
    if not check['passed'] or not candidate.covers(core):raise ValueError('ROUND_PROPOSAL_REJECTED')
    positive=candidate.difference(core).area>1e-12
    if positive and not candidate.equals(Point(*center).buffer(fitted,quad_segs=128)):raise ValueError('ROUND_SHAPE_NOT_RETAINED')
    all_geoms=[r['geometry'] for r in objects];tree=STRtree(all_geoms);local=sorted(int(i) for i in tree.query(crop,predicate='intersects'));before=unary_union([all_geoms[i] for i in local]).intersection(crop)
    after=unary_union([candidate if objects[i]['source_id'] in aliases else all_geoms[i] for i in local]).intersection(crop);added=after.difference(before)
    if before.difference(after).area>1e-12:raise ValueError('SOURCE_COPPER_REMOVED')
    out.mkdir()
    for name,geometry in [('source_core',core),('candidate',candidate),('before',before),('after',after),('added',added)]:(out/f'{name}.wkb').write_bytes(to_wkb(geometry))
    result=dict(status='C03_SINGLE_ROUND_GROWTH_PROPOSAL_LOCAL_PASS_NOT_FROZEN' if positive else 'C03_SINGLE_ROUND_TARGET_KEEP_NO_POSITIVE_GROWTH',source_sha256=sha,source_id=sid,aliases=aliases,source_geometry_sha256=meta[sid]['geometry_sha256'],native_center_mm=center,original_radius_mm=radius,proposed_radius_mm=fitted,radius_factor=fitted/radius,hard_ceiling=1.5,round_shape_retained=True,source_core_retained=True,source_neighbor_count=len(neighbors),positive_growth=positive,added_crop_copper_mm2=added.area,removed_crop_area_mm2=before.difference(after).area,viewport_mm=b['native_crop_bounds_mm'],closeup_bounds_mm=b['closeup_bounds_mm'],asset_integrity=integrity,registration_status=b['c3_screenshot_location_status'],T02='NOT_RUN',T03='NOT_RUN',T04='NOT_RUN',accepted_cumulative_land_baseline='NOT_ESTABLISHED',scope='One previously identified source circle only; no claim of complete focused C03 coverage or C02 lineage inheritance',decision_authority='Standing in-lane development authorization; proposed geometry only, not owner acceptance')
    for name,data in [('RESULT.json',result),('FINAL_CHECK.json',check),('CAP_REJECTION_OR_CHECK.json',cap_check)]: (out/name).write_text(json.dumps(data,indent=2,sort_keys=True)+'\n')
    for scale_name,bounds in [('full',b['native_crop_bounds_mm']),('closeup',b['closeup_bounds_mm'])]:
        for stage,copper in [('before',before),('after',after)]:
            svg=out/f'{scale_name}_{stage}.svg'
            render(svg,f'C03 / round growth example / {scale_name} {stage}',copper,added if stage=='after' else added.difference(added),bounds,[],{},[
                f'Source circle at ({center[0]}, {center[1]}); radius factor {fitted/radius:.9f}, ceiling1.5; round shape retained.',
                'Red = actual cumulative copper; teal = exact added copper. Every source core and original contact retained.',
                f'{len(neighbors)} source-bound neighboring operands checked;20um hard minimum,20.1um construction guard, original attachment ports only.',
                'One-circle proposal only. No accepted C03 land baseline or completed target coverage; no C02 transformations inherited.',
                f'Screenshot registration remains provisional (IoU{b["c3_screenshot_to_org_iou"]:.6f}); no EDIT-derived target geometry.'])
            subprocess.run(['sips','-s','format','png',str(svg),'--out',str(svg.with_suffix('.png'))],check=True,capture_output=True)
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>C03 round growth example</title><style>body{font:18px system-ui;margin:24px}img{max-width:100%}</style><h1>C03: one source-grounded round-growth proposal</h1><p>Not a frozen or complete C03 stage. Original source and proposed cumulative copper at identical coordinates.</p><h2>Located neighborhood before</h2><img src="closeup_before.png"><h2>Located neighborhood after</h2><img src="closeup_after.png"><h2>Full source crop before</h2><img src="full_before.png"><h2>Full source crop after</h2><img src="full_after.png"><p><a href="RESULT.json">Source binding and scope</a> · <a href="FINAL_CHECK.json">Actual pair checks</a></p>')
    print(json.dumps(result))

if __name__=='__main__':main(*map(Path,sys.argv[1:]))
