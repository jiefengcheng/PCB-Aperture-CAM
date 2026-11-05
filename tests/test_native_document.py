import copy,struct
from dataclasses import replace
import pytest,sexpdata
from src.native_document import NativeDocument,NativeSequence,mutable_copy
from src.u05_board.worker_preparation import ParsePreparation
from src.native_inventory import geometry
from shapely import to_wkb
from shapely.geometry import box

CASES=['(board (a 1 -0.0 3.5) (name "µ") (bool t) (nil nil))', '(kicad_pcb (gr_circle (center 0 0) (end .1 0) (stroke (width 0) (type solid)) (fill yes) (layer "F.Cu")))']
@pytest.mark.parametrize('source',CASES)
def test_read_only_and_mutable_boundaries_preserve_complete_legacy_tree(source):
    expected=sexpdata.loads(source);doc=NativeDocument.from_owned_tree(sexpdata.loads(source));view=doc.root
    assert isinstance(view,NativeSequence) and view==expected and expected==view
    actual=mutable_copy(view)
    assert type(actual)is list and actual==expected
    assert sexpdata.dumps(actual)==sexpdata.dumps(expected)
    assert copy.deepcopy(view) is view
    with pytest.raises(TypeError):view[0]='changed'
    with pytest.raises(TypeError):view._index=99
    with pytest.raises(TypeError):doc.blob=b'changed'
    actual.append('edited');assert mutable_copy(view)==expected

def test_prefix_and_semantic_numeric_comparisons_preserve_original_acceptance():
    def view(s):return NativeDocument.from_owned_tree(sexpdata.loads(s)).root
    before=view('(board (a 1) (name "x"))');after=view('(board (a 1) (name "x") (extra 2))')
    assert after[:len(before)]==before
    assert before==view('(board (a 1.0) (name "x"))')
    assert before!=view('(board (a 1) (name x))')
    assert before!=view('(board (a 2) (name "x"))')
    assert before!=after
    assert list(reversed(mutable_copy(before)))==list(before[::-1])

def test_geometry_and_original_contacts_use_same_numbers_and_roles():
    doc=NativeDocument.from_owned_tree(sexpdata.loads(CASES[1]));a=doc.root[1];b=sexpdata.loads(CASES[1])[1]
    assert to_wkb(geometry(a,'gr_circle'))==to_wkb(geometry(b,'gr_circle'))

def test_cached_document_corruption_and_root_index_binding_reject():
    c=ParsePreparation('one',minimum_source_bytes=0);c.view(CASES[0]);key=next(iter(c.values));entry=c.values[key]
    object.__setattr__(entry.document,'root_indices',memoryview(b'\0'*len(entry.document.root_indices)*4).cast('I'))
    with pytest.raises(ValueError,match='NATIVE_DOCUMENT_BINDING'):c.view(CASES[0])

def test_float_bits_and_big_integer_projection_are_exact():
    source='(a -0.0 0.0 123456789012345678901234567890 1e-200)'
    expected=sexpdata.loads(source);actual=mutable_copy(NativeDocument.from_owned_tree(sexpdata.loads(source)).root)
    assert [type(x) for x in actual]==[type(x) for x in expected]
    for a,b in zip(actual,expected):
        assert struct.pack('!d',a)==struct.pack('!d',b) if type(a)is float else a==b

def test_document_cache_does_not_retain_editable_returned_ast():
    c=ParsePreparation('one',minimum_source_bytes=0);a=c.loads(CASES[0]);a[1].append('edit')
    assert c.loads(CASES[0])==sexpdata.loads(CASES[0])
    assert c.view(CASES[0])==sexpdata.loads(CASES[0])


def test_indexed_field_queries_match_legacy_children_including_unusual_heads():
    from src.native_reference import children
    source='(board (pts (xy 1 2)) (pts (xy 3 4)) ((nested) x) (1.0 y) ("quoted" z))'
    old=sexpdata.loads(source);new=NativeDocument.from_owned_tree(sexpdata.loads(source)).root
    for key in ['pts',str(old[3][0]),'1.0','quoted','absent']:
        assert [mutable_copy(x) for x in children(new,key)]==children(old,key)


@pytest.mark.parametrize('source',['1','-0.0','a','"quoted"','nil','t'])
def test_scalar_documents_retain_legacy_types_and_values(source):
    c=ParsePreparation('one',minimum_source_bytes=0)
    a,b=c.loads(source),sexpdata.loads(source)
    assert type(a)is type(b) and a==b
    assert c.loads(source)==b

def test_read_indices_preserve_list_boolean_indexing():
    node=NativeDocument.from_owned_tree(sexpdata.loads('(a b c)')).root
    assert node[True]==sexpdata.Symbol('b')


def test_native_file_acceptance_and_fault_reasons_match_legacy_parser():
    from contextlib import nullcontext
    from src.u05_board.export import U05DataService
    from src.u05_board.worker_preparation import evaluation_preparation
    service=U05DataService.__new__(U05DataService)
    service.raw=b'(kicad_pcb (version 20241229) (gr_circle (center 0 0) (end 1 0) (stroke (width 0) (type solid)) (fill yes) (layer "F.Cu")))'
    service.targets={'one-patch':box(3,3,4,4)}
    body=service.native_body()
    cases={'positive':body,'numeric_equivalent':body.replace(b'(version 20241229)',b'(version 20241229.0)'),
           'protected_metadata':body.replace(b'(version 20241229)',b'(version 20241230)'),
           'wrong_role':body.replace(b'(layer "F.Cu")',b'(layer "B.Cu")',1),
           'quoted_role_type':body.replace(b'(layer "F.Cu")',b'(layer F.Cu)',1),
           'missing_patch':service.raw}
    outcomes=[]
    for context in [nullcontext(),evaluation_preparation('native-controls',minimum_source_bytes=0)]:
        result={}
        with context:
            for name,value in cases.items():
                try:result[name]=service.native_check(value)
                except ValueError as error:result[name]=str(error)
        outcomes.append(result)
    assert outcomes[0]==outcomes[1]
    assert outcomes[1]['positive']['passed'] and outcomes[1]['numeric_equivalent']['passed']
    assert all(isinstance(outcomes[1][n],str) for n in ['protected_metadata','wrong_role','quoted_role_type','missing_patch'])
