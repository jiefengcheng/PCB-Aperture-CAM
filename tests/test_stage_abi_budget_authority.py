import time
from tests.test_stage_abi_service import environment


def test_complete_output_budget_includes_events_and_metadata_not_just_copper(tmp_path):
 s,service,doc,req,prepare,_=environment(tmp_path,dict(max_output_bytes=32));plan,auth,scope=prepare();before=s.get(doc['profiles']['spindle']['scene_refs'][0]);r=service.dispatch(req('run',dict(output_scope_ref=scope),plan_ref=plan,authorization_ref=auth,idempotency_key='small-budget'));assert r['error']['code']=='BUDGET_EXHAUSTED';assert s.get(doc['profiles']['spindle']['scene_refs'][0])==before
 jobs=list((s.root/'jobs').iterdir());assert len(jobs)==1 and s.get_json(__import__('json').loads(jobs[0].read_text())['result_ref'])['status']=='FAIL'

def test_deadline_is_checked_after_a_slow_geometry_call_before_publication(tmp_path,monkeypatch):
 import src.stage_abi.spindle as module
 original=module.fit_spindle_blend
 def slow(*a,**kw):time.sleep(1.1);return original(*a,**kw)
 monkeypatch.setattr(module,'fit_spindle_blend',slow);s,service,doc,req,prepare,_=environment(tmp_path,dict(max_seconds=1));plan,auth,scope=prepare();r=service.dispatch(req('run',dict(output_scope_ref=scope),plan_ref=plan,authorization_ref=auth,idempotency_key='deadline'));assert r['error']['code']=='BUDGET_EXHAUSTED'

def test_changed_registered_bounds_invalidate_existing_plan(tmp_path):
 s,service,doc,req,prepare,_=environment(tmp_path);plan,auth,scope=prepare();doc['profiles']['spindle']['bounds_ref']=s.put_json('bounds',dict(max_seconds=1));r=service.dispatch(req('run',dict(output_scope_ref=scope),plan_ref=plan,authorization_ref=auth,idempotency_key='changed'));assert r['error']['code']=='STALE_PLAN';assert not list((s.root/'jobs').iterdir())

def test_verifier_must_return_a_literal_boolean_not_a_truthy_status(tmp_path,monkeypatch):
 s,service,doc,req,prepare,verifier=environment(tmp_path);plan,auth,scope=prepare();r=service.dispatch(req('run',dict(output_scope_ref=scope),plan_ref=plan,authorization_ref=auth,idempotency_key='construct'));candidate=r['result']['result']['candidate_ref'];adapter=service.adapters['spindle'];monkeypatch.setattr(adapter,'verify',lambda *a,**kw:{'passed':'PASS'});proof=s.put_json('proof-scope',dict(scope='complete-source-and-all-patches'));v=service.dispatch(req('verify',dict(candidate_ref=candidate,verifier_ref=verifier,proof_scope_ref=proof),plan_ref=plan,authorization_ref=auth,idempotency_key='bad-bool'));assert v['error']['code']=='EXPLICIT_GEOMETRY_VERDICT_REQUIRED'
