"""U04 T01+T04+T02 contour writeback and actual native Gerber reparse.

Changed trace copper uses the same qualified filled-polygon/file-grid format
as T01. Original path/nominal-width authority remains explicit in T04 records.
All other native nodes and plot atoms are protected.
"""
import copy,math,re,traceback
from pathlib import Path
import sexpdata
from shapely import from_wkb,STRtree
from src.stage_abi.store import digest,canonical
from src.source_locators import locate
from src.native_inventory import geometry
from src.native_reference import one
from src.pcb_data_abi.board_export import BoardDataService
from src.pcb_data_abi import board_native as native,gerber
from src.pcb_data_abi.board_geometry import fidelity,quantize
from src.pcb_data_abi.service import fresh,record,LAYERS,go,CLI,CLI_SHA
from tools.t01_operator_host import read
from .custody import export_root
from src.u03_board.source import route_evidence


def required_export_controls(measured):
    """Keep inherited controls and require each applicable new copper fault."""
    required=dict(gerber_units='GERBER_PROFILE',native_protected_object='PROTECTED_NATIVE_OBJECT_CHANGED')
    if measured['changed_native_trace_parts']:
        required['missing_width_copper']='U03_WIDTH_POLYGON_NOT_IN_GERBER'
    elif any(r['growing'] for r in measured['targets']):
        required['missing_T01_copper']='TARGET_POLYGON_NOT_IN_GERBER'
    else:required['wrong_layer_role']='FCU_FILE_ROLE_UNSUPPORTED'
    if measured['rectangle_parts']:required['missing_rectangle_copper']='U04_RECTANGLE_POLYGON_NOT_IN_GERBER'
    if measured['inclusive_parts']:required['missing_inclusive_copper']='U04_INCLUSIVE_POLYGON_NOT_IN_GERBER'
    return required


def validate_export_controls(result,measured):
    expected=required_export_controls(measured);controls=result['controls'];facts=result['facts']
    if (facts.get('passed') is not True or facts.get('all_rejected_for_expected_reason') is not True or
        facts.get('deliberate_controls')!=len(expected) or len(controls)!=len(expected) or
        {r['name'] for r in controls}!=set(expected) or
        any(r['status']!='PASS_EXPECTED_REJECTION' or r['expected']!=expected[r['name']] or
            not r['error'].startswith(expected[r['name']]) for r in controls)):
        raise ValueError('U04_REQUIRED_EXPORT_CONTROLS_MISMATCH')
    return facts


