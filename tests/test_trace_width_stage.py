import pytest
from src.trace_width_stage import validate_width_partition, SourceWidthStage

def test_singletons_and_parallel_group_have_one_complete_partition():
    chains={'a':{'source_ids':['s1','s2']},'b':{'source_ids':['s3']},'c':{'source_ids':['s4']}}
    assignment, sources=validate_width_partition(chains,[{'group_id':'bundle','members':['a','b']},{'group_id':'single','members':['c']}])
    assert assignment=={'a':'bundle','b':'bundle','c':'single'} and len(sources)==4

@pytest.mark.parametrize('groups',[[{'group_id':'g','members':['a','a']}], [{'group_id':'g','members':['other']}], [{'group_id':'g','members':[]}], [{'group_id':'g','members':['a']},{'group_id':'g','members':['b']}]])
def test_duplicate_missing_or_empty_membership_rejects(groups):
    with pytest.raises(ValueError):validate_width_partition({'a':{'source_ids':['s1']},'b':{'source_ids':['s2']}},groups)

def test_overlap_and_fixed_contributions_cannot_be_widened_twice():
    groups=[{'group_id':'g','members':['a','b']}]
    with pytest.raises(ValueError,match='SOURCE_PARTITION'):validate_width_partition({'a':{'source_ids':['s']},'b':{'source_ids':['s']}},groups)
    with pytest.raises(ValueError,match='PROTECTED_SOURCE'):validate_width_partition({'a':{'source_ids':['s']}},[{'group_id':'g','members':['a']}],fixed_source_ids=['s'])

@pytest.mark.parametrize('value',[float('nan'),float('inf'),True,.99,1.51])
def test_invalid_factor_rejects_before_native_construction(value):
    model=SourceWidthStage(b'',{'a':{'source_ids':['s']}},[{'group_id':'g','members':['a']}],{}, {})
    with pytest.raises(ValueError,match='INVALID_COMPLETE_TRACE_SCALE'):model.build({'g':value})
