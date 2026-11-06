import pytest
from src.gerber_u05 import pipeline as p
from src.gerber_u05.legacy_prefix import prove_no_retained_partials,partial_reload_delta_only

def retained(tmp_path,metadata):
 store=p.Store(tmp_path/'runtime');ref=store.put_json('scene',dict(objects=[dict(metadata=metadata)]));p.save(tmp_path/'t04.json',dict(output_scene_ref=ref));return ref

def test_unreached_partial_fix_requires_complete_retained_scene_inventory(tmp_path):
 retained(tmp_path,{});assert prove_no_retained_partials(tmp_path,['t04'])['scene_refs_checked']==1

def test_an_actual_retained_partial_forbids_dormant_branch_reuse(tmp_path):
 retained(tmp_path,dict(approved_partial_pockets=[dict(pocket_id='has-a-rim')]))
 with pytest.raises(ValueError,match='REQUIRES_FRESH_STAGE'):prove_no_retained_partials(tmp_path,['t04'])

def test_altered_retained_scene_cannot_hide_a_partial(tmp_path):
 ref=retained(tmp_path,dict(approved_partial_pockets=[dict(pocket_id='has-a-rim')]));(tmp_path/'runtime/artifacts'/ref['artifact_id']).write_bytes(p.canonical(dict(objects=[dict(metadata={})])))
 with pytest.raises(ValueError,match='SCENE_BINDING_CHANGED'):prove_no_retained_partials(tmp_path,['t04'])

def test_unrelated_policy_change_cannot_share_the_reload_fix_authority():
 before="def register(scope,channel,sid,md):\n if channel not in scope.cores or scope.owner(sid)!=channel:raise ValueError('PARTIAL_POCKET_FUNCTIONAL_OWNER_BINDING_CHANGED')\n return 0.040\n"
 after=before.replace("scope.owner(sid)!=channel", "md.get('original_channel_id')!=channel or scope.ids.get(sid,(channel,))!=(channel,) or md.get('original_channel_witness_sha256')!=digest(to_wkb(scope.cores[channel]))")
 partial_reload_delta_only(before,after)
 with pytest.raises(ValueError,match='DELTA_NOT_ISOLATED'):partial_reload_delta_only(before,after.replace('return 0.040','return 0.020'))
