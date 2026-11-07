import copy
import json
import pytest

from src.gerber_u05.land_reconstruction import reconstruct
from src.gerber_u05.component_rectangles import ComponentRectangleAdapter
from src.u04_board.search import FastRectangleAdapter
from src.stage_abi.lands import land_parameters
from src.stage_abi.store import canonical
from test_t02_shared_gaps import fixture,contexts


def constructed(tmp_path,implementation=FastRectangleAdapter):
    original,scene,store=fixture(tmp_path)
    adapter=implementation('t02');ref=store.put_json('scene',scene)
    policy=dict(stage='t02',parameters=land_parameters('t02'))
    limits=dict(max_source_objects=100,max_targets=100,max_evaluations=10000,
                max_output_bytes=10**7,max_seconds=60)
    details=adapter.plan(store,scene,policy,dict(stage='t02',scene_ref=ref,source_ids=['a','b']),limits)
    plan=dict(stage='t02',scene_ref=ref,policy_ref=store.put_json('policy',policy),
              implementation=adapter.describe()['implementation'],details=details)
    candidate=adapter.run(store,scene,policy,plan,lambda _:None)
    return scene,store,policy,plan,dict(candidate=candidate,plan=plan)


@pytest.mark.parametrize('implementation',[FastRectangleAdapter,ComponentRectangleAdapter])
def test_fresh_worker_reconstructs_same_candidate_and_verifies_without_search(tmp_path,monkeypatch,implementation):
    scene,store,policy,plan,recorded=constructed(tmp_path,implementation)
    def forbidden(*args,**kwargs):raise AssertionError('Optimizer/trial search must not run during fixed-candidate verification')
    monkeypatch.setattr('src.u04_board.search.fit_joint_rectangle',forbidden)
    monkeypatch.setattr(FastRectangleAdapter,'_trial_check',forbidden)
    adapter=implementation('t02')
    result=reconstruct(adapter,store,scene,policy,plan,recorded)
    assert canonical(result)==canonical(recorded['candidate'])
    check=adapter.verify(store,scene,policy,plan,result,{'scope':'complete-source-land-and-inclusive'},lambda _:None)
    assert check['passed'] and check['reconstructed_targets']==2


@pytest.mark.parametrize('mutation,reason',[
    ('factor','FACTORS_CHANGED'),('attempt_sha','FINAL_PROPOSAL_CHANGED'),
    ('attempt_pass','FINAL_PROPOSAL_CHANGED'),('attempt_failure','FINAL_PROPOSAL_CHANGED'),
    ('evaluations','EVALUATION_WITNESS_CHANGED'),('protected','PROTECTED_SOURCE_CHANGED'),
    ('missing_target','TARGETS_CHANGED'),('status','STATUS_CHANGED'),
    ('candidate_ref','DECISIONS_CHANGED'),('scene_check','FRESH_COMPLETE_SCENE_CHECK_CHANGED'),
    ('gap','FIXED_CANDIDATE_RECONSTRUCTION_CHANGED'),
])
def test_corrupted_constructed_checkpoint_is_rejected(tmp_path,mutation,reason):
    scene,store,policy,plan,recorded=constructed(tmp_path);bad=copy.deepcopy(recorded)
    candidate=bad['candidate'];row=candidate['decisions'][0]
    if mutation=='factor':row['pre_shared_factors'][0]=1.251
    elif mutation=='attempt_sha':row['attempts'][-1]['candidate_sha256']='0'*64
    elif mutation=='attempt_pass':row['attempts'][-1]['passed']=False
    elif mutation=='attempt_failure':row['attempts'][-1]['failures']=[{'reason':'UNRESOLVED'}]
    elif mutation=='evaluations':candidate['evaluations']+=1
    elif mutation=='protected':candidate['protected_source_refs']={}
    elif mutation=='missing_target':candidate['decisions'].pop()
    elif mutation=='status':row['status']='UNKNOWN'
    elif mutation=='candidate_ref':row['candidate_ref']=candidate['decisions'][1]['candidate_ref']
    elif mutation=='scene_check':candidate['checks']['passed']=False
    elif mutation=='gap':candidate['shared_neighbor_gaps']['zones'][0]['gap_mm']-=.01
    with pytest.raises(ValueError,match=reason):
        reconstruct(FastRectangleAdapter('t02'),store,scene,policy,plan,bad)


def test_changed_plan_is_rejected_before_reconstruction(tmp_path):
    scene,store,policy,plan,recorded=constructed(tmp_path);changed=copy.deepcopy(plan)
    changed['details']['bounds']['max_evaluations']+=1
    with pytest.raises(ValueError,match='PLAN_CHANGED'):
        reconstruct(FastRectangleAdapter('t02'),store,scene,policy,changed,recorded)


@pytest.mark.parametrize('field',['status','stage','candidate_sha256','producer_binding_sha256','source_sha256'])
def test_worker_requires_matching_successful_construction_receipt(tmp_path,monkeypatch,field):
    from src.gerber_u05 import pipeline as p,worker
    run=tmp_path/'job';(run/'audits/t02').mkdir(parents=True)
    value={'candidate':{}};binding=b'{}';source='a'*64
    (run/'t02.json').write_bytes(p.canonical(value));(run/'PRODUCER_BINDING.json').write_bytes(binding)
    (run/'source.json').write_text(json.dumps(dict(source_ref=dict(sha256=source))))
    proof=dict(status='PASS',stage='t02',candidate_sha256=p.digest(p.canonical(value)),
               producer_binding_sha256=p.digest(binding),source_sha256=source)
    proof[field]='CHANGED';(run/'audits/t02/construct.json').write_text(json.dumps(proof))
    monkeypatch.setenv('U05_WORKER_MODE','1')
    def forbidden(*args,**kwargs):raise AssertionError('Changed construction receipt must stop before stage evaluation')
    monkeypatch.setattr(p,'stage',forbidden)
    with pytest.raises(ValueError,match='SUCCESSFUL_CONSTRUCTION_CHECKPOINT_REQUIRED'):
        worker.compute(run,'t02')
