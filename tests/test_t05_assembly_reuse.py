"""Exact assembly reuse must still reread artifacts and reject added copper."""
import copy
import pytest
from shapely import to_wkb
from shapely.geometry import box
from src.stage_abi.loaded_geometry import GeometrySnapshot
from src.stage_abi.store import ArtifactStore
from src.u05_board.coverage import verify_assembled_output

class CountingSnapshot(GeometrySnapshot):
    def __init__(self,*args,**kwargs):
        self.compositions=0
        super().__init__(*args,**kwargs)
    def composed(self,*args):
        self.compositions+=1
        return super().composed(*args)

def fixture(tmp_path):
    store=ArtifactStore(tmp_path/'runtime')
    refs=[store.put('geometry',to_wkb(g))for g in (box(0,0,1,1),box(.9,.2,1.2,.8))]
    rows=[dict(source_id=s,kind=k,geometry_ref=r,original_ref=r)for s,k,r in zip(('source','accepted-fill'),('rectangle','junction_addition'),refs)]
    scene=dict(objects=rows,viewport_mm=[-1,-1,3,3]);snapshot=CountingSnapshot(store,scene)
    expected=snapshot.composed(store,scene);after=store.put('geometry',to_wkb(expected));snapshot.compositions=0
    return store,snapshot,scene,after,expected

def test_exact_rows_reuse_union_but_reread_every_geometry(tmp_path):
    store,snapshot,scene,after,expected=fixture(tmp_path);accesses=snapshot.stats['artifact_accesses']
    actual=verify_assembled_output(snapshot,store,scene,scene['objects'],copy.deepcopy(scene),after)
    assert to_wkb(actual)==to_wkb(expected) and snapshot.compositions==1
    assert snapshot.stats['artifact_accesses']-accesses==2*len(scene['objects'])

@pytest.mark.parametrize('mutation',['extra','removed','viewport','after'])
def test_accepted_fill_does_not_allow_changed_assembly(tmp_path,mutation):
    store,snapshot,scene,after,_=fixture(tmp_path);output=copy.deepcopy(scene)
    if mutation=='extra':
        ref=store.put('geometry',to_wkb(box(1.5,1.5,2,2)))
        output['objects'].append(dict(source_id='forged',geometry_ref=ref,original_ref=ref))
    elif mutation=='removed':output['objects'].pop()
    elif mutation=='viewport':output['viewport_mm']=[0,0,.5,.5]
    else:after=store.put('geometry',to_wkb(box(0,0,1,1)))
    with pytest.raises(ValueError,match='ASSEMBLY_CHANGED|AFTER_CHANGED'):
        verify_assembled_output(snapshot,store,scene,scene['objects'],output,after)


def test_changed_order_keeps_original_fallback(tmp_path):
    store,snapshot,scene,after,expected=fixture(tmp_path);output=copy.deepcopy(scene);output['objects'].reverse()
    actual=verify_assembled_output(snapshot,store,scene,scene['objects'],output,after)
    assert to_wkb(actual)==to_wkb(expected) and snapshot.compositions==2

@pytest.mark.parametrize('mutation',['artifact','decoded_shape'])
def test_corruption_between_composition_and_second_reads_is_rejected(tmp_path,monkeypatch,mutation):
    store,snapshot,scene,after,_=fixture(tmp_path);original=store.get;ref=scene['objects'][0]['geometry_ref']
    def tamper(reference,*,kind=None):
        body=original(reference,kind=kind)
        if reference==after:
            if mutation=='artifact':(store.root/'artifacts'/ref['artifact_id']).write_bytes(b'corrupt')
            else:
                _,checksum=snapshot.shapes[ref['sha256']]
                snapshot.shapes[ref['sha256']]=(box(0,0,2,2),checksum)
        return body
    monkeypatch.setattr(store,'get',tamper)
    with pytest.raises(ValueError):verify_assembled_output(snapshot,store,scene,scene['objects'],scene,after)
