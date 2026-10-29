#!/usr/bin/env python3
"""Pin the latest owner-accepted C02 result232 and reconstruct its source operands.

Strict independent replay REVISE remains open; no construction is rerun.
"""
from pathlib import Path
import sys,json,hashlib,shutil
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from shapely import from_wkb,to_wkb,STRtree
from shapely.geometry import box
from shapely.ops import unary_union
from src.crop_circle_sources import verify_assets
B=ROOT/'out/crop_dynamic_tasks';F=B/'c02_t01_t02_geometric_freeze_20261029_32';P=B/'c02_context_rectangle_completion_20261029_232';W=B/'c02_upper_bundle_width_20261029_222';T=B/'c02_t02_revised_trace_stage_20261029_226';M=B/'c02_inclusive_rectangle_20pct_20261029_229';CACHE=B/'c02_focused_growth_coverage_20261028_05/inputs';O=B/'c02_latest_pre_T05_freeze_20261030_262'
def sha(b):return hashlib.sha256(b).hexdigest()
def read(p):return json.loads(p.read_text())
def save(p,d):p.write_text(json.dumps(d,indent=2)+'\n')
def main():
 if O.exists():raise ValueError('FRESH_FREEZE_REQUIRED')
 assets=verify_assets();f=read(F/'FREEZE_RECEIPT.json');bank=read(CACHE/'source_manifest.json');original={};bindings=[]
 assert f['source_sha256']==bank['source_sha256']
 for row in bank['objects']:
  blob=(CACHE/'source_wkb'/f"{row['geometry_sha256']}.wkb").read_bytes();assert sha(blob)==row['geometry_sha256'];original[row['id']]=from_wkb(blob)
 current=dict(original);replacements={}
 for row in read(F/'REPLACEMENT_MANIFEST.json'):
  if row['kind']!='CIRCLE':continue
  blob=(F/row['path']).read_bytes();assert sha(blob)==row['sha256'];d=read(B/'c02_focused_growth_coverage_20261028_05/t01/decision.json')
  for sid in d['aliases']:current[sid]=from_wkb(blob);replacements[sid]=blob
 for row in read(W/'CONSTRUCTION.json'):
  for part in row['primitives']:
   sid=part['source_id'];blob=(W/'nominal_source_parts'/f'{sha(sid.encode())}.wkb').read_bytes();assert sha(blob)==part['nominal_candidate_wkb_sha256'];current[sid]=from_wkb(blob);replacements[sid]=blob
 for row in read(T/'DECISIONS.json'):
  sid=row['source_id'];blob=(T/'rectangle_parts'/f'{sha(sid.encode())}.wkb').read_bytes();assert sha(blob)==row['geometry_sha256'];current[sid]=from_wkb(blob);replacements[sid]=blob
 crop=box(*f['viewport_mm']);ids=sorted(current);tree=STRtree([current[s] for s in ids]);ordinary=unary_union([current[ids[int(i)]] for i in tree.query(crop,predicate='intersects')]).intersection(crop)
 assert to_wkb(ordinary)==(T/'after_T02.wkb').read_bytes(),'ORDINARY_ASSEMBLY_NOT_EXACT'
 merged=ordinary;merges=[]
 for row in read(M/'CANDIDATES.json'):
  if row['status']!='MERGED':continue
  blob=(M/f"{row['candidate']}_inclusive.wkb").read_bytes();assert sha(blob)==row['inclusive_wkb_sha256'];g=from_wkb(blob);merged=merged.union(g);merges.append(dict(row,geometry_sha256=sha(blob)))
 assert to_wkb(merged)==(M/'after.wkb').read_bytes(),'MERGED_ASSEMBLY_NOT_EXACT'
 additions=[]
 for row in read(P/'DECISIONS.json'):
  if 'axis_factors' not in row:continue
  sid=row['source_id'];blob=(P/'parts'/f'{sha(sid.encode())}.wkb').read_bytes();g=from_wkb(blob);additions.append(g.difference(original[sid]));current[sid]=g;replacements[sid]=blob
 after=merged.union(unary_union(additions));r=read(P/'RESULT.json');assert sha(to_wkb(after))==r['after_sha256']==sha((P/'after.wkb').read_bytes()),'FINAL232_ASSEMBLY_NOT_EXACT'
 O.mkdir();(O/'parts').mkdir();(O/'merges').mkdir();shutil.copyfile(P/'after.wkb',O/'before_T05.wkb');shutil.copyfile(CACHE/'source_manifest.json',O/'source_manifest.json')
 for sid,blob in replacements.items():
  name=f'parts/{sha(sid.encode())}.wkb';(O/name).write_bytes(blob);bindings.append(dict(source_id=sid,path=name,sha256=sha(blob)))
 for row in merges:shutil.copyfile(M/f"{row['candidate']}_inclusive.wkb",O/'merges'/f"{row['candidate']}.wkb")
 for name,path in [('T04_CONSTRUCTION.json',W/'CONSTRUCTION.json'),('T04_PATHS.json',B/'c02_trace_first_setup_20261029_214/definitions/UNIFORM_SOURCE_PATHS.json'),('SOURCE_RESULT232.json',P/'RESULT.json'),('INDEPENDENT_REV234_RECEIPT.json',ROOT/'docs/implementation/20261029/audit/REV234_INDEPENDENT_BATCH_AUDIT_RECEIPT.json')]:shutil.copyfile(path,O/name)
 assert sha((O/'T04_PATHS.json').read_bytes())==read(W/'RESULT.json')['definition_sha256']
 save(O/'REPLACEMENTS.json',bindings);save(O/'INCLUSIVE_MERGES.json',merges)
 manifest={str(p.relative_to(O)):sha(p.read_bytes()) for p in O.rglob('*') if p.is_file()};save(O/'SHA256SUMS.json',manifest)
 receipt=dict(status='FROZEN_LATEST_OWNER_ACCEPTED_C02_PRE_T05',authority='Owner requests T05 after T02 based on latest available frozen C02 result',source_result=str(P.relative_to(ROOT)),source_sha256=f['source_sha256'],after_sha256=r['after_sha256'],viewport_mm=f['viewport_mm'],sequence=['T01','T03_NO_ROUTE_CHANGE','T04','T02','T05_NEXT'],exact_local_saved_source_assembly='PASS_226_229_232',source_replacements=len(bindings),T04_routes=len(read(W/'CONSTRUCTION.json')),inclusive_merges=len(merges),assets=assets,manifest_sha256=sha((O/'SHA256SUMS.json').read_bytes()),independent_qualification='REV234_REVISE_STRICT_EXACT_REPLAY_NOT_CLOSED; preserved, not waived',owner_predecessor_visual_acceptance='PASSED_AS_RECORDED_FOR_RESULT232',geometry_export_electrical_manufacturing='NOT_ESTABLISHED')
 save(O/'FREEZE_RECEIPT.json',receipt);print(json.dumps(receipt))
if __name__=='__main__':main()
