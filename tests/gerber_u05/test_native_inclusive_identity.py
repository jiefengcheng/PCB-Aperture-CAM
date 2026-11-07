"""Approved inclusive fills retain their source-member native check identity."""
import copy
import pytest
from shapely.geometry import box
from shapely.ops import unary_union
from src import component_clearance as cc
from src.gerber_u05 import pipeline as p
from src.gerber_u05.native_inclusive_identity import bind


def case():
    original = dict(a=box(0, 0, 1, 1), b=box(0, 1.3, 1, 2.3),
                    joint=box(.45, .9, .55, 1.4), foreign=box(3, 0, 4, 3))
    context = cc.Context(unary_union(list(original.values())), 'a' * 64, original)
    logical = box(0, 0, 1, 2.3)
    ref = dict(artifact_id='geometry:' + p.digest(p.to_wkb(logical)), sha256=p.digest(p.to_wkb(logical)))
    sid = 't02-inclusive:' + ref['sha256']
    owner = context.owner('a');assert context.owner('b') == owner
    context.assign(sid, logical, [owner])
    row = dict(source_id=sid, kind='inclusive_rectangle', original_ref=ref, geometry_ref=ref,
               metadata=dict(origin='t02-inclusive-fill', members=['a', 'b'],
                   original_component_owner_id=owner, original_source_sha256=context.source_hash,
                   original_member_wkb_sha256={m: p.digest(p.to_wkb(original[m])) for m in ['a', 'b']}))
    decision = dict(status='MERGED', reasons=[], shortage=.1, check=dict(passed=True),
                    candidate_ref=ref, members=['a', 'b'], original_component_owners=[owner])
    value = dict(candidate=dict(inclusive_candidates=[decision], decisions=[dict(source_id=m) for m in ['a', 'b']]))
    return sid, row, value, original, dict(original), dict(original, **{sid: logical}), context


def test_inclusive_predecessor_uses_members_not_the_fill_and_mutates_no_inputs():
    sid, row, value, previous, original, wanted, context = case()
    before = {s: p.to_wkb(g) for s, g in previous.items()}
    core, source, proof = bind('t02', sid, row, value, previous, original, wanted, context)
    assert core.equals(unary_union([previous['a'], previous['b']]))
    assert source.equals(core) and not core.equals(wanted[sid])
    assert proof['members'] == ['a', 'b'] and proof['qualified_rectangle_sha256'] == row['geometry_ref']['sha256']
    assert before == {s: p.to_wkb(g) for s, g in previous.items()}
    assert sid not in previous and sid not in original


@pytest.mark.parametrize('change', ['stage', 'kind', 'origin', 'duplicate_member', 'missing_member',
    'rejected', 'duplicate_decision', 'reasons', 'failed_check', 'budget', 'changed_reference',
    'changed_members', 'missing_ordinary_decision', 'changed_logical_rectangle',
    'owner', 'source_hash', 'source_member_hash', 'no_context'])
def test_unbound_or_changed_fill_cannot_acquire_a_native_source_core(change):
    sid, row, value, previous, original, wanted, context = case()
    stage = 't02';decision = value['candidate']['inclusive_candidates'][0]
    if change == 'stage':stage = 't01'
    elif change == 'kind':row['kind'] = 'rectangle'
    elif change == 'origin':row['metadata']['origin'] = 'unbound'
    elif change == 'duplicate_member':row['metadata']['members'] = ['a', 'a']
    elif change == 'missing_member':previous.pop('b')
    elif change == 'rejected':decision['status'] = 'REJECTED'
    elif change == 'duplicate_decision':value['candidate']['inclusive_candidates'].append(copy.deepcopy(decision))
    elif change == 'reasons':decision['reasons'] = ['PROTECTED_PIN_SEPARATION_ENTIRE_FILL']
    elif change == 'failed_check':decision['check']['passed'] = False
    elif change == 'budget':decision['shortage'] = .20001
    elif change == 'changed_reference':row['geometry_ref'] = dict(sha256='0' * 64)
    elif change == 'changed_members':decision['members'] = ['b', 'a']
    elif change == 'missing_ordinary_decision':value['candidate']['decisions'].pop()
    elif change == 'changed_logical_rectangle':wanted['b'] = box(0, 1.3, 1.01, 2.3)
    elif change == 'owner':row['metadata']['original_component_owner_id'] = context.owner('foreign')
    elif change == 'source_hash':row['metadata']['original_source_sha256'] = 'b' * 64
    elif change == 'source_member_hash':row['metadata']['original_member_wkb_sha256']['a'] = '0' * 64
    elif change == 'no_context':context = None
    with pytest.raises(ValueError, match='NATIVE_T02_INCLUSIVE_PREDECESSOR_UNBOUND'):
        bind(stage, sid, row, value, previous, original, wanted, context)


def test_connected_only_through_remote_bar_does_not_bind_different_channels():
    sid, row, value, previous, original, wanted, context = case()
    class Channels:
        def owner(self, name):return {'a': 'left', 'b': 'right', sid: 'left'}[name]
    context.functional = Channels()
    row['metadata']['original_channel_id'] = 'left'
    value['candidate']['inclusive_candidates'][0]['functional_source_channel_ids'] = ['left']
    with pytest.raises(ValueError, match='NATIVE_T02_INCLUSIVE_PREDECESSOR_UNBOUND'):
        bind('t02', sid, row, value, previous, original, wanted, context)
