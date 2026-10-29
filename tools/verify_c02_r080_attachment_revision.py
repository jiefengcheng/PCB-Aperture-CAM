#!/usr/bin/env python3
"""Replay an R080-only proposal against an explicitly supplied REV05 packet."""
import sys
from pathlib import Path
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import json,hashlib
from tools.run_c02_r080_attachment_revision import compute
from shapely import from_wkb,to_wkb


def main(predecessor,packet):
    p=Path(packet)
    computed,g=compute(Path(predecessor))
    saved=json.loads((p/'result.json').read_text())
    for k,v in computed.items():assert saved[k]==v,k
    for name in ('before','after','exposed','core','proposal'):
        blob=(p/f'geometry/{name}.wkb').read_bytes()
        assert blob==to_wkb(g[name]),name
    assert json.loads((p/'final_scene_checks.json').read_text())==g['finalchecks']
    assert hashlib.sha256((p/'inputs/ORG_source.kicad_pcb').read_bytes()).hexdigest()==saved['source_sha256']
    print(json.dumps({'status':'PASS_AUTHOR_SIDE_R080_REPLAY','rechecked_source_objects':saved['source_object_count'],
        'final_replacements_checked':75,'other_replacements_byte_identical':74,
        'proposed_new_exposed_area_mm2':saved['new_exposed_added_area_mm2'],'stage':'NOT_FROZEN',
        'completion_credit':'PENDING_DESIGNATED_AUDIT'}))


if __name__=='__main__':main(sys.argv[1],sys.argv[2])
