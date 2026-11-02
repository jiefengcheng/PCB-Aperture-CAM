"""Same per-slice observations and native receipts, without model-authored JSON."""
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from tools.pcb_c01_operator import Operator, STEPS, sha
from tools.t01_route_client import encode


@pytest.fixture
def operator(tmp_path):
    class Native:
        root = tmp_path
        setup = {'route_id': 'test', 'native': {'runtime': 'test'}}
        position = 0
        pending = None
        calls = []
        notes = []
        def call(self, operation, args):
            self.calls.append(operation)
            assert operation == 'native_route.verify_receipt'
            return {'receipt_sha256': self.pending['receipt_sha256']}
        def invoke(self, operation, attempt, audit=None):
            self.calls.append(operation)
            if operation == 'native_route.info':
                return dict(native=self.setup['native'], pending_audit=self.pending['attempt'] if self.pending else None,
                    next_operation=obj.steps[self.position] if self.position < len(obj.steps) else None,
                    accepted_operations=list(obj.steps[:self.position]),
                    status=obj.complete_status if self.position == len(obj.steps) else 'READY')
            if operation == 'native_route.audit':
                assert audit['response_sha256'] == self.pending['result']['raw_response_sha256']
                assert audit['observed'] == self.pending['result']['facts']
                self.notes.append(audit['note'])
                if audit['verdict'] != 'PASS':
                    raise ValueError('OPERATOR_AUDIT_MISMATCH')
                folder = self.root/'audits'/str(self.position)
                folder.mkdir(parents=True)
                (folder/'request.json').write_bytes(encode(dict(arguments=dict(attempt_id=attempt, audit=audit))))
                self.pending = None; self.position += 1
                return {'status': 'PASS_SLICE_OBSERVATION_AUDIT'}
            assert operation == obj.steps[self.position] and self.pending is None
            folder = self.root/'attempts'/attempt; (folder/'abi').mkdir(parents=True)
            facts = dict(passed=True, phase=self.position+1)
            raw = folder/'abi/stdout.json'
            raw.write_bytes(encode(dict(result=dict(facts=facts, audits={'pixels': 1378560}, controls=['four expected rejections']))))
            receipt = folder/'receipt.json'; receipt.write_bytes(encode(dict(files={'abi/stdout.json': sha(raw.read_bytes())})))
            result = dict(facts=facts, raw_response_path=str(raw), raw_response_sha256=sha(raw.read_bytes()),
                audit_required=dict(verdict='PASS', response_sha256=sha(raw.read_bytes()), observed=facts, note='pending'))
            self.pending = dict(result=result, receipt_path=str(receipt), receipt_sha256=sha(receipt.read_bytes()), attempt=attempt, error=None)
            return self.pending
    obj = Operator.__new__(Operator); obj.client = Native(); obj.binding_blob = b'fixed binding'
    obj.ui = tmp_path/'operator_ui'; obj.state_path = obj.ui/'current.json'
    out = tmp_path/'render_output'; out.mkdir()
    (out/'index.html').write_bytes(b'<!doctype html>test')
    (out/'comparison.png').write_bytes(b'\x89PNG\r\n\x1a\n'+b'\0'*8+(2584).to_bytes(4,'big')+(1267).to_bytes(4,'big'))
    (out/'render.json').write_bytes(encode(dict(files={n:sha((out/n).read_bytes()) for n in ['index.html','comparison.png']})))
    return obj


def test_four_calls_keep_three_distinct_observation_gates(operator):
    first = operator.start()
    assert first['status'] == 'REVIEW_REQUIRED' and operator.client.position == 0
    assert len(list((operator.ui/'..'/'attempts').glob('*/receipt.json'))) == 1
    assert operator.review('Two panels; read-only scope retained.')['operation'] == STEPS[1]
    assert operator.review('Every pixel passes the declared bands.')['operation'] == STEPS[2]
    result = operator.review('Four intended rejections; owner remains pending.')
    assert result['terminal'] and result['next_action'] == 'REPORT_AND_STOP'
    assert len(operator.client.notes) == 3 and operator.client.position == 3
    assert len(list(operator.ui.glob('review-*.json'))) == 3
    calls = list(operator.client.calls)
    assert operator.review('Already finished.') == result
    assert operator.client.calls == calls


def test_full_facade_retains_eighteen_individual_observations(operator, monkeypatch):
    from tools.pcb_c01_full_operator import FullOperator
    operator.__class__ = FullOperator
    monkeypatch.setattr(operator, 'delivery', lambda: dict(terminal=True,files=[],native_slices=18))
    result=operator.start()
    for index in range(18):
        assert result['operation']==operator.steps[index]
        assert operator.client.position==index
        assert len(list(operator.ui.glob('review-*.json')))==index
        result=operator.review('Observed native facts for '+operator.steps[index]+'.')
    assert result['terminal'] and operator.client.position==18
    assert len(operator.client.notes)==18
    calls=list(operator.client.calls)
    assert operator.start()==result
    assert operator.client.calls==calls


@pytest.mark.parametrize('what', ['raw', 'receipt', 'summary', 'output'])
def test_changed_evidence_cannot_be_reviewed_or_delivered(operator, what):
    operator.start()
    state = operator.state()
    if what == 'raw':
        Path(operator.client.pending['result']['raw_response_path']).write_bytes(b'{}')
    elif what == 'receipt':
        Path(operator.client.pending['receipt_path']).write_bytes(b'{}')
    elif what == 'summary':
        Path(state['summary']).write_bytes(b'{}')
    else:
        (operator.client.root/'render_output/comparison.png').write_bytes(b'changed')
    with pytest.raises(ValueError):
        if what == 'output':
            operator.review('Observed one.'); operator.review('Observed two.'); operator.review('Observed controls.')
        else:
            operator.review('Observed result.')


