import gzip,json
from pathlib import Path
import pytest
from src.gerber_u05 import durable_groups as d
from src.stage_abi.store import canonical


def fixture():
    runs=[dict(run_id=str(i),route_id=str(i),source_ids=[str(i)],start=[0.,i*.1],
               end=[2.-i,i*.1],length_mm=2.-i,angle_degrees=0.)for i in range(2)]
    return dict(runs=runs,cases={'admitted_0.05':dict(edges=[dict(a=0,b=1,alignment_angle_degrees=0.,shared_projected_length_mm=.1)])}),dict(arcs=[],cases={'admitted_0.05':dict(groups=[])})


def test_durable_reload_preserves_members_and_does_not_regroup(tmp_path,monkeypatch):
    straight,curves=fixture()
    first,binding,hit=d.prepare(tmp_path,straight,curves,dict(source='accepted'))
    assert not hit
    monkeypatch.setattr(d,'catalogue',lambda *a,**kw:pytest.fail('regrouped on cache hit'))
    second,again,hit=d.prepare(tmp_path,straight,curves,dict(source='accepted'))
    assert hit and canonical(first)==canonical(second)and binding==again
    assert first['straight_groups'][0]['members'][0]['member_domain_mm']==[0.,2.]


def test_source_and_confidence_changes_create_separate_immutable_artifacts(tmp_path):
    straight,curves=fixture()
    _,a,_=d.prepare(tmp_path,straight,curves,dict(source='first'))
    before=(Path(a['directory'])/'BINDING.json').read_bytes()
    _,b,_=d.prepare(tmp_path,straight,curves,dict(source='second'))
    _,c,_=d.prepare(tmp_path,straight,curves,dict(source='first'),noise_fraction=.02)
    assert len({v['directory']for v in(a,b,c)})==3
    assert (Path(a['directory'])/'BINDING.json').read_bytes()==before


def test_altered_and_incomplete_catalogues_cannot_silently_rebuild(tmp_path):
    straight,curves=fixture();_,binding,_=d.prepare(tmp_path,straight,curves,{})
    root=Path(binding['directory']);(root/'CATALOGUE.json.gz').write_bytes(gzip.compress(b'{}'))
    with pytest.raises(ValueError,match='BYTES_CHANGED'):d.prepare(tmp_path,straight,curves,{})
    (root/'BINDING.json').unlink()
    with pytest.raises(FileExistsError):d.prepare(tmp_path,straight,curves,{})


def test_existing_relationship_catalogue_is_imported_once_without_regrouping(tmp_path):
    from src.stage_abi.store import digest
    seed=tmp_path/'seed';seed.mkdir();straight,curves=fixture()
    files={}
    for name,value in(('GROUPS.json.gz',straight),('CURVE_GROUPS.json.gz',curves)):
        raw=gzip.compress(canonical(value),mtime=0);(seed/name).write_bytes(raw);files[name]=digest(raw)
    binding=dict(source_key={},files=files);(seed/'BINDING.json').write_bytes(canonical(binding))
    reads=[]
    def loader(store,scene,rows,admission,roles,rule):
        root=Path(rule['group_cache']);reads.append(root)
        assert root.exists(),'unexpected relationship geometry rebuild'
        b=json.loads((root/'BINDING.json').read_bytes())
        values=[json.loads(gzip.decompress((root/name).read_bytes()))for name in('GROUPS.json.gz','CURVE_GROUPS.json.gz')]
        return *values,b
    rule=dict(group_cache=str(seed),role_table_sha256='a'*64)
    a=d.source_catalogue(tmp_path/'shared',None,{},None,None,None,rule,loader)
    b=d.source_catalogue(tmp_path/'shared',None,{},None,None,None,dict(rule,group_cache=str(tmp_path/'new-job-cache')),loader)
    assert canonical(list(a[:3]))==canonical(list(b[:3]))
    assert a[3]['imported_seed']and b[3]['cache_hit']
    assert reads==[seed,Path(b[3]['directory'])]
