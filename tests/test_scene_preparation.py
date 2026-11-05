import copy
import pytest,sexpdata
from src.source_locators import locate
from src.u05_board.scene import bound_original_node
from src.native_document import NativeDocument,mutable_copy

RAW=b'(kicad_pcb (version 20241229) (gr_circle (center 0 0) (end 1 0) (fill yes)) (gr_poly (pts (xy 2 0) (xy 3 0) (xy 3 1)) (fill solid)))'

def bindings():
    spans=locate(RAW);top=[s for s in spans if s.parent_start==spans[0].start]
    positions={s.identity:i+1 for i,s in enumerate(top)};indexed={s.identity:s for s in top}
    return top,positions,indexed

@pytest.mark.parametrize('immutable',[False,True])
def test_whole_source_nodes_equal_every_independent_byte_span_parse(immutable):
    top,positions,indexed=bindings();tree=sexpdata.loads(RAW.decode())
    if immutable:tree=NativeDocument.from_owned_tree(tree).root
    for span in top:
        row=dict(id=span.identity,source_span=[span.start,span.end],kind=span.head)
        node=bound_original_node(tree,positions,indexed,span.identity,row)
        expected=sexpdata.loads(RAW[span.start:span.end].decode())
        assert mutable_copy(node)==expected
        assert sexpdata.dumps(mutable_copy(node))==sexpdata.dumps(expected)

@pytest.mark.parametrize('fault',['span','identity','kind','missing'])
def test_changed_source_mapping_rejects_instead_of_selecting_another_node(fault):
    top,positions,indexed=bindings();tree=sexpdata.loads(RAW.decode());span=top[1]
    row=dict(id=span.identity,source_span=[span.start,span.end],kind=span.head)
    if fault=='span':row['source_span']=[top[2].start,top[2].end]
    elif fault=='identity':row['id']=top[2].identity
    elif fault=='kind':row['kind']='gr_poly'
    else:positions.pop(span.identity)
    with pytest.raises(ValueError,match='U05_(ORIGINAL_SOURCE_.*BINDING|TOP_LEVEL_NATIVE_SOURCE_REQUIRED)'):
        bound_original_node(tree,positions,indexed,span.identity,row)

def test_bound_node_reuse_does_not_change_input_or_shared_source_ids():
    top,positions,indexed=bindings();tree=sexpdata.loads(RAW.decode());before=copy.deepcopy(tree)
    for span in top:
        bound_original_node(tree,positions,indexed,span.identity,dict(id=span.identity,source_span=[span.start,span.end],kind=span.head))
    assert tree==before and positions=={s.identity:i+1 for i,s in enumerate(top)}
