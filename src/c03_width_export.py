"""Actual append-only native width contours and full plotted-surface checks."""
import re,copy,math
from pathlib import Path
from importlib.metadata import version
import sexpdata
from shapely import from_wkb,to_wkb,STRtree
from shapely.ops import unary_union
from src.stage_abi.store import digest,canonical
from src.native_inventory import geometry
from src.native_reference import one
from src.pcb_data_abi import board_native as native,gerber
from src.pcb_data_abi.board_geometry import fidelity,quantize
from src.pcb_data_abi.crop import TEMPLATE
from src.pcb_data_abi.service import DataService,CLI,CLI_SHA,LAYERS,go,fresh,record
from src.u03_board.export import U03DataService
from src.u03_board.selection import window
from src.prepared_width_scene import PreparedWidthScene
from src.trace_width_clearance import TraceWidthContract


def actual_hard_floor(report):
    """The existing 20 um actual-export floor, distinct from model 20.10 um.

    Keep the complete 20.10 um diagnostic report, including its failures. The
    model construction guard must already pass independently. No source port,
    visibility, epsilon, file-grid or other bound is enlarged for actual files.
    """
    c=TraceWidthContract();failures=[]
    for r in report['traces']:
        failures.extend(dict(trace_id=r['trace_id'],reason=x)for x in r['failures'])
        for p in r['pairs']:
            gap=p['new_exposed_to_visible_neighbor_gap_mm']
            if gap is not None and gap+c.comparison_epsilon_mm<c.hard_gap_mm:failures.append(dict(trace_id=r['trace_id'],neighbor_id=p['neighbor_id'],reason='ACTUAL_WIDTH_BELOW_HARD_GAP',gap_mm=gap))
    return dict(passed=not failures,hard_gap_mm=c.hard_gap_mm,failures=failures,construction_guard_report=report,scope='Actual file hard floor only; separate unchanged conservative model construction proof is mandatory')


