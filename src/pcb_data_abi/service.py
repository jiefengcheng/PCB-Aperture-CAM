"""Source-bound C01 file operations, raw native export evidence and rereads."""
from collections import Counter
from datetime import datetime,timezone
import hashlib,json,os,re,subprocess
from importlib.metadata import version as package_version
from pathlib import Path
import sexpdata
from shapely import from_wkb,to_wkb,set_precision
from shapely.ops import unary_union
from gerbonara import graphic_objects as go
from src.stage_abi.store import ArtifactStore,canonical,digest
from src.native_inventory import geometry
from . import ABI_VERSION
from .geometry import quantize,fidelity,GRID_MM
from . import native,gerber

CLI=Path('/Users/geoffcheng/Projects/client/misc_repo/KiCAD_PCB_CAM/build/release/kicad/KiCad.app/Contents/MacOS/kicad-cli')
CLI_SHA='9b06a97e609f8ff61753a6e2ca5e4710572df77643630366c8c2ad1428b4b497'
LAYERS=['F.Cu','B.Cu','F.Mask','B.Mask','F.Paste','B.Paste','F.SilkS','B.SilkS','Edge.Cuts']
OPERATIONS=['pcb_kicad_write','pcb_kicad_verify','pcb_gerber_export','pcb_gerber_verify','pcb_export_controls']


def plot_name(layer):
    return 'board-'+layer.replace('.','_').replace('SilkS','Silkscreen')+'.gbr'


def read(p):return json.loads(Path(p).read_bytes())
def fresh(p,blob):
    with p.open('xb') as f:f.write(blob)
def record(p,value):fresh(p,canonical(value))


