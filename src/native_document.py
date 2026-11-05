"""Immutable native-document arena, produced only by the maintained parser.

This is a private read representation, not a parser or source of authority.
Explicit mutable_copy returns the exact legacy list/sexpdata atom types.
"""
import json,struct,sys,operator
from array import array
from collections.abc import Sequence
import sexpdata

HEADER=struct.Struct('<8sIII')
MAGIC=b'PCBND01\0'
LIST,SYMBOL,STRING,INTEGER,FLOAT,BOOL,NONE,QUOTED=range(8)

class NativeSequence(Sequence):
    __slots__=()
    def __eq__(self,other):
        if not isinstance(other,(NativeSequence,list)):return False
        if len(self)!=len(other):return False
        if isinstance(self,NativeNode) and isinstance(other,NativeNode):
            if self._doc is other._doc and self._index==other._index:return True
            if self._index==other._index==0 and self._doc.blob==other._doc.blob:return True
        return all(a==b for a,b in zip(self,other))
    def __ne__(self,other):return not self==other
    def __deepcopy__(self,memo):return self
    def mutable_copy(self):return [mutable_copy(item) for item in self]

class NativeNode(NativeSequence):
    __slots__=('_doc','_index')
    def __init__(self,doc,index):object.__setattr__(self,'_doc',doc);object.__setattr__(self,'_index',index)
    def __setattr__(self,*args):raise TypeError('NATIVE_DOCUMENT_READ_ONLY')
    def __len__(self):return self._doc.words[self._index]&0xffffffff
    def __iter__(self):
        doc=self._doc;index=self._index+1
        for _ in range(len(self)):
            yield doc.value(index);index=doc.skip(index)
        if index!=doc.skip(self._index):raise ValueError('NATIVE_DOCUMENT_CHILDREN')
    def named_children(self,key):
        doc=self._doc;index=self._index+1;found=[]
        for _ in range(len(self)):
            if doc.tags[index]==LIST and doc.words[index]&0xffffffff:
                head=index+1
                if doc.tags[head]==SYMBOL:name=doc.symbols[doc.words[head]]
                else:
                    value=doc.value(head);name=str(mutable_copy(value)) if isinstance(value,NativeSequence) else str(value)
                if name==key:found.append(NativeNode(doc,index))
            index=doc.skip(index)
        return found
    def first_named_tail(self,key,default=None):
        doc=self._doc;index=self._index+1;first=None;count=0
        # Keep the complete head scan: a later malformed head must still fail.
        # Only the selected tail gets a view; no match list or node slice is built.
        for _ in range(len(self)):
            if doc.tags[index]==LIST and doc.words[index]&0xffffffff:
                head=index+1
                if doc.tags[head]==SYMBOL:name=doc.symbols[doc.words[head]]
                else:
                    value=doc.value(head);name=str(mutable_copy(value)) if isinstance(value,NativeSequence) else str(value)
                if name==key and first is None:first=doc.skip(head);count=(doc.words[index]&0xffffffff)-1
            index=doc.skip(index)
        return NativeTail(doc,first,count) if first is not None else default
    def __getitem__(self,key):
        if isinstance(key,slice):
            start,stop,step=key.indices(len(self))
            if self._index!=0 and step==1:
                doc=self._doc;index=self._index+1
                for _ in range(start):index=doc.skip(index)
                return NativeTail(doc,index,max(stop-start,0))
            return NativeSlice(self,tuple(range(start,stop,step)))
        key=operator.index(key)
        if key<0:key+=len(self)
        if not 0<=key<len(self):raise IndexError(key)
        doc=self._doc
        if self._index==0:return doc.value(doc.root_indices[key])
        index=self._index+1
        for _ in range(key):index=doc.skip(index)
        return doc.value(index)

class NativeTail(NativeSequence):
    """Immutable contiguous values of one field, without an index tuple."""
    __slots__=('_doc','_index','_count')
    def __init__(self,doc,index,count):
        object.__setattr__(self,'_doc',doc);object.__setattr__(self,'_index',index);object.__setattr__(self,'_count',count)
    def __setattr__(self,*args):raise TypeError('NATIVE_DOCUMENT_READ_ONLY')
    def __len__(self):return self._count
    def __iter__(self):
        doc=self._doc;index=self._index
        for _ in range(self._count):
            yield doc.value(index);index=doc.skip(index)
    def __getitem__(self,key):
        if isinstance(key,slice):
            start,stop,step=key.indices(self._count)
            if step==1:
                doc=self._doc;index=self._index
                for _ in range(start):index=doc.skip(index)
                return NativeTail(doc,index,max(stop-start,0))
            return NativeSlice(self,tuple(range(start,stop,step)))
        try:index=operator.index(key)
        except TypeError:
            if getattr(type(key),'__index__',None) is not None:raise
            raise TypeError('tuple indices must be integers or slices, not '+type(key).__name__) from None
        if index<0:index+=self._count
        if not 0<=index<self._count:raise IndexError('tuple index out of range')
        doc=self._doc;position=self._index
        for _ in range(index):position=doc.skip(position)
        return doc.value(position)