class U04DataService(BoardDataService):
    def predecessor_root(self,host):return export_root(host)

    def command(self,argv,stem):
        try:return super().command(argv,stem)
        except BaseException as error:
            if not (self.out/(stem+'.command.json')).exists():
                def blob(value):return value if isinstance(value,bytes) else str(value or '').encode()
                fresh(self.out/(stem+'.stdout.txt'),blob(getattr(error,'stdout',getattr(error,'output',b''))))
                fresh(self.out/(stem+'.stderr.txt'),blob(getattr(error,'stderr',b'')))
                record(self.out/(stem+'.command.json'),dict(argv=list(map(str,argv)),exit_status=getattr(error,'returncode',None),
                    error_type=type(error).__name__,error=str(error),errno=getattr(error,'errno',None),traceback=traceback.format_exc()))
            raise

    def __init__(self,host):
        super().__init__(host)
        run=read(self.previous/'u03_t04/t04_run.json')['result']
        if self.store.get_json(run['candidate_ref'],kind='candidate')!=run['candidate']:
            raise ValueError('U03_WIDTH_EXPORT_CANDIDATE_CHANGED')
        self.width=run['candidate'];self.width_targets={};self.width_primitives={}
        from .rectangles import RectangleGates
        gates=RectangleGates(self.previous);self.rectangles=gates.validate_verification()
        self.rectangle_targets={};self.inclusive_targets={}
        self.rectangle_sources={r['source_id']:r for r in gates.scene['objects']}
        for decision in self.rectangles['decisions']:
            if decision['status']=='GROWN':
                self.rectangle_targets[decision['source_id']]=from_wkb(self.store.get(decision['candidate_ref'],kind='geometry'))
        for row in self.store.get_json(self.rectangles['output_scene_ref'],kind='scene')['objects']:
            if row['source_id'] not in self.rectangle_sources:
                if row['kind']!='inclusive_rectangle':raise ValueError('U04_UNAUTHORIZED_DERIVED_COPPER')
                self.inclusive_targets[row['source_id']]=from_wkb(self.store.get(row['geometry_ref'],kind='geometry'))
        for c in self.width['construction']:
            if c['factor']==1:continue
            for p in c['primitives']:
                sid=p['source_id'];self.width_targets[sid]=from_wkb(self.store.get(self.width['parts'][sid]['nominal_ref'],kind='geometry'))
                self.width_primitives[sid]=p

    def native_body(self):
        body,rows=native.write_board(self.raw,self.edit,self.decisions,self.targets)
        tree=sexpdata.loads(body.decode());spans=locate(self.raw)
        top=[s for s in spans if s.parent_start==spans[0].start];positions={s.identity:i+1 for i,s in enumerate(top)}
        template=native.edit_template(self.edit);width_rows=[]
        for sid,g in sorted(self.width_targets.items()):
            if sid not in positions:raise ValueError('U03_TOP_LEVEL_WIDTH_SOURCE_REQUIRED:'+sid)
            index=positions[sid]
            if str(tree[index][0]) not in ('segment','arc') or str(one(tree[index],'layer',[''])[0])!='F.Cu':raise ValueError('U03_WIDTH_SOURCE_ROLE_CHANGED')
            node,metrics,uid=native.polygon_node(g,template,sid,self.width['parts'][sid]['nominal_ref']['sha256'])
            tree[index]=node;width_rows.append(dict(source_id=sid,index=index,uuid=uid,quantization=metrics))
        for sid,g in sorted(self.rectangle_targets.items()):
            members=self.rectangle_sources[sid]['metadata']['native_source_ids']
            if members!=[sid] or sid not in positions:raise ValueError('U04_NATIVE_RECTANGLE_IDENTITY_REQUIRED')
            index=positions[sid];node=tree[index]
            if str(node[0])!='gr_poly' or str(one(node,'layer',[''])[0])!='F.Cu':raise ValueError('U04_RECTANGLE_SOURCE_ROLE_CHANGED')
            from shapely import to_wkb
            tree[index]=native.polygon_node(g,template,sid,digest(to_wkb(g)))[0]
        for sid,g in sorted(self.inclusive_targets.items()):
            from shapely import to_wkb
            tree.append(native.polygon_node(g,template,sid,digest(to_wkb(g)))[0])
        return native.board_bytes(tree),rows,width_rows

    def native_check(self,body,rows,width_rows):
        before=sexpdata.loads(self.raw.decode());after=sexpdata.loads(body.decode())
        if len(after)!=len(before)+len(self.inclusive_targets):raise ValueError('PROTECTED_NATIVE_OBJECT_CHANGED:U04 object count')
        reconstructed,t01,expected_width=self.native_body()
        if rows!=t01 or width_rows!=expected_width:raise ValueError('U03_WIDTH_NATIVE_MAP_CHANGED')
        expected=sexpdata.loads(reconstructed.decode())
        if after!=expected:raise ValueError('PROTECTED_NATIVE_OBJECT_CHANGED:U03 complete reconstruction')
        # Separately reparse actual output contours, then restore the original
        # trace nodes for the unchanged T01 native verifier.
        restored=copy.deepcopy(after[:len(before)]);proofs=[];rectangle_proofs=[];inclusive_proofs=[]
        spans=locate(self.raw);positions={r.identity:i+1 for i,r in enumerate([s for s in spans if s.parent_start==spans[0].start])}
        for sid,g in sorted(self.rectangle_targets.items()):
            index=positions[sid];node=after[index]
            if str(node[0])!='gr_poly' or str(one(node,'layer',[''])[0])!='F.Cu':raise ValueError('U04_RECTANGLE_NATIVE_ROLE_CHANGED')
            rectangle_proofs.append(dict(source_id=sid,**fidelity(g,geometry(node,'gr_poly'))));restored[index]=before[index]
        for i,(sid,g) in enumerate(sorted(self.inclusive_targets.items()),len(before)):
            node=after[i]
            if str(node[0])!='gr_poly' or str(one(node,'layer',[''])[0])!='F.Cu':raise ValueError('U04_INCLUSIVE_NATIVE_ROLE_CHANGED')
            inclusive_proofs.append(dict(source_id=sid,**fidelity(g,geometry(node,'gr_poly'))))
        for r in width_rows:
            sid=r['source_id'];node=after[r['index']]
            if str(node[0])!='gr_poly' or str(one(node,'layer',[''])[0])!='F.Cu':raise ValueError('U03_WIDTH_OUTPUT_ROLE_CHANGED')
            proofs.append(dict(source_id=sid,**fidelity(self.width_targets[sid],geometry(node,'gr_poly'))))
            restored[r['index']]=before[r['index']]
        checked=native.verify_board(self.raw,native.board_bytes(restored),rows,self.decisions,self.targets)
        return dict(checked,rectangle_targets=rectangle_proofs,inclusive_targets=inclusive_proofs,rectangle_parts=len(rectangle_proofs),inclusive_parts=len(inclusive_proofs),width_targets=proofs,changed_native_trace_parts=len(proofs),source_paths_unchanged=True,
                    width_representation='Source-bound nominal copper contours, same existing 1 nm file-grid normalization; no net-intent claim')

    def write_kicad(self):
        self.out.mkdir();(self.out/'before').mkdir();(self.out/'candidate').mkdir()
        body,rows,width_rows=self.native_body();checked=self.native_check(body,rows,width_rows)
        fresh(self.before,self.raw);fresh(self.board,body);record(self.out/'TARGET_MAP.json',rows);record(self.out/'WIDTH_TARGET_MAP.json',width_rows)
        return self.finish('pcb_kicad_write',dict(board=str(self.board),board_sha256=digest(body),versions=self.versions,
            width_representation=checked['width_representation'],facts=dict(passed=True,canonical_sites=checked['canonical_sites'],source_occurrences=checked['source_occurrences'],
            rectangle_parts=len(self.rectangle_targets),inclusive_parts=len(self.inclusive_targets),changed_native_trace_parts=len(width_rows),protected_nodes_equal=True,all_target_contours_pass=True)))

    def verify_kicad(self):
        saved=read(self.out/'pcb_kicad_write.json')
        if digest(self.board.read_bytes())!=saved['board_sha256']:raise ValueError('CANDIDATE_BOARD_CHANGED')
        q=self.native_check(self.board.read_bytes(),read(self.out/'TARGET_MAP.json'),read(self.out/'WIDTH_TARGET_MAP.json'))
        return self.finish('pcb_kicad_verify',dict(verification=q,facts=dict(passed=True,canonical_sites=q['canonical_sites'],source_occurrences=q['source_occurrences'],
            rectangle_parts=q['rectangle_parts'],inclusive_parts=q['inclusive_parts'],changed_native_trace_parts=q['changed_native_trace_parts'],protected_nodes_equal=True,all_target_contours_pass=True)))

    def verify_gerber(self):
        self.allow_source_plot_probes=True
        try:return super().verify_gerber()
        finally:self.allow_source_plot_probes=False

    def source_trace_indices(self,objects):
        """Bind actual source plot atoms by native endpoints, kind and width."""
        from collections import defaultdict
        bank=defaultdict(list)
        grid=.000001;endpoint_tolerance=.000002
        def cell(point):return tuple(int(round(v/grid)) for v in point)
        for i,o in enumerate(objects):
            if not isinstance(o,(go.Line,go.Arc)) or not o.polarity_dark or not hasattr(o.aperture,'diameter'):continue
            key=('arc' if isinstance(o,go.Arc) else 'segment',round(float(o.aperture.diameter),6))
            for point in ((o.x1,-o.y1),(o.x2,-o.y2)):bank[(*key,cell(point))].append(i)
        result=set();proofs=[]
        source=self.store.get_json(read(self.previous/'RECEIPT.json')['scene_ref'],kind='scene')
        original={r['source_id']:r for r in source['objects']}
        for sid,p in sorted(self.width_primitives.items()):
            keys=[(p['kind'],round(p['original_width_mm'],6))]
            if p['kind']=='arc':keys.append(('segment',round(p['original_width_mm'],6)))
            cx,cy=cell(p['start_mm'])
            indices=sorted({i for key in keys for dx in range(-2,3) for dy in range(-2,3) for i in bank[(*key,(cx+dx,cy+dy))] if i not in result})
            # Native source WKB is independently retained in each construction
            # primitive. Resolve its actual original source-map contribution.
            row=original[sid]
            g=from_wkb(self.store.get(row['geometry_ref'],kind='geometry'))
            matched=[];isolated=None;source_discrepancies={}
            for i in indices:
                obj=objects[i];a=(obj.x1,-obj.y1);b=(obj.x2,-obj.y2)
                endpoint_error=min(max(math.dist(p['start_mm'],a),math.dist(p['end_mm'],b)),max(math.dist(p['start_mm'],b),math.dist(p['end_mm'],a)))
                if endpoint_error>endpoint_tolerance+1e-12:continue
                actual=gerber.native_geometry(obj);tol=.000025
                source_discrepancies[i]=g.hausdorff_distance(actual)
                same_kind=(p['kind']=='arc')==isinstance(obj,go.Arc)
                if same_kind and source_discrepancies[i]<=tol and g.symmetric_difference(actual).area<=2*g.length*tol+math.pi*tol**2:
                    matched.append(i)
                elif p['kind']=='arc':
                    if isolated is None:isolated=self.isolated_arc_plot(sid,p)
                    if canonical(route_evidence(gerber.atom(obj)))==isolated['atom_bytes']:matched.append(i)
            if not matched:raise ValueError('U03_SOURCE_TRACE_PLOT_MEMBERSHIP_FAILED:'+sid)
            index=min(matched);result.add(index);proofs.append(dict(source_id=sid,plot_index=index,source_native_bytes_sha256=p['fragment_sha256'],tolerance_mm=.000025,endpoint_tolerance_mm=endpoint_tolerance,
                source_plot_hausdorff_mm=source_discrepancies[index],source_kind=p['kind'],plot_kind=type(objects[index]).__name__,
                isolated_native_plot=None if isolated is None else isolated['receipt']))
        return result,proofs

    def isolated_arc_plot(self,sid,primitive):
        """Bind an exporter representation by actual pinned native execution.

        A nearly straight native arc can be emitted as a line. No tolerance is
        enlarged: the bulk plot atom must equal this isolated native plot atom.
        This is source identity evidence, not a different T04 geometry family.
        """
        prefix,start,end=sid.rsplit(':',2);start,end=int(start),int(end)
        fragment=self.raw[start:end]
        if prefix!=digest(self.raw)+':bytes' or digest(fragment)!=primitive['fragment_sha256'] or str(sexpdata.loads(fragment.decode())[0])!='arc':
            raise ValueError('U03_ISOLATED_ARC_SOURCE_CHANGED')
        folder=self.out/'source_trace_probes'/f'{start}-{end}';receipt=folder/'RECEIPT.json'
        binding=dict(source_sha256=digest(self.raw),source_id=sid,fragment_sha256=digest(fragment),cli_sha256=CLI_SHA,
                     purpose='Exact original native arc source → pinned native plotting atom; no width/route change')
        if receipt.exists():
            value=read(receipt)
            if value['binding']!=binding:raise ValueError('U03_ISOLATED_ARC_BINDING_CHANGED')
            for path,h in value['files'].items():
                if digest((folder/path).read_bytes())!=h:raise ValueError('U03_ISOLATED_ARC_EVIDENCE_CHANGED')
        else:
            if not getattr(self,'allow_source_plot_probes',False):raise ValueError('U03_ISOLATED_ARC_EVIDENCE_MISSING')
            folder.mkdir(parents=True,exist_ok=False)
            root=sexpdata.loads(self.raw.decode())
            metadata={'version','generator','generator_version','general','paper','layers','setup','net','net_class','embedded_fonts'}
            prefix_nodes=[n for n in root[1:] if isinstance(n,list) and str(n[0]) in metadata]
            # Keep the original native arc fragment byte-for-byte in the
            # isolated source; no fitting, midpoint or width replacement.
            body=('(kicad_pcb\n'+'\n'.join(native.encode(n) for n in prefix_nodes)+'\n').encode()+fragment+b'\n)\n'
            board=folder/'board.kicad_pcb';fresh(board,body);plots=folder/'gerbers';plots.mkdir()
            stem=f'arc_source_{start}_{end}'
            self.command([CLI,'pcb','export','gerbers','--layers','F.Cu','--precision','6','--no-protel-ext','-o',str(plots)+'/',board],stem)
            for suffix in ('.command.json','.stdout.txt','.stderr.txt'):
                log=self.out/(stem+suffix);fresh(folder/(stem+suffix),log.read_bytes())
            value=dict(binding=binding,files={str(p.relative_to(folder)):digest(p.read_bytes()) for p in folder.rglob('*') if p.is_file()},
                       execution='ACTUAL_PINNED_NATIVE_SOURCE_PLOT',rendering='NOT_REQUESTED')
            record(receipt,value)
        plot=folder/'gerbers/board-F_Cu.gbr';parsed=gerber.parse(plot)
        if parsed.file_attrs.get('.FileFunction')!=('Copper','L1','Top') or parsed.file_attrs.get('.FilePolarity')!=('Positive',):
            raise ValueError('U03_ISOLATED_ARC_PLOT_ROLE_CHANGED')
        if len(parsed.objects)!=1 or not isinstance(parsed.objects[0],(go.Line,go.Arc)) or not parsed.objects[0].polarity_dark:
            raise ValueError('U03_ISOLATED_ARC_PLOT_NOT_ONE_ATOM')
        return dict(atom_bytes=canonical(route_evidence(gerber.atom(parsed.objects[0]))),receipt=str(receipt))

    def controls(self):
        if not read(self.out/'pcb_gerber_verify.json')['facts']['passed']:raise ValueError('GERBER_VERIFY_REQUIRED')
        directory=self.out/'controls';directory.mkdir();reports=[]
        def expect(name,prefix,fn):
            try:fn()
            except ValueError as error:
                if not str(error).startswith(prefix):raise ValueError('WRONG_NEGATIVE_REJECTION:'+str(error))
                reports.append(dict(name=name,expected=prefix,error=str(error),status='PASS_EXPECTED_REJECTION'))
            else:raise ValueError('U03_NEGATIVE_NOT_REJECTED:'+name)
        path=Path(read(self.out/'pcb_gerber_export.json')['exports']['candidate']['F.Cu']);blob=path.read_bytes()
        bad=directory/'wrong_units.gbr';fresh(bad,blob.replace(b'%MOMM*%',b'%MOIN*%',1));expect('gerber_units','GERBER_PROFILE',lambda:gerber.parse(bad))
        # Remove an actual width polygon from the candidate Gerber.
        _,_,parsed=self.plot_check();sid=next(iter(self.width_targets),None)
        growing=[d for d in self.decisions if d['decision'] in ('GROW_COMPANION','ROUND_GROW_PRIORITY')]
        if sid or growing:
            target=self.width_targets[sid] if sid else self.targets[growing[0]['source_id']];region_index=0;which=None
            for obj in parsed.objects:
                if not isinstance(obj,go.Region):continue
                try:fidelity(target,gerber.native_geometry(obj))
                except ValueError:region_index+=1;continue
                which=region_index;break
            if which is None:raise ValueError('U03_ACTUAL_NEGATIVE_REGION_NOT_FOUND')
            span=list(re.finditer(rb'G36\*.*?G37\*',blob,re.S))[which];missing=directory/'missing_width.gbr';fresh(missing,blob[:span.start()]+blob[span.end():])
            expect('missing_width_copper' if sid else 'missing_T01_copper','U03_WIDTH_POLYGON_NOT_IN_GERBER' if sid else 'TARGET_POLYGON_NOT_IN_GERBER',lambda:self.plot_check(missing))
        else:
            role=directory/'wrong_role.gbr';fresh(role,blob.replace(b'Copper,L1,Top',b'Copper,L2,Bot',1))
            expect('wrong_layer_role','FCU_FILE_ROLE_UNSUPPORTED',lambda:self.plot_check(role))
        measured,_,_=self.plot_check()
        for name,key,prefix in [('missing_rectangle','rectangle_targets','U04_RECTANGLE_POLYGON_NOT_IN_GERBER'),('missing_inclusive','inclusive_targets','U04_INCLUSIVE_POLYGON_NOT_IN_GERBER')]:
            if not measured[key]:continue
            index=measured[key][0]['plot_index'];which=sum(isinstance(o,go.Region) for o in parsed.objects[:index])
            span=list(re.finditer(rb'G36\*.*?G37\*',blob,re.S))[which];missing=directory/(name+'.gbr');fresh(missing,blob[:span.start()]+blob[span.end():])
            expect(name+'_copper',prefix,lambda path=missing:self.plot_check(path))
        root=sexpdata.loads(self.board.read_text());rows=read(self.out/'TARGET_MAP.json');wr=read(self.out/'WIDTH_TARGET_MAP.json')
        changed={r['index'] for r in rows if r['growing']}|{r['index'] for r in wr}
        index=next((i for i,n in enumerate(root[1:],1) if i not in changed and isinstance(n,list) and str(n[0]) in ('gr_poly','gr_circle','segment','arc')),1)
        root[index].append([sexpdata.Symbol('property'),'u03-corrupt-control','1']);badbody=native.board_bytes(root);fresh(directory/'protected_changed.kicad_pcb',badbody)
        expect('native_protected_object','PROTECTED_NATIVE_OBJECT_CHANGED',lambda:self.native_check(badbody,rows,wr))
        return self.finish('pcb_export_controls',dict(controls=reports,facts=dict(passed=True,deliberate_controls=len(reports),all_rejected_for_expected_reason=True)))

    def plot_check(self,candidate_fcu=None):
        exported=read(self.out/'pcb_gerber_export.json');paths=exported['exports']
        before=gerber.parse(paths['before']['F.Cu']);after=gerber.parse(candidate_fcu or paths['candidate']['F.Cu'])
        if any(g.file_attrs.get('.FileFunction')!=('Copper','L1','Top') or g.file_attrs.get('.FilePolarity')!=('Positive',) for g in (before,after)):raise ValueError('FCU_FILE_ROLE_UNSUPPORTED')
        regions=[(i,gerber.native_geometry(o)) for i,o in enumerate(after.objects) if isinstance(o,go.Region)]
        region_tree=STRtree([g for _,g in regions])
        excluded_before,source_width_proofs=self.source_trace_indices(before.objects);excluded_after=set();rows=[];target_geometries={}
        width_rows=[];rectangle_rows=[];inclusive_rows=[]
        source_scene=self.store.get_json(self.receipt['scene_ref'],kind='scene');original={r['source_id']:r for r in source_scene['objects']}
        for d in self.decisions:
            growing=d['decision'] in ('GROW_COMPANION','ROUND_GROW_PRIORITY');source=from_wkb(self.store.get(original[d['source_id']]['geometry_ref'],kind='geometry'))
            center=d['center'];radius=(source.bounds[2]-source.bounds[0]+source.bounds[3]-source.bounds[1])/4
            bi=gerber.circle_indices(before.objects,center,radius)
            if len(bi)!=2*len(d['aliases']):raise ValueError('SOURCE_CIRCLE_ALIAS_MEMBERSHIP_FAILED:'+d['key'])
            if growing:
                expected,_=quantize(self.targets[d['source_id']]);matches=[]
                for position in sorted(map(int,region_tree.query(expected.envelope.buffer(.000002)))):
                    index,g=regions[position]
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
        for sid,reference in sorted(self.width_targets.items()):
            expected,_=quantize(reference);matches=[]
            for position in sorted(map(int,region_tree.query(expected.envelope.buffer(.000002)))):
                index,g=regions[position]
                if index in excluded_after or any(abs(a-b)>.000002 for a,b in zip(g.bounds,expected.bounds)):continue
                try:proof=fidelity(reference,g)
                except ValueError:continue
                matches.append((index,g,proof))
            if not matches:raise ValueError('U03_WIDTH_POLYGON_NOT_IN_GERBER:'+sid)
            index,g,proof=min(matches,key=lambda r:r[0]);excluded_after.add(index);target_geometries[sid]=g
            width_rows.append(dict(source_id=sid,plot_index=index,**proof))
        def region_match(reference,objects,excluded,label):
            expected,_=quantize(reference);matches=[]
            for index,obj in enumerate(objects):
                if index in excluded or not isinstance(obj,go.Region):continue
                g=gerber.native_geometry(obj)
                if any(abs(a-b)>.000002 for a,b in zip(g.bounds,expected.bounds)):continue
                try:proof=fidelity(reference,g)
                except ValueError:continue
                matches.append((index,g,proof))
            if not matches:raise ValueError(label)
            return min(matches,key=lambda r:r[0])
        for sid,reference in sorted(self.rectangle_targets.items()):
            original=from_wkb(self.store.get(self.rectangle_sources[sid]['original_ref'],kind='geometry'))
            bi,_,source_proof=region_match(original,before.objects,excluded_before,'U04_RECTANGLE_SOURCE_PLOT_MISSING:'+sid)
            ai,g,proof=region_match(reference,after.objects,excluded_after,'U04_RECTANGLE_POLYGON_NOT_IN_GERBER:'+sid)
            excluded_before.add(bi);excluded_after.add(ai);target_geometries[sid]=g
            rectangle_rows.append(dict(source_id=sid,source_plot_index=bi,plot_index=ai,source_proof=source_proof,**proof))
        for sid,reference in sorted(self.inclusive_targets.items()):
            ai,g,proof=region_match(reference,after.objects,excluded_after,'U04_INCLUSIVE_POLYGON_NOT_IN_GERBER:'+sid)
            excluded_after.add(ai);target_geometries[sid]=g;inclusive_rows.append(dict(source_id=sid,plot_index=ai,**proof))
        if gerber.protected_counter(before.objects,excluded_before)!=gerber.protected_counter(after.objects,excluded_after):raise ValueError('PROTECTED_FCU_PLOT_GEOMETRY_CHANGED')
        non_copper=[]
        for layer in LAYERS[1:]:
            b=gerber.parse(paths['before'][layer]);a=gerber.parse(paths['candidate'][layer])
            role=lambda g:{k:v for k,v in g.file_attrs.items() if k not in ('.CreationDate','.ProjectId')}
            if role(b)!=role(a) or gerber.protected_counter(b.objects,set())!=gerber.protected_counter(a.objects,set()):raise ValueError('PROTECTED_LAYER_PLOT_CHANGED:'+layer)
            non_copper.append(layer)
        return dict(passed=True,rectangle_targets=rectangle_rows,inclusive_targets=inclusive_rows,rectangle_parts=len(rectangle_rows),inclusive_parts=len(inclusive_rows),width_targets=width_rows,source_width_plot_bindings=source_width_proofs,changed_native_trace_parts=len(width_rows),targets=rows,canonical_sites=len(rows),source_occurrences=sum(r['aliases'] for r in rows),removed_source_plot_atoms=len(excluded_before),added_target_regions=len(excluded_after),protected_fcu_atoms_equal=True,protected_layers_equal=non_copper),target_geometries,after

