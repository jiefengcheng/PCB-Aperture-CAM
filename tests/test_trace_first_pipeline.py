"""Negative controls for stage ordering, source custody and dependent-stage stops."""
import json
from pathlib import Path
import pytest
from shapely.geometry import box
from shapely import to_wkb
from src.trace_first_pipeline import TraceFirstPipeline,ORDER,digest,read,write,inventory,verify_files

def case(tmp_path,monkeypatch):
 (tmp_path/'out').mkdir();source=tmp_path/'source';source.write_text('bound source')
 monkeypatch.setattr(TraceFirstPipeline,'check_protected',lambda self:[])
 c=dict(schema='prepared-native-region-pipeline/1',sequence=list(ORDER),t03_mode='growth-only-no-route-change',profile='round-class-full-route-width-whole-rectangle-spindle/1',protected_freezes=[dict(crop=c) for c in ['C01','C02','C03']],inputs={'source':dict(path='source',sha256=digest(source))})
 return c,source

def stages(corrupt=None):
 def adapter(stage):
  def run(out,inputs):
   p=out/stage;p.mkdir();g=box(0,0,1,1);before=to_wkb(g);after=before
   if corrupt==stage:before=to_wkb(box(0,0,2,2))
   (p/'before.wkb').write_bytes(before);(p/'after.wkb').write_bytes(after)
   write(p/'RESULT.json',dict(after_sha256=digest(p/'after.wkb'),route_changes=0,growth_check_passed=True))
  return run
 return {s:adapter(s) for s in ORDER}

def test_sequence_and_exact_predecessor(tmp_path,monkeypatch):
 c,_=case(tmp_path,monkeypatch);out=tmp_path/'out/pass';r=TraceFirstPipeline(tmp_path,c,out).execute(stages());assert r['sequence']==list(ORDER);assert r['owner_acceptance']=='NOT_GRANTED_BY_PIPELINE';assert len(read(out/'STAGE_RECEIPTS.json'))==5

def test_broken_predecessor_retains_failed_stage_and_stops(tmp_path,monkeypatch):
 c,_=case(tmp_path,monkeypatch);out=tmp_path/'out/fail'
 with pytest.raises(ValueError,match='EXACT_PREDECESSOR'):TraceFirstPipeline(tmp_path,c,out).execute(stages('T04'))
 assert (out/'T04').exists() and not (out/'T02').exists();assert read(out/'FAILURE.json')['stage']=='T04'

def test_changed_source_rejected_before_output(tmp_path,monkeypatch):
 c,source=case(tmp_path,monkeypatch);source.write_text('changed')
 with pytest.raises(ValueError,match='PINNED_INPUT'):TraceFirstPipeline(tmp_path,c,tmp_path/'out/x')
 assert not (tmp_path/'out/x').exists()

def test_no_skipped_or_reordered_stage(tmp_path,monkeypatch):
 c,_=case(tmp_path,monkeypatch);c['sequence']=['T01','T02','T03','T04','T05']
 with pytest.raises(ValueError,match='EXACT_TRACE_FIRST'):TraceFirstPipeline(tmp_path,c,tmp_path/'out/x')

def test_unknown_route_repair_mode_rejects(tmp_path,monkeypatch):
 c,_=case(tmp_path,monkeypatch);c['t03_mode']='assume repair not needed'
 with pytest.raises(ValueError,match='ROUTE_REPAIR'):TraceFirstPipeline(tmp_path,c,tmp_path/'out/x')

def test_changed_inputs_between_stages_prevents_dependent_work(tmp_path,monkeypatch):
 c,source=case(tmp_path,monkeypatch);a=stages();first=a['T01']
 def changed(out,inputs):first(out,inputs);source.write_text('changed after first stage')
 a['T01']=changed;out=tmp_path/'out/x'
 with pytest.raises(ValueError,match='PINNED_INPUT'):TraceFirstPipeline(tmp_path,c,out).execute(a)
 assert not (out/'T03').exists()

def test_symlink_and_escape_evidence_reject(tmp_path):
 target=tmp_path/'x';target.write_text('x');folder=tmp_path/'scope';folder.mkdir();(folder/'link').symlink_to(target)
 with pytest.raises(ValueError,match='SYMLINK'):inventory(folder)
 with pytest.raises(ValueError,match='INPUT_FILE'):verify_files(folder,{'../x':digest(target)})

def test_missing_growth_verdict_stops_T03(tmp_path,monkeypatch):
 c,_=case(tmp_path,monkeypatch);a=stages();f=a['T03']
 def uncertain(out,inputs):
  f(out,inputs);p=out/'T03/RESULT.json';r=read(p);r['growth_check_passed']=None;write(p,r)
 a['T03']=uncertain;out=tmp_path/'out/x'
 with pytest.raises(ValueError,match='T03_NO_CHANGE'):TraceFirstPipeline(tmp_path,c,out).execute(a)
 assert not (out/'T04').exists()

def test_real_frozen_manifest_cannot_be_changed(tmp_path):
 from src.trace_first_pipeline import frozen_fingerprint
 p=tmp_path/'f';(p/'frozen').mkdir(parents=True);(p/'frozen/a').write_text('accepted')
 write(p/'SHA256SUMS.json',{'a':digest(p/'frozen/a')});write(p/'FREEZE_RECEIPT.json',dict(manifest_sha256=digest(p/'SHA256SUMS.json')));entry=dict(path='f',receipt_sha256=digest(p/'FREEZE_RECEIPT.json'))
 assert frozen_fingerprint(tmp_path,entry)['files']==1
 write(p/'SHA256SUMS.json',{})
 with pytest.raises(ValueError,match='FROZEN_MANIFEST'):frozen_fingerprint(tmp_path,entry)

def test_final_stage_input_mutation_is_detected(tmp_path,monkeypatch):
 c,source=case(tmp_path,monkeypatch);a=stages();last=a['T05']
 def changed(out,inputs):last(out,inputs);source.write_text('changed last')
 a['T05']=changed;out=tmp_path/'out/x'
 with pytest.raises(ValueError,match='PINNED_INPUT'):TraceFirstPipeline(tmp_path,c,out).execute(a)
 assert not (out/'PIPELINE_RECEIPT.json').exists()

def test_saved_replay_copies_only_hash_bound_files(tmp_path):
 from src.trace_first_pipeline import copy_bound
 source=tmp_path/'source';source.mkdir();(source/'bound').write_text('yes');(source/'unbound').write_text('no')
 out=tmp_path/'copy';copy_bound(source,out,{'bound':digest(source/'bound')});assert (out/'bound').exists() and not (out/'unbound').exists()

def test_construction_requires_source_role_ledger_before_any_stage():
 from tools.run_trace_first_pipeline import adapters
 with pytest.raises(ValueError,match='SOURCE_ELIGIBILITY_DISPOSITIONS_REQUIRED'):adapters({}, {})
