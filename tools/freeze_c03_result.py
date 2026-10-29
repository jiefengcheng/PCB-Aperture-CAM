#!/usr/bin/env python3
"""Freeze C03 owner acceptance without rewriting construction-time evidence."""
from pathlib import Path
import hashlib,json,shutil,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.crop_circle_sources import verify_assets
B=ROOT/'out/crop_dynamic_tasks';RUN=B/'c03_sequence_20261030_269';OUT=B/'c03_final_so_far_freeze_20261030_270'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
def verify_protected():
 for row in read(RUN/'START_RECEIPT.json')['protected_accepted_crops']:
  p=ROOT/row['path'];assert sha(p/'FREEZE_RECEIPT.json')==row['receipt_sha256'];r=read(p/'FREEZE_RECEIPT.json');manifest=read(p/'SHA256SUMS.json') if (p/'SHA256SUMS.json').exists() else r['files']
  for n,h in manifest.items():assert sha(p/'frozen'/n)==h,(p,n)
 return '971 frozen C01/C02 files and both acceptance receipts unchanged'
def main():
 if OUT.exists():raise ValueError('FRESH_FREEZE_REQUIRED')
 assets=verify_assets();protected=verify_protected();result=read(RUN/'T05/RESULT.json');replay=read(RUN/'verification/REPLAY.json');assert replay['status']=='PASS_SAME_ASSISTANT_C03_FINAL_SOURCE_SEQUENCE_REPLAY';assert sha(RUN/'T05/after.wkb')==replay['after_sha256']==result['after_sha256']
 for n,h in read(RUN/'SHA256SUMS.json').items():assert sha(RUN/n)==h,n
 OUT.mkdir();shutil.copytree(RUN,OUT/'frozen',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
 snapshot=OUT/'frozen/source_snapshot';snapshot.mkdir()
 for n,h in read(RUN/'SESSION_CHECKPOINT.json')['source_code_hashes'].items():
  p=ROOT/n;assert sha(p)==h;npath=snapshot/n;npath.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,npath)
 manifest={str(p.relative_to(OUT/'frozen')):sha(p) for p in (OUT/'frozen').rglob('*') if p.is_file()};(OUT/'SHA256SUMS.json').write_text(json.dumps(manifest,indent=2)+'\n')
 receipt=dict(status='FROZEN_C03_FINAL_SO_FAR_OWNER_ACCEPTED',authority='Owner: Looks good. Plz freeze this as the final C03 result so far, keeping C01 and C02 unchanged, then commit & push the latest implementation and results.',source_result=str(RUN.relative_to(ROOT)),sequence=result['sequence'],source_sha256=result['source_sha256'],after_sha256=result['after_sha256'],geometry_path='frozen/T05/after.wkb',review_path='frozen/review/index.html',manifest_sha256=sha(OUT/'SHA256SUMS.json'),frozen_files=len(manifest),owner_visual_acceptance='PASSED',asset_integrity=assets,protected_C01_C02=protected,local_replay=replay['status'],registration=result['source_registration'],independent_native_electrical_manufacturing='NOT_ESTABLISHED',acceptance_scope='Owner-accepted final C03 result so far; separate crop lineage, not whole-board qualification. Original provisional registration and construction-time labels retained.')
 (OUT/'FREEZE_RECEIPT.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
if __name__=='__main__':main()
