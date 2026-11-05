"""Snapshot namespaces must remain on the verified existing external image."""
import importlib.util,json,plistlib
from pathlib import Path
import pytest

@pytest.fixture
def storage(tmp_path,monkeypatch):
 file=Path(__file__).resolve().parents[2]/'tools/pcb_workspace.py'
 spec=importlib.util.spec_from_file_location('isolated_snapshot_storage',file)
 module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 mount=tmp_path/'mounted';root=mount/'snapshot';root.mkdir(parents=True)
 work=root/'out/lacie_work'
 monkeypatch.setattr(module,'ROOT',root);monkeypatch.setattr(module,'WORK',work)
 monkeypatch.setattr(module.os.path,'ismount',lambda p:Path(p)==mount)
 info={'images':[{'image-path':str(module.IMAGE),'system-entities':[{'mount-point':str(mount)}]}]}
 monkeypatch.setattr(module.subprocess,'check_output',lambda *a,**kw:plistlib.dumps(info))
 (mount/'STORAGE_IDENTITY.json').write_text(json.dumps({'lacie_volume_uuid':module.IDENTITY,'image':str(module.IMAGE)}))
 return module,mount,root,work,info

def test_verified_backing_admits_namespace_without_creating_it(storage):
 m,mount,root,work,info=storage
 assert m.snapshot_backing()==mount and not work.exists()

def test_wrong_image_never_admits_or_creates_namespace(storage):
 m,mount,root,work,info=storage;info['images'][0]['image-path']='/other/image'
 assert m.snapshot_backing()is None and not work.exists()

def test_bad_custody_marker_fails_closed(storage):
 m,mount,root,work,info=storage
 (mount/'STORAGE_IDENTITY.json').write_text(json.dumps({'lacie_volume_uuid':'wrong','image':str(m.IMAGE)}))
 with pytest.raises(RuntimeError,match='IDENTITY_MISMATCH'):m.snapshot_backing()
 assert not work.exists()

def test_namespace_symlink_escape_is_rejected(storage,tmp_path):
 m,mount,root,work,info=storage
 outside=tmp_path/'outside';outside.mkdir();(root/'out').mkdir();work.symlink_to(outside,target_is_directory=True)
 assert m.snapshot_backing()is None and not(outside/'tmp').exists()
