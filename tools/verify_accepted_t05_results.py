#!/usr/bin/env python3
"""Verify a checked-in accepted T05 result delivery, not omitted source inputs."""
from pathlib import Path
import sys,argparse,json,hashlib,re
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from shapely import from_wkb
from src.junction_spindle_blend import check_spindle

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
def main(package):
 manifest=read(package/'SHA256SUMS.json');actual={str(p.relative_to(package)) for p in package.rglob('*') if p.is_file() and p!=package/'SHA256SUMS.json'}
 assert actual==set(manifest),'DELIVERY_MEMBERSHIP_MISMATCH'
 for name,h in manifest.items():assert sha(package/name)==h,name
 c1=package/'c01_final_so_far_freeze_20261030_261';r1=read(c1/'FREEZE_RECEIPT.json');assert r1['status']=='FROZEN_C01_FINAL_SO_FAR_OWNER_ACCEPTED' and r1['T02']=='SKIPPED_BY_OWNER_FOR_C01'
 for name,h in r1['files'].items():assert sha(c1/'frozen'/name)==h,name
 assert sha(c1/'frozen/after.wkb')==r1['after_sha256']
 p=package/'c02_t05_after_T02_20261030_263';replay=read(package/'c02_t05_replay_20261030_264/REPLAY.json');r2=read(package/'c02_final_so_far_freeze_20261030_266/FREEZE_RECEIPT.json');result=read(p/'RESULT.json');assert r2['owner_visual_acceptance']=='PASSED' and r2['status']=='FROZEN_C02_FINAL_SO_FAR_OWNER_ACCEPTED'
 assert sha(p/'after.wkb')==r2['after_sha256']==result['after_sha256']==replay['after_sha256'];assert sha(p/'before.wkb')==r2['predecessor_sha256']==result['predecessor_sha256'];assert sha(p/'RESULT.json')==replay['proposal_result_sha256']
 before,after,added=[from_wkb((p/(name+'.wkb')).read_bytes()) for name in ['before','after','added']]
 assert after.is_valid and before.difference(after).area<=1e-12 and after.symmetric_difference(before.union(added)).area<=1e-12
 grown=[r for r in read(p/'DECISIONS.json') if r['status']=='GROWN'];assert len(grown)==r2['grown_routes']==replay['patches_exactly_reconstructed']==56
 for r in grown:
  cid=r['id'];geoms={}
  for key,suffix in [('addition',''),('owner','_owner'),('window','_window')]:
   file=p/'patches'/f'{cid}{suffix}.wkb';assert sha(file)==r[key+'_sha256'];geoms[key]=from_wkb(file.read_bytes())
  check=check_spindle(geoms['owner'],geoms['owner'].union(geoms['addition']),geoms['addition'],geoms['window'],[]);assert check['passed'],(cid,check['failures'])
 # Presentation links only: historic executable source and custody manifests
 # may refer to the deliberately omitted original input cache.
 links=0
 for page in package.rglob('*.html'):
  for link in re.findall(r'(?:src|href)="([^"]+)"',page.read_text()):
   if link.startswith(('http:','https:','#','mailto:','data:')):continue
   assert (page.parent/link.split('#')[0]).exists(),(str(page),link);links+=1
 print(json.dumps(dict(status='PASS_CHECKED_IN_T05_DELIVERY_INTEGRITY_AND_ADDITIVE_GEOMETRY',files=len(manifest),local_links=links,C01_owner_acceptance=r1['status'],C02_owner_acceptance=r2['status'],C02_saved_patches_checked=len(grown),scope='Package integrity and saved additive geometry only; original-source constructor replay is recorded separately, not rerun; inherited independent REVISE remains open')))
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('package',type=Path);main(**vars(p.parse_args()))
