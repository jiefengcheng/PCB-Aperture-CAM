"""Export completion delivers bound files without assuming any rendering output."""
from pathlib import Path
from types import SimpleNamespace
import json,pytest
from tools import pcb_t01_board_export_operator as module
from tools.t01_route_client import encode


def put(p,value):
    p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(value if isinstance(value,bytes)else encode(value));return module.sha(p.read_bytes())


@pytest.fixture
def terminal(tmp_path,monkeypatch):
    root=tmp_path/'job/native';out=root/'data_output';board=out/'candidate/board.kicad_pcb';gerber=out/'candidate/gerbers/board-F_Cu.gbr';bh=put(board,b'actual candidate bytes');gh=put(gerber,b'actual exported Gerber bytes')
    put(out/'pcb_kicad_write.json',dict(board=str(board),board_sha256=bh));put(out/'pcb_gerber_export.json',dict(exports=dict(candidate={'F.Cu':str(gerber)}),output_sha256={str(gerber):gh}))
    manifest=root.parent/'INPUT_DIRECTORY.json';mh=put(manifest,dict(provided_directory='/explicit/raw directory',files=[]));put(root.parent/'job.json',dict(input_directory=str(manifest),input_directory_sha256=mh))
    for name in['RECEIPT.json','data_board/directory_inputs_verified.json']:put(root/name,{})
    put(root/'data_board/verified.json',dict(canonical_sites=2,source_occurrences=3,source_objects=5))
    put(root/'operator_ui/slice-10.json',dict(result=dict(facts=dict(added_area_mm2=.2,removed_area_mm2=0))))
    cp=root/'EXPORT_CHECKPOINT.json';ch=put(cp,dict(files={str(board.relative_to(root)):bh,str(gerber.relative_to(root)):gh}));put(root/'EXPORT_ONLY_RECEIPT.json',dict(status='PASS_FRESH_DIRECTORY_T01_EXPORT',operations=list(module.ExportOperator.steps),rendering='NOT_REQUESTED',checkpoint=str(cp),checkpoint_sha256=ch))
    monkeypatch.setattr(module,'scoped',lambda p:Path(p));operator=module.ExportOperator.__new__(module.ExportOperator);operator.client=SimpleNamespace(root=root);return operator


def test_native_exports_produce_only_html_report_and_bound_delivery(terminal):
    result=terminal.delivery();assert result['native_slices']==result['observation_audits']==18 and result['render_operations']==0 and result['rendering']=='NOT_REQUESTED'
    assert result['fresh_source_construction']is True and result['owner']=='PENDING_USER'and Path(result['html']).exists()
    assert not(terminal.client.root/'render_output').exists()and all(p.suffix not in('.png','.svg','.pdf')for p in terminal.client.root.rglob('*'))
    assert 'supplied raw directory'in result['ready_markdown']


@pytest.mark.parametrize('change',['checkpoint','candidate','render_output','render_host'])
def test_terminal_refuses_changed_files_or_unrequested_rendering(terminal,change):
    root=terminal.client.root
    if change=='checkpoint':(root/'EXPORT_CHECKPOINT.json').write_text('{}')
    if change=='candidate':(root/'data_output/candidate/board.kicad_pcb').write_bytes(b'changed')
    if change=='render_output':(root/'render_output').mkdir()
    if change=='render_host':(root/'pipeline_render_host.json').write_text('{}')
    with pytest.raises(ValueError):terminal.delivery()


def test_excluded_companions_are_delivered_identically_with_no_geometry_claim(terminal):
    root=terminal.client.root;manifest=root.parent/'INPUT_DIRECTORY.json';source=root.parent/'raw_inputs/nested/unmatched.gbr';blob=b'raw original companion';put(source,blob)
    row=dict(relative_path='nested/unmatched.gbr',kind='companion',layer=None,sha256=module.sha(blob),bytes=len(blob))
    mh=put(manifest,dict(provided_directory='/explicit/raw directory',files=[row]));put(root.parent/'job.json',dict(input_directory=str(manifest),input_directory_sha256=mh))
    result=terminal.delivery();companion=result['excluded_companions'][0]
    assert Path(companion['path']).read_bytes()==blob and 'NOT_ESTABLISHED'in companion['geometry_qualification']
    assert 'excluded companion files'in result['ready_markdown']
    Path(companion['path']).write_bytes(b'changed')
    with pytest.raises(ValueError,match='COMPANION_COPY_CHANGED'):terminal.delivery()
