"""Transparent APFS encoding for newly written evidence, never old artifacts.

All consumers still read the original bytes. Content hashes, logical-byte
budgets, geometry and gate values are unchanged. Encoding occurs on a pending
file before its immutable name is published. A failed encoding is retained and
halts; no internal-storage or historical-artifact fallback is permitted.
"""
import os
from pathlib import Path
import shutil
import stat
import subprocess
import uuid

THRESHOLD_BYTES = 64 * 1024
RESERVE_BYTES = 5 * 1024**3
VERIFY_CHUNK_BYTES = 1024 * 1024
_backing = None


def policy():
    return dict(schema='gerber-evidence-filesystem-encoding/1',
                mode='NEW_FILES_ONLY_BEFORE_IMMUTABLE_PUBLICATION',
                method='/usr/bin/ditto --noclone --hfsCompression',
                threshold_bytes=THRESHOLD_BYTES,
                verification='EXACT_CHUNKED_BYTE_EQUALITY_AND_EOF',
                budget_basis='ORIGINAL_LOGICAL_BYTES_NOT_COMPRESSED_SIZE',
                reserve_bytes=RESERVE_BYTES,
                geometry_change='NONE', historical_files_modified=False)


def _require_directory(path, temporary_bytes):
    global _backing
    from .workspace import configure, IMAGE
    if _backing is None: _backing = configure().resolve()
    parent = Path(path).parent.resolve()
    if (not parent.is_relative_to(_backing)
            or parent.stat().st_dev != _backing.stat().st_dev):
        raise ValueError('EVIDENCE_ENCODING_REQUIRES_VERIFIED_LACIE_DIRECTORY')
    from src.cleanup_runtime import is_portable
    free = shutil.disk_usage(_backing).free if is_portable() else min(shutil.disk_usage(_backing).free, shutil.disk_usage(IMAGE.parent).free)
    if free < RESERVE_BYTES + temporary_bytes + 64 * 1024:
        raise ValueError('EVIDENCE_ENCODING_TRANSIENT_SPACE_RESERVE_REQUIRED')


def verify_bytes(path, blob):
    """Bound verification memory even when an artifact is large."""
    with Path(path).open('rb') as stream:
        view = memoryview(blob)
        for offset in range(0, len(blob), VERIFY_CHUNK_BYTES):
            if stream.read(VERIFY_CHUNK_BYTES) != view[offset:offset+VERIFY_CHUNK_BYTES]:
                raise ValueError('EVIDENCE_ENCODING_BYTES_CHANGED:' + str(path))
        if stream.read(1):
            raise ValueError('EVIDENCE_ENCODING_TRAILING_BYTES:' + str(path))


def prepare_pending(path, blob):
    """Prepare only the caller's new temporary; final artifacts are never opened."""
    if len(blob) < THRESHOLD_BYTES: return False
    path = Path(path)
    if path.is_symlink() or not stat.S_ISREG(path.stat().st_mode):
        raise ValueError('EVIDENCE_ENCODING_PENDING_FILE_UNSAFE')
    _require_directory(path, len(blob))
    encoded = path.with_name(path.name + '.encoded-' + uuid.uuid4().hex)
    result = subprocess.run(['/usr/bin/ditto', '--noclone', '--hfsCompression',
                             str(path), str(encoded)], capture_output=True, text=True)
    if result.returncode:
        raise ValueError('EVIDENCE_ENCODING_FAILED:' + str(encoded) + ':' + result.stderr)
    if encoded.is_symlink() or not stat.S_ISREG(encoded.stat().st_mode):
        raise ValueError('EVIDENCE_ENCODING_OUTPUT_UNSAFE:' + str(encoded))
    verify_bytes(encoded, blob)
    with encoded.open('rb') as stream: os.fsync(stream.fileno())
    os.replace(encoded, path)
    return True


def write_new(path, blob):
    """Exclusive publication for large JSON; return False for the old small path."""
    if len(blob) < THRESHOLD_BYTES: return False
    path = Path(path)
    _require_directory(path, 2 * len(blob))
    pending = path.with_name('.' + path.name + '.pending-' + uuid.uuid4().hex)
    with pending.open('xb') as stream:
        stream.write(blob); stream.flush(); os.fsync(stream.fileno())
    prepare_pending(pending, blob)
    # A hard link publishes these same verified bytes without overwriting an
    # existing immutable result, even if another writer won the publication.
    os.link(pending, path)
    pending.unlink()
    return True
