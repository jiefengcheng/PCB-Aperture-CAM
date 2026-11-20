"""Opt-in, process-local proof-carrying acceptance of additive T05 patches.

The issuer runs the existing physical checker ONCE for a proposal and proves
containment in freshly certified local cells (including explicitly labelled
contact collars/numerical regions). Acceptance records a hash chain of frozen
patches. Every later issue must account for the whole accepted prefix, either
as a current obstacle or under the existing explicit owner-exemption policy.

Consumers check authenticated input bindings, the actual artifact bytes, local
containment and the ordered acceptance chain. They never measure clearance to
old patches again. Future growth preserves the invariant when IT is admitted.
The authority key is ephemeral and never serialized: this prototype is scoped
to the existing single-process construction/replay ABI, not portable trust in
an arbitrary JSON 'passed' flag. Persisted receipts remain engineering evidence.
"""
from hashlib import sha256
from hmac import digest as mac, compare_digest
from secrets import token_bytes
from time import perf_counter
from collections import Counter
from math import isfinite
from src.t05_certified_enclosure import window_policy_proof,WINDOW_SCHEMA
from shapely import from_wkb,to_wkb
from src.stage_abi.store import canonical
from src.stage_abi.loaded_geometry import geometry_checksum

SCHEMA='t05-incremental-certificate/2'
def hash_bytes(value):return sha256(value).hexdigest()
def body_hash(value):return hash_bytes(canonical(value))

class CertificateError(ValueError):pass

def require(condition,code):
    if not condition:raise CertificateError(code)

