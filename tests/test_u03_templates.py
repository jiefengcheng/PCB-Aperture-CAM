import sys,types,importlib,hashlib,copy
from pathlib import Path
import pytest
from shapely import to_wkb
from shapely.geometry import Point
from src.u03_board import templates as T
@pytest.fixture(scope='module')
def model():
 from tests.test_u03_board import source_case
 from src.trace_width_stage import SourceWidthStage
 from src.stage_abi.store import digest
 raw,rows,blobs=source_case(['(segment (start 0 0) (end 1 0) (width .1) (layer "F.Cu"))','(segment (start 1 0) (end 2 0) (width .1) (layer "F.Cu"))'])
 chain=dict(component_id='route',source_ids=[r['id'] for r in rows],source_sha256=digest(raw))
 chains={'route':chain};meta={r['id']:r for r in rows};sources={'route':raw}
 m=SourceWidthStage(raw,chains,[dict(group_id='group',members=['route'])],meta,blobs,sources=sources)
 T.install_route_templates(m,sources,meta,blobs)
 return None,None,m,None,sources,chains,meta,blobs
@pytest.mark.parametrize('kind',['source','chain','width','blob'])
def test_mutations_reject_even_on_cache_hit(model,kind):
 m=model[2];sid=min(m.chains);t=m.route_templates[sid];m.construct(sid,1.25);member=t.ids[0]
 if kind=='source':container,key,value=t.raw,sid,t.source+b' '
 elif kind=='chain':container,key,value=m.chains,sid,dict(m.chains[sid],component_id='corrupted')
 elif kind=='width':container,key,value=t.meta,member,dict(t.meta[member],trace_width_mm=999.)
 else:container,key,value=t.blobs,member,t.blobs[member]+b'bad'
 old=container[key];container[key]=value
 try:
  with pytest.raises(ValueError,match='OPERANDS_CHANGED'):m.construct(sid,1.25)
 finally:container[key]=old
@pytest.mark.parametrize('factor',[True,float('nan'),float('inf'),.999,1.500001])
def test_invalid_factor_rejected(model,factor):
 with pytest.raises(ValueError):model[2].construct(min(model[2].chains),factor)
def test_template_records_cannot_be_poisoned_by_returned_record(model):
 t=model[2].route_templates[min(model[2].chains)];a=t.build(1.2);a[0]['primitives'][0]['original_width_mm']=999
 assert t.build(1.3)[0]['primitives'][0]['original_width_mm']!=999
@pytest.mark.parametrize('budget',[0,512,4096])
def test_identity_hash_reuse_and_memory_bound(budget):
 h=T.GeometryHashes(budget)
 for i in range(50):
  g=Point(i,0).buffer(.1);expected=hashlib.sha256(to_wkb(g)).hexdigest();assert h.sha(g)==h.sha(g)==expected;assert h.weight<=budget


def test_template_matches_original_constructor_records_and_all_geometry(model):
 from src.source_offset_width import construct_source_offset_width
 m=model[2];raw,chains,meta,blobs=model[4:];sid=min(chains)
 for f in (1.,1.000001,1.125,1.5):
  a=m.construct(sid,f);b=construct_source_offset_width(raw[sid],chains[sid],meta,blobs,f)
  assert a[0]==b[0]
  assert all(to_wkb(a[k])==to_wkb(b[k]) for k in (3,4,5))
  for k in (1,2):assert all(to_wkb(a[k][s])==to_wkb(b[k][s]) for s in a[k])
