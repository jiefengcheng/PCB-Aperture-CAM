"""Use native staged attachment bytes without touching original directories."""
from pathlib import Path
import pytest
from tools import t01_crop_jobs as jobs
from tools.t01_crop_attachments import candidates,ingest


@pytest.fixture
def project(tmp_path,monkeypatch):
    monkeypatch.setattr(jobs,'ROOT',tmp_path)
    return tmp_path


def test_desktop_label_reads_only_project_copy_and_handles_timestamp_space(project,monkeypatch):
    p=project/'Screenshot at 10.05.46\u202fPM.png';p.write_bytes(b'actual native staged image')
    seen=[]
    def read(path):
        assert path.parent==project
        seen.append(path)
        return jobs.attachment(path)
    def forbidden(*args,**kwargs):pytest.fail('attachment adapter attempted a file search')
    for name in ['glob','rglob','iterdir']:monkeypatch.setattr(Path,name,forbidden)
    row,blob=ingest('/Users/owner/Desktop/Screenshot at 10.05.46 PM.png',project,read)
    assert seen==[p] and blob==b'actual native staged image'
    assert row['ingestion']['original_path_opened'] is False
    assert row['ingestion']['directory_search'] is False
    assert row['ingestion']['staged_name']==p.name


def test_arbitrary_new_crop_name_is_not_tied_to_screenshot_or_prior_crop(project):
    p=project/'new board ROI.png';p.write_bytes(b'new crop')
    row,blob=ingest(p.name,project,jobs.attachment)
    assert blob==b'new crop' and row['path']==str(p)


def test_missing_stage_does_not_open_original_even_if_original_exists(project,tmp_path_factory):
    outside=tmp_path_factory.mktemp('original')/'crop.png';outside.write_bytes(b'original inaccessible to client')
    with pytest.raises(ValueError,match='ATTACHMENT_BYTES_UNAVAILABLE'):
        ingest(str(outside),project,lambda p:pytest.fail('read original file'))


def test_missing_stage_never_substitutes_previous_image(project):
    (project/'old crop.png').write_bytes(b'old input')
    with pytest.raises(ValueError,match='ATTACHMENT_BYTES_UNAVAILABLE'):
        ingest('current crop.png',project,jobs.attachment)


def test_conflicting_timestamp_names_halt_even_if_exact_exists(project):
    (project/'Crop 10.05 PM.png').write_bytes(b'old')
    (project/'Crop 10.05\u202fPM.png').write_bytes(b'new')
    with pytest.raises(ValueError,match='ATTACHMENT_NAME_AMBIGUOUS'):
        ingest('Crop 10.05 PM.png',project,jobs.attachment)


def test_identical_name_variants_are_byte_bound(project):
    for name in ['Crop 10.05 PM.png','Crop 10.05\u202fPM.png']:(project/name).write_bytes(b'same')
    row,blob=ingest('Crop 10.05 PM.png',project,jobs.attachment,expected_sha256=jobs.digest(b'same'))
    assert blob==b'same' and row['ingestion']['metadata_hash_verified'] is True
    with pytest.raises(ValueError,match='METADATA_HASH_MISMATCH'):
        ingest('Crop 10.05 PM.png',project,jobs.attachment,expected_sha256=jobs.digest(b'different'))


def test_staged_symlink_is_not_followed(project):
    p=project/'target';p.write_bytes(b'bytes');(project/'attachment.png').symlink_to(p)
    with pytest.raises(ValueError,match='SYMLINK'):ingest('attachment.png',project,jobs.attachment)


@pytest.mark.parametrize('label',['../outside.png','folder/file.png','/Users/owner/../outside.png','',None])
def test_invalid_labels_reject_before_reads(label,project):
    with pytest.raises(ValueError):ingest(label,project,lambda p:pytest.fail('unexpected read'))


def test_only_declared_filename_rules_apply():
    assert set(candidates('ROI at noon.png'))=={'ROI at noon.png'}
    assert 'ROI at\u202fnoon.png' not in candidates('ROI at noon.png')
    assert len(candidates('Screenshot 10.05.46 PM.png'))==2


def test_permission_error_on_staged_file_stops_without_desktop_fallback(project):
    p=project/'crop.png';p.write_bytes(b'file')
    def denied(path):raise PermissionError('denied project attachment')
    with pytest.raises(PermissionError):ingest('/Desktop/crop.png',project,denied)


def test_job_inputs_stage_crop_and_replacements_through_same_adapter(project):
    contract=project/'contracts/operator';contract.mkdir(parents=True)
    (contract/'t01_project.json').write_text('{"inputs":{}}')
    blobs=dict(crop=b'image',kicad=b'native',gerber=b'gerber')
    names=dict(crop='ROI.png',kicad='board.kicad_pcb',gerber='board.gbr')
    for key in blobs:(project/names[key]).write_bytes(blobs[key])
    rows,actual=jobs.inputs(None,attachments=names)
    assert actual==blobs and all(row['ingestion']['original_path_opened'] is False for row in rows.values())
    with pytest.raises(ValueError,match='ONE_INPUT_REPRESENTATION'):
        jobs.inputs('other-crop.png',attachments=names)
