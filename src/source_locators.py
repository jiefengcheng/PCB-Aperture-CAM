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

def locate(source:bytes, *, max_depth=None):
    """Return every list occurrence in source order, including nested objects.

    Byte offsets refer to the original UTF-8 artifact, rather than decoded
    character offsets. A repeated UUID has no effect on occurrence identity.
    """
    if max_depth is not None and (not isinstance(max_depth,int) or isinstance(max_depth,bool) or max_depth<1):
        raise LocatorError('INVALID_LOCATOR_DEPTH')
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
            if max_depth is not None and len(stack)>=max_depth:continue
            first=start+1
            while first<index and source[first] in b' \t\r\n\v\f':first+=1
            last=first
            while last<index and source[last] not in b' \t\r\n\v\f()':last+=1
            head=source[first:last]
            try:name=head.decode('utf-8')
            except UnicodeDecodeError as exc:raise LocatorError('INVALID_UTF8_HEAD') from exc
            closed.append(SourceSpan(revision,start,index+1,parent,name))
    if quoted:raise LocatorError('UNTERMINATED_STRING')
    if stack:raise LocatorError('UNTERMINATED_LIST')
    return sorted(closed,key=lambda span:span.start)
