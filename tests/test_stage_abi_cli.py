import hashlib,json,subprocess,tempfile
from pathlib import Path
from tests.test_stage_abi_service import environment
ROOT=Path(__file__).resolve().parents[1]

def test_local_cli_dispatch_and_registry_digest_rejection():
 with tempfile.TemporaryDirectory(dir=ROOT/'out',prefix='stage_abi_cli_') as folder:
  p=Path(folder);store,service,doc,req,_,_=environment(p);doc['profiles']['spindle']['adapter']='spindle-v1';registry=p/'registry.json';registry.write_text(json.dumps(doc));request=json.dumps(req('describe',dict(requested_contract_version=None)))
  cmd=[str(ROOT/'.venv/bin/python'),str(ROOT/'tools/stage_agent_abi.py'),'--registry',str(registry),'--registry-sha256',hashlib.sha256(registry.read_bytes()).hexdigest(),'--store',str(store.root)]
  good=subprocess.run(cmd,input=request,capture_output=True,text=True,check=True);response=json.loads(good.stdout);assert response['status']=='OK' and response['result']['profiles']['spindle']['support']['family']=='land-sized-additive-spindle/1'
  bad=subprocess.run(cmd,input='{"operation":"one","operation":"two"}',capture_output=True,text=True);assert bad.returncode==2 and json.loads(bad.stdout)['error']['code']=='INPUT_OR_HOST_CONFIG_INVALID'
  cmd[cmd.index('--registry-sha256')+1]='0'*64;bad=subprocess.run(cmd,input=request,capture_output=True,text=True);assert bad.returncode==2 and json.loads(bad.stdout)['error']['code']=='REGISTRY_BINDING_MISMATCH'
