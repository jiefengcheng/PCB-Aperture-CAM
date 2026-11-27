"""Explicit workspace adapter for the sealed standalone cleanup package.

The ordinary checkout still requires its LaCie mount. An environment variable
alone cannot enable the portable profile. Nothing selects a fallback directory.
"""
import hashlib
import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import tempfile
import uuid

ROOT=Path(__file__).resolve().parents[1]
PROFILE={'schema':'portable-copper-cleanup/2','architecture':'arm64','minimum_macos':'15.0',
         'workspace':'EXPLICIT_USER_SELECTED_APFS_DIRECTORY','operation':'TRIM_THEN_T04'}
MARKER='CLEANUP_WORKSPACE.json'
_binding=None


def is_portable():
    path=ROOT/'PORTABLE_PACKAGE.json'
    if not path.exists():
        if os.environ.get('PCB_CLEANUP_WORKSPACE'):raise ValueError('PORTABLE_PACKAGE_PROFILE_REQUIRED')
        return False
    if path.is_symlink() or json.loads(path.read_bytes())!=PROFILE:
        raise ValueError('PORTABLE_PACKAGE_PROFILE_CHANGED')
    return True


def _volume(root):
    mount=root
    while not mount.is_mount():
        if mount.parent==mount:raise ValueError('WORKSPACE_VOLUME_NOT_ESTABLISHED')
        mount=mount.parent
    info=plistlib.loads(subprocess.check_output(['/usr/sbin/diskutil','info','-plist',str(mount)]))
    if 'APFS' not in info.get('FilesystemType','').upper()+info.get('FileSystemPersonality','').upper():
        raise ValueError('PORTABLE_WORKSPACE_REQUIRES_APFS')
    if not info.get('VolumeUUID') or info.get('ReadOnlyVolume'):
        raise ValueError('WRITABLE_VOLUME_IDENTITY_REQUIRED')
    return mount,info['VolumeUUID']


def initialize(root):
    if not is_portable():raise ValueError('PORTABLE_PACKAGE_PROFILE_REQUIRED')
    root=Path(root)
    if not root.is_absolute():raise ValueError('EXPLICIT_ABSOLUTE_WORKSPACE_REQUIRED')
    root=root.resolve(strict=True)
    if not root.is_dir() or root.is_relative_to(ROOT.parent):
        raise ValueError('SELECT_A_SEPARATE_WORKSPACE_DIRECTORY')
    mount,volume=_volume(root)
    if shutil.disk_usage(root).free<5*1024**3:raise ValueError('WORKSPACE_REQUIRES_5_GIB_FREE')
    marker=root/MARKER
    expected=dict(schema='portable-copper-workspace/1',volume_uuid=volume)
    if marker.exists():
        value=json.loads(marker.read_bytes())
        if marker.is_symlink() or any(value.get(k)!=v for k,v in expected.items()) or not value.get('workspace_id'):
            raise ValueError('PORTABLE_WORKSPACE_IDENTITY_CHANGED')
    else:
        value=dict(expected,workspace_id=uuid.uuid4().hex)
        with marker.open('x') as stream:
            json.dump(value,stream,sort_keys=True);stream.flush();os.fsync(stream.fileno())
    for name in ('tmp','cache','large_copper_jobs','shared_copper_context','native_sessions'):
        path=root/name
        if path.is_symlink():raise ValueError('WORKSPACE_DIRECTORY_SYMLINK_REJECTED')
        path.mkdir(exist_ok=True)
    return dict(workspace=str(root),volume_uuid=volume,workspace_id=value['workspace_id'],mount=str(mount))


def portable_workspace():
    global _binding
    value=os.environ.get('PCB_CLEANUP_WORKSPACE')
    if not value or not Path(value).is_absolute():raise ValueError('EXPLICIT_PORTABLE_WORKSPACE_REQUIRED')
    root=Path(value).resolve(strict=True)
    raw=(root/MARKER).read_bytes()
    if _binding is None or _binding['root']!=root:
        mount,volume=_volume(root)
        marker=json.loads(raw)
        if marker.get('schema')!='portable-copper-workspace/1' or marker.get('volume_uuid')!=volume or not marker.get('workspace_id'):
            raise ValueError('PORTABLE_WORKSPACE_IDENTITY_CHANGED')
        _binding=dict(root=root,mount=mount,device=mount.stat().st_dev,sha256=hashlib.sha256(raw).hexdigest())
    b=_binding
    if (not b['mount'].is_mount() or b['mount'].stat().st_dev!=b['device'] or
            root.stat().st_dev!=b['device'] or hashlib.sha256(raw).hexdigest()!=b['sha256'] or (root/MARKER).is_symlink()):
        raise ValueError('PORTABLE_WORKSPACE_UNAVAILABLE_NO_FALLBACK')
    if shutil.disk_usage(root).free<5*1024**3:raise ValueError('WORKSPACE_REQUIRES_5_GIB_FREE')
    return root


def workspace_root():
    if is_portable():return portable_workspace()
    work=(ROOT/'out/lacie_work').resolve()
    if not work.is_mount():raise ValueError('LACIE_OUTPUT_REQUIRED')
    return work


def configure_portable():
    root=portable_workspace()
    tmp=root/'tmp'
    if not tmp.is_dir() or tmp.is_symlink():raise ValueError('PORTABLE_WORKSPACE_NOT_INITIALIZED')
    os.environ.update(TMPDIR=str(tmp),TMP=str(tmp),TEMP=str(tmp),PYTHONDONTWRITEBYTECODE='1',
                      PYTHONNOUSERSITE='1',XDG_CACHE_HOME=str(root/'cache'))
    tempfile.tempdir=str(tmp)
    return root
