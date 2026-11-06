"""Synthetic binding/corruption controls; these fixtures claim no native execution."""
import hashlib,json
from pathlib import Path
import pytest
from src.gerber_u05 import legacy_prefix as q,guard

def put(file,value):
 file.parent.mkdir(parents=True,exist_ok=True);file.write_text(json.dumps(value,sort_keys=True));return file

def binding_fixture(tmp_path,monkeypatch):
 old=tmp_path/'operator_routes/gerber_u05/job/legacy';original=tmp_path/'evidence/original';current=tmp_path/'evidence/current'
 names=['src/static.py','contracts/frozen.json','src/gerber_u05/t01_complete_audit.py']
 for name in names:
  for root in(original,current):
   file=root/name;file.parent.mkdir(parents=True,exist_ok=True);file.write_text('{}'if name.endswith('.json')else'# immutable\n')
 artifacts=old/'runtime/artifacts';artifacts.mkdir(parents=True)
 def artifact(kind,value):
  body=json.dumps(value,sort_keys=True).encode();sha=hashlib.sha256(body).hexdigest();(artifacts/(kind+':'+sha)).write_bytes(body);return dict(artifact_id=kind+':'+sha,sha256=sha)
 source_ref=artifact('gerber-source',dict(synthetic=True));scene_ref=artifact('scene',dict(objects=[]))
 put(old/'source.json',dict(scene_ref=scene_ref,source_ref=source_ref))
 put(old/'input_inventory.json',dict(input_directory='/unit',files={'top.art.gbr':source_ref['sha256']},ignored=[],selected='top.art.gbr'));put(old/'LEGACY_REFERENCE_JOB.json',dict(schema='unit-binding-only'))
 seal=dict(files={str(original/name):q.sha(original/name)for name in names},job_inputs={str(old/name):q.sha(old/name)for name in('input_inventory.json','LEGACY_REFERENCE_JOB.json')},source_binding_sha256=q.sha(old/'source.json'));put(old/'PRODUCER_BINDING.json',seal)
 records={};pid=1
 for stage in('t01','t03','t04','t02'):
  put(old/(stage+'.json'),dict(output_scene_ref=scene_ref,stage=stage))
  proof=dict(status='PASS',producer_binding_sha256=q.sha(old/'PRODUCER_BINDING.json'),candidate_sha256=q.sha(old/(stage+'.json')))
  for mode in('construct','1','2'):
   put(old/'audits'/stage/(mode+'.json'),proof);records['legacy_'+stage+'_'+mode]=dict(status='PASS',returncode=0,pid=pid);pid+=1
  put(old/'audits'/stage/'proof.json',proof)
 supplement=dict(status='PASS',source_sha256=source_ref['sha256'],stage_result_sha256=q.sha(old/'t01.json'),addendum_producer_sha256=q.sha(original/'src/gerber_u05/t01_complete_audit.py'))
 for mode in('1','2'):
  put(old/'audits/t01'/('supplement_'+mode+'.json'),supplement);records['legacy_t01_supplement_'+mode]=dict(status='PASS',returncode=0,pid=pid);pid+=1
 put(old.parent/'STATUS.current.json',dict(status='HALTED',checks=records))
 monkeypatch.setattr(q,'configure',lambda:tmp_path);monkeypatch.setattr(q,'ROOT',current);monkeypatch.setattr(guard,'producer_files',lambda:[current/name for name in names])
 return old,current,artifacts

def test_complete_prefix_retains_both_native_record_sets(tmp_path,monkeypatch):
 old,_,_=binding_fixture(tmp_path,monkeypatch);result=q.inspect(old,'t02')
 assert result['retained_operation_count']==14 and len(result['original_checks'])==14
 assert result['original_route_completion'].startswith('NOT_CLAIMED')


def test_t03_boundary_never_retains_a_failed_t04(tmp_path,monkeypatch):
 old,_,_=binding_fixture(tmp_path,monkeypatch)
 path=old.parent/'STATUS.current.json';state=json.loads(path.read_bytes())
 state['checks']['legacy_t04_construct']['status']='FAIL';put(path,state)
 result=q.inspect(old,'t03')
 assert result['stages']==['t01','t03']
 assert result['retained_operation_count']==8
 assert 't04.json'not in result['files']
 assert not any('t04'in k for k in result['original_checks'])


def test_t04_eviction_delta_authorizes_only_exact_bookkeeping_correction():
 before='def evict(self):\n self.bytes -= self.cache.popitem(last=False)[1]\n'
 after=before.replace('[1]','[1][1]')
 q.t04_eviction_delta_only(before,after)
 with pytest.raises(ValueError,match='EVICTION_DELTA_NOT_ISOLATED'):
  q.t04_eviction_delta_only(before,after+'def changed_geometry():\n return 42\n')

