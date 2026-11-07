"""Single fresh construction/reconstruction worker; every failed job stays sealed."""
import json,os,sys,time
from pathlib import Path
from . import pipeline as p
from .guard import verify_sources,install_read_fence
ORDER=('t01','t03','t04','t02','t05')
def compute(run,name):
 if name=='t02'and os.environ.get('U05_WORKER_MODE')in('1','2'):
  recorded=p.load(run/'t02.json');proof=p.load(run/'audits/t02/construct.json')
  if (proof.get('status')!='PASS'or proof.get('stage')!='t02'or
      proof.get('candidate_sha256')!=p.digest(p.canonical(recorded))or
      proof.get('producer_binding_sha256')!=p.digest((run/'PRODUCER_BINDING.json').read_bytes())or
      proof.get('source_sha256')!=p.load(run/'source.json')['source_ref']['sha256']):
   raise ValueError('T02_SUCCESSFUL_CONSTRUCTION_CHECKPOINT_REQUIRED')
  value=p.stage(run,name,recorded=recorded)
 elif name=='t04'and(os.environ.get('U05_WORKER_MODE')!='construct'or(run/'REUSED_WIDTH_BINDING.json').exists()):
  from .width_prefix import reconstruct
  value=reconstruct(run,os.environ['U05_WORKER_MODE'])
 else:value=p.stage(run,name)
 if name=='t04'and os.environ.get('U05_WORKER_MODE')=='construct'and not(run/'REUSED_WIDTH_BINDING.json').exists():p.save(run/'RAW_WIDTH_CHECKPOINT.json',value)
 if name=='t05':p.save(run/'raw_checkpoints'/('t05_'+os.environ.get('U05_WORKER_MODE','unit')+'.json'),value)
 if name in('t04','t05')and not(run/'LEGACY_REFERENCE_JOB.json').exists():
  from .component_finish import finish
  store=p.Store(run/'runtime');binding=p.load(run/'source.json');scene=store.get_json(value['output_scene_ref'],kind='scene')
  completed=finish(store,scene,binding,name,junction_result=value if name=='t05'else None,mode=os.environ.get('U05_WORKER_MODE','unit'))
  if name=='t05':
   from .joint_smoothing import apply
   completed=apply(store,scene,binding,completed,name,value)
  value=dict(value,raw_output_scene_ref=value['output_scene_ref'],output_scene_ref=completed['output_scene_ref'],intra=completed)
  value['summary']=dict(value['summary'],inclusive_fills=completed['summary']['fills'],inclusive_added_area_mm2=completed['summary']['added_area_mm2']);store.verify_reads()
 from src.t04_width_fence import require as require_width_fence
 if name=='t04':
  store=p.Store(run/'runtime');checked_scene=store.get_json(value['output_scene_ref'],kind='scene');_,material,_=p.operands(store,checked_scene)
  width_proof=require_width_fence(p.unary_union(list(material.values())),scope=name+'_complete')
  if width_proof is not None:value=dict(value,t04_width_fence=width_proof)
 elif name=='t02':
  from .width_stage_constraints import require_t02
  store=p.Store(run/'runtime');width_proof=require_t02(store,p.load(run/'t04.json')['output_scene_ref'],value)
  if width_proof is not None:value=dict(value,t04_width_fence=width_proof)
 from src import pin_separation as pin
 if pin.ACTIVE is not None:
  store=p.Store(run/'runtime');scene=store.get_json(value['output_scene_ref'],kind='scene');_,material,_=p.operands(store,scene)
  import copy
  scene=copy.deepcopy(scene);scene['lineage'][-1]['pin_separation_state']=pin.ACTIVE.state(store)
  value=dict(value,output_scene_ref=store.put_json('scene',scene),pin_separation=pin.ACTIVE.require(p.unary_union(list(material.values())),scope=name+'_complete'))
 return value

def main():
 p.configure();run=Path(sys.argv[1]);name,mode=sys.argv[2:4];os.environ['U05_WORKER_MODE']=mode;install_read_fence(run);verify_sources(run);start=time.monotonic()
 if name in ORDER:
  for old in ORDER[:ORDER.index(name)]:
   for prior in('construct','1','2'):
    proof=p.load(run/'audits'/old/(prior+'.json'))
    if proof['status']!='PASS'or proof['candidate_sha256']!=p.digest((run/(old+'.json')).read_bytes()):raise ValueError('PREDECESSOR_STAGE_PROOF_CHANGED')
  value=compute(run,name);path=run/(name+'.json')
  if mode=='construct':p.save(path,value)
  elif p.canonical(value)!=p.canonical(p.load(path)):raise ValueError('FRESH_STAGE_RECONSTRUCTION_CHANGED:'+name)
  proof=dict(status='PASS',stage=name,candidate_sha256=p.digest(p.canonical(value)),producer_binding_sha256=p.digest((run/'PRODUCER_BINDING.json').read_bytes()),source_sha256=p.load(run/'source.json')['source_ref']['sha256'],summary=value['summary'])
  p.save(run/'audits'/name/(mode+'.json'),proof)
  if mode=='2':p.save(run/'audits'/name/'proof.json',proof)
 elif name=='t01_supplement':
  from .t01_complete_audit import audit
  value=audit(run);p.save(run/'audits/t01'/('supplement_'+mode+'.json'),value)
 elif name=='legacy_export':
  from . import legacy_export as e
  body,ledger=e.construct(run);folder=run/'export'
  if mode=='construct':
   folder.mkdir();(folder/'top.art.gbr').write_bytes(body);p.save(folder/'ledger.json',ledger)
  else:
   if body!=(folder/'top.art.gbr').read_bytes()or p.canonical(ledger)!=p.canonical(p.load(folder/'ledger.json')):raise ValueError('FRESH_LEGACY_EXPORT_RECONSTRUCTION_CHANGED')
   proof=e.check(run,body,ledger);p.save(folder/('proof_'+mode+'.json'),proof)
 else:raise ValueError('UNKNOWN_OPERATION')
 verify_sources(run);print(json.dumps(dict(status='PASS',stage=name,mode=mode,pid=os.getpid(),seconds=time.monotonic()-start)),flush=True)
if __name__=='__main__':main()
