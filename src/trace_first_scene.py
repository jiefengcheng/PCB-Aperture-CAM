"""Prepared native-region source scene; crop identities and cache are explicit inputs."""
from pathlib import Path
import json,hashlib
from shapely import from_wkb,to_wkb
def sha(blob):return hashlib.sha256(blob).hexdigest()
def read(path):return json.loads(path.read_text())
def save(path,data):path.write_text(json.dumps(data,indent=2)+'\n')
def load_scene(run,through='T04',*,cache):
 run=Path(run);CACHE=Path(cache)
 if through not in ('T01','T04','T02'):raise ValueError('SUPPORTED_NATIVE_REGION_STAGE_REQUIRED')
 scope=read(run/'T01/SUPPORTED_TARGETS.json');r1=read(run/'T01/RESULT.json');assert sha((run/'T01/after.wkb').read_bytes())==r1['after_sha256'];assert sha((run/'T01/SUPPORTED_TARGETS.json').read_bytes())==r1['scope_sha256'];raw=(CACHE/'ORG_source.kicad_pcb').read_bytes();assert sha(raw)==scope['source_sha256']==r1['source_sha256'];binding=read(run/'SOURCE_BINDINGS.json');assert binding['source_sha256']==scope['source_sha256'];assert binding['scope_sha256']==sha((run/'T01/SUPPORTED_TARGETS.json').read_bytes());assert binding['source_manifest_sha256']==sha((CACHE/'source_manifest.json').read_bytes());bank=read(CACHE/'source_manifest.json');assert bank['source_sha256']==scope['source_sha256'];meta={r['id']:r for r in bank['objects']};original={}
 for sid,r in meta.items():
  blob=(CACHE/'source_wkb'/f"{r['geometry_sha256']}.wkb").read_bytes();assert sha(blob)==r['geometry_sha256'];original[sid]=from_wkb(blob)
 current=dict(original);replacements={}
 for r in read(run/'T01/DECISIONS.json'):
  blob=(run/'T01/candidates'/f"{r['key']}.wkb").read_bytes();assert sha(blob)==r['candidate_sha256']
  for sid in r['aliases']:current[sid]=from_wkb(blob);replacements[sid]=blob
 routes=[]
 if through in ('T04','T02'):
  width=read(run/'T04/RESULT.json');assert width['source_sha256']==scope['source_sha256'] and width['land_predecessor_sha256']==r1['after_sha256'];assert sha((run/'T04/after.wkb').read_bytes())==width['after_sha256'];routes=read(run/'T04/CONSTRUCTION.json')
  for route in routes:
   for r in route['primitives']:
    sid=r['source_id'];blob=(run/'T04/nominal_source_parts'/f'{sha(sid.encode())}.wkb').read_bytes();assert sha(blob)==r['nominal_candidate_wkb_sha256'];current[sid]=from_wkb(blob);replacements[sid]=blob
 if through=='T02':
  rect=read(run/'T02/RESULT.json');assert rect['predecessor_sha256']==sha((run/'T04/after.wkb').read_bytes());assert rect['after_sha256']==sha((run/'T02/after.wkb').read_bytes())
  for r in read(run/'T02/DECISIONS.json'):
   blob=(run/'T02/rectangle_parts'/f"{r['key']}.wkb").read_bytes();assert sha(blob)==r['candidate_sha256']
   for sid in r['aliases']:current[sid]=from_wkb(blob);replacements[sid]=blob
  for r in read(run/'T02/INCLUSIVE_CANDIDATES.json'):
   if r['status']!='MERGED':continue
   blob=(run/'T02/merges'/f"{r['candidate']}.wkb").read_bytes();assert sha(blob)==r['inclusive_wkb_sha256'];current['inclusive:'+r['candidate']]=from_wkb(blob)
 return scope,meta,original,current,replacements,routes
