import hashlib
import json
import os
from pathlib import Path
import pytest
from shapely import from_wkb,to_wkb
from shapely.geometry import box,Polygon
from shapely.geometry.base import BaseGeometry
from shapely.errors import GEOSException
from src.gerber_u05 import finite_profile_union as overlay
from src.gerber_u05.tangent_finish import face_cut


def test_scoped_difference_keeps_exact_fast_path_bytes():
    a=box(0,0,3,3);b=box(1,1,4,4);window=box(.5,.5,2,2)
    assert to_wkb(overlay.difference_for_window(a,b,window))==to_wkb(a.difference(b))


def test_exception_fallback_retains_every_finite_face_in_the_window(monkeypatch):
    a=box(0,0,3,3);b=box(1,1,4,4);window=box(.5,.5,2,2)
    expected=a.difference(b).intersection(window);before=[to_wkb(g)for g in(a,b)]
    original=BaseGeometry.difference
    def fail_first(self,other,*args,**kwargs):
        if self is a and other is b:raise GEOSException('global non-noded intersection')
        return original(self,other,*args,**kwargs)
    monkeypatch.setattr(BaseGeometry,'difference',fail_first)
    result=overlay.difference_for_window(a,b,window)
    assert result.is_valid and result.equals(expected)
    assert [to_wkb(g)for g in(a,b)]==before


def test_invalid_restricted_operands_cannot_turn_into_a_pass(monkeypatch):
    a=box(0,0,3,3);b=box(1,1,4,4)
    def fail(*args,**kwargs):raise GEOSException('original failure')
    monkeypatch.setattr(BaseGeometry,'difference',fail)
    monkeypatch.setattr(overlay,'polygonal',lambda g:Polygon([(0,0),(1,1),(0,1),(1,0)]))
    with pytest.raises(GEOSException,match='original failure'):overlay.difference_for_window(a,b,box(0,0,2,2))


def test_saved_tangent_opening_failure_preserves_protected_copper_and_depth():
    root=os.environ.get('PCB_T04_TANGENT_REPRO')
    if not root:pytest.skip('saved full-board tangent failure operand not supplied')
    root=Path(root);raw=(root/'support.wkb').read_bytes();opened_raw=(root/'opened.wkb').read_bytes()
    assert hashlib.sha256(raw).hexdigest()=='17b52c132dc708531c7c15a5bcca48c62a5a9f6236eab60eb6814566d6ccb870'
    assert hashlib.sha256(opened_raw).hexdigest()=='5118ec311909e9822809147d3d6e604eeae3992d6ae0f69f63c22ec5d7536912'
    support=from_wkb(raw);opened=from_wkb(opened_raw);window=from_wkb((root/'window.wkb').read_bytes());protected=from_wkb((root/'protected.wkb').read_bytes())
    spec=json.loads((root/'CASE.json').read_bytes())
    assert support.is_valid and not opened.is_valid and opened.intersection(window).is_valid
    with pytest.raises(GEOSException):support.difference(opened).intersection(window).difference(protected)
    cut=face_cut(support,spec['center'],spec['axis'],window,protected)
    assert cut.is_valid and cut.area>0 and to_wkb(support)==raw
    assert window.covers(cut)and cut.intersection(protected).area==0
    assert cut.intersection(support.buffer(-.005,quad_segs=64)).area==0
    assert support.difference(cut).is_valid
