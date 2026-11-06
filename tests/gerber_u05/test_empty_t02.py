import copy
import pytest
from shapely.geometry import box
from src.gerber_u05 import pipeline as p

def scene(store,kind='fixed_source'):
 ref=p.geomref(store,box(0,0,1,1))
 row=dict(source_id='s',kind=kind,geometry_ref=ref,original_ref=ref,metadata={})
 return dict(source_sha256='a'*64,frame='native-kicad-mm',units='mm',layer='F.Cu',viewport_mm=[-2,-2,2,2],objects=[row],lineage=[],findings=[],acceptance=dict(owner='PENDING_USER'))

def test_zero_eligible_rectangles_preserves_complete_scene(tmp_path):
 store=p.Store(tmp_path/'runtime');before=scene(store);frozen=copy.deepcopy(before)
 value=p.run_t02(store,before)
 assert before==frozen and value['verification']['passed']
 assert value['verification']['status']=='NOT_APPLICABLE_EMPTY_NATIVE_RECTANGLE_INVENTORY'
 assert value['verification']['inventory']['source_objects']==1
 assert store.get_json(value['output_scene_ref'],kind='scene')==frozen
 assert value['candidate']['decisions']==value['candidate']['inclusive_candidates']==[]
 assert value['candidate']['protected_source_refs']=={'s':before['objects'][0]['geometry_ref']}
 assert value['summary']==dict(rectangles=0,grown=0,contained_keep=0,inclusive=0)

def test_empty_path_cannot_hide_an_eligible_rectangle(tmp_path):
 store=p.Store(tmp_path/'runtime')
 with pytest.raises(ValueError,match='HAS_ELIGIBLE_TARGET'):p.empty_t02(store,scene(store,'rectangle'))

def test_empty_path_still_revalidates_source_geometry(tmp_path):
 store=p.Store(tmp_path/'runtime');value=scene(store);ref=value['objects'][0]['geometry_ref']
 (store.root/'artifacts'/ref['artifact_id']).write_bytes(b'corrupt')
 with pytest.raises(ValueError):p.run_t02(store,value)
