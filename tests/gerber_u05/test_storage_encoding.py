"""Physical encoding cannot change logical bytes, budgets or immutable custody."""
from types import SimpleNamespace
import json
import pytest
from src.gerber_u05 import pipeline as p,storage_encoding as encoding
from src.stage_abi.store import ArtifactStore
from src.stage_abi.contracts import StageABIError
from src.stage_abi.journal import execution_journal


def test_new_compressed_artifact_has_identical_reference_and_normal_reads(tmp_path,monkeypatch):
 blob=(b'original geometry and checks\n'*40000)
 plain=ArtifactStore(tmp_path/'plain');compressed=p.Store(tmp_path/'compressed')
 expected=plain.put('geometry',blob);actual=compressed.put('geometry',blob)
 assert actual==expected
 path=compressed.root/'artifacts'/actual['artifact_id']
 assert path.read_bytes()==blob and compressed.get(actual)==blob
 assert path.stat().st_blocks*512 < len(blob)//2
 assert getattr(path.stat(),'st_flags',0)&32
 before=path.stat()
 def no_reencoding(*args):raise AssertionError('Existing immutable artifact was reencoded')
 monkeypatch.setattr(compressed,'_prepare_new_artifact',no_reencoding)
 assert compressed.put('geometry',blob)==actual
 assert path.stat().st_ino==before.st_ino and path.stat().st_mtime_ns==before.st_mtime_ns


def test_large_json_remains_exclusive_and_canonical(tmp_path):
 target=tmp_path/'result.json';value=dict(data=['same native geometry']*10000)
 expected=p.canonical(value);p.save(target,value)
 assert target.read_bytes()==expected and json.loads(target.read_bytes())==value
 assert target.stat().st_blocks*512<len(expected)//2
 before=target.stat()
 with pytest.raises(ValueError,match='IMMUTABLE_RESULT_EXISTS'):p.save(target,dict(other=True))
 assert target.read_bytes()==expected and target.stat().st_ino==before.st_ino


def test_small_files_use_the_existing_storage_path(tmp_path,monkeypatch):
 original=encoding.subprocess.run
 def no_process(args,**kwargs):
  if args[0]=='/usr/bin/ditto':raise AssertionError('Small file launched native encoding')
  return original(args,**kwargs)
 monkeypatch.setattr(encoding.subprocess,'run',no_process)
 store=p.Store(tmp_path/'runtime');ref=store.put('geometry',b'small original')
 assert store.get(ref)==b'small original'
 p.save(tmp_path/'result.json',{'small':True})


def test_bad_native_encoding_keeps_pending_evidence_and_does_not_publish(tmp_path,monkeypatch):
 original=encoding.subprocess.run
 def corrupt(args,**kwargs):
  if args[0]!='/usr/bin/ditto':return original(args,**kwargs)
  from pathlib import Path
  Path(args[-1]).write_bytes(b'corrupted storage result')
  return SimpleNamespace(returncode=0,stderr='')
 monkeypatch.setattr(encoding.subprocess,'run',corrupt)
 store=p.Store(tmp_path/'runtime');blob=b'original'*20000
 with pytest.raises(ValueError,match='EVIDENCE_ENCODING_BYTES_CHANGED'):store.put('geometry',blob)
 artifacts=store.root/'artifacts'
 assert not(artifacts/('geometry:'+p.digest(blob))).exists()
 assert (artifacts/('geometry:'+p.digest(blob)+'.tmp')).read_bytes()==blob
 assert list(artifacts.glob('*.encoded-*'))


def test_base_store_independently_rejects_a_mutating_preparation_hook(tmp_path):
 class BadEncoding(ArtifactStore):
  def _prepare_new_artifact(self,path,blob):path.write_bytes(blob+b'bad');return True
 store=BadEncoding(tmp_path/'runtime');blob=b'valid data'
 with pytest.raises(StageABIError)as error:store.put('geometry',blob)
 assert error.value.code=='ARTIFACT_CORRUPTED'
 assert not(store.root/'artifacts'/('geometry:'+p.digest(blob))).exists()


def test_reserve_includes_transient_storage_before_writing_large_json(tmp_path,monkeypatch):
 monkeypatch.setattr(encoding.shutil,'disk_usage',lambda path:SimpleNamespace(free=encoding.RESERVE_BYTES+encoding.THRESHOLD_BYTES))
 target=tmp_path/'new.json'
 with pytest.raises(ValueError,match='SPACE_RESERVE_REQUIRED'):
  encoding.write_new(target,b'a'*encoding.THRESHOLD_BYTES)
 assert not target.exists()and not list(tmp_path.glob('*.pending-*'))


@pytest.mark.parametrize('fits',[False,True])
def test_output_budget_charges_original_bytes_even_when_compressed(tmp_path,fits):
 store=p.Store(tmp_path/'runtime');key={'test':'logical-output-budget'};binding={'version':1}
 started,job=store.begin(key,binding);assert started
 blob=b'budgeted copper'*10000
 with execution_journal(store,key,binding,job,bounds={'max_output_bytes':len(blob)if fits else len(blob)-1,'max_seconds':30})as journal:
  if not fits:
   with pytest.raises(StageABIError)as error:store.put('geometry',blob)
   assert error.value.code=='BUDGET_EXHAUSTED'
   assert journal.output_bytes==0
  else:
   ref=store.put('geometry',blob)
   assert store.get(ref)==blob and journal.output_bytes==len(blob)
   assert (store.root/'artifacts'/ref['artifact_id']).stat().st_blocks*512<len(blob)
