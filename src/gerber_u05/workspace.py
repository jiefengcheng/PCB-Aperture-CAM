"""Use the already prepared, identity-checked LaCie image; never fall back."""
import json,os,plistlib,shutil,subprocess,tempfile
from pathlib import Path
IMAGE=Path('/Volumes/LaCie/PCB_Aperture_CAM_Workspace/PCB_CAM_Work.sparsebundle')
IDENTITY='5E178CE8-A7FF-37D9-B307-F0D08FBB4D14'
def configure():
 images=plistlib.loads(subprocess.check_output(['hdiutil','info','-plist']))['images']
 mounts=[Path(e['mount-point'])for i in images if Path(i.get('image-path',''))==IMAGE for e in i.get('system-entities',[])if e.get('mount-point')]
 if len(mounts)!=1:raise RuntimeError('PREPARED_LACIE_IMAGE_REQUIRED_NO_FALLBACK')
 work=mounts[0];marker=json.loads((work/'STORAGE_IDENTITY.json').read_bytes())
 if not os.path.ismount(work)or marker.get('lacie_volume_uuid')!=IDENTITY or Path(marker.get('image',''))!=IMAGE:raise RuntimeError('LACIE_IDENTITY_MISMATCH')
 if min(shutil.disk_usage(work).free,shutil.disk_usage(IMAGE.parent).free)<5*1024**3:raise RuntimeError('LACIE_LOW_SPACE')
 tmp=work/'tmp';tmp.mkdir(exist_ok=True);os.environ.update(TMPDIR=str(tmp),TMP=str(tmp),TEMP=str(tmp),PYTHONDONTWRITEBYTECODE='1',XDG_CACHE_HOME=str(work/'cache'));tempfile.tempdir=str(tmp)
 return work
