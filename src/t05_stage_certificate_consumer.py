"""Dedicated, opt-in T05 stage consumer with no construction replay.

Trust boundary: the existing constructor and its complete closing guards are
the process-local issuer. Its real canonical composition call is observed once;
no externally supplied 'passed' flag substitutes for that call. After successful
construction the issuer seals all decisions (including KEEP), source/policy/plan,
the actual output manifest/copper, the complete read dependency closure, and the
accepted certificate chain. The verifier authenticates those SAME inputs, reads
actual dependency bytes and consumes committed local certificates. It never
rebuilds routes, fits curves, measures foreign clearance or unions scene copper.

This is not portable signed-artifact trust: the authority key is ephemeral and
must stay in the same trusted process as construction. Persisted manifests are
evidence only. The module is not activated in ordinary production adapters.
"""
from collections import Counter
from copy import deepcopy
from hmac import compare_digest, digest as mac
from secrets import token_bytes
from time import perf_counter

from shapely import from_wkb
from src.stage_abi.store import canonical
from src.stage_abi.scene import validate_scene
from src.t05_certificate_verifier import body_hash, hash_bytes, require

SCHEMA = 't05-completed-construction/1'


def artifact_refs(value):
    """Yield refs from arbitrary plain-JSON metadata, without following cycles."""
    if type(value) is dict:
        if set(value) == {'artifact_id', 'sha256'}:
            yield value
        else:
            for member in value.values():
                yield from artifact_refs(member)
    elif type(value) is list:
        for member in value:
            yield from artifact_refs(member)


