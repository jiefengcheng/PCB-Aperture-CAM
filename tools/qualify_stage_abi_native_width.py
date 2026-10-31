#!/usr/bin/env python3
"""Fresh ABI width execution on one actual C03 native complete route.

All inputs stay frozen. This is a local regression scope, not whole-board or
new owner acceptance. Requests and responses are retained for inspection.
"""
from pathlib import Path
import sys,json,hashlib,argparse,shutil
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.stage_abi import ABI_VERSION
from src.stage_abi.store import ArtifactStore,canonical
from src.stage_abi.native_import import import_width_scene
from src.stage_abi.registry import TrustedRegistry
from src.stage_abi.service import StageService,runtime_fingerprint
from src.stage_abi.width import WidthAdapter,width_parameters
from src.trace_first_pipeline import read,write,digest
from src.stage_abi.scene import composed,validate_scene
from tools.c03_sequence_scene import load_scene,CACHE
from src.crop_circle_sources import verify_assets
from shapely import from_wkb


def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,default=ROOT/'out/crop_dynamic_tasks/stage_abi_native_width_20261031_279');args=parser.parse_args();out=args.output.resolve()
 if not out.is_relative_to(ROOT/'out'):raise ValueError('PROJECT_OUTPUT_REQUIRED')
 if out.exists():raise ValueError('FRESH_QUALIFICATION_OUTPUT_REQUIRED')
 assets=verify_assets();run=ROOT/'out/crop_dynamic_tasks/c03_sequence_20261030_269';scope,meta,original,current,replacements,_=load_scene(run,'T01');construction=read(run/'T04/CONSTRUCTION.json');chosen=next(r for r in construction if r['factor']==1.5 and len(r['complete_source_ids'])>1);chain=dict(component_id=chosen['component_id'],source_ids=chosen['complete_source_ids'],source_sha256=scope['source_sha256']);raw=(CACHE/'ORG_source.kicad_pcb').read_bytes();manifest=read(CACHE/'source_manifest.json');blobs={sid:(CACHE/'source_wkb'/f"{m['geometry_sha256']}.wkb").read_bytes() for sid,m in meta.items()};out.mkdir();store=ArtifactStore(out/'runtime')
 fingerprint=runtime_fingerprint()
 for source in [*sorted((ROOT/'src').glob('*.py')),*sorted((ROOT/'src/stage_abi').glob('*.py')),Path(__file__)]:
  target=out/'code_snapshot'/source.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
 q=read(ROOT/'out/crop_dynamic_tasks/trace_first_pipeline_t03_recheck_20261030_273/T03/CHECK.json')
 if not q['passed'] or not q['evaluation_complete']:raise ValueError('SOURCE_LAND_QUALIFICATION_NOT_PASS')
 imported=import_width_scene(store,source=raw,manifest=manifest,original_blobs=blobs,current_blobs=replacements,chains=[chain],viewport_mm=scope['viewport_mm'],qualification=dict(source_sha256=digest(CACHE/'ORG_source.kicad_pcb'),T01_after_sha256=digest(run/'T01/after.wkb'),full_T01_check_sha256=digest(ROOT/'out/crop_dynamic_tasks/trace_first_pipeline_t03_recheck_20261030_273/T03/CHECK.json'),route_definition_sha256=digest(run/'eligibility/UNIFORM_SOURCE_PATHS.json'),scope='Existing prepared native complete route; no whole-board electrical qualification'))
 scene=imported['scene_ref'];actual=validate_scene(store,scene);assert composed(store,actual).symmetric_difference(from_wkb((run/'T01/after.wkb').read_bytes())).area<=1e-12
 policy=store.put_json('policy',dict(stage='t04',parameters=width_parameters()));bounds=store.put_json('bounds',dict(max_source_objects=20000,max_targets=1,max_evaluations=100,max_output_bytes=100000000,max_seconds=300));verifier=store.put_json('verifier',dict(family=width_parameters()['family']));doc=dict(schema='stage-agent-registry/1',profiles={'c03-single-native-route':dict(stage='t04',adapter='native-width-v1',policy_ref=policy,scene_refs=[scene],bounds_ref=bounds,verifier_ref=verifier)},authorization_refs=[],decision_refs=[]);service=StageService(store,TrustedRegistry(store,doc),{'native-width-v1':WidthAdapter()});transcript=[]
 def request(verb,payload,**kw):return dict(abi_version=ABI_VERSION,request_id='c03-'+verb,operation='t04_'+verb,profile_id='c03-single-native-route',scene_ref=scene,policy_ref=policy,plan_ref=kw.get('plan_ref'),authorization_ref=kw.get('authorization_ref'),idempotency_key=kw.get('idempotency_key'),payload=payload)
 def call(r):
  response=service.dispatch(r);transcript.append(dict(request=r,response=response));write(out/'TRANSCRIPT.json',transcript)
  if response['status']!='OK':raise ValueError(response)
  return response['result']
 inspected=call(request('inspect',dict(source_ids=imported['target_ids'],finding_ids=[],page_size=10,cursor=None)));selection=store.put_json('selection',dict(stage='t04',scene_ref=scene,source_ids=imported['target_ids'],groups=[dict(group_id='singleton',members=imported['target_ids'])]));qualification=store.put_json('verification',dict(scene_ref=scene,geometric_status='PASS',scope='Exact normalized native source/T01 predecessor composition, source cache bindings and prepared complete-chain admission; no independent review'))
 planned=call(request('plan',dict(inspection_ref=inspected['inspection_ref'],selection_ref=selection,predecessor_qualification_ref=qualification,bounds_ref=bounds,strategy='collective_uniform_width')));plan=planned['plan_ref'];output=store.put_json('output-scope',dict(kind='immutable-local-artifacts'));auth=store.put_json('authorization',dict(profile_id='c03-single-native-route',scene_ref=scene,policy_ref=policy,plan_ref=plan,operations=['t04_run','t04_verify'],authority='User active goal: fully implement all ABI suites; project-local regression execution preserving frozen C01/C02/C03',output_scope_ref=output));doc['authorization_refs'].append(auth)
 candidate=call(request('run',dict(output_scope_ref=output),plan_ref=plan,authorization_ref=auth,idempotency_key='native-width-construct'))['result'];proof=store.put_json('proof-scope',dict(scope='complete-source-nominal-envelope-and-upper-proofs'));verified=call(request('verify',dict(candidate_ref=candidate['candidate_ref'],verifier_ref=verifier,proof_scope_ref=proof),plan_ref=plan,authorization_ref=auth,idempotency_key='native-width-verify'))['result']
 assert verified['verification']['geometric_status']=='PASS';value=candidate['candidate'];receipt=dict(status='PASS_REAL_SOURCE_SINGLE_COMPLETE_ROUTE_ABI_EXECUTION_AND_REPLAY',runtime_fingerprint=fingerprint,asset_integrity=assets,imported=imported,selected_scales=value['solution']['selected_scales'],native_parts=len(value['parts']),candidate_ref=candidate['candidate_ref'],verification_ref=verified['verification_ref'],scope='Actual full C03 source context and one prepared native full route; not all routes, stage composition, independent/native-export/electrical/manufacturing qualification')
 if runtime_fingerprint()!=fingerprint:raise ValueError('RUNTIME_CHANGED_DURING_QUALIFICATION')
 write(out/'RECEIPT.json',receipt);write(out/'registry.json',doc);(out/'before.wkb').write_bytes(store.get(value['before_ref'],kind='geometry'));(out/'after.wkb').write_bytes(store.get(value['after_ref'],kind='geometry'));print(json.dumps(receipt))
if __name__=='__main__':main()
