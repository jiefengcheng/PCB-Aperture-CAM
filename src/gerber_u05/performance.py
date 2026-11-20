"""Job-local T02/T05 reuse settings and lifetime.

The worker binds the opt-in snapshot to its producer seal. A cache entry is a
parsed reference stream, keyed by the full input and parser/codec identities.
Each worker rebuilds ownership, reservations, and every safety witness.
"""
from pathlib import Path

SNAPSHOT = 'PERFORMANCE_REUSE_SNAPSHOT.json'
PROFILE = {
    'schema': 'pcb-cam/t02-t05-performance-reuse/1',
    'share_parsed_reference': True,
}
T05_SNAPSHOT = 'T05_CERTIFICATE_EXECUTION.json'
T05_PROFILE = {
    'schema': 'pcb-cam/t05-certificate-execution/1',
    'constructor': 'source-spindle',
    'verifier': 'completed-construction-consumer',
    'region': 'actual-physically-checked-deposit',
    'memo_bytes': 512*1024**2,
    'reference_measurement_bank': False,
}


def capture_t05(run):
    """Explicit opt-in, captured before producer sealing; no runtime toggle."""
    from .pipeline import canonical
    with (Path(run)/T05_SNAPSHOT).open('xb') as stream:
        stream.write(canonical(T05_PROFILE))


def t05_profile(run):
    from .pipeline import canonical, digest, load
    run=Path(run);path=run/T05_SNAPSHOT
    if not path.exists() and not path.is_symlink():return None
    producer=load(run/'PRODUCER_BINDING.json')
    if path.is_symlink() or producer.get('job_inputs',{}).get(str(path))!=digest(path.read_bytes()):
        raise ValueError('T05_CERTIFICATE_EXECUTION_UNBOUND')
    if path.read_bytes()!=canonical(T05_PROFILE):raise ValueError('T05_CERTIFICATE_PROFILE_UNSUPPORTED')
    return dict(T05_PROFILE)


def configure_t05_adapter(run,adapter):
    if t05_profile(run) is not None:adapter.enable_certificate_consumption()
    return adapter


def capture(run):
    """Create the opt-in snapshot before sealing a fresh connected job."""
    from .pipeline import canonical

    with (Path(run) / SNAPSHOT).open('xb') as stream:
        stream.write(canonical(PROFILE))


def parsed_reference_cache(run, stage):
    """Return a job-owned cache for the two adjacent consumers only."""
    run = Path(run)
    path = run / SNAPSHOT
    if stage not in ('t02', 't05') or not path.exists():
        return None

    from .pipeline import canonical, digest, load
    from .parsed_gerber_cache import ParsedGerberCache

    body = path.read_bytes()
    producer = load(run / 'PRODUCER_BINDING.json')
    if path.is_symlink() or producer.get('job_inputs', {}).get(str(path)) != digest(body):
        raise ValueError('PERFORMANCE_REUSE_SNAPSHOT_UNBOUND')
    if body != canonical(PROFILE):
        raise ValueError('PERFORMANCE_REUSE_PROFILE_UNSUPPORTED')

    # The read fence admits the fresh job only. A parsed cache must remain
    # job-owned even when another directory on LaCie has the same content.
    parent = run / 'performance_cache'
    root = parent / 'parsed_reference'
    if parent.is_symlink() or not root.resolve().is_relative_to(run.resolve()):
        raise ValueError('PERFORMANCE_CACHE_OUTSIDE_JOB')
    return ParsedGerberCache(root)
