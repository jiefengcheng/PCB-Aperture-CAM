#!/usr/bin/env python3
"""Record explicit owner acceptance without changing geometric qualification."""
from pathlib import Path
import json,hashlib,shutil,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.crop_circle_sources import verify_assets
B=ROOT/'out/crop_dynamic_tasks';P=B/'c01_t05_spindle_trial_20261030_260';O=B/'c01_final_so_far_freeze_20261030_261'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 if O.exists():raise ValueError('FRESH_FREEZE_REQUIRED')
 assets=verify_assets();r=json.loads((P/'RESULT.json').read_text());check=json.loads((P/'SAVED_TRIAL_RECHECK.json').read_text());assert sha(P/'after.wkb')==r['after_sha256']==check['after_sha256']
 for name,h in json.loads((P/'FILE_HASHES.json').read_text()).items():assert sha(P/name)==h
 O.mkdir();shutil.copytree(P,O/'frozen');files={str(p.relative_to(O/'frozen')):sha(p) for p in (O/'frozen').rglob('*') if p.is_file()}
 receipt=dict(status='FROZEN_C01_FINAL_SO_FAR_OWNER_ACCEPTED',authority='Owner: Awesome. Plz frozen this as final C01 result so far. No need for T02 since there is no rectangle in this image.',asset_integrity=assets,source_result=str(P.relative_to(ROOT)),after_sha256=r['after_sha256'],files=files,T02='SKIPPED_BY_OWNER_FOR_C01',T01='FROZEN_UNCHANGED',T04='SOURCE_PARTS_AND_ROUTES_UNCHANGED',T05='ACCEPTED_SPINDLE_RESULT260',unresolved_geometric_scope='Five branched/mixed components and one unaccepted contacted component retained as known limits; owner accepts displayed result as final so far',independent_qualification='OPEN_UNCHANGED',native_electrical_manufacturing='NOT_ESTABLISHED')
 (O/'FREEZE_RECEIPT.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps({k:v for k,v in receipt.items() if k!='files'}))
 H=ROOT/'out/visualization_results';p=H/'C01_CURRENT_STATE.json';d=json.loads(p.read_text());(H/'C01_STATE_BEFORE_OWNER_FREEZE261.json').write_bytes(p.read_bytes());d.update(status=receipt['status'],freeze_receipt=str(O/'FREEZE_RECEIPT.json'),review=str(O/'frozen/index.html'),T02=receipt['T02'],owner_acceptance='PASSED',next='C01 frozen; resume C02 T05 after T02');p.write_text(json.dumps(d,indent=2)+'\n')
if __name__=='__main__':main()
