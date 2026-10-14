"""Byte locators for native S-expressions; semantics remain with sexpdata.

This scanner only retains source spans and parent occurrences. It does not
interpret KiCad geometry, repair malformed files, or reserialize source bytes.
"""
from dataclasses import dataclass
import hashlib

class LocatorError(ValueError):
    pass

@dataclass(frozen=True)
class SourceSpan:
    revision: str
    start: int
    end: int
    parent_start: int | None
    head: str

    @property
    def identity(self):
        return f'{self.revision}:bytes:{self.start}:{self.end}'

    def bytes_from(self,source):
        if hashlib.sha256(source).hexdigest()!=self.revision:
            raise LocatorError('SOURCE_REVISION_MISMATCH')
        return source[self.start:self.end]

def locate(source:bytes):
    """Return every list occurrence in source order, including nested objects.

    Byte offsets refer to the original UTF-8 artifact, rather than decoded
    character offsets. A repeated UUID has no effect on occurrence identity.
    """
    revision=hashlib.sha256(source).hexdigest()
    stack=[];closed=[];quoted=False;escaped=False;comment=False
    for index,value in enumerate(source):
        if comment:
            if value in (10,13):comment=False
            continue
        if quoted:
            if escaped:escaped=False
            elif value==92:escaped=True
            elif value==34:quoted=False
            continue
        if value==59:comment=True
        elif value==34:quoted=True
        elif value==40:stack.append((index,stack[-1][0] if stack else None))
        elif value==41:
            if not stack:raise LocatorError(f'UNMATCHED_CLOSE at byte {index}')
            start,parent=stack.pop()
            body=source[start+1:index].lstrip()
            head=body.split(None,1)[0].split(b')',1)[0] if body else b''
            if b'(' in head:head=head.split(b'(',1)[0]
            try:name=head.decode('utf-8')
            except UnicodeDecodeError as exc:raise LocatorError('INVALID_UTF8_HEAD') from exc
            closed.append(SourceSpan(revision,start,index+1,parent,name))
    if quoted:raise LocatorError('UNTERMINATED_STRING')
    if stack:raise LocatorError('UNTERMINATED_LIST')
    return sorted(closed,key=lambda span:span.start)
