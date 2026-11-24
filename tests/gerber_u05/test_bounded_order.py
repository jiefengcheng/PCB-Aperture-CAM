"""Connection/floor custody controls for the separate bounded experiment."""
import copy
import pytest
from shapely.geometry import box
from src.gerber_u05 import bounded_order as b, pipeline as p
from src import pin_separation as pin


@pytest.fixture
def case(tmp_path, monkeypatch):
    monkeypatch.setattr(pin, 'ACTIVE', None)
    store = p.Store(tmp_path/'runtime')
    source_ref=store.put('gerber-source', b'unit-test-source; no Gerber-intake claim')
    objects=[]
    for sid,g in [('trace',box(0,0,2,.1)),('land',box(1.9,-.1,2.2,.2))]:
        ref=p.geomref(store,g)
        objects.append(dict(source_id=sid,kind='stroke' if sid=='trace' else 'land',
                            original_ref=ref,geometry_ref=ref,metadata={}))
    scene=dict(source_sha256=source_ref['sha256'],objects=objects,lineage=[])
    binding=dict(source_ref=source_ref,scene_ref=store.put_json('scene',scene))
    stage=dict(native_trace_source_ids_by_route={'JR-test':['trace']},hybrid_components={
        'frozen_endpoint_obligations':dict(passed=False,failures=[{'reason':'RETAINED_DIAGNOSTIC'}]),
        'corner_smoothing':dict(unresolved=1)})
    return store,binding,scene,stage


def test_later_growth_preserves_trace_and_retains_diagnostics(case):
    store,binding,source,stage=case
    _,material,_=p.operands(store,source)
    material['land']=material['land'].buffer(.02)
    final=store.get_json(p.artifact_scene(store,source,material,'unit-test'),kind='scene')
    proof=b.reconcile(store,binding,source,source,final,stage,['land'])
    assert proof['passed'] and proof['terminal_attachments'][0]['passed']
    assert proof['accepted_t03'] is False and proof['publication_ready'] is False
    assert proof['inherited_endpoint_diagnostics']['passed'] is False


def test_trimmed_trace_is_rejected_even_when_still_connected(case):
    store,binding,source,stage=case
    _,material,_=p.operands(store,source);material['trace']=box(.01,0,2,.1)
    final=store.get_json(p.artifact_scene(store,source,material,'unit-test'),kind='scene')
    proof=b.reconcile(store,binding,source,source,final,stage,['land'])
    assert not proof['passed']
    assert any(f['reason']=='CONSTRUCTED_TRACE_FLOOR_CHANGED' for f in proof['failures'])


def test_disconnected_terminal_and_core_loss_rejected(case):
    store,binding,source,stage=case
    _,material,_=p.operands(store,source);material['land']=box(3,0,4,1)
    final=store.get_json(p.artifact_scene(store,source,material,'unit-test'),kind='scene')
    proof=b.reconcile(store,binding,source,source,final,stage,['land'])
    assert not proof['passed']
    assert {f['reason'] for f in proof['failures']} >= {'TERMINAL_CORE_REMOVED','ORIGINAL_TERMINAL_ATTACHMENT_LOST'}


def test_mutated_pose_metadata_rejects_before_reconciliation(case):
    store,binding,source,stage=case
    final=copy.deepcopy(source);final['objects'][0]['metadata']['route_points_mm']=[[0,0],[1,1]]
    with pytest.raises(ValueError,match='IDENTITY_OR_POSE'):
        b.reconcile(store,binding,source,source,final,stage,['land'])


def test_missing_source_custody_rejects(case):
    store,binding,source,stage=case
    final=copy.deepcopy(source);final['objects'].pop()
    with pytest.raises(ValueError,match='IDENTITY_OR_POSE'):
        b.require_source(store,binding,final)


def test_retained_artifacts_are_rehashed_at_exit(tmp_path):
    from src.gerber_u05.profile_intake import EvidenceStore
    retained=tmp_path/'retained'
    producer=p.Store(retained/'runtime')
    ref=producer.put('gerber-source',b'original immutable bytes')
    store=b.ExperimentStore(tmp_path/'experiment/runtime',EvidenceStore(retained))
    assert store.get(ref)==b'original immutable bytes'
    (retained/'runtime/artifacts'/ref['artifact_id']).write_bytes(b'tampered')
    with pytest.raises(ValueError,match='ARTIFACT_CHANGED'):
        store.verify_reads()
