#!/usr/bin/env python3
"""Source-bound C03 land target scope using existing native eligibility helpers."""
from pathlib import Path
import sys,json,hashlib,math,subprocess
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from sexpdata import loads
from shapely import from_wkb,STRtree
from shapely.geometry import Point,box
from shapely.ops import unary_union
from src.crop_circle_sources import verify_assets
from src.crop_rect_t02 import rectangular_feature
from src.crop_diameter_selection import admissible_diameters
from src.crop_balanced_t01 import local_groups
from src.native_reference import one
from tools.render_c03_source_frame import render_source_frame as render


def main(pre,inventory,baseline,policy_path,out):
    if out.exists():raise ValueError('FRESH_OUTPUT_REQUIRED')
    integrity=verify_assets();inv=json.loads(inventory.read_text());base=json.loads(baseline.read_text());policy=json.loads(policy_path.read_text());source=(pre/'inputs/ORG_source.kicad_pcb').read_bytes()
    if hashlib.sha256(source).hexdigest()!=inv['source_sha256'] or inv['source_sha256']!=base['org_source_sha256']:raise ValueError('SOURCE_BINDING_MISMATCH')
    rows=json.loads((pre/'inputs/source_manifest.json').read_text())['objects'];meta={r['id']:r for r in rows};payloads={};geoms={}
    for row in rows:
        digest=row['geometry_sha256'];blob=payloads.get(digest)
        if blob is None:
            blob=(pre/f'inputs/source_wkb/{digest}.wkb').read_bytes()
            if hashlib.sha256(blob).hexdigest()!=digest:raise ValueError('SOURCE_GEOMETRY_HASH_MISMATCH')
            payloads[digest]=blob
        geoms[row['id']]=from_wkb(blob)
    bounds=base['native_crop_bounds_mm'];crop=box(*bounds);trace_ids=[r['id'] for r in rows if r['kind'] in ('segment','arc')];trace_geoms=[geoms[s] for s in trace_ids];trace_tree=STRtree(trace_geoms)
    palette=policy['diameter_classes_mm'];records=[];circles=[];rectangles=[];seen=set()
    for original in inv['candidates']:
        row=dict(original);sid=row['source_id'];core=geoms[sid];kind=row['source_shape'];digest=meta[sid]['geometry_sha256'];row['selected']=False
        if row['fully_covered']:row['scope_disposition']='SKIP_FULLY_COVERED'
        elif digest in seen:row['scope_disposition']='EXACT_GEOMETRY_ALIAS_ONE_TARGET'
        elif kind=='CIRCLE_SOURCE':
            node=loads(source[slice(*meta[sid]['source_span'])].decode());center=[float(v) for v in one(node,'center')];end=[float(v) for v in one(node,'end')];radius=math.dist(center,end);cap=Point(*center).buffer(1.5*radius,quad_segs=128)
            if str(one(node,'fill')[0]) not in ('yes','solid') or float(one(one(node,'stroke'),'width')[0])!=0:row['scope_disposition']='UNSUPPORTED_CIRCLE_NATIVE_FORM'
            elif not crop.covers(cap):row['scope_disposition']='CONTEXT_CAP_CROSSES_SOURCE_VIEWPORT'
            else:
                choices=admissible_diameters(radius,palette);traces=[trace_ids[int(i)] for i in trace_tree.query(cap.buffer(.0201),predicate='intersects')]
                row.update(center_mm=center,original_radius_mm=radius,admissible_diameters_mm=choices,nearby_trace_source_ids=sorted(traces))
                if not choices:row['scope_disposition']='UNRESOLVED_NO_ADMISSIBLE_EXISTING_DIAMETER_CLASS'
                elif not traces:row['scope_disposition']='CONTEXT_NO_TRACE_IN_CAP_NEIGHBORHOOD'
                else:
                    row.update(scope_disposition='T01_ROUND_CLASS_TARGET_PROPOSAL',selected=True);circles.append(dict(source_id=sid,center=center,radius=radius,core=core));seen.add(digest)
        else:
            feature=rectangular_feature(meta[sid],payloads,crop,max_axis_factor=1.25)
            if feature is None:row['scope_disposition']='CONTEXT_NOT_FULLY_SUPPORTED_NATIVE_RECTANGLE_WITH_1P25_CAP_IN_VIEWPORT'
            else:
                from shapely.affinity import scale
                cap=scale(core,1.25,1.25,origin=core.centroid);traces=[trace_ids[int(i)] for i in trace_tree.query(cap.buffer(.0201),predicate='intersects')]
                row.update(source_size_mm=feature['source_size_mm'],orientation_radians=feature['orientation_radians'],nearby_trace_source_ids=sorted(traces))
                if not traces:row['scope_disposition']='CONTEXT_NO_TRACE_IN_CAP_NEIGHBORHOOD'
                else:row.update(scope_disposition='T02_RECTANGLE_TARGET_PROPOSAL',selected=True);rectangles.append(sid);seen.add(digest)
        records.append(row)
    seed=policy['approved_pair']
    if not set(seed)<={r['source_id'] for r in circles}:raise ValueError('EXISTING_REVIEWED_PAIR_NOT_SUPPORTED_IN_C03')
    groups=local_groups(circles,seed,gap=.0201)
    byid={r['source_id']:r for r in records}
    for group in groups:
        choices=[set(byid[s]['admissible_diameters_mm']) for s in group['site_ids']];common=set.intersection(*choices);group['desired_shared_diameter_mm']=max(common) if common else None
        for sid in group['site_ids']:byid[sid]['desired_diameter_mm']=group['desired_shared_diameter_mm'] or max(byid[sid]['admissible_diameters_mm'])
    local=[geoms[r['id']] for r in rows if geoms[r['id']].intersects(crop)];copper=unary_union(local).intersection(crop)
    result=dict(status='C03_SUPPORTED_TARGET_SCOPE_PROPOSAL_NOT_COMPLETE_STAGE',source_sha256=inv['source_sha256'],asset_integrity=integrity,viewport_mm=bounds,source_inventory_sha256=hashlib.sha256(inventory.read_bytes()).hexdigest(),policy_reference_sha256=hashlib.sha256(policy_path.read_bytes()).hexdigest(),policy_reuse='Diameter palette and nearest competition-pair helper only; no old crop acceptance, square recess exception, net label, or old geometry inherited',round_policy='All selected C03 circles remain round; one complete source core retained; applicable finite-copper gap checks required before any stage acceptance',rectangle_ceiling=1.25,circle_ceiling=1.5,circle_targets=len(circles),rectangle_targets=len(rectangles),circle_groups=groups,records=records,unresolved_existing_class_count=sum(r['scope_disposition'].startswith('UNRESOLVED') for r in records),trace_scope='Actual source trace primitive in1.5circle or1.25rectangle cap neighborhood plus20.1um guard; membership only, not defect classification',accepted_C03_land_scene='NOT_ESTABLISHED',screenshot_registration=base['c3_screenshot_location_status'])
    out.mkdir();(out/'SUPPORTED_TARGETS.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    for name,field in [('full',bounds),('neighborhood',base['closeup_bounds_mm'])]:
        svg=out/f'{name}.svg';render(svg,f'C03 / supported land target scope / {name}',copper,copper.difference(copper),field,records,geoms,[
            f'{len(circles)} round circle targets; {len(rectangles)} rectangle targets; {result["unresolved_existing_class_count"]} unresolved existing-class ranges.',
            'Gold = exact supported source target; gray = skipped/context source. No additional copper growth in this inventory.',
            'Full cap must fit source viewport. Fully covered source shapes skipped. Native source classification, no aspect-ratio guess.',
            'Existing palette/group selection reused as a proposal; no earlier crop acceptance or non-round exception inherited.',
            'C03 screenshot localization remains provisional. Actual source identities and all exclusions in SUPPORTED_TARGETS.json.'])
        subprocess.run(['sips','-s','format','png',str(svg),'--out',str(svg.with_suffix('.png'))],check=True,capture_output=True)
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>C03 supported target scope</title><style>body{font:18px system-ui;margin:24px}img{max-width:100%}</style><h1>C03 supported land target scope proposal</h1><p>Source-supported targets and explicit exclusions. Not a completed T01/T02 stage.</p><img src="full.png"><img src="neighborhood.png"><a href="SUPPORTED_TARGETS.json">Source identities, palette/group targets and exclusions</a>')
    print(json.dumps({k:result[k] for k in ('status','circle_targets','rectangle_targets','unresolved_existing_class_count')}))

if __name__=='__main__':main(*map(Path,sys.argv[1:]))
