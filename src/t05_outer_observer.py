"""Disk-backed record of actual reads and live authenticated stage completions.

This does not create a PASS. The only completion observation is emitted by the
real StageCertificateConsumer after its authenticated complete replay succeeds.
The outer issuer rechecks its live authority and all input bindings before
signing. Store reads are recorded AFTER their original content hash validation.
SQLite bounds the read-set cache; it does not retain board geometry in memory.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
import sqlite3

ACTIVE=ContextVar('t05_outer_actual_execution',default=None)
RESERVED_BYTES=1024**2


def read_observed(root,reference):
    current=ACTIVE.get()
    if current is not None:current.record(root,reference)


def completed_stage(consumer,scene,policy,plan,candidate,execution_binding):
    current=ACTIVE.get()
    if current is not None:
        current.groups.append((consumer,scene,policy,plan,candidate,execution_binding))

def worker_completed(run,name,value):
    current=ACTIVE.get()
    if current is not None:
        if Path(run).resolve()!=current.run or name!='t05' or current.worker is not None:
            raise ValueError('OUTER_WORKER_COMPLETION_SCOPE')
        current.worker=value
        from src.t05_certificate_verifier import body_hash
        current.worker_sha256=body_hash(value)


class Capture:
    def __init__(self,run,database):
        self.run=Path(run).resolve();self.path=Path(database)
        if self.path.exists():raise ValueError('OUTER_CAPTURE_ALREADY_EXISTS')
        self.db=sqlite3.connect(self.path)
        self.db.execute('PRAGMA cache_size=-128')
        self.db.execute('PRAGMA temp_store=FILE')
        self.db.execute('CREATE TABLE reads(namespace TEXT NOT NULL,artifact_id TEXT NOT NULL,sha256 TEXT NOT NULL,PRIMARY KEY(namespace,artifact_id)) WITHOUT ROWID')
        self.groups=[];self.requests=0;self.worker=None;self.worker_sha256=None;self.closed_sources_verified=False

    def record(self,root,reference):
        root=Path(root).resolve()
        if not root.is_relative_to(self.run):raise ValueError('OUTER_ARTIFACT_READ_OUTSIDE_JOB')
        namespace=str(root.relative_to(self.run))
        # Initial profile is one legacy stage and its actual runtime store.
        # Broader connected/completion stores need separate qualification.
        if namespace!='runtime':raise ValueError('OUTER_STORE_NAMESPACE_UNQUALIFIED')
        self.db.execute('INSERT OR IGNORE INTO reads VALUES(?,?,?)',
            (namespace,reference['artifact_id'],reference['sha256']))
        self.requests+=1

    @contextmanager
    def observe(self):
        token=ACTIVE.set(self)
        try:yield self
        finally:
            ACTIVE.reset(token);self.db.commit();self.db.close()

    def count(self):
        with sqlite3.connect(f'file:{self.path}?mode=ro',uri=True)as connection:
            return connection.execute('SELECT COUNT(*) FROM reads').fetchone()[0]
