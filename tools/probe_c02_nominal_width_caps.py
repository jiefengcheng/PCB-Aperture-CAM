#!/usr/bin/env python3
"""Nominal/envelope containment probes; full caps are NOT clearance-approved."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import json,hashlib
from shapely import to_wkb
from src.crop_circle_sources import verify_assets
from src.uniform_trace_nominal import construct_nominal_width


def main():
    pre,definitions,out=map(Path,sys.argv[1:]);assert not out.exists();verify_assets()
    raw=(pre/'inputs/ORG_source.kicad_pcb').read_bytes();bank=json.loads((pre/'inputs/source_manifest.json').read_text());assert hashlib.sha256(raw).hexdigest()==bank['source_sha256']
    meta={r['id']:r for r in bank['objects']};d=json.loads((definitions/'UNIFORM_SOURCE_PATHS.json').read_text());assert d['source_sha256']==bank['source_sha256']
    out.mkdir(parents=True);(out/'geometry').mkdir();records=[]
    for r in d['paths']:
        chain=dict(r,component_id=r['path_id'])
        blobs={sid:(pre/f'inputs/source_wkb/{meta[sid]["geometry_sha256"]}.wkb').read_bytes() for sid in r['source_ids']}
        try:
            record,nominal_parts,envelope_parts,original,nominal,envelope=construct_nominal_width(raw,chain,meta,blobs,1.5)
            (out/f'geometry/{r["path_id"]}_nominal.wkb').write_bytes(to_wkb(nominal))
            (out/f'geometry/{r["path_id"]}_envelope.wkb').write_bytes(to_wkb(envelope))
            records.append(dict(path_id=r['path_id'],definition_status=r['definition_status'],status='PASS_NOMINAL_CORE_RETENTION_AND_ENVELOPE_CONTAINMENT',source_ids=r['source_ids'],construction=record,clearance='NOT_CHECKED; cap probe only'))
        except ValueError as e:
            records.append(dict(path_id=r['path_id'],definition_status=r['definition_status'],status='NOMINAL_CONSTRUCTION_NOT_ESTABLISHED',source_ids=r['source_ids'],error=str(e),clearance='NOT_RUN'))
    failures=[r for r in records if r['status']!='PASS_NOMINAL_CORE_RETENTION_AND_ENVELOPE_CONTAINMENT']
    result=dict(schema='c02-nominal-width-cap-probes/1',source_sha256=bank['source_sha256'],definition_sha256=hashlib.sha256((definitions/'UNIFORM_SOURCE_PATHS.json').read_bytes()).hexdigest(),factor=1.5,path_count=len(records),source_primitive_count=sum(len(r['source_ids']) for r in records),passed=len(records)-len(failures),not_established=len(failures),records=records,source_scene_change='NONE; individual cap construction probes only',stage_acceptance='NONE',width_ceiling='Nominal copper has no verification margin; conservative envelope is separate',clearance='Caps are not feasible source scene results; simultaneous checks still required')
    (out/'NOMINAL_CAP_PROBES.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='records'}))
    if failures:print(json.dumps([dict(path_id=r['path_id'],error=r['error']) for r in failures]))


if __name__=='__main__':main()
