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
 put(old/'RAW_WIDTH_CHECKPOINT.json',json.loads((old/'t04.json').read_bytes()))
 monkeypatch.setattr(q,'configure',lambda:tmp_path);monkeypatch.setattr(q,'ROOT',current);monkeypatch.setattr(guard,'producer_files',lambda:[current/name for name in names])
 return old,current,artifacts

def test_complete_prefix_retains_both_native_record_sets(tmp_path,monkeypatch):
 old,_,_=binding_fixture(tmp_path,monkeypatch);result=q.inspect(old,'t02')
 assert result['retained_operation_count']==14 and len(result['original_checks'])==14
 assert result['original_route_completion'].startswith('NOT_CLAIMED')


def test_frozen_release_requires_complete_hash_bound_manifest(tmp_path):
 root=tmp_path/'releases/release/source';file=root/'src/example.py';file.parent.mkdir(parents=True);file.write_text('# frozen\n')
 with pytest.raises(ValueError,match='MANIFEST_REQUIRED'):q.source_namespace(root,tmp_path)
 put(root.parent/'SOURCE_MANIFEST.json',dict(root=str(root),files={'src/example.py':q.sha(file)}))
 q.source_namespace(root,tmp_path)
 file.write_text('# changed\n')
 with pytest.raises(ValueError,match='RELEASE_SOURCE_CHANGED'):q.source_namespace(root,tmp_path)
 with pytest.raises(ValueError,match='NAMESPACE_INVALID'):q.source_namespace(tmp_path/'other/source',tmp_path)


def test_shared_gap_correction_never_adopts_a_completed_t02_or_its_frozen_state(tmp_path,monkeypatch):
 old,_,_=binding_fixture(tmp_path,monkeypatch)
 q.t02_only_before_stage(['t01','t03','t04'],old)
 with pytest.raises(ValueError,match='REQUIRES_FRESH_T02_T05'):q.t02_only_before_stage(['t01','t03','t04','t02'],old)
 value=json.loads((old/'t04.json').read_bytes());scene=dict(objects=[],lineage=[dict(stage='t02')]);body=json.dumps(scene).encode();h=hashlib.sha256(body).hexdigest();(old/'runtime/artifacts'/('scene:'+h)).write_bytes(body)
 value['output_scene_ref']=dict(artifact_id='scene:'+h,sha256=h);put(old/'t04.json',value)
 with pytest.raises(ValueError,match='HAS_SHARED_GAP_STATE'):q.t02_only_before_stage(['t04'],old)


def test_snapshot_cache_change_retains_pre_t05_only_and_rejects_a_t05_result(tmp_path,monkeypatch):
 old,current,_=binding_fixture(tmp_path,monkeypatch)
 seal=json.loads((old/'PRODUCER_BINDING.json').read_bytes())
 original=Path(next(iter(seal['files']))).parents[1]
 name='src/stage_abi/loaded_geometry.py'
 for root,text in [(original,'# old cache\n'),(current,'# bounded cache\n')]:
  file=root/name;file.parent.mkdir(parents=True,exist_ok=True);file.write_text(text)
 seal['files'][str(original/name)]=q.sha(original/name);put(old/'PRODUCER_BINDING.json',seal)
 source=json.loads((old/'source.json').read_bytes());scene_ref=source['scene_ref']
 put(old/'t05.json',dict(output_scene_ref=scene_ref,stage='t05'))
 state=json.loads((old.parent/'STATUS.current.json').read_bytes())
 for stage in('t01','t03','t04','t02','t05'):
  proof=dict(status='PASS',producer_binding_sha256=q.sha(old/'PRODUCER_BINDING.json'),candidate_sha256=q.sha(old/(stage+'.json')))
  for i,mode in enumerate(('construct','1','2')):
   put(old/'audits'/stage/(mode+'.json'),proof)
   if stage=='t05':state['checks']['legacy_t05_'+mode]=dict(status='PASS',returncode=0,pid=100+i)
  put(old/'audits'/stage/'proof.json',proof)
 put(old.parent/'STATUS.current.json',state)
 monkeypatch.setattr(guard,'producer_files',lambda:[current/Path(n).relative_to(original)for n in seal['files']])
 assert q.inspect(old,'t02')['retained_operation_count']==14
 with pytest.raises(ValueError,match='SNAPSHOT_CHANGE_REQUIRES_FRESH_T05'):q.inspect(old,'t05')


