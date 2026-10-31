import pytest
from src.stage_abi.store import ArtifactStore
from src.stage_abi.native_import import import_width_scene
from src.stage_abi.contracts import StageABIError
from tests.test_uniform_trace_width import fixture


def test_native_import_binds_all_cache_and_preserves_original_member_ids(tmp_path):
 raw,chain,meta,blobs=fixture(['(segment (start 0 0) (end 1 0) (width 0.1) (layer F.Cu) (net 0))']);s=ArtifactStore(tmp_path/'runtime');manifest=dict(source_sha256=chain['source_sha256'],objects=[dict(r,kind='segment') for r in meta.values()]);imported=import_width_scene(s,source=raw,manifest=manifest,original_blobs=blobs,current_blobs={},chains=[chain],viewport_mm=[-1,-1,2,2],qualification={'scope':'Synthetic parsed-native source chain'});scene=s.get_json(imported['scene_ref']);assert imported['selected_native_members']==1 and scene['objects'][0]['metadata']['native_source_ids']==chain['source_ids']
 with pytest.raises(StageABIError):import_width_scene(s,source=raw,manifest=manifest,original_blobs={},current_blobs={},chains=[chain],viewport_mm=[-1,-1,2,2],qualification={})

def test_native_import_rejects_source_drift_and_changed_selected_strokes(tmp_path):
 raw,chain,meta,blobs=fixture(['(segment (start 0 0) (end 1 0) (width 0.1) (layer F.Cu) (net 0))']);s=ArtifactStore(tmp_path/'runtime');manifest=dict(source_sha256=chain['source_sha256'],objects=[dict(r,kind='segment') for r in meta.values()]);args=dict(manifest=manifest,original_blobs=blobs,chains=[chain],viewport_mm=[-1,-1,2,2],qualification={})
 with pytest.raises(StageABIError):import_width_scene(s,source=raw+b'changed',current_blobs={},**args)
 with pytest.raises(StageABIError):import_width_scene(s,source=raw,current_blobs={chain['source_ids'][0]:b'changed'},**args)
