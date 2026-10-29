from pathlib import Path
import sys,json,hashlib
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
from shapely import from_wkb,to_wkb,STRtree
from shapely.geometry import box
from shapely.ops import unary_union
from src.junction_spindle_blend import check_spindle
B=ROOT/'out/crop_dynamic_tasks';P=Path(__file__).parent;F=B/'c01_existing_t01_freeze_20261029_239';W=B/'c01_t04_width_proposal_20261029_250';CACHE=B/'c02_focused_growth_coverage_20261028_05/inputs'
def sha(b):return hashlib.sha256(b).hexdigest()
def read(p):return json.loads(p.read_text())
f=read(F/'FREEZE_RECEIPT.json');result=read(P/'RESULT.json');current={}
for name,h in f['file_bindings'].items():assert sha((F/'frozen'/name).read_bytes())==h
for row in read(CACHE/'source_manifest.json')['objects']:
 b=(CACHE/'source_wkb'/f"{row['geometry_sha256']}.wkb").read_bytes();assert sha(b)==row['geometry_sha256'];current[row['id']]=from_wkb(b)
lands={}
for d in read(F/'frozen/report.json')['decisions']:
 b=(F/'frozen'/d['geometry']['dynamic']).read_bytes();assert sha(b)==d['candidate_sha256'];g=from_wkb(b);lands[d['source_id']]=(g,d['aliases'])
 for sid in d['aliases']:current[sid]=g
parts=0
for r in read(W/'CONSTRUCTION.json'):
 for part in r['primitives']:
  sid=part['source_id'];b=(W/'nominal_source_parts'/f'{sha(sid.encode())}.wkb').read_bytes();assert sha(b)==part['nominal_candidate_wkb_sha256'];current[sid]=from_wkb(b);parts+=1
ids=sorted(current);tree=STRtree([current[s] for s in ids]);rows=[r for r in read(P/'DECISIONS.json') if r['status']=='GROWN'];patches={}
for r in rows:
 cid=r['id'];addition=(P/'patches'/f'{cid}.wkb').read_bytes();assert sha(addition)==r['addition_sha256'];patches[cid]=from_wkb(addition)
checks=[]
for r in rows:
 cid=r['id'];trace=unary_union([current[s] for s in r['source_ids']]);owner=unary_union([trace]+[lands[s][0] for s in r['land_ids']]);assert to_wkb(owner)==(P/'patches'/f'{cid}_owner.wkb').read_bytes()
 window_blob=(P/'patches'/f'{cid}_window.wkb').read_bytes();assert sha(window_blob)==r['window_sha256'];window=from_wkb(window_blob);allowed=set(r['source_ids'])|{s for lid in r['land_ids'] for s in lands[lid][1]}
 foreign=[(ids[int(i)],current[ids[int(i)]]) for i in tree.query(window.buffer(.02011)) if ids[int(i)] not in allowed]+[(k,g) for k,g in patches.items() if k!=cid]
 check=check_spindle(owner,owner.union(patches[cid]),patches[cid],window,foreign);assert check['passed'],(cid,check['failures']);checks.append(dict(id=cid,check=check))
before=(W/'after.wkb').read_bytes();assert sha(before)==result['predecessor_sha256'];after=from_wkb(before).union(unary_union(list(patches.values())));assert sha(to_wkb(after))==result['after_sha256']==sha((P/'after.wkb').read_bytes())
gaps=[x['gap_mm'] for c in checks for x in c['check']['pairs'] if x.get('gap_mm') is not None]
receipt=dict(status='PASS_SAME_ASSISTANT_SAVED_TRIAL_RECHECK',patches=len(checks),frozen_T01_files=len(f['file_bindings']),unchanged_T04_parts=parts,minimum_checked_added_foreign_gap_mm=min(gaps),after_sha256=result['after_sha256'],scope='Exact source-owner and cumulative-assembly replay; saved patch/window hash checks; full-neighborhood final clearance recheck. Not constructor replay, independent review or final T05 acceptance.')
(P/'SAVED_TRIAL_RECHECK.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
