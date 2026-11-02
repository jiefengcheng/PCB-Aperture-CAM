"""The board and crop routes share the working file-only native launch setup."""
from pathlib import Path
import pytest
from tools import t01_crop_jobs as jobs
from tools import t01_board_jobs as board
from tools.t01_route_client import publish,encode

@pytest.fixture
def registry(tmp_path,monkeypatch):
    monkeypatch.setattr(jobs,'ROOT',tmp_path);monkeypatch.setattr(jobs,'MANAGED',tmp_path/'out/managed');monkeypatch.setattr(jobs,'implementation',lambda:'board-code-v1');jobs.MANAGED.mkdir(parents=True);return tmp_path

def payload():
    blobs=dict(kicad=b'board source',gerber=b'source Gerber');return {k:dict(path='/explicit/'+k,sha256=jobs.digest(v),bytes=len(v))for k,v in blobs.items()},blobs

def test_whole_board_job_has_no_crop_dependency_and_keeps_completed_crop(registry):
    rows,blobs=payload();crop_rows=dict(rows,crop=dict(path='/explicit/crop',sha256=jobs.digest(b'crop'),bytes=4));crop_blobs=dict(blobs,crop=b'crop');old,_=jobs.allocate(crop_rows,crop_blobs);ui=old/'native/operator_ui';ui.mkdir(parents=True);publish(ui/'current.json',encode(dict(status='COMPLETE')))
    from src.trace_first_pipeline import inventory
    before=inventory(old);new,row=board.allocate(rows,blobs)
    assert row['task_scope']=='full-board'and set(row['staged'])=={'kicad','gerber'}and inventory(old)==before
    assert Path(row['staged']['kicad']).read_bytes()==b'board source'

def test_board_and_crop_cannot_start_over_each_other(registry):
    board.allocate(*payload())
    with pytest.raises(ValueError,match='IN_PROGRESS'):board.allocate(*payload())
    rows,blobs=payload();rows['crop']=dict(path='crop',sha256=jobs.digest(b'c'),bytes=1);blobs['crop']=b'c'
    with pytest.raises(ValueError,match='IN_PROGRESS'):jobs.allocate(rows,blobs)

def test_board_failure_cannot_be_retried_or_renamed(registry):
    old,_=board.allocate(*payload());jobs.halt(old,'full-board control failure');rows,blobs=payload();rows['kicad']['path']='renamed.kicad_pcb'
    with pytest.raises(ValueError,match='FAILED_CROP_INPUTS_RETAINED'):board.allocate(rows,blobs)
