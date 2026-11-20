"""Adversarial checks of incremental certification and artifact-consuming replay."""
from copy import deepcopy
from hashlib import sha256
import pytest
from shapely import to_wkb
from shapely.geometry import box
from src.t05_certificate_verifier import CertificateLedger,CertificateError

def setup(binding=None):
    blobs={};calls=[]
    def write(raw):
        h=sha256(raw).hexdigest();ref=dict(artifact_id='geometry:'+h,sha256=h);blobs[h]=raw;return ref
    def read(ref):return blobs[ref['sha256']]
    ledger=CertificateLedger(binding or {'policy':'fixed','source':'fixed'},write,read)
    return ledger,blobs,calls

def issue(ledger,calls,sid='A',foreign=(),addition=None):
    owner=box(0,0,1,1);patch=box(1,0,1.2,1) if addition is None else addition
    window=box(-1,-1,4,4);region=patch.buffer(.01,join_style='mitre')
    def check():
        calls.append(sid)
        pairs=[dict(source_id=k,gap_mm=patch.distance(g),passed=patch.distance(g)+1e-12>=.1) for k,g in foreign]
        return dict(passed=all(v['passed']for v in pairs),failures=[] if all(v['passed']for v in pairs)else['FOREIGN_CLEARANCE'],pairs=pairs)
    proof,receipt=ledger.issue(sid,owner,patch,window,region,foreign,(),check)
    return proof,receipt,owner,patch,window

def commit(ledger,receipt,sid,owner,patch,window):
    ref=ledger.write(to_wkb(patch));ledger.commit(receipt,sid,ref,owner,window);return ref

def test_two_additions_keep_global_clearance_without_backward_checker_calls():
    l,b,c=setup();_,a,owner,patch,win=issue(l,c);ra=commit(l,a,'A',owner,patch,win)
    _,d,owner2,patch2,win2=issue(l,c,'B',[('A',patch)],box(1,1.3,1.2,2));rb=commit(l,d,'B',owner2,patch2,win2)
    assert c==['A','B']
    for _ in range(2):
        l.begin_replay();assert l.consume(a,'A',ra,owner,win)['passed'];assert l.consume(d,'B',rb,owner2,win2)['passed'];l.finish_replay()
    assert c==['A','B'] and l.diagnostics()['counts']['consumed']==4

def test_later_addition_crossing_previous_one_is_never_certified():
    l,b,c=setup();_,a,o,p,w=issue(l,c);commit(l,a,'A',o,p,w)
    proof,receipt,*_=issue(l,c,'B',[('A',p)],box(1.1,0,1.3,1))
    assert not proof['passed'] and receipt is None and len(l.accepted)==1

@pytest.mark.parametrize('change',['missing','changed'])
def test_complete_prefix_required_before_issuer_check(change):
    l,b,c=setup();_,a,o,p,w=issue(l,c);commit(l,a,'A',o,p,w)
    foreign=[] if change=='missing'else[('A',box(20,20,21,21))]
    with pytest.raises(CertificateError,match='PREFIX'):issue(l,c,'B',foreign,box(2,0,2.2,1))
    assert c==['A']

@pytest.mark.parametrize('field,value',[('binding','changed'),('prefix_head','changed'),('source_id','changed'),('physical_proof',{'passed':True,'failures':[]})])
def test_mutated_certificate_cannot_authenticate(field,value):
    l,b,c=setup();_,a,o,p,w=issue(l,c);ref=commit(l,a,'A',o,p,w)
    damaged=deepcopy(a);damaged['body'][field]=value
    l.begin_replay()
    with pytest.raises(CertificateError):l.consume(damaged,'A',ref,o,w)

def test_actual_stored_bytes_corruption_rejected():
    l,b,c=setup();_,a,o,p,w=issue(l,c);ref=commit(l,a,'A',o,p,w)
    b[ref['sha256']]=to_wkb(box(50,50,51,51));l.begin_replay()
    with pytest.raises(CertificateError,match='ARTIFACT_CORRUPTED'):l.consume(a,'A',ref,o,w)

