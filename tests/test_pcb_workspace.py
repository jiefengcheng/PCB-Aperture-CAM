import os,json,tempfile,fcntl
from pathlib import Path
import pytest
from tools import pcb_workspace as storage


def test_missing_external_mount_never_creates_fallback(tmp_path,monkeypatch):
    missing=tmp_path/'absent';monkeypatch.setattr(storage,'WORK',missing)
    with pytest.raises(RuntimeError,match='UNAVAILABLE'):storage.configure()
    assert not missing.exists()


def test_internal_directory_cannot_impersonate_workspace(tmp_path,monkeypatch):
    monkeypatch.setattr(storage,'WORK',tmp_path)
    monkeypatch.setattr(storage,'ROOT',tmp_path)
    monkeypatch.setattr(storage.os.path,'ismount',lambda p:True)
    (tmp_path/'STORAGE_IDENTITY.json').write_text(json.dumps(dict(lacie_volume_uuid=storage.IDENTITY)))
    with pytest.raises(RuntimeError,match='IS_INTERNAL'):storage.require_storage()


def test_real_external_workspace_supports_evidence_protocol(tmp_path):
    work=storage.configure()
    assert tmp_path.is_relative_to(work)
    assert Path(tempfile.gettempdir()).is_relative_to(work)
    assert work.stat().st_dev!=storage.ROOT.stat().st_dev
    a=tmp_path/'evidence';a.write_bytes(b'evidence');b=tmp_path/'published';os.link(a,b)
    assert a.stat().st_ino==b.stat().st_ino
    with a.open('rb') as f:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
    assert os.environ['TMPDIR']==str(work/'tmp')


def test_low_external_space_halts_before_run(monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setattr(storage.shutil,'disk_usage',lambda p:SimpleNamespace(free=1024))
    with pytest.raises(RuntimeError,match='LOW_SPACE'):storage.require_storage()


def test_pytest_cache_is_external(request):
    assert request.config.cache._cachedir.is_relative_to(storage.WORK)


def test_unmounted_cache_path_cannot_create_internal_fallback(tmp_path,monkeypatch):
    mountpoint=tmp_path/'guarded';monkeypatch.setattr(storage,'WORK',mountpoint)
    storage.guard_mountpoint()
    try:
        assert mountpoint.stat().st_mode&0o777==0
        with pytest.raises(PermissionError):(mountpoint/'local_code').mkdir()
    finally:mountpoint.chmod(0o700)


def test_guard_preserves_nonempty_unmounted_directory(tmp_path,monkeypatch):
    mountpoint=tmp_path/'existing';mountpoint.mkdir();(mountpoint/'keep').write_text('preserved')
    monkeypatch.setattr(storage,'WORK',mountpoint)
    with pytest.raises(RuntimeError,match='NOT_EMPTY'):storage.guard_mountpoint()
    assert (mountpoint/'keep').read_text()=='preserved'
