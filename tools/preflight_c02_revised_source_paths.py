#!/usr/bin/env python3
"""Check revised complete source definitions at exact original widths only."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import json,hashlib
from shapely import to_wkb
from src.crop_circle_sources import verify_assets
from src.uniform_trace_width_v2 import construct_uniform_width
from src.trace_width_clearance import verify_width_scene
from tools.run_c02_four_attachment_diagnostic_v2 import compute


def main(verifier=verify_width_scene):
    pre,definitions,freeze,out=map(Path,sys.argv[1:]);assert not out.exists()
    verify_assets();frozen=json.loads(freeze.read_text());assert frozen['status']=='FROZEN_GEOMETRIC_PREDECESSOR'
    report,g=compute(pre);scene=g['scene'];assert report['cumulative_sha256']==frozen['cumulative_sha256']
    d=json.loads((definitions/'UNIFORM_SOURCE_PATHS.json').read_text());assert d['cumulative_land_scene_sha256']==frozen['cumulative_sha256']
    meta={r['id']:r for r in json.loads((pre/'inputs/source_manifest.json').read_text())['objects']}
    raw=g['base']['source'];records=[];traces=[];represented=set()
    active={'VISIBLE_COMPLETE_UNIFORM_PATH_PROPOSAL_CONTACT_CHECKS_RETAINED','VISIBLE_UNIFORM_NETWORK_JUNCTION_ASSESSMENT_RETAINED'}
    for r in d['paths']:
        chain=dict(r,component_id=r['path_id'])
        blobs={sid:(pre/f'inputs/source_wkb/{meta[sid]["geometry_sha256"]}.wkb').read_bytes() for sid in r['source_ids']}
        record,parts,original,candidate=construct_uniform_width(raw,chain,meta,blobs,1.)
        assert original.equals(candidate) and record['added_area_mm2']==0 and record['core_removed_mm2']==0
        assert all(to_wkb(parts[sid])==blobs[sid] for sid in r['source_ids'])
        records.append(dict(path_id=r['path_id'],definition_status=r['definition_status'],factor=1.,
            primitive_count=len(parts),primitive_wkb_exact=True,complete_source_ids=r['source_ids'],
            original_width_mm=record['verified_original_width_mm'],status='PASS_SOURCE_BINDING_AND_ROUTE_ENVELOPE'))
        if r['definition_status'] in active:
            assert represented.isdisjoint(r['source_ids']);represented.update(r['source_ids'])
            traces.append(dict(id=r['path_id'],original=original,candidate=candidate,verified_original_width_mm=record['verified_original_width_mm']))
    fixed=[dict(id=sid,geometry=scene.replacements.get(sid,r['geometry']),trace_width_mm=r['trace_width_mm']) for sid,r in scene.objects.items() if sid not in represented]
    check=verifier(traces,fixed)
    assert len(represented)+len(fixed)==17849
    out.mkdir(parents=True)
    (out/'FULL_SCENE_CHECK.json').write_text(json.dumps(check,indent=2,sort_keys=True)+'\n')
    print(json.dumps(dict(raw_check_passed=check['passed'],new_exposed_copper_mm2=check['new_exposed_copper_area_mm2'],
        failures=check['failures'][:4],all_trace_wkb_identity=all(to_wkb(r['original'])==to_wkb(r['candidate']) for r in traces))),flush=True)
    assert check['passed'] and check['new_exposed_copper_area_mm2']==0
    result=dict(schema='c02-revised-source-path-preflight/1',status='PASS_EXACT_ORIGINAL_WIDTH_PREFLIGHT',source_sha256=report['source_sha256'],frozen_land_cumulative_sha256=report['cumulative_sha256'],definition_sha256=hashlib.sha256((definitions/'UNIFORM_SOURCE_PATHS.json').read_bytes()).hexdigest(),defined_source_records=len(records),source_primitives_verified=sum(r['primitive_count'] for r in records),active_paths_and_networks=len(traces),represented_active_source_primitives=len(represented),fixed_source_objects=len(fixed),accounted_source_objects=len(represented)+len(fixed),factor=1.,new_exposed_copper_mm2=0.,records=records,positive_source_growth='NOT_RUN_BY_THIS_PREFLIGHT',limitations='Input binding and declared source-route envelope at original width only; no positive-width feasibility or expanded T04 acceptance')
    (out/'SOURCE_PREFLIGHT.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='records'}))


if __name__=='__main__':main()
