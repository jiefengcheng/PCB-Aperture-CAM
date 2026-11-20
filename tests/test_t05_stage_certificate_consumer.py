"""Adversarial stage-level controls; real store, composition and local ledger.

Only the tiny fixture's issuer callback is synthetic. The actual 160-route
qualification separately uses the original physical issuer/checker. These tests
establish that completed-construction authority cannot be used with mutated
inputs/artifacts, omitted KEEP decisions, extra copper or a changed prefix.
"""
from copy import deepcopy
import json

import pytest
from shapely import to_wkb
from shapely.geometry import box
from src.gerber_u05.pipeline import Store
from src.stage_abi.loaded_geometry import GeometrySnapshot
from src.t05_certificate_verifier import CertificateLedger, CertificateError
from src.t05_stage_certificate_consumer import StageCertificateConsumer


def fixture(tmp_path, *, seal=True):
    store = Store(tmp_path/'store')
    owner, patch, window = box(0, 0, 1, 1), box(1, .2, 1.2, .8), box(-1, -1, 3, 3)
    put = lambda shape: store.put('geometry', to_wkb(shape))
    before_ref = put(owner)
    scene = dict(source_sha256='0'*64, frame='test', units='mm', layer='F.Cu',
        viewport_mm=[-1, -1, 3, 3], findings=[], lineage=[], acceptance={},
        objects=[dict(source_id='source', kind='trace', geometry_ref=before_ref,
            original_ref=before_ref, metadata={})])
    policy = dict(stage='t05', parameters=dict(area_epsilon_mm2=1e-12))
    rows = [dict(source_id='route:A', land_ids=['source']), dict(source_id='route:KEEP', land_ids=[])]
    plan = dict(stage='t05', scene_ref=store.put_json('scene', scene), policy_ref=store.put_json('policy', policy),
        implementation='test-issuer', details=dict(routes=rows))
    ledger = CertificateLedger(dict(scene=scene, policy=policy, plan=plan),
        lambda raw: store.put('geometry', raw), lambda ref: store.get(ref, kind='geometry'))
    _, receipt = ledger.issue('route:A', owner, patch, window, patch.buffer(.01), [], [],
        lambda: dict(passed=True, failures=[]))
    patch_ref = put(patch)
    ledger.commit(receipt, 'route:A', patch_ref, owner, window)
    receipt_ref = store.put_json('t05-certificate', receipt)
    ledger.begin_replay(); ledger.consume(receipt, 'route:A', patch_ref, owner, window); ledger.finish_replay()
    grown = dict(rows[0], status='GROWN', scale=1., patch_ref=patch_ref, attachment_outcomes=[dict(status='TREATED_VERIFIED')])
    keep = dict(rows[1], status='KEEP', attachment_outcomes=[])
    from src.u05_board.coverage import addition_source_id
    output = deepcopy(scene)
    output['objects'].append(dict(source_id=addition_source_id(grown), kind='junction_addition',
        geometry_ref=patch_ref, original_ref=patch_ref, metadata=dict(origin='t05-derived-addition',
            owner_trace='route:A', predecessor_ref=plan['scene_ref'])))
    output['lineage'] += [dict(stage='t05', predecessor_ref=plan['scene_ref'], policy_ref=plan['policy_ref'],
        implementation=plan['implementation'], plan_ref=store.put_json('plan', plan))]
    authority = StageCertificateConsumer(ledger, store)
    snapshot = GeometrySnapshot(store, scene)
    # This observes the real canonical composition, not a guessed after shape.
    actual = snapshot.composed(store, output)
    authority.observe_composition(output, to_wkb(actual))
    snapshot.validate_bindings(); store.verify_reads()
    candidate = dict(status='CONSTRUCTED', before_ref=before_ref, after_ref=put(actual),
        output_scene_ref=store.put_json('scene', output), decisions=[grown, keep],
        checks=[], protected_source_refs={'source': before_ref}, evaluations=1,
        coverage=dict(targets=2, grown=1, attachment_outcomes=1))
    # Dependency accessed by construction but not needed for replay geometry.
    dependency = store.put_json('gerber-route', dict(path='fixed'))
    store.get_json(dependency)
    execution_binding = dict(scope='fixture', source='fixed')
    args = [scene, policy, plan, candidate, {'route:A': receipt_ref}, execution_binding]
    if seal:
        authority.seal(*args)
    return authority, store, args, dependency


