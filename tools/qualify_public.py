#!/usr/bin/env python3
"""Read-only public source inventory and no-edit native export qualification.
No external scripts, hooks, plugins, project code or fabrication rules are run.
"""
from pathlib import Path, PurePosixPath
import argparse, collections, hashlib, json, os, shutil, subprocess, sys, warnings, zipfile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.validator import load, Unsupported, sha
from tools.preflight import verify_manifest
from gerbonara.rs274x import GerberFile

KINDS={'.kicad_pcb':'native_board','.kicad_pro':'native_project','.kicad_sch':'schematic','.sch':'schematic','.gbr':'gerber','.ger':'gerber','.gtl':'gerber','.gbl':'gerber','.gts':'mask','.gbs':'mask','.drl':'drill','.xln':'drill','.kicad_dru':'design_rules'}

def inventory(source):
    rows=[]
    for p in sorted(source.rglob('*')):
        if '.git' in p.relative_to(source).parts: continue
        if p.is_symlink(): raise ValueError('source symlinks require separate scoped qualification')
        if not p.is_file(): continue
        row={'path':p.relative_to(source).as_posix(),'sha256':sha(p),'bytes':p.stat().st_size,'kind':KINDS.get(p.suffix.lower(),'other')}
        if p.suffix.lower()=='.zip':
            with zipfile.ZipFile(p) as z:
                row['members']=[{'path':i.filename,'bytes':i.file_size,'sha256':hashlib.sha256(z.read(i)).hexdigest(),'kind':KINDS.get(PurePosixPath(i.filename).suffix.lower(),'other')} for i in z.infolist() if not i.is_dir()]
        rows.append(row)
    return rows

def command(argv,dest):
    env=dict(os.environ,KICAD_RUN_FROM_BUILD_DIR='1')
    p=subprocess.run(list(map(str,argv)),capture_output=True,text=True,env=env,timeout=240)
    dest.write_text('$ '+' '.join(map(str,argv))+'\n'+p.stdout+'\n'+p.stderr)
    return {'argv':list(map(str,argv)),'exit_code':p.returncode,'log':str(dest.relative_to(ROOT))}

def parser_probe(file):
    with warnings.catch_warnings(record=True) as ws:
        warnings.simplefilter('always')
        try:
            g=GerberFile.open(file)
            # Physical primitive fingerprint excludes timestamps and unqualified object attrs.
            # Region.attrs in Gerbonara 1.6.3 may be an uninitialized dataclass Field.
            canonical=json.dumps({'unit':str(g.unit),'role':g.file_attrs.get('.FileFunction'),'polarity':g.file_attrs.get('.FilePolarity'),'objects':[{'type':type(o).__name__,'primitives':[{'type':type(p).__name__,**vars(p)} for p in o.to_primitives()]} for o in g.objects]},sort_keys=True)
            result={'status':'PASS' if not ws else 'NOT_ESTABLISHED','objects':len(g.objects),'object_types':dict(collections.Counter(type(o).__name__ for o in g.objects)),
                'roles':g.file_attrs.get('.FileFunction'),'polarity':g.file_attrs.get('.FilePolarity'),
                'parsed_object_fingerprint':hashlib.sha256(canonical.encode()).hexdigest()}
        except Exception as exc: result={'status':'NOT_ESTABLISHED','error':str(exc)}
        result['warnings']=[str(w.message) for w in ws]
    return result

