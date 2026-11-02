"""Whole-board verified T01 export; existing native writer/checks reused."""
from .crop import CropDataService,TEMPLATE
from .crop import version,ArtifactStore,Path,read,digest,from_wkb,CLI,CLI_SHA
from .board_geometry import export_reference,quantize,fidelity
from . import board_native as native,gerber
from .service import fresh,record,GRID_MM,go,LAYERS
from .crop import sexpdata,re


class BoardDataService(CropDataService):
    def predecessor_root(self,host):
        from .board_custody import validate_host
        return validate_host(host,'data')

    def __init__(self,host):
        root=self.predecessor_root(host)
        self.host=host;self.out=root/'data_output';self.previous=root
        self.versions={p:version(p) for p in ('gerbonara','sexpdata','shapely')}
        if self.versions!={'gerbonara':'1.6.3','sexpdata':'1.0.2','shapely':'2.1.2'}:raise ValueError('PCB_EXPORT_DEPENDENCY_VERSION_CHANGED')
        self.receipt=read(root/'RECEIPT.json');self.store=ArtifactStore(root/'runtime')
        if self.receipt['status']!='PASS_BOARD_T01_VERIFIED':raise ValueError('VERIFIED_PREDECESSOR_REQUIRED')
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
            modified_occurrences=check['modified_occurrences'],file_grid_normalization_targets=len(self.file_grid_normalization),resolvable_hole_targets=sum(p.get('resolvable_holes_preserved',0)>0 for p in self.file_grid_normalization),single_component_multipolygon_targets=sum(p.get('raw_type')=='MultiPolygon'for p in self.file_grid_normalization),base='Supplied original KiCad + verified T01; EDIT-compatible filled polygons',grid_mm=GRID_MM),
            board=str(self.board),board_sha256=digest(body),representation_template_sha256=digest(TEMPLATE),versions=self.versions,
            quantization=[r['quantization'] for r in rows if r['quantization']],file_grid_normalization=self.file_grid_normalization))
    def verify_kicad(self):
        saved=read(self.out/'pcb_kicad_write.json')
        if digest(self.board.read_bytes())!=saved['board_sha256']:raise ValueError('CANDIDATE_BOARD_CHANGED')
        if saved['file_grid_normalization']!=self.file_grid_normalization:raise ValueError('FILE_GRID_NORMALIZATION_PROOF_CHANGED')
        result=native.verify_board(self.raw,self.board.read_bytes(),read(self.out/'TARGET_MAP.json'),self.decisions,self.targets)
        return self.finish('pcb_kicad_verify',dict(facts=dict(passed=True,canonical_sites=result['canonical_sites'],source_occurrences=result['source_occurrences'],protected_nodes_equal=True,all_target_contours_pass=True,file_grid_normalization_targets=len(self.file_grid_normalization),resolvable_hole_targets=sum(p.get('resolvable_holes_preserved',0)>0 for p in self.file_grid_normalization),single_component_multipolygon_targets=sum(p.get('raw_type')=='MultiPolygon'for p in self.file_grid_normalization)),verification=result,file_grid_normalization=self.file_grid_normalization))
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

