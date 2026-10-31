"""All 35 public operations through the actual stdin/stdout CLI and factories."""
import copy,hashlib,json,subprocess,tempfile
from pathlib import Path
import pytest
from src.stage_abi.responses import validate_response
from tests.test_stage_abi_resume import prepared
ROOT=Path(__file__).resolve().parents[1]
FACTORIES=dict(t01='round-class-v1',t02='rectangle-inclusive-v1',t03='parallel-route-v1',t04='native-width-v1',t05='spindle-v1')
PROOFS=dict(t01='complete-source-land-and-inclusive',t02='complete-source-land-and-inclusive',t03='complete-source-parallel-route-and-attachments',t04='complete-source-nominal-envelope-and-upper-proofs',t05='complete-source-and-all-patches')

@pytest.mark.parametrize('stage',['t01','t02','t03','t04','t05'])
def test_all_seven_operations_are_real_closed_cli_responses(stage):
 with tempfile.TemporaryDirectory(dir=ROOT/'out',prefix='all_abi_wire_') as name:
  folder=Path(name);store,service,base=prepared(folder,stage);pid=base['profile_id'];doc=copy.deepcopy(service.registry.document);profile=doc['profiles'][pid];profile['adapter']=FACTORIES[stage];catalogue=folder/'registry.json';catalogue.write_text(json.dumps(doc));command=[str(ROOT/'.venv/bin/python'),str(ROOT/'tools/stage_agent_abi.py'),'--registry',str(catalogue),'--registry-sha256',hashlib.sha256(catalogue.read_bytes()).hexdigest(),'--store',str(store.root)];seen=[]
  def call(verb,payload,execution=False):
   request=dict(base,operation=stage+'_'+verb,payload=payload,request_id='wire:'+verb)
   if not execution:request.update(plan_ref=None,authorization_ref=None,idempotency_key=None)
   else:request['idempotency_key']='wire:'+verb
   if verb=='describe':request.update(scene_ref=None,policy_ref=None)
   done=subprocess.run(command,input=json.dumps(request),capture_output=True,text=True);response=json.loads(done.stdout);validate_response(response);assert done.returncode==0 and response['status']=='OK',response;seen.append(verb);return response['result']
  call('describe',dict(requested_contract_version=None));plan=store.get_json(base['plan_ref'],kind='plan');selection=store.get_json(plan['selection_ref'],kind='selection');inspect=call('inspect',dict(source_ids=selection['source_ids'],finding_ids=[],page_size=100,cursor=None));planned=call('plan',dict(inspection_ref=inspect['inspection_ref'],selection_ref=plan['selection_ref'],predecessor_qualification_ref=plan['qualification_ref'],bounds_ref=plan['bounds_ref'],strategy=plan['strategy']));assert planned['plan_ref']==base['plan_ref']
  run=call('search' if stage=='t03' else 'run',base['payload'],execution=True);assert run['job']['status']=='COMPLETED';candidate=run['result']['candidate_ref'];proof=store.put_json('proof-scope',dict(scope=PROOFS[stage]));verified=call('verify',dict(candidate_ref=candidate,verifier_ref=profile['verifier_ref'],proof_scope_ref=proof),execution=True);assert verified['result']['verification']['geometric_status']=='PASS';output=run['result']['candidate']['output_scene_ref'];scene=store.get_json(base['scene_ref'],kind='scene');view=store.put_json('viewport',dict(frame=scene['frame'],bounds_mm=scene['viewport_mm']));filtered=store.put_json('evidence-selection',dict(source_ids=selection['source_ids']));compare=call('compare',dict(left_ref=base['scene_ref'],right_ref=output,viewport_ref=view,evidence_selection_ref=filtered));assert 'visuals' in compare
  review=call('review',dict(candidate_ref=candidate,verification_ref=verified['result']['verification_ref'],decision_filters=dict(types=['owner','independent'],page_size=100,cursor=None)));assert review['owner_status']=='PENDING' and review['independent_status']=='NOT_RUN';assert len(seen)==7