class StageCertificateConsumer:
    """One construction authority; disk-backed manifests, bounded retained index.

    Allocate ``limit_bytes`` from the existing 0.5 MiB ledger/index reserve,
    not from an additional cache. Large dependency lists live in the actual
    artifact store. Only their immutable reference/hash and compact witness are
    retained here. Accounting bounds retained metadata, not transient JSON/RSS.
    """
    def __init__(self, ledger, store, *, limit_bytes=16*1024):
        self.ledger = ledger
        self.store = store
        self.limit_bytes = limit_bytes
        self._key = token_bytes(32)
        self._composition = None
        self._seal = None
        self.replay_ref = None
        self.counts = Counter()
        self.seconds = Counter()
        self.peak_bytes = 0

    def _charge(self):
        amount = 2048 + len(canonical([self._composition, self._seal, self.replay_ref]))
        require(amount <= self.limit_bytes, 'STAGE_CERTIFICATE_BUDGET')
        self.peak_bytes = max(self.peak_bytes, amount)

    def observe_composition(self, scene, actual_wkb):
        """Called only by a wrapper around the REAL constructor composition.

        The wrapper returns the original geometry unchanged. Recording bytes
        here avoids a duplicate union at sealing or replay. Sealing below must
        match both the exact output scene and the real stored after artifact.
        A second composition replaces this observation; an unrelated final
        observation cannot match the output manifest and fails closed.
        """
        require(self._seal is None, 'STAGE_CERTIFICATE_ALREADY_SEALED')
        self._composition = dict(scene_sha256=body_hash(scene), copper_sha256=hash_bytes(actual_wkb))
        self.counts['observed_compositions'] += 1
        self._charge()

    @staticmethod
    def _input_hash(scene, policy, plan, candidate, execution_binding):
        return body_hash(dict(scene=scene, policy=policy, plan=plan,
            candidate=candidate, execution_binding=execution_binding))

    def seal(self, scene, policy, plan, candidate, receipt_refs, execution_binding):
        """Issue AFTER the constructor returned through all closing guards.

        The integration must not call this from inside the run body before its
        execution context has verified input/snapshot/source integrity. Real
        composition provenance, full ordered source/decision membership, all
        original row identities, the real output scene, and exact ledger commit
        coverage are checked here. Decisions/attachment/scope results are bound
        from the successfully completed trusted constructor, not regenerated.
        """
        began = perf_counter()
        try:
            require(self._seal is None, 'STAGE_CERTIFICATE_ALREADY_SEALED')
            require(candidate['status'] == 'CONSTRUCTED', 'STAGE_CERTIFICATE_NOT_CONSTRUCTED')
            rows = plan['details']['routes']
            require(self.store.get_json(plan['scene_ref'], kind='scene') == scene
                and self.store.get_json(plan['policy_ref'], kind='policy') == policy, 'STAGE_CERTIFICATE_PLAN_INPUTS')
            decisions = candidate['decisions']
            require([d['source_id'] for d in decisions] == [r['source_id'] for r in rows], 'STAGE_CERTIFICATE_DECISION_COVERAGE')
            for row, decision in zip(rows, decisions):
                require(all(decision[k] == v for k, v in row.items()), 'STAGE_CERTIFICATE_MEMBERSHIP')
                require(decision['status'] in ('KEEP', 'GROWN'), 'STAGE_CERTIFICATE_DECISION_STATUS')
                # Preserve the old verifier's LOGICAL acceptance guards without
                # recomputing needs, attachment intersections or route geometry.
                # Their actual measured outcomes come from the completed,
                # source-bound constructor; all are subsequently authenticated.
                outcomes = decision['attachment_outcomes']
                if not row['land_ids']:
                    require(decision['status'] == 'KEEP' and not outcomes, 'STAGE_CERTIFICATE_NO_CONTACT_FORGED')
                elif decision['status'] == 'GROWN':
                    from src.u05_board.coverage import CONTRACT
                    require(decision['scale'] in CONTRACT.radius_scales, 'STAGE_CERTIFICATE_SCALE_CHANGED')
                    require(not any(a['status'] == 'MISSING_TREATMENT' for a in outcomes), 'STAGE_CERTIFICATE_MISSING_TREATMENT')
                elif any(a.get('needed', False) for a in outcomes):
                    require(row.get('reference_status') != 'GROWN', 'STAGE_CERTIFICATE_REQUIRED_REFERENCE_BLOCKED')
            protected = {r['source_id']: r['geometry_ref'] for r in scene['objects']}
            require(candidate['protected_source_refs'] == protected, 'STAGE_CERTIFICATE_SOURCE_CHANGED')
            output = validate_scene(self.store, candidate['output_scene_ref'])
            require(self._composition is not None and self._composition['scene_sha256'] == body_hash(output), 'STAGE_CERTIFICATE_COMPOSITION_MISSING')
            require(self._composition['copper_sha256'] == candidate['after_ref']['sha256'], 'STAGE_CERTIFICATE_COMPOSITION_CHANGED')
            # Source rows and viewport are unchanged. Only declared accepted
            # additions may follow them, in exact decision order. This binds
            # the once-composed copper to its additive leaf manifest.
            require(output['objects'][:len(scene['objects'])] == scene['objects'], 'STAGE_CERTIFICATE_SOURCE_ROWS_CHANGED')
            for key in ('source_sha256', 'frame', 'units', 'layer', 'viewport_mm', 'findings'):
                require(output[key] == scene[key], 'STAGE_CERTIFICATE_OUTPUT_BINDING')
            plan_ref = self.store.put_json('plan', plan)
            lineage = scene['lineage'] + [dict(stage='t05', predecessor_ref=plan['scene_ref'],
                policy_ref=plan['policy_ref'], implementation=plan['implementation'], plan_ref=plan_ref)]
            require(output['lineage'] == lineage, 'STAGE_CERTIFICATE_LINEAGE_CHANGED')
            grown = [d for d in decisions if d['status'] == 'GROWN']
            accepted = self.ledger.accepted
            require(len(grown) == len(accepted), 'STAGE_CERTIFICATE_COMMIT_COVERAGE')
            require(self.ledger.counts['complete_replays'] >= 1, 'STAGE_CERTIFICATE_CONSTRUCTION_REPLAY_MISSING')
            additions = output['objects'][len(scene['objects']):]
            require(len(additions) == len(grown), 'STAGE_CERTIFICATE_EXTRA_OUTPUT')
            from src.u05_board.coverage import addition_source_id
            certificates = []
            for decision, entry, row in zip(grown, accepted, additions):
                sid = decision['source_id']
                require(entry['source_id'] == sid and entry['patch_ref'] == decision['patch_ref'], 'STAGE_CERTIFICATE_COMMIT_CHANGED')
                expected_row = dict(source_id=addition_source_id(decision), kind='junction_addition',
                    geometry_ref=decision['patch_ref'], original_ref=decision['patch_ref'],
                    metadata=dict(origin='t05-derived-addition', owner_trace=sid, predecessor_ref=plan['scene_ref']))
                require(row == expected_row, 'STAGE_CERTIFICATE_ADDITION_ROW_CHANGED')
                reference = receipt_refs[sid]
                receipt = self.store.get_json(reference, kind='t05-certificate')
                require(body_hash(receipt) == entry['receipt_sha256'], 'STAGE_CERTIFICATE_RECEIPT_CHANGED')
                certificates.append(dict(source_id=sid, patch_ref=entry['patch_ref'], receipt_ref=reference))
            # Preserve the original removed-area measurement exactly, ONCE at
            # issuance. It is authenticated on replay, never guessed as zero.
            before = from_wkb(self.store.get(candidate['before_ref'], kind='geometry'))
            after = from_wkb(self.store.get(candidate['after_ref'], kind='geometry'))
            require(before.is_valid and after.is_valid, 'STAGE_CERTIFICATE_ASSEMBLY_INVALID')
            result = dict(passed=True, failures=[], reconstructed_patches=len(grown),
                removed_area_mm2=before.difference(after).area,
                verified_attachments=sum(len(d['attachment_outcomes']) for d in decisions))
            require(candidate['coverage'] == dict(targets=len(decisions), grown=len(grown),
                attachment_outcomes=result['verified_attachments']), 'STAGE_CERTIFICATE_COVERAGE_CHANGED')
            # All construction-read dependencies are included, not just refs
            # obvious in the scene. Nested route/source/policy/cell artifacts
            # remain byte-bound even when final verification does not use them
            # to recompute geometry. The adapter's run closing guards already
            # validated decoded/snapshot/index integrity before this point.
            dependencies = dict(getattr(self.store, 'read_refs', getattr(self.store, '_reads', {})))
            for ref in artifact_refs([scene, policy, plan, candidate, certificates]):
                self.store.get(ref)
                dependencies[ref['artifact_id']] = ref
            manifest = dict(schema=SCHEMA, certificates=certificates,
                dependencies=[dependencies[k] for k in sorted(dependencies)])
            manifest_ref = self.store.put_json('t05-stage-manifest', manifest)
            body = dict(schema=SCHEMA, input_sha256=self._input_hash(scene, policy, plan, candidate, execution_binding),
                ledger_binding=self.ledger.binding, ledger_head=self.ledger.head,
                accepted_sha256=body_hash(self.ledger.accepted), manifest_ref=manifest_ref,
                composition=self._composition, result=result)
            self._seal = dict(body=body, authentication=mac(self._key, canonical(body), 'sha256').hex())
            self._charge()
            self.counts['sealed'] += 1
            return deepcopy(self._seal)
        finally:
            self.seconds['seal'] += perf_counter() - began

    def verify(self, scene, policy, plan, candidate, proof_scope, execution_binding):
        """Direct certificate consumer; deliberately no adapter execution scope."""
        began = perf_counter()
        try:
            require(proof_scope == {'scope': 'complete-source-and-all-patches'}, 'STAGE_CERTIFICATE_PROOF_SCOPE')
            require(self._seal is not None, 'STAGE_CERTIFICATE_NOT_SEALED')
            body = self._seal['body']
            require(compare_digest(self._seal['authentication'], mac(self._key, canonical(body), 'sha256').hex()), 'STAGE_CERTIFICATE_AUTHENTICATION')
            require(body['input_sha256'] == self._input_hash(scene, policy, plan, candidate, execution_binding), 'STAGE_CERTIFICATE_INPUT_CHANGED')
            require(body['ledger_binding'] == self.ledger.binding and body['ledger_head'] == self.ledger.head
                and body['accepted_sha256'] == body_hash(self.ledger.accepted), 'STAGE_CERTIFICATE_CHAIN_CHANGED')
            manifest = self.store.get_json(body['manifest_ref'], kind='t05-stage-manifest')
            require(manifest['schema'] == SCHEMA, 'STAGE_CERTIFICATE_MANIFEST_SCHEMA')
            for ref in manifest['dependencies']:
                self.store.get(ref)  # hashes the actual current bytes, no decode
                self.counts['dependency_reads'] += 1
            # This validates authenticated actual output JSON independently of
            # the caller's in-memory candidate. Composition itself was already
            # executed and authenticated at construction; no second union.
            output = validate_scene(self.store, candidate['output_scene_ref'])
            require(body_hash(output) == body['composition']['scene_sha256'], 'STAGE_CERTIFICATE_OUTPUT_CHANGED')
            self.ledger.begin_replay()
            checks = []
            for entry in manifest['certificates']:
                receipt = self.store.get_json(entry['receipt_ref'], kind='t05-certificate')
                check = self.ledger.consume_committed(receipt, entry['source_id'], entry['patch_ref'])
                checks.append(dict(id=entry['source_id'], check=check))
            self.ledger.finish_replay()
            self.replay_ref = self.store.put_json('t05-stage-replay', dict(
                schema=SCHEMA, input_sha256=body['input_sha256'], ledger_head=self.ledger.head,
                manifest_ref=body['manifest_ref'], checks=checks, result=body['result']))
            self._charge()
            self.counts['verifications'] += 1
            from src.t05_outer_observer import completed_stage
            completed_stage(self,scene,policy,plan,candidate,execution_binding)
            return deepcopy(body['result'])
        finally:
            self.seconds['verify'] += perf_counter() - began

    def diagnostics(self):
        return dict(schema=SCHEMA, counts=dict(self.counts), seconds=dict(self.seconds),
            peak_bytes=self.peak_bytes, limit_bytes=self.limit_bytes,
            manifest_ref=None if self._seal is None else self._seal['body']['manifest_ref'],
            replay_ref=self.replay_ref,
            trust='PROCESS_LOCAL_COMPLETED_CONSTRUCTOR; no portable unsigned-JSON authority')
