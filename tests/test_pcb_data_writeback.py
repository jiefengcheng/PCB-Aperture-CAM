"""Format precision, semantic preservation and real parser negative controls."""
import json,subprocess
from pathlib import Path
import pytest,sexpdata
from shapely.geometry import Point,Polygon
from shapely import from_wkb
from src.source_locators import locate
from src.stage_abi.store import ArtifactStore,digest
from src.pcb_data_abi.geometry import quantize,fidelity
from src.pcb_data_abi import native,gerber
from src.pcb_data_abi.service import plot_name

ROOT=Path(__file__).resolve().parents[1]
RAW=b'(kicad_pcb (version 20240928) (generator "test") (layers (0 F.Cu signal) (1 F.Mask user)) (gr_circle (center 1 -1) (end 1.1 -1) (stroke (width 0) (type solid)) (fill yes) (layer F.Cu)) (gr_line (start 0 0) (end 1 0) (stroke (width 0.01) (type solid)) (layer F.Mask)))'
EDIT=b'(kicad_pcb (version 20240928) (gr_poly (pts (xy 0 0) (xy 1 0) (xy 1 1) (xy 0 1)) (stroke (width 0) (type solid)) (fill yes) (layer F.Cu)))'


def test_pinned_kicad_native_output_layer_names():
 assert plot_name('F.SilkS')=='board-F_Silkscreen.gbr'
 assert plot_name('B.SilkS')=='board-B_Silkscreen.gbr'
 assert plot_name('F.Cu')=='board-F_Cu.gbr'


def operands():
 sid=next(s.identity for s in locate(RAW) if s.head=='gr_circle')
 shape=Point(1,-1).buffer(.15,quad_segs=128)
 decision=dict(key='S31',source_id=sid,aliases=[sid],decision='GROW_COMPANION',candidate_ref=dict(sha256=digest(shape.wkb)))
 return [decision],{sid:shape}


def test_edit_style_roundtrip_allows_different_bytes_and_preserves_protected_semantics():
 decisions,targets=operands();body,rows=native.write_board(RAW,EDIT,decisions,targets)
 assert body!=RAW and b'gr_poly' in body
 result=native.verify_board(RAW,body,rows,decisions,targets)
 assert result['passed'] and result['modified_occurrences']==1
 assert rows[0]['uuid'] in body.decode()


def test_changed_mask_geometry_rejected_even_when_target_matches():
 decisions,targets=operands();body,rows=native.write_board(RAW,EDIT,decisions,targets)
 root=sexpdata.loads(body.decode());node=next(n for n in root if isinstance(n,list) and str(n[0])=='gr_line');next(n for n in node if isinstance(n,list) and str(n[0])=='start')[1]=.01
 with pytest.raises(ValueError,match='PROTECTED_NATIVE_OBJECT_CHANGED'):native.verify_board(RAW,native.board_bytes(root),rows,decisions,targets)


def test_wrong_target_layer_rejected():
 decisions,targets=operands();body,rows=native.write_board(RAW,EDIT,decisions,targets)
 root=sexpdata.loads(body.decode());node=root[rows[0]['index']];next(n for n in node if isinstance(n,list) and str(n[0])=='layer')[1]=sexpdata.Symbol('F.Mask')
 with pytest.raises(ValueError,match='TARGET_NATIVE_LAYER_CHANGED'):native.verify_board(RAW,native.board_bytes(root),rows,decisions,targets)


def test_keep_source_circle_is_not_replaced():
 decisions,targets=operands();decisions[0]['decision']='KEEP_PRIORITY';targets[decisions[0]['source_id']]=native.geometry(next(n for n in sexpdata.loads(RAW.decode())[1:] if isinstance(n,list) and str(n[0])=='gr_circle'),'gr_circle')
 body,rows=native.write_board(RAW,EDIT,decisions,targets)
 assert rows[0]['growing'] is False and rows[0]['uuid'] is None
 assert native.verify_board(RAW,body,rows,decisions,targets)['modified_occurrences']==0


def test_actual_s01_rounding_regression_measured_not_silently_repaired():
 r=ROOT/'out/crop_dynamic_tasks/t01_c01_macos_recovery_20261031_305/run';s=ArtifactStore(r/'runtime');v=json.loads((r/'RECEIPT.json').read_bytes());c=s.get_json(v['candidate_ref'],kind='candidate');d=next(d for d in c['decisions'] if d['key']=='S01');g=from_wkb(s.get(d['candidate_ref'],kind='geometry'))
 pointwise=Polygon([(round(x,6),round(y,6)) for x,y in g.exterior.coords]);assert not pointwise.is_valid
 q,report=quantize(g)
 assert q.is_valid and report['subgrid_collapse_visible']
 assert report['raw_symmetric_difference_mm2']<=report['area_change_bound_mm2']
 assert fidelity(g,q)['passed']