def test_reject_does_not_run_next_slice(operator):
    operator.start()
    with pytest.raises(ValueError, match='OPERATOR_AUDIT_MISMATCH'):
        operator.review('Reject this result.', reject=True)
    assert operator.client.position == 0
    assert STEPS[1] not in operator.client.calls


def test_start_cannot_replay_pending_native_slice(operator):
    operator.start()
    calls = list(operator.client.calls)
    with pytest.raises(ValueError, match='TASK_ALREADY_STARTED'):
        operator.start()
    assert operator.client.calls == calls


def test_completed_delivery_is_rechecked_without_native_reexecution(operator):
    operator.start(); operator.review('First.'); operator.review('Second.'); operator.review('Third.')
    calls = list(operator.client.calls)
    (operator.client.root/'render_output/comparison.png').write_bytes(b'changed')
    with pytest.raises(ValueError, match='FINAL_ARTIFACT_CHANGED'):
        operator.start()
    assert operator.client.calls == calls


def test_cli_failure_latches_and_prevents_any_retry(operator, monkeypatch, capsys):
    from tools import pcb_c01_operator as facade
    import sys
    operator.start()
    Path(operator.client.pending['result']['raw_response_path']).write_bytes(b'changed')
    monkeypatch.setattr(facade, 'Operator', lambda: operator)
    monkeypatch.setattr(sys, 'argv', ['operator', 'review', 'Observed first slice.'])
    assert facade.main() == 2
    assert json.loads(capsys.readouterr().out)['next_action'] == 'REPORT_AND_STOP'
    assert (operator.ui/'failure.json').is_file()
    calls = list(operator.client.calls)
    monkeypatch.setattr(sys, 'argv', ['operator', 'start'])
    assert facade.main() == 2
    assert operator.client.calls == calls


def test_stopped_native_setup_fails_before_any_call(tmp_path):
    from tools.t01_route_client import SCHEMA
    setup = tmp_path/'agent_setup.json'
    setup.write_bytes(encode(dict(schema=SCHEMA, route_id='stopped', native={},
        inbox=str(tmp_path/'inbox'), replies=str(tmp_path/'replies'),
        tools=[dict(name=name) for name in STEPS])))
    binding = tmp_path/'binding.json'
    binding.write_bytes(encode(dict(schema='pcb-c01-operator-binding/1', setup=str(setup), setup_sha256=sha(setup.read_bytes()))))
    (tmp_path/'adapter_stopped.json').write_bytes(b'{}')
    with pytest.raises(ValueError, match='SETUP_REQUIRED'):
        Operator(binding)
    assert not (tmp_path/'inbox').exists()


def test_long_observation_is_retained_losslessly_and_hash_bound_to_native_audit(operator):
    operator.start()
    observation = 'Observed all four negative controls and their exact expected reasons. '*8
    operator.review(observation)
    record = json.loads((operator.ui/'review-1.json').read_bytes())
    assert record['agent_observation'] == observation
    assert record['agent_observation_sha256'] == sha(observation.encode())
    assert record['agent_observation_sha256'] in operator.client.notes[0]
    assert len(operator.client.notes[0]) <= 300
    assert operator.client.position == 1


def test_changed_full_observation_cannot_be_hidden_by_short_native_note(operator):
    operator.start(); operator.review('Original full observation.')
    path = operator.ui/'review-1.json'; record = json.loads(path.read_bytes())
    record['agent_observation'] = 'Changed observation.'
    path.write_bytes(encode(record))
    with pytest.raises(ValueError, match='AGENT_OBSERVATION_BINDING_CHANGED'):
        operator.verify_observations()


@pytest.mark.parametrize('missing', ['review', 'audit', 'both'])
def test_completed_delivery_requires_all_three_review_and_native_audit_records(operator, missing):
    operator.start(); operator.review('First.'); operator.review('Second.'); operator.review('Third.')
    calls = list(operator.client.calls)
    if missing in ('review', 'both'):
        (operator.ui/'review-3.json').unlink()
    if missing in ('audit', 'both'):
        (operator.client.root/'audits/2/request.json').unlink()
    with pytest.raises(ValueError, match='AGENT_OBSERVATION_BINDING_CHANGED'):
        operator.start()
    assert operator.client.calls == calls


def test_crop_facade_requires_twenty_one_separate_observations(operator,monkeypatch):
    from tools.pcb_t01_operator import CropOperator
    operator.__class__=CropOperator
    monkeypatch.setattr(operator,'summary_details',lambda index,raw:dict(total_slices=21))
    monkeypatch.setattr(operator,'delivery',lambda:dict(terminal=True,files=[],native_slices=21))
    result=operator.start()
    for index in range(21):
        assert result['operation']==operator.steps[index]
        assert operator.client.position==index
        assert len(list(operator.ui.glob('review-*.json')))==index
        result=operator.review('Observed the actual facts for '+operator.steps[index]+'.')
    assert result['terminal'] and operator.client.position==21
    assert len(operator.client.notes)==21
    calls=list(operator.client.calls)
    assert operator.review('Already complete.')==result
    assert operator.client.calls==calls
