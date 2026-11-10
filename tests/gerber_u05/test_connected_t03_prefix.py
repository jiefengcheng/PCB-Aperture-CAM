from pathlib import Path
import pytest
from src.gerber_u05 import prefix,incremental
from src.gerber_u05.pipeline import save


def test_only_explicit_retention_boundaries_are_supported():
 assert len(prefix.operation_keys(('t01','t03')))==29
 assert len(prefix.operation_keys(prefix.STAGES))==35
 assert not any(k.startswith('connected_t04')for k in prefix.operation_keys(('t01','t03')))
 assert len(prefix.operation_keys(()))==23
 assert len(prefix.operation_keys(incremental.stages_before('t05')))==38
 for stages in [('t01',),('t01','t04'),('t01','t03','t04'),(*prefix.EXPORT_PREFIX,'export')]:
  with pytest.raises(ValueError,match='BOUNDARY_UNSUPPORTED'):prefix.operation_keys(stages)


@pytest.mark.parametrize('summary',[
 {'moved':1,'disposition':'NO_CHANGE_REQUIRED'},
 {'moved':0,'disposition':'MOVED'},{}])
def test_retained_t03_must_be_complete_zero_movement(tmp_path,summary):
 save(tmp_path/'t03.json',{'summary':summary})
 with pytest.raises(ValueError,match='MOVEMENT_REQUIRES_FRESH'):prefix.require_retained_t03(tmp_path)


@pytest.mark.parametrize('relative',sorted(prefix.WIDTH_CORRECTION))
def test_exact_width_correction_reuses_only_t03_and_rejects_extra_edits(tmp_path,monkeypatch,relative):
 root=Path(__file__).resolve().parents[2];old=tmp_path/'old';new=tmp_path/'new'
 source=old/relative;target=new/relative
 source.parent.mkdir(parents=True);target.parent.mkdir(parents=True)
 source.write_bytes(b'old immutable producer fixture')
 target.write_bytes((root/relative).read_bytes())
 before,after=prefix.WIDTH_CORRECTION[relative];real_sha=prefix.sha
 assert real_sha(target)==after
 # Model the independently hash-verified original producer; the new code's
 # real bytes, exact allowance and tamper rejection are exercised below.
 monkeypatch.setattr(prefix,'sha',lambda file:before if Path(file)==source else real_sha(file))
 original={'files':{str(source):before}}
 assert prefix.verify_code(original,new,old,stages=('t01','t03'))
 with pytest.raises(ValueError,match='UPSTREAM_DEPENDENCY_CHANGED'):prefix.verify_code(original,new,old)
 target.write_bytes(target.read_bytes()+b'\nPOLICY_CHANGED=True\n')
 with pytest.raises(ValueError,match='UPSTREAM_DEPENDENCY_CHANGED'):prefix.verify_code(original,new,old,stages=('t01','t03'))


class Coordinator:
 def __init__(self,job):self.job=job;self.calls=[]
 def execute(self,run,stage,modes):
  self.calls.append((stage,tuple(modes)))
  for mode in modes:save(run/'audits'/stage/(mode+'.json'),{'status':'PASS','stage':stage})


def test_t03_continuation_runs_all_three_fresh_stages_and_prior_fence(tmp_path,monkeypatch):
 from src.gerber_u05 import width_prior
 run=tmp_path/'connected';coordinator=Coordinator(tmp_path);fences=[]
 monkeypatch.setattr(width_prior,'verify',lambda old,new:fences.append((old,new)))
 incremental.continue_stages(coordinator,run,'t03')
 assert coordinator.calls==[(s,m)for s in('t04','t02','t05')for m in(('construct',),('1','2'))]
 assert fences==[(tmp_path/'legacy',run)]


def test_default_t02_continuation_runs_only_t05(tmp_path):
 coordinator=Coordinator(tmp_path)
 incremental.continue_stages(coordinator,tmp_path/'connected','t02')
 assert coordinator.calls==[('t05',('construct',)),('t05',('1','2'))]


def test_mismatched_native_proofs_stop_before_later_stages(tmp_path):
 class Bad(Coordinator):
  def execute(self,run,stage,modes):
   self.calls.append((stage,tuple(modes)))
   for mode in modes:save(run/'audits'/stage/(mode+'.json'),{'status':'FAIL'if mode=='2'else'PASS','stage':stage})
 coordinator=Bad(tmp_path)
 with pytest.raises(ValueError,match='FRESH_PAIRED_STAGE_PROOFS_DIFFER:t04'):
  incremental.continue_stages(coordinator,tmp_path/'connected','t03')
 assert {s for s,_ in coordinator.calls}=={'t04'}


