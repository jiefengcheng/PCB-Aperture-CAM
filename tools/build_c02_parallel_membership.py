#!/usr/bin/env python3
"""Source-based local parallel relationships; no trace growth or acceptance."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import hashlib,json,re,subprocess,html
from collections import Counter
from shapely import STRtree
from shapely.geometry import LineString,box
from shapely.ops import unary_union
from src.parallel_trace_relations import parallel_relation,relation_groups
from tools.run_c02_four_attachment_diagnostic_v2 import compute
from tools.run_c02_growth_coverage import render,svg_shape


def main():
    pre,inventory,qualification,out=map(Path,sys.argv[1:])
    assert not out.exists()
    report,g=compute(pre)
    d=json.loads((inventory/'TRACE_ENDPOINT_INVENTORY.json').read_text())
    q=json.loads((qualification/'CHAIN_CONTACT_QUALIFICATION.json').read_text())
    qualified={c['component_id']:c for c in q['chains']}
    scene=g['scene'];raw=g['base']['source'];crop=box(*g['base']['bounds'])
    ids=sorted(scene.objects)
    all_geoms={sid:scene.replacements.get(sid,scene.objects[sid]['geometry']) for sid in ids}
    tree=STRtree([all_geoms[sid] for sid in ids])
    members={c['component_id']:c for c in d['components']
             if qualified[c['component_id']]['status']!='COVERED_SOURCE_TRACE_NO_INDEPENDENT_EXPOSED_ROUTE'}
    entries=[]
    for cid,c in sorted(members.items()):
        for r in c['original_full_source_members']:
            if r['kind']!='segment' or not all_geoms[r['source_id']].intersects(crop):continue
            a,b=map(int,r['source_id'].rsplit(':',2)[1:]);fragment=raw[a:b]
            points=[]
            for name in ('start','end'):
                m=re.search(rb'\('+name.encode()+rb'\s+([^\s()]+)\s+([^\s()]+)\)',fragment)
                assert m is not None
                points.append([float(v) for v in m.groups()])
            if points[0]==points[1]:continue
            entries.append(dict(component=cid,source_id=r['source_id'],points=points))
    entries.sort(key=lambda r:r['source_id'])
    paths=[LineString(r['points']) for r in entries];path_tree=STRtree(paths)
    accepted=[];blocked=[]
    for i,a in enumerate(entries):
        for j in sorted(int(v) for v in path_tree.query(paths[i].buffer(.5)) if int(v)>i):
            b=entries[j]
            if a['component']==b['component']:continue
            relation=parallel_relation(a['points'],b['points'])
            if relation is None:continue
            ag,bg=all_geoms[a['source_id']],all_geoms[b['source_id']]
            if ag.intersects(bg):continue
            cross=LineString(relation['midpoint_cross_section_mm']).difference(ag.union(bg))
            excluded=set(members[a['component']]['source_ids']+members[b['component']]['source_ids'])
            blockers=sorted(ids[int(k)] for k in tree.query(cross,predicate='intersects') if ids[int(k)] not in excluded)
            row=dict(component_a=a['component'],component_b=b['component'],source_a=a['source_id'],source_b=b['source_id'],
                     finite_width_source_gap_mm=ag.distance(bg),**relation)
            if blockers:
                blocked.append(dict(**row,cross_section_blocker_source_ids=blockers))
            else:accepted.append(row)
    edges=sorted({tuple(sorted((r['component_a'],r['component_b']))) for r in accepted})
    grouped=relation_groups(sorted(members),edges)
    groups=[]
    for row in grouped:
        cid='PG-'+hashlib.sha256('\n'.join(row).encode()).hexdigest()[:16]
        ready=all(qualified[v]['status']=='SOURCE_CHAIN_GEOMETRICALLY_QUALIFIED_FOR_WIDTH_FEASIBILITY' for v in row)
        groups.append(dict(group_id=cid,members=row,source_member_count=sum(len(members[v]['source_ids']) for v in row),
            status='DEFINED_FOR_COLLECTIVE_WIDTH_FEASIBILITY' if ready else 'GROUP_SCOPE_HAS_UNRESOLVED_SOURCE_CHAIN',
            intended_scale_rule='One common factor; each full defined trace retains its own original uniform width, fixed route; maximum 1.5',
            width_growth='NOT_RUN'))
    out.mkdir(parents=True);(out/'visuals').mkdir()
    result=dict(schema='c02-source-local-parallel-membership/1',source_sha256=report['source_sha256'],
        proposed_cumulative_scene_sha256=report['cumulative_sha256'],selection_parameters=dict(angle_degrees=1.,minimum_shared_projection_mm=.25,maximum_transverse_distance_mm=.5),
        accepted_local_cross_section_relationships=accepted,blocked_cross_section_relationships=blocked,
        groups=groups,classifications=dict(Counter(r['status'] for r in groups)),
        limitations=['Relationship proposals only; all-path width and clearance verification still required.',
            'Straight source spans establish local membership; arcs and remote sections remain full-route constraints.',
            'A clear midpoint cross-section alone is not proof of clearance throughout a corridor.',
            'No route or width edits. No T02 freeze or T04 execution. Covered source chains remain in the prior inventory.'])
    (out/'PARALLEL_MEMBERSHIP.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    ready_groups=[r for r in groups if r['status']=='DEFINED_FOR_COLLECTIVE_WIDTH_FEASIBILITY']
    palette=['#23c9b3','#ffca58','#69baff','#d497ff','#ff9e78','#a7da58','#f184c2','#8fd5e8','#b8b7ff','#e9bf8b','#86c6ab','#edeb89','#e6a7dd']
    for index,r in enumerate(ready_groups):r['visual_color']=palette[index%len(palette)]
    (out/'VISUAL_COLOR_BINDINGS.json').write_text(json.dumps({r['group_id']:dict(color=r['visual_color'],members=r['members']) for r in ready_groups},indent=2,sort_keys=True)+'\n')
    overlays=unary_union([all_geoms[sid] for r in ready_groups for cid in r['members'] for sid in members[cid]['source_ids']])
    notes=[f'{len(accepted)} unblocked local source-span relations; {len(blocked)} blocked cross-sections retained.',
        f'{len(ready_groups)} groups/singletons have defined source chains; other memberships remain unresolved.',
        'Distinct colors = unchanged native footprints of defined groups; red = retained cumulative copper. Colors map to the table.',
        'Group membership uses source directions and an actual finite-copper cross-section blocker check.',
        'Clearance along full routes, remote obstacles and curved sections still constrain any common width scale.',
        'No width growth, routing, stage acceptance or T02 freeze. Local relationships are preparation only.']
    render(out/'visuals/defined_groups.svg','C02 / immediate parallel-neighbor preparation',g['after'],overlays,g['base']['bounds'],[],{},notes)
    svg=out/'visuals/defined_groups.svg'
    colored=''.join(svg_shape(unary_union([all_geoms[sid] for cid in r['members'] for sid in members[cid]['source_ids']]).intersection(crop),r['visual_color']) for r in ready_groups)
    svg.write_text(svg.read_text().replace('</svg>',colored+'</svg>',1))
    subprocess.run(['sips','-s','format','png',str(out/'visuals/defined_groups.svg'),'--out',str(out/'visuals/defined_groups.png')],check=True,capture_output=True)
    table=''.join('<tr><td style="border-left:12px solid '+r.get('visual_color','#999')+'">'+r['group_id']+'</td><td>'+str(len(r['members']))+'</td><td>'+html.escape(r['status'])+'</td><td>'+html.escape(', '.join(r['members']))+'</td></tr>' for r in groups)
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>C02 parallel membership</title><style>body{font:18px system-ui;margin:24px;color:#142a3f}img{width:100%}td{padding:8px;border-bottom:1px solid #ddd}</style><h1>C02 parallel-neighbor proposals — no width growth</h1><img src="visuals/defined_groups.png"><table>'+table+'</table>')
    print(json.dumps(dict(source_spans=len(entries),accepted_relations=len(accepted),blocked_cross_sections=len(blocked),groups=len(groups),classifications=result['classifications'])))


if __name__=='__main__':main()
