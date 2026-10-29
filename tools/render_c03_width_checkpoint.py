#!/usr/bin/env python3
"""Render one complete passing T04 search vector without promoting it."""
from pathlib import Path
import sys,json,argparse,subprocess
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from shapely import STRtree,to_wkb,from_wkb
from shapely.geometry import box
from shapely.ops import unary_union
from src.source_offset_width import construct_source_offset_width
from tools.c03_sequence_scene import load_scene,read,save,sha,CACHE
from tools.render_c03_source_frame import render_source_frame as render

def main(run):
 if not run.resolve().is_relative_to(ROOT/'out'):raise ValueError('PROJECT_LOCAL_RUN_REQUIRED')
 selected=None
 for file in sorted((run/'T04/checks').glob('*.json'),reverse=True):
  blob=file.read_bytes()
  try:check=json.loads(blob)
  except json.JSONDecodeError:continue
  if check['check']['passed'] and check['check']['evaluation_complete']:selected=file,blob,check;break
 if selected is None:raise ValueError('NO_COMPLETE_PASSING_VECTOR')
 file,blob,check=selected;out=run/('width_checkpoint_'+file.stem)
 if out.exists():raise ValueError('FRESH_CHECKPOINT_REQUIRED')
 scope,meta,original,current,protected,_=load_scene(run,'T01');binding=read(run/'T04/INPUT_BINDING.json');assert binding['source_sha256']==scope['source_sha256'];assert binding['definition_sha256']==sha((run/'eligibility/UNIFORM_SOURCE_PATHS.json').read_bytes());assert binding['groups_sha256']==sha((run/'groups/PARALLEL_MEMBERSHIP.json').read_bytes());defs=read(run/'eligibility/UNIFORM_SOURCE_PATHS.json');paths={r['path_id']:dict(r,component_id=r['path_id']) for r in defs['paths'] if r['definition_status']=='VISIBLE_COMPLETE_UNIFORM_PATH_PROPOSAL_CONTACT_CHECKS_RETAINED'};groups=read(run/'groups/PARALLEL_MEMBERSHIP.json')['groups'];assignment={cid:g['group_id'] for g in groups for cid in g['members']};assert set(paths)==set(assignment);raw=(CACHE/'ORG_source.kicad_pcb').read_bytes();sids={s for p in paths.values() for s in p['source_ids']};blobs={s:(CACHE/'source_wkb'/f"{meta[s]['geometry_sha256']}.wkb").read_bytes() for s in sids}
 for cid,p in sorted(paths.items()):
  f=check['scales'][assignment[cid]];assert 1<=f<=1.5;_,parts,_,_,_,_=construct_source_offset_width(raw,p,meta,blobs,f);current.update(parts)
 ids=sorted(current);crop=box(*scope['viewport_mm']);tree=STRtree([current[s] for s in ids]);after=unary_union([current[ids[int(i)]] for i in tree.query(crop,predicate='intersects')]).intersection(crop);before=from_wkb((run/'T01/after.wkb').read_bytes());assert before.difference(after).area<=1e-12;out.mkdir();(out/'after.wkb').write_bytes(to_wkb(after));(out/'CHECKED_SEARCH_VECTOR.json').write_bytes(blob)
 result=dict(status='INTERIM_PASSING_T04_VECTOR_NOT_FINAL_OR_PROMOTED',source_check=str(file.relative_to(run)),source_check_sha256=sha(blob),after_sha256=sha(to_wkb(after)),routes=len(paths),groups=len(groups),positive_groups=sum(v>1 for v in check['scales'].values()),at_ceiling=sum(v==1.5 for v in check['scales'].values()),T02_T05='NOT_YET_RUN',registration=scope['screenshot_registration'],C01_C02='UNCHANGED');save(out/'RESULT.json',result)
 for name,g in [('clean_after',after),('growth',after)]:
  p=out/(name+'.svg');render(p,'C03 / interim safe T04 vector / '+name,g,after.difference(before) if name=='growth' else after.difference(after),scope['viewport_mm'],notes=[f"Complete{len(paths)} route vector /{len(groups)} groups;{result['positive_groups']} currently grow;{result['at_ceiling']} at1.5x.",'INTERIM search checkpoint, not final/maximal or owner accepted. T02/T05 still pending.','Selected conservative-envelope vector passed complete full-source clearance checks; nominal copper shown.', 'T01 circle parts unchanged. Source localization provisional; C01/C02 accepted results remain frozen.']);subprocess.run(['sips','-s','format','png',str(p),'--out',str(p.with_suffix('.png'))],capture_output=True,check=True)
 (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>C03 interim T04</title><style>body{font:18px system-ui;max-width:1700px;margin:30px auto}img{width:100%}</style><h1>C03 · interim passing T04 vector</h1><p>Actual nominal copper from a complete passing search vector. Search continues; this is not the final sequence result. T02/T05 pending, no promotion.</p><img src="clean_after.png"><h2>Actual trace-width addition</h2><img src="growth.png"><a href="RESULT.json">Checkpoint bindings</a>');print(json.dumps(result))
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('run',type=Path);main(**vars(p.parse_args()))
