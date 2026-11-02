"""Input-dir ABI inventories actual bytes/roles; no project defaults or filename guessing."""
from pathlib import Path
import json,pytest
from src.pcb_data_abi.input_directory import collect,verify_snapshot,digest,layer_role,validate
from tools import t01_crop_jobs as jobs,t01_board_export_jobs as export_jobs


def gerber(role='Copper,L1,Top'):
    return ('%TF.FileFunction,'+role+'*%\n%MOMM*%\nM02*\n').encode()

def inputs(root):
    root.mkdir();(root/'my raw board.kicad_pcb').write_bytes(b'(kicad_pcb (version 20260101))');(root/'layers').mkdir();(root/'layers/anything.dat').write_bytes(gerber());return root


def test_explicit_dir_nested_roles_and_unicode_names(tmp_path):
    root=inputs(tmp_path/'input space');(root/'layers/背面.gbr').write_bytes(gerber('Copper,L2,Bot'));(root/'.DS_Store').write_bytes(b'metadata')
    manifest,blobs=collect(root);assert len(manifest['files'])==3 and manifest['ignored_metadata']==['.DS_Store']
    assert {r['layer']for r in manifest['files']}=={None,'F.Cu','B.Cu'}
    snapshot=tmp_path/'snapshot'
    for name,blob in blobs.items():
        target=snapshot/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(blob)
    assert verify_snapshot(manifest,snapshot)['F.Cu'].name=='anything.dat'
    assert all(digest(blobs[r['relative_path']])==r['sha256']for r in manifest['files'])


@pytest.mark.parametrize('mutation',['missing_board','missing_fcu','two_boards','two_fcu','unsupported_layer','untyped','symlink_file','symlink_dir','wrong_board'])
def test_ambiguous_or_unsupported_raw_input_halts(tmp_path,mutation):
    root=inputs(tmp_path/'input');board=root/'my raw board.kicad_pcb';fcu=root/'layers/anything.dat'
    if mutation=='missing_board':board.unlink()
    if mutation=='missing_fcu':fcu.unlink()
    if mutation=='two_boards':(root/'other.kicad_pcb').write_bytes(board.read_bytes())
    if mutation=='two_fcu':(root/'duplicate.gbr').write_bytes(fcu.read_bytes())
    if mutation=='unsupported_layer':fcu.write_bytes(gerber('Copper,L3,Inr'))
    if mutation=='untyped':(root/'note.txt').write_text('not PCB input')
    if mutation=='symlink_file':(root/'link.gbr').symlink_to(fcu)
    if mutation=='symlink_dir':(root/'linked').symlink_to(root/'layers',target_is_directory=True)
    if mutation=='wrong_board':board.write_bytes(b'not a KiCad board')
    with pytest.raises(ValueError):collect(root)


def test_no_input_directory_means_no_defaults():
    with pytest.raises(ValueError,match='EXPLICIT_INPUT_DIRECTORY'):collect(None)


@pytest.mark.parametrize('role,layer',[('Copper,L1,Top','F.Cu'),('Copper,L32,Bot','B.Cu'),('Legend,Bot','B.SilkS'),('Profile,NP','Edge.Cuts')])
def test_x2_roles_are_explicit_not_filename_dependent(role,layer):assert layer_role(gerber(role))==layer


def test_snapshot_file_and_inventory_tampering_reject(tmp_path):
    root=inputs(tmp_path/'input');manifest,_=collect(root);file=root/'layers/anything.dat';file.write_bytes(file.read_bytes()+b'changed')
    with pytest.raises(ValueError,match='SNAPSHOT_CHANGED'):verify_snapshot(manifest,root)
    file.unlink()
    with pytest.raises(ValueError,match='FILE_SET_CHANGED'):verify_snapshot(manifest,root)


def test_manifest_traversal_rejects(tmp_path):
    manifest,_=collect(inputs(tmp_path/'input'));manifest['files'][0]['relative_path']='../outside'
    with pytest.raises(ValueError,match='PATH_INVALID'):validate(manifest)


@pytest.fixture
def managed(tmp_path,monkeypatch):
    monkeypatch.setattr(jobs,'ROOT',tmp_path);monkeypatch.setattr(jobs,'MANAGED',tmp_path/'out/managed');monkeypatch.setattr(jobs,'implementation',lambda:'export-only-v1');jobs.MANAGED.mkdir(parents=True);return tmp_path


def test_stages_all_raw_bytes_and_failed_renaming_cannot_retry(managed):
    source=inputs(managed/'source');(source/'mask.gbr').write_bytes(gerber('Soldermask,Top'));manifest,blobs=collect(source);job,row=export_jobs.allocate(manifest,blobs)
    assert row['task_scope']=='full-board-export-only'and row['rendering']=='NOT_REQUESTED'
    assert collect(source)[1]==blobs and verify_snapshot(manifest,job/'raw_inputs')['F.Mask'].read_bytes()==gerber('Soldermask,Top')
    jobs.halt(job,'deliberate failure');(source/'layers/anything.dat').rename(source/'layers/renamed.gbr');renamed,more=collect(source)
    with pytest.raises(ValueError,match='FAILED_CROP_INPUTS_RETAINED'):export_jobs.allocate(renamed,more)


def test_cannot_replace_active_other_profile_and_cannot_edit_raw_input(managed):
    manifest,blobs=collect(inputs(managed/'source'));first,_=export_jobs.allocate(manifest,blobs)
    with pytest.raises(ValueError,match='IN_PROGRESS'):export_jobs.allocate(manifest,blobs)
    assert collect(managed/'source')[1]==blobs


def test_failed_staging_keeps_failed_job_identity(managed):
    manifest,blobs=collect(inputs(managed/'source'));blobs[manifest['files'][0]['relative_path']]=b'changed'
    with pytest.raises(ValueError,match='BEFORE_STAGING'):export_jobs.allocate(manifest,blobs)
    recorded=list((jobs.MANAGED/'jobs').glob('*/job.json'));assert len(recorded)==1 and(recorded[0].parent/'halted.json').exists()
    with pytest.raises(ValueError,match='FAILED_CROP_INPUTS_RETAINED'):export_jobs.allocate(manifest,blobs)


def test_concurrent_addition_cannot_be_omitted_from_input_directory(tmp_path,monkeypatch):
    from src.pcb_data_abi import input_directory as module
    root=inputs(tmp_path/'input');original=module.regular_bytes;changed=False
    def read(path):
        nonlocal changed
        data=original(path)
        if not changed:(root/'late.gbr').write_bytes(gerber('Soldermask,Top'));changed=True
        return data
    monkeypatch.setattr(module,'regular_bytes',read)
    with pytest.raises(ValueError,match='FILE_SET_CHANGED_DURING_INTAKE'):collect(root)