class CertificateLedger:
    """One frozen-input authority, disk-backed receipts and bounded tiny index.

    ``write``/``read`` are the actual hash-validating ArtifactStore geometry
    operations. Receipt I/O belongs to the caller's external job directory.
    Only compact committed references are retained; the declared 128 KiB ledger
    reservation is taken from the existing certificate-cache partition.
    """
    def __init__(self,binding,write,read,*,limit_bytes=128*1024,area_epsilon_mm2=1e-12):
        require(type(area_epsilon_mm2)in(int,float)and isfinite(area_epsilon_mm2)and area_epsilon_mm2>=0,'CERTIFICATE_WINDOW_POLICY_INVALID')
        # In the real adapter, policy is the complete source-bound T05 policy.
        # Refuse an epsilon inconsistent with that frozen policy. Tiny synthetic
        # unit fixtures may use a descriptive binding without a policy object.
        declared=binding.get('policy')if isinstance(binding,dict)else None
        if isinstance(declared,dict)and isinstance(declared.get('parameters'),dict):
            require(declared['parameters'].get('area_epsilon_mm2')==area_epsilon_mm2,'CERTIFICATE_WINDOW_POLICY_BINDING')
        self.area_epsilon_mm2=float(area_epsilon_mm2)
        self.binding=body_hash(dict(inputs=binding,window_area_epsilon_mm2=self.area_epsilon_mm2));self.write=write;self.read=read
        self._key=token_bytes(32);self.base=body_hash([SCHEMA,self.binding])
        self.head=self.base;self.accepted=[];self.pending={}
        self.limit_bytes=limit_bytes;self.peak_bytes=0
        self.counts=Counter();self.seconds=Counter()
        self.replay_head=self.base;self.replay_index=0
    def _charge(self):
        size=2048+len(canonical(self.accepted))+len(canonical(self.pending))
        require(size<=self.limit_bytes,'CERTIFICATE_LEDGER_BUDGET')
        self.peak_bytes=max(self.peak_bytes,size)
    def _sign(self,body):return mac(self._key,canonical(body),'sha256').hex()
    def issue(self,sid,owner,addition,window,region,foreign,exemptions,check):
        """Freshly check the new patch; attest inputs and complete prefix.

        Exemptions must be produced by the adapter's existing owner policy;
        they never stand in for a missing or changed foreign operand. The
        physical checker receives the actual complete non-exempt foreign list.
        Failed proposals receive no accepted-state authority.
        """
        began=perf_counter()
        try:
            foreign=list(foreign);byid={key:shape for key,shape in foreign}
            require(len(byid)==len(foreign),'CERTIFICATE_DUPLICATE_OBSTACLE')
            for entry in self.accepted:
                key=entry['source_id']
                if key in byid:
                    require(hash_bytes(to_wkb(byid[key]))==entry['patch_ref']['sha256'],'CERTIFICATE_PREFIX_GEOMETRY_CHANGED')
                else:require(key in exemptions,'CERTIFICATE_PREFIX_MISSING')
            proof=check()
            self.counts['issuer_physical_checks']+=1
            if not proof['passed']:return proof,None
            if addition.is_empty:return proof,None
            require(region.is_valid and not region.is_empty,'CERTIFICATE_REGION_INVALID')
            subset=region.covers(addition) or addition.difference(region).is_empty
            require(subset,'CERTIFICATE_ISSUED_PATCH_OUTSIDE_CELLS')
            window_started=perf_counter()
            # This witness is for the ACTUAL post-filter proposal, not the raw
            # constructor material. It is authenticated with the patch bytes.
            window_proof=window_policy_proof(addition,window,area_epsilon_mm2=self.area_epsilon_mm2)
            self.seconds['window_policy_issue']+=perf_counter()-window_started
            self.counts['window_policy_issued']+=1
            patch_ref=self.write(to_wkb(addition));region_ref=self.write(to_wkb(region))
            window_ref=self.write(to_wkb(window))
            body=dict(schema=SCHEMA,binding=self.binding,source_id=sid,
                prefix_head=self.head,prefix_count=len(self.accepted),
                owner=geometry_checksum(owner),window=geometry_checksum(window),
                patch_ref=patch_ref,region_ref=region_ref,window_ref=window_ref,window_policy=window_proof,
                foreign=[[key,geometry_checksum(g)]for key,g in foreign],
                owner_exemptions=sorted(exemptions),physical_proof=proof,
                physical_proof_sha256=body_hash(proof))
            receipt=dict(body=body,authentication=self._sign(body))
            self.pending[sid]=dict(receipt_sha256=body_hash(receipt),prefix_head=self.head)
            self._charge();self.counts['issued']+=1
            return proof,receipt
        finally:self.seconds['issue']+=perf_counter()-began
    def _validate(self,receipt,sid,patch_ref,owner,window,head,index,*,committed_artifacts=False):
        body=receipt['body']
        require(compare_digest(receipt['authentication'],self._sign(body)),'CERTIFICATE_AUTHENTICATION')
        require(body['schema']==SCHEMA and body['binding']==self.binding,'CERTIFICATE_INPUT_BINDING')
        require(body['source_id']==sid and body['prefix_head']==head and body['prefix_count']==index,'CERTIFICATE_STALE_PREFIX')
        # An ordinary caller must still supply and bind current owner/window
        # geometry. A committed-artifact replay instead obtains those bindings
        # from the authenticated receipt frozen at commit. That entry point is
        # used only after the stage consumer has bound the entire current
        # source/policy/plan/candidate to the completed construction seal.
        if not committed_artifacts:
            require(body['owner']==geometry_checksum(owner) and body['window']==geometry_checksum(window),'CERTIFICATE_GEOMETRY_BINDING')
        require(body['patch_ref']==patch_ref,'CERTIFICATE_STORED_PATCH_CHANGED')
        require(body_hash(body['physical_proof'])==body['physical_proof_sha256'] and body['physical_proof']['passed'],'CERTIFICATE_PHYSICAL_PROOF')
        # Consume the separately authenticated original domain-policy witness.
        # Exact enclosure containment below is unchanged. There is deliberately
        # NO enclosure.intersection(window) or new window overlay on replay.
        wp=body['window_policy']
        require(wp['schema']==WINDOW_SCHEMA and wp['patch_sha256']==patch_ref['sha256']
            and wp['window_fingerprint']==body['window']
            and wp['area_epsilon_mm2']==self.area_epsilon_mm2
            and type(wp['outside_area_mm2'])is float and isfinite(wp['outside_area_mm2'])
            and 0<=wp['outside_area_mm2']<=self.area_epsilon_mm2
            and wp['predicate']=='GEOS_DIFFERENCE_AREA_LEQ_EXISTING_POLICY',
            'CERTIFICATE_WINDOW_WITNESS_CHANGED')
        if not committed_artifacts:
            require(body['window_ref']['sha256']==hash_bytes(to_wkb(window)),'CERTIFICATE_WINDOW_REFERENCE_CHANGED')
        self.counts['window_policy_consumed']+=1
        # Read actual immutable bytes, not the caller's in-memory candidate.
        raw=self.read(patch_ref);region_raw=self.read(body['region_ref'])
        window_raw=self.read(body['window_ref'])
        require(hash_bytes(window_raw)==body['window_ref']['sha256']
            and (committed_artifacts or window_raw==to_wkb(window)),'CERTIFICATE_WINDOW_ARTIFACT_CORRUPTED')
        require(hash_bytes(raw)==patch_ref['sha256'] and hash_bytes(region_raw)==body['region_ref']['sha256'],'CERTIFICATE_ARTIFACT_CORRUPTED')
        actual=from_wkb(raw);region=from_wkb(region_raw)
        require(actual.is_valid and not actual.is_empty and region.is_valid,'CERTIFICATE_ARTIFACT_INVALID')
        require(region.covers(actual) or actual.difference(region).is_empty,'CERTIFICATE_STORED_PATCH_OUTSIDE_CELLS')
        return body
    def commit(self,receipt,sid,patch_ref,owner,window):
        began=perf_counter()
        try:
            require(sid in self.pending and self.pending[sid]['receipt_sha256']==body_hash(receipt),'CERTIFICATE_UNISSUED')
            self._validate(receipt,sid,patch_ref,owner,window,self.head,len(self.accepted))
            entry=dict(source_id=sid,patch_ref=patch_ref,receipt_sha256=body_hash(receipt))
            require(sid not in {r['source_id']for r in self.accepted},'CERTIFICATE_DUPLICATE_ACCEPTANCE')
            self.accepted.append(entry);self.head=body_hash([self.head,entry]);self.pending.pop(sid)
            self._charge();self.counts['committed']+=1
        finally:self.seconds['commit']+=perf_counter()-began
    def begin_replay(self):self.replay_head=self.base;self.replay_index=0
    def consume(self,receipt,sid,patch_ref,owner,window):
        return self._consume(receipt,sid,patch_ref,owner,window,committed_artifacts=False)
    def consume_committed(self,receipt,sid,patch_ref):
        """Consume actual artifacts of an ALREADY committed receipt.

        This does not issue or commit authority, infer an owner, or accept a
        portable receipt. The same process-local authentication and exact
        accepted-entry/prefix checks below are mandatory. A stage-level caller
        must separately authenticate all current execution inputs. Owner and
        window were checked at commit; their unchanged authenticated artifact
        bindings avoid reconstructing route operands just to check them again.
        Actual patch/region/window bytes and exact containment still execute.
        """
        return self._consume(receipt,sid,patch_ref,None,None,committed_artifacts=True)
    def _consume(self,receipt,sid,patch_ref,owner,window,*,committed_artifacts):
        began=perf_counter()
        try:
            i=self.replay_index
            require(i<len(self.accepted),'CERTIFICATE_EXTRA_PATCH')
            expected=self.accepted[i]
            require(expected==dict(source_id=sid,patch_ref=patch_ref,receipt_sha256=body_hash(receipt)),'CERTIFICATE_REPLAY_CHANGED')
            body=self._validate(receipt,sid,patch_ref,owner,window,self.replay_head,i,committed_artifacts=committed_artifacts)
            self.replay_head=body_hash([self.replay_head,expected]);self.replay_index+=1
            self.counts['consumed']+=1
            return dict(passed=True,failures=[],certificate_schema=SCHEMA,certificate_sha256=body_hash(receipt),physical_proof_sha256=body['physical_proof_sha256'],accepted_prefix_count=i)
        finally:self.seconds['consume']+=perf_counter()-began
    def finish_replay(self):
        require(self.replay_head==self.head and self.replay_index==len(self.accepted),'CERTIFICATE_INCOMPLETE_REPLAY')
        self.counts['complete_replays']+=1
    def diagnostics(self):return dict(counts=dict(self.counts),seconds=dict(self.seconds),peak_bytes=self.peak_bytes,limit_bytes=self.limit_bytes,accepted=len(self.accepted),head=self.head,scope='PROCESS_LOCAL_TRUSTED_ISSUER; no portable unsigned-JSON authority')
