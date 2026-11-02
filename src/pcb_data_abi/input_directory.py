"""Explicit raw-input directory ingestion; stdlib only, no defaults or searches outside the supplied root."""
import hashlib,os,re,stat
from pathlib import Path

MAX_FILE=256*1024*1024

class IntakeAccessError(ValueError):
    """Retain the OS facts; EPERM alone does not identify TCC as the cause."""
    def __init__(self,error):
        self.details=dict(code='INPUT_DIRECTORY_ACCESS_FAILED',errno=error.errno,path=str(error.filename),os_message=error.strerror)
        super().__init__('INPUT_DIRECTORY_ACCESS_FAILED:'+str(self.details))

def walk_files(root):
    def failed(error):raise IntakeAccessError(error)from error
    try:
        for folder,dirs,files in os.walk(root,followlinks=False,onerror=failed):
            dirs.sort()
            for name in dirs:
                if (Path(folder)/name).is_symlink():raise ValueError('INPUT_DIRECTORY_SYMLINK_FORBIDDEN')
            for name in sorted(files):yield Path(folder)/name
    except OSError as error:raise IntakeAccessError(error)from error

def collect_raw(value):
    """Native-side complete inventory before any role is assigned."""
    if not value:raise ValueError('EXPLICIT_INPUT_DIRECTORY_REQUIRED')
    root=Path(value).expanduser().absolute()
    if '..'in root.parts or any(p.is_symlink()for p in(root,*root.parents)):raise ValueError('ACTUAL_INPUT_DIRECTORY_REQUIRED')
    try:
        if not stat.S_ISDIR(root.stat().st_mode):raise ValueError('ACTUAL_INPUT_DIRECTORY_REQUIRED')
    except OSError as error:raise IntakeAccessError(error)from error
    blobs={};ignored=[]
    for path in walk_files(root):
        relative=path.relative_to(root).as_posix()
        if path.name=='.DS_Store':
            if path.is_symlink():raise ValueError('INPUT_DIRECTORY_SYMLINK_FORBIDDEN')
            ignored.append(relative);continue
        try:blobs[relative]=regular_bytes(path)
        except OSError as error:raise IntakeAccessError(error)from error
    final={p.relative_to(root).as_posix()for p in walk_files(root)}
    if final!=set(blobs)|set(ignored):raise ValueError('INPUT_DIRECTORY_FILE_SET_CHANGED_DURING_INTAKE')
    return root,blobs,sorted(ignored)
ROLE_MAP={('Copper','L1','Top'):'F.Cu',('Soldermask','Top'):'F.Mask',('Soldermask','Bot'):'B.Mask',('Paste','Top'):'F.Paste',('Paste','Bot'):'B.Paste',('Legend','Top'):'F.SilkS',('Legend','Bot'):'B.SilkS',('Profile','NP'):'Edge.Cuts'}

def digest(blob):return hashlib.sha256(blob).hexdigest()

def layer_role(blob):
    roles=re.findall(rb'%TF\.FileFunction,([^*%]+)\*%',blob)
    if len(roles)!=1:raise ValueError('INPUT_DIRECTORY_GERBER_ROLE_REQUIRED')
    try:role=tuple(roles[0].decode('ascii').split(','))
    except UnicodeDecodeError as error:raise ValueError('INPUT_DIRECTORY_GERBER_ROLE_UNSUPPORTED')from error
    if len(role)==3 and role[0]=='Copper'and re.fullmatch(r'L[2-9][0-9]*|L1[0-9]+',role[1])and role[2]=='Bot':return 'B.Cu'
    if role not in ROLE_MAP:raise ValueError('INPUT_DIRECTORY_GERBER_ROLE_UNSUPPORTED:'+str(role))
    return ROLE_MAP[role]

def regular_bytes(path):
    path=Path(path)
    if any(p.is_symlink()for p in(path,*path.parents)):raise ValueError('INPUT_DIRECTORY_SYMLINK_FORBIDDEN')
    fd=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_NONBLOCK',0))
    with os.fdopen(fd,'rb')as stream:
        before=os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode)or not 0<before.st_size<=MAX_FILE:raise ValueError('INPUT_DIRECTORY_FILE_SIZE_OR_TYPE')
        blob=stream.read(MAX_FILE+1);after=os.fstat(stream.fileno())
    if (before.st_size,before.st_mtime_ns,before.st_ino)!=(after.st_size,after.st_mtime_ns,after.st_ino)or len(blob)!=before.st_size:raise ValueError('INPUT_DIRECTORY_CHANGED_DURING_INTAKE')
    return blob

