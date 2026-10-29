#!/usr/bin/env python3
"""Freeze the owner-accepted C02 post-T02 T05 result with all local evidence."""
from pathlib import Path
import json,hashlib,shutil,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.crop_circle_sources import verify_assets
B=ROOT/'out/crop_dynamic_tasks';F=B/'c02_latest_pre_T05_freeze_20261030_262';P=B/'c02_t05_after_T02_20261030_263';R=B/'c02_t05_replay_20261030_264';V=B/'c02_t05_owner_review_20261030_265';O=B/'c02_final_so_far_freeze_20261030_266'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
def main():
 if O.exists():raise ValueError('FRESH_FREEZE_REQUIRED')
 assets=verify_assets();result=read(P/'RESULT.json');replay=read(R/'REPLAY.json');assert sha(P/'after.wkb')==result['after_sha256']==replay['after_sha256'];assert sha(P/'RESULT.json')==replay['proposal_result_sha256'];assert sha(F/'before_T05.wkb')==result['predecessor_sha256'];assert replay['patches_exactly_reconstructed']==result['grown_routes']==56
 for folder in [F,P,R,V]:
  for name,h in read(folder/'DELIVERY_SHA256SUMS.json').items():assert sha(folder/name)==h,(folder,name)
 for row in read(V/'IMAGE_BINDINGS.json'):assert sha(V/row['file'])==row['sha256']
 O.mkdir();(O/'frozen').mkdir()
 for folder in [F,P,R,V]:shutil.copytree(folder,O/'frozen'/folder.name)
 c01=B/'c01_final_so_far_freeze_20261030_261';c01target=O/'frozen'/c01.name;c01target.mkdir();shutil.copyfile(c01/'FREEZE_RECEIPT.json',c01target/'FREEZE_RECEIPT.json')
 manifest={str(p.relative_to(O/'frozen')):sha(p) for p in (O/'frozen').rglob('*') if p.is_file()};(O/'SHA256SUMS.json').write_text(json.dumps(manifest,indent=2)+'\n')
 receipt=dict(status='FROZEN_C02_FINAL_SO_FAR_OWNER_ACCEPTED',authority='Owner: Looks good. Plz freeze this as the final C02 result so far, and commit & push the latest implementation and results.',source_result=str(P.relative_to(ROOT)),accepted_review=str(V.relative_to(ROOT)),sequence=['T01','T03_NO_ROUTE_CHANGE','T04','T02','T05'],source_sha256=result['source_sha256'],predecessor_sha256=result['predecessor_sha256'],after_sha256=result['after_sha256'],geometry_path=f'frozen/{P.name}/after.wkb',review_path=f'frozen/{V.name}/index.html',manifest_sha256=sha(O/'SHA256SUMS.json'),frozen_files=len(manifest),asset_integrity=assets,owner_visual_acceptance='PASSED',grown_routes=56,land_contact_incidences=88,rectangle_contact_incidences=65,keep_routes=57,unchanged_parts=606,exact_local_constructor_replay=replay['status'],minimum_checked_added_foreign_gap_mm=replay['minimum_added_foreign_surface_gap_mm'],known_limits='57 unchanged routes retained:51 no exposed qualified contact,5 no new copper,1 invalid/disconnected candidate rejected.16 fixed bulk contributors retain standing skip.',independent_qualification='INHERITED_REV234_REVISE_STRICT_EXACT_REPLAY_NOT_CLOSED; no new independent T05 qualification',native_electrical_manufacturing='NOT_ESTABLISHED',C01='ACCEPTED_FROZEN261_T02_SKIPPED',C03='STOPPED')
 (O/'FREEZE_RECEIPT.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
 H=ROOT/'out/visualization_results'
 for name in ['C02_CURRENT_STATE.json','CURRENT_RESUME.json']:
  p=H/name;(H/(p.stem+'_BEFORE_OWNER_FREEZE266.json')).write_bytes(p.read_bytes());d=read(p);d.update(status=receipt['status'],owner_T05_acceptance='PASSED',latest_frozen_result=str(O/'FREEZE_RECEIPT.json'),review=str(O/receipt['review_path']),after_sha256=receipt['after_sha256'],next='C01 and C02 final results so far frozen with owner acceptance; independent audit limitations retained');p.write_text(json.dumps(d,indent=2)+'\n')
 p=H/'index.html';(H/'index_before_C02_OWNER_FREEZE266.html').write_bytes(p.read_bytes());p.write_text('<!doctype html><meta charset="utf-8"><title>C01 and C02 accepted results</title><style>body{font:18px system-ui;max-width:1600px;margin:30px auto;line-height:1.5}img{width:100%}</style><h1>C02 · owner-accepted final result so far</h1><p>Frozen sequence: T01 → T03(no route change) → T04 → T02 → T05.56 route blends;88 land-contact incidences including65 rectangle incidences. Local exact replay passes. Existing independent audit limitations remain open.</p><p><a href="../crop_dynamic_tasks/'+O.name+'/'+receipt['review_path']+'">Frozen C02 before/after and junction details</a> · <a href="../crop_dynamic_tasks/'+c01.name+'/frozen/index.html">Frozen accepted C01 result</a></p><img src="../crop_dynamic_tasks/'+O.name+'/frozen/'+V.name+'/after.png"><p><a href="index_before_C02_OWNER_FREEZE266.html">Preserved pre-acceptance history</a></p>')
if __name__=='__main__':main()
