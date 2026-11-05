"""Additive producer custody for the explicitly authorized canonical revision.

The historical baseline and its mismatches remain intact. New source-wide jobs
bind the complete current producer set, exact entry source archive, pinned
geometry kernels and unchanged numerical verifiers, and the canonical semantic contract. No old job is resealed.
"""
import json
from pathlib import Path
from src.stage_abi.store import digest
from src.t01_canonical import marker
ROOT=Path(__file__).resolve().parents[1]
AUTHORITY=ROOT/'out/lacie_work/evidence/canonical_T01_restoration_20261104T135353Z/ENTRY.json'

def producers():
    files=[ROOT/'AGENTS.md',ROOT/'requirements.lock.txt',*[p for folder in ('src','tools','contracts','tests')for p in (ROOT/folder).rglob('*')if p.is_file()and(p.suffix=='.py'or folder=='contracts')]]
    return {str(p.relative_to(ROOT)):digest(p.read_bytes())for p in sorted(files)}

def historical(baseline):
    blob=Path(baseline).read_bytes();value=json.loads(blob)
    # Preserve the original closed baseline's representation and complete list.
    files=value.get('files',value)
    if not isinstance(files,dict):raise ValueError('T01_HISTORICAL_BASELINE_INVALID')
    mismatches=[]
    for name,h in files.items():
        if not isinstance(h,str):raise ValueError('T01_HISTORICAL_BASELINE_INVALID')
        p=ROOT/name
        current=digest(p.read_bytes())if p.is_file()else None
        if current!=h:mismatches.append(dict(path=name,historical_sha256=h,current_sha256=current))
    return dict(baseline_sha256=digest(blob),files=len(files),status='FAIL_RETAINED'if mismatches else'PASS_HISTORICAL_BYTES',mismatches=mismatches,acceptance='UNCHANGED; not a refresh or promotion')

def create(baseline):
    entry=json.loads(AUTHORITY.read_bytes());before=entry['source_before_sha256'];directory=AUTHORITY.parent/'source_before'
    if entry['branch']!='codex/c03-coverage-recovery' or 'canonical deterministic T01'not in entry['owner_request']:raise ValueError('T01_CANONICAL_AUTHORITY_REQUIRED')
    for name,h in before.items():
        if digest((directory/name).read_bytes())!=h:raise ValueError('T01_CANONICAL_ENTRY_ARCHIVE_CHANGED:'+name)
    now=producers();changed=[dict(path=p,before_sha256=before.get(p),after_sha256=h)for p,h in now.items()if before.get(p)!=h]
    return dict(schema='t01-canonical-producer-custody/1',canonical_t01=marker(),authority_sha256=digest(AUTHORITY.read_bytes()),producer_files=now,authorized_revision_delta=changed,historical_baseline=historical(baseline),status='BOUND_NEW_CANONICAL_REVISION_ONLY')

def check(record,baseline):
    if record!=create(baseline):raise ValueError('T01_CANONICAL_PRODUCER_OR_AUTHORITY_CHANGED')
    return dict(status='PASS_CANONICAL_CUSTODY_ONLY',reconciliation_sha256=None,canonical_t01=marker(),producer_files=len(record['producer_files']),historical_baseline=record['historical_baseline'])
