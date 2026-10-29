#!/usr/bin/env python3
"""Read-only correction of source path definitions and old coverage exclusions."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import json,hashlib,subprocess,html
from collections import Counter
from shapely import STRtree,to_wkb
from shapely.geometry import Point,box
from shapely.ops import unary_union
from src.uniform_source_paths import uniform_source_paths
from src.crop_circle_sources import verify_assets
from tools.run_c02_four_attachment_diagnostic_v2 import compute
from tools.run_c02_growth_coverage import render


def main(path_builder=None):
    pre,inventory,marked,out=map(Path,sys.argv[1:]);assert not out.exists()
    integrity=verify_assets();report,g=compute(pre);scene=g['scene'];crop=box(*g['base']['bounds'])
    inv=json.loads((inventory/'TRACE_ENDPOINT_INVENTORY.json').read_text())
    raw=g['base']['source'];assert hashlib.sha256(raw).hexdigest()==inv['source_sha256']
    rows={r['source_id']:r for c in inv['components'] for r in c['original_full_source_members']}
    seeds={sid for c in inv['components'] for sid in c['seed_ids']}
    assert len(rows)==inv['source_members_after_full_endpoint_expansion'] and len(seeds)==853
    for sid,r in rows.items():
        start,end=map(int,sid.rsplit(':',2)[-2:])
        assert hashlib.sha256(raw[start:end]).hexdigest()==r['source_fragment_sha256']
        assert hashlib.sha256(to_wkb(scene.objects[sid]['geometry'])).hexdigest()==r['source_wkb_sha256']
    paths=(uniform_source_paths(list(rows.values()),seeds) if path_builder is None else
           path_builder(list(rows.values()),seeds,raw))
    meta={r['id']:r for r in json.loads((pre/'inputs/source_manifest.json').read_text())['objects']}
    ids=sorted(scene.objects);geos=[scene.replacements.get(sid,scene.objects[sid]['geometry']) for sid in ids];tree=STRtree(geos)
    cores={};old_component={sid:c['component_id'] for c in inv['components'] for sid in c['source_ids']}
    statuses=[]
    for r in paths:
        members=set(r['source_ids']);core=unary_union([scene.objects[sid]['geometry'] for sid in r['source_ids']]);cores[r['path_id']]=core
        contacts=[ids[int(i)] for i in tree.query(core,predicate='intersects') if ids[int(i)] not in members]
        other=unary_union([scene.replacements.get(sid,scene.objects[sid]['geometry']) for sid in contacts])
        independently_exposed=core.difference(other)
        for port in r.get('original_junction_ports',r['original_width_transition_ports']):
            point=Point(*map(float,port['point_decimal_mm']))
            neighbor_ids=port.get('neighboring_source_ids',port.get('other_width_source_ids',[]))
            port['original_contact_checks']=[dict(source_id=sid,source_contact_observed=core.intersects(scene.objects[sid]['geometry'])) for sid in neighbor_ids]
            assert all(v['source_contact_observed'] for v in port['original_contact_checks'])
            port['original_land_covering_port']=[sid for sid in contacts if meta[sid]['kind'] not in ('segment','arc') and scene.objects[sid]['geometry'].covers(point)]
            port['current_land_covering_port']=[sid for sid in contacts if meta[sid]['kind'] not in ('segment','arc') and scene.replacements.get(sid,scene.objects[sid]['geometry']).covers(point)]
            port['growth_obligation']='Preserve original contact and validate exposed growth outside finite original overlap port; not blanket component permission'
        terminals=[]
        for xy in r['terminal_points_decimal_mm']:
            point=Point(*map(float,xy))
            terminals.append(dict(point_decimal_mm=xy,
                current_land_covering_terminal=[sid for sid in contacts if meta[sid]['kind'] not in ('segment','arc') and scene.replacements.get(sid,scene.objects[sid]['geometry']).covers(point)],
                is_original_width_transition=any(p['point_decimal_mm']==xy for p in r['original_width_transition_ports'])))
        visible_in_crop=independently_exposed.intersection(crop)
        covered=independently_exposed.is_empty
        if covered:status='COVERED_SOURCE_PATH_NO_INDEPENDENT_GROWTH_CREDIT'
        elif visible_in_crop.is_empty:status='SOURCE_PATH_VISIBLE_ONLY_OUTSIDE_CROP_CONTEXT'
        elif r.get('route_type')=='DEGENERATE_SOURCE_STROKE_CONTEXT':status='DEGENERATE_SOURCE_STROKE_NOT_A_TRACE_ROUTE_CONTEXT'
        elif r['path_status']=='PROPOSED_COMPLETE_UNIFORM_SOURCE_PATH':status='VISIBLE_COMPLETE_UNIFORM_PATH_PROPOSAL_CONTACT_CHECKS_RETAINED'
        else:status='VISIBLE_UNIFORM_NETWORK_JUNCTION_ASSESSMENT_RETAINED'
        r.update(definition_status=status,source_sha256=report['source_sha256'],
            original_core_sha256=hashlib.sha256(to_wkb(core)).hexdigest(),
            original_core_area_mm2=core.area,independently_exposed_area_mm2=independently_exposed.area,
            independently_exposed_in_crop_area_mm2=visible_in_crop.area,
            old_endpoint_component_ids=sorted({old_component[sid] for sid in members}),
            outside_crop_source_ids=sorted(members-seeds),original_terminal_evidence=terminals,
            fixed_land_contact_ids=[sid for sid in contacts if meta[sid]['kind'] not in ('segment','arc')],
            neighboring_trace_contact_ids=[sid for sid in contacts if meta[sid]['kind'] in ('segment','arc')],
            change_from_old_filter='Existing interior land contacts and missing separate land at a native end are evidence to preserve/check, not automatic exclusion of the complete visible source path',
            construction_authority='DEFINITION_PROPOSAL_ONLY; source width growth NOT_RUN')
        statuses.append(status)
        r['_independent_exposed_geometry']=visible_in_crop
    owner=json.loads((marked/'COVERAGE_CORRECTION.json').read_text());path_by_source={sid:r['path_id'] for r in paths for sid in r['source_ids']}
    by_path={r['path_id']:r for r in paths}
    regions=[]
    for region in owner['regions']:
        found=sorted({path_by_source[sid] for sid in region['formerly_omitted_source_ids']})
        regions.append(dict(name=region['name'],formerly_omitted_source_ids=region['formerly_omitted_source_ids'],
            new_source_path_ids=found,new_definition_statuses=dict(Counter(by_path[k]['definition_status'] for k in found))))
    result=dict(schema='c02-uniform-source-path-proposals/1',asset_integrity=integrity,source_sha256=report['source_sha256'],
        cumulative_land_scene_sha256=report['cumulative_sha256'],viewport_mm=g['base']['bounds'],
        source_endpoint_inventory_sha256=hashlib.sha256((inventory/'TRACE_ENDPOINT_INVENTORY.json').read_bytes()).hexdigest(),
        full_source_objects=len(scene.objects),crop_seed_count=len(seeds),source_members_after_same_width_expansion=sum(len(r['source_ids']) for r in paths),
        path_count=len(paths),classifications=dict(Counter(statuses)),paths=paths,marked_regions=regions,
        width_transition_port_count=sum(len(r['original_width_transition_ports']) for r in paths),
        original_junction_port_count=sum(len(r.get('original_junction_ports',[])) for r in paths),
        source_copper_edit='NONE',width_growth='NOT_RUN',parallel_groups='NEXT; no singleton assumption from absent old eligibility',
        limitations=['These are new explicit source-path definitions, not accepted T04 target scope.',
            'Width changes at original source endpoints are recorded boundaries; no original primitive is trimmed or crop-cut.',
            'Visible branches/cycles retained for junction assessment; no independent branch acceptance.',
            'Covered primitives receive no independent growth credit but do not justify skipping visible containing copper.',
            'Required original contacts and full finite-copper checks remain mandatory; no electrical-intent claim.'])
    out.mkdir(parents=True);(out/'visuals').mkdir();(out/'exposed_source_paths').mkdir()
    exposed_geometry={}
    for r in paths:
        geo=r.pop('_independent_exposed_geometry');exposed_geometry[r['path_id']]=geo
        blob=to_wkb(geo);(out/f'exposed_source_paths/{r["path_id"]}.wkb').write_bytes(blob)
        r['exposed_in_crop_wkb_sha256']=hashlib.sha256(blob).hexdigest()
    (out/'UNIFORM_SOURCE_PATHS.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    for name,status in [('uniform_paths','VISIBLE_COMPLETE_UNIFORM_PATH_PROPOSAL_CONTACT_CHECKS_RETAINED'),('junction_networks','VISIBLE_UNIFORM_NETWORK_JUNCTION_ASSESSMENT_RETAINED')]:
        selected=[r for r in paths if r['definition_status']==status]
        copper=unary_union([exposed_geometry[r['path_id']] for r in selected])
        render(out/f'visuals/{name}.svg',f'C02 / revised trace definitions / {name.replace("_"," ")}',g['after'],copper,g['base']['bounds'],[],{},
            [f'{len(selected)} source definitions; TEAL = independently exposed source copper in this class. Red = cumulative scene.',
             'Definition correction only: all complete same-width members retained, including remote sections.',
             'Existing width-transition endpoints explicitly recorded; no arbitrary route trimming or crop boundary cuts.',
             'Original land and trace contacts remain protected evidence, not blanket clearance exemptions.',
             'Original junction boundaries and aliases stay explicit. Parallel memberships must be rebuilt.',
             'No trace widening or routing. Proposed definitions are not final T04 coverage/acceptance.'])
        subprocess.run(['sips','-s','format','png',str(out/f'visuals/{name}.svg'),'--out',str(out/f'visuals/{name}.png')],check=True,capture_output=True)
    table=''.join(f'<tr><td>{r["path_id"]}</td><td>{r["uniform_original_width_mm"]}</td><td>{len(r["source_ids"])}</td><td>{len(r["original_width_transition_ports"])}</td><td>{r["definition_status"]}</td></tr>' for r in paths)
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>C02 revised trace definitions</title><style>body{font:18px system-ui;max-width:1500px;margin:24px auto;color:#142a3f}img{width:100%}td{padding:7px;border-bottom:1px solid #ddd}</style><h1>C02 revised source path definitions — no width growth</h1><p>Complete native paths are retained across the full source. Existing width-transition boundaries are explicit; branch networks remain intact.</p><img src="visuals/uniform_paths.png"><img src="visuals/junction_networks.png"><p><a href="UNIFORM_SOURCE_PATHS.json">Exact source members, original junction ports and all11marked-region mappings</a></p><table><tr><th>Path ID</th><th>Original width</th><th>Full primitives</th><th>Width-transition ports</th><th>Definition status</th></tr>'+table+'</table>')
    print(json.dumps({k:v for k,v in result.items() if k not in ('paths','marked_regions','limitations')}))


if __name__=='__main__':main()