class WidthExport(DataService):
    def __init__(self,continuation,context,candidate):
        self.continuation=continuation;self.context=context;self.candidate=candidate;self.store=continuation.store;self.out=continuation.out/'data_output';self.raw=continuation.raw;self.before=self.out/'before/board.kicad_pcb';self.board=self.out/'candidate/board.kicad_pcb';self.targets={};self.primitives={}
        self.versions={p:version(p)for p in ('gerbonara','sexpdata','shapely')}
        if self.versions!={'gerbonara':'1.6.3','sexpdata':'1.0.2','shapely':'2.1.2'}or digest(CLI.read_bytes())!=CLI_SHA:raise ValueError('C03_PINNED_NATIVE_EXPORT_RUNTIME_CHANGED')
        for row in candidate['construction']:
            for p in row['primitives']:
                self.primitives[p['source_id']]=p
                if row['factor']>1:self.targets[p['source_id']]=from_wkb(self.store.get(candidate['parts'][p['source_id']]['nominal_ref'],kind='geometry'))
        self.domain=window(continuation.selection)
        if any(not self.domain.covers(g) for g in self.targets.values()):raise ValueError('C03_WIDTH_CONTOUR_OUTSIDE_UNCHANGED_BOUNDARY')

    def native_body(self):
        template=native.edit_template(TEMPLATE);nodes=[]
        for sid,g in sorted(self.targets.items()):nodes.append(native.polygon_node(g,template,sid,digest(to_wkb(g)))[0])
        prefix=self.raw.rstrip()
        if not prefix.endswith(b')'):raise ValueError('C03_NATIVE_ROOT_TERMINATOR_REQUIRED')
        return prefix[:-1]+b'\n'+b'\n'.join(('  '+native.encode(n)).encode()for n in nodes)+b'\n)\n'

    def native_check(self,body):
        before=sexpdata.loads(self.raw.decode());after=sexpdata.loads(body.decode());expected=sexpdata.loads(self.native_body().decode())
        if len(after)!=len(before)+len(self.targets)or after[:len(before)]!=before:raise ValueError('C03_PROTECTED_U05_NATIVE_NODE_CHANGED')
        if after!=expected:raise ValueError('C03_WIDTH_NATIVE_RECONSTRUCTION_FAILED')
        proofs=[]
        for index,(sid,g) in enumerate(sorted(self.targets.items()),len(before)):
            node=after[index]
            if str(node[0])!='gr_poly'or str(one(node,'layer',[''])[0])!='F.Cu':raise ValueError('C03_WIDTH_NATIVE_ROLE_CHANGED')
            proofs.append(dict(source_id=sid,node_index=index,**fidelity(g,geometry(node,'gr_poly'))))
        return dict(passed=True,all_U05_native_nodes_equal=True,complete_append_reconstruction=True,width_parts=len(proofs),targets=proofs)

    def write_kicad(self):
        self.out.mkdir();(self.out/'before').mkdir();(self.out/'candidate').mkdir();body=self.native_body();proof=self.native_check(body);fresh(self.before,self.raw);fresh(self.board,body)
        return self.finish('pcb_kicad_write',dict(board=str(self.board),board_sha256=digest(body),predecessor_sha256=digest(self.raw),versions=self.versions,verification=proof,facts=dict(passed=True,all_U05_native_nodes_equal=True,width_parts=len(self.targets))))

    def verify_kicad(self):
        saved=self.continuation.read(self.out/'pcb_kicad_write.json')
        if digest(self.board.read_bytes())!=saved['board_sha256']or self.before.read_bytes()!=self.raw:raise ValueError('C03_SAVED_NATIVE_WIDTH_CANDIDATE_CHANGED')
        q=self.native_check(self.board.read_bytes());return self.finish('pcb_kicad_verify',dict(verification=q,facts=dict(passed=True,all_U05_native_nodes_equal=True,width_parts=len(self.targets))))

    def source_bindings(self,before,*,allow_probes=False):
        # Reuse the existing endpoint/kind/width binding and exact isolated
        # native arc-plot fallback; every source stays original in this route.
        shim=object.__new__(U03DataService);shim.width_primitives=self.primitives;shim.previous=self.continuation.source_root;shim.store=self.continuation.source_store;shim.raw=self.continuation.original_raw;shim.out=self.out;shim.board=self.board;shim.allow_source_plot_probes=allow_probes
        return shim.source_trace_indices(before.objects)

    def fixed_width_bindings(self,before):
        # A plotted filled circle uses arc strokes internally. Its aperture
        # diameter is NOT a native trace width and must never widen a port.
        # Bind true trace arcs to original unchanged native arc occurrences;
        # bind filled-circle arcs with the existing exact circle-plot formula.
        arc_bank=__import__('collections').defaultdict(list);circles=__import__('collections').defaultdict(list);grid=.000001
        cell=lambda p:tuple(int(round(v/grid))for v in p)
        for row in self.continuation.manifest['objects']:
            sid=row['id'];kind=row['kind']
            if kind=='arc'and sid not in self.continuation.replaced_source_ids:
                node=sexpdata.loads(self.continuation.original_raw[slice(*row['source_span'])].decode());a=list(map(float,one(node,'start')));b=list(map(float,one(node,'end')));width=float(one(node,'width')[0]);entry=dict(source_id=sid,start=a,end=b,width=width,geometry=from_wkb(self.continuation.original[sid]))
                for point in (a,b):arc_bank[(round(width,6),*cell(point))].append(entry)
            elif kind=='gr_circle'and self.continuation.t01_current[sid]==self.continuation.original[sid]:
                node=sexpdata.loads(self.continuation.original_raw[slice(*row['source_span'])].decode())
                if str(one(node,'fill',[''])[0])not in ('yes','solid'):continue
                center=list(map(float,one(node,'center')));radius=math.dist(center,list(map(float,one(node,'end'))));circles[cell(center)].append((sid,center,radius))
        widths={};proofs=[]
        for i,obj in enumerate(before.objects):
            ap=getattr(obj,'aperture',None)
            if isinstance(obj,go.Line)and hasattr(ap,'diameter'):
                widths[i]=float(ap.diameter);continue
            if not isinstance(obj,go.Arc)or not hasattr(ap,'diameter'):widths[i]=0.;continue
            start=(obj.x1,-obj.y1);end=(obj.x2,-obj.y2);cx,cy=cell(start);matches=[]
            for dx in range(-2,3):
                for dy in range(-2,3):
                    for r in arc_bank[(round(float(ap.diameter),6),cx+dx,cy+dy)]:
                        error=min(max(math.dist(start,r['start']),math.dist(end,r['end'])),max(math.dist(start,r['end']),math.dist(end,r['start'])))
                        if error<=.000002+1e-12:
                            g=gerber.native_geometry(obj);tol=.000025
                            if r['geometry'].hausdorff_distance(g)<=tol and r['geometry'].symmetric_difference(g).area<=2*r['geometry'].length*tol+math.pi*tol**2:matches.append(r)
            center=(obj.x1+obj.cx,-obj.y1-obj.cy);cx,cy=cell(center);filled=[]
            for dx in (-1,0,1):
                for dy in (-1,0,1):
                    for sid,p,radius in circles[(cx+dx,cy+dy)]:
                        if abs(p[0]-center[0])<=.000001 and abs(p[1]-center[1])<=.000001 and abs(ap.diameter-radius)<=.000001 and abs(math.hypot(obj.cx,obj.cy)*2-radius)<=.000002:filled.append(sid)
            if filled:widths[i]=0.;basis='BOUND_NATIVE_FILLED_CIRCLE; no trace-port enlargement'
            elif matches:widths[i]=max(r['width']for r in matches);basis='BOUND_UNCHANGED_NATIVE_ARC_WIDTH'
            else:raise ValueError('C03_FIXED_ARC_NATIVE_ROLE_UNQUALIFIED:'+str(i))
            proofs.append(dict(plot_index=i,native_source_ids=sorted(set(filled+[r['source_id']for r in matches])),native_trace_width_mm=widths[i],basis=basis))
        return widths,proofs

    def plot_check(self,candidate_fcu=None,*,allow_probes=False):
        exported=self.continuation.read(self.out/'pcb_gerber_export.json');paths=exported['exports']
        for p,h in exported['output_sha256'].items():self.continuation.body(p,h)
        before=gerber.parse(paths['before']['F.Cu']);after=gerber.parse(candidate_fcu or paths['candidate']['F.Cu'])
        for plot in (before,after):
            if plot.file_attrs.get('.FileFunction')!=('Copper','L1','Top')or plot.file_attrs.get('.FilePolarity')!=('Positive',):raise ValueError('C03_FCU_FILE_ROLE_UNSUPPORTED')
            if any(not o.polarity_dark for o in plot.objects):raise ValueError('C03_FCU_CLEAR_POLARITY_UNSUPPORTED')
        # A fresh plot of the retained board must equal the retained final plot
        # on ALL nine layers, before it can be a predecessor in the checks.
        retained=self.continuation.read(self.continuation.predecessor/'data_output/pcb_gerber_export.json')['exports']['candidate'];role=lambda g:{k:v for k,v in g.file_attrs.items()if k not in ('.CreationDate','.ProjectId')}
        protected=[]
        for layer in LAYERS:
            b=before if layer=='F.Cu'else gerber.parse(paths['before'][layer]);r=gerber.parse(retained[layer])
            if role(b)!=role(r)or gerber.protected_counter(b.objects,set())!=gerber.protected_counter(r.objects,set()):raise ValueError('C03_RETAINED_U05_FRESH_PLOT_CORRESPONDENCE_FAILED:'+layer)
            if layer!='F.Cu':
                a=gerber.parse(paths['candidate'][layer])
                if role(a)!=role(b)or gerber.protected_counter(a.objects,set())!=gerber.protected_counter(b.objects,set()):raise ValueError('C03_PROTECTED_OTHER_LAYER_CHANGED:'+layer)
                protected.append(layer)
        regions=[(i,gerber.native_geometry(o))for i,o in enumerate(after.objects)if isinstance(o,go.Region)];tree=STRtree([g for _,g in regions]);excluded=set();actual={};proofs=[]
        for sid,g in sorted(self.targets.items()):
            expected,_=quantize(g);matches=[]
            for position in sorted(int(i)for i in tree.query(expected.envelope.buffer(.000002))):
                index,geom=regions[position]
                if index in excluded or any(abs(a-b)>.000002 for a,b in zip(geom.bounds,expected.bounds)):continue
                try:proof=fidelity(g,geom)
                except ValueError:continue
                matches.append((index,geom,proof))
            if not matches:raise ValueError('C03_WIDTH_POLYGON_NOT_IN_GERBER:'+sid)
            index,geom,proof=min(matches,key=lambda r:r[0]);excluded.add(index);actual[sid]=geom;proofs.append(dict(source_id=sid,plot_index=index,**proof))
        if gerber.protected_counter(before.objects,set())!=gerber.protected_counter(after.objects,excluded):raise ValueError('C03_PROTECTED_U05_FCU_ATOM_CHANGED')
        selected,binding=self.source_bindings(before,allow_probes=allow_probes);byid={p['source_id']:p['plot_index']for p in binding};base={s:gerber.native_geometry(before.objects[i])for s,i in byid.items()};traces=[]
        for row in self.candidate['construction']:
            members=row['complete_source_ids'];core=unary_union([base[s]for s in members]);candidate=core if row['factor']==1 else core.union(unary_union([actual[s]for s in members]))
            traces.append(dict(id=row['component_id'],original=core,candidate=candidate,verified_original_width_mm=row['verified_original_width_mm']))
        fixed=[];fixed_widths,fixed_width_proofs=self.fixed_width_bindings(before)
        for i,obj in enumerate(before.objects):
            if i in selected:continue
            width=fixed_widths[i]
            fixed.append(dict(id='retained-plot:'+str(i),geometry=gerber.native_geometry(obj),trace_width_mm=width))
        checked=PreparedWidthScene(traces,fixed).check(traces,materialize_scene=True,fail_fast=False);hard=actual_hard_floor(checked)
        if not hard['passed']:raise ValueError('C03_ACTUAL_WIDTH_HARD_GAP_REJECTED:'+str(hard['failures'][:4]))
        if any(t['candidate'].difference(t['original']).difference(self.domain).area>1e-12 for t in traces):raise ValueError('C03_ACTUAL_WIDTH_OUTSIDE_BOUNDARY')
        return dict(passed=True,all_U05_fcu_atoms_preserved=True,other_layers_preserved=protected,source_width_bindings=binding,fixed_arc_native_role_bindings=fixed_width_proofs,width_targets=proofs,actual_width_check=hard,retained_U05_fresh_plot_correspondence=True,all_fcu_primitives_positive=True,original_source_targets_unchanged=['C028','R304','R305'])

    def verify_gerber(self):
        proof=self.plot_check(allow_probes=True);return self.finish('pcb_gerber_verify',dict(verification=proof,facts=dict(passed=True,actual_hard_gap_mm=.02000,width_parts=len(self.targets),all_U05_fcu_atoms_preserved=True,protected_other_layers=8)))

    def control_operands(self):
        path=Path(self.continuation.read(self.out/'pcb_gerber_export.json')['exports']['candidate']['F.Cu']);blob=path.read_bytes();directory=self.out/'controls';result={}
        for name,old,new in [('wrong_units',b'%MOMM*%',b'%MOIN*%'),('clear_polarity',b'%LPD*%',b'%LPC*%'),('wrong_role',b'Copper,L1,Top',b'Copper,L2,Bot')]:result[name]=(directory/(name+'.gbr'),blob.replace(old,new,1))
        proof=self.continuation.read(self.out/'pcb_gerber_verify.json')['verification'];index=proof['width_targets'][0]['plot_index'];parsed=gerber.parse(path);ordinal=sum(isinstance(o,go.Region)for o in parsed.objects[:index]);span=list(re.finditer(rb'G36\*.*?G37\*',blob,re.S))[ordinal];result['missing_width']=(directory/'missing_width.gbr',blob[:span.start()]+blob[span.end():])
        before=sexpdata.loads(self.raw.decode());after=sexpdata.loads(self.board.read_text());idx=next(i for i,n in enumerate(before[1:],1)if isinstance(n,list)and str(n[0])in ('gr_poly','gr_circle','segment','arc'));after[idx].append([sexpdata.Symbol('property'),'c03-corruption','1']);result['protected_native_node']=(directory/'protected_changed.kicad_pcb',native.board_bytes(after))
        return result

    def controls(self):
        directory=self.out/'controls';directory.mkdir();controls=[]
        def reject(name,prefix,fn):
            try:fn()
            except ValueError as error:
                if not str(error).startswith(prefix):raise ValueError('C03_WRONG_NATIVE_CONTROL_REJECTION:'+name+':'+str(error))
                controls.append(dict(name=name,expected=prefix,error=str(error),status='PASS_EXPECTED_REJECTION'))
            else:raise ValueError('C03_NATIVE_CONTROL_NOT_REJECTED:'+name)
        path=Path(self.continuation.read(self.out/'pcb_gerber_export.json')['exports']['candidate']['F.Cu']);blob=path.read_bytes()
        for name,old,new,prefix in [('wrong_units',b'%MOMM*%',b'%MOIN*%','GERBER_PROFILE'),('clear_polarity',b'%LPD*%',b'%LPC*%','C03_FCU_CLEAR_POLARITY_UNSUPPORTED'),('wrong_role',b'Copper,L1,Top',b'Copper,L2,Bot','C03_FCU_FILE_ROLE_UNSUPPORTED')]:
            bad=directory/(name+'.gbr');fresh(bad,blob.replace(old,new,1));reject(name,prefix,(lambda p=bad:gerber.parse(p))if name=='wrong_units'else(lambda p=bad:self.plot_check(p)))
        proof=self.continuation.read(self.out/'pcb_gerber_verify.json')['verification'];index=proof['width_targets'][0]['plot_index'];parsed=gerber.parse(path);ordinal=sum(isinstance(o,go.Region)for o in parsed.objects[:index]);span=list(re.finditer(rb'G36\*.*?G37\*',blob,re.S))[ordinal];bad=directory/'missing_width.gbr';fresh(bad,blob[:span.start()]+blob[span.end():]);reject('missing_width','C03_WIDTH_POLYGON_NOT_IN_GERBER',lambda:self.plot_check(bad))
        before=sexpdata.loads(self.raw.decode());after=sexpdata.loads(self.board.read_text());idx=next(i for i,n in enumerate(before[1:],1)if isinstance(n,list)and str(n[0])in ('gr_poly','gr_circle','segment','arc'));after[idx].append([sexpdata.Symbol('property'),'c03-corruption','1']);badbody=native.board_bytes(after);fresh(directory/'protected_changed.kicad_pcb',badbody);reject('protected_native_node','C03_PROTECTED_U05_NATIVE_NODE_CHANGED',lambda:self.native_check(badbody))
        operands=self.control_operands()
        for control in controls:
            path,expected=operands[control['name']]
            if path.read_bytes()!=expected:raise ValueError('C03_NATIVE_CONTROL_OPERAND_CHANGED')
            control.update(mutation=str(path),mutation_sha256=digest(expected))
        return self.finish('pcb_export_controls',dict(controls=controls,facts=dict(passed=True,deliberate_controls=len(controls),all_rejected_for_expected_reason=True)))
