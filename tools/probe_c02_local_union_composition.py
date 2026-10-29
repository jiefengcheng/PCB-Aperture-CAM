#!/usr/bin/env python3
"""Four fixed read-only union constructions around the diagnosed source join.

Uses all 45 unchanged parts, not cached union output. Two native-adjacent
preunions fix an explicit local operation order; the final union retains the
remaining original source order. Expected hashes are comparisons only.
"""
import sys,json,hashlib
from pathlib import Path
from shapely import from_wkb,to_wkb,get_num_coordinates
from shapely.ops import unary_union


def sha(b):return hashlib.sha256(b).hexdigest()


def main():
    proposal,out=map(Path,sys.argv[1:]);assert not out.exists()
    record=next(r for r in json.loads((proposal/'CONSTRUCTION.json').read_text()) if r['component_id']=='JR-e705e7bd6dea8c02')
    assert record['factor']==1.5 and len(record['primitives'])==45
    ids=record['complete_source_ids'];metadata={p['source_id']:p for p in record['primitives']};parts=[]
    for sid in ids:
        blob=(proposal/'nominal_source_parts'/f'{sha(sid.encode())}.wkb').read_bytes()
        assert sha(blob)==metadata[sid]['nominal_candidate_wkb_sha256'];parts.append(from_wkb(blob))
    def locate(suffix):return next(i for i,sid in enumerate(ids) if sid.endswith(suffix))
    a,b,c,d=map(locate,[':410281:410369',':485094:485214',':484605:484724',':484971:485091'])
    def endpoints(i):return {tuple(metadata[ids[i]][field]) for field in ['start_mm','end_mm']}
    assert endpoints(a)&endpoints(c) and endpoints(b)&endpoints(d)
    def composed(pair):
        merged=parts[pair[0]].union(parts[pair[1]])
        sequence=[]
        for i,p in enumerate(parts):
            if i==min(pair):sequence.append(merged)
            elif i not in pair:sequence.append(p)
        return unary_union(sequence)
    strategies=[('original_45_source_order',None),('diagnosed_overlap_pair_control',(a,b)),
        ('native_adjacent_segment_previous_arc',(a,c)),('native_adjacent_arc_next_arc',(b,d))]
    out.mkdir();rows=[]
    for name,pair in strategies:
        geometry=unary_union(parts) if pair is None else composed(pair);blob=to_wkb(geometry);h=sha(blob)
        (out/f'{name}.wkb').write_bytes(blob)
        rows.append(dict(strategy=name,preunion_source_ids=None if pair is None else [ids[i] for i in pair],sha256=h,
            exact_sealed_hash=h==record['nominal_copper_wkb_sha256'],coordinate_count=int(get_num_coordinates(geometry))))
    result=dict(role='READ_ONLY_CONSTRUCTION_PROBE_NO_POLICY_OR_GEOMETRY_ACCEPTANCE',source_order=ids,
        expected_sealed_sha256=record['nominal_copper_wkb_sha256'],source_parts_modified='NONE',output_vertices_edited='NONE',precision_change='NONE',results=rows)
    (out/'PROBE.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n');print(json.dumps(rows))


if __name__=='__main__':main()
