import copy
import pytest
from shapely import from_wkb
from shapely.geometry import box
from src.gerber_u05 import pipeline as p,source_assembly as a
from src import source_channel_scope as scope

RAW=b'''%FSLAX46Y46*%
%MOMM*%
%ADD10C,0.100000*%
%ADD11C,0.080000*%
%ADD12C,0.300000*%
%LPD*%
D10*
X0000000000Y0000000000D02*
X0010000000Y0000000000D01*
X0010000000Y0010000000D01*
X0000000000Y0010000000D01*
X0000000000Y0000000000D01*
D11*
X0002000000Y0000000000D02*
X0002000000Y0008000000D01*
X0008000000Y0000000000D02*
X0008000000Y0008000000D01*
D12*
X0002000000Y0007000000D03*
X0008000000Y0007000000D03*
M02*
'''

def test_only_confirmed_outer_strokes_removed_with_exact_native_retention(tmp_path):
 assembled,proof=a.reconstruct(RAW,p.Store(tmp_path/'runtime'))
 assert proof['removed_objects']==4 and proof['retained_objects']==4
 assert proof['policy']==a.POLICY and proof['disposition']=='CONFIRMED_ENCLOSURE_REMOVED'
 assert proof['raw_source_sha256']==p.digest(RAW) and not proof['raw_input_modified']
 assert assembled.count(b'D01*')==2 and assembled.count(b'D02*')==7
 assert a.verify_payload(RAW,assembled,proof,p.Store(tmp_path/'independent'))==proof

def test_duplicate_enclosure_occurrences_all_removed(tmp_path):
 duplicate=b'D10*\nX0000000000Y0000000000D02*\nX0010000000Y0000000000D01*\n'
 raw=RAW.replace(b'M02*',duplicate+b'M02*')
 assembled,proof=a.reconstruct(raw,p.Store(tmp_path/'runtime'))
 assert proof['removed_objects']==5 and proof['retained_objects']==4
 assert p.source_profile.parse_source(assembled)[0].objects

def test_open_loop_and_functional_copper_unchanged(tmp_path):
 raw=RAW.replace(b'X0000000000Y0000000000D01*\n',b'X0000000000Y0000000001D01*\n')
 assembled,proof=a.reconstruct(raw,p.Store(tmp_path/'runtime'))
 assert assembled==raw and proof['removed_objects']==0
 assert proof['disposition']=='NO_UNAMBIGUOUS_ENCLOSURE_UNCHANGED'

def test_inner_loop_is_not_deleted_when_other_artwork_is_outside(tmp_path):
 raw=RAW.replace(b'M02*',b'D12*\nX0020000000Y0020000000D03*\nM02*')
 assembled,proof=a.reconstruct(raw,p.Store(tmp_path/'runtime'))
 assert assembled==raw and proof['removed_objects']==0

@pytest.mark.parametrize('mutation',['restore','trace','polarity','receipt','source'])
def test_unauthorized_geometry_or_proof_change_rejected(tmp_path,mutation):
 assembled,proof=a.reconstruct(RAW,p.Store(tmp_path/'runtime'));raw=RAW
 if mutation=='restore':assembled=RAW
 elif mutation=='trace':assembled=assembled.replace(b'X0002000000Y0008000000',b'X0002000001Y0008000000')
 elif mutation=='polarity':assembled=assembled.replace(b'%LPD*%',b'%LPC*%')
 elif mutation=='receipt':proof=copy.deepcopy(proof);proof['removed_objects']-=1
 else:raw=raw.replace(b'0.300000',b'0.310000')
 with pytest.raises(ValueError,match='ASSEMBLY_AUTHORIZED_CHANGE_OR_PROOF_CHANGED'):
  a.verify_payload(raw,assembled,proof,p.Store(tmp_path/'independent'))

def test_implicit_operation_is_rejected_before_assembly(tmp_path):
 # Existing parser forbids implicit operations; assembly must retain that check.
 raw=RAW.replace(b'D11*\nX0002000000Y0000000000D02*',b'D11*\nX0002000000Y0000000000*')
 with pytest.raises(SyntaxError,match='without explicit operation code'):
  a.reconstruct(raw,p.Store(tmp_path/'runtime'))

def test_removal_keeps_integral_pad_trace_owner_but_separates_channels(tmp_path,monkeypatch):
 store=p.Store(tmp_path/'runtime');raw,proof=a.reconstruct(RAW,store);binding=p.build_source(store,raw);scene=store.get_json(binding['scene_ref'],kind='scene')
 parsed,_,_=p.source_profile.parse_source(raw);source=p.affine_scale(p.source_profile.ordered((p.source_profile.object_geometry(o)[0],o.polarity_dark)for o in parsed.objects),1,-1,origin=(0,0))
 old=scope.ACTIVE
 try:
  integral=scope.bind(source,p.digest(raw),scene,store,integral=True)
  assert len(integral.cores)==2 and not integral.frame_ids
  rows={r['source_id']:from_wkb(store.get(r['original_ref'],kind='geometry'))for r in scene['objects']}
  assert sorted(len([s for s in rows if integral.owner(s)==o])for o in integral.cores)==[2,2]
  assert integral.channels.check(source)['passed']
  assert not integral.channels.check(source.union(box(2,-6,8,-5.9)))['passed']
 finally:scope.ACTIVE=old

def test_integral_binding_rejects_an_unremoved_enclosure(tmp_path):
 store=p.Store(tmp_path/'runtime');binding=p.build_source(store,RAW);scene=store.get_json(binding['scene_ref'],kind='scene');source=p.unary_union([p.geometry(store,r['original_ref'])for r in scene['objects']])
 with pytest.raises(ValueError,match='ASSEMBLED_SOURCE_STILL_HAS_CONFIRMED_OUTER_ENCLOSURE'):
  scope.bind(source,p.digest(RAW),scene,store,integral=True)
