#!/usr/bin/env python3
"""Read-only source-surface bounds; not a T04 construction or clearance pass."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import hashlib,json,subprocess,html
from collections import Counter
from shapely import STRtree
from shapely.geometry import LineString
from shapely.ops import unary_union,nearest_points
from src.collective_width_bounds import shared_scale_bound
from tools.run_c02_four_attachment_diagnostic_v2 import compute
from tools.run_c02_growth_coverage import render


def main():
    pre,inventory,qualification,membership,out=map(Path,sys.argv[1:])
    assert not out.exists()
    report,g=compute(pre)
    source=json.loads((inventory/'TRACE_ENDPOINT_INVENTORY.json').read_text())
    contacts=json.loads((qualification/'CHAIN_CONTACT_QUALIFICATION.json').read_text())
    parallel=json.loads((membership/'PARALLEL_MEMBERSHIP.json').read_text())
    chains={c['component_id']:c for c in source['components']}
    qualified={c['component_id']:c for c in contacts['chains']}
    scene=g['scene'];ids=sorted(scene.objects)
    geom={sid:scene.replacements.get(sid,scene.objects[sid]['geometry']) for sid in ids}
    tree=STRtree([geom[sid] for sid in ids])
    rows=[]
    for group in parallel['groups']:
        if group['status']!='DEFINED_FOR_COLLECTIVE_WIDTH_FEASIBILITY':continue
        widths={cid:chains[cid]['original_widths_mm'][0] for cid in group['members']}
        cores={cid:unary_union([geom[sid] for sid in chains[cid]['source_ids']]) for cid in widths}
        all_members={sid for cid in widths for sid in chains[cid]['source_ids']}
        constraints=[];unresolved=[];seen=set()
        for cid,core in sorted(cores.items()):
            radius=widths[cid]/4+.02010+max(widths.values())/4
            neighbor_ids={ids[int(i)] for i in tree.query(core.buffer(radius))}-all_members
            comparisons=[(other,cores[other],set(chains[other]['source_ids'])) for other in sorted(cores) if cid<other]
            comparisons += [(sid,geom[sid],{sid}) for sid in sorted(neighbor_ids)]
            for other,ob,other_sources in comparisons:
                key=(cid,other)
                if key in seen:continue
                seen.add(key)
                distance=core.distance(ob)
                if distance>radius:continue
                pair_id='W-'+hashlib.sha256((cid+'\n'+other).encode()).hexdigest()[:16]
                if distance==0:
                    unresolved.append(dict(constraint_id=pair_id,member_a=cid,neighbor=other,
                        status='ORIGINAL_CONTACT_REQUIRES_FINITE_ATTACHMENT_PORT_CHECK',surface_gap_mm=distance))
                    continue
                points=nearest_points(core,ob);witness=LineString(points)
                excluded=set(chains[cid]['source_ids'])|other_sources
                occluders=sorted(ids[int(i)] for i in tree.query(witness,predicate='intersects') if ids[int(i)] not in excluded)
                if occluders:
                    unresolved.append(dict(constraint_id=pair_id,member_a=cid,neighbor=other,
                        status='RAW_NEAREST_WITNESS_OCCLUDED_BY_OTHER_SOURCE_COPPER',surface_gap_mm=distance,
                        witness_mm=[list(p.coords[0]) for p in points],occluding_source_ids=occluders))
                    continue
                constraints.append(dict(constraint_id=pair_id,member_a=cid,member_b=other if other in cores else None,
                    fixed_neighbor_source_id=None if other in cores else other,
                    surface_gap_mm=distance,applicability='EXPOSED_DISCONNECTED_SURFACES',
                    witness_mm=[list(p.coords[0]) for p in points]))
        bound=shared_scale_bound(widths,constraints)
        rows.append(dict(group_id=group['group_id'],members=group['members'],analytical_bound=bound,
            applicable_witnesses=constraints,remaining_relationship_checks=unresolved,
            status='PRELIMINARY_BOUND_ONLY_NOT_EXECUTABLE',
            reasons=['Finite original attachment ports still require complete growth verification.',
                     'Other groups remain fixed in this analysis; simultaneous growth requires cumulative checking.',
                     'No width geometry or unchanged-source feasibility verdict is inferred from this upper bound.']))
    out.mkdir(parents=True);(out/'visuals').mkdir()
    result=dict(schema='c02-collective-width-source-bounds/1',source_sha256=report['source_sha256'],
        proposed_cumulative_scene_sha256=report['cumulative_sha256'],groups=rows,
        construction='NOT_RUN',T02='NOT_FROZEN_PENDING_BATCH_AUDIT',
        summary=dict(groups=len(rows),positive_bound_groups=sum(r['analytical_bound']['common_factor_upper_bound']>1 for r in rows),
            constraint_witnesses=sum(len(r['applicable_witnesses']) for r in rows),
            remaining_relationships=sum(len(r['remaining_relationship_checks']) for r in rows)))
    (out/'COLLECTIVE_WIDTH_BOUNDS.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    selected=unary_union([geom[sid] for r in rows for cid in r['members'] for sid in chains[cid]['source_ids']])
    notes=[f'{len(rows)} defined groups/singletons: source-derived preliminary shared scale bounds; hard cap 1.5.',
        'Teal = unchanged original full trace footprints, not widened copper. Red = current cumulative predecessor.',
        'Only unoccluded nearest-surface witnesses enter analytical bounds; internal source boundaries are not defects.',
        'Original contacts and occluded witnesses remain explicit for finite-port/full-scene checks.',
        'Bounds include remote sections of each full source chain. A limiting relationship constrains every group member.',
        'NOT EXECUTABLE: no T04 width result or T02 freeze. Coupled groups and full finite-copper validation still required.']
    render(out/'visuals/source_bounds.svg','C02 / collective trace-width preparation — source witnesses',g['after'],selected,g['base']['bounds'],[],{},notes)
    subprocess.run(['sips','-s','format','png',str(out/'visuals/source_bounds.svg'),'--out',str(out/'visuals/source_bounds.png')],check=True,capture_output=True)
    table=''.join('<tr><td>'+r['group_id']+'</td><td>'+str(len(r['members']))+'</td><td>'+format(r['analytical_bound']['common_factor_upper_bound'],'.9f')+'</td><td>'+str(len(r['remaining_relationship_checks']))+'</td></tr>' for r in rows)
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>C02 width bounds</title><style>body{font:18px system-ui;margin:24px;color:#142a3f}img{width:100%}td,th{padding:8px;border-bottom:1px solid #ddd}</style><h1>C02 shared width bounds — preparation only</h1><p>These bounds are not width-growth results or clearance verdicts. An unchanged inherited relationship is not a T02 defect.</p><img src="visuals/source_bounds.png"><table><tr><th>Group</th><th>Traces</th><th>Preliminary common-factor upper bound</th><th>Remaining relationship checks</th></tr>'+table+'</table>')
    print(json.dumps(result['summary']))


if __name__=='__main__':main()
