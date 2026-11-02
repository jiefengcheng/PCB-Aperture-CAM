"""C01-only, operator-driven T01 calls and technical observation gates.

The operator selects one operation at a time. This module supplies trusted
operands, preserves actual ABI results and conditionally grants the checked plan.
It never imports or invokes a geometry constructor or the one-shot reproducer.
"""
from datetime import datetime, timezone
from pathlib import Path
import uuid
from src.stage_abi.store import canonical, digest
from tools.t01_native_route import NativeRoute, RouteError, ID, closed, verify_attempt
from tools.t01_operator_host import ROOT, check, read, fresh, register, grant, response_view


class C01Route(NativeRoute):
    OPERATION_STATUS = 'PASS_T01_OPERATION_CHECKS'
    OPERATION_AUTHORITY = 'Bound C01 T01; technical slice gate only'

    def __init__(self, session, **kwargs):
        super().__init__(session, **kwargs)
        self.contract = read(ROOT / 'contracts/t01/c01_route.json')
        self.operations = self.contract['operations']
        self.position = 0
        self.pending = None
        self.responses = {}
        self.accepted = []
        self.audit_hashes = {}
        (self.session / 'audits').mkdir()
        (self.session / 'operator').mkdir()
        fresh(self.session / 'DECISION_POLICY.json', self.contract)

    def tools(self):
        result = super().tools()
        schema = dict(type='object', additionalProperties=False,
            properties=dict(route_id=dict(type='string'), attempt_id=dict(type='string', pattern=ID.pattern)),
            required=['route_id', 'attempt_id'])
        for name in self.operations:
            result.append(dict(name=name, input_schema=schema,
                description='One actual C01 T01 operation; preceding checked observation audit required.'))
        result.append(dict(name='native_route.audit', description='Submit observations of the pending actual response; no owner acceptance.',
            input_schema=dict(type='object', additionalProperties=False,
                properties=dict(**schema['properties'], audit=dict(type='object')),
                required=['route_id','attempt_id','audit'])))
        return result

    def info(self):
        info = super().info()
        info.update(scope='Full bound C01 T01 only; no T02-T05 or acceptance promotion',
            sequence=self.operations, accepted_operations=list(self.accepted),
            pending_audit=self.pending['attempt_id'] if self.pending else None,
            next_operation=None if self.position == len(self.operations) else self.operations[self.position],
            status='COMPLETE_AUDITED_SEQUENCE_ORACLE_PENDING' if self.position == len(self.operations) else 'READY_FOR_AUDIT' if self.pending else 'READY_FOR_OPERATION')
        return info

    def _valid_args(self, args, *, audit=False):
        closed(args, {'route_id', 'attempt_id', 'audit'} if audit else {'route_id','attempt_id'})
        if args['route_id'] != self.route_id or type(args['attempt_id']) is not str or not ID.fullmatch(args['attempt_id']):
            raise RouteError('ROUTE_OR_ATTEMPT_INVALID', 'Current route and safe attempt ID required')

    def _prior_integrity(self):
        for attempt, sha in self.receipt_hashes.items():
            verify_attempt(self.session / 'attempts' / attempt, sha)
        for path, sha in self.audit_hashes.items():
            if digest(Path(path).read_bytes()) != sha:
                raise RouteError('AUDIT_RECEIPT_CHANGED', path)

    def _request_for(self, operation, rid):
        c, r = self.cap, self.responses
        verb = 'compile' if operation == 't01_negative_compile' else operation.removeprefix('t01_')
        if verb == 'compile':
            payload = dict(english_ref=self.negative if operation == 't01_negative_compile' else c['english_ref'], binding_ref=c['binding_ref'])
        elif verb == 'discover':
            payload = dict(bounds_ref=c['bounds_ref'])
        elif verb == 'inspect':
            payload = dict(selection_ref=r['t01_discover']['result']['selection_ref'],page_size=100,cursor=None)
        elif verb == 'plan':
            payload = dict(inspection_ref=r['t01_inspect']['result']['inspection_ref'],selection_ref=r['t01_discover']['result']['selection_ref'],predecessor_qualification_ref=c['qualification_ref'],bounds_ref=c['bounds_ref'],strategy='priority_companion_growth')
        elif verb == 'run':
            payload = dict(output_scope_ref=c['output_scope_ref'])
        elif verb == 'verify':
            payload = dict(candidate_ref=r['t01_run']['result']['result']['candidate_ref'],verifier_ref=c['verifier_ref'],proof_scope_ref=c['proof_scope_ref'])
        elif verb == 'compare':
            payload = dict(left_ref=c['scene_ref'],right_ref=r['t01_run']['result']['result']['candidate']['output_scene_ref'],viewport_ref=c['viewport_ref'],evidence_selection_ref=c['evidence_selection_ref'])
        elif verb == 'review':
            payload = dict(candidate_ref=r['t01_run']['result']['result']['candidate_ref'],verification_ref=r['t01_verify']['result']['result']['verification_ref'],decision_filters=dict(types=['owner','independent','local'],page_size=100,cursor=None))
        else:
            raise RouteError('TOOL_NOT_EXPOSED', operation)
        req = self._request(verb, payload, rid)
        if verb != 'compile':
            req.update(profile_id=c['profile_id'],scene_ref=c['scene_ref'],policy_ref=c['policy_ref'])
        if verb in ('run','verify'):
            req.update(plan_ref=c['plan_ref'],authorization_ref=c['authorization_ref'],idempotency_key='macos-c01-' + rid)
        return req

    def _facts(self, operation, response, code, path):
        """Check actual fields, not a model's description of success."""
        expected = self.contract['expected']
        def require(condition, reason):
            if not condition:
                raise RouteError('C01_OPERATION_CHECK_FAILED', reason)
        if operation == 't01_negative_compile':
            e = response.get('error') or {}
            require(code == 2 and response['status'] == 'REJECTED' and response['result'] is None and e.get('code') == 'T01_ENGLISH_UNSUPPORTED' and e.get('message','').startswith('R14:'), 'R14 semantic negative')
            return dict(abi_status=response['status'],exit_status=code,negative_code=e['code'],policy_emitted=False,construction_status='NOT_RUN')
        require(code == 0 and response['status'] == 'OK' and response['error'] is None, 'Actual ABI success/exit')
        v = response_view(path)
        r = response['result']
        if operation == 't01_compile':
            target = read(ROOT / 'contracts/t01/compile_gate.json')['expected']
            require(r['policy_ref']['sha256'] == target['policy_sha256_for_c01_binding'] and r['policy']['binding_ref'] == self.cap['binding_ref'] and r['construction_status'] == 'NOT_RUN' and len(r['policy']['clause_trace']) == 15, 'Exact English/policy/binding')
            return dict(abi_status='OK',clauses=15,family=r['policy']['family'],hard_gap_mm=r['policy']['settings']['hard_gap'],construction_status=r['construction_status'])
        if operation == 't01_discover':
            d=r['discovery']
            require(d['source_objects'] == expected['source_objects'] and d['unique_sites'] == expected['sites'] and d['occurrences'] == expected['aliases'] and len(set(d['source_ids'])) == expected['sites'] and r['construction_status'] == 'NOT_RUN', 'Full source discovery')
            return dict(source_objects=d['source_objects'],canonical_sites=d['unique_sites'],aliases=d['occurrences'],construction_status=r['construction_status'])
        if operation == 't01_inspect':
            require(r['total_records'] == expected['sites'] and set(r['selected_source_ids']) == set(self.responses['t01_discover']['result']['discovery']['source_ids']) and r['next_cursor'] is None, 'Complete discovery selection inspected')
            return dict(inspected_sites=r['total_records'],selection_matches_discovery=True,cursor_exhausted=True,construction_status='NOT_RUN')
        if operation == 't01_plan':
            require(len(v['targets']) == expected['sites'] and v['class_record_count'] == expected['sites'] and v['group_count'] == expected['groups'] and v['physical_component_count'] == expected['physical_components'] and v['priority_count'] == expected['round_priorities'] and len(v['exceptions']) == expected['exceptions'] and v['construction_status'] == 'NOT_RUN' and v['strategy'] == 'priority_companion_growth' and v['implementation'] == self.identity['implementation'] and v['runtime'] == self.identity['shared_runtime'], 'Source/strategy/allocation/runtime-bound plan')
            return dict(targets=len(v['targets']),groups=v['group_count'],physical_components=v['physical_component_count'],round_priorities=v['priority_count'],exceptions=len(v['exceptions']),strategy=v['strategy'],construction_status=v['construction_status'])
        if operation == 't01_run':
            c=r['result']['candidate']
            require(v['job_status'] == 'COMPLETED' and v['reused'] is False and v['execution_evidence']['mode'] == 'FRESH_EXECUTION' and c['source_objects'] == expected['source_objects'] and c['unique_sites'] == expected['sites'] and c['source_occurrences'] == expected['aliases'] and len(c['decisions']) == expected['sites'] and c['counts'] == expected['counts'] and len(c['events']) == expected['neighbor_controls'] and c['neighbor_response_sites'] == expected['neighbor_response_sites'] and c['evolving_companion_response_sites'] == 0 and len(c['final_checks']) == expected['sites'] and all(q['check']['passed'] for q in c['final_checks']), 'Fresh complete C01 construction/checks')
            require(c['owner_status'] == 'PENDING' and c['independent_status'] == 'NOT_RUN' and c['native_electrical_manufacturing'] == 'NOT_ESTABLISHED', 'Acceptance not promoted')
            require(len(c['square_disabled_controls']) == 1 and c['square_disabled_controls'][0]['key'] == 'S31' and c['square_disabled_controls'][0]['symmetric_difference_mm2'] > 0, 'S31 recess control')
            return dict(canonical_sites=c['unique_sites'],aliases=c['source_occurrences'],counts=c['counts'],neighbor_controls=len(c['events']),neighbor_response_sites=c['neighbor_response_sites'],final_checks_passed=True,fresh_execution=True,owner_status=c['owner_status'],independent_status=c['independent_status'])
        if operation == 't01_verify':
            q=r['result']['verification'];t=q['check']
            require(v['job_status'] == 'COMPLETED' and v['reused'] is False and v['execution_evidence']['mode'] == 'FRESH_EXECUTION' and q['geometric_status'] == 'PASS' and t['passed'] is True and t['failures'] == [] and t['reconstructed_sites'] == expected['sites'] and t['reconstructed_alias_occurrences'] == expected['aliases'] and t['final_assembled_checks'] == expected['sites'] and q['candidate_ref'] == self.responses['t01_run']['result']['result']['candidate_ref'], 'Fresh reconstruction verdict and candidate binding')
            require(q['owner_status'] == 'PENDING' and q['independent_status'] == 'NOT_RUN' and q['native_electrical_manufacturing'] == 'NOT_ESTABLISHED', 'Verification acceptance boundary')
            return dict(geometric_status=q['geometric_status'],reconstructed_sites=t['reconstructed_sites'],aliases=t['reconstructed_alias_occurrences'],assembled_checks=t['final_assembled_checks'],fresh_reconstruction=True,owner_status=q['owner_status'],independent_status=q['independent_status'])
        if operation == 't01_compare':
            records=r['source_changes'];changed=sum(x['left_ref'] != x['right_ref'] for x in records)
            require(len(records) == expected['sites'] and changed == 42 and r['removed_area_mm2'] <= 1e-10 and r['added_area_mm2'] > 0, 'Growth-only comparison and all selected records')
            return dict(selected_records=len(records),changed_sources=changed,unchanged_sources=len(records)-changed,added_area_mm2=r['added_area_mm2'],removed_area_mm2=r['removed_area_mm2'])
        if operation == 't01_review':
            require(r['owner_status'] == 'PENDING' and r['independent_status'] == 'NOT_RUN' and r['records'] == [] and r['next_cursor'] is None, 'Read-only review; no fabricated acceptance')
            return dict(owner_status=r['owner_status'],independent_status=r['independent_status'],decision_records=len(r['records']),cursor_exhausted=True)
        raise RouteError('TOOL_NOT_EXPOSED',operation)

    def _step(self, operation, args, caller):
        self._valid_args(args)
        if self.pending or self.position == len(self.operations) or operation != self.operations[self.position]:
            raise RouteError('C01_SLICE_GATE_CLOSED', 'Audit current result before the next permitted operation')
        path=self.session/'attempts'/args['attempt_id']
        try:
            path.mkdir()
        except FileExistsError as e:
            raise RouteError('ATTEMPT_EXISTS','Never overwrite a previous attempt') from e
        fresh(path/'invocation.json',dict(tool=operation,arguments=args,caller=caller,started_at=datetime.now(timezone.utc).isoformat()))
        result=error=None
        try:
            check(self.session)
            self._prior_integrity()
            request=self._request_for(operation,args['attempt_id'])
            response,code=self._invoke(path/'abi',operation,request)
            if any(response.get(k) != request[k] for k in ('abi_version','request_id','operation')):
                raise RouteError('ABI_RESPONSE_CORRELATION_FAILED',operation)
            facts=self._facts(operation,response,code,path/'abi/stdout.json')
            check(self.session)
            result=dict(status=self.OPERATION_STATUS,operation=operation,facts=facts,
                raw_response_path=str(path/'abi/stdout.json'),raw_response_sha256=digest((path/'abi/stdout.json').read_bytes()),
                audit_required=dict(verdict='PASS',response_sha256=digest((path/'abi/stdout.json').read_bytes()),observed=facts,note='Operator supplies a brief observation, not an acceptance claim'))
        except Exception as e:
            error=dict(code=getattr(e,'code','C01_OPERATION_FAILED'),message=str(e))
        fresh(path/'result.json',dict(result=result,error=error))
        files={str(p.relative_to(path)):digest(p.read_bytes()) for p in sorted(path.rglob('*')) if p.is_file()}
        fresh(path/'receipt.json',dict(schema='pcb-native-attempt-receipt/1',attempt_id=args['attempt_id'],tool=operation,caller=caller,native=self.identity,files=files,status='FAIL' if error else result['status'],completed_at=datetime.now(timezone.utc).isoformat(),authority=self.OPERATION_AUTHORITY))
        sha=digest((path/'receipt.json').read_bytes());self.receipt_hashes[args['attempt_id']]=sha
        verify_attempt(path,sha)
        if not error:
            self.pending=dict(attempt_id=args['attempt_id'],operation=operation,response=response,result=result,path=path)
        return dict(result=result,error=error,receipt_path=str(path/'receipt.json'),receipt_sha256=sha,native=self.identity,route_id=self.route_id)

    def _audit(self,args,caller):
        self._valid_args(args,audit=True)
        audit_dir=self.session/'audits'/uuid.uuid4().hex;audit_dir.mkdir()
        fresh(audit_dir/'request.json',dict(arguments=args,caller=caller))
        try:
            check(self.session);self._prior_integrity()
            p=self.pending
            if p is None or args['attempt_id'] != p['attempt_id']:
                raise RouteError('NO_MATCHING_PENDING_AUDIT','Pending attempt required')
            a=args['audit'];closed(a,{'verdict','response_sha256','observed','note'})
            if a['verdict'] != 'PASS' or a['response_sha256'] != p['result']['raw_response_sha256'] or canonical(a['observed']) != canonical(p['result']['facts']) or type(a['note']) is not str or not 1 <= len(a['note']) <= 300:
                raise RouteError('OPERATOR_AUDIT_MISMATCH','Actual digest and all observed facts must match; brief operator note required')
            operation=p['operation']
            if operation == 't01_compile' and self.cap['capsule_revision'] == 0:
                self.cap=register(self.session,p['path']/'abi/stdout.json')
            if operation == 't01_plan':
                self.cap=grant(self.session,p['path']/'abi/stdout.json')
            self.responses[operation]=p['response']
            self.accepted.append(operation);self.position+=1;self.pending=None
            output=dict(status='PASS_SLICE_OBSERVATION_AUDIT',accepted_operation=operation,
                next_operation=self.operations[self.position] if self.position < len(self.operations) else None,
                authority='Codex-authored conditional technical gate; no owner or independent acceptance',
                native=self.identity,route_id=self.route_id)
            fresh(audit_dir/'decision.json',output)
            for file in audit_dir.iterdir():self.audit_hashes[str(file)]=digest(file.read_bytes())
            return output
        except Exception as e:
            fresh(audit_dir/'decision.json',dict(status='FAIL',error=dict(code=getattr(e,'code','AUDIT_FAILED'),message=str(e))))
            raise

    def call(self,name,args,caller):
        with self.lock:
            if name == 'native_route.audit':return self._audit(args,caller)
            if name in self.operations:return self._step(name,args,caller)
            if name == 'native_route.conformance' and (self.position or self.pending):
                raise RouteError('C01_SLICE_GATE_CLOSED','Setup cannot register a new profile during the sequence')
            return super().call(name,args,caller)