def test_legacy_ancestry_keeps_distinct_stage_producers_and_rejects_forgery(tmp_path):
 import json
 run=tmp_path/'new/connected';evidence=run/'prefix_evidence';legacy=evidence/'legacy';reference=evidence/'reference';old=tmp_path/'old/connected'
 records={k:{'status':'PASS','returncode':0,'pid':i+1}for i,k in enumerate(prefix.operation_keys(('t01','t03')))}
 source={'source_ref':{'sha256':'raw-source'}}
 save(legacy/'source.json',source);save(reference/'source.json',source)
 authority=legacy/'REUSED_LEGACY_BINDING.json';save(authority,{'original':{'stages':['t01','t03','t04','t02']}})
 save(legacy/'PRODUCER_BINDING.json',{'source_binding_sha256':prefix.sha(legacy/'source.json'),'job_inputs':{str(authority):prefix.sha(authority)}})
 save(reference/'PRODUCER_BINDING.json',{'source_binding_sha256':prefix.sha(reference/'source.json')})
 producers={s:'generation-'+str(i//2)for i,s in enumerate(('t01','t03','t04','t02','t05'))}
 for stage,producer in producers.items():
  save(legacy/(stage+'.json'),{'stage':stage})
  proof={'status':'PASS','producer_binding_sha256':producer,'source_sha256':'raw-source','candidate_sha256':prefix.sha(legacy/(stage+'.json'))}
  for mode in('construct','1','2'):save(legacy/'audits'/stage/(mode+'.json'),proof)
 supplement={'status':'PASS','source_sha256':'raw-source','stage_result_sha256':prefix.sha(legacy/'t01.json')}
 for mode in('1','2'):save(legacy/'audits/t01'/('supplement_'+mode+'.json'),supplement)
 for folder,modes in((legacy,('1','2')),(reference,('construct','1','2'))):
  (folder/'export').mkdir();(folder/'export/top.art.gbr').write_bytes(b'qualified gerber fixture')
  proof={'status':'PASS','generated_sha256':prefix.sha(folder/'export/top.art.gbr')}
  for mode in modes:save(folder/'export'/('proof_'+mode+'.json'),proof)
 inspection={'original_run':str(old.parent/'legacy'),'original_producer_binding_sha256':prefix.sha(legacy/'PRODUCER_BINDING.json'),'source_binding_sha256':prefix.sha(legacy/'source.json'),'source_sha256':'raw-source','stages':list(producers),'retained_operation_count':17,'original_checks':{k:v for k,v in records.items()if k.startswith('legacy_')and 'export'not in k},'files':{'source.json':prefix.sha(legacy/'source.json')},'stage_producer_bindings':producers}
 inspection_path=evidence/'ORIGINAL_LEGACY_PREFIX_PROOF.json';save(inspection_path,inspection)
 binding={'original_run':str(old),'source_sha256':'raw-source','original_checks':records,'retained_operation_count':29,'reused_stages':['t01','t03']}
 assert prefix.verify_predecessor_families(run,binding)['retained_operations']==29
 # A parent's single producer must never replace the actual stage producer.
 inspection['stage_producer_bindings']['t02']='wrong-immediate-parent'
 inspection_path.write_text(json.dumps(inspection))
 with pytest.raises(ValueError,match='REUSED_LEGACY_STAGE_PROOF_CHANGED:t02'):prefix.verify_predecessor_families(run,binding)


@pytest.mark.parametrize('relative',sorted(prefix.SOURCE_VOID_T04_ONLY))
def test_source_void_t04_delta_cannot_retain_old_width_stages(tmp_path,monkeypatch,relative):
 root=Path(__file__).resolve().parents[2];old=tmp_path/'old';new=tmp_path/'new';source=old/relative;target=new/relative;source.parent.mkdir(parents=True);target.parent.mkdir(parents=True);source.write_bytes(b'old qualified upstream fixture');target.write_bytes((root/relative).read_bytes());before=prefix.SOURCE_VOID_T04_ONLY[relative][0][0];after=prefix.SOURCE_VOID_T04_ONLY[relative][1];real_sha=prefix.sha;assert real_sha(target)==after
 monkeypatch.setattr(prefix,'sha',lambda f:before if Path(f)==source else real_sha(f));original={'files':{str(source):before}}
 assert prefix.verify_code(original,new,old,stages=('t01','t03'))
 with pytest.raises(ValueError,match='UPSTREAM_DEPENDENCY_CHANGED'):prefix.verify_code(original,new,old)
 target.write_bytes(target.read_bytes()+b'\nINVALID_POLICY=True\n')
 with pytest.raises(ValueError,match='UPSTREAM_DEPENDENCY_CHANGED'):prefix.verify_code(original,new,old,stages=('t01','t03'))


@pytest.mark.parametrize('stages,count,fresh',[(('t01','t03'),29,'T04, T02 and T05'),(prefix.STAGES,35,'T05 is newly'),(prefix.EXPORT_PREFIX,38,'both actual-file evaluations')])
def test_connected_visual_reports_the_actual_retained_boundary(stages,count,fresh):
 value={'reused_stages':list(stages),'retained_operation_count':count};text=prefix.connected_visual_evidence(value)
 assert str(count)in text and fresh in text
 value['retained_operation_count']=count+3
 with pytest.raises(ValueError,match='VISUAL_REUSED_EVIDENCE_SCOPE_CHANGED'):prefix.connected_visual_evidence(value)
