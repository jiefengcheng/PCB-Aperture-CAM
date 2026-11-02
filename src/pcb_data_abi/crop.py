"""Generic verified-T01 file materialization inside the PCB data ABI suite."""
import re
from importlib.metadata import version
from pathlib import Path
import sexpdata
from shapely import from_wkb
from src.stage_abi.store import ArtifactStore,digest
from src.native_reference import one
from .service import DataService,CLI,CLI_SHA,read,fresh,record
from . import native,gerber
from .geometry import GRID_MM,fidelity
from .crop_quantization import export_reference

# A minimal instance of the EDIT-compatible representation, not EDIT copper.
TEMPLATE=b'(kicad_pcb (gr_poly (pts (xy 0 0) (xy 1 0) (xy 0 1)) (stroke (width 0) (type solid)) (fill yes) (layer "F.Cu")))'

class CropDataService(DataService):
    def __init__(self,host):
        from .crop_custody import validate_host
        root=validate_host(host,'data')
        self.host=host;self.out=root/'data_output';self.previous=root
        self.versions={p:version(p) for p in ('gerbonara','sexpdata','shapely')}
        if self.versions!={'gerbonara':'1.6.3','sexpdata':'1.0.2','shapely':'2.1.2'}:raise ValueError('PCB_EXPORT_DEPENDENCY_VERSION_CHANGED')
        self.receipt=read(root/'RECEIPT.json');self.store=ArtifactStore(root/'runtime')
        if self.receipt['status']!='PASS_CROP_T01_VERIFIED':raise ValueError('VERIFIED_PREDECESSOR_REQUIRED')
        self.candidate=self.store.get_json(self.receipt['candidate_ref'],kind='candidate')
        verified=self.store.get_json(self.receipt['verification_ref'],kind='verification')
        if verified['geometric_status']!='PASS' or verified['candidate_ref']!=self.receipt['candidate_ref']:raise ValueError('VERIFIED_CANDIDATE_BINDING_FAILED')
        binding=self.store.get_json(self.receipt['binding_ref'],kind='t01-binding')
        self.raw=self.store.get(binding['source_ref'],kind='native-source')
        if digest(self.raw)!=self.receipt['source_sha256']:raise ValueError('SOURCE_CHANGED')
        if digest(CLI.read_bytes())!=CLI_SHA:raise ValueError('PINNED_KICAD_CLI_CHANGED')
        self.edit=TEMPLATE;self.decisions=self.candidate['decisions']
        self.targets={d['source_id']:from_wkb(self.store.get(d['candidate_ref'],kind='geometry')) for d in self.decisions}
        self.file_grid_normalization=[]
        for d in self.decisions:
            if d['decision'] not in ('GROW_COMPANION','ROUND_GROW_PRIORITY'):continue
            reference,proof=export_reference(self.targets[d['source_id']])
            if proof is not None:
                self.targets[d['source_id']]=reference
                self.file_grid_normalization.append(dict(source_id=d['source_id'],key=d['key'],verified_ref=d['candidate_ref'],**proof))
        self.before=self.out/'before/board.kicad_pcb';self.board=self.out/'candidate/board.kicad_pcb'
    def write_kicad(self):
        self.out.mkdir();(self.out/'before').mkdir();(self.out/'candidate').mkdir()
        body,rows=native.write_board(self.raw,self.edit,self.decisions,self.targets)
        check=native.verify_board(self.raw,body,rows,self.decisions,self.targets)
        fresh(self.before,self.raw);fresh(self.board,body);record(self.out/'TARGET_MAP.json',rows)
        return self.finish('pcb_kicad_write',dict(facts=dict(passed=True,canonical_sites=check['canonical_sites'],source_occurrences=check['source_occurrences'],
            modified_occurrences=check['modified_occurrences'],subgrid_hole_targets=len(self.file_grid_normalization),base='Supplied original KiCad + verified T01; EDIT-compatible filled polygons',grid_mm=GRID_MM),
            board=str(self.board),board_sha256=digest(body),representation_template_sha256=digest(TEMPLATE),versions=self.versions,
            quantization=[r['quantization'] for r in rows if r['quantization']],file_grid_normalization=self.file_grid_normalization))
    def verify_kicad(self):
        saved=read(self.out/'pcb_kicad_write.json')
        if digest(self.board.read_bytes())!=saved['board_sha256']:raise ValueError('CANDIDATE_BOARD_CHANGED')
        if saved['file_grid_normalization']!=self.file_grid_normalization:raise ValueError('FILE_GRID_NORMALIZATION_PROOF_CHANGED')
        result=native.verify_board(self.raw,self.board.read_bytes(),read(self.out/'TARGET_MAP.json'),self.decisions,self.targets)
        return self.finish('pcb_kicad_verify',dict(facts=dict(passed=True,canonical_sites=result['canonical_sites'],source_occurrences=result['source_occurrences'],protected_nodes_equal=True,all_target_contours_pass=True,subgrid_hole_targets=len(self.file_grid_normalization)),verification=result,file_grid_normalization=self.file_grid_normalization))
    def controls(self):
        if not read(self.out/'pcb_gerber_verify.json')['facts']['passed']:raise ValueError('GERBER_VERIFY_REQUIRED')
        directory=self.out/'controls';directory.mkdir();reports=[]
        def expect(name,prefix,fn):
            try:fn()
            except ValueError as e:
                if not str(e).startswith(prefix):raise ValueError('WRONG_NEGATIVE_REJECTION:'+str(e)) from e
                reports.append(dict(name=name,expected=prefix,error=str(e),status='PASS_EXPECTED_REJECTION'))
            else:raise ValueError('NEGATIVE_CONTROL_NOT_REJECTED:'+name)
        fcu=Path(read(self.out/'pcb_gerber_export.json')['exports']['candidate']['F.Cu']);blob=fcu.read_bytes()
        bad=directory/'wrong_units.gbr';fresh(bad,blob.replace(b'%MOMM*%',b'%MOIN*%',1))
        expect('gerber_units','GERBER_PROFILE',lambda:gerber.parse(bad))
        _,_,parsed=self.plot_check();growing=[d for d in self.decisions if d['decision'] in ('GROW_COMPANION','ROUND_GROW_PRIORITY')]
        if growing:
            d=growing[0];which=None;region_index=0
            from gerbonara import graphic_objects as go
            for obj in parsed.objects:
                if not isinstance(obj,go.Region):continue
                try:fidelity(self.targets[d['source_id']],gerber.native_geometry(obj))
                except ValueError:region_index+=1;continue
                which=region_index;break
            if which is None:raise ValueError('GROWING_CONTROL_REGION_NOT_FOUND')
            span=list(re.finditer(rb'G36\*.*?G37\*',blob,re.S))[which]
            missing=directory/'missing_target.gbr';fresh(missing,blob[:span.start()]+blob[span.end():])
            expect('missing_grown_target','TARGET_POLYGON_NOT_IN_GERBER:'+d['key'],lambda:self.plot_check(missing))
        else:
            changed=directory/'wrong_role.gbr';fresh(changed,blob.replace(b'Copper,L1,Top',b'Copper,L2,Bot',1))
            expect('gerber_layer_role','FCU_FILE_ROLE_UNSUPPORTED',lambda:self.plot_check(changed))
        root=sexpdata.loads(self.board.read_text());records=read(self.out/'TARGET_MAP.json')
        changed_indices={r['index'] for r in records if r['growing']}
        index=next(i for i,node in enumerate(root[1:],1) if i not in changed_indices and isinstance(node,list) and str(node[0]) in ('gr_line','gr_poly','gr_circle','segment','arc'))
        node=root[index];child=next((n for n in node if isinstance(n,list) and str(n[0]) in ('start','center')),None)
        if child is not None:child[1]=float(child[1])+.01
        else:node.append([sexpdata.Symbol('property'),'corrupted','1'])
        body=native.board_bytes(root);fresh(directory/'protected_changed.kicad_pcb',body)
        expect('native_protected_object','PROTECTED_NATIVE_OBJECT_CHANGED',lambda:native.verify_board(self.raw,body,records,self.decisions,self.targets))
        return self.finish('pcb_export_controls',dict(facts=dict(passed=True,deliberate_controls=len(reports),all_rejected_for_expected_reason=True),controls=reports))
