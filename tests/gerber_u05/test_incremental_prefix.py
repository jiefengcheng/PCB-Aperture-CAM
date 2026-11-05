from pathlib import Path
import hashlib,json
import pytest
from src.gerber_u05.prefix import pipeline_prefix_same,verify_code
from src.gerber_u05 import guard


def test_only_t05_algorithm_and_isolated_adapter_import_may_change():
 old='from src.u05_board.coverage import CoverageAdapter\ndef run_t04():return 4\ndef run_t05():return 5\n'
 new='from .prior_copper import CoverageAdapter\ndef run_t04():return 4\ndef run_t05():return 6\n'
 assert pipeline_prefix_same(old,new)['status']=='UNCHANGED_UPSTREAM_AST'
 with pytest.raises(ValueError,match='UPSTREAM_PIPELINE'):pipeline_prefix_same(old,new.replace('return 4','return 7'))
 with pytest.raises(ValueError,match='UPSTREAM_PIPELINE'):pipeline_prefix_same(old,new+'\nrun_t04=lambda:9\n')


def source_pair(tmp_path):
 old=tmp_path/'old';new=tmp_path/'new';relative='contracts/clearance/settings.json'
 for root in(old,new):(root/relative).parent.mkdir(parents=True);(root/relative).write_text('{"nominal":0.04}')
 file=old/relative;original={'files':{str(file):hashlib.sha256(file.read_bytes()).hexdigest()}}
 return old,new,relative,original


def test_policy_change_invalidates_prefix_reuse(tmp_path):
 old,new,relative,original=source_pair(tmp_path);assert verify_code(original,new,old)==[]
 (new/relative).write_text('{"nominal":0.05}')
 with pytest.raises(ValueError,match='UPSTREAM_DEPENDENCY_CHANGED'):verify_code(original,new,old)


def test_original_producer_tampering_is_not_a_cache_hit(tmp_path):
 old,new,relative,original=source_pair(tmp_path);(old/relative).write_text('changed')
 with pytest.raises(ValueError,match='ORIGINAL_PRODUCER_CHANGED'):verify_code(original,new,old)


def test_unrecognized_geometry_change_cannot_use_equivalence_exception(tmp_path):
 old=tmp_path/'old';new=tmp_path/'new';relative='src/native_boundary_metric.py'
 for root in(old,new):(root/relative).parent.mkdir(parents=True);(root/relative).write_text('old')
 file=old/relative;original={'files':{str(file):hashlib.sha256(file.read_bytes()).hexdigest()}};(new/relative).write_text('return zero for everything')
 with pytest.raises(ValueError,match='UPSTREAM_DEPENDENCY_CHANGED'):verify_code(original,new,old)


def test_reuse_binding_is_itself_a_hash_bound_job_input(tmp_path,monkeypatch):
 from src.gerber_u05.pipeline import save
 monkeypatch.setattr(guard,'producer_files',lambda:[])
 save(tmp_path/'source.json',{'source':'raw'})
 save(tmp_path/'REUSED_PREFIX_BINDING.json',{'scope':'declared-prefix'})
 guard.seal(tmp_path,'fixture')
 seal=json.loads((tmp_path/'PRODUCER_BINDING.json').read_bytes())
 assert str(tmp_path/'REUSED_PREFIX_BINDING.json')in seal['job_inputs']
 (tmp_path/'REUSED_PREFIX_BINDING.json').write_text('{"scope":"different"}')
 with pytest.raises(ValueError,match='JOB_INPUT_CHANGED'):guard.verify_sources(tmp_path)
