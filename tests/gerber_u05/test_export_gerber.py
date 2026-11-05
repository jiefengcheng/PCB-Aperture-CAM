import pytest
import copy,re
from shapely.geometry import box
from test_gerber_source import fixture,source_circle
from src.gerber_u05 import legacy_export as e
from src.gerber_u05 import pipeline as p

def test_integer_canonicalization_reparses_exact_atoms_and_polarity():
    raw=fixture('D10*\nXY-D03*\nD12*\nX00000000Y00000000D02*\nX-00050000Y00000000D01*\n%LPC*%\nD10*\nX00500000Y00000000D03*\n')
    base,proof=e.canonical_base(raw);after=e.parse((base+'M02*\n').encode());before,_,_=p.source_profile.parse_source(raw)
    assert proof['exact_integer_conversion']and len(before.objects)==len(after.objects)
    for a,b in zip(before.objects,after.objects):
        assert type(a)==type(b)and a.polarity_dark==b.polarity_dark
        ga,_=p.source_profile.object_geometry(a);gb,_=p.source_profile.object_geometry(b);assert ga.equals(gb)

@pytest.mark.parametrize('hole',[False,True])
def test_positive_export_regions_roundtrip_preserves_resolvable_hole(tmp_path,hole):
    shape=box(-.3,-.3,.3,.3)
    if hole:shape=shape.difference(box(-.1,-.1,.1,.1))
    records=[];blocks=[];store=p.Store(tmp_path/'store');e.append_regions(shape,'t05','owner',records,blocks,store)
    base,_=e.canonical_base(source_circle());parsed=e.parse((base+''.join(blocks)+'M02*\n').encode());obj=parsed.objects[-1]
    assert obj.polarity_dark
    observed,_=p.source_profile.object_geometry(obj);observed=p.affine_scale(observed,1,-1,origin=(0,0))
    assert e.fidelity(shape,observed)['passed']and len(observed.interiors)==int(hole)

@pytest.mark.parametrize('mutation,reason',[(lambda x:x.replace(b'M02*',b''),'mandatory M02 EOF'),(lambda x:x.replace(b'%MOMM*%',b'%MOIN*%'),'FORMAT_OR_COMPLETENESS'),(lambda x:x.replace(b'%MOMM*%',b'%MOMM*%%MOMM*%'),'Re-definition of file units'),(lambda x:x.replace(b'X0000000000',b'XNaN'),'Unknown')])
def test_corrupt_serialized_gerber_fails_for_reason(mutation,reason):
    base,_=e.canonical_base(source_circle());raw=(base+'M02*\n').encode()
    with pytest.raises(Exception)as error:e.parse(mutation(raw))
    assert reason.lower()in str(error.value).lower()

def test_full_source_chain_exports_and_checks_actual_copper(tmp_path,monkeypatch):
    monkeypatch.setattr(e,'verify_sources',lambda _:None)
    run=tmp_path/'run';run.mkdir();store=p.Store(run/'runtime')
    raw=fixture('D11*\nX00000000Y00000000D03*\nD10*\nX00200000Y00000000D03*\nD12*\nX00200000Y00000000D02*\nX00150000Y00000000D01*\n')
    binding=p.build_source(store,raw);p.save(run/'source.json',binding);scene=store.get_json(binding['scene_ref'],kind='scene');results={}
    for stage in e.ORDER:
        if stage=='t01':result=p.run_t01(store,scene,binding)
        elif stage=='t03':result=p.run_t03(store,scene,binding,results['t01'])
        elif stage=='t04':result=p.run_t04(store,scene)
        elif stage=='t02':result=p.run_t02(store,scene)
        else:result=p.run_t05(store,scene,results['t04'])
        results[stage]=result;p.save(run/(stage+'.json'),result);p.save(run/'audits'/stage/'proof.json',dict(status='PASS'));scene=store.get_json(result['output_scene_ref'],kind='scene')
    for i in(1,2):p.save(run/'audits/t01'/f'supplement_{i}.json',dict(test='Unit fixture supplements tested separately'))
    body,ledger=e.construct(run);proof=e.check(run,body,ledger)
    assert proof['status']=='PASS'and proof['final_copper']['added_area_mm2']>0
    assert proof['actual_hard_gap_mm']==.040
    # Mutated ledger hash prevents a generic hash mismatch from hiding the
    # intended semantic reason. None of these mutants are accepted candidates.
    prefix=body.index(b'G04 qualified ')
    mutations=[('ORIGINAL_CANONICAL_COMMAND_PREFIX_CHANGED',body[:prefix].replace(b'X0000000000',b'X0000100000',1)+body[prefix:]),('APPENDED_REGION_ROLE_OR_POLARITY_CHANGED',body[:prefix]+body[prefix:].replace(b'%LPD*%',b'%LPC*%',1)),('GENERATED_GERBER_COUNT_OR_HASH_CHANGED',body[:prefix]+re.sub(rb'G36\*.*?G37\*',b'',body[prefix:],count=1,flags=re.S))]
    for reason,mutant in mutations:
        mutant_ledger=copy.deepcopy(ledger);mutant_ledger['generated_sha256']=p.digest(mutant)
        with pytest.raises(ValueError,match=reason):e.check(run,mutant,mutant_ledger)