class DataService:
    def __init__(self,host):
        self.versions={p:package_version(p) for p in ('gerbonara','sexpdata','shapely')}
        if self.versions!={'gerbonara':'1.6.3','sexpdata':'1.0.2','shapely':'2.1.2'}:raise ValueError('PCB_EXPORT_DEPENDENCY_VERSION_CHANGED')
        self.host=host;self.out=Path(host['output']);self.previous=Path(host['predecessor'])
        if digest((self.previous/'RECEIPT.json').read_bytes())!=host['predecessor_receipt_sha256']:raise ValueError('PREDECESSOR_RECEIPT_CHANGED')
        self.receipt=read(self.previous/'RECEIPT.json');self.store=ArtifactStore(self.previous/'runtime')
        if self.receipt['status']!='PASS_BOUNDED_C01_MACOS_NATIVE_ROUTE_REPRODUCTION':raise ValueError('VERIFIED_PREDECESSOR_REQUIRED')
        self.candidate=self.store.get_json(self.receipt['candidate_ref'],kind='candidate')
        verification=self.store.get_json(self.receipt['verification_ref'],kind='verification')
        if verification['geometric_status']!='PASS' or verification['candidate_ref']!=self.receipt['candidate_ref']:raise ValueError('VERIFIED_CANDIDATE_BINDING_FAILED')
        binding=self.store.get_json(self.receipt['binding_ref'],kind='t01-binding')
        self.raw=self.store.get(binding['source_ref'],kind='native-source')
        if digest(self.raw)!=host['source_sha256']:raise ValueError('SOURCE_CHANGED')
        self.edit=Path(host['edit_reference']).read_bytes()
        if digest(self.edit)!=host['edit_sha256']:raise ValueError('EDIT_REFERENCE_CHANGED')
        if digest(CLI.read_bytes())!=CLI_SHA:raise ValueError('PINNED_KICAD_CLI_CHANGED')
        self.decisions=self.candidate['decisions']
        self.targets={d['source_id']:from_wkb(self.store.get(d['candidate_ref'],kind='geometry')) for d in self.decisions}
        self.before=self.out/'before/board.kicad_pcb';self.board=self.out/'candidate/board.kicad_pcb'

    def finish(self,name,value):
        record(self.out/(name+'.json'),value);return value

    def write_kicad(self):
        self.out.mkdir()
        (self.out/'before').mkdir();(self.out/'candidate').mkdir()
        body,rows=native.write_board(self.raw,self.edit,self.decisions,self.targets)
        # Reopen before publishing an operation success; separate verify still
        # reloads the stored file in another CLI process.
        check=native.verify_board(self.raw,body,rows,self.decisions,self.targets)
        fresh(self.before,self.raw);fresh(self.board,body);record(self.out/'TARGET_MAP.json',rows)
        q=[r['quantization'] for r in rows if r['quantization']]
        return self.finish('pcb_kicad_write',dict(facts=dict(passed=True,canonical_sites=check['canonical_sites'],source_occurrences=check['source_occurrences'],modified_occurrences=check['modified_occurrences'],base='ORG + verified T01; EDIT filled-polygon representation',grid_mm=GRID_MM),board=str(self.board),board_sha256=digest(body),edit_reference_sha256=digest(self.edit),versions=self.versions,raw_file_grid_collapse_records=[r for r in rows if r['quantization'] and r['quantization']['subgrid_collapse_visible']],quantization=q))

    def verify_kicad(self):
        saved=read(self.out/'pcb_kicad_write.json')
        if digest(self.board.read_bytes())!=saved['board_sha256']:raise ValueError('CANDIDATE_BOARD_CHANGED')
        result=native.verify_board(self.raw,self.board.read_bytes(),read(self.out/'TARGET_MAP.json'),self.decisions,self.targets)
        return self.finish('pcb_kicad_verify',dict(facts=dict(passed=True,canonical_sites=result['canonical_sites'],source_occurrences=result['source_occurrences'],protected_nodes_equal=True,all_target_contours_pass=True),verification=result))

    def command(self,argv,stem):
        before=digest(self.board.read_bytes())
        p=subprocess.run(list(map(str,argv)),capture_output=True,timeout=120,env=dict(os.environ,KICAD_RUN_FROM_BUILD_DIR='1'))
        fresh(self.out/(stem+'.stdout.txt'),p.stdout);fresh(self.out/(stem+'.stderr.txt'),p.stderr)
        record(self.out/(stem+'.command.json'),dict(argv=list(map(str,argv)),exit_status=p.returncode,cli_sha256=CLI_SHA,at=datetime.now(timezone.utc).isoformat(),environment={'KICAD_RUN_FROM_BUILD_DIR':'1'}))
        if p.returncode:raise ValueError('NATIVE_KICAD_COMMAND_FAILED:'+stem)
        if digest(self.board.read_bytes())!=before:raise ValueError('BOARD_CHANGED_BY_KICAD_EXPORT')
        return p.stdout.decode()

    def export_gerber(self):
        if not read(self.out/'pcb_kicad_verify.json')['facts']['passed']:raise ValueError('KICAD_VERIFY_REQUIRED')
        version=self.command([CLI,'version'],'kicad_version').strip()
        if version!='10.99.0':raise ValueError('KICAD_VERSION_CHANGED')
        exports={}
        for label,board in [('before',self.before),('candidate',self.board)]:
            folder=self.out/label/'gerbers';folder.mkdir()
            self.command([CLI,'pcb','export','gerbers','--layers',','.join(LAYERS),'--precision','6','--no-protel-ext','-o',str(folder)+'/',board],label+'_export')
            paths={layer:str(folder/plot_name(layer)) for layer in LAYERS}
            if any(not Path(p).is_file() for p in paths.values()):raise ValueError('NATIVE_GERBER_LAYER_MISSING')
            exports[label]=paths
        return self.finish('pcb_gerber_export',dict(facts=dict(passed=True,native_export_exit=0,layers=len(LAYERS),precision_decimals=6,kicad_version=version),exports=exports,output_sha256={p:digest(Path(p).read_bytes()) for items in exports.values() for p in items.values()}))

    def plot_check(self,candidate_fcu=None):
        exported=read(self.out/'pcb_gerber_export.json');paths=exported['exports']
        before=gerber.parse(paths['before']['F.Cu']);after=gerber.parse(candidate_fcu or paths['candidate']['F.Cu'])
        if any(g.file_attrs.get('.FileFunction')!=('Copper','L1','Top') or g.file_attrs.get('.FilePolarity')!=('Positive',) for g in (before,after)):raise ValueError('FCU_FILE_ROLE_UNSUPPORTED')
        regions=[(i,gerber.native_geometry(o)) for i,o in enumerate(after.objects) if isinstance(o,go.Region)]
        excluded_before=set();excluded_after=set();rows=[];target_geometries={}
        source_scene=self.store.get_json(self.receipt['scene_ref'],kind='scene');original={r['source_id']:r for r in source_scene['objects']}
        for d in self.decisions:
            growing=d['decision'] in ('GROW_COMPANION','ROUND_GROW_PRIORITY');source=from_wkb(self.store.get(original[d['source_id']]['geometry_ref'],kind='geometry'))
            center=d['center'];radius=(source.bounds[2]-source.bounds[0]+source.bounds[3]-source.bounds[1])/4
            bi=gerber.circle_indices(before.objects,center,radius)
            if len(bi)!=2*len(d['aliases']):raise ValueError('SOURCE_CIRCLE_ALIAS_MEMBERSHIP_FAILED:'+d['key'])
            if growing:
                expected,_=quantize(self.targets[d['source_id']]);matches=[]
                for index,g in regions:
                    if index in excluded_after:continue
                    if any(abs(a-b)>0.000002 for a,b in zip(g.bounds,expected.bounds)):continue
                    try:fidelity(self.targets[d['source_id']],g)
                    except ValueError:continue
                    matches.append((index,g))
                if len(matches)!=len(d['aliases']):raise ValueError('TARGET_POLYGON_NOT_IN_GERBER:'+d['key'])
                for i,g in matches:excluded_after.add(i)
                excluded_before.update(bi);actual=matches[0][1]
            else:
                ai=gerber.circle_indices(after.objects,center,radius)
                if len(ai)!=len(bi):raise ValueError('KEEP_CIRCLE_CHANGED')
                actual=gerber.native_circle(after.objects,ai)
            match=fidelity(self.targets[d['source_id']],actual,native_circle=not growing)
            target_geometries[d['source_id']]=actual
            rows.append(dict(key=d['key'],source_id=d['source_id'],aliases=len(d['aliases']),growing=growing,**match))
        if gerber.protected_counter(before.objects,excluded_before)!=gerber.protected_counter(after.objects,excluded_after):raise ValueError('PROTECTED_FCU_PLOT_GEOMETRY_CHANGED')
        non_copper=[]
        for layer in LAYERS[1:]:
            b=gerber.parse(paths['before'][layer]);a=gerber.parse(paths['candidate'][layer])
            role=lambda g:{k:v for k,v in g.file_attrs.items() if k not in ('.CreationDate','.ProjectId')}
            if role(b)!=role(a) or gerber.protected_counter(b.objects,set())!=gerber.protected_counter(a.objects,set()):raise ValueError('PROTECTED_LAYER_PLOT_CHANGED:'+layer)
            non_copper.append(layer)
        return dict(passed=True,targets=rows,canonical_sites=len(rows),source_occurrences=sum(r['aliases'] for r in rows),removed_source_plot_atoms=len(excluded_before),added_target_regions=len(excluded_after),protected_fcu_atoms_equal=True,protected_layers_equal=non_copper),target_geometries,after

    def verify_gerber(self):
        exported=read(self.out/'pcb_gerber_export.json')
        for p,h in exported['output_sha256'].items():
            if digest(Path(p).read_bytes())!=h:raise ValueError('PLOTTED_GERBER_CHANGED')
        result,geometries,_=self.plot_check()
        directory=self.out/'gerber_target_wkb';directory.mkdir()
        for sid,g in geometries.items():fresh(directory/(sid.rsplit(':',2)[1]+'-'+sid.rsplit(':',1)[1]+'.wkb'),to_wkb(g))
        return self.finish('pcb_gerber_verify',dict(facts=dict(passed=True,canonical_sites=result['canonical_sites'],source_occurrences=result['source_occurrences'],added_target_regions=result['added_target_regions'],protected_fcu_atoms_equal=True,protected_other_layers=len(result['protected_layers_equal'])),verification=result))

    def controls(self):
        if not read(self.out/'pcb_gerber_verify.json')['facts']['passed']:raise ValueError('GERBER_VERIFY_REQUIRED')
        directory=self.out/'controls';directory.mkdir();reports=[]
        def expect(name,expected,fn):
            try:fn()
            except ValueError as e:
                if not str(e).startswith(expected):raise ValueError('WRONG_NEGATIVE_REJECTION:'+str(e)) from e
                reports.append(dict(name=name,expected=expected,error=str(e),status='PASS_EXPECTED_REJECTION'))
            else:raise ValueError('NEGATIVE_CONTROL_NOT_REJECTED:'+name)
        paths=read(self.out/'pcb_gerber_export.json')['exports']['candidate'];fcu=Path(paths['F.Cu']);blob=fcu.read_bytes()
        bad=directory/'wrong_units.gbr';fresh(bad,blob.replace(b'%MOMM*%',b'%MOIN*%',1));expect('gerber_units','GERBER_PROFILE',lambda:gerber.parse(bad))
        _,_,parsed=self.plot_check();s31=next(d for d in self.decisions if d['key']=='S31');which=None
        for i,o in enumerate(parsed.objects):
            if isinstance(o,go.Region):
                try:fidelity(self.targets[s31['source_id']],gerber.native_geometry(o))
                except ValueError:continue
                which=sum(isinstance(x,go.Region) for x in parsed.objects[:i]);break
        if which is None:raise ValueError('S31_CONTROL_REGION_NOT_FOUND')
        spans=list(re.finditer(rb'G36\*.*?G37\*',blob,re.S));m=spans[which]
        missing=directory/'missing_s31.gbr';fresh(missing,blob[:m.start()]+blob[m.end():]);expect('missing_S31','TARGET_POLYGON_NOT_IN_GERBER:S31',lambda:self.plot_check(missing))
        root=sexpdata.loads(self.board.read_text())
        protected=next(n for n in root[1:] if isinstance(n,list) and str(n[0])=='gr_line' and str(native.one(n,'layer',[''])[0])=='F.Mask')
        start=next(n for n in protected if isinstance(n,list) and str(n[0])=='start')
        start[1]=float(start[1])+0.01
        changed=native.board_bytes(root);bad_native=directory/'protected_changed.kicad_pcb';fresh(bad_native,changed)
        expect('native_protected_object','PROTECTED_NATIVE_OBJECT_CHANGED',lambda:native.verify_board(self.raw,changed,read(self.out/'TARGET_MAP.json'),self.decisions,self.targets))
        return self.finish('pcb_export_controls',dict(facts=dict(passed=True,deliberate_controls=len(reports),all_rejected_for_expected_reason=True),controls=reports))

    def dispatch(self,operation):
        handlers=dict(pcb_kicad_write=self.write_kicad,pcb_kicad_verify=self.verify_kicad,pcb_gerber_export=self.export_gerber,pcb_gerber_verify=self.verify_gerber,pcb_export_controls=self.controls)
        if operation not in handlers:raise ValueError('PCB_DATA_OPERATION_NOT_EXPOSED')
        return handlers[operation]()
