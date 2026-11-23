import json
from pathlib import Path

import pytest

from src import cleanup_runtime as runtime


def portable(tmp_path,monkeypatch):
    payload=tmp_path/'Portable.app/Contents/Resources/payload';payload.mkdir(parents=True)
    (payload/'PORTABLE_PACKAGE.json').write_text(json.dumps(runtime.PROFILE))
    monkeypatch.setattr(runtime,'ROOT',payload);monkeypatch.setattr(runtime,'_binding',None)
    root=tmp_path/'work';root.mkdir()
    monkeypatch.setenv('PCB_CLEANUP_WORKSPACE',str(root))
    return root


def test_environment_alone_cannot_enable_portable_storage(tmp_path,monkeypatch):
    monkeypatch.setattr(runtime,'ROOT',tmp_path)
    monkeypatch.setenv('PCB_CLEANUP_WORKSPACE',str(tmp_path))
    with pytest.raises(ValueError,match='PACKAGE_PROFILE_REQUIRED'):runtime.workspace_root()


def test_explicit_folder_initialization_and_volume_binding(tmp_path,monkeypatch):
    root=portable(tmp_path,monkeypatch)
    receipt=runtime.initialize(root)
    assert receipt['workspace']==str(root) and receipt['volume_uuid']
    assert runtime.workspace_root()==root
    marker=(root/runtime.MARKER).read_bytes()
    assert runtime.initialize(root)['workspace_id']==receipt['workspace_id']
    assert (root/runtime.MARKER).read_bytes()==marker
    assert runtime.configure_portable()==root


def test_corrupt_marker_never_reinitializes_or_uses_fallback(tmp_path,monkeypatch):
    root=portable(tmp_path,monkeypatch);runtime.initialize(root);runtime.workspace_root()
    marker=root/runtime.MARKER;marker.write_text('{"schema":"corrupted"}')
    with pytest.raises(ValueError,match='UNAVAILABLE_NO_FALLBACK'):runtime.workspace_root()
    with pytest.raises(ValueError,match='IDENTITY_CHANGED'):runtime.initialize(root)
    assert marker.read_text()=='{"schema":"corrupted"}'


def test_missing_work_folder_is_not_created_implicitly(tmp_path,monkeypatch):
    root=portable(tmp_path,monkeypatch)
    monkeypatch.setenv('PCB_CLEANUP_WORKSPACE',str(root/'missing'))
    with pytest.raises(FileNotFoundError):runtime.workspace_root()
    assert not (root/'missing').exists()


def test_payload_cannot_be_selected_as_workspace(tmp_path,monkeypatch):
    portable(tmp_path,monkeypatch)
    with pytest.raises(ValueError,match='SEPARATE_WORKSPACE'):runtime.initialize(runtime.ROOT)


def test_profile_corruption_does_not_activate_workspace(tmp_path,monkeypatch):
    portable(tmp_path,monkeypatch)
    (runtime.ROOT/'PORTABLE_PACKAGE.json').write_text('{}')
    with pytest.raises(ValueError,match='PROFILE_CHANGED'):runtime.workspace_root()


def test_changed_device_is_not_an_internal_fallback(tmp_path,monkeypatch):
    root=portable(tmp_path,monkeypatch);runtime.initialize(root);runtime.workspace_root()
    runtime._binding['device']=-1
    with pytest.raises(ValueError,match='UNAVAILABLE_NO_FALLBACK'):runtime.workspace_root()