def validate(manifest):
    v2=manifest.get('schema')=='pcb-raw-input-directory/2'
    keys={'schema','provided_directory','files','ignored_metadata'}|({'identification'}if v2 else set())
    if set(manifest)!=keys or manifest['schema']not in('pcb-raw-input-directory/1','pcb-raw-input-directory/2'):raise ValueError('INPUT_DIRECTORY_MANIFEST_INVALID')
    seen=set();roles=set();boards=0
    for row in manifest['files']:
        if set(row)!={'relative_path','kind','layer','sha256','bytes'}:raise ValueError('INPUT_DIRECTORY_MEMBER_INVALID')
        p=Path(row['relative_path'])
        if p.is_absolute()or not p.parts or '..'in p.parts or str(p)!=row['relative_path']or row['relative_path']in seen:raise ValueError('INPUT_DIRECTORY_MEMBER_PATH_INVALID')
        seen.add(row['relative_path'])
        if row['kind']=='kicad'and row['layer']is None:boards+=1
        elif v2 and row['kind']=='companion'and row['layer']is None:pass
        elif row['kind']=='gerber'and row['layer']in set(ROLE_MAP.values())|{'B.Cu'}:
            if row['layer']in roles:raise ValueError('INPUT_DIRECTORY_AMBIGUOUS_GERBER_ROLE:'+row['layer'])
            roles.add(row['layer'])
        else:raise ValueError('INPUT_DIRECTORY_MEMBER_KIND_INVALID')
        if type(row['bytes'])is not int or not 0<row['bytes']<=MAX_FILE or not re.fullmatch('[0-9a-f]{64}',row['sha256']):raise ValueError('INPUT_DIRECTORY_MEMBER_DIGEST_INVALID')
    if boards!=1:raise ValueError('INPUT_DIRECTORY_EXACTLY_ONE_KICAD_REQUIRED')
    if 'F.Cu'not in roles:raise ValueError('INPUT_DIRECTORY_FCU_GERBER_REQUIRED')
    if v2:
        proof=manifest['identification']
        if proof.get('schema')!='pcb-directory-identification/1'or proof.get('companion_policy')!='PRESERVE_EXCLUDED'or proof.get('registration_fit_used')is not False:raise ValueError('INPUT_DIRECTORY_IDENTIFICATION_INVALID')
        assigned={r['relative_path']:r['layer']for r in manifest['files']if r['kind']=='gerber'}
        if assigned!={r['relative_path']:r['layer']for r in proof['matches']}:raise ValueError('INPUT_DIRECTORY_IDENTIFICATION_BINDING_CHANGED')
        if sorted(r['relative_path']for r in manifest['files']if r['kind']=='companion')!=proof['excluded_companions']:raise ValueError('INPUT_DIRECTORY_COMPANION_BINDING_CHANGED')
        if proof.get('native_source_sha256')!=next(r['sha256']for r in manifest['files']if r['kind']=='kicad'):raise ValueError('INPUT_DIRECTORY_IDENTIFICATION_SOURCE_CHANGED')
    return manifest

def collect(value):
    root,blobs,ignored=collect_raw(value);rows=[]
    for relative,blob in blobs.items():
        if Path(relative).suffix.lower()=='.kicad_pcb':
            if not blob.lstrip().startswith(b'(kicad_pcb'):raise ValueError('INPUT_DIRECTORY_KICAD_FORMAT_REQUIRED')
            kind,layer='kicad',None
        else:kind,layer='gerber',layer_role(blob)
        rows.append(dict(relative_path=relative,kind=kind,layer=layer,sha256=digest(blob),bytes=len(blob)))
    return validate(dict(schema='pcb-raw-input-directory/1',provided_directory=str(root),files=sorted(rows,key=lambda r:r['relative_path']),ignored_metadata=sorted(ignored))),blobs

def verify_snapshot(manifest,root):
    validate(manifest);root=Path(root)
    actual={p.relative_to(root).as_posix()for p in walk_files(root)}
    if actual!={r['relative_path']for r in manifest['files']}:raise ValueError('INPUT_DIRECTORY_SNAPSHOT_FILE_SET_CHANGED')
    paths={}
    for row in manifest['files']:
        p=root/row['relative_path'];blob=regular_bytes(p)
        if digest(blob)!=row['sha256']or len(blob)!=row['bytes']:raise ValueError('INPUT_DIRECTORY_SNAPSHOT_CHANGED:'+row['relative_path'])
        if row['kind']=='gerber'and manifest['schema']=='pcb-raw-input-directory/1'and layer_role(blob)!=row['layer']:raise ValueError('INPUT_DIRECTORY_ROLE_CHANGED')
        if row['kind']!='companion':paths['kicad'if row['kind']=='kicad'else row['layer']]=p
    return paths