def qualify(name,cli,board,archive=None):
    verify_manifest()
    source=ROOT/'external/sources'/name
    dest=ROOT/'out/v1_5'/name;dest.mkdir(parents=True,exist_ok=True)
    if (dest/'qualification.json').exists(): raise SystemExit('Frozen report already exists; use a new run directory rather than overwriting')
    files=inventory(source)
    git=lambda *a:subprocess.check_output(['git','-C',str(source),*a],text=True).strip()
    report={'name':name,'origin':git('remote','get-url','origin'),'commit':git('rev-parse','HEAD'),
            'source_inventory':files,'source_worktree_before':git('status','--porcelain'),
            'kiCad_cli':str(cli),'cli_sha256':sha(cli),'environment':{'KICAD_RUN_FROM_BUILD_DIR':'1'},
            'license_declaration':{'status':'NOT_ESTABLISHED','evidence':[]},'commands':[],
            'cursor_review':{'status':'NOT_RUN','reason':'CHANNEL_UNAVAILABLE'}}
    for row in files:
        if Path(row['path']).name.lower().startswith(('readme','license','copying')):
            text=(source/row['path']).read_text(errors='replace')
            found=[line for line in text.splitlines() if any(t in line.lower() for t in ('license','licence','cc by-sa','cern-ohl'))]
            if found: report['license_declaration']['evidence'].append({'path':row['path'],'sha256':row['sha256'],'declaration_lines':found})
    if report['license_declaration']['evidence']:report['license_declaration']['status']='PASS_DECLARATION_RECORDED'
    work=dest/'work'; work.mkdir()
    if archive:
        with zipfile.ZipFile(source/archive) as z:
            for info in z.infolist():
                rel=PurePosixPath(info.filename)
                if rel.is_absolute() or '..' in rel.parts or (info.external_attr>>16)&0o170000==0o120000: raise ValueError('unsafe archive member')
                if info.is_dir() or '__MACOSX' in rel.parts: continue
                target=work.joinpath(*rel.parts);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(z.read(info))
    else:
        for row in files:
            target=work/row['path'];target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source/row['path'],target)
    native=(work/board).resolve()
    if not native.is_relative_to(work.resolve()): raise ValueError('selected board escapes copied work area')
    if not native.is_file(): raise ValueError('selected native board missing')
    report['selection']={'archive':archive,'board':board,'source_board_sha256':sha(native),'reason':'Smallest simple LED-strip variant for first native compatibility probe' if name=='GlowStitch' else 'Unpanelized native FPC board; custom rules and schematic retained in copied work area'}
    report['commands'].append(command([cli,'version'],dest/'version.log'))
    report['tool_version']=(dest/'version.log').read_text().splitlines()[1:]
    report['commands'].append(command([cli,'pcb','drc','--format','json','--severity-all','--exit-code-violations','-o',dest/'drc.json',native],dest/'drc.log'))
    rounds=[]
    for idx in (1,2):
        out=dest/f'export_{idx}';out.mkdir()
        c=command([cli,'pcb','export','gerbers','--layers','F.Cu,B.Cu,F.Mask,B.Mask,Edge.Cuts,F.SilkS,B.SilkS,F.Paste,B.Paste','--precision','6','--no-protel-ext','-o',str(out)+'/',native],dest/f'export_{idx}.log')
        report['commands'].append(c)
        # Drill compatibility is supplementary and not a V1 connectivity input.
        report['commands'].append(command([cli,'pcb','export','drill','-o',str(out)+'/',native],dest/f'drill_{idx}.log'))
        rounds.append({p.name:{'sha256':sha(p),'parser':parser_probe(p) if p.suffix=='.gbr' else None} for p in sorted(out.iterdir()) if p.is_file()})
    report['exports']=rounds
    parsed_pairs=[]
    for file,row in rounds[0].items():
        p=row['parser']; q=rounds[1].get(file,{}).get('parser')
        if p is not None:
            parsed_pairs.append(bool(q and p['status']=='PASS' and q['status']=='PASS' and p['parsed_object_fingerprint']==q['parsed_object_fingerprint']))
    report['no_edit_baseline']={'source_board_unchanged':sha(native)==report['selection']['source_board_sha256'],
        'native_load_and_export':'PASS' if all(c['exit_code']==0 for c in report['commands'] if 'gerbers' in c['argv']) and all(rounds) else 'NOT_ESTABLISHED',
        'repeated_parsed_objects':'PASS' if parsed_pairs and all(parsed_pairs) and set(rounds[0])==set(rounds[1]) else 'NOT_ESTABLISHED',
        'gui_open':'NOT_RUN','native_save_reload_roundtrip':'NOT_RUN',
        'limitation':'Two no-edit CLI loads/exports; parsed-object reproducibility is not independently qualified geometric equivalence or a native save/reload test.'}
    qualified=[]
    for file in sorted((dest/'export_1').glob('*.gbr')):
        role=next((r for r in ('F_Cu','F_Mask','Edge_Cuts') if file.stem.endswith('-'+r)),None)
        if role:
            try: load(file,role); result={'status':'PASS','limitation':'Import subset only; no public design policy or electrical acceptance established'}
            except (Unsupported,OSError,ValueError) as exc: result={'status':'NOT_ESTABLISHED','reason':str(exc)}
            qualified.append({'file':file.name,'role':role,**result})
    report['frozen_v1_readonly_import']=qualified
    report['public_electrical_and_manufacturing_acceptance']={'status':'NOT_ESTABLISHED','reason':'Frozen V1 policy, P1-P4 identity, aperture A1 and net intent apply only to the coupon. Public-design netlist/schematic availability does not establish a qualified independent oracle, coverlay rules, registration bounds or authorized edit scope.'}
    report['overall']='NOT_ESTABLISHED'
    report['source_immutable']=files==inventory(source) and report['source_worktree_before']==git('status','--porcelain')==''
    if not report['source_immutable']:report['overall']='FAIL'
    (dest/'qualification.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('name','commit','no_edit_baseline','frozen_v1_readonly_import','source_immutable','overall')},indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--name',choices=['GlowStitch','HALPI2-HDMI-FPC'],required=True);p.add_argument('--cli',type=Path,required=True);p.add_argument('--board',required=True);p.add_argument('--archive');a=p.parse_args()
    qualify(a.name,a.cli,a.board,a.archive)
