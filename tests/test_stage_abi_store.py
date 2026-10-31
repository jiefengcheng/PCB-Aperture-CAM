from concurrent.futures import ThreadPoolExecutor
import pytest
from src.stage_abi.store import ArtifactStore,canonical
from src.stage_abi.contracts import StageABIError

def test_canonical_immutable_artifact_and_corruption(tmp_path):
 s=ArtifactStore(tmp_path/'store');a=s.put_json('scene',{'b':2,'a':1});assert a==s.put_json('scene',{'a':1,'b':2})
 assert s.get_json(a,kind='scene')=={'a':1,'b':2}
 with pytest.raises(StageABIError,match='scene'):s.get(a,kind='policy')
 (s.root/'artifacts'/a['artifact_id']).write_bytes(b'corrupt')
 with pytest.raises(StageABIError):s.get(a)
 with pytest.raises(StageABIError):s.put('scene',canonical({'a':1,'b':2}))

def test_refs_cannot_escape_or_follow_symlink(tmp_path):
 s=ArtifactStore(tmp_path/'store');a=s.put('scene',b'data');p=s.root/'artifacts'/a['artifact_id'];p.unlink();target=tmp_path/'outside';target.write_bytes(b'data');p.symlink_to(target)
 with pytest.raises(StageABIError):s.get(a)
 with pytest.raises(StageABIError):s.get(dict(artifact_id='../outside',sha256=a['sha256']))

def test_concurrent_attempt_claim_is_once_and_binding_conflicts(tmp_path):
 s=ArtifactStore(tmp_path/'store');key={'stage':'t04','profile':'p','key':'one'};binding={'plan':'exact'}
 with ThreadPoolExecutor(max_workers=8) as pool:results=list(pool.map(lambda _:s.begin(key,binding),range(8)))
 assert sum(won for won,_ in results)==1
 with pytest.raises(StageABIError) as e:s.begin(key,{'plan':'different'})
 assert e.value.code=='IDEMPOTENCY_CONFLICT'
 checkpoint=s.put_json('checkpoint',{'ordinal':7,'budget_used':8});s.checkpoint(key,binding,checkpoint)
 result=s.put_json('result',{'status':'PASS'});finished=s.finish(key,binding,result);assert finished['checkpoint_ref']==checkpoint
 assert s.begin(key,binding)==(False,finished);assert s.finish(key,binding,result)==finished
 with pytest.raises(StageABIError):s.finish(key,binding,s.put_json('result',{'status':'OTHER'}))

def test_failed_attempt_not_silently_relaunched(tmp_path):
 s=ArtifactStore(tmp_path/'store');key={'key':'one'};binding={'plan':1};s.begin(key,binding);r=s.put_json('result',{'status':'FAIL'});s.finish(key,binding,r,failed=True)
 won,state=s.begin(key,binding);assert not won and state['status']=='FAILED'

def test_concurrent_content_identical_puts_are_one_artifact(tmp_path):
 s=ArtifactStore(tmp_path/'store');data=b'bounded evidence'*10000
 with ThreadPoolExecutor(max_workers=8) as pool:refs=list(pool.map(lambda _:s.put('evidence',data),range(16)))
 assert all(r==refs[0] for r in refs) and s.get(refs[0])==data
