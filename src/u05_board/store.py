"""New U05 artifacts with hash-checked, strictly read-only U04 operands."""
from pathlib import Path
import os,stat
from src.stage_abi.store import ArtifactStore,digest
from src.stage_abi.contracts import ref as validate_ref,StageABIError

class ReadOnlyStore(ArtifactStore):
    def __init__(self,root):
        self.root=Path(root)
        if not self.root.is_dir() or self.root.is_symlink():raise ValueError('U05_RETAINED_STORE_REQUIRED')
    def put(self,*a,**k):raise ValueError('U05_PREDECESSOR_WRITE_FORBIDDEN')
    def get(self,reference,*,kind=None):
        validate_ref(reference,'artifact_ref');aid=reference['artifact_id'];parts=aid.split(':',1)
        if len(parts)!=2 or parts[1]!=reference['sha256'] or (kind is not None and parts[0]!=kind):raise StageABIError('ARTIFACT_KIND_MISMATCH',aid)
        # One atomic no-follow open replaces separate symlink/stat/open walks.
        # Bytes are never cached: every access still reads and SHA-256 checks.
        try:
            fd=os.open(self.root/'artifacts'/aid,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
            with os.fdopen(fd,'rb') as stream:
                if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):raise StageABIError('ARTIFACT_MISSING_OR_UNSAFE',aid)
                body=stream.read()
        except OSError as error:raise StageABIError('ARTIFACT_MISSING_OR_UNSAFE',aid) from error
        if digest(body)!=reference['sha256']:raise StageABIError('ARTIFACT_CORRUPTED',aid)
        return body

class OverlayStore(ArtifactStore):
    def __init__(self,root,predecessor,evidence=None):
        super().__init__(root);self.predecessor=ReadOnlyStore(predecessor);self.own=ReadOnlyStore(root);self.evidence=evidence;self._locations={};self._reads={}
    def put(self,kind,blob):
        h=digest(blob);reference=dict(artifact_id=kind+':'+h,sha256=h);aid=reference['artifact_id'];path=self.predecessor.root/'artifacts'/aid
        if aid in self._locations or (self.root/'artifacts'/aid).exists():
            if self.get(reference,kind=kind)!=blob:raise ValueError('U05_ARTIFACT_CHANGED')
            return reference
        if path.exists() or path.is_symlink():
            if self.get(reference,kind=kind)!=blob:raise ValueError('U05_RETAINED_ARTIFACT_CHANGED')
            if self.evidence is not None:self.evidence[str(path.absolute())]=h
            return reference
        return super().put(kind,blob)
    def get(self,reference,*,kind=None):
        aid=reference['artifact_id'];path=self.root/'artifacts'/aid
        if aid in self._locations:
            layer=self._locations[aid];path=layer.root/'artifacts'/aid;blob=layer.get(reference,kind=kind)
        elif path.exists() or path.is_symlink():layer=self.own;blob=layer.get(reference,kind=kind)
        else:
            layer=self.predecessor;path=layer.root/'artifacts'/aid;blob=layer.get(reference,kind=kind)
        self._locations[aid]=layer;self._reads[aid]=dict(reference)
        if self.evidence is not None:self.evidence[str(path.absolute())]=digest(blob)
        return blob

    def verify_reads(self):
        # Cache only artifact locations, never bytes or an unverified stat result.
        # Re-read and hash every operand before using an operation-local result.
        for reference in list(self._reads.values()):self.get(reference)
