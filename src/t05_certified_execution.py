"""Opt-in integration of proposal issuance and the dedicated T05 consumer.

The normal source constructor remains authoritative. This module needs no saved
reference fitting bank: its certified region is the actual checked deposit.
Reference-assisted fitting may supply a freshly certified enclosure through the
adapter hook, but cannot supply a stored PASS or omit the physical issuer.

Session authentication/receipts stay outside canonical stage values. Canonical
checks project deterministic physical evidence so fresh construction and both
independent reconstruction workers can still agree byte for byte. Every worker
creates its own authority and reissues every proposal check; no persisted HMAC
receipt is trusted across processes.
"""
from src.stage_abi.store import canonical
from src.t05_certificate_verifier import CertificateLedger, require
from src.t05_stage_certificate_consumer import StageCertificateConsumer
from src.t05_owner_exemption_preparation import prepare_owner_exemptions

PROFILE = 'source-spindle-certified-consumption/1'
MEMO_BYTES = 512*1024**2 - 512*1024
RESERVE_BYTES = 512*1024
STAGE_BYTES = 16*1024


class CertifiedExecution:
    def __init__(self, adapter, store, scene, policy, plan):
        self.adapter, self.store = adapter, store
        self.inputs = (scene, policy, plan)
        binding = dict(scene=scene, policy=policy, plan=plan, execution=self.binding())
        self.ledger = CertificateLedger(binding, lambda raw: store.put('geometry', raw),
            lambda ref: store.get(ref, kind='geometry'), limit_bytes=RESERVE_BYTES-STAGE_BYTES,
            area_epsilon_mm2=policy['parameters']['area_epsilon_mm2'])
        self.consumer = StageCertificateConsumer(self.ledger, store, limit_bytes=STAGE_BYTES)
        self.pending = {}
        self.receipts = {}
        self.seal_ref = None
        self.metadata_peak = 0

    def _charge(self):
        size=self.ledger.peak_bytes+self.consumer.peak_bytes+len(canonical(self.receipts))
        require(size<RESERVE_BYTES,'T05_CERTIFIED_EXECUTION_METADATA_BUDGET')
        self.metadata_peak=max(self.metadata_peak,size)

    def binding(self):
        return dict(profile=PROFILE, implementation=self.adapter.describe()['implementation'],
            scope=self.adapter._scope_binding(), budgets=self.adapter.geometry_budgets)

    def proposal(self, row, owner, addition, window, foreign):
        exemptions,prefix = prepare_owner_exemptions(self.ledger.accepted, owner,
            lambda ref: self.store.get(ref, kind='geometry'), self.adapter._foreign_for,with_prefix=True)
        foreign=list(foreign);present={sid for sid,_ in foreign}
        foreign.extend((sid,shape)for sid,shape in prefix if sid not in present)
        # Owner exemption is ONLY the existing clearance classification. Global
        # pin separation must see every earlier patch, including the same owner.
        # The dynamic adapter checker filters clearance itself and receives this
        # complete material list for its other safety predicates.
        candidate = self.adapter._geometry.union(owner, addition)
        proof, receipt = self.ledger.issue(row['source_id'], owner, addition, window,
            self.adapter._certificate_region(addition), foreign, exemptions,
            lambda: self.adapter._check(owner, candidate, addition, window, foreign))
        if receipt is not None:
            self.pending[row['source_id']] = (receipt, foreign)
        return proof

    def decline(self, sid):
        self.pending.pop(sid, None)
        self.ledger.pending.pop(sid, None)

    def accept(self, decision, owner, window, addition, physical, needs, scope):
        """Bind NORMALIZED stored copper, not a previous raw trial candidate.

        The old source constructor fills encoded patches only after a trial
        passes. When that changes bytes, freshly issue for the actual normalized
        deposit. A failed post-normalization guard stops rather than adopting an
        unqualified shape or silently substituting another treatment.
        """
        sid = decision['source_id']
        receipt, foreign = self.pending[sid]
        if receipt['body']['patch_ref'] != decision['patch_ref']:
            proof = self.proposal(decision, owner, addition, window, foreign)
            require(proof['passed'], 'T05_CERTIFIED_NORMALIZED_PHYSICAL_FAILURE')
            receipt, foreign = self.pending[sid]
        # Use the constructor's ACTUAL post-normalization, crop-bound delta.
        # Re-subtracting the uncropped adapter predecessor would both duplicate
        # work and change semantics for scoped/cropped executions.
        require(physical.difference(scope).area <= 1e-12, 'T05_CERTIFIED_NORMALIZED_SCOPE_FAILURE')
        outcomes = self.adapter.outcomes(needs, physical, decision)
        require(outcomes == decision['attachment_outcomes'] and
            not any(a['status']=='MISSING_TREATMENT' for a in outcomes), 'T05_CERTIFIED_NORMALIZED_ATTACHMENT_FAILURE')
        self.ledger.commit(receipt, sid, decision['patch_ref'], owner, window)
        self.receipts[sid] = self.store.put_json('t05-certificate', receipt)
        self.pending.pop(sid)
        self._charge()

    @staticmethod
    def projection(body):
        # Authentication nonces and receipt IDs are deliberately not stage
        # output. They remain actual sidecar artifacts, validated in-process.
        return dict(passed=True, failures=[], schema=PROFILE,
            physical_proof_sha256=body['physical_proof_sha256'],
            accepted_prefix_count=body['prefix_count'], source_id=body['source_id'],
            patch_sha256=body['patch_ref']['sha256'])

    def final(self, patch, ordinal):
        if ordinal == 0:
            self.ledger.begin_replay()
        receipt = self.store.get_json(self.receipts[patch['id']], kind='t05-certificate')
        self.ledger.consume(receipt, patch['id'], receipt['body']['patch_ref'], patch['owner'], patch['window'])
        if self.ledger.replay_index == len(self.ledger.accepted):
            self.ledger.finish_replay()
        return self.projection(receipt['body'])

    def seal(self, candidate):
        if not self.ledger.accepted:
            self.ledger.begin_replay(); self.ledger.finish_replay()
        value = self.consumer.seal(*self.inputs, candidate, self.receipts, self.binding())
        self.seal_ref = self.store.put_json('t05-construction-seal', value)
        # Account references as well as the ledger and stage consumer. No new
        # unbounded resident bank/index is introduced by this execution option.
        self._charge()

    def verify(self, scene, policy, plan, candidate, proof_scope):
        result = self.consumer.verify(scene, policy, plan, candidate, proof_scope, self.binding())
        # An ephemeral, per-worker evidence artifact, never a canonical stage
        # field. It records actual local replay plus ledger costs and counts.
        self.audit_ref = self.store.put_json('t05-execution-audit', self.diagnostics())
        return result

    def diagnostics(self):
        return dict(profile=PROFILE, ledger=self.ledger.diagnostics(), stage=self.consumer.diagnostics(),
            seal_ref=self.seal_ref, configured_memo_bytes=512*1024**2,
            metadata_peak_bytes=self.metadata_peak,metadata_limit_bytes=RESERVE_BYTES,
            scope='FRESH_PROCESS_LOCAL_ISSUANCE; exact checked deposit region; no reference bank required')
