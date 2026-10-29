#!/usr/bin/env python3
"""Two fixed native-join-first constructions; unchanged 45 source parts."""
import sys,json,hashlib
from pathlib import Path
from shapely import from_wkb,to_wkb
from shapely.ops import unary_union


def sha(b):return hashlib.sha256(b).hexdigest()


def main():
    proposal,out=map(Path,sys.argv[1:]);assert not out.exists()
    r=next(r for r in json.loads((proposal/'CONSTRUCTION.json').read_text()) if r['component_id']=='JR-e705e7bd6dea8c02')
    assert r['factor']==1.5 and len(r['primitives'])==45
    ids=r['complete_source_ids'];meta={p['source_id']:p for p in r['primitives']};parts=[]
    for sid in ids:
        blob=(proposal/'nominal_source_parts'/f'{sha(sid.encode())}.wkb').read_bytes()
        assert sha(blob)==meta[sid]['nominal_candidate_wkb_sha256'];parts.append(from_wkb(blob))
    def index(suffix):return next(i for i,sid in enumerate(ids) if sid.endswith(suffix))
    cases=[('segment_previous_arc_front',index(':410281:410369'),index(':484605:484724')),
           ('arc_next_arc_front',index(':485094:485214'),index(':484971:485091'))]
    out.mkdir();results=[]
    for name,a,b in cases:
        ends=lambda i:{tuple(meta[ids[i]][k]) for k in ['start_mm','end_mm']}
        assert ends(a)&ends(b)
        joined=parts[a].union(parts[b])
        result=unary_union([joined,*[g for i,g in enumerate(parts) if i not in (a,b)]])
        blob=to_wkb(result);h=sha(blob);(out/f'{name}.wkb').write_bytes(blob)
        results.append(dict(strategy=name,preunion_source_ids=[ids[a],ids[b]],sha256=h,exact_sealed_hash=h==r['nominal_copper_wkb_sha256']))
    (out/'PROBE.json').write_text(json.dumps(dict(scope='Exactly two fixed constructions: merged native pair FIRST, remaining source order unchanged; no cache input/vertex/precision edits',results=results),indent=2)+'\n')
    print(json.dumps(results))


if __name__=='__main__':main()
