import hashlib
import json
import os
from pathlib import Path
import pytest
from shapely import from_wkb,to_wkb
from shapely.errors import GEOSException
from shapely.geometry import box,LineString,Polygon
from src.gerber_u05 import corner_transition as corner
from src.native_inventory import ERROR_MM


def simple():
    support=box(0,-.025,1,.025).union(box(0,-.04,.1,.04))
    return support,LineString([[0,0],[1,0]]),box(.05,-.1,.2,.1)


def test_exception_fallback_reorders_only_the_local_addition(monkeypatch):
    support,path,window=simple();before=to_wkb(support)
    expected=corner.skin_fill(support,path,window,.04)
    def fail(*a,**k):raise GEOSException('synthetic non-noded closing')
    monkeypatch.setattr(corner,'spindle_addition',fail)
    actual=corner.skin_fill(support,path,window,.04)
    assert actual.is_valid and actual.symmetric_difference(expected).area==0
    assert to_wkb(support)==before


def test_fast_path_keeps_its_exact_existing_bytes():
    support,path,window=simple()
    addition=corner.spindle_addition(support,.05,window)
    corridor=path.buffer(.04+ERROR_MM,quad_segs=128)
    expected=corner.polygonal(addition.intersection(corridor).intersection(support.buffer(.005,quad_segs=128)))
    assert to_wkb(corner.skin_fill(support,path,window,.04))==to_wkb(expected)


def test_corruption_errors_do_not_enter_geometry_fallback(monkeypatch):
    def fail(*a,**k):raise ValueError('GEOMETRY_CACHE_CORRUPTED')
    monkeypatch.setattr(corner,'spindle_addition',fail)
    with pytest.raises(ValueError,match='CACHE_CORRUPTED'):corner.skin_fill(*simple(),.04)


def test_invalid_local_closing_is_not_admitted(monkeypatch):
    def fail(*a,**k):raise GEOSException('original overlay failure')
    monkeypatch.setattr(corner,'spindle_addition',fail)
    monkeypatch.setattr(corner,'polygonal',lambda g:Polygon([(0,0),(1,1),(0,1),(1,0)]))
    with pytest.raises(GEOSException,match='original overlay failure'):corner.skin_fill(*simple(),.04)


def test_saved_valid_skin_with_invalid_off_window_closing():
    root=os.environ.get('PCB_T04_SKIN_REPRO')
    if not root:pytest.skip('saved full-board failure operand not supplied')
    root=Path(root);raw=(root/'support.wkb').read_bytes()
    assert hashlib.sha256(raw).hexdigest()=='9d93d4388a858fffb59d001c7c56a28311b393a9e4bfad3f7bb8c777ebd82d6a'
    support=from_wkb(raw);path=from_wkb((root/'path.wkb').read_bytes());window=from_wkb((root/'window.wkb').read_bytes())
    spec=json.loads((root/'CASE.json').read_bytes());closed=support.buffer(.05,quad_segs=64).buffer(-.05,quad_segs=64)
    assert support.is_valid and not closed.is_valid and closed.intersection(window).is_valid
    with pytest.raises(GEOSException):closed.difference(support).intersection(window)
    addition=corner.skin_fill(support,path,window,spec['face_radius'],**spec['parameters'])
    assert addition.is_valid and addition.area>0 and to_wkb(support)==raw
    assert window.covers(addition)
    assert support.buffer(.005,quad_segs=128).covers(addition)
    assert path.buffer(spec['face_radius']+ERROR_MM,quad_segs=128).covers(addition)
