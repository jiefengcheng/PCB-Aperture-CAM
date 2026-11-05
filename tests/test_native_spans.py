import pytest,sexpdata,copy,struct
from src.native_document import NativeDocument,NativeSlice,NativeTail,NativeSequence,mutable_copy
def witness(value):
    if isinstance(value,NativeSequence):value=mutable_copy(value)
    if type(value)is list:return ('list',tuple(map(witness,value)))
    if type(value)is float:return ('float',struct.pack('!d',value))
    return (type(value),str(value) if isinstance(value,str) else value)

def old_slice(owner,key):return NativeSlice(owner,tuple(range(*key.indices(len(owner)))))

@pytest.mark.parametrize('owner_kind',['node','tail'])
@pytest.mark.parametrize('key',[slice(None),slice(1,3),slice(0,0),slice(100,200),slice(-3,None),slice(None,-1),slice(None,None,2),slice(None,None,-1),slice(3,1),slice(-100,100),slice(1,1,1),slice(None,None,-2)])
def test_all_slice_values_and_types_match_previous_view(owner_kind,key):
    root=NativeDocument.from_owned_tree(sexpdata.loads('(board (field a -0.0 (nested 1) "b"))')).root
    owner=root[1] if owner_kind=='node' else root.first_named_tail('field')
    assert witness(owner[key])==witness(old_slice(owner,key))

def test_slice_index_protocol_runs_once():
    root=NativeDocument.from_owned_tree(sexpdata.loads('(board (field 1 2 3))')).root
    class Index:
        def __init__(self,n):self.n=n;self.calls=0
        def __index__(self):self.calls+=1;return self.n
    for owner in [root,root[1],root.first_named_tail('field')]:
        for make in [lambda o,k:o[k],old_slice]:
            a,b,c=Index(0),Index(2),Index(1);key=slice(a,b,c)
            assert len(make(owner,key))==2 and [a.calls,b.calls,c.calls]==[1,1,1]

def test_root_prefix_fast_comparison_remains_native_slice():
    before=NativeDocument.from_owned_tree(sexpdata.loads('(board (a 1) (b 2))')).root
    after=NativeDocument.from_owned_tree(sexpdata.loads('(board (a 1) (b 2) (extra 3))')).root
    prefix=after[:len(before)];assert isinstance(prefix,NativeSlice) and prefix==before
    changed=NativeDocument.from_owned_tree(sexpdata.loads('(board (a 9) (b 2))')).root
    assert prefix!=changed

def test_contiguous_view_is_read_only_and_mutable_copy_is_owned():
    root=NativeDocument.from_owned_tree(sexpdata.loads('(board (field a (nested 1) 2))')).root
    tail=root[1][1:3];assert isinstance(tail,NativeTail) and copy.deepcopy(tail) is tail
    with pytest.raises(TypeError):tail._count=100
    result=mutable_copy(tail);result[1].append('edit')
    assert witness(tail)==witness(old_slice(root[1],slice(1,3)))
