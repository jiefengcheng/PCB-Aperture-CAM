"""Build an offline Apple-silicon cleanup app and DMG on prepared LaCie storage.

Only this project's code/contracts/synthetic assets and its installed runtime
are copied. Client sources, jobs, caches and previous results are excluded.
"""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import plistlib
import re
import shutil
import subprocess
import sys
import sysconfig
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(argv,**kwargs):
    result=subprocess.run([str(x) for x in argv],capture_output=True,text=True,**kwargs)
    if result.returncode:raise RuntimeError(json.dumps(dict(argv=list(map(str,argv)),stdout=result.stdout,stderr=result.stderr)))
    return result.stdout


def ignored(directory,names):
    return {n for n in names if n in ('__pycache__','.DS_Store') or n.endswith(('.pyc','.pyo'))}


def macho(path):
    if not path.is_file() or path.is_symlink():return False
    with path.open('rb') as stream:magic=stream.read(4)
    return magic in (b'\xcf\xfa\xed\xfe',b'\xce\xfa\xed\xfe',b'\xfe\xed\xfa\xcf',b'\xca\xfe\xba\xbe',b'\xbe\xba\xfe\xca')


def dependencies(path):
    result=[]
    for block in run(['/usr/bin/otool','-l',path]).split('Load command ')[1:]:
        if not re.search(r'\bcmd LC_(?:LOAD_DYLIB|LOAD_WEAK_DYLIB|REEXPORT_DYLIB|LOAD_UPWARD_DYLIB)\b',block):continue
        match=re.search(r'\n\s+name (.+?) \(offset ',block)
        if match:result.append(match[1])
    return result


def make_runtime(app,base,site):
    framework=app/'Contents/Frameworks/Python.framework'
    version=framework/'Versions/3.14';version.mkdir(parents=True)
    (version/'bin').mkdir();shutil.copy2(base/'bin/python3.14',version/'bin/python3.14')
    shutil.copy2(base/'Python',version/'Python')
    def stdlib_ignore(directory,names):
        rejected=ignored(directory,names)
        if Path(directory)==base/'lib/python3.14':rejected|=set(names)&{'test','site-packages','idlelib','ensurepip','tkinter','turtledemo'}
        if Path(directory)==base/'lib/python3.14/lib-dynload':rejected|={n for n in names if n.startswith('_tkinter.')}
        return rejected
    shutil.copytree(base/'lib',version/'lib',ignore=stdlib_ignore,symlinks=True)
    shutil.copytree(site,version/'lib/python3.14/site-packages',ignore=ignored,symlinks=True)
    # Runtime package managers and test runners are not installation dependencies.
    for pattern in ('pip','pip-*.dist-info','pytest','_pytest','pytest-*.dist-info'):
        for path in (version/'lib/python3.14/site-packages').glob(pattern):
            if path.is_dir():shutil.rmtree(path)
    (version/'Resources').mkdir()
    shutil.copy2(base/'Resources/Info.plist',version/'Resources/Info.plist')
    shutil.copytree(base/'Resources/Python.app',version/'Resources/Python.app',ignore=ignored,symlinks=True)
    (framework/'Versions/Current').symlink_to('3.14')
    (framework/'Python').symlink_to('Versions/Current/Python')
    (framework/'Resources').symlink_to('Versions/Current/Resources')
    original_geos=site/'shapely/.dylibs/libgeos_c.1.19.2.dylib'
    bundled_geos=version/'lib/python3.14/site-packages/shapely/.dylibs/libgeos_c.1.19.2.dylib'
    geos_sha=sha(original_geos)
    mutations=[]
    # Rewrite CPython's own absolute framework dependencies. Wheel geometry
    # libraries stay byte-identical, including their existing signatures.
    for path in sorted(version.rglob('*')):
        if not macho(path):continue
        replacements=[]
        for dependency in set(dependencies(path)):
            if dependency.startswith(str(base)+'/'):
                target=version/dependency[len(str(base))+1:]
                if not target.exists():raise ValueError('BUNDLED_PYTHON_DEPENDENCY_MISSING:'+str(target))
                replacements+=['-change',dependency,'@loader_path/'+os.path.relpath(target,path.parent)]
        if path==version/'Python':replacements+=['-id','@rpath/Python.framework/Versions/3.14/Python']
        if replacements:
            run(['/usr/bin/install_name_tool',*replacements,path])
            run(['/usr/bin/codesign','--force','--sign','-',path]);mutations.append(str(path.relative_to(app)))
    run(['/usr/bin/codesign','--force','--sign','-',version/'Resources/Python.app'])
    run(['/usr/bin/codesign','--force','--sign','-',framework])
    if sha(bundled_geos)!=geos_sha:raise ValueError('PINNED_GEOS_BYTES_CHANGED_DURING_PACKAGING')
    return version,dict(relocated_binaries=mutations,geos_c_sha256=geos_sha)


