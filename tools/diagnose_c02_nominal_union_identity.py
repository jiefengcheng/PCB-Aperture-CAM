#!/usr/bin/env python3
"""Read-only union identity diagnostic. No assertion is weakened or waived."""
import sys,json,hashlib,platform
from pathlib import Path
import shapely
from shapely import from_wkb,to_wkb,normalize,get_num_coordinates
from shapely.ops import unary_union


def sha(b):return hashlib.sha256(b).hexdigest()


def main():
    proposal,canonical,out=map(Path,sys.argv[1:]);assert not out.exists()
    pins=json.loads((canonical/'CANONICAL_ROUTE_CACHE.json').read_text())['records']
    targets={r['path_id'] for r in pins};assert targets and len(targets)==len(pins)
    records=[]
    for r in json.loads((proposal/'CONSTRUCTION.json').read_text()):
        if r['component_id'] not in targets:continue
        cid=r['component_id'];blob=(canonical/f'{cid}.wkb').read_bytes()
        assert sha(blob)==r['nominal_copper_wkb_sha256'],'CANONICAL_PREIMAGE_HASH_MISMATCH'
        expected=from_wkb(blob);parts=[];part_checks=[]
        for p in r['primitives']:
            sid=p['source_id'];part=(proposal/'nominal_source_parts'/f'{sha(sid.encode())}.wkb').read_bytes()
            assert sha(part)==p['nominal_candidate_wkb_sha256'],'RETAINED_PART_HASH_MISMATCH'
            parts.append(from_wkb(part));part_checks.append(dict(source_id=sid,retained_part_sha256=sha(part)))
        union=unary_union(parts);actual=to_wkb(union)
        row=dict(path_id=cid,expected_sha256=sha(blob),actual_sha256=sha(actual),raw_wkb_exact=actual==blob,
            normalized_wkb_exact=to_wkb(normalize(union))==to_wkb(normalize(expected)),
            topological_equals=union.equals(expected),coordinate_sequence_equals_zero_tolerance=union.equals_exact(expected,0.),
            expected_coordinates=int(get_num_coordinates(expected)),actual_coordinates=int(get_num_coordinates(union)),
            symmetric_difference_area_mm2=union.symmetric_difference(expected).area,
            hausdorff_distance_mm=union.hausdorff_distance(expected),parts=part_checks)
        records.append(row)
    assert {r['path_id'] for r in records}==targets
    out.mkdir();result=dict(role='DIAGNOSTIC_ONLY_NO_ACCEPTANCE_OR_TOLERANCE_CHANGE',python=sys.version,platform=platform.platform(),shapely=shapely.__version__,geos=shapely.geos_version_string,route_count=len(records),raw_identity_mismatches=sum(not r['raw_wkb_exact'] for r in records),normalized_identity_mismatches=sum(not r['normalized_wkb_exact'] for r in records),records=records)
    (out/'UNION_IDENTITY_DIAGNOSTIC.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='records'}))


if __name__=='__main__':main()
