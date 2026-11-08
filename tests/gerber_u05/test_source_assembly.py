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


def outer_rectangle(low,high):
 def coord(value):return f'{value:010d}'.encode()
 def point(x,y,op):return b'X'+coord(x)+b'Y'+coord(y)+op+b'*\n'
 return (b'D10*\n'+point(low,low,b'D02')+point(high,low,b'D01')+
         point(high,high,b'D01')+point(low,high,b'D01')+point(low,low,b'D01'))


@pytest.mark.parametrize('case,expected',[
 ('single','8ebf0161b59e9baf5257b8b32e1f079d8049187f4b0ee0693803956792af5ede'),
 ('none','18a10b9b041147cb864099ff14f1a5a9734eeefe8dadbef6eb2e37f43e1bd68c'),
])
def test_single_and_no_frame_receipts_match_frozen_626_baseline(tmp_path,case,expected):
 raw=RAW if case=='single'else RAW.replace(b'M02*',b'D12*\nX0020000000Y0020000000D03*\nM02*')
 _,proof=a.reconstruct(raw,p.Store(tmp_path/'runtime'))
 assert p.digest(p.canonical(proof))==expected
 assert 'enclosure_rounds'not in proof


@pytest.mark.parametrize('count',[2,3])
def test_nested_rectangles_all_removed_before_integral_binding(tmp_path,count):
 # Retain an isolated interior pad so the unchanged requirement for at least
 # two physical components after each candidate frame removal is satisfied.
 raw=RAW.replace(b'M02*',b'D12*\nX0005000000Y0005000000D03*\nM02*')
 for n in range(1,count):
  raw=raw.replace(b'M02*',outer_rectangle(-n*1000000,(10+n)*1000000)+b'M02*')
 store=p.Store(tmp_path/'runtime');assembled,proof=a.reconstruct(raw,store)
 assert proof['removed_objects']==4*count and proof['retained_objects']==5
 assert len(proof['enclosure_rounds'])==count
 assert proof['final_enclosure_certificate']['status']=='NO_UNAMBIGUOUS_COMMON_FRAME'
 assert len({r['original_ordinal']for r in proof['removed']})==4*count
 chain=proof['enclosure_rounds']
 assert chain[0]['input_source_sha256']==p.digest(raw)
 assert chain[-1]['output_source_sha256']==p.digest(assembled)
 assert all(left['output_source_sha256']==right['input_source_sha256']for left,right in zip(chain,chain[1:]))
 assert a.verify_payload(raw,assembled,proof,p.Store(tmp_path/'independent'))==proof
 binding=p.build_source(store,assembled);scene=store.get_json(binding['scene_ref'],kind='scene')
 parsed,_,_=p.source_profile.parse_source(assembled)
 source=p.affine_scale(p.source_profile.ordered((p.source_profile.object_geometry(o)[0],o.polarity_dark)for o in parsed.objects),1,-1,origin=(0,0))
 old=scope.ACTIVE
 try:
  integral=scope.bind(source,p.digest(assembled),scene,store,integral=True)
  assert len(integral.cores)==3 and not integral.frame_ids
  assert integral.channels.check(source)['passed']
 finally:scope.ACTIVE=old


def test_nested_removal_stops_when_inner_loop_does_not_enclose_all_copper(tmp_path):
 outside=b'D12*\nX0012000000Y0012000000D03*\n'
 outer=outer_rectangle(-2000000,14000000)
 raw=RAW.replace(b'M02*',outside+outer+b'M02*')
 assembled,proof=a.reconstruct(raw,p.Store(tmp_path/'runtime'))
 assert proof['removed_objects']==4
 assert proof['retained_objects']==9
 assert assembled.count(b'D01*')==6
 assert 'enclosure_rounds'not in proof


def test_tampered_nested_round_or_terminal_certificate_rejected(tmp_path):
 raw=RAW.replace(b'M02*',b'D12*\nX0005000000Y0005000000D03*\n'+outer_rectangle(-1000000,11000000)+b'M02*')
 assembled,proof=a.reconstruct(raw,p.Store(tmp_path/'runtime'))
 for mutation in ('round','terminal'):
  altered=copy.deepcopy(proof)
  if mutation=='round':altered['enclosure_rounds'][1]['input_source_sha256']='0'*64
  else:altered['final_enclosure_certificate']['status']='UNAMBIGUOUS_ORIGINAL_COMMON_FRAME'
  with pytest.raises(ValueError,match='ASSEMBLY_AUTHORIZED_CHANGE_OR_PROOF_CHANGED'):
   a.verify_payload(raw,assembled,altered,p.Store(tmp_path/mutation))


def test_empty_certified_frame_cannot_create_an_unbounded_loop(tmp_path,monkeypatch):
 import src.source_common_frame as common
 monkeypatch.setattr(common,'discover',lambda *args:(box(0,0,10,10),dict(status='UNAMBIGUOUS_ORIGINAL_COMMON_FRAME',frame_source_rows=[])))
 with pytest.raises(ValueError,match='ASSEMBLY_ENCLOSURE_REMOVAL_MUST_PROGRESS'):
  a.reconstruct(RAW,p.Store(tmp_path/'runtime'))
