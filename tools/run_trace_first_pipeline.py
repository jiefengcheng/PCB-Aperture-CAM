#!/usr/bin/env python3
"""Execute or replay a pinned prepared-region T01/T03/T04/T02/T05 sequence."""
from pathlib import Path
import argparse,functools,json,shutil,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.trace_first_pipeline import TraceFirstPipeline,ORDER,read,write,digest,verify_files,replay_adapter,copy_bound
from src.trace_first_scene import load_scene
from src.crop_circle_sources import verify_assets

def adapters(config,inputs,*,replay=False):
 def scoped(name):
  p=(ROOT/name).resolve()
  if not p.is_relative_to(ROOT):raise ValueError('PROJECT_LOCAL_PREPARED_SNAPSHOT_REQUIRED')
  return p
 if not replay and 'source_eligibility' not in inputs:raise ValueError('SOURCE_ELIGIBILITY_DISPOSITIONS_REQUIRED')
 cache=inputs['source'].parent
 if cache.name!='inputs' or inputs['source_manifest'].parent!=cache:raise ValueError('PREPARED_INPUT_CACHE_LAYOUT_REQUIRED')
 loader=functools.partial(load_scene,cache=cache)
 def prepare(run):
  write(run/'SOURCE_BINDINGS.json',dict(source_sha256=digest(inputs['source']),source_manifest_sha256=digest(inputs['source_manifest']),scope_sha256=digest(inputs['scope'])))
  for name,role in [('eligibility','definitions'),('groups','groups')]:
   dest=run/name;dest.mkdir();shutil.copyfile(inputs[role],dest/inputs[role].name)
  if 'source_eligibility' in inputs:shutil.copyfile(inputs['source_eligibility'],run/'eligibility/SOURCE_ELIGIBILITY.json')
  if 'bulk_roles' in inputs:shutil.copyfile(inputs['bulk_roles'],run/'FIXED_BULK_ROLES.json')
 def t01(run,bindings):
  prepare(run)
  if 't01_snapshot' in config:
   snap=config['t01_snapshot'];source=scoped(snap['path']);copy_bound(source,run/'T01',read(inputs['t01_manifest']))
  else:
   from tools.run_c03_round_class_stage import main
   main(cache.parent,inputs['scope'],inputs['baseline'],run/'T01',surface_mode=True)
   shutil.copyfile(inputs['scope'],run/'T01/SUPPORTED_TARGETS.json')
  write(run/'T01/PREDECESSOR_RECEIPT.json',dict(status='PINNED_PREPARED_T01_PROFILE',source_sha256=digest(inputs['source']),cumulative_sha256=digest(run/'T01/after.wkb')))
 def t03(run,bindings):
  from src.prepared_land_scene import PreparedLandScene
  scope,meta,original,current,_,_=loader(run,'T01');decisions=read(run/'T01/DECISIONS.json');ids={r['source_id'] for r in decisions};lands=[dict(id=s,original=original[s],candidate=current[s],native_source_kind='gr_circle',native_stroke_width_mm=0.) for s in sorted(ids)]
  if lands:
   checker=PreparedLandScene(lands,[dict(id=s,geometry=g,trace_width_mm=meta[s]['trace_width_mm']) for s,g in original.items() if s not in ids]);q=checker.check(lands,materialize_scene=True)
   if not q['passed'] or not q['evaluation_complete']:raise ValueError('T03_ROUTE_REPAIR_REQUIRED_NOT_QUALIFIED_BY_THIS_PROFILE')
  else:q=dict(passed=True,evaluation_complete=True,scope='NO_T01_CIRCLE_TARGETS')
  out=run/'T03';out.mkdir();write(out/'CHECK.json',q)
  for name in ['before','after']:shutil.copyfile(run/'T01/after.wkb',out/(name+'.wkb'))
  write(out/'RESULT.json',dict(status='PASS_T03_GROWTH_ONLY_NO_ROUTE_CHANGE',after_sha256=digest(out/'after.wkb'),growth_check_passed=True,route_changes=0,scope='Pre-existing unchanged relationships are not repaired'))
 def t04(run,bindings):
  from tools.trace_first_width_stage import run_width_stage
  hints=read(inputs['warm_start']) if 'warm_start' in inputs else {}
  run_width_stage(run,cache,initial_scales=hints.get('initial_scales'),prior_upper_factors=hints.get('prior_upper_factors'),limits=config['limits'])
 def t02(run,bindings):
  scope=read(run/'T01/SUPPORTED_TARGETS.json')
  if not any(r['scope_disposition']=='T02_RECTANGLE_TARGET_PROPOSAL' for r in scope['records']):
   out=run/'T02';out.mkdir();(out/'rectangle_parts').mkdir();(out/'merges').mkdir()
   for n in ['before','after']:shutil.copyfile(run/'T04/after.wkb',out/(n+'.wkb'))
   for n in ['DECISIONS','INCLUSIVE_CANDIDATES']:write(out/(n+'.json'),[])
   write(out/'RESULT.json',dict(status='NOT_APPLICABLE_NO_RECTANGLE_TARGETS',predecessor_sha256=digest(out/'before.wkb'),after_sha256=digest(out/'after.wkb'),rectangle_targets=0,grown=0,keep=0,inclusive_merges=0))
   return
  from tools.run_c03_trace_first_rectangles import main
  main(run,scene_loader=loader)
 def t05(run,bindings):
  from tools.run_c03_junction_stage import main
  main(run,scene_loader=loader,source_cache=cache)
 if not replay:return dict(T01=t01,T03=t03,T04=t04,T02=t02,T05=t05)
 result={}
 for stage in ORDER:
  spec=config['replay_stages'][stage];source=scoped(spec['path']);files=read(inputs['replay_'+stage]);result[stage]=replay_adapter(stage,source,files)
 prior=result['T01']
 def first(run,bindings):prepare(run);prior(run,bindings)
 result['T01']=first
 return result

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('config',type=Path);p.add_argument('output',type=Path);p.add_argument('--replay',action='store_true',help='Saved-stage replay; not a new construction/search');a=p.parse_args();verify_assets();config=read(a.config);pipeline=TraceFirstPipeline(ROOT,config,a.output)
 limits=config['limits']
 if set(limits)!={'max_source_objects','max_routes','max_groups','max_width_evaluations'} or any(type(v)!=int or v<=0 for v in limits.values()):raise ValueError('EXPLICIT_POSITIVE_INTEGER_LIMITS_REQUIRED')
 count=len(read(pipeline.inputs['source_manifest'])['objects']);paths=read(pipeline.inputs['definitions'])['paths'];groups=read(pipeline.inputs['groups'])['groups']
 routes=sum(r['definition_status']=='VISIBLE_COMPLETE_UNIFORM_PATH_PROPOSAL_CONTACT_CHECKS_RETAINED' for r in paths)
 if count>limits['max_source_objects'] or routes>limits['max_routes'] or len(groups)>limits['max_groups']:raise ValueError('PREPARED_SCOPE_EXCEEDS_DECLARED_BUDGET')
 print(json.dumps(pipeline.execute(adapters(config,pipeline.inputs,replay=a.replay),mode='SAVED_STAGE_REPLAY' if a.replay else 'CONSTRUCTION')))
if __name__=='__main__':main()