def consume(authority, args):
    return authority.verify(*args[:4], {'scope': 'complete-source-and-all-patches'}, args[5])


def test_dedicated_path_consumes_real_artifacts_without_composition_or_geometry_replay(tmp_path, monkeypatch):
    authority, store, args, _ = fixture(tmp_path)
    monkeypatch.setattr(GeometrySnapshot, 'composed', lambda *_: pytest.fail('repeated composition'))
    from src.u05_board.coverage import CoverageAdapter
    for method in ('_operands', '_blend_addition', 'needs', '_check', 'execution'):
        monkeypatch.setattr(CoverageAdapter, method, lambda *_: pytest.fail('old adapter replay'))
    result = consume(authority, args)
    assert result == dict(passed=True, failures=[], reconstructed_patches=1, removed_area_mm2=0., verified_attachments=1)
    assert authority.ledger.counts['complete_replays'] == 2
    assert authority.ledger.counts['issuer_physical_checks'] == 1
    assert authority.diagnostics()['counts']['verifications'] == 1
    assert authority.peak_bytes < authority.limit_bytes


@pytest.mark.parametrize('change', ['keep_missing', 'keep_changed', 'order', 'patch', 'before', 'after', 'output',
    'source', 'policy', 'plan', 'binding', 'attachment', 'coverage', 'extra_copper'])
def test_changed_inputs_and_undeclared_copper_cannot_consume_completed_stage(tmp_path, change):
    authority, store, args, _ = fixture(tmp_path)
    args = deepcopy(args)
    candidate = args[3]
    if change == 'keep_missing': candidate['decisions'].pop()
    elif change == 'keep_changed': candidate['decisions'][1]['status'] = 'GROWN'
    elif change == 'order': candidate['decisions'].reverse()
    elif change == 'patch': candidate['decisions'][0]['patch_ref'] = store.put('geometry', to_wkb(box(7,7,8,8)))
    elif change in ('before', 'after', 'output'): candidate[change+'_ref' if change != 'output' else 'output_scene_ref']['sha256'] = '1'*64
    elif change == 'source': args[0]['objects'][0]['metadata']['changed'] = True
    elif change == 'policy': args[1]['parameters']['area_epsilon_mm2'] = 1.
    elif change == 'plan': args[2]['implementation'] = 'changed'
    elif change == 'binding': args[5]['source'] = 'changed'
    elif change == 'attachment': candidate['decisions'][0]['attachment_outcomes'] = []
    elif change == 'coverage': candidate['coverage']['grown'] = 0
    elif change == 'extra_copper': candidate['after_ref'] = store.put('geometry', to_wkb(box(-1,-1,3,3)))
    with pytest.raises(CertificateError, match='INPUT_CHANGED'):
        consume(authority, args)


@pytest.mark.parametrize('target', ['source', 'patch', 'before', 'after', 'nested_dependency', 'receipt', 'region', 'window', 'manifest'])
def test_actual_stored_artifact_corruption_still_fails(tmp_path, target):
    authority, store, args, dep = fixture(tmp_path)
    manifest = store.get_json(authority._seal['body']['manifest_ref'])
    cert_ref = args[4]['route:A']
    cert = store.get_json(cert_ref)
    refs = dict(source=args[0]['objects'][0]['geometry_ref'], patch=args[3]['decisions'][0]['patch_ref'],
        before=args[3]['before_ref'], after=args[3]['after_ref'], nested_dependency=dep,
        receipt=cert_ref, region=cert['body']['region_ref'], window=cert['body']['window_ref'],
        manifest=authority._seal['body']['manifest_ref'])
    (store.root/'artifacts'/refs[target]['artifact_id']).write_bytes(b'corrupted')
    with pytest.raises(ValueError): consume(authority, args)


