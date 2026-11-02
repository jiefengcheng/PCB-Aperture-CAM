"""Project-local LaCie-backed APFS workspace. Never fall back to internal storage."""
import os,json,tempfile,subprocess,plistlib,sys,uuid,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
VOLUME=Path('/Volumes/LaCie')
IMAGE=VOLUME/'PCB_Aperture_CAM_Workspace/PCB_CAM_Work.sparsebundle'
WORK=ROOT/'out/lacie_work'
IDENTITY='5E178CE8-A7FF-37D9-B307-F0D08FBB4D14'


def require_storage():
    if not os.path.ismount(VOLUME) or not os.path.ismount(WORK):
        raise RuntimeError('LACIE_WORKSPACE_UNAVAILABLE: run tools/Prepare_LaCie_Workspace.command; no internal fallback')
    marker=WORK/'STORAGE_IDENTITY.json'
    if not marker.is_file() or json.loads(marker.read_text()).get('lacie_volume_uuid')!=IDENTITY:
        raise RuntimeError('LACIE_WORKSPACE_IDENTITY_MISMATCH')
    if WORK.stat().st_dev==ROOT.stat().st_dev:
        raise RuntimeError('LACIE_WORKSPACE_IS_INTERNAL')
    if min(shutil.disk_usage(WORK).free,shutil.disk_usage(VOLUME).free)<5*1024**3:
        raise RuntimeError('LACIE_LOW_SPACE: at least 5 GiB reserve required')
    return WORK


def configure():
    work=require_storage();tmp=work/'tmp';tmp.mkdir(exist_ok=True)
    os.environ.update(TMPDIR=str(tmp),TMP=str(tmp),TEMP=str(tmp),PYTHONDONTWRITEBYTECODE='1',XDG_CACHE_HOME=str(work/'cache'))
    tempfile.tempdir=str(tmp)
    return work


def guard_mountpoint():
    """An absent external volume must leave an unwritable internal directory."""
    if os.path.ismount(WORK):raise RuntimeError('CANNOT_GUARD_MOUNTED_VOLUME')
    WORK.mkdir(parents=True,exist_ok=True)
    old_mode=WORK.stat().st_mode&0o777
    os.chmod(WORK,0o700)
    try:
        if any(WORK.iterdir()):raise RuntimeError('MOUNTPOINT_NOT_EMPTY: preserve existing files')
    except BaseException:
        os.chmod(WORK,old_mode);raise
    os.chmod(WORK,0)


def prepare():
    info=plistlib.loads(subprocess.check_output(['diskutil','info','-plist',str(VOLUME)]))
    if info.get('VolumeUUID')!=IDENTITY or info.get('MountPoint')!=str(VOLUME):
        raise RuntimeError('LACIE_VOLUME_IDENTITY_MISMATCH')
    if not IMAGE.exists():raise RuntimeError('LACIE_APFS_IMAGE_MISSING')
    WORK.mkdir(parents=True,exist_ok=True)
    if not os.path.ismount(WORK):
        guard_mountpoint()
        subprocess.run(['hdiutil','attach',str(IMAGE),'-mountpoint',str(WORK),'-nobrowse'],check=True)
    images=plistlib.loads(subprocess.check_output(['hdiutil','info','-plist']))['images']
    if not any(Path(i.get('image-path',''))==IMAGE and any(e.get('mount-point')==str(WORK) for e in i.get('system-entities',[])) for i in images):
        raise RuntimeError('LACIE_IMAGE_BACKING_MISMATCH')
    marker=WORK/'STORAGE_IDENTITY.json'
    if not marker.exists():marker.write_text(json.dumps(dict(lacie_volume_uuid=IDENTITY,image=str(IMAGE)),indent=2))
    configure()


if __name__=='__main__':
    prepare()
    if len(sys.argv)>1:
        os.execvpe(sys.argv[1],sys.argv[1:],os.environ)
    print(json.dumps(dict(status='READY',workspace=str(WORK),image=str(IMAGE),free_bytes=__import__('shutil').disk_usage(WORK).free)))