class NativeSlice(NativeSequence):
    __slots__=('_owner','_indices')
    def __init__(self,owner,indices):object.__setattr__(self,'_owner',owner);object.__setattr__(self,'_indices',indices)
    def __setattr__(self,*args):raise TypeError('NATIVE_DOCUMENT_READ_ONLY')
    def __len__(self):return len(self._indices)
    def __iter__(self):
        if not self._indices:return
        # Coordinate-tail slices dominate geometry reads. Decode exactly the
        # selected contiguous children, without allocating/skipping head atoms.
        if isinstance(self._owner,NativeNode) and self._indices[-1]-self._indices[0]==len(self._indices)-1:
            owner=self._owner;doc=owner._doc;first=self._indices[0]
            index=doc.root_indices[first] if owner._index==0 else owner._index+1
            if owner._index!=0:
                for _ in range(first):index=doc.skip(index)
            for _ in self._indices:
                yield doc.value(index);index=doc.skip(index)
        else:
            for index in self._indices:yield self._owner[index]
    def __eq__(self,other):
        if isinstance(self._owner,NativeNode) and self._owner._index==0 and isinstance(other,NativeNode) and other._index==0 and self._indices==tuple(range(len(other))):
            if self._owner._doc.prefix_equal(len(self),other._doc):return True
        return super().__eq__(other)
    def __getitem__(self,key):
        if isinstance(key,slice):return NativeSlice(self._owner,self._indices[key])
        return self._owner[self._indices[key]]

def mutable_copy(value):
    if isinstance(value,NativeSequence):return value.mutable_copy()
    if type(value) is list:return [mutable_copy(x) for x in value]
    # Readers get new Symbol/String objects, never shared mutable atom metadata.
    if type(value) is sexpdata.Symbol:return sexpdata.Symbol(str(value))
    if type(value) is sexpdata.String:return sexpdata.String(str(value))
    return value

