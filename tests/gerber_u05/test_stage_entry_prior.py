from types import SimpleNamespace
import pytest
from shapely.geometry import box
from src.gerber_u05 import pipeline as p,stage_entry_prior as entry
from src import component_clearance as cc,t02_shared_gaps as gaps,pin_separation as pin


def case(tmp_path,monkeypatch):
 store=p.Store(tmp_path/'runtime');core=box(0,0,1,1);current=box(0,0,1.1,1)
 scene=dict(source_sha256='a'*64,objects=[dict(source_id='pad',geometry_ref=p.geomref(store,current))])
 ref=store.put_json('scene',scene);value=dict(output_scene_ref=ref)
 p.save(tmp_path/'t02.json',value);proof=dict(status='PASS',candidate_sha256=p.digest(p.canonical(value)))
 for mode in('construct','1','2'):p.save(tmp_path/'audits/t02'/(mode+'.json'),proof)
 ctx=SimpleNamespace(source_hash='a'*64,cores=dict(a=core),reserved=dict(a=box(-1,-1,3,3)),reservation_sha256='old',binding='source',functional=None,project=lambda material:dict(a=material['pad']),partial_pocket_failures=lambda material:[])
 monkeypatch.setattr(cc,'ACTIVE',ctx);monkeypatch.setattr(gaps,'ACTIVE',None);monkeypatch.setattr(pin,'ACTIVE',None);monkeypatch.setattr(p,'validate_scene',lambda store,ref:store.get_json(ref,kind='scene'))
 monkeypatch.setattr(p,'operands',lambda store,scene:({},dict(pad=p.geometry(store,scene['objects'][0]['geometry_ref'])),{}))
 return store,ctx,current,proof


def test_old_reference_cannot_force_growth_beyond_qualified_predecessor(tmp_path,monkeypatch):
 store,ctx,current,_=case(tmp_path,monkeypatch);proof=entry.bind(store)
 assert ctx.reserved['a'].equals(current)
 assert proof['geometry_changed']is False
 assert proof['old_reference_binding_sha256']=='old'
 assert entry.bind(store)is proof
 assert ctx.reserved['a'].bounds==(0.,0.,1.1,1.)


@pytest.mark.parametrize('change',['missing','changed','failed'])
def test_predecessor_requires_all_three_matching_native_proofs(tmp_path,monkeypatch,change):
 store,ctx,current,proof=case(tmp_path,monkeypatch)
 path=tmp_path/'audits/t02/2.json'
 if change=='missing':path.unlink()
 else:
  proof=dict(proof,**({'candidate_sha256':'bad'}if change=='changed'else{'status':'FAIL'}));path.write_bytes(p.canonical(proof))
 with pytest.raises((ValueError,FileNotFoundError)):entry.bind(store)
 assert ctx.reservation_sha256=='old'
