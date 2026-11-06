import json,hashlib
from pathlib import Path
import pytest
from src.gerber_u05.qualification_tail import validate_export,verify_code

def packet(tmp_path):
 run=tmp_path/'run';(run/'export').mkdir(parents=True);(run/'negative_controls').mkdir()
 def save(path,value):path.write_text(json.dumps(value))
 body=b'checked native prefix';(run/'export/top.art.gbr').write_bytes(body)
 save(run/'PRODUCER_BINDING.json',{'immutable':'producer'})
 producer=hashlib.sha256((run/'PRODUCER_BINDING.json').read_bytes()).hexdigest();bodysha=hashlib.sha256(body).hexdigest()
 proof=dict(status='PASS',generated_sha256=bodysha,geometry_producer_binding_sha256=producer)
 for m in('1','2'):save(run/'export'/('proof_'+m+'.json'),proof)
 save(run/'export/ledger.json',dict(generated_sha256=bodysha,geometry_producer_binding_sha256=producer))
 save(run/'negative_controls/RESULT.json',dict(status='PASS',generated_sha256=bodysha))
 keys=('connected_export_construct','connected_export_1','connected_export_2','connected_controls_all')
 return run,dict(checks={k:dict(status='PASS',returncode=0,pid=i+1)for i,k in enumerate(keys)})

def test_actual_prefix_processes_and_separate_evaluations_are_required(tmp_path):
 run,state=packet(tmp_path);assert len(validate_export(run,state))==4
 state['checks']['connected_export_2']['pid']=state['checks']['connected_export_1']['pid']
 with pytest.raises(ValueError,match='WORKERS_NOT_SEPARATE'):validate_export(run,state)

def test_changed_native_body_cannot_reuse_old_proofs(tmp_path):
 run,state=packet(tmp_path);(run/'export/top.art.gbr').write_bytes(b'changed')
 with pytest.raises(ValueError,match='PAIRED_PROOF_CHANGED'):validate_export(run,state)

def test_proof_cannot_be_rebound_to_another_producer(tmp_path):
 run,state=packet(tmp_path);(run/'PRODUCER_BINDING.json').write_text('{}')
 with pytest.raises(ValueError,match='PRODUCER_BINDING_CHANGED'):validate_export(run,state)

def test_geometry_code_change_requires_new_native_qualification(tmp_path):
 old=tmp_path/'old';current=tmp_path/'current';(old/'src').mkdir(parents=True);(current/'src').mkdir(parents=True)
 before=old/'src/geometry.py';before.write_text('geometry=1');(current/'src/geometry.py').write_text('geometry=2')
 original={'files':{str(before):hashlib.sha256(before.read_bytes()).hexdigest()}}
 with pytest.raises(ValueError,match='GEOMETRY_OR_CHECK_CODE_CHANGED'):verify_code(original,old,current)

def test_unknown_added_producer_is_rejected(tmp_path):
 old=tmp_path/'old';current=tmp_path/'current';(old/'src').mkdir(parents=True);(current/'src').mkdir(parents=True)
 before=old/'src/geometry.py';before.write_text('geometry=1');(current/'src/geometry.py').write_bytes(before.read_bytes())
 (current/'src/extra_geometry.py').write_text('geometry=2')
 original={'files':{str(before):hashlib.sha256(before.read_bytes()).hexdigest()}}
 with pytest.raises(ValueError,match='UNKNOWN_PRODUCER_ADDED'):verify_code(original,old,current)
