"""Synthetic helper inputs, actual Gerber parse, and source-ID corruptions.

These are unit controls, not fabricated managed-route qualification receipts.
"""
import copy
import pytest
from shapely import from_wkb
from src.gerber_u05 import pipeline as p,legacy_export as legacy
from src.gerber_u05.channel_material import check_owned,legacy_channels
from src import source_channel_scope as functional
from tests.gerber_u05.test_channel_construction import fixture

def test_owned_native_pad_growth_remains_integral_across_the_preserved_bar(tmp_path,monkeypatch):
 store,scene,source,scope,originals=fixture(tmp_path,monkeypatch);own=scope.owner('trace:0');owned=dict(scope.cores);grown=originals['trace:0'].buffer(.03,quad_segs=64);owned[own]=owned[own].union(grown)
 assert check_owned(scope,owned)['passed']
 # Whole-image subtraction alone loses the pad's original source identity.
 image_only=scope.channels.check(source.union(grown))
 assert any(r['reason']=='NEW_UNBOUND_COPPER_OUTSIDE_TEMPORARY_FRAME'for r in image_only['failures'])

def test_a_native_contour_cannot_be_assigned_to_a_different_source_channel(tmp_path,monkeypatch):
 store,scene,source,scope,originals=fixture(tmp_path,monkeypatch);wrong=scope.owner('trace:1');owned=dict(scope.cores);owned[wrong]=owned[wrong].union(originals['trace:0'].buffer(.03,quad_segs=64))
 assert not check_owned(scope,owned)['passed']
 with pytest.raises(ValueError,match='INVENTORY_CHANGED'):check_owned(scope,{wrong:owned[wrong]})

def native_fixture(tmp_path,monkeypatch):
 monkeypatch.setattr(functional,'ACTIVE',None)
 raw=b'%FSLAX46Y46*%\n%MOMM*%\n%ADD10C,0.100000*%\n%ADD11C,0.080000*%\n%LPD*%\nD10*\nX0000000000Y0000000000D02*\nX0010000000Y0000000000D01*\nX0010000000Y0010000000D01*\nX0000000000Y0010000000D01*\nX0000000000Y0000000000D01*\nD11*\nX0002000000Y0000000000D02*\nX0002000000Y0008000000D01*\nX0008000000Y0000000000D02*\nX0008000000Y0008000000D01*\nM02*\n'
 store=p.Store(tmp_path/'runtime');binding=p.build_source(store,raw);scene=store.get_json(binding['scene_ref'],kind='scene');parsed,_,_=p.source_profile.parse_source(raw);source=p.affine_scale(p.source_profile.ordered((p.source_profile.object_geometry(o)[0],o.polarity_dark)for o in parsed.objects),1,-1,origin=(0,0));scope=functional.bind(source,p.digest(raw),scene,store);monkeypatch.setattr(functional,'ACTIVE',scope)
 assert scope is not None
 candidates=[r for r in scene['objects']if r['source_id']not in scope.frame_ids];sid=candidates[0]['source_id'];g=p.geometry(store,candidates[0]['geometry_ref']).buffer(.01,quad_segs=64);records=[];blocks=[];legacy.append_regions(g,'t04',sid,records,blocks,store);base,_=legacy.canonical_base(raw);body=(base+'\n'+''.join(blocks)+'M02*\n').encode();ledger=dict(source_sha256=p.digest(raw),generated_sha256=p.digest(body),records=records);proof=dict(status='PASS',scope='SYNTHETIC_HELPER_INPUT_ONLY',generated_sha256=p.digest(body),source_objects_preserved=binding['source_objects'],contour_proofs=[dict(ordinal=binding['source_objects']+i,stage='t04',source_id=sid)for i in range(len(records))]);out=copy.deepcopy(scene)
 for row in out['objects']:
  if row['source_id']==sid:row['geometry_ref']=p.geomref(store,g)
 stages=[dict(output_scene_ref=store.put_json('scene',out))];return scope,store,binding,stages,body,ledger,[proof,copy.deepcopy(proof)]

def test_actual_native_contours_are_completely_assigned_by_source_id(tmp_path,monkeypatch):
 args=native_fixture(tmp_path,monkeypatch);owned,proof=legacy_channels(*args)
 assert proof['status']=='PASS'and proof['native_positive_regions']==len(args[5]['records'])
 assert len(owned)==len(args[0].cores)
 assert all(r['actual_native_geometry_sha256']for r in proof['inventory'])

@pytest.mark.parametrize('change',['source_id','inventory','prefix','polarity','contour'])
def test_native_channel_controls_cannot_be_promoted_by_a_new_file_hash(tmp_path,monkeypatch,change):
 args=list(native_fixture(tmp_path,monkeypatch));scope,store,binding,stages,body,ledger,proofs=args;reason=''
 if change=='source_id':ledger['records'][0]['source_id']='forged-other-source';reason='SOURCE_ID_OR_STAGE_CHANGED'
 elif change=='inventory':ledger['records'].pop();reason='COMPLETE_REGION_INVENTORY_CHANGED'
 elif change=='prefix':body=body.replace(b'X0010000000',b'X0010001000',1);reason='ORIGINAL_PREFIX_CHANGED'
 elif change=='polarity':
  prefix=(legacy.canonical_base(store.get(binding['source_ref'],kind='gerber-source'))[0]+'\n').encode();body=body[:len(prefix)]+body[len(prefix):].replace(b'%LPD*%',b'%LPC*%',1);reason='REGION_ROLE_CHANGED'
 else:
  ledger['records'][0]['geometry_ref']=p.geomref(store,p.box(50,50,51,51));reason='FIDELITY'
 ledger['generated_sha256']=p.digest(body)
 for proof in proofs:proof['generated_sha256']=p.digest(body)
 with pytest.raises(ValueError)as exc:legacy_channels(scope,store,binding,stages,body,ledger,proofs)
 if change=='contour':assert 'FIDELITY'in str(exc.value).upper()or'HAUSDORFF'in str(exc.value).upper()
 else:assert reason in str(exc.value)
