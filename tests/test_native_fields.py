import copy,struct
import pytest,sexpdata
from src.native_document import NativeDocument,NativeTail,NativeSequence,mutable_copy,HEADER
from src.native_reference import children,one
from src.native_inventory import geometry
from shapely import to_wkb

def slow_one(node,key,default=None):
    found=children(node,key);return found[0][1:] if found else default

def witness(value):
    if isinstance(value,NativeSequence):value=mutable_copy(value)
    if type(value)is list:return ('list',tuple(map(witness,value)))
    if type(value)is float:return ('float',struct.pack('!d',value))
    return (type(value),str(value) if isinstance(value,str) else value)

@pytest.mark.parametrize('key',['start','empty','duplicate','quoted','1.0',"[Symbol('nested')]",'absent'])
def test_first_field_matches_complete_previous_query(key):
    text='(board (start -0.0 12345678901234567890 "µ" symbol) (empty) (duplicate 1) (duplicate 2) ("quoted" z) (1.0 y) ((nested) x))'
    node=NativeDocument.from_owned_tree(sexpdata.loads(text)).root;default=object()
    actual=one(node,key,default);expected=slow_one(node,key,default)
    if expected is default:assert actual is default
    else:assert witness(actual)==witness(expected) and isinstance(actual,NativeTail)

@pytest.mark.parametrize('key',[0,-1,1,True,slice(None),slice(None,None,-1),slice(1,3),slice(0,0)])
def test_indexing_slicing_and_negative_indices_match_previous_view(key):
    node=NativeDocument.from_owned_tree(sexpdata.loads('(board (field a -0.0 (nested x) "z"))')).root
    assert witness(one(node,'field')[key])==witness(slow_one(node,'field')[key])

@pytest.mark.parametrize('key',[20,-20,1.5,None,slice(None,None,0)])
def test_index_errors_match_previous_view(key):
    node=NativeDocument.from_owned_tree(sexpdata.loads('(board (field 1 2))')).root;errors=[]
    for tail in [slow_one(node,'field'),one(node,'field')]:
        try:tail[key]
        except Exception as e:errors.append((type(e),str(e)))
    assert len(errors)==2 and errors[0]==errors[1]

def test_stateful_index_protocol_is_called_once():
    node=NativeDocument.from_owned_tree(sexpdata.loads('(board (field 1 2))')).root
    class Index:
        def __init__(self):self.calls=0
        def __index__(self):self.calls+=1;return 1
    for tail in [slow_one(node,'field'),one(node,'field')]:
        index=Index();assert tail[index]==2 and index.calls==1

def test_tail_mutation_rejects_and_mutable_copy_is_separate():
    node=NativeDocument.from_owned_tree(sexpdata.loads('(board (field a (nested 1)))')).root
    tail=one(node,'field');assert copy.deepcopy(tail) is tail
    with pytest.raises(TypeError):tail._index=0
    with pytest.raises(TypeError):tail[0]='changed'
    modified=mutable_copy(tail);modified[1].append('edit');assert witness(tail)==witness(slow_one(node,'field'))

def test_later_malformed_head_still_rejects_after_an_earlier_match():
    doc=NativeDocument.from_owned_tree(sexpdata.loads('(board (field 1) (later 2))'))
    head=doc.root_indices[2]+1;blob=bytearray(doc.blob);blob[HEADER.size+head]=255
    node=NativeDocument(bytes(blob)).root;errors=[]
    for query in [slow_one,one]:
        with pytest.raises(ValueError,match='NATIVE_DOCUMENT_TAG') as e:query(node,'field')
        errors.append(str(e.value))
    assert errors[0]==errors[1]

@pytest.mark.parametrize('source,kind',[
 ('(gr_circle (center 0 0) (end 1 0) (stroke (width 0.1)) (fill none))','gr_circle'),
 ('(gr_line (start -0.0 0) (end 1 2) (stroke (width .2)))','gr_line'),
 ('(gr_rect (start 0 0) (end 1 2) (stroke (width 0)) (fill solid))','gr_rect'),
 ('(gr_poly (pts (xy 0 0) (xy 1 0) (xy 0 1)) (stroke (width 0)) (fill yes))','gr_poly')])
def test_native_geometry_and_field_types_match_maintained_parser(source,kind):
    old=sexpdata.loads(source);new=NativeDocument.from_owned_tree(sexpdata.loads(source)).root
    assert to_wkb(geometry(old,kind))==to_wkb(geometry(new,kind))

def test_plain_legacy_queries_remain_unchanged():
    node=sexpdata.loads('(board (field 1) (field 2))');default=object()
    assert type(one(node,'field'))is list and one(node,'field')==[1]
    assert one(node,'absent',default) is default
