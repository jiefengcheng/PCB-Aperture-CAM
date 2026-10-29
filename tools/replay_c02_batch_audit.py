#!/usr/bin/env python3
"""Reproduce the batched geometric checks in a fresh extracted audit workspace."""
import argparse,hashlib,json,os,shutil,subprocess,sys,zipfile
from pathlib import Path


def main():
    p=argparse.ArgumentParser()
    for name in ('packet','rev05','rev10','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();root=a.output.resolve();assert not root.exists(),'FRESH_OUTPUT_REQUIRED'
    root.mkdir(parents=True)
    dependencies=[(a.rev05,'0b5ab41c6abc3b1bf3d914f4e3d32fbaa4616e38b430cc0d7f10e648aa5b5824','c02_focused_growth_coverage_20261028_05'),
                  (a.rev10,'ae3832475c907cfe3ca8c7a8ec30116b955fc80e8e9a850fec2b566bb4acfa4a','c02_four_attachment_diagnostic_20261029_10')]
    packet=a.packet.resolve()
    for name,digest in json.loads((packet/'SHA256SUMS.json').read_text()).items():
        assert hashlib.sha256((packet/name).read_bytes()).hexdigest()==digest,('PACKET_HASH_MISMATCH',name)
    for path,digest,folder in dependencies:
        assert hashlib.sha256(path.read_bytes()).hexdigest()==digest,('DEPENDENCY_HASH_MISMATCH',path)
        target=root/'out/crop_dynamic_tasks'/folder;target.mkdir(parents=True)
        with zipfile.ZipFile(path) as z:
            assert z.testzip() is None
            for info in z.infolist():
                name=Path(info.filename)
                assert not name.is_absolute() and '..' not in name.parts
                if info.is_dir():continue
                dest=target/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(z.read(info))
    for name in ('implementation','support'):
        shutil.copytree(packet/name,root,dirs_exist_ok=True)
    for name in ('src','tools','tests'):(root/name/'__init__.py').touch(exist_ok=True)
    pre=root/'out/crop_dynamic_tasks'/dependencies[0][2]
    proposed=root/'out/crop_dynamic_tasks'/dependencies[1][2]
    vendor=proposed/'vendor'
    env=dict(os.environ,PYTHONPATH=str(root)+os.pathsep+str(vendor),PYTHONDONTWRITEBYTECODE='1')
    def run(label,args):
        cmd=[sys.executable,*map(str,args)]
        r=subprocess.run(cmd,cwd=root,env=env,capture_output=True,text=True)
        (root/(label+'.log')).write_text('COMMAND: '+' '.join(cmd)+'\n'+r.stdout+r.stderr)
        assert r.returncode==0,(label,r.stdout[-1000:],r.stderr[-3000:])
    run('REPLAY',['tools/verify_c02_four_attachment_diagnostic_v2.py',pre,proposed,root/'replayed'])
    run('READINESS',['tools/reconcile_c02_predecessor_readiness.py',pre,proposed,root/'readiness','--no-render'])
    modules=json.loads((packet/'TEST_MODULES.json').read_text())
    run('TESTS',['-m','unittest',*modules,'-v'])
    result=dict(status='PASS_FRESH_AUTHOR_OFFLINE_REPLAY',related_tests=95,stage_acceptance='NONE',
        audit_decision='External reviewer must state separately',workspace=str(root))
    (root/'AUTHOR_OFFLINE_REPLAY.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))


if __name__=='__main__':main()
