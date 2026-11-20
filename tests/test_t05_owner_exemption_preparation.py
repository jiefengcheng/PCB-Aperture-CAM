from hashlib import sha256
from types import SimpleNamespace
import pytest
from shapely.geometry import box
from shapely import to_wkb
from src.t05_owner_exemption_preparation import prepare_owner_exemptions
from src.u05_board import coverage
from src.stage_abi.store import digest

def fixture(monkeypatch):
    context=SimpleNamespace(ids={'A':['one'],'B':['two'],'C':['one']})
    monkeypatch.setattr(coverage,'integral_context',lambda:context)
    owners=[box(0,0,1,1),box(2,0,3,1)]
    adapter=SimpleNamespace(_surface_owners={digest(to_wkb(g)):o for g,o in zip(owners,['one','two'])})
    blobs={};accepted=[]
    for i,sid in enumerate(['A','B','C','unknown','owner:one']):
        raw=to_wkb(box(i,0,i+.1,.1));h=sha256(raw).hexdigest();blobs[h]=raw;accepted.append(dict(source_id=sid,patch_ref={'sha256':h}))
    calls=[]
    def policy(owner,pairs):calls.append(1);return coverage.CoverageAdapter._foreign_for(adapter,owner,pairs)
    return context,owners,accepted,lambda ref:blobs[ref['sha256']],policy,calls

def test_exact_actual_policy_matches_individual_calls_and_resolves_owner_once(monkeypatch):
    from shapely import from_wkb
    _,owners,accepted,read,policy,calls=fixture(monkeypatch)
    expected=[e['source_id']for e in accepted if not policy(owners[0],[(e['source_id'],from_wkb(read(e['patch_ref'])))])]
    calls.clear();assert prepare_owner_exemptions(accepted,owners[0],read,policy)==expected==['A','C','owner:one']
    assert len(calls)==1

def test_changed_owner_policy_and_added_prefix_are_re_evaluated(monkeypatch):
    context,owners,accepted,read,policy,calls=fixture(monkeypatch)
    assert prepare_owner_exemptions(accepted,owners[1],read,policy)==['B']
    context.ids['A']=['two']
    assert prepare_owner_exemptions(accepted,owners[1],read,policy)==['A','B']
    assert prepare_owner_exemptions(accepted[:1],owners[0],read,policy)==[]
    assert len(calls)==3

def test_empty_prefix_does_not_resolve_an_unneeded_owner():
    assert prepare_owner_exemptions([],None,lambda _:None,lambda *_:pytest.fail('called'))==[]

def test_actual_stored_patch_corruption_still_rejects(monkeypatch):
    _,owners,accepted,read,policy,calls=fixture(monkeypatch)
    with pytest.raises(ValueError,match='PATCH_CORRUPTED'):
        prepare_owner_exemptions(accepted,owners[0],lambda _:to_wkb(box(40,40,41,41)),policy)
    assert not calls

@pytest.mark.parametrize('mode',['new_id','duplicate','changed_geometry'])
def test_policy_cannot_manufacture_or_replace_prefix_material(monkeypatch,mode):
    _,owners,accepted,read,_,_=fixture(monkeypatch)
    def bad(owner,pairs):
        if mode=='new_id':return [('invented',pairs[0][1])]
        if mode=='duplicate':return [pairs[0],pairs[0]]
        return [(pairs[0][0],box(10,10,11,11))]
    with pytest.raises(ValueError,match='NOT_A_FILTER'):prepare_owner_exemptions(accepted,owners[0],read,bad)