def test_large_contour_change_is_not_a_file_precision_exception():
 _,targets=operands();g=next(iter(targets.values()))
 with pytest.raises(ValueError,match='CONTOUR_FIDELITY_FAILED'):fidelity(g,g.buffer(.001))


@pytest.mark.parametrize('shape',[Polygon(),Polygon([(0,0),(1,1),(0,1),(1,0)]),Point(0,0).buffer(1).difference(Point(0,0).buffer(.5))])
def test_unsupported_or_invalid_polygon_is_explicit(shape):
 with pytest.raises(ValueError):quantize(shape)


GOOD=b'%FSLAX46Y46*%\n%MOMM*%\n%TF.SameCoordinates,Original*%\n%TF.FileFunction,Copper,L1,Top*%\n%TF.FilePolarity,Positive*%\n%ADD10C,0.001*%\nD10*\nG01*\nG36*\nX0Y0D02*\nX1000000Y0D01*\nX1000000Y1000000D01*\nX0Y1000000D01*\nX0Y0D01*\nG37*\nM02*\n'


def test_real_gerber_parser_and_fixed_axis_mapping(tmp_path):
 p=tmp_path/'valid.gbr';p.write_bytes(GOOD);g=gerber.parse(p)
 q=gerber.native_geometry(g.objects[0]);assert q.bounds==(0,-1,1,0)
 assert gerber.atom(g.objects[0])[0]=='region'


def test_graphic_profile_does_not_silently_drop_explicit_object_attributes(tmp_path):
 p=tmp_path/'attributed.gbr';p.write_bytes(GOOD.replace(b'G36*',b'%TO.N,not-qualified*%\nG36*'))
 with pytest.raises(ValueError,match='OBJECT_ATTRIBUTES_OUTSIDE_GRAPHIC_PROFILE'):gerber.parse(p)


def test_native_empty_unassigned_net_attribute_is_supported(tmp_path):
 p=tmp_path/'unassigned.gbr';p.write_bytes(GOOD.replace(b'G36*',b'%TO.N,*%\nG36*'))
 assert len(gerber.parse(p).objects)==1


@pytest.mark.parametrize('old,new,error',[(b'MOMM',b'MOIN','GERBER_PROFILE'),(b'G37*\n',b'','GERBER_PROFILE'),(b'Original',b'Unregistered','GERBER_COORDINATE_FRAME_UNQUALIFIED')])
def test_deliberate_corrupted_gerber_fails(tmp_path,old,new,error):
 p=tmp_path/'bad.gbr';p.write_bytes(GOOD.replace(old,new))
 with pytest.raises(ValueError,match=error):gerber.parse(p)


def test_registry_hash_is_checked_by_actual_pcb_cli(tmp_path):
 reg=tmp_path/'host.json';reg.write_bytes(b'{}');request=tmp_path/'request.json';request.write_text(json.dumps(dict(abi_version='pcb-data-abi/1',request_id='hash-negative',operation='pcb_kicad_write')))
 p=subprocess.run([str(ROOT/'.venv/bin/python'),'-B',str(ROOT/'tools/pcb_data_abi.py'),'--registry',str(reg),'--registry-sha256','0'*64,'--input',str(request)],capture_output=True)
 v=json.loads(p.stdout);assert p.returncode==2 and v['status']=='REJECTED' and v['result']is None
 assert v['error']['message']=='PCB_DATA_HOST_HASH_MISMATCH'


@pytest.mark.parametrize('blob',[b'[]',b'{"abi_version":NaN}',b'{"operation":"a","operation":"b"}'])
def test_actual_cli_returns_closed_rejection_for_bad_wire_input(tmp_path,blob):
 reg=tmp_path/'host.json';reg.write_bytes(b'{}');request=tmp_path/'request.json';request.write_bytes(blob)
 p=subprocess.run([str(ROOT/'.venv/bin/python'),'-B',str(ROOT/'tools/pcb_data_abi.py'),'--registry',str(reg),'--registry-sha256',digest(b'{}'),'--input',str(request)],capture_output=True)
 v=json.loads(p.stdout);assert p.returncode==2 and v['status']=='REJECTED' and v['result']is None
