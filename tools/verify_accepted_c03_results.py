#!/usr/bin/env python3
"""Verify delivered accepted C03 bytes and cumulative saved geometry, not native intent."""
from pathlib import Path
import sys,json,hashlib,re
from shapely import from_wkb

def main(root):
 sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
 read=lambda p:json.loads(p.read_text())
 manifest=read(root/'SHA256SUMS.json')
 for n,h in manifest.items():assert sha(root/n)==h,n
 receipt=read(root/'FREEZE_RECEIPT.json');assert receipt['status']=='FROZEN_C03_FINAL_SO_FAR_OWNER_ACCEPTED'
 assert sha(root/'result/T05/after.wkb')==receipt['after_sha256']==read(root/'result/verification/REPLAY.json')['after_sha256']
 previous=None
 for stage in ['T01','T04','T02','T05']:
  g=from_wkb((root/f'result/{stage}/after.wkb').read_bytes());assert g.is_valid
  if previous is not None:assert previous.difference(g).area<=1e-12
  previous=g
 links=0
 for p in root.rglob('*.html'):
  for url in re.findall(r'(?:src|href)=[\"\']([^\"\']+)',p.read_text()):
   if url.startswith(('data:','http:','https:','#')):continue
   assert (p.parent/url.split('#')[0]).exists(),(p,url);links+=1
 print(json.dumps(dict(status='PASS_ACCEPTED_C03_DELIVERY_INTEGRITY_AND_CUMULATIVE_GEOMETRY',files=len(manifest),links=links,after_sha256=receipt['after_sha256'],scope='Saved bytes and cumulative geometry; source replay recorded separately. No independent/native/electrical/manufacturing acceptance.')))
if __name__=='__main__':main(Path(sys.argv[1]))
