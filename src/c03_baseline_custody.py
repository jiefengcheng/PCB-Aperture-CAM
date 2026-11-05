"""One explicitly authorized successor; historical baseline is immutable.

Every historical entry is checked. Only an explicit exact-source C03 job with
the pinned reconciliation marker may use the one committed successor. Source
copies, owner instruction and provenance are re-read and hashed on every call.
"""
import json
from pathlib import Path
from src.c03_recovery import bound_bytes
from src.stage_abi.store import digest

ROOT=Path(__file__).resolve().parents[1]
CONTRACT=ROOT/'contracts/operator/c03_baseline_custody.json'
CONTRACT_SHA256='204f7950f4b3f215a9314ea9a78959a6a638ac662569d02fb4168fd0f7593096'
SUCCESSOR='src/junction_spindle_blend.py'


def specification(root=ROOT):
    root=Path(root)
    value=json.loads(bound_bytes(root,'contracts/operator/c03_baseline_custody.json',CONTRACT_SHA256))
    if (set(value)!={'schema','scope','historical_baseline','authorization','source_provenance',
                     'successors','blocked_original_obligations'} or
            value['schema']!='c03-baseline-custody-successor/1' or
            value['scope']!='EXPLICIT_C03_JOB_ONLY' or len(value['successors'])!=1 or
            value['successors'][0]['path']!=SUCCESSOR or
            value['blocked_original_obligations']!=['T01:C028','T02:R304','T02:R305']):
        raise ValueError('C03_CUSTODY_CONTRACT_INVALID')
    def linked(reference):
        if set(reference)!={'path','sha256'}:raise ValueError('C03_CUSTODY_REFERENCE_INVALID')
        return bound_bytes(root,reference['path'],reference['sha256'])
    baseline_blob=linked(value['historical_baseline']);baseline=json.loads(baseline_blob)
    authorization=json.loads(linked(value['authorization']))
    provenance=json.loads(linked(value['source_provenance']))
    row=value['successors'][0]
    old=linked(row['historical_copy']);new=linked(row['successor_copy'])
    if (baseline.get(SUCCESSOR)!=row['historical_sha256'] or digest(old)!=row['historical_sha256'] or
            digest(new)!=row['successor_sha256'] or
            provenance['commit']!=row['commit'] or
            provenance['historical_file_sha256']!=digest(old) or
            provenance['successor_file_sha256']!=digest(new) or
            provenance['historical_baseline_sha256']!=digest(baseline_blob) or
            authorization['schema']!='c03-baseline-custody-owner-authorization/1' or
            authorization['branch']!='codex/c03-coverage-recovery' or
            authorization['blocked']!=value['blocked_original_obligations']):
        raise ValueError('C03_CUSTODY_PROVENANCE_CHANGED')
    return value,baseline


def marker(root=ROOT):
    value,_=specification(root)
    return dict(schema='c03-job-baseline-successor/1',contract=value,
                contract_sha256=CONTRACT_SHA256)


def check(root,session,historical_path):
    root=Path(root);session=Path(session);path=session/'C03_BASELINE_CUSTODY.json'
    historical_blob=Path(historical_path).read_bytes();historical=json.loads(historical_blob)
    if path.is_symlink():raise ValueError('C03_CUSTODY_MARKER_UNSAFE')
    reconciliation=None
    if path.exists():
        from src.c03_input_family import selected
        if not selected(session):raise ValueError('C03_CUSTODY_EXPLICIT_FAMILY_REQUIRED')
        reconciliation,expected=specification(root)
        if (json.loads(path.read_bytes())!=marker(root) or historical!=expected or
                digest(historical_blob)!=reconciliation['historical_baseline']['sha256']):
            raise ValueError('C03_CUSTODY_JOB_BINDING_CHANGED')
    successors={} if reconciliation is None else {r['path']:r for r in reconciliation['successors']}
    raw_failures=[]
    for name,original_sha in historical.items():
        # No-follow reads also reject symlink components and path traversal.
        expected=successors.get(name,{}).get('successor_sha256',original_sha)
        try:actual=digest(bound_bytes(root,name,expected))
        except ValueError as error:
            raise ValueError('BASELINE_CODE_CHANGED:'+name) from error
        if actual!=original_sha:
            raw_failures.append(dict(path=name,historical_expected_sha256=original_sha,
                                     current_sha256=actual,historical_status='FAIL_RETAINED'))
    return dict(schema='c03-baseline-custody-check/1',effective_status='PASS',
        baseline_files=len(historical),historical_baseline_sha256=digest(historical_blob),
        reconciliation_sha256=None if reconciliation is None else CONTRACT_SHA256,
        retained_historical_mismatches=raw_failures)
