"""Owned restoration copies under active immutable native preparation."""
from pathlib import Path
import pytest,sexpdata
from shapely.geometry import box
from src.stage_abi.preparation import worker_resources
from src.native_preparation import native_view
from src.native_document import NativeNode
from src.pcb_data_abi import board_native as native
from src.pcb_data_abi.crop import TEMPLATE

@pytest.mark.parametrize('stage',['u03','u04'])
def test_restoration_is_owned_and_protected_nodes_still_reject(stage):
    from src.u03_board.export import U03DataService
    from src.u04_board.export import U04DataService
    cls=U03DataService if stage=='u03'else U04DataService
    raw=('(kicad_pcb (general (padding "'+('x'*5000)+'")) (segment (start 0 0) (end 1 0) (width .1) (layer "F.Cu")))').encode()
    tree=sexpdata.loads(raw.decode());g=box(0,-.075,1,.075)
    tree[2]=native.polygon_node(g,native.edit_template(TEMPLATE),'trace','a'*64)[0];body=native.board_bytes(tree)
    service=cls.__new__(cls);service.raw=raw;service.width_targets={'trace':g};service.decisions=[];service.targets={}
    service.rectangle_targets={};service.inclusive_targets={};rows=[];width=[dict(source_id='trace',index=2)]
    service.native_body=lambda:(body,rows,width)
    with worker_resources('writer-ownership:'+stage):
        before=native_view(raw.decode());assert isinstance(before,NativeNode)
        result=service.native_check(body,rows,width)
        assert result['changed_native_trace_parts']==1 and result['source_paths_unchanged']
        assert native_view(raw.decode())==before
        corrupted=sexpdata.loads(body.decode());corrupted[1].append([sexpdata.Symbol('changed'),1])
        with pytest.raises(ValueError,match='PROTECTED_NATIVE_OBJECT_CHANGED'):service.native_check(native.board_bytes(corrupted),rows,width)
