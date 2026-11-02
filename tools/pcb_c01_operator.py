#!/usr/bin/env python3
"""Small stdlib operator surface; one native slice per observed review."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
import uuid

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.t01_route_client import Client, child, decode, encode, publish, verify_files

ACTIVE = ROOT/'out/operator_routes/c01_render/current.json'
STEPS = ('render_c01_compare', 'render_c01_verify', 'render_c01_controls')


def sha(blob):
    return hashlib.sha256(blob).hexdigest()


def scoped(path):
    path = Path(path).absolute()
    if '..' in path.parts or not path.is_relative_to(ROOT/'out'):
        raise ValueError('PROJECT_OUTPUT_PATH_REQUIRED')
    return child(ROOT, path)


def now():
    return datetime.now(timezone.utc).isoformat()


def replace_state(path, value):
    temporary = path.with_name('.state-'+uuid.uuid4().hex)
    publish(temporary, encode(value))
    os.replace(temporary, path)


class Operator:
    steps = STEPS
    complete_status = 'COMPLETE_AUDITED_RENDER_SEQUENCE'
    def __init__(self, binding=ACTIVE):
        binding = scoped(binding)
        if not binding.is_file():
            raise ValueError('SETUP_REQUIRED: start the project native C01 render launcher; no environment probes')
        self.binding_blob = binding.read_bytes()
        value = decode(self.binding_blob)
        if set(value) != {'schema', 'setup', 'setup_sha256'} or value['schema'] != 'pcb-c01-operator-binding/1':
            raise ValueError('OPERATOR_BINDING_INVALID')
        setup = scoped(value['setup'])
        if sha(setup.read_bytes()) != value['setup_sha256']:
            raise ValueError('OPERATOR_SETUP_CHANGED')
        self.client = Client(setup, 'LocalCode')
        names = {t['name'] for t in self.client.setup['tools']}
        self.validate_tools(names)
        self.ui = self.client.root/'operator_ui'
        self.state_path = self.ui/'current.json'
        if (self.client.root/'adapter_stopped.json').exists():
            if not self.state_path.exists() or decode(self.state_path.read_bytes()).get('status') != 'COMPLETE':
                raise ValueError('SETUP_REQUIRED: native launcher is stopped; do not probe or retry')

    def validate_tools(self, names):
        if not set(self.steps).issubset(names) or 't01_run' in names or 'native_route.conformance' in names:
            raise ValueError('READ_ONLY_RENDER_PROFILE_REQUIRED')

    def info(self):
        value = self.client.invoke('native_route.info', None)
        if value['native'] != self.client.setup['native']:
            raise ValueError('NATIVE_IDENTITY_CHANGED')
        return value

    def state(self):
        state = decode(self.state_path.read_bytes())
        if state['binding_sha256'] != sha(self.binding_blob):
            raise ValueError('ACTIVE_BINDING_CHANGED')
        return state

    def load_bound(self, path, digest):
        blob = scoped(path).read_bytes()
        if sha(blob) != digest:
            raise ValueError('OPERATOR_EVIDENCE_CHANGED')
        return decode(blob)

    def offer(self, index):
        info = self.info()
        if info['pending_audit'] is not None or info['next_operation'] != self.steps[index]:
            raise ValueError('NATIVE_SLICE_STATE_MISMATCH')
        attempt = 'english-'+uuid.uuid4().hex[:20]
        result = self.client.invoke(self.steps[index], attempt)
        if result.get('error'):
            raise ValueError(json.dumps(result['error'], sort_keys=True))
        full = self.ui/f'slice-{index+1}.json'
        publish(full, encode(result))
        raw = decode(scoped(result['result']['raw_response_path']).read_bytes())['result']
        summary = dict(status='REVIEW_REQUIRED', slice=index+1, operation=self.steps[index],
                       facts=result['result']['facts'], owner='PENDING_USER',
                       evidence_scope='Native facts only; no visual inspection by the agent is implied. Each raster is checked against its own input file; cross-file contour equality, aperture-mask stability and electrical/manufacturing acceptance are not established by these checks.',
                       next_action='Review the facts, then submit one observation with review. State one finding; the client already retains every fact. Do not claim visual inspection from JSON or run separate probes.')
        summary.update(self.summary_details(index, raw))
        summary_path = self.ui/f'summary-{index+1}.json'
        publish(summary_path, encode(summary))
        replace_state(self.state_path, dict(binding_sha256=sha(self.binding_blob), index=index,
            status='REVIEW_REQUIRED', attempt=attempt, result=str(full), result_sha256=sha(full.read_bytes()),
            summary=str(summary_path), summary_sha256=sha(summary_path.read_bytes())))
        return summary

    def summary_details(self, index, raw):
        if index == 1:return dict(measurements=raw['audits'])
        if index == 2:return dict(controls=raw['controls'])
        return {}

    def start(self):
        if self.state_path.exists():
            state = self.state()
            if state['status'] == 'COMPLETE':
                return self.terminal_result(state)
            raise ValueError('TASK_ALREADY_STARTED: review the retained slice; never retry start')
        self.ui.mkdir()
        publish(self.ui/'binding.json', self.binding_blob)
        publish(self.ui/'started.json', encode(dict(at=now(), mode='AGENT_REVIEWS_EACH_SLICE')))
        return self.offer(0)

    def review(self, note, reject=False):
        state = self.state()
        if state['status'] == 'COMPLETE':
            return self.terminal_result(state)
        if state['status'] != 'REVIEW_REQUIRED' or not 1 <= len(note) <= 4096:
            raise ValueError('OBSERVATION_REQUIRED_OR_TOO_LARGE')
        result = self.load_bound(state['result'], state['result_sha256'])
        summary = self.load_bound(state['summary'], state['summary_sha256'])
        verified = self.client.call('native_route.verify_receipt',
            dict(route_id=self.client.setup['route_id'], attempt_id=state['attempt']))
        if verified['receipt_sha256'] != result['receipt_sha256']:
            raise ValueError('NATIVE_RECEIPT_CHANGED')
        verify_files(Path(result['receipt_path']), result['receipt_sha256'])
        if summary['facts'] != result['result']['facts']:
            raise ValueError('SUMMARY_FACTS_CHANGED')
        info = self.info()
        if info['pending_audit'] != state['attempt'] or info['next_operation'] != self.steps[state['index']]:
            raise ValueError('PENDING_REVIEW_CHANGED')
        note_hash = sha(note.encode('utf-8'))
        native_note = f'Agent observation sha256:{note_hash}; full text in operator_ui/review-{state["index"]+1}.json. Facts-only observation; no owner or visual acceptance.'
        audit = dict(result['result']['audit_required'], note=native_note, verdict='FAIL' if reject else 'PASS')
        publish(self.ui/f'review-{state["index"]+1}.json', encode(dict(at=now(),
            attempt_id=state['attempt'],
            summary_sha256=state['summary_sha256'], agent_observation=note,
            agent_observation_sha256=note_hash,
            mechanical_fields='Digest and every fact copied by client from verified native receipt', audit=audit)))
        accepted = self.client.invoke('native_route.audit', state['attempt'], audit)
        if accepted['status'] != 'PASS_SLICE_OBSERVATION_AUDIT':
            raise ValueError('NATIVE_REVIEW_NOT_ACCEPTED')
        self.verify_observations()
        if state['index'] < len(self.steps)-1:
            return self.offer(state['index']+1)
        return self.finish()

    def terminal_result(self, state):
        result = self.load_bound(state['terminal'], state['terminal_sha256'])
        self.verify_observations()
        for record in result['files']:
            if sha(scoped(record['path']).read_bytes()) != record['sha256']:
                raise ValueError('FINAL_ARTIFACT_CHANGED')
        return result

    def verify_observations(self):
        native = {}
        for path in (self.client.root/'audits').glob('*/request.json'):
            arguments = decode(path.read_bytes())['arguments']
            native.setdefault(arguments['attempt_id'], []).append(arguments['audit'])
        reviews = list(self.ui.glob('review-*.json'))
        expected = len(self.steps) if self.state()['status'] == 'COMPLETE' else len(native)
        if (len(native) != expected or {p.name for p in reviews} !=
                {f'review-{n}.json' for n in range(1, expected+1)}):
            raise ValueError('AGENT_OBSERVATION_BINDING_CHANGED')
        for path in reviews:
            record = decode(path.read_bytes())
            note_hash = sha(record['agent_observation'].encode('utf-8'))
            summary = self.ui/path.name.replace('review-', 'summary-')
            if (note_hash != record['agent_observation_sha256'] or note_hash not in record['audit']['note']
                    or record['audit'] not in native.get(record['attempt_id'], [])
                    or sha(summary.read_bytes()) != record['summary_sha256']
                    or decode(summary.read_bytes())['facts'] != record['audit']['observed']):
                raise ValueError('AGENT_OBSERVATION_BINDING_CHANGED')

    def finish(self):
        info = self.info()
        if (info['status'] != self.complete_status or info['pending_audit'] is not None
                or info['next_operation'] is not None or info['accepted_operations'] != list(self.steps)):
            raise ValueError('INCOMPLETE_NATIVE_SEQUENCE')
        result = self.delivery()
        terminal = self.ui/'terminal.json'
        publish(terminal, encode(result))
        replace_state(self.state_path, dict(binding_sha256=sha(self.binding_blob), status='COMPLETE',
                       terminal=str(terminal), terminal_sha256=sha(terminal.read_bytes())))
        return result

    def delivery(self):
        out = self.client.root/'render_output'
        saved = decode((out/'render.json').read_bytes())
        files = []
        for name in ('index.html', 'comparison.png'):
            blob = (out/name).read_bytes()
            if sha(blob) != saved['files'][name]:
                raise ValueError('FINAL_ARTIFACT_CHANGED')
            record = dict(path=str(out/name), bytes=len(blob), sha256=sha(blob), format='HTML')
            if name.endswith('.png'):
                if blob[:8] != b'\x89PNG\r\n\x1a\n':
                    raise ValueError('PNG_SIGNATURE_CHANGED')
                record.update(format='PNG', dimensions=list(struct.unpack('>II', blob[16:24])))
            files.append(record)
        result = dict(status='COMPLETE_AUDITED_RENDER_SEQUENCE', native_slices=3, observation_audits=3,
            next_action='REPORT_AND_STOP', terminal=True, files=files, owner='PENDING_USER',
            scope='Read-only C01; frozen results and T02-T05 unchanged',
            proof='Native raster, frame, file-hash and four-control checks passed. No ls/file/git/environment probes are required.',
            report_text='The C01 KiCad/Gerber comparison is ready at the returned HTML/PNG paths. Three native slices and three observation audits passed. Each image matches its own input within the declared display bands; this is not a new cross-file geometry, aperture-mask, electrical or manufacturing approval. Owner review remains pending. Task complete; no additional commands are needed.',
            evidence=str(self.client.root), independent='NOT_RUN', manufacturing='NOT_ESTABLISHED')
        return result


def main(operator_class=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['start', 'review', 'reject'])
    parser.add_argument('observation', nargs='?', default='')
    args = parser.parse_args()
    operator = None
    started = now()
    def journal(result, code):
        if operator and operator.ui.exists():
            folder = operator.ui/'client_calls'
            folder.mkdir(exist_ok=True)
            publish(folder/(uuid.uuid4().hex+'.json'), encode(dict(started_at=started,
                completed_at=now(), action=args.action, observation=args.observation,
                returncode=code, result=result)))
    try:
        operator = (operator_class or Operator)()
        failure = operator.ui/'failure.json'
        if failure.exists():
            raise ValueError('TASK_HALTED: retained failure; no retry or other probes')
        result = operator.start() if args.action == 'start' else operator.review(args.observation, args.action == 'reject')
        journal(result, 0)
        print(json.dumps(result, sort_keys=True))
        return 0
    except Exception as error:
        result = dict(status='HALTED', next_action='REPORT_AND_STOP', error=str(error),
            task_outcome='INCOMPLETE_NOT_ACCEPTED',
            report_text='The C01 task stopped before all required gates passed. Report this error and stop; this session cannot be repaired by retrying. Do not search for display paths or ask the user to rerun it. Coordinator review is required.',
            evidence=str(operator.client.root) if operator else None)
        if operator and operator.ui.exists() and not (operator.ui/'failure.json').exists():
            publish(operator.ui/'failure.json', encode(dict(result, at=now())))
        journal(result, 2)
        print(json.dumps(result, sort_keys=True))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
