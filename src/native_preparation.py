"""One fresh audit's bounded immutable native-document ownership scope."""
from collections import Counter,OrderedDict
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
import hashlib
from sexpdata import loads as original_loads
from src.native_document import NativeDocument,mutable_copy
ACTIVE=ContextVar('u05_worker_preparation',default=None)
@dataclass(frozen=True)
class Entry:
    source_sha256:str
    blob:bytes
    blob_sha256:str
    weight:int
    document:object
    binding:tuple
class ParsePreparation:
    def __init__(self,binding,*,limit=32*1024**2,entries=64,minimum_source_bytes=4096):
        if any(type(v)is not int or v<0 for v in (limit,entries,minimum_source_bytes)):raise ValueError('U05_PREPARATION_BUDGET')
        self.binding=binding;self.limit=limit;self.max_entries=entries;self.minimum=minimum_source_bytes
        self.values=OrderedDict();self.weight=0;self.peak=0;self.stats=Counter()
    @staticmethod
    def sha(body):return hashlib.sha256(body).hexdigest()
    def _check(self,key,entry):
        if key[0]!=self.binding or entry.source_sha256!=key[1] or self.sha(entry.blob)!=entry.blob_sha256:raise ValueError('U05_PREPARATION_CORRUPTED')
        entry.document.validate_binding(entry.blob,entry.binding)
    def validate(self):
        for key,entry in self.values.items():self._check(key,entry)
    def _document(self,text):
        source=text.encode();self.stats['calls']+=1
        if len(source)<self.minimum:
            self.stats['bypassed_small']+=1;return original_loads(text)
        self.stats['source_bytes_hashed']+=len(source);h=self.sha(source);key=(self.binding,h);entry=self.values.get(key)
        if entry is not None:
            self._check(key,entry);self.values.move_to_end(key);self.stats['hits']+=1
            return entry.document.root
        self.stats['misses']+=1;tree=original_loads(text)
        try:doc=NativeDocument.from_owned_tree(tree)
        except (TypeError,ValueError,OverflowError):
            self.stats['not_representable']+=1;return original_loads(text)
        weight=doc.estimated_bytes+512+len(self.binding.encode())
        if weight<=self.limit and self.max_entries:
            while self.values and (self.weight+weight>self.limit or len(self.values)>=self.max_entries):
                _,old=self.values.popitem(last=False);self.weight-=old.weight;self.stats['evictions']+=1
            self.values[key]=Entry(h,doc.blob,self.sha(doc.blob),weight,doc,doc.data_binding());self.weight+=weight;self.peak=max(self.peak,self.weight)
        else:self.stats['not_retained']+=1
        return doc.root
    def view(self,text,*args,**kwargs):
        if type(text)is not str or args or kwargs:self.stats['bypassed_options']+=1;return original_loads(text,*args,**kwargs)
        return self._document(text)
    def loads(self,text,*args,**kwargs):return mutable_copy(self.view(text,*args,**kwargs))
    def close(self):self.values.clear();self.weight=0
    def diagnostics(self):return dict(self.stats,estimated_retained_bytes=self.weight,peak_estimated_bytes=self.peak,limit_bytes=self.limit,entry_count=len(self.values),entry_limit=self.max_entries)
@contextmanager
def evaluation_preparation(binding,**kwargs):
    if ACTIVE.get() is not None:raise ValueError('U05_PREPARATION_NESTED_EVALUATION')
    cache=ParsePreparation(binding,**kwargs);token=ACTIVE.set(cache)
    try:
        yield cache
        cache.validate()
    finally:cache.close();ACTIVE.reset(token)
def native_loads(text,*args,**kwargs):
    cache=ACTIVE.get();return original_loads(text,*args,**kwargs) if cache is None else cache.loads(text,*args,**kwargs)
def native_view(text,*args,**kwargs):
    cache=ACTIVE.get();return original_loads(text,*args,**kwargs) if cache is None else cache.view(text,*args,**kwargs)

@contextmanager
def preparation_scope(binding,**kwargs):
    """Join only the current worker; an outer owner always clears on exit."""
    current=ACTIVE.get()
    if current is not None:
        yield current
        current.validate()
    else:
        with evaluation_preparation(binding,**kwargs) as cache:yield cache
