"""Pinned native P-256/SHA-256 signatures for an OUTER job authority.

No handwritten cryptographic primitive, persisted private key, ambient key lookup
or certificate-supplied trust anchor. The coordinator generates the key; only
construction receives the private capability through an inherited anonymous FD.
Readers receive the coordinator-pinned public anchor. The original inner HMAC
keys remain process-local and are neither exported nor reconstructed.
"""
from dataclasses import dataclass, field
import base64
import hashlib
import os
import subprocess

BACKEND='/usr/bin/openssl'
BACKEND_SHA256='9004f458fa403d5fdb763ffffb45803b2fad45a579bf7353930e781b5db07d43'
VERSION='LibreSSL 3.3.6'
ALGORITHM='ECDSA_P256_SHA256_NATIVE/1'


def sha(raw):return hashlib.sha256(raw).hexdigest()


def backend_identity():
    with open(BACKEND,'rb')as stream:actual=sha(stream.read())
    version=subprocess.check_output([BACKEND,'version'],text=True).strip()
    if actual!=BACKEND_SHA256 or version!=VERSION:raise ValueError('OUTER_SIGNATURE_BACKEND_CHANGED')
    return dict(path=BACKEND,sha256=actual,version=version,algorithm=ALGORITHM)


def _pipe(raw):
    if len(raw)>8192:raise ValueError('OUTER_KEY_OR_SIGNATURE_TOO_LARGE')
    read,write=os.pipe()
    try:
        if os.write(write,raw)!=len(raw):raise ValueError('OUTER_KEY_PIPE_SHORT_WRITE')
    finally:os.close(write)
    return read


def public_is_p256(public):
    result=subprocess.run([BACKEND,'pkey','-pubin','-text','-noout'],input=public,capture_output=True)
    if result.returncode or b'ASN1 OID: prime256v1'not in result.stdout:
        raise ValueError('OUTER_TRUST_ANCHOR_NOT_P256')


@dataclass(repr=False)
class Signer:
    _private: bytes=field(repr=False)
    public: bytes

    @classmethod
    def generate(cls):
        backend_identity()
        private=subprocess.run([BACKEND,'ecparam','-name','prime256v1','-genkey','-noout'],capture_output=True,check=True).stdout
        public=subprocess.run([BACKEND,'pkey','-pubout'],input=private,capture_output=True,check=True).stdout
        public_is_p256(public)
        return cls(private,public)

    @classmethod
    def from_inherited_fd(cls,fd,expected_public):
        with os.fdopen(fd,'rb')as stream:private=stream.read(8193)
        if len(private)>8192:raise ValueError('OUTER_SIGNING_CAPABILITY_INVALID')
        public=subprocess.run([BACKEND,'pkey','-pubout'],input=private,capture_output=True,check=True).stdout
        if public!=expected_public:raise ValueError('OUTER_SIGNING_CAPABILITY_ANCHOR_CHANGED')
        public_is_p256(public)
        return cls(private,public)

    def inherited_fd(self):return _pipe(self._private)

    def sign(self,payload):
        backend_identity()
        fd=_pipe(self._private)
        try:
            result=subprocess.run([BACKEND,'dgst','-sha256','-sign',f'/dev/fd/{fd}'],
                input=payload,capture_output=True,pass_fds=(fd,))
        finally:os.close(fd)
        if result.returncode:raise ValueError('OUTER_NATIVE_SIGNING_FAILED')
        return base64.b64encode(result.stdout).decode('ascii')


def verify(public,payload,signature):
    """The public key MUST come from the coordinator, never the signed packet."""
    backend_identity();public_is_p256(public)
    try:raw=base64.b64decode(signature,validate=True)
    except Exception as error:raise ValueError('OUTER_SIGNATURE_ENCODING')from error
    if not 8<=len(raw)<=256:raise ValueError('OUTER_SIGNATURE_ENCODING')
    pfd,sfd=_pipe(public),_pipe(raw)
    try:
        result=subprocess.run([BACKEND,'dgst','-sha256','-verify',f'/dev/fd/{pfd}',
            '-signature',f'/dev/fd/{sfd}'],input=payload,capture_output=True,pass_fds=(pfd,sfd))
    finally:os.close(pfd);os.close(sfd)
    if result.returncode:raise ValueError('OUTER_SIGNATURE_REJECTED')
