#!/usr/bin/env python3
"""C01 source-qualified spindle trial, preserved separately from first T05."""
from pathlib import Path
import sys,json,hashlib,subprocess,shutil
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from shapely import from_wkb,to_wkb,STRtree
from shapely.geometry import box,GeometryCollection
from shapely.ops import unary_union
from src.crop_circle_sources import verify_assets
from src.junction_spindle_stage import CONTRACT,prepare_spindle_context,fit_spindle_blend,verify_spindle_batch,assemble_spindle_scene
from tools.run_c02_growth_coverage import render
B=ROOT/'out/crop_dynamic_tasks';F=B/'c01_existing_t01_freeze_20261029_239';W=B/'c01_t04_width_proposal_20261029_250';CACHE=B/'c02_focused_growth_coverage_20261028_05/inputs';OUT=B/'c01_t05_spindle_trial_20261030_260'
def sha(b):return hashlib.sha256(b).hexdigest()
def read(p):return json.loads(p.read_text())
def save(p,d):p.write_text(json.dumps(d,indent=2)+'\n')
def main(out=OUT):
 global OUT
 OUT=Path(out)
 if not OUT.resolve().is_relative_to(ROOT/'out'):raise ValueError('PROJECT_LOCAL_OUTPUT_REQUIRED')
 if OUT.exists():raise ValueError('FRESH_OUTPUT_REQUIRED')
 assets=verify_assets();f=read(F/'FREEZE_RECEIPT.json');P=F/'frozen'
 for n,h in f['file_bindings'].items():assert sha((P/n).read_bytes())==h
 bank=read(CACHE/'source_manifest.json');assert bank['source_sha256']==f['source_sha256'];original={}
 for r in bank['objects']:
  blob=(CACHE/'source_wkb'/f"{r['geometry_sha256']}.wkb").read_bytes();assert sha(blob)==r['geometry_sha256'];original[r['id']]=from_wkb(blob)
 current=dict(original);lands=[]
 for d in read(P/'report.json')['decisions']:
  blob=(P/d['geometry']['dynamic']).read_bytes();assert sha(blob)==d['candidate_sha256'];g=from_wkb(blob)
  for sid in d['aliases']:current[sid]=g
  lands.append(dict(id=d['source_id'],aliases=d['aliases'],label=d['key'],geometry=g))
 for route in read(W/'CONSTRUCTION.json'):
  for part in route['primitives']:
   sid=part['source_id'];blob=(W/'nominal_source_parts'/f'{sha(sid.encode())}.wkb').read_bytes();assert sha(blob)==part['nominal_candidate_wkb_sha256'];current[sid]=from_wkb(blob)
 before_blob=(W/'after.wkb').read_bytes();assert sha(before_blob)==read(W/'RESULT.json')['after_sha256'];before=from_wkb(before_blob);crop=box(*f['viewport_mm']);ids=sorted(current);tree=STRtree([current[s] for s in ids]);components=read(B/'c01_t03_source_intake_20261029_240/TRACE_ENDPOINT_COMPONENTS.json');accepted=[];decisions=[];OUT.mkdir();(OUT/'patches').mkdir()
 for ci,comp in enumerate(components):
  row=dict(component_index=ci,source_ids=comp['source_ids'],status='KEEP');sids=comp['source_ids']
  if comp['unresolved_reasons']:
   row.update(reason='BRANCHED_OR_MIXED_COMPONENT_REQUIRES_LOCAL_SPLIT',details=comp['unresolved_reasons']);decisions.append(row);continue
  trace=unary_union([current[s] for s in sids]);oldtrace=unary_union([original[s] for s in sids]);attached=[d for d in lands if original[d['id']].intersection(oldtrace).area>1e-12]
  row['land_ids']=[d['id'] for d in attached];row['land_labels']=[d['label'] for d in attached]
  if not attached:
   row['reason']='NO_SOURCE_QUALIFIED_CIRCLE_CONTACT';decisions.append(row);continue
  owner,radius,window=prepare_spindle_context(trace,[d['geometry'] for d in attached],crop)
  allowed=set(sids)|{s for d in attached for s in d['aliases']}
  foreign=[(ids[int(i)],current[ids[int(i)]]) for i in tree.query(window.buffer(.02011)) if ids[int(i)] not in allowed];foreign += [('trial:'+a['id'],a['addition']) for a in accepted]
  best,attempts=fit_spindle_blend(owner,radius,window,foreign)
  row['attempts']=attempts
  if best:
   candidate,addition,check,scale=[best[k] for k in ['candidate','addition','check','scale']];cid=f'SP-{ci:03}';row.update(id=cid,status='GROWN',radius_mm=radius*scale,window_sha256=sha(to_wkb(window)),addition_sha256=sha(to_wkb(addition)),added_area_mm2=addition.area,check=check)
   for n,g in [(cid,addition),(cid+'_window',window),(cid+'_owner',owner)]:(OUT/'patches'/f'{n}.wkb').write_bytes(to_wkb(g))
   accepted.append(dict(id=cid,addition=addition,owner=owner,window=window,foreign=[p for p in foreign if not p[0].startswith('trial:')]))
  else:row['reason']='NO_VALID_BOUNDED_LAND_SIZED_BLEND'
  decisions.append(row)
 final=verify_spindle_batch(accepted)
 after=assemble_spindle_scene(before,accepted)
 for n,h in f['file_bindings'].items():assert sha((P/n).read_bytes())==h
 for n,g in [('before',before),('after',after),('added',after.difference(before))]:(OUT/f'{n}.wkb').write_bytes(to_wkb(g))
 save(OUT/'DECISIONS.json',decisions);save(OUT/'FINAL_CHECKS.json',final)
 result=dict(status='EXPERIMENTAL_C01_LAND_SIZED_SPINDLE_BLEND',asset_integrity=assets,source_sha256=f['source_sha256'],predecessor_sha256=sha(before_blob),after_sha256=sha(to_wkb(after)),source_components=len(components),grown_components=len(accepted),grown_source_land_contacts=sum(len(r['land_ids']) for r in decisions if r['status']=='GROWN'),kept_components=sum(r['status']=='KEEP' for r in decisions),added_area_mm2=after.difference(before).area,operator='Source-qualified connected owner; land-radius rolling-disc closing; only additions trimmed by 0.02011 mm foreign barriers; final gap checked at 0.02010 mm',limitations='Trial, not qualified final T05; branched components require local split; no reference-geometry copying; no route or T04 source-width edits',T01='266 frozen hashes unchanged',T04='All source parts unchanged',T02='NOT_APPLIED',first_T05_256='PRESERVED_SEPARATELY')
 save(OUT/'RESULT.json',result);save(OUT/'STAGE_CONTRACT.json',CONTRACT.__dict__);(OUT/'source_snapshot').mkdir()
 for n in ['src/junction_spindle_blend.py','src/junction_spindle_stage.py','tools/run_c01_spindle_trial.py','tests/test_junction_spindle_blend.py']:shutil.copyfile(ROOT/n,OUT/'source_snapshot'/Path(n).name)
 for name,title,g,d in [('before','Before spindle trial',before,GeometryCollection()),('after','C01 / broader spindle trial',after,GeometryCollection()),('growth','C01 / actual spindle additions',after,after.difference(before))]:
  p=OUT/(name+'.svg');render(p,title,g,d,f['viewport_mm'],[],{},[f"{len(accepted)} source trace components blended; {result['grown_source_land_contacts']} source-qualified circle contacts.",'Teal = actual additions; frozen T01 / T04 contributions unchanged. T02 not applied.','Land-sized closing compared with original short T05 tapers; trial only, not final acceptance.']);subprocess.run(['sips','-s','format','png',str(p),'--out',str(p.with_suffix('.png'))],capture_output=True,check=True)
 reference=B/'t03_t04_s1_registration_20261025/C1_edit_reference.png';shutil.copyfile(reference,OUT/'EDIT_reference.png');result['reference_sha256']=sha(reference.read_bytes());save(OUT/'RESULT.json',result)
 (OUT/'index.html').write_text('<!doctype html><meta charset="utf-8"><style>body{font:18px system-ui;max-width:1500px;margin:30px auto}img{width:100%}</style><h1>C01 · spindle trial against EDIT</h1><p>Experimental wider junction treatment. First T05 result preserved. Frozen T01/T04 source parts unchanged. Branched/mixed components remain unhandled.</p><h2>EDIT directional reference, not copied target geometry</h2><img src="EDIT_reference.png"><h2>Before</h2><img src="before.png"><h2>After</h2><img src="after.png"><h2>Actual added copper</h2><img src="growth.png"><p><a href="RESULT.json">Result and scope</a> · <a href="DECISIONS.json">Every component outcome</a> · <a href="FINAL_CHECKS.json">Final simultaneous clearance checks</a></p>');print(json.dumps(result))
if __name__=='__main__':
 import argparse
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,default=OUT);main(parser.parse_args().out)
