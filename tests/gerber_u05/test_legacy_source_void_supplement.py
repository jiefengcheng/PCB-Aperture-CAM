from pathlib import Path
import hashlib,json
import pytest
from src.gerber_u05 import pipeline as p,legacy_prefix as q,source_assembly
from src.t04_settings import capture_job
from test_source_assembly import RAW


def case(tmp_path,monkeypatch):
 from src import component_clearance,source_channel_scope,pin_separation,t04_width_fence,t02_shared_gaps
 for module in (component_clearance,source_channel_scope,pin_separation,t04_width_fence,t02_shared_gaps):monkeypatch.setattr(module,'ACTIVE',None)
 run=tmp_path/'legacy';store=p.Store(run/'runtime');assembled,_=source_assembly.reconstruct(RAW,store);binding=p.build_source(store,assembled);scene=store.get_json(binding['scene_ref'],kind='scene');p.save(run/'source.json',binding);p.save(run/'LEGACY_REFERENCE_JOB.json',{});p.save(run/'SOURCE_ASSEMBLY_BINDING.json',{});capture_job(run);p.initialize(store,binding,scene);value=p.run_t04(store,scene);p.save(run/'t03.json',dict(output_scene_ref=binding['scene_ref']));p.save(run/'RAW_WIDTH_CHECKPOINT.json',value);return run,store,value


def hashes(run):return {str(f.relative_to(run)):hashlib.sha256(f.read_bytes()).hexdigest()for f in run.rglob('*')if f.is_file()}


def test_supplement_checks_both_contexts_and_writes_no_old_artifact(tmp_path,monkeypatch):
 run,_,_=case(tmp_path,monkeypatch);before=hashes(run);proof=q.source_void_supplement(run)
 assert proof['nominal_route_bytes_identical']
 assert [row['scope']for row in proof['records']]==['physical','functional']
 assert all(row['accepted_trials_checked']>0 and all(v['passed']for v in row['complete'].values())for row in proof['records'])
 assert hashes(run)==before
 proof['status']='caller changed returned copy'
 assert q.source_void_supplement(run)['status']=='ORIGINAL_WIDTH_GEOMETRY_AND_FRESH_SOURCE_VOID_CHECKS_PASS'


def test_changed_nominal_source_geometry_cannot_be_retained(tmp_path,monkeypatch):
 run,store,value=case(tmp_path,monkeypatch);q.source_void_supplement(run);scene=store.get_json(value['output_scene_ref'],kind='scene');sid=next(iter(value['part_factors']));row=next(r for r in scene['objects']if r['source_id']==sid);row['geometry_ref']=p.geomref(store,p.geometry(store,row['geometry_ref']).buffer(.01));value['output_scene_ref']=store.put_json('scene',scene);(run/'RAW_WIDTH_CHECKPOINT.json').write_bytes(p.canonical(value))
 with pytest.raises(ValueError,match='NOMINAL_ROUTE_CHANGED'):q.source_void_supplement(run)


def test_ladder_or_source_part_factor_tampering_invalidates_cached_report(tmp_path,monkeypatch):
 run,_,value=case(tmp_path,monkeypatch);q.source_void_supplement(run);sid=next(s for s,v in value['part_factors'].items()if v!=1.);value['part_factors'][sid]=1.;(run/'RAW_WIDTH_CHECKPOINT.json').write_bytes(p.canonical(value))
 with pytest.raises(ValueError,match='PART_FACTORS_CHANGED'):q.source_void_supplement(run)


def test_missing_assembly_authority_never_qualifies_legacy_width(tmp_path,monkeypatch):
 run,_,_=case(tmp_path,monkeypatch);(run/'SOURCE_ASSEMBLY_BINDING.json').unlink()
 with pytest.raises(ValueError,match='REQUIRES_ASSEMBLED_LADDER'):q.source_void_supplement(run)
