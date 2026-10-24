#!/usr/bin/env python3
"""Fresh-process same-parser audit of T02's deferred native-trace overlap ledger."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

from shapely import wkb
from shapely.geometry import LineString
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.native_reference import one
from src.native_inventory import arc_points
from src.org_edit_target_map import _inventory_side, _row_geometry
from src.crop_rect_t02 import is_side_by_side_trace

def sha(data):
    return hashlib.sha256(data).hexdigest()

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--run',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args()
    run=args.run if args.run.is_absolute() else ROOT/args.run
    output=args.output if args.output.is_absolute() else ROOT/args.output
    result=json.loads((run/'t02_result.json').read_bytes())
    ledger=json.loads((run/'future_trace_work_items.json').read_bytes())
    decisions=json.loads((run/'t02_decisions.json').read_bytes())['decisions']
    policy=json.loads((run/'t02_policy.json').read_bytes())
    source= (ROOT/policy['source']).read_bytes()
    source_hash=sha(source)
    if source_hash!=result['source_sha256'] or ledger['source_sha256']!=source_hash:
        raise ValueError('T02_TRACE_AUDIT_SOURCE_HASH_MISMATCH')
    side=_inventory_side(source,source_hash)
    rows={r['id']:r for r in side['rows']}
    traces={}
    for row in side['rows']:
        if row.get('kind') not in policy['trace_interactions']['trace_source_kinds'] or 'F.Cu' not in row.get('layers',[]):
            continue
        node=__import__('sexpdata').loads(source[row['source_span'][0]:row['source_span'][1]].decode())
        xy=lambda k:tuple(map(float,one(node,k)))
        start,end=xy('start'),xy('end')
        center=LineString(arc_points(start,xy('mid'),end) if row['kind']=='arc' else [start,end])
        traces[row['id']]={'row':row,'geometry':_row_geometry(row,side['payloads']),'centerline':center}
    decisions_by_id={d['source_id']:d for d in decisions}
    ledger_keys=set()
    checked=0
    for item in ledger['items']:
        key=(item['rectangle_source_id'],item['trace_source_id'])
        if key in ledger_keys:
            raise ValueError('DUPLICATE_T02_FUTURE_TRACE_WORK_ITEM')
        ledger_keys.add(key)
        d=decisions_by_id[key[0]]
        t=traces[key[1]]
        if list(d['source_span'])!=item['rectangle_source_span']:
            raise ValueError('RECTANGLE_SOURCE_SPAN_MISMATCH')
        if list(t['row']['source_span'])!=item['trace_source_span']:
            raise ValueError('TRACE_SOURCE_SPAN_MISMATCH')
        if t['row']['geometry_sha256']!=item['trace_geometry_sha256']:
            raise ValueError('TRACE_GEOMETRY_HASH_MISMATCH')
        candidate=wkb.loads((run/'t02_candidates'/f"{sha(key[0].encode())}.wkb").read_bytes())
        core=_row_geometry(rows[key[0]],side['payloads'])
        intersection=candidate.difference(core).intersection(t['geometry'])
        if intersection.is_empty or intersection.area<=1e-12:
            raise ValueError('RECORDED_TRACE_OVERLAP_NOT_PRESENT')
        if abs(intersection.area-item['overlap_area_mm2'])>1e-10:
            raise ValueError('RECORDED_TRACE_OVERLAP_AREA_MISMATCH')
        if sha(intersection.wkb)!=item['growth_trace_copper_intersection_wkb_sha256']:
            raise ValueError('RECORDED_TRACE_OVERLAP_HASH_MISMATCH')
        if item['disposition']!='DEFERRED_TO_FUTURE_TRACE_SESSION' or item['trace_changed_in_t02'] is not False:
            raise ValueError('TRACE_WORK_ITEM_DISPOSITION_INVALID')
        checked+=1
    expected=set()
    side_centerline_checks=0
    for d in decisions:
        candidate=wkb.loads((run/'t02_candidates'/f"{sha(d['source_id'].encode())}.wkb").read_bytes())
        core=_row_geometry(rows[d['source_id']],side['payloads'])
        # Recover the center and orientation from the exact native rectangle.
        center=core.centroid.coords[0]
        orientation=float(d['orientation_radians'])
        for tid,t in traces.items():
            side_by_side=is_side_by_side_trace(core,center,orientation,t['centerline'],t['row']['kind'])
            if side_by_side:
                side_centerline_checks+=1
                if candidate.distance(t['centerline'])+float(policy['geometry_tolerance_mm'])<float(policy['construction_gap_mm']):
                    raise ValueError('SIDE_BY_SIDE_CENTERLINE_GAP_VIOLATION')
            intersection=candidate.difference(core).intersection(t['geometry'])
            if not intersection.is_empty and intersection.area>1e-12:
                expected.add((d['source_id'],tid))
    if expected!=ledger_keys:
        raise ValueError(f'T02_FUTURE_TRACE_LEDGER_COVERAGE_MISMATCH:missing={len(expected-ledger_keys)} extra={len(ledger_keys-expected)}')
    trace_union=unary_union([t['geometry'] for t in traces.values()])
    addition_union=wkb.loads((run/'t02_additions.wkb').read_bytes())
    unique_overlap=addition_union.intersection(trace_union).area
    if abs(unique_overlap-float(ledger['unique_t02_added_copper_overlap_area_mm2']))>1e-10:
        raise ValueError('T02_UNIQUE_TRACE_OVERLAP_AREA_MISMATCH')
    report={
      'schema':'t02-future-trace-overlap-audit/1',
      'status':'PASS_SAME_PARSER_SAME_GEOMETRY_LIBRARY_LEDGER_AND_CENTERLINE_CHECKS',
      'source_sha256':source_hash,
      'policy_sha256':result['policy_sha256'],
      't01_scene_sha256':result['accepted_T01_scene_sha256'],
      'run':run.name,
      'trace_overlap_records_checked':checked,
      'expected_trace_overlap_pairs':len(expected),
      'pairwise_overlap_area_total_mm2':sum(float(x['overlap_area_mm2']) for x in ledger['items']),
      'unique_added_copper_overlap_area_mm2':unique_overlap,
      'unique_overlap_fraction_of_added_copper':unique_overlap/addition_union.area if addition_union.area else 0.0,
      'side_by_side_centerline_checks':side_centerline_checks,
      'side_by_side_required_gap_mm':policy['construction_gap_mm'],
      'trace_changed_in_t02':False,
      'limitations':['Uses the same native-inventory parser and Shapely geometry library as construction; this is not an independent parser/kernel audit.','Confirms records correspond to saved geometry; it does not judge whether measured overlaps qualify as slight or approve any future trace change.','Native source graphics do not establish net continuity or electrical intent.']
    }
    output.mkdir(parents=True,exist_ok=False)
    report['audit_sha256']=None
    data=(json.dumps(report,indent=2,sort_keys=True)+'\n').encode()
    (output/'future_trace_overlap_audit.json').write_bytes(data)
    report['audit_sha256']=sha(data)
    (output/'audit_summary.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    (output/'SHA256SUMS.txt').write_text(''.join(f'{sha(p.read_bytes())}  {p.name}\n' for p in sorted(output.iterdir()) if p.is_file() and p.name!='SHA256SUMS.txt'))
    print(json.dumps(report,indent=2))

if __name__=='__main__':
    main()