@pytest.mark.parametrize('mutation',['artifact','process','producer','supplement'])
def test_changed_or_incomplete_prefix_is_rejected(tmp_path,monkeypatch,mutation):
 old,current,artifacts=binding_fixture(tmp_path,monkeypatch)
 if mutation=='artifact':next(artifacts.glob('scene:*')).write_bytes(b'corrupt')
 elif mutation=='process':
  file=old.parent/'STATUS.current.json';value=json.loads(file.read_bytes());value['checks']['legacy_t03_1']['status']='FAIL';put(file,value)
 elif mutation=='producer':(current/'src/static.py').write_text('# changed upstream\n')
 else:
  file=old/'audits/t01/supplement_1.json';value=json.loads(file.read_bytes());value['stage_result_sha256']='0'*64;put(file,value)
 with pytest.raises(ValueError):q.inspect(old,'t02')

def test_empty_target_adapter_branch_does_not_authorize_other_pipeline_edits():
 before='def run_t02(store,scene):\n ids=[1]\n return ids\n'
 after='def empty_t02(store,scene):\n return None\ndef run_t02(store,scene):\n ids=[1]\n if not ids:return empty_t02(store,scene)\n return ids\n'
 q.pipeline_same(before,after)
 with pytest.raises(ValueError,match='PIPELINE_CHANGED'):q.pipeline_same(before,after.replace('ids=[1]','ids=[2]'))


def test_changed_fresh_companion_inventory_cannot_adopt_prefix(tmp_path,monkeypatch):
 old,_,artifacts=binding_fixture(tmp_path,monkeypatch);prefix=q.inspect(old,'t02')
 coordinator=object.__new__(q.IncrementalCoordinator);coordinator.old=old;coordinator.prefix=prefix
 inventory=json.loads((old/'input_inventory.json').read_bytes());inventory['files']['new-companion.gbr']='0'*64
 raw=next(artifacts.glob('gerber-source:*')).read_bytes()
 with pytest.raises(ValueError,match='CUSTODY_DIFFERS'):coordinator.prepare(tmp_path/'new-legacy',raw,inventory,True)
 assert not(tmp_path/'new-legacy').exists()


@pytest.mark.parametrize('changed',[False,True])
def test_adopted_binding_and_copied_prefix_are_revalidated(tmp_path,monkeypatch,changed):
 import shutil
 old,_,_=binding_fixture(tmp_path,monkeypatch);original=q.inspect(old,'t02');run=tmp_path/'new-job/legacy';run.mkdir(parents=True)
 for name in original['files']:
  target=run/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(old/name,target)
 put(run/'REUSED_LEGACY_BINDING.json',dict(original=original))
 if changed:
  (run/'t03.json').write_bytes(b'changed')
  with pytest.raises(ValueError,match='COPY_CHANGED'):q.verify(run)
 else:assert q.verify(run)['original']==original


@pytest.mark.parametrize('changed',[False,True])
def test_nested_prefix_preserves_original_process_and_producer_bindings(tmp_path,monkeypatch,changed):
 import shutil
 old,current,_=binding_fixture(tmp_path,monkeypatch);original=q.inspect(old,'t02');middle=tmp_path/'operator_routes/gerber_u05_incremental_legacy/middle/legacy';middle.mkdir(parents=True)
 for name in original['files']:
  target=middle/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(old/name,target)
 put(middle/'REUSED_LEGACY_BINDING.json',dict(original=original));put(middle/'input_inventory.json',json.loads((old/'input_inventory.json').read_bytes()));put(middle/'LEGACY_REFERENCE_JOB.json',dict(schema='unit-nested-binding-only'))
 files={str(file):q.sha(file)for file in current.rglob('*')if file.is_file()}
 inputs={str(middle/name):q.sha(middle/name)for name in('REUSED_LEGACY_BINDING.json','input_inventory.json','LEGACY_REFERENCE_JOB.json')}
 put(middle/'PRODUCER_BINDING.json',dict(files=files,job_inputs=inputs,source_binding_sha256=q.sha(middle/'source.json')));put(middle.parent/'STATUS.current.json',dict(status='HALTED',checks={}))
 if changed:
  (middle/'t03.json').write_bytes(b'corrupt inherited copy')
  with pytest.raises(ValueError,match='INHERITED_LEGACY_COPY_CHANGED'):q.inspect(middle,'t02')
 else:
  result=q.inspect(middle,'t02');assert result['retained_operation_count']==14
  assert result['original_checks']==original['original_checks']
  assert len(result['original_source_roots'])==2