class NativeDocument:
    __slots__=('blob','tags','words','floats','pool','symbols','symbol_bytes','count','root_indices')
    def __init__(self,blob):
        if type(blob) is not bytes or len(blob)<HEADER.size:raise ValueError('NATIVE_DOCUMENT_HEADER')
        magic,n,symlen,poollen=HEADER.unpack_from(blob)
        if magic!=MAGIC or sys.byteorder!='little' or len(blob)!=HEADER.size+9*n+symlen+poollen:raise ValueError('NATIVE_DOCUMENT_LAYOUT')
        start=HEADER.size;view=memoryview(blob);symbols_start=start+9*n
        symbol_bytes=blob[symbols_start:symbols_start+symlen];symbols=json.loads(symbol_bytes)
        if type(symbols)is not list or any(type(s)is not str for s in symbols):raise ValueError('NATIVE_DOCUMENT_SYMBOLS')
        for key,val in dict(blob=blob,tags=view[start:start+n],words=view[start+n:start+9*n].cast('Q'),floats=view[start+n:start+9*n].cast('d'),pool=view[symbols_start+symlen:],symbols=tuple(symbols),symbol_bytes=symbol_bytes,count=n).items():object.__setattr__(self,key,val)
        indices=array('I');i=1
        if n==0:raise ValueError('NATIVE_DOCUMENT_EMPTY_ARENA')
        if self.tags[0]==LIST:
            for _ in range(self.words[0]&0xffffffff):indices.append(i);i=self.skip(i)
            if i!=n:raise ValueError('NATIVE_DOCUMENT_ROOT_BOUNDS')
        object.__setattr__(self,'root_indices',memoryview(indices.tobytes()).cast('I'))
    def __setattr__(self,*args):raise TypeError('NATIVE_DOCUMENT_READ_ONLY')
    def data_binding(self):
        return (self.tags,self.words,self.floats,self.pool,self.symbols,self.root_indices,self.count,self.symbol_bytes)
    def validate_binding(self,blob,binding):
        now=self.data_binding()
        if len(now)!=len(binding) or any(a is not b for a,b in zip(now,binding)):
            raise ValueError('NATIVE_DOCUMENT_BINDING')
        if self.blob is not blob or self.tags.obj is not blob or self.words.obj is not blob or self.pool.obj is not blob:raise ValueError('NATIVE_DOCUMENT_BINDING')
        if json.dumps(list(self.symbols),ensure_ascii=False,separators=(',',':')).encode()!=self.symbol_bytes:raise ValueError('NATIVE_DOCUMENT_SYMBOL_BINDING')
    def value(self,index):
        if not 0<=index<self.count:raise ValueError('NATIVE_DOCUMENT_INDEX')
        kind=self.tags[index];word=self.words[index]
        if kind==LIST:return NativeNode(self,index)
        if kind==SYMBOL:
            if word>=len(self.symbols):raise ValueError('NATIVE_DOCUMENT_SYMBOL_INDEX')
            return sexpdata.Symbol(self.symbols[word])
        if kind==FLOAT:return self.floats[index]
        if kind==BOOL:return bool(word)
        if kind==NONE:return None
        if kind not in (STRING,INTEGER,QUOTED):raise ValueError('NATIVE_DOCUMENT_TAG')
        offset,length=word>>32,word&0xffffffff
        if offset+length>len(self.pool):raise ValueError('NATIVE_DOCUMENT_STRING_BOUNDS')
        value=self.pool[offset:offset+length].tobytes().decode('utf-8')
        return int(value) if kind==INTEGER else sexpdata.String(value) if kind==QUOTED else value
    def skip(self,index):return self.words[index]>>32 if self.tags[index]==LIST else index+1
    def prefix_equal(self,length,other):
        if length!=len(other.root) or length>len(self.root):return False
        end=self.skip(self.root_indices[length-1]) if length else 1
        if end!=other.count:return False
        if self.symbols[:len(other.symbols)]!=other.symbols or len(self.pool)<len(other.pool):return False
        return (self.tags[1:end].tobytes()==other.tags[1:].tobytes() and
                self.words[1:end].tobytes()==other.words[1:].tobytes() and
                self.pool[:len(other.pool)].tobytes()==other.pool.tobytes())
    @property
    def root(self):return self.value(0)
    @property
    def estimated_bytes(self):return len(self.blob)+len(self.root_indices)*4+2048+sum(sys.getsizeof(s) for s in self.symbols)

    @classmethod
    def from_owned_tree(cls,tree):
        if sys.byteorder!='little':raise ValueError('NATIVE_DOCUMENT_ENDIAN')
        tags=bytearray();words=array('Q');pool=bytearray();symbols=[];symbol_ids={}
        def text_word(text):
            encoded=text.encode('utf-8');offset=len(pool);pool.extend(encoded)
            if max(offset,len(encoded))>=2**32:raise ValueError('NATIVE_DOCUMENT_SIZE')
            return offset<<32|len(encoded)
        def visit(value):
            index=len(tags)
            if index>=2**32:raise ValueError('NATIVE_DOCUMENT_SIZE')
            tags.append(0);words.append(0);t=type(value)
            if t is list:
                length=len(value)
                for j in range(length):
                    child=value[j];value[j]=None;visit(child)
                words[index]=len(tags)<<32|length
            elif t is sexpdata.Symbol:
                tags[index]=SYMBOL;text=str(value)
                if text not in symbol_ids:symbol_ids[text]=len(symbols);symbols.append(text)
                words[index]=symbol_ids[text]
            elif t in (str,sexpdata.String):tags[index]=STRING if t is str else QUOTED;words[index]=text_word(str(value))
            elif t is int:tags[index]=INTEGER;words[index]=text_word(str(value))
            elif t is float:tags[index]=FLOAT;words[index]=struct.unpack('=Q',struct.pack('=d',value))[0]
            elif t is bool:tags[index]=BOOL;words[index]=int(value)
            elif value is None:tags[index]=NONE
            else:raise TypeError('NATIVE_DOCUMENT_UNSUPPORTED_ATOM')
            return index
        visit(tree);symbol_bytes=json.dumps(symbols,ensure_ascii=False,separators=(',',':')).encode()
        blob=HEADER.pack(MAGIC,len(tags),len(symbol_bytes),len(pool))+bytes(tags)+words.tobytes()+symbol_bytes+bytes(pool)
        return cls(blob)
