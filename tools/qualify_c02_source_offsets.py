#!/usr/bin/env python3
"""Read-only nominal/core/envelope qualification for every source route."""
import sys,json,hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.crop_circle_sources import verify_assets
from src.source_offset_width import construct_source_offset_width,FAMILY


def main():
    pre,definitions,out=map(Path,sys.argv[1:]);assert not out.exists()
    integrity=verify_assets();raw=(pre/'inputs/ORG_source.kicad_pcb').read_bytes()
    meta={r['id']:r for r in json.loads((pre/'inputs/source_manifest.json').read_text())['objects']}
    definition=definitions/'UNIFORM_SOURCE_PATHS.json';d=json.loads(definition.read_text())
    assert hashlib.sha256(raw).hexdigest()==d['source_sha256']
    records=[];factors=[1.,1.000001,1.01,1.25,1.5]
    for r in d['paths']:
        blobs={sid:(pre/f'inputs/source_wkb/{meta[sid]["geometry_sha256"]}.wkb').read_bytes() for sid in r['source_ids']}
        previous=None;checks=[]
        try:
            for factor in factors:
                record,_,_,core,nominal,envelope=construct_source_offset_width(raw,dict(r,component_id=r['path_id']),meta,blobs,factor)
                if previous is not None and not envelope.covers(previous):raise ValueError('NON_NESTED_ENVELOPE')
                previous=envelope
                checks.append(dict(factor=factor,nominal_sha256=record['nominal_copper_wkb_sha256'],envelope_sha256=record['verification_envelope_wkb_sha256']))
            records.append(dict(path_id=r['path_id'],status='PASS_CORE_RETENTION_CONTAINMENT_SAMPLED_NESTING',checks=checks))
        except ValueError as e:records.append(dict(path_id=r['path_id'],status='NOT_ESTABLISHED',error=str(e),checks=checks))
    result=dict(geometry_family=FAMILY,asset_integrity=integrity,source_sha256=d['source_sha256'],definition_file_sha256=hashlib.sha256(definition.read_bytes()).hexdigest(),sampled_factors=factors,path_count=len(records),passed=sum(r['status'].startswith('PASS') for r in records),records=records,clearance='NOT_RUN; construction qualification only',acceptance='NONE')
    out.mkdir();(out/'QUALIFICATION.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='records'}))


if __name__=='__main__':main()
