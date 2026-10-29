#!/usr/bin/env python3
"""Bounded full-route source-width proposal; requires a hash-bound land freeze.

Writes only derived evidence. Does not update native board data or acceptance.
The input gate receipt records the separate audited model-space predecessor.
"""
import argparse,hashlib,json,sys,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from shapely import STRtree,to_wkb
from shapely.geometry import box
from shapely.ops import unary_union
from src.crop_circle_sources import verify_assets
from src.uniform_trace_width_v2 import construct_uniform_width,FAMILY
from src.bounded_width_solver import solve_width_scales
from src.trace_width_clearance import verify_width_scene
from tools.run_c02_four_attachment_diagnostic_v2 import compute
from tools.run_c02_growth_coverage import render


def sha(data):return hashlib.sha256(data).hexdigest()


def main():
    p=argparse.ArgumentParser()
    for name in ('predecessor','inventory','qualification','groups','freeze-receipt','output'):
        p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();assert not a.output.exists(),'FRESH_OUTPUT_REQUIRED'
    receipt=json.loads(a.freeze_receipt.read_text())
    assert receipt['status']=='FROZEN_GEOMETRIC_PREDECESSOR','VALID_LAND_PREDECESSOR_REQUIRED'
    assert receipt['source_width_proposal_scope']=='DEFINED_GROUPS_FULL_SOURCE_CHECK','BOUNDED_SCOPE_REQUIRED'
    assert receipt['audit_verdict_observed'] is True,'RECORDED_AUDIT_REQUIRED'
    verify_assets()
    report,g=compute(a.predecessor);scene=g['scene'];source=g['base']['source']
    assert report['source_sha256']==receipt['source_sha256']
    assert report['cumulative_sha256']==receipt['cumulative_sha256']
    group_file=a.groups/'PARALLEL_MEMBERSHIP.json'
    qualification_file=a.qualification/'CHAIN_CONTACT_QUALIFICATION.json'
    assert sha(group_file.read_bytes())==receipt['parallel_membership_sha256']
    assert sha(qualification_file.read_bytes())==receipt['chain_qualification_sha256']
    groups=json.loads(group_file.read_text())
    assert groups['proposed_cumulative_scene_sha256']==receipt['cumulative_sha256']
    qualified=json.loads(qualification_file.read_text())
    allowed={r['component_id'] for r in qualified['chains'] if r['status']=='SOURCE_CHAIN_GEOMETRICALLY_QUALIFIED_FOR_WIDTH_FEASIBILITY'}
    inventory_file=a.inventory/'TRACE_ENDPOINT_INVENTORY.json'
    assert qualified['endpoint_inventory_sha256']==sha(inventory_file.read_bytes())
    inv=json.loads(inventory_file.read_text())
    selected=[r for r in groups['groups'] if r['status']=='DEFINED_FOR_COLLECTIVE_WIDTH_FEASIBILITY']
    members=[cid for r in selected for cid in r['members']]
    assert len(set(members))==len(members) and set(members)<=allowed
    chains={r['component_id']:dict(r,source_sha256=report['source_sha256']) for r in inv['components'] if r['component_id'] in members}
    assert len(chains)==len(members)
    meta={r['id']:r for r in json.loads((a.predecessor/'inputs/source_manifest.json').read_text())['objects']}
    source_ids={sid for r in chains.values() for sid in r['source_ids']}
    assert len(source_ids)==sum(len(r['source_ids']) for r in chains.values())
    blobs={sid:(a.predecessor/f'inputs/source_wkb/{meta[sid]["geometry_sha256"]}.wkb').read_bytes() for sid in source_ids}
    fixed=[dict(id=sid,geometry=scene.replacements.get(sid,r['geometry']),trace_width_mm=r['trace_width_mm'])
           for sid,r in scene.objects.items() if sid not in source_ids]
    group_by_chain={cid:r['group_id'] for r in selected for cid in r['members']}
    a.output.mkdir(parents=True);(a.output/'checks').mkdir();cache={};calls=[]
    def build(scales):
        traces=[];records=[];parts={}
        for cid,chain in sorted(chains.items()):
            factor=scales[group_by_chain[cid]];key=(cid,factor)
            if key not in cache:cache[key]=construct_uniform_width(source,chain,meta,blobs,factor)
            r,pp,original,candidate=cache[key];records.append(r);parts.update(pp)
            traces.append(dict(id=cid,original=original,candidate=candidate,verified_original_width_mm=r['verified_original_width_mm']))
        return traces,records,parts
    def evaluate(scales):
        # Construction errors abort the experiment, rather than masquerading as
        # clearance evidence or an upper-bound proof.
        traces,_,_=build(scales)
        q=verify_width_scene(traces,fixed)
        path=a.output/'checks'/f'{len(calls):04d}.json'
        path.write_text(json.dumps(dict(scales=scales,check=q),indent=2,sort_keys=True)+'\n')
        calls.append(dict(path=str(path.relative_to(a.output)),sha256=sha(path.read_bytes())))
        return q
    solution=solve_width_scales([r['group_id'] for r in selected],evaluate,geometry_family=FAMILY)
    (a.output/'SOLVER.json').write_text(json.dumps(solution,indent=2,sort_keys=True)+'\n')
    assert solution['passed'],'SOURCE_WIDTH_PROPOSAL_REJECTED'
    traces,records,parts=build(solution['selected_scales'])
    final=evaluate(solution['selected_scales']);assert final['passed']
    crop=box(*g['base']['bounds']);ids=sorted(scene.objects)
    current={sid:parts.get(sid,scene.replacements.get(sid,scene.objects[sid]['geometry'])) for sid in ids}
    tree=STRtree([current[sid] for sid in ids])
    after=unary_union([current[ids[int(i)]] for i in tree.query(crop,predicate='intersects')]).intersection(crop)
    before=g['after'];removed=before.difference(after).area
    assert removed<=1e-12,'LAND_PREDECESSOR_COPPER_REMOVED'
    for sid in scene.replacements:
        assert sid not in parts,'ACCEPTED_LAND_EDIT_ATTEMPT'
    for label,geometry in [('before',before),('after',after),('added',after.difference(before))]:
        (a.output/f'{label}.wkb').write_bytes(to_wkb(geometry))
    (a.output/'CONSTRUCTION.json').write_text(json.dumps(records,indent=2,sort_keys=True)+'\n')
    (a.output/'CHECK_INDEX.json').write_text(json.dumps(calls,indent=2)+'\n')
    result=dict(schema='c02-source-width-proposal/1',status='PROPOSED_PENDING_BATCH_AUDIT',
        source_sha256=report['source_sha256'],land_predecessor_sha256=report['cumulative_sha256'],
        freeze_receipt_sha256=sha(a.freeze_receipt.read_bytes()),group_count=len(selected),complete_trace_count=len(chains),
        original_source_primitive_count=len(source_ids),fixed_source_object_count=len(fixed),
        total_accounted_source_objects=len(source_ids)+len(fixed),current_crop_sha256=sha(to_wkb(after)),
        selected_scales=solution['selected_scales'],maximum_established=solution['maximum_established'],
        width_geometry_role='CONSERVATIVE_MODEL_VERIFICATION_ENVELOPES; no native board export',
        positive_groups=sum(v>1 for v in solution['selected_scales'].values()),
        added_copper_in_crop_mm2=after.difference(before).area,predecessor_removed_mm2=removed,
        unresolved_group_scopes=[r['group_id'] for r in groups['groups'] if r not in selected],
        unresolved_scope='Retained, not accepted or treated as clearance defects',
        T03='DEFERRED',T04='BOUNDED_SOURCE_PROPOSAL_NOT_FINAL_ACCEPTANCE')
    (a.output/'RESULT.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    for label,copper,delta in [('before',before,before.difference(before)),('after',after,after.difference(before))]:
        svg=a.output/f'{label}.svg'
        render(svg,f'C02 / uniform full-route width proposal / {label}',copper,delta,g['base']['bounds'],[],{},
            [f'Actual source-bound model: {len(selected)} defined groups, {len(chains)} complete traces. All other source copper fixed.',
             'Each complete trace has one nominal width; each parallel group or singleton has one common factor, at most1.5.',
             'Full routes beyond the crop and simultaneous finite-copper surfaces checked. Accepted land geometry fixed.',
             'Red = cumulative copper union; teal = width verification envelope added relative to frozen lands.',
             'Positive geometry includes10nm conservative validation margin. No route change, neckdown or native export.',
             'Bounded proposal only. Unresolved source/group definitions remain excluded; no final C02/electrical acceptance.'])
        subprocess.run(['sips','-s','format','png',str(svg),'--out',str(a.output/f'{label}.png')],check=True,capture_output=True)
    (a.output/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>C02 source width proposal</title><style>body{font:18px system-ui;max-width:1400px;margin:24px auto}img{width:100%}</style><h1>C02 cumulative width proposal — bounded scope</h1><h2>Frozen land predecessor</h2><img src="before.png"><h2>Uniform-width source proposal</h2><img src="after.png"><p><a href="RESULT.json">Coverage, group scales and unresolved scope</a> · <a href="SOLVER.json">Solver checks and maximum claims</a></p>')
    print(json.dumps(result))


if __name__=='__main__':main()
