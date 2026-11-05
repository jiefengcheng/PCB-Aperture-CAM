"""Differential source-bound controls: path preparation cannot cache disk state."""
from pathlib import Path
import os,sys,importlib.util
import pytest
from src.stage_abi.store import ArtifactStore
from src.u05_board.store import ReadOnlyStore
import src.u05_board.store as new_module

ORACLE=Path(__file__).resolve().parent/'fixtures/preparation_readonly_original.py'
spec=importlib.util.spec_from_file_location('retained_pathname_oracle',ORACLE)
old_module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=old_module;spec.loader.exec_module(old_module)
OldReader=old_module.ReadOnlyStore

def outcome(reader,reference,kind='geometry'):
    try:return ('PASS',reader.get(reference,kind=kind))
    except Exception as error:return ('FAIL',type(error).__name__,getattr(error,'code',None),str(error),getattr(error.__cause__,'errno',None))

def fixture(tmp_path):
    store=ArtifactStore(tmp_path/'store');ref=store.put('geometry',b'qualified-body')
    return store,ref,store.root/'artifacts'/ref['artifact_id']

@pytest.mark.parametrize('case',['valid','missing','corrupt','wrong-sha','wrong-kind','invalid-id','symlink','directory','fifo'])
def test_differential_file_and_reference_guards(tmp_path,case):
    store,ref,path=fixture(tmp_path);old=OldReader(store.root);new=ReadOnlyStore(store.root);kind='geometry'
    if case=='missing':path.unlink()
    elif case=='corrupt':path.write_bytes(b'changed')
    elif case=='wrong-sha':ref=dict(ref,sha256='0'*64)
    elif case=='wrong-kind':kind='scene'
    elif case=='invalid-id':ref=dict(ref,artifact_id='../'+ref['artifact_id'])
    elif case in ['symlink','directory','fifo']:
        path.unlink()
        if case=='symlink':
            target=tmp_path/'target';target.write_bytes(b'qualified-body');path.symlink_to(target)
        elif case=='directory':path.mkdir()
        else:os.mkfifo(path)
    a=outcome(old,ref,kind);b=outcome(new,ref,kind)
    assert a==b
    assert (a[0]=='PASS')==(case=='valid')

@pytest.mark.parametrize('change',['overwrite','replace-file','replace-artifacts-dir','replace-root-dir','parent-symlink'])
def test_replacements_are_observed_each_access(tmp_path,change):
    store,ref,path=fixture(tmp_path);old=OldReader(store.root);new=ReadOnlyStore(store.root)
    assert outcome(old,ref)==outcome(new,ref)==('PASS',b'qualified-body')
    if change=='overwrite':path.write_bytes(b'changed')
    elif change=='replace-file':
        path.rename(tmp_path/'retained-old-file');path.write_bytes(b'changed')
    elif change=='replace-artifacts-dir':
        path.parent.rename(tmp_path/'retained-artifacts');path.parent.mkdir();path.write_bytes(b'changed')
    else:
        store.root.rename(tmp_path/'retained-root')
        if change=='parent-symlink':
            target=tmp_path/'replacement-root';target.mkdir();store.root.symlink_to(target,target_is_directory=True)
        else:store.root.mkdir()
        path.parent.mkdir();path.write_bytes(b'changed')
    a=outcome(old,ref);b=outcome(new,ref)
    assert a==b and a[0]=='FAIL'

@pytest.mark.parametrize('case',['missing','symlink'])
def test_root_construction_guards_unchanged(tmp_path,case):
    root=tmp_path/'root'
    if case=='symlink':
        target=tmp_path/'target';target.mkdir();root.symlink_to(target,target_is_directory=True)
    for cls in [OldReader,ReadOnlyStore]:
        with pytest.raises(ValueError,match='U05_RETAINED_STORE_REQUIRED'):cls(root)

def test_public_root_reassignment_retains_original_behavior(tmp_path):
    store,ref,_=fixture(tmp_path);other=ArtifactStore(tmp_path/'other');next_ref=other.put('geometry',b'other-body')
    for cls in [OldReader,ReadOnlyStore]:
        reader=cls(store.root);assert outcome(reader,ref)==('PASS',b'qualified-body')
        reader.root=other.root;assert outcome(reader,next_ref)==('PASS',b'other-body')
        reader.root=store.root;assert outcome(reader,ref)==('PASS',b'qualified-body')

def test_relative_root_tracks_current_directory(tmp_path,monkeypatch):
    first=tmp_path/'first';second=tmp_path/'second';first.mkdir();second.mkdir()
    store=ArtifactStore(first/'store');ref=store.put('geometry',b'qualified-body')
    destination=second/'store/artifacts';destination.mkdir(parents=True);(destination/ref['artifact_id']).write_bytes(b'changed')
    monkeypatch.chdir(first);old=OldReader('store');new=ReadOnlyStore('store')
    assert outcome(old,ref)==outcome(new,ref)==('PASS',b'qualified-body')
    monkeypatch.chdir(second);a=outcome(old,ref);b=outcome(new,ref);assert a==b and a[0]=='FAIL'

def test_each_access_keeps_open_fstat_read_and_hash(tmp_path,monkeypatch):
    store,ref,path=fixture(tmp_path)
    original_open=os.open;original_fstat=os.fstat;original_fdopen=os.fdopen
    def traced(module,cls):
        reader=cls(store.root);events=[];original_digest=module.digest
        def opened(p,flags,*args,**kwargs):events.append(('open',os.fspath(p),flags));return original_open(p,flags,*args,**kwargs)
        def stated(fd):events.append(('fstat',));return original_fstat(fd)
        class Stream:
            def __init__(self,stream):self.stream=stream
            def __enter__(self):self.stream.__enter__();return self
            def __exit__(self,*args):return self.stream.__exit__(*args)
            def fileno(self):return self.stream.fileno()
            def read(self,*args,**kwargs):events.append(('read',));return self.stream.read(*args,**kwargs)
        def fdopened(fd,mode):events.append(('fdopen',mode));return Stream(original_fdopen(fd,mode))
        def hashed(body):events.append(('sha256',len(body)));return original_digest(body)
        with monkeypatch.context() as patch:
            patch.setattr(os,'open',opened);patch.setattr(os,'fstat',stated);patch.setattr(os,'fdopen',fdopened);patch.setattr(module,'digest',hashed)
            assert reader.get(ref,kind='geometry')==reader.get(ref,kind='geometry')==b'qualified-body'
        return events
    old=traced(old_module,OldReader);new=traced(new_module,ReadOnlyStore)
    flags=os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK
    expected=[('open',str(path),flags),('fdopen','rb'),('fstat',),('read',),('sha256',14)]*2
    assert old==new==expected

def test_read_only_write_prohibition_unchanged(tmp_path):
    store,_,_=fixture(tmp_path)
    for cls in [OldReader,ReadOnlyStore]:
        with pytest.raises(ValueError,match='U05_PREDECESSOR_WRITE_FORBIDDEN'):cls(store.root).put('geometry',b'new')