def test_preparation_class_delta_cannot_change_a_shared_budget_or_geometry_helper():
 before='from .loaded_geometry import budget\nINDEX_BYTES=32\nclass SpatialQueries: pass\ndef bounds(x): return x\n'
 after=before.replace('import budget','import budget, geometry_checksum').replace('class SpatialQueries: pass','class SpatialQueries:\n def bounded(self): return True')
 q.preparation_class_delta_only(before,after,'spatial_queries')
 for changed in(after.replace('INDEX_BYTES=32','INDEX_BYTES=64'),after.replace('return x','return None')):
  with pytest.raises(ValueError,match='POLICY_OR_HELPER_CHANGED'):q.preparation_class_delta_only(before,changed,'spatial_queries')
 before='SNAPSHOT_BYTES=192\nMEMO_BYTES=32\nclass GeometrySnapshot: pass\nclass GeometryMemo: pass\n'
 after=before.replace('class GeometrySnapshot: pass','class OperandView: pass\nclass GeometrySnapshot:\n def bounded(self): return True')
 q.preparation_class_delta_only(before,after,'loaded_geometry')
 with pytest.raises(ValueError,match='POLICY_OR_HELPER_CHANGED'):q.preparation_class_delta_only(before,after.replace('MEMO_BYTES=32','MEMO_BYTES=64'),'loaded_geometry')


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


def test_pin_eviction_delta_cannot_authorize_a_spacing_change():
 before='def evict(self):\n self.weight-=self.cache.popitem(last=False)[1]\n'
 after=before.replace('[1]','[1][1]')
 q.pin_eviction_delta_only(before,after)
 with pytest.raises(ValueError,match='PIN_EVICTION_DELTA_NOT_ISOLATED'):
  q.pin_eviction_delta_only(before,after+'def clearance():\n return 0\n')


def test_t05_support_delta_cannot_change_its_original_geometry_predicates():
 after=(Path(q.__file__).with_name('export_absorption.py')).read_text()
 new=""" window=domain.buffer(-NATIVE_OWNER_OVERLAP_MM,quad_segs=64)
 support=owner.intersection(window);target=owner.union(addition)
"""
 before='\n'.join(line for line in after.splitlines()if not line.lstrip().startswith('#'))+'\n'
 before=before.replace(new," support=owner.intersection(domain.buffer(-NATIVE_OWNER_OVERLAP_MM,quad_segs=64))\n").replace(' region=target.intersection(window).union(addition)',' region=support.union(addition);target=owner.union(addition)')
 q.t05_support_delta_only(before,after)
 with pytest.raises(ValueError,match='SUPPORT_DELTA_NOT_ISOLATED'):
  q.t05_support_delta_only(before,after.replace('support.difference(owner).area<=CONTRACT.area_epsilon_mm2','True',1))


def test_completed_width_checkpoint_is_hash_bound_to_the_retained_t04(tmp_path,monkeypatch):
 old,_,_=binding_fixture(tmp_path,monkeypatch)
 proof=q.inspect(old,'t04')
 assert proof['retained_operation_count']==11
 assert 'RAW_WIDTH_CHECKPOINT.json'in proof['files']
 put(old/'RAW_WIDTH_CHECKPOINT.json',dict(forged=True))
 with pytest.raises(ValueError,match='RAW_WIDTH_CHECKPOINT_CHANGED'):q.inspect(old,'t04')


def test_t02_worker_attribution_delta_cannot_change_t04_execution():
 after=(Path(q.__file__).with_name('worker.py')).read_text()
 extra=""" elif name=='t02':
  from .width_stage_constraints import require_t02
  store=p.Store(run/'runtime');width_proof=require_t02(store,p.load(run/'t04.json')['output_scene_ref'],value)
  if width_proof is not None:value=dict(value,t04_width_fence=width_proof)
"""
 assert after.count(extra)==1
 before=after.replace(extra,'').replace("if name=='t04':\n  store=p.Store(run/'runtime');checked_scene", "if name in('t04','t02'):\n  store=p.Store(run/'runtime');checked_scene")
 q.t02_attribution_worker_delta_only(before,after)
 with pytest.raises(ValueError,match='ATTRIBUTION_DELTA_NOT_ISOLATED'):
  q.t02_attribution_worker_delta_only(before,after.replace("scope=name+'_complete'","scope='unrelated'",1))

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