@pytest.mark.parametrize('field', ['result', 'ledger_head', 'manifest_ref', 'composition'])
def test_stage_seal_cannot_be_rewritten_as_unsigned_success(tmp_path, field):
    authority, _, args, _ = fixture(tmp_path)
    authority._seal['body'][field] = {}
    with pytest.raises(CertificateError, match='AUTHENTICATION'): consume(authority, args)


def test_foreign_process_authority_and_unsealed_constructor_are_rejected(tmp_path):
    authority, store, args, _ = fixture(tmp_path)
    other = StageCertificateConsumer(authority.ledger, store)
    with pytest.raises(CertificateError, match='NOT_SEALED'): consume(other, args)
    other._seal = deepcopy(authority._seal)
    with pytest.raises(CertificateError, match='AUTHENTICATION'): consume(other, args)


@pytest.mark.parametrize('change', ['missing_composition', 'wrong_composition', 'extra_output', 'missing_keep', 'ledger'])
def test_incomplete_or_mismatched_construction_cannot_be_sealed(tmp_path, change):
    authority, store, args, _ = fixture(tmp_path, seal=False)
    if change == 'missing_composition': authority._composition = None
    elif change == 'wrong_composition': authority._composition['copper_sha256'] = '1'*64
    elif change == 'extra_output':
        output = store.get_json(args[3]['output_scene_ref']); output['objects'].append(deepcopy(output['objects'][-1]))
        args[3]['output_scene_ref'] = store.put_json('scene', output)
    elif change == 'missing_keep': args[3]['decisions'].pop()
    elif change == 'ledger': authority.ledger.accepted = []
    with pytest.raises(ValueError): authority.seal(*args)


def test_new_commit_after_sealing_invalidates_stage(tmp_path):
    authority, _, args, _ = fixture(tmp_path)
    authority.ledger.head = 'changed'
    with pytest.raises(CertificateError, match='CHAIN_CHANGED'): consume(authority, args)


@pytest.mark.parametrize('change', ['required_reference_blocked', 'missing_attachment', 'bad_scale', 'no_contact_forged'])
def test_original_logical_verification_guards_are_preserved_at_sealing(tmp_path, change):
    authority, store, args, _ = fixture(tmp_path, seal=False)
    scene, policy, plan, candidate = args[:4]
    if change == 'required_reference_blocked':
        plan['details']['routes'][1].update(land_ids=['source'], reference_status='GROWN')
        candidate['decisions'][1].update(land_ids=['source'], reference_status='GROWN',
            attachment_outcomes=[dict(needed=True, status='BLOCKED_CLEARANCE_OR_BOUNDARY')])
    elif change == 'missing_attachment':
        candidate['decisions'][0]['attachment_outcomes'][0]['status'] = 'MISSING_TREATMENT'
    elif change == 'bad_scale': candidate['decisions'][0]['scale'] = .123456
    elif change == 'no_contact_forged': candidate['decisions'][1]['attachment_outcomes'] = [dict(status='invented')]
    with pytest.raises(CertificateError, match='REQUIRED_REFERENCE_BLOCKED|MISSING_TREATMENT|SCALE_CHANGED|NO_CONTACT_FORGED'):
        authority.seal(*args)


def test_dedicated_consumer_keeps_exact_cell_containment(tmp_path):
    authority, _, args, _ = fixture(tmp_path)
    # Authenticity/commit coverage is checked before a committed-artifact replay
    # can touch anything. It cannot grant authority to even a tiny extra patch.
    receipt = authority.store.get_json(args[4]['route:A'])
    receipt['body']['patch_ref'] = authority.store.put('geometry', to_wkb(box(1,.2,1.2,.800000000001)))
    authority.ledger.begin_replay()
    with pytest.raises(CertificateError, match='REPLAY_CHANGED'):
        authority.ledger.consume_committed(receipt, 'route:A', receipt['body']['patch_ref'])