def audit_native(app):
    inventory={};external=[]
    for path in sorted(app.rglob('*')):
        if not macho(path):continue
        deps=dependencies(path)
        for dep in deps:
            if dep.startswith('/') and not dep.startswith(('/usr/lib/','/System/Library/')):
                external.append(dict(binary=str(path.relative_to(app)),dependency=dep))
        inventory[str(path.relative_to(app))]=dict(sha256=sha(path),dependencies=deps)
    if external:raise ValueError('NONPORTABLE_NATIVE_DEPENDENCIES:'+json.dumps(external))
    return inventory


def build(output,*,build_workspace=None):
    from src.gerber_u05.workspace import configure
    from src.cleanup_runtime import PROFILE
    from tools.preflight import verify_manifest
    if build_workspace is None:
        work=configure().resolve()
    else:
        # Explicit standalone build adapter for another Mac. The normal
        # checkout still uses configure() and never selects a fallback.
        from src.cleanup_runtime import _volume
        work=Path(build_workspace)
        if not work.is_absolute():raise ValueError('EXPLICIT_ABSOLUTE_BUILD_WORKSPACE_REQUIRED')
        work=work.resolve(strict=True)
        if not work.is_dir() or work.is_relative_to(ROOT):raise ValueError('SEPARATE_BUILD_WORKSPACE_REQUIRED')
        _volume(work)
        if shutil.disk_usage(work).free<5*1024**3:raise ValueError('WORKSPACE_REQUIRES_5_GIB_FREE')
        tmp=work/'tmp';tmp.mkdir(exist_ok=True)
        if tmp.is_symlink():raise ValueError('BUILD_TMP_SYMLINK_REJECTED')
        os.environ.update(TMPDIR=str(tmp),TMP=str(tmp),TEMP=str(tmp),
                          XDG_CACHE_HOME=str(work/'cache'),PYTHONDONTWRITEBYTECODE='1')
        tempfile.tempdir=str(tmp)
    output=output.resolve()
    if not output.is_relative_to(work) or output==work:raise ValueError('BUILD_OUTPUT_OUTSIDE_VERIFIED_WORKSPACE')
    if platform.machine()!='arm64':raise ValueError('APPLE_SILICON_BUILD_REQUIRED')
    if sys.version_info[:2]!=(3,14):raise ValueError('CPYTHON_314_FRAMEWORK_BUILD_REQUIRED')
    assets=verify_manifest()
    output.mkdir(parents=True,exist_ok=False)
    stage=output/'image';stage.mkdir()
    app=stage/'Copper Trimming.app'
    resources=app/'Contents/Resources';resources.mkdir(parents=True)
    (app/'Contents/MacOS').mkdir()
    payload=resources/'payload';payload.mkdir()
    shutil.copytree(ROOT/'src',payload/'src',ignore=ignored)
    shutil.copytree(ROOT/'contracts',payload/'contracts',ignore=ignored)
    shutil.copytree(ROOT/'assets',payload/'assets',ignore=ignored)
    (payload/'tools').mkdir()
    for path in sorted((ROOT/'tools').rglob('*.py')):
        if '__pycache__' in path.parts:continue
        target=payload/'tools'/path.relative_to(ROOT/'tools');target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,target)
    (payload/'PORTABLE_PACKAGE.json').write_text(json.dumps(PROFILE,sort_keys=True))
    files={str(p.relative_to(payload)):sha(p) for p in sorted(payload.rglob('*')) if p.is_file()}
    (payload/'PAYLOAD_MANIFEST.json').write_text(json.dumps(dict(schema='portable-cleanup-payload/1',files=files),sort_keys=True))
    base=Path(sys.base_prefix);site=Path(sysconfig.get_paths()['purelib'])
    version,runtime=make_runtime(app,base,site)
    (payload/'.venv/bin').mkdir(parents=True)
    (payload/'.venv/bin/python').symlink_to(os.path.relpath(version/'bin/python3.14',payload/'.venv/bin'))
    licenses=resources/'Third Party Notices';licenses.mkdir()
    shutil.copy2(base/'Resources/English.lproj/Documentation/_sources/license.rst.txt',licenses/'Python-license.txt')
    packages={d.metadata['Name']:d.version for d in importlib.metadata.distributions(path=[str(site)]) if d.metadata['Name'].lower() not in ('pip','pytest')}
    (licenses/'PACKAGE_VERSIONS.json').write_text(json.dumps(packages,sort_keys=True,indent=2))
    viewer_work=work/'viewer'
    # A clean clone has no pre-existing Swift build/cache directories.
    for name in ('tmp','cache/clang','cache/swift','cache/swiftpm','config','security'):
        (viewer_work/name).mkdir(parents=True,exist_ok=True)
    env=dict(os.environ,TMPDIR=str(viewer_work/'tmp'),CLANG_MODULE_CACHE_PATH=str(viewer_work/'cache/clang'),
        SWIFTPM_MODULECACHE_OVERRIDE=str(viewer_work/'cache/swift'),SWIFT_MODULECACHE_PATH=str(viewer_work/'cache/swift'),
        XDG_CACHE_HOME=str(viewer_work/'cache'))
    command=['/usr/bin/swift','build','--package-path',ROOT/'viewer','--scratch-path',viewer_work/'build',
             '--cache-path',viewer_work/'cache/swiftpm','--config-path',viewer_work/'config',
             '--security-path',viewer_work/'security','--disable-sandbox','-c','release']
    (output/'swift-build.log').write_text(run(command,env=env))
    binary=Path(run([*command,'--show-bin-path'],env=env).strip())
    shutil.copy2(binary/'GerberViewer',app/'Contents/MacOS/CopperTrimming')
    shutil.copytree(binary/'GerberViewer_GerberViewer.bundle',resources/'GerberViewer_GerberViewer.bundle')
    info=dict(CFBundleIdentifier='local.pcbcam.coppertrimming',CFBundleName='Copper Trimming',CFBundleDisplayName='Copper Trimming',
        CFBundleExecutable='CopperTrimming',CFBundlePackageType='APPL',CFBundleVersion='20261123.3',
        CFBundleShortVersionString='0.2.0',LSMinimumSystemVersion='15.0',LSArchitecturePriority=['arm64'],
        NSHighResolutionCapable=True,CleanupPortable=True)
    (app/'Contents/Info.plist').write_bytes(plistlib.dumps(info))
    readme='''Copper Trimming — Apple silicon / macOS 15 or newer

Open Copper Trimming.app directly, or copy it to a folder on the other Mac.
Choose an APFS work folder with at least 5 GiB free. Click “Run large copper
trimming…” and select a supported positive-copper Gerber source.

Python, the geometry libraries and the native viewer are included. No Python,
KiCad, Xcode, package installation, network connection or original checkout is
needed. The work folder is explicit; no missing-drive fallback is used.

One fixed operation considers straight flanks, source-supported circular voids
at exposed native pads and round trace ends, causing-pad noise, compound source
draws, proven redundant endpoint flashes and the separate shallow-edge rule.
Unqualified findings remain unresolved; declared and unrelated terminals stay
protected. Rectangular bumps are ignored. All family/rule filters affect SAVED
viewing only. Grey/pink views and Play never run treatment.
No growth, additions, rerouting, Gerber export or manufacturing approval.

Keep the chosen work folder in place: saved evidence uses absolute paths.
The app itself can move. Client inputs, historical jobs and caches are excluded.
The synthetic coupon assets required by integrity checks are included.

CLI: "./Run Trimming.command" --workspace /ABSOLUTE/WORK/FOLDER init
     "./Run Trimming.command" --workspace /ABSOLUTE/WORK/FOLDER run --source /ABSOLUTE/source.gbr --prepare-display
     "./Run Trimming.command" --workspace /ABSOLUTE/WORK/FOLDER status --job /ABSOLUTE/JOB

The app is locally ad-hoc signed, not Developer ID notarized. No security
settings are changed by this package. Physical testing on another Mac remains
separate from relocation tests on the build Mac.
'''
    (stage/'READ ME.txt').write_text(readme)
    wrapper='''#!/bin/sh
set -eu
TASK_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
TASK_APP="$TASK_DIR/Copper Trimming.app"
export PYTHONHOME="$TASK_APP/Contents/Frameworks/Python.framework/Versions/3.14"
export PYTHONPATH="$TASK_APP/Contents/Resources/payload"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
unset __PYVENV_LAUNCHER__
exec "$PYTHONHOME/bin/python3.14" -B "$PYTHONPATH/tools/portable_cleanup.py" "$@"
'''
    (stage/'Run Trimming.command').write_text(wrapper);(stage/'Run Trimming.command').chmod(0o755)
    run(['/usr/bin/codesign','--force','--sign','-',app])
    (output/'native-dependencies.json').write_text(json.dumps(audit_native(app),sort_keys=True,indent=2))
    run(['/usr/bin/codesign','--verify','--deep','--strict',app])
    manifest=dict(schema='portable-copper-build/1',app=str(app),architecture='arm64',minimum_macos='15.0',
        assets_verified=assets,payload_files=files,runtime=runtime,packages=packages,
        signing='AD_HOC_LOCAL_NOT_NOTARIZED',client_data_included=False,
        app_signature=run(['/usr/bin/codesign','-dv','--verbose=2',app]) if False else 'verified --deep --strict',
        build_workspace=str(work),workspace_selection='EXPLICIT_APFS' if build_workspace is not None else 'CHECKOUT_LACIE')
    (output/'BUILD.json').write_text(json.dumps(manifest,sort_keys=True,indent=2))
    qa=output/'qa';qa.mkdir();(qa/'work').mkdir()
    offline_env={'PATH':'/usr/bin:/bin:/usr/sbin:/sbin'}
    cli=[stage/'Run Trimming.command','--workspace',qa/'work']
    (qa/'INIT.json').write_text(run([*cli,'init'],env=offline_env))
    (qa/'SELF_CHECK.json').write_text(run([*cli,'self-check'],env=offline_env))
    check=json.loads((qa/'SELF_CHECK.json').read_bytes())
    if check['exact_distance_mm']!=1.0 or not Path(check['prefix']).is_relative_to(app):
        raise ValueError('BUNDLED_RUNTIME_QUALIFICATION_FAILED')
    if any(not Path(p).is_relative_to(app) for p in check['loaded_extensions']):
        raise ValueError('BUNDLED_EXTENSION_ESCAPED_PACKAGE')
    # Building the DMG is a separate explicit finalize step after relocated tests.
    return manifest


