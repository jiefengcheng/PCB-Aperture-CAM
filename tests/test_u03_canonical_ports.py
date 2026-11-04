"""Port page custody is derived from full canonical source, not a view."""
import copy
import pytest
from tests.test_u02_board import native_session
from src.t01_board.source import context
from src.u02_board.ports import source_port_binding
from src.t01_canonical import full_bounds

@pytest.mark.parametrize('fault',['analysis_bounds','marker'])
def test_changed_allocation_binding_rejects_before_port_page_reuse(tmp_path,fault):
    a=native_session(tmp_path);policy=a.store.get_json(a.cap['policy_ref']);scene=a.store.get_json(a.receipt['scene_ref'])
    binding,raw,rows,shapes,sites=context(a.store,scene,policy)
    allocation=a.store.get_json(a.cap['plan_ref'])['details']['allocation']
    expected=source_port_binding(policy,raw,shapes,sites,allocation)
    assert expected['viewport_mm']==full_bounds(shapes)!=binding['viewport_mm']
    bad=copy.deepcopy(allocation)
    if fault=='analysis_bounds':bad['analysis_bounds_mm']=binding['viewport_mm']
    else:bad['canonical_t01']['contract_sha256']='0'*64
    with pytest.raises(ValueError,match='CANONICAL_PORT_BINDING_CHANGED'):source_port_binding(policy,raw,shapes,sites,bad)

def test_canonical_view_checks_all_sites_and_rejects_changed_port_artifact(tmp_path):
    from tests.test_u03_crops import verified_window
    from src.u03_board.crop_t03 import CropRetainPathsAdapter
    from src.stage_abi.store import canonical
    from src.stage_abi.contracts import StageABIError
    a=native_session(tmp_path);chosen=verified_window(tmp_path,a.scene['source_sha256'],[-1,-1,1,1]);(tmp_path/'U03_SELECTION.json').write_bytes(canonical(chosen))
    adapter=CropRetainPathsAdapter(tmp_path);records,coverage=adapter.assess()
    assert coverage['canonical_sites']==2 and coverage['source_objects']==3 and len(records)==1
    plan=a.store.get_json(a.cap['plan_ref']);ref=plan['details']['allocation']['ports']['index_ref'];index=a.store.get_json(ref)
    page=index['pages'][0]['page_ref'];(a.store.root/'artifacts'/page['artifact_id']).write_bytes(b'changed')
    with pytest.raises(StageABIError)as e:adapter.assess()
    assert e.value.code=='ARTIFACT_CORRUPTED'
