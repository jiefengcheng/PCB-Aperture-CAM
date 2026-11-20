"""Spatial preparation retains exact original positive-area contact witnesses."""
import copy
import pytest
from shapely import to_wkb,set_precision
from shapely.geometry import box,Polygon
from src.gerber_u05 import pipeline as p
from src.gerber_u05.pin_policy import SourceContacts


def fixture(tmp_path):
 store=p.Store(tmp_path/'runtime')
 shapes=[box(3,3,4,4),box(0,0,1,1),box(0,0,1,1),box(1,0,2,1),
         Polygon([(0,0),(.000001,0),(0,.000001)])]
 rows=[dict(source_id=str(i),original_ref=p.geomref(store,g))for i,g in enumerate(shapes)]
 return store,rows,shapes


def test_indexed_contacts_match_full_scan_order_aliases_and_tiny_contacts(tmp_path,monkeypatch):
 store,rows,shapes=fixture(tmp_path);index=SourceContacts(store,rows)
 def reread(*args,**kwargs):raise AssertionError('contact query should use the verified snapshot')
 monkeypatch.setattr(store,'get',reread)
 for piece in [box(0,0,.1,.1),box(1,0,1.1,.1),box(5,5,6,6),set_precision(box(.1,.1,.9,.9),.01)]:
  expected=[dict(source_id=r['source_id'],original_geometry_sha256=r['original_ref']['sha256'])for r,g in zip(rows,shapes)if g.intersection(piece).area>0]
  assert index.contacts(piece)==expected
 assert [r['source_id']for r in index.contacts(box(0,0,.1,.1))]==['1','2','4']


def test_changed_occurrence_binding_rejects_and_new_initialization_rebuilds(tmp_path):
 store,rows,_=fixture(tmp_path);index=SourceContacts(store,rows);changed=copy.deepcopy(rows)
 changed[0]['original_ref']=p.geomref(store,box(0,0,.05,.05))
 with pytest.raises(ValueError,match='PIN_CONTACT_SNAPSHOT_CHANGED'):index.validate(store,changed)
 rebuilt=SourceContacts(store,changed)
 assert rebuilt.contacts(box(0,0,.1,.1))[0]['source_id']=='0'
 with pytest.raises(ValueError,match='PIN_CONTACT_SNAPSHOT_CHANGED'):index.validate(store,list(reversed(rows)))


def test_distant_corrupt_source_rejects_during_preparation_and_final_read_check(tmp_path):
 store,rows,_=fixture(tmp_path);index=SourceContacts(store,rows)
 path=store.root/'artifacts'/rows[0]['original_ref']['artifact_id'];path.write_bytes(b'corrupt')
 with pytest.raises(ValueError):SourceContacts(store,rows)
 with pytest.raises(ValueError):store.verify_reads()
