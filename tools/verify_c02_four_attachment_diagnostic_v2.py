#!/usr/bin/env python3
"""Fresh diagnostic replay; geometry and non-port-area receipt values stay exact."""
import sys
sys.dont_write_bytecode=True
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import copy,hashlib,json
from shapely import to_wkb
from tools.run_c02_four_attachment_diagnostic_v2 import compute
from src.crop_replay_comparison import compare_final_scene_checks


def main():
    pre,packet,out=map(Path,sys.argv[1:])
    assert not out.exists();out.mkdir(parents=True)
    expected={'src/crop_stage_growth.py':'f416d87ace52e3d21857032bc02e5fcf34442d1bbcf7c7e0033a14ae4fba9529',
              'src/crop_attachment_support.py':'740d1886eb17aa3f58f26c54719bcb16e3e0daef53dee0ed7a0997eaed8436d2',
              'tools/run_c02_r080_attachment_revision.py':'28963ee1ff22458314f2bfadf3051365223388df8ecb00c85479739f6f5b507f'}
    for name,digest in expected.items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,name
    from src.crop_circle_sources import verify_assets
    integrity=verify_assets()
    report,g=compute(pre)
    bindings=g['source_binding_evidence']
    assert len(bindings)==9
    assert all(row['geometry_authority']=='EXACT_REV05_CACHED_WKB_ONLY' for row in bindings)
    assert sum(row['source_id'].endswith((':1651778:1651902', ':1652641:1652766')) for row in bindings)==2
    (out/'SOURCE_BINDING_EVIDENCE.json').write_text(json.dumps(bindings,indent=2,sort_keys=True)+'\n')
    saved=json.loads((packet/'result.json').read_text());saved.pop('asset_integrity')
    saved_checks=[];actual_checks=[]
    for sr,ar in zip(saved['sites'],report['sites'],strict=True):
        for sp,ap in zip(sr['probes'],ar['probes'],strict=True):
            for key in ('saved_REV05_check','current_full_context_ordinary_check','diagnostic_check'):
                saved_checks.append(dict(check=sp.pop(key)));actual_checks.append(dict(check=ap.pop(key)))
    assert saved==report,'NON_CHECK_REPORT_VALUES_MUST_MATCH_EXACTLY'
    comparisons={'probe_checks':compare_final_scene_checks(saved_checks,actual_checks),
                 'final_scene':compare_final_scene_checks(json.loads((packet/'final_scene_checks.json').read_text()),g['final'])}
    for key,comparison in comparisons.items():
        (out/f'{key}_comparison.json').write_text(json.dumps(comparison,indent=2,sort_keys=True)+'\n')
        assert comparison['passed'],(key,comparison['rejected_differences'])
    wkb_count=0
    from src.crop_stage_growth import GrowthContract,original_attachment_port
    from shapely import from_wkb
    for name in ('before','after','exposed'):
        assert to_wkb(g[name])==(packet/f'geometry/{name}.wkb').read_bytes(),name
        wkb_count+=1
    for site in json.loads((packet/'result.json').read_text())['sites']:
        key,sid=site['site'],site['source_id'];b=g['bindings'][sid];core=g['scene'].objects[sid]['geometry']
        port=original_attachment_port(core,from_wkb(b.obstacle_wkb) if b.feed_id is None else from_wkb(b.feed_wkb),b.width_mm,GrowthContract())
        assert to_wkb(g['proposals'][sid])==(packet/f'geometry/{key}_proposal.wkb').read_bytes(),key
        assert to_wkb(port)==(packet/f'geometry/{key}_port.wkb').read_bytes(),key
        wkb_count+=2
    receipt=dict(status='PASS_VERSIONED_FIXED_DIAGNOSTIC_REPLAY_PENDING_ACCEPTANCE',binding_contract='c02-pinned-circle-binding/1',asset_integrity=integrity,checks=75,wkb_payloads_exact=wkb_count,
                 unchanged_production_module_hashes=expected,comparison=comparisons,
                 geometry_status='Four proposed witnesses only; 70 remain accepted, T02 NOT_FROZEN')
    (out/'REPLAY_RECEIPT.json').write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
    print(json.dumps({k:v for k,v in receipt.items() if k!='comparison'}))


if __name__=='__main__':main()
