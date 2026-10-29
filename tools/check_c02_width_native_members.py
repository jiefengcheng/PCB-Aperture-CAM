#!/usr/bin/env python3
"""Check the saved bounded proposal without collapsing source primitive pairs."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import json,hashlib
from shapely import STRtree,to_wkb,from_wkb
from shapely.geometry import box
from shapely.ops import unary_union
from src.crop_circle_sources import verify_assets
from src.uniform_trace_width_v2 import construct_uniform_width
from src.prepared_width_scene import PreparedWidthScene
from tools.run_c02_four_attachment_diagnostic_v2 import compute


def main():
    pre,saved,out=map(Path,sys.argv[1:]);assert not out.exists();verify_assets()
    report,g=compute(pre);scene=g['scene'];bank=json.loads((pre/'inputs/source_manifest.json').read_text());meta={r['id']:r for r in bank['objects']}
    original_records=json.loads((saved/'CONSTRUCTION.json').read_text());parts={};traces=[]
    for r in original_records:
        chain=dict(component_id=r['component_id'],source_ids=r['complete_source_ids'],source_sha256=bank['source_sha256'])
        blobs={sid:(pre/f'inputs/source_wkb/{meta[sid]["geometry_sha256"]}.wkb').read_bytes() for sid in chain['source_ids']}
        new,pieces,_,_=construct_uniform_width(g['base']['source'],chain,meta,blobs,r['factor'])
        for p in r['primitives']:
            sid=p['source_id'];assert hashlib.sha256(to_wkb(pieces[sid])).hexdigest()==p['candidate_wkb_sha256']
            assert sid not in parts
            parts[sid]=pieces[sid]
            traces.append(dict(id=sid,original=from_wkb(blobs[sid]),candidate=pieces[sid],verified_original_width_mm=p['original_width_mm']))
    fixed=[dict(id=sid,geometry=scene.replacements.get(sid,r['geometry']),trace_width_mm=r['trace_width_mm']) for sid,r in scene.objects.items() if sid not in parts]
    assert len(traces)+len(fixed)==17849
    context=PreparedWidthScene(traces,fixed);check=context.check(traces,materialize_scene=True)
    out.mkdir(parents=True);(out/'FULL_NATIVE_MEMBER_CHECK.json').write_text(json.dumps(check,indent=2,sort_keys=True)+'\n')
    ids=sorted(scene.objects);current=[parts.get(sid,scene.replacements.get(sid,scene.objects[sid]['geometry'])) for sid in ids];tree=STRtree(current);crop=box(*g['base']['bounds'])
    after=unary_union([current[int(i)] for i in tree.query(crop,predicate='intersects')]).intersection(crop)
    assert to_wkb(after)==(saved/'after.wkb').read_bytes()
    result=dict(schema='c02-width-native-member-check/1',passed=check['passed'],source_sha256=bank['source_sha256'],frozen_land_sha256=report['cumulative_sha256'],complete_route_count=len(original_records),native_member_rows=len(traces),fixed_rows=len(fixed),all_source_objects_accounted=17849,saved_candidate_parts_exact=True,saved_crop_wkb_exact=True,source_growth='NONE_NEW; rechecks exact saved proposal',policy='Same finite original-contact and visible-surface predicates; every changed source primitive remains independently checked, including same-route pairs',unchanged_source_identity='No growth by exact WKB identity',failures=check['failures'])
    (out/'RESULT.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n');print(json.dumps(result))


if __name__=='__main__':main()
