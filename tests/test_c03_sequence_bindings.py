"""Fail-closed admission controls for the new C03 sequence adapter."""
from pathlib import Path
import json,hashlib,tempfile
import pytest
import tools.c03_sequence_scene as scene
ROOT=Path(__file__).resolve().parents[1]


def test_unknown_stage_rejects_before_any_file_read():
 with pytest.raises(ValueError,match='SUPPORTED_C03_STAGE_REQUIRED'):
  scene.load_scene(ROOT/'out/nonexistent_C03_case',through='T99')


def test_changed_saved_T01_scene_stops_before_geometry_loading():
 with tempfile.TemporaryDirectory(dir=ROOT/'out',prefix='c03_negative_') as name:
  p=Path(name);(p/'T01').mkdir();(p/'T01/SUPPORTED_TARGETS.json').write_text('{}')
  (p/'T01/RESULT.json').write_text(json.dumps(dict(after_sha256='0'*64)))
  (p/'T01/after.wkb').write_bytes(b'not the bound accepted T01 geometry')
  with pytest.raises(AssertionError):scene.load_scene(p,'T01')
  assert not (p/'T04').exists()


def test_wrong_original_source_hash_stops_before_inventory_read(monkeypatch):
 with tempfile.TemporaryDirectory(dir=ROOT/'out',prefix='c03_source_negative_') as name:
  p=Path(name);(p/'T01').mkdir();cache=p/'inputs';cache.mkdir();(cache/'ORG_source.kicad_pcb').write_bytes(b'controlled wrong source')
  scope=json.dumps(dict(source_sha256='f'*64)).encode();geometry=b'controlled bound bytes'
  (p/'T01/SUPPORTED_TARGETS.json').write_bytes(scope);(p/'T01/after.wkb').write_bytes(geometry)
  (p/'T01/RESULT.json').write_text(json.dumps(dict(after_sha256=hashlib.sha256(geometry).hexdigest(),scope_sha256=hashlib.sha256(scope).hexdigest(),source_sha256='f'*64)))
  monkeypatch.setattr(scene,'CACHE',cache)
  with pytest.raises(AssertionError):scene.load_scene(p,'T01')
  assert not (cache/'source_manifest.json').exists()
