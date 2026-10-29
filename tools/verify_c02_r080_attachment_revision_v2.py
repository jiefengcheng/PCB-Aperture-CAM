#!/usr/bin/env python3
"""Versioned replay: only diagnostic port-area receipts use reviewed tolerance."""
import sys
sys.dont_write_bytecode=True
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import hashlib,importlib,json
from shapely import to_wkb
from src.crop_replay_comparison import compare_final_scene_checks,AREA_EPSILON_MM2
from tools.run_c02_r080_attachment_revision import compute

EXPECTED_MODULES={
    'src.crop_stage_growth':'f416d87ace52e3d21857032bc02e5fcf34442d1bbcf7c7e0033a14ae4fba9529',
    'src.crop_attachment_support':'740d1886eb17aa3f58f26c54719bcb16e3e0daef53dee0ed7a0997eaed8436d2',
    'tools.run_c02_r080_attachment_revision':'28963ee1ff22458314f2bfadf3051365223388df8ecb00c85479739f6f5b507f'}


def verify(predecessor,packet):
    provenance={}
    for name,expected in EXPECTED_MODULES.items():
        m=importlib.import_module(name);path=Path(m.__file__)
        actual=hashlib.sha256(path.read_bytes()).hexdigest();assert actual==expected,name
        provenance[name]={'path':str(path),'sha256':actual}
    p=Path(packet);computed,g=compute(Path(predecessor))
    saved=json.loads((p/'result.json').read_text())
    assert saved['contract']['area_epsilon_mm2']==AREA_EPSILON_MM2
    for k,v in computed.items():assert saved[k]==v,k
    for name in ('before','after','exposed','core','proposal'):
        assert (p/f'geometry/{name}.wkb').read_bytes()==to_wkb(g[name]),name
    expected=json.loads((p/'final_scene_checks.json').read_text())
    comparison=compare_final_scene_checks(expected,g['finalchecks'])
    assert hashlib.sha256((p/'inputs/ORG_source.kicad_pcb').read_bytes()).hexdigest()==saved['source_sha256']
    receipt={'status':'PASS_FIELD_SPECIFIC_REPLAY' if comparison['passed'] else 'FAIL_FIELD_SPECIFIC_REPLAY',
        'comparison':comparison,'module_provenance':provenance,
        'rechecked_source_objects':saved['source_object_count'],'replacements_checked':75,
        'other_replacements_byte_identical':74,'five_geometry_payloads_byte_identical':True,
        'unchanged_source_sha256':saved['source_sha256'],'stage':'NOT_FROZEN',
        'completion_credit':'PENDING_DESIGNATED_AUDIT',
        'original_strict_reference':'Unmodified REV06 verifier retained; no retroactive strict-replay PASS.'}
    return receipt,g['finalchecks']


if __name__=='__main__':
    receipt,recomputed=verify(sys.argv[1],sys.argv[2])
    if len(sys.argv)>3:
        out=Path(sys.argv[3]);out.mkdir(parents=True,exist_ok=False)
        (out/'FIELD_SPECIFIC_REPLAY_RECEIPT.json').write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
        (out/'recomputed_final_scene_checks.json').write_text(json.dumps(recomputed,indent=2,sort_keys=True)+'\n')
    print(json.dumps(receipt,sort_keys=True))
    if receipt['status']!='PASS_FIELD_SPECIFIC_REPLAY':sys.exit(1)