def seal(output):
    """Create and verify a new image; never overwrite an existing delivery."""
    image=output/'Copper_Trimming_0.2.0.dmg'
    if image.exists():raise ValueError('IMMUTABLE_DMG_ALREADY_EXISTS')
    creation=run(['/usr/bin/hdiutil','create','-volname','Copper Trimming 0.2.0',
                  '-srcfolder',output/'image','-format','UDZO',image])
    (output/'dmg-create.log').write_text(creation)
    verification=run(['/usr/bin/hdiutil','verify',image])
    (output/'dmg-verify.log').write_text(verification)
    receipt=dict(schema='portable-copper-dmg/1',file=image.name,sha256=sha(image),
                 bytes=image.stat().st_size,verification='HDIUTIL_VERIFY_PASS',
                 build_sha256=sha(output/'BUILD.json'),
                 bit_identical_to_historical_image='NOT_REQUIRED',
                 native_viewer_baseline_reproduction='NOT_RUN_FOR_THIS_BUILD')
    (output/'DMG.json').write_text(json.dumps(receipt,sort_keys=True,indent=2))
    return receipt


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--build-workspace',type=Path,help='Existing separate APFS directory for an explicit standalone build on another Mac; default retains the checkout LaCie policy')
    parser.add_argument('--seal-dmg',action='store_true',help='After app/runtime checks, create and verify a new read-only DMG')
    args=parser.parse_args();manifest=build(args.output_dir,build_workspace=args.build_workspace)
    if args.seal_dmg:manifest['dmg']=seal(args.output_dir.resolve())
    print(json.dumps(manifest,sort_keys=True))


if __name__=='__main__':main()
