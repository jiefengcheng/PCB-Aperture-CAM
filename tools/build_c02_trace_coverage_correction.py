#!/usr/bin/env python3
"""Show all trace source copper, including definitions omitted from width scope."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import hashlib,html,json,subprocess
from collections import Counter
from shapely import STRtree,to_wkb
from shapely.geometry import box
from shapely.ops import unary_union
from src.crop_circle_sources import verify_assets
from tools.run_c02_four_attachment_diagnostic_v2 import compute
from tools.run_c02_growth_coverage import render,svg_shape


def main():
    pre,inventory,qualification,out,registration=map(Path,sys.argv[1:]);assert not out.exists()
    verify_assets()
    binding=json.loads(registration.read_text())
    report,g=compute(pre);scene=g['scene'];bounds=g['base']['bounds'];crop=box(*bounds)
    inv=json.loads((inventory/'TRACE_ENDPOINT_INVENTORY.json').read_text())
    q=json.loads((qualification/'CHAIN_CONTACT_QUALIFICATION.json').read_text())
    labels={r['component_id']:r for r in q['chains']}
    components={sid:r for r in inv['components'] for sid in r['source_ids']}
    meta={r['id']:r for r in json.loads((pre/'inputs/source_manifest.json').read_text())['objects']}
    land=unary_union([scene.replacements.get(sid,r['geometry']) for sid,r in scene.objects.items() if meta[sid]['kind'] not in ('segment','arc')])
    ledger=[];previous=[];omitted=[];trace_by_id={}
    for sid,r in sorted(scene.objects.items()):
        if meta[sid]['kind'] not in ('segment','arc') or not r['geometry'].intersects(crop):continue
        c=components[sid];qualified=labels[c['component_id']]
        visible=r['geometry'].difference(land).intersection(crop)
        was_shown=qualified['status']=='SOURCE_CHAIN_GEOMETRICALLY_QUALIFIED_FOR_WIDTH_FEASIBILITY'
        (previous if was_shown else omitted).append(visible)
        trace_by_id[sid]=r['geometry']
        ledger.append(dict(source_id=sid,source_kind=meta[sid]['kind'],source_width_mm=meta[sid]['trace_width_mm'],
            source_wkb_sha256=meta[sid]['geometry_sha256'],endpoint_component=c['component_id'],
            old_qualification=qualified['status'],old_definition_reasons=qualified['unresolved_reasons'],
            old_teal_overlay_included=was_shown,visible_outside_fixed_lands_area_in_crop_mm2=visible.area,
            coverage_status='PREVIOUSLY_SHOWN_SUBSET' if was_shown else 'OMITTED_FROM_OLD_OVERLAY_NOW_SHOWN',
            growth_execution='NOT_RUN'))
    assert len(ledger)==inv['crop_seed_count']
    teal=unary_union(previous);amber=unary_union(omitted).difference(teal)
    out.mkdir(parents=True);(out/'visuals').mkdir()
    for name,geo in [('previous_subset',teal),('omitted_trace_copper',amber)]:
        (out/f'{name}.wkb').write_bytes(to_wkb(geo))
    # Viewport locators from the owner's screenshot are selection aids only.
    # Colored geometry and all identities are exact source-derived copper.
    regions=[('A_upper_left_vertical',(.09,0.,.125,.19)),('B_upper_long_trace',(.61,.135,.999,.17)),
        ('C_upper_comb_backbone',(.31,.26,.70,.36)),('D_upper_vertical_route',(.685,.19,.71,.35)),
        ('E_left_short_link',(.15,.265,.267,.31)),('F_left_vertical_link',(.19,.39,.222,.51)),
        ('G_left_middle_link',(.23,.31,.26,.43)),('H_lower_comb_backbone',(.255,.606,.53,.696)),
        ('I_lower_second_backbone',(.277,.695,.535,.786)),('J_bottom_parallel_routes',(.1,.875,.858,.974)),
        ('K_upper_right_routes',(.937,.196,.999,.247))]
    frames=[('full_crop',bounds)];region_records=[]
    x0,y0,x1,y1=bounds
    ref_x0,ref_y0,ref_x1,ref_y1=binding['reference_copper_viewport_px']
    owner_width,owner_height=binding['owner_image_size_px']
    scale=binding['reference_to_owner_scale'];dx,dy=binding['reference_to_owner_translation_px']
    def source_point(u,v):
        px=(u*owner_width-dx)/scale;py=(v*owner_height-dy)/scale
        return [x0+(px-ref_x0)/(ref_x1-ref_x0)*(x1-x0),y0+(py-ref_y0)/(ref_y1-ref_y0)*(y1-y0)]
    for name,(u0,v0,u1,v1) in regions:
        b=[*source_point(u0,v0),*source_point(u1,v1)]
        frame=box(*b);hits=[r for r in ledger if trace_by_id[r['source_id']].intersects(frame)]
        # Slight padding improves visual context without changing measurement operands.
        frames.append((name,[b[0]-.08,b[1]-.08,b[2]+.08,b[3]+.08]))
        region_records.append(dict(name=name,selection_scope='Owner screenshot region registered by source silhouettes; raster locator only, exact source geometry thereafter',
            viewport_mm=b,source_ids=[r['source_id'] for r in hits],
            formerly_omitted_source_ids=[r['source_id'] for r in hits if not r['old_teal_overlay_included']]))
    ids=sorted(scene.objects);geometries=[scene.replacements.get(sid,scene.objects[sid]['geometry']) for sid in ids];tree=STRtree(geometries)
    for name,b in frames:
        frame=box(*b);copper=unary_union([geometries[int(i)] for i in tree.query(frame,predicate='intersects')])
        path=out/f'visuals/{name}.svg'
        render(path,f'C02 trace coverage correction / {name.replace("_"," ")}',copper,teal,b,[],{},
            [f'All {len(ledger)} crop-intersecting native trace primitives accounted for; complete source IDs retained.',
             'TEAL = source copper in old qualified overlay. AMBER = visible trace copper omitted from that overlay.',
             'RED = fixed/current copper scene. Original circle/rectangle lands are preserved and remain red.',
             'Colors indicate existing source coverage, NOT width growth, route modification or qualification.',
             'Main omission: whole endpoint-component branch/mixed-width/contact filters were too restrictive.',
             'Source hash850c4c74d55717a7. Exact geometry-derived contours; screenshot regions are locating aids only.'])
        svg=path.read_text();svg=svg.replace('</svg><text x="40"',svg_shape(amber.intersection(frame),'#ffb448')+'</svg><text x="40"',1)
        path.write_text(svg)
        subprocess.run(['sips','-s','format','png',str(path),'--out',str(out/f'visuals/{name}.png')],check=True,capture_output=True)
    result=dict(schema='c02-complete-visible-trace-coverage-correction/1',source_sha256=report['source_sha256'],
        cumulative_land_scene_sha256=report['cumulative_sha256'],viewport_mm=bounds,owner_view_registration=binding,
        crop_trace_primitive_count=len(ledger),previously_shown_primitive_count=sum(r['old_teal_overlay_included'] for r in ledger),
        omitted_primitive_count=sum(not r['old_teal_overlay_included'] for r in ledger),
        omitted_visible_copper_area_mm2=amber.area,records=ledger,regions=region_records,
        source_width_growth='NOT_RUN',stage_acceptance='NONE',coverage='All crop-intersecting native segment/arc primitives, not yet all qualified complete routes',
        correction='Do not equate unresolved whole endpoint-component classification with exclusion of its visible trace copper')
    (out/'COVERAGE_CORRECTION.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    rows=''.join(f'<tr><td>{html.escape(r["source_id"].split(":bytes:")[1])}</td><td>{r["source_width_mm"]}</td><td>{r["old_qualification"]}</td><td>{html.escape(", ".join(r["old_definition_reasons"]))}</td></tr>' for r in ledger if not r['old_teal_overlay_included'])
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>C02 corrected trace coverage</title><style>body{font:18px system-ui;max-width:1500px;margin:24px auto;color:#142a3f}img{width:100%}td{padding:6px;border-bottom:1px solid #ddd}</style><h1>C02 complete trace coverage — omissions shown in amber</h1><p>Teal was the old subset. Amber is existing trace copper omitted from that overlay. No trace width has changed.</p><img src="visuals/full_crop.png">'+''.join(f'<h2>{name.replace("_"," ")}</h2><img src="visuals/{name}.png">' for name,_ in frames[1:])+'<p><a href="COVERAGE_CORRECTION.json">All exact source IDs, old exclusions and screenshot region bindings</a></p><table><tr><th>Source byte span</th><th>Original width mm</th><th>Old classification</th><th>Old exclusion reasons</th></tr>'+rows+'</table>')
    print(json.dumps({k:v for k,v in result.items() if k not in ('records','regions')}))


if __name__=='__main__':main()