def test_changed_owner_window_and_stored_patch_rejected():
    l,b,c=setup();_,a,o,p,w=issue(l,c);ref=commit(l,a,'A',o,p,w)
    for owner,window,reference in [(box(0,0,2,2),w,ref),(o,box(-2,-2,4,4),ref),(o,w,l.write(to_wkb(box(1,0,1.1,1))))]:
        l.begin_replay()
        with pytest.raises(CertificateError):l.consume(a,'A',reference,owner,window)

def test_unissued_duplicate_and_incomplete_replay_rejected():
    l,b,c=setup();_,a,o,p,w=issue(l,c);ref=commit(l,a,'A',o,p,w)
    with pytest.raises(CertificateError):l.commit(a,'A',ref,o,w)
    l.begin_replay()
    with pytest.raises(CertificateError,match='INCOMPLETE'):l.finish_replay()

def test_issuer_containment_rejects_patch_outside_cells():
    l,b,c=setup();o=box(0,0,1,1);p=box(1,0,2,1)
    with pytest.raises(CertificateError,match='OUTSIDE_CELLS'):
        l.issue('A',o,p,box(-1,-1,3,3),box(1,0,1.5,1),[],(),lambda:dict(passed=True,failures=[]))

def test_foreign_authority_cannot_consume_even_identical_input_bindings():
    l,b,c=setup();_,a,o,p,w=issue(l,c);ref=commit(l,a,'A',o,p,w)
    other=CertificateLedger({'policy':'fixed','source':'fixed'},l.write,l.read)
    other.accepted=deepcopy(l.accepted);other.head=l.head
    with pytest.raises(CertificateError):other.consume(a,'A',ref,o,w)


def test_window_witness_matches_exact_stored_patch_and_original_policy():
    l,b,c=setup();_,a,o,p,w=issue(l,c);ref=commit(l,a,'A',o,p,w)
    witness=a['body']['window_policy']
    assert witness['patch_sha256']==ref['sha256']and witness['outside_area_mm2']==0.
    assert witness['area_epsilon_mm2']==1e-12
    l.begin_replay();l.consume(a,'A',ref,o,w);l.finish_replay()
    assert l.counts['window_policy_issued']==1 and l.counts['window_policy_consumed']==2

def test_outside_window_patch_cannot_be_signed_even_if_callback_claims_pass():
    l,b,c=setup();o=box(0,0,1,1);p=box(1,0,1.2,1)
    with pytest.raises(ValueError,match='WINDOW_POLICY_REJECTED'):
        l.issue('A',o,p,box(0,0,1.1,1),box(0,0,2,2),[],(),lambda:dict(passed=True,failures=[]))

def test_changed_window_epsilon_is_bound_to_frozen_policy():
    with pytest.raises(CertificateError,match='WINDOW_POLICY_BINDING'):
        CertificateLedger({'policy':{'parameters':{'area_epsilon_mm2':.1}}},lambda _:None,lambda _:None)

@pytest.mark.parametrize('field,value',[('outside_area_mm2',.01),('area_epsilon_mm2',1.),('patch_sha256','changed'),('window_fingerprint','changed')])
def test_window_witness_mutation_cannot_be_consumed(field,value):
    l,b,c=setup();_,a,o,p,w=issue(l,c);ref=commit(l,a,'A',o,p,w)
    bad=deepcopy(a);bad['body']['window_policy'][field]=value;l.begin_replay()
    with pytest.raises(CertificateError):l.consume(bad,'A',ref,o,w)

def test_stored_window_artifact_corruption_rejects():
    l,b,c=setup();_,a,o,p,w=issue(l,c);ref=commit(l,a,'A',o,p,w)
    b[a['body']['window_ref']['sha256']]=to_wkb(box(50,50,51,51));l.begin_replay()
    with pytest.raises(CertificateError,match='WINDOW_ARTIFACT_CORRUPTED'):l.consume(a,'A',ref,o,w)
