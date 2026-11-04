"""Append-only native U05 contours, actual before/after plots and hard-gap checks."""
import copy,re
from contextlib import nullcontext
from pathlib import Path
from importlib.metadata import version
import sexpdata
from shapely import from_wkb,to_wkb,STRtree,set_precision
from shapely.geometry import box
from shapely.ops import unary_union
from src.stage_abi.store import digest,canonical
from src.native_inventory import geometry
from src.native_reference import one
from src.pcb_data_abi import board_native as native,gerber
from src.pcb_data_abi.board_geometry import fidelity,quantize
from src.pcb_data_abi.geometry import CIRCLE_TOLERANCE_MM,POLYGON_TOLERANCE_MM
from src.pcb_data_abi.crop import TEMPLATE
from src.pcb_data_abi.service import DataService,CLI,CLI_SHA,LAYERS,GRID_MM,go,fresh,record
from src.junction_spindle_stage import CONTRACT,prepare_spindle_context
from src.junction_spindle_blend import check_spindle
from src.u03_board.selection import window
from tools.t01_operator_host import read
from .junctions import JunctionGates

NATIVE_OWNER_OVERLAP_MM=2*max(CIRCLE_TOLERANCE_MM,POLYGON_TOLERANCE_MM)

def export_region(addition,owner,window):
    # Duplicate only existing owner copper next to the addition. The physical
    # union is unchanged; the overlap prevents native clipping of razor tips.
    target=owner.union(addition)
    region=target.intersection(addition.buffer(NATIVE_OWNER_OVERLAP_MM,quad_segs=64)).intersection(window)
    support=region.difference(addition)
    if support.difference(owner).area>CONTRACT.area_epsilon_mm2 or addition.difference(region).area>CONTRACT.area_epsilon_mm2 or owner.union(region).symmetric_difference(target).area>CONTRACT.area_epsilon_mm2:raise ValueError('U05_NATIVE_SUPPORT_CHANGES_QUALIFIED_COPPER')
    return region,support

def actual_spindle_check(owner,regions,addition,window,foreign):
    # Test the physical plotted union directly. Re-subtracting and re-adding
    # owner copper can manufacture disconnected ULP-sized GEOS slivers.
    candidate=owner.union(unary_union(regions))
    return check_spindle(owner,candidate,addition,window,foreign,gap=CONTRACT.hard_gap_mm)

def require_positive_copper(*plots):
    if any(not obj.polarity_dark for plot in plots for obj in plot.objects):raise ValueError('U05_FCU_CLEAR_POLARITY_UNSUPPORTED')

class U05DataService(DataService):
    def finish(self,name,value):
        if name=='pcb_gerber_export' and hasattr(self.gates,'reference'):
            from .owner_plot import create
            value=dict(value,owner_source_plot=create(self))
        return super().finish(name,value)
    def __init__(self,root,gates=None):
        self.root=Path(root)
        if gates is None and (self.root/'U05_START.json').exists() and read(self.root/'U05_START.json').get('reference'):
            from .junctions import make_gates
            gates=make_gates(root)
        self.gates=gates if gates is not None else JunctionGates(root)
        if self.gates.root!=self.root:raise ValueError('U05_NATIVE_GATE_CONTEXT_ROOT_CHANGED')
        self.store=self.gates.store;self.candidate=self.gates.validate_verification();self.out=self.root/'data_output'
        self.raw=Path(self.gates.predecessor['kicad']).read_bytes();self.before=self.out/'before/board.kicad_pcb';self.board=self.out/'candidate/board.kicad_pcb';self.versions={k:version(k) for k in ('gerbonara','sexpdata','shapely')}
        if self.versions!={'gerbonara':'1.6.3','sexpdata':'1.0.2','shapely':'2.1.2'} or digest(CLI.read_bytes())!=CLI_SHA:raise ValueError('U05_PINNED_EXPORT_RUNTIME_CHANGED')
        if (self.out/'pcb_kicad_write.json').exists():
            written=read(self.out/'pcb_kicad_write.json')
            if digest(self.board.read_bytes())!=written['board_sha256'] or self.before.read_bytes()!=self.raw:raise ValueError('U05_NATIVE_SAVED_FILE_CHANGED')
        self.scene,self.policy,self.plan,_=self.gates.context();self.rows={r['source_id']:r for r in self.scene['objects']};self.targets={};self.owners={};self.normalization=[]
        with self.gates.adapter.execution(self.store,self.scene,self.policy) if hasattr(self.gates.adapter,'execution') else nullcontext():
            for d in self.candidate['decisions']:
                if d['status']!='GROWN':continue
                qualified=from_wkb(self.store.get(d['patch_ref'],kind='geometry'));owner,radius,domain,foreign=self.gates.adapter._operands(self.store,self.scene,self.policy,self.plan['details'],d);raw,support=export_region(qualified,owner,domain);q=set_precision(raw,GRID_MM,mode='valid_output');bound=2*raw.length*GRID_MM+__import__('math').pi*GRID_MM**2;area=raw.symmetric_difference(q).area
                if q.is_empty or not q.is_valid or q.geom_type not in ('Polygon','MultiPolygon') or area>bound:raise ValueError('U05_PATCH_FILE_GRID_NORMALIZATION_FAILED')
                pieces=[q] if q.geom_type=='Polygon' else list(q.geoms)
                self.normalization.append(dict(source_id=d['source_id'],qualified_ref=d['patch_ref'],existing_owner_support_area_mm2=support.area,owner_overlap_mm=NATIVE_OWNER_OVERLAP_MM,physical_union_changed=False,grid_mm=GRID_MM,mode='valid_output',area_change_mm2=area,area_bound_mm2=bound,resolvable_components=len(pieces),resolvable_holes=sum(len(p.interiors) for p in pieces)))
                for i,p in enumerate(sorted(pieces,key=to_wkb)):
                    sid=d['source_id']+':patch:'+str(i);self.targets[sid]=p;self.owners[sid]=d['source_id']

    def native_body(self):
        template=native.edit_template(TEMPLATE);nodes=[native.polygon_node(g,template,sid,digest(to_wkb(g)))[0] for sid,g in sorted(self.targets.items())]
        prefix=self.raw.rstrip()
        if not prefix.endswith(b')'):raise ValueError('U05_NATIVE_ROOT_TERMINATOR_REQUIRED')
        return prefix[:-1]+b'\n'+b'\n'.join(('  '+native.encode(n)).encode() for n in nodes)+b'\n)\n'

    def native_check(self,body):
        before=sexpdata.loads(self.raw.decode());after=sexpdata.loads(body.decode());expected=sexpdata.loads(self.native_body().decode())
        if len(after)!=len(before)+len(self.targets) or after[:len(before)]!=before:raise ValueError('U05_U04_NATIVE_NODE_CHANGED')
        if after!=expected:raise ValueError('U05_NATIVE_APPEND_RECONSTRUCTION_FAILED')
        proofs=[]
        for index,(sid,g) in enumerate(sorted(self.targets.items()),len(before)):
            node=after[index]
            if str(node[0])!='gr_poly' or str(one(node,'layer',[''])[0])!='F.Cu':raise ValueError('U05_JUNCTION_NATIVE_ROLE_CHANGED')
            proofs.append(dict(source_id=sid,node_index=index,**fidelity(g,geometry(node,'gr_poly'))))
        return dict(passed=True,all_U04_nodes_equal=True,junction_parts=len(proofs),targets=proofs)

    def write_kicad(self):
        self.out.mkdir();(self.out/'before').mkdir();(self.out/'candidate').mkdir();body=self.native_body();proof=self.native_check(body);fresh(self.before,self.raw);fresh(self.board,body)
        return self.finish('pcb_kicad_write',dict(board=str(self.board),board_sha256=digest(body),predecessor_sha256=digest(self.raw),versions=self.versions,normalization=self.normalization,verification=proof,facts=dict(passed=True,all_U04_nodes_equal=True,junction_parts=len(self.targets))))

    def verify_kicad(self):
        saved=read(self.out/'pcb_kicad_write.json')
        if digest(self.board.read_bytes())!=saved['board_sha256'] or self.before.read_bytes()!=self.raw or saved['normalization']!=self.normalization:raise ValueError('U05_NATIVE_SAVED_FILE_CHANGED')
        proof=self.native_check(self.board.read_bytes());return self.finish('pcb_kicad_verify',dict(verification=proof,facts=dict(passed=True,all_U04_nodes_equal=True,junction_parts=len(self.targets))))

    def _before(self):
        exported=read(self.out/'pcb_gerber_export.json');paths=exported['exports'];key=tuple((p,digest(Path(p).read_bytes())) for p in paths['before'].values())
        for p,h in key:
            if exported['output_sha256'][p]!=h:raise ValueError('U05_BEFORE_PLOT_CHANGED')
        if getattr(self,'_before_key',None)==key:return self._before_context
        before=gerber.parse(paths['before']['F.Cu']);geometries=[gerber.native_geometry(o) for o in before.objects];tree=STRtree(geometries)
        old=read(Path(self.gates.predecessor['root'])/'data_output/pcb_gerber_export.json')['exports']['candidate']
        for layer in LAYERS:
            fresh_plot=before if layer=='F.Cu' else gerber.parse(paths['before'][layer]);retained=gerber.parse(old[layer]);role=lambda g:{k:v for k,v in g.file_attrs.items() if k not in ('.CreationDate','.ProjectId')}
            if role(fresh_plot)!=role(retained) or gerber.protected_counter(fresh_plot.objects,set())!=gerber.protected_counter(retained.objects,set()):raise ValueError('U05_RETAINED_U04_PLOT_CORRESPONDENCE_FAILED:'+layer)
        self._before_key=key;self._before_context=(before,geometries,tree);return self._before_context

    def owner_indices(self,before,geometries,tree,row):
        selected=set();sid=row['source_id'];owners=[sid,*row['land_ids']]
        if not hasattr(self,'owner_primitive_bindings'):self.owner_primitive_bindings={}
        if not hasattr(self,'_owner_native_tree'):self._owner_native_tree=sexpdata.loads(self.raw.decode())
        source_plot=None
        if hasattr(self.gates,'reference'):
            from .owner_plot import binding,plot_atom
            source_plot=getattr(self,'_plot_source_binding',None) or binding(self)
            if not hasattr(self,'_before_atom_index'):
                self._before_atom_index={}
                for i,o in enumerate(before.objects):self._before_atom_index.setdefault(digest(canonical(plot_atom(o))),[]).append(i)
        def match(g,count,kinds):
            if set(kinds)=={'gr_circle'}:
                cx,cy=g.centroid.coords[0];radius=(g.bounds[2]-g.bounds[0]+g.bounds[3]-g.bounds[1])/4;indices=gerber.circle_indices(before.objects,[cx,cy],radius)
                if len(indices)!=2*count:raise ValueError('U05_NATIVE_CIRCLE_OWNER_MEMBERSHIP_FAILED')
                return set(indices)
            expected=quantize(g)[0];exact=[];bounded=[]
            for i in sorted(map(int,tree.query(expected.envelope.buffer(.000002)))):
                if i in selected or geometries[i].is_empty or any(abs(a-b)>.000002 for a,b in zip(expected.bounds,geometries[i].bounds)):continue
                try:fidelity(g,geometries[i])
                except ValueError:continue
                (exact if expected.equals(set_precision(geometries[i],GRID_MM,mode='valid_output')) else bounded).append(i)
            if len(exact)>=count:return set(exact[:count])
            if len(exact)+len(bounded)!=count:raise ValueError('U05_NATIVE_OWNER_PLOT_BINDING_AMBIGUOUS')
            return set(exact+bounded)
        for owner in owners:
            obj=self.rows[owner];md=obj['metadata']
            if obj['kind']=='trace':
                for source,ref in sorted(md['native_part_refs'].items()):
                    shape=from_wkb(self.store.get(ref,kind='geometry'));kind=md['native_part_kinds'][source]
                    if kind in ('segment','gr_line','arc','gr_arc'):
                        from .stroke_owner import primitive_match,stroke_fidelity,STROKE_GEOMETRY_BOUND_MM
                        source_row=self.rows.get(source);index=source_row['metadata']['native_node_indices'][0] if source_row else md['native_node_indices'][sorted(md['native_part_refs']).index(source)];node=self._owner_native_tree[index];matches=[]
                        if str(node[0])!=kind:raise ValueError('U05_NATIVE_STROKE_KIND_CHANGED')
                        if source_plot is not None:
                            key=digest(canonical(source_plot['bindings'][source]['exact_plot_atom']));matches=[i for i in self._before_atom_index.get(key,[]) if i not in selected]
                        else:
                            for i in sorted(map(int,tree.query(shape.envelope.buffer(STROKE_GEOMETRY_BOUND_MM)))):
                                if i not in selected and primitive_match(node,before.objects[i]):
                                    stroke_fidelity(shape,geometries[i]);matches.append(i)
                        if not matches:raise ValueError('U05_NATIVE_STROKE_PLOT_MEMBERSHIP_FAILED:'+source)
                        chosen=min(matches);selected.add(chosen);self.owner_primitive_bindings[source]=dict(native_node_index=index,native_node_sha256=digest(native.encode(node).encode()),source_kind=kind,plot_index=chosen,primitive_identity_passed=True,exact_fresh_source_plot_atom=source_plot is not None,geometry=stroke_fidelity(shape,geometries[chosen]))
                    else:selected.update(match(shape,1,[kind]))
            else:
                aliases=md['alias_source_ids'];selected.update(match(from_wkb(self.store.get(obj['geometry_ref'],kind='geometry')),len(aliases),md['native_node_kinds']))
        return selected

    def plot_check(self,candidate_fcu=None):
        exported=read(self.out/'pcb_gerber_export.json');paths=exported['exports']
        for path,h in exported['output_sha256'].items():
            if digest(Path(path).read_bytes())!=h:raise ValueError('U05_EXPORTED_GERBER_CHANGED')
        before,before_shapes,tree=self._before();after=gerber.parse(candidate_fcu or paths['candidate']['F.Cu'])
        require_positive_copper(before,after)
        if hasattr(self.gates,'reference'):
            from .owner_plot import binding
            self._plot_source_binding=binding(self)
        if any(g.file_attrs.get('.FileFunction')!=('Copper','L1','Top') or g.file_attrs.get('.FilePolarity')!=('Positive',) for g in (before,after)):raise ValueError('FCU_FILE_ROLE_UNSUPPORTED')
        regions=[(i,gerber.native_geometry(o)) for i,o in enumerate(after.objects) if isinstance(o,go.Region)];rt=STRtree([g for _,g in regions]);excluded=set();target_geometries={};proofs=[];actual_by_owner={}
        for sid,reference in sorted(self.targets.items()):
            expected=quantize(reference)[0];matches=[]
            for k in sorted(map(int,rt.query(expected.envelope.buffer(.000002)))):
                i,g=regions[k]
                if i in excluded or any(abs(a-b)>.000002 for a,b in zip(expected.bounds,g.bounds)):continue
                try:proof=fidelity(reference,g)
                except ValueError:continue
                matches.append((i,g,proof))
            if not matches:raise ValueError('U05_JUNCTION_POLYGON_NOT_IN_GERBER:'+sid)
            i,g,proof=min(matches,key=lambda r:r[0]);excluded.add(i);target_geometries[sid]=g;actual_by_owner.setdefault(self.owners[sid],[]).append(g);proofs.append(dict(source_id=sid,plot_index=i,**proof))
        if gerber.protected_counter(before.objects,set())!=gerber.protected_counter(after.objects,excluded):raise ValueError('U05_PROTECTED_U04_FCU_CHANGED')
        protected=[]
        for layer in LAYERS[1:]:
            a=gerber.parse(paths['candidate'][layer]);b=gerber.parse(paths['before'][layer]);role=lambda g:{k:v for k,v in g.file_attrs.items() if k not in ('.CreationDate','.ProjectId')}
            if role(a)!=role(b) or gerber.protected_counter(a.objects,set())!=gerber.protected_counter(b.objects,set()):raise ValueError('U05_PROTECTED_LAYER_CHANGED:'+layer)
            protected.append(layer)
        before_copper=unary_union(before_shapes);patches=[];crop=window(self.gates.selection) if self.gates.selection else box(*self.scene['viewport_mm'])
        for decision in self.candidate['decisions']:
            if decision['status']!='GROWN':continue
            indices=self.owner_indices(before,before_shapes,tree,decision);owner=unary_union([before_shapes[i] for i in sorted(indices)]);native_owner=from_wkb(self.store.get(self.rows[decision['source_id']]['geometry_ref'],kind='geometry'));lands=[from_wkb(self.store.get(self.rows[s]['geometry_ref'],kind='geometry')) for s in decision['land_ids']];_,_,domain=prepare_spindle_context(native_owner,lands,box(*self.scene['viewport_mm']));addition=unary_union(actual_by_owner[decision['source_id']]).difference(before_copper);foreign=[('plot:'+str(i),before_shapes[i]) for i in sorted(map(int,tree.query(domain.buffer(CONTRACT.barrier_gap_mm+.000025)))) if i not in indices]
            if addition.area<=CONTRACT.minimum_visible_addition_mm2:raise ValueError('U05_ACTUAL_VISIBLE_SPINDLE_NOT_ESTABLISHED')
            scope=self.gates.adapter.scope(decision) if hasattr(self.gates.adapter,'scope') else crop
            if addition.difference(scope).area>CONTRACT.area_epsilon_mm2:raise ValueError('U05_NATIVE_ADDITION_OUTSIDE_CROP')
            patches.append(dict(id=decision['source_id'],owner=owner,regions=actual_by_owner[decision['source_id']],addition=addition,window=domain.buffer(2*GRID_MM),foreign=foreign,owner_plot_indices=sorted(indices)))
        actual_checks=[]
        for p in patches:
            q=actual_spindle_check(p['owner'],p['regions'],p['addition'],p['window'],p['foreign']+[(other['id'],other['addition']) for other in patches if other['id']!=p['id']])
            if not q['passed']:raise ValueError('U05_ACTUAL_GERBER_SPINDLE_CHECK_FAILED:'+str(q['failures']))
            actual_checks.append(dict(source_id=p['id'],owner_plot_indices=p['owner_plot_indices'],check=q))
        result=dict(passed=True,junction_parts=len(proofs),targets=proofs,all_fcu_primitives_positive=True,protected_fcu_atoms_equal=True,protected_layers_equal=protected,actual_hard_gap_mm=CONTRACT.hard_gap_mm,actual_spindle_checks=actual_checks,retained_U04_fresh_plot_correspondence=True,added_target_regions=len(excluded),owner_primitive_bindings=getattr(self,'owner_primitive_bindings',{}))
        if hasattr(self.gates,'reference'):
            from .attachment_export import verify_attachments
            result['attachment_coverage']=verify_attachments(self,before_shapes,tree,actual_by_owner)
            if binding(self)!=self._plot_source_binding:raise ValueError('U05_OWNER_SOURCE_PLOT_CHANGED_DURING_CHECK')
        return result,target_geometries,after

    def verify_gerber(self):
        exported=read(self.out/'pcb_gerber_export.json')
        for p,h in exported['output_sha256'].items():
            if digest(Path(p).read_bytes())!=h:raise ValueError('U05_EXPORTED_GERBER_CHANGED')
        q,_,_=self.plot_check();facts=dict(passed=True,junction_parts=q['junction_parts'],actual_hard_gap_mm=q['actual_hard_gap_mm'],protected_other_layers=8,protected_U04_fcu=True)
        if 'attachment_coverage' in q:facts.update({k:v for k,v in q['attachment_coverage'].items() if k not in ('records','reference_witnesses')})
        return self.finish('pcb_gerber_verify',dict(verification=q,facts=facts))

    def controls(self):
        if not read(self.out/'pcb_gerber_verify.json')['facts']['passed']:raise ValueError('U05_GERBER_VERIFY_REQUIRED')
        folder=self.out/'controls';folder.mkdir();results=[]
        def expect(name,prefix,path,fn):
            try:fn()
            except ValueError as error:
                if not str(error).startswith(prefix):raise
                results.append(dict(name=name,expected=prefix,error=str(error),path=str(path),sha256=digest(path.read_bytes()),status='PASS_EXPECTED_REJECTION'))
            else:raise ValueError('U05_EXPORT_CONTROL_NOT_REJECTED:'+name)
        blob=Path(read(self.out/'pcb_gerber_export.json')['exports']['candidate']['F.Cu']).read_bytes();bad=folder/'wrong_units.gbr';fresh(bad,blob.replace(b'%MOMM*%',b'%MOIN*%',1));expect('units','GERBER_PROFILE',bad,lambda:gerber.parse(bad))
        role=folder/'wrong_role.gbr';fresh(role,blob.replace(b'Copper,L1,Top',b'Copper,L2,Bot',1));expect('role','FCU_FILE_ROLE_UNSUPPORTED',role,lambda:self.plot_check(role))
        body=sexpdata.loads(self.board.read_text());body[1].append([sexpdata.Symbol('u05_corrupt'),'1']);badbody=native.board_bytes(body);path=folder/'changed_U04.kicad_pcb';fresh(path,badbody);expect('protected_U04','U05_U04_NATIVE_NODE_CHANGED',path,lambda:self.native_check(badbody))
        measured,_,parsed=self.plot_check()
        if self.targets:
            index=measured['targets'][0]['plot_index'];which=sum(isinstance(o,go.Region) for o in parsed.objects[:index]);span=list(re.finditer(rb'G36\*.*?G37\*',blob,re.S))[which];missing=folder/'missing_spindle.gbr';fresh(missing,blob[:span.start()]+blob[span.end():]);expect('missing_spindle','U05_JUNCTION_POLYGON_NOT_IN_GERBER',missing,lambda:self.plot_check(missing))
            if hasattr(self.gates,'reference'):
                clear=folder/'clear_spindle.gbr';fresh(clear,blob[:span.start()]+b'%LPC*%\n'+blob[span.start():span.end()]+b'\n%LPD*%\n'+blob[span.end():]);expect('clear_polarity','U05_FCU_CLEAR_POLARITY_UNSUPPORTED',clear,lambda:self.plot_check(clear))
        return self.finish('pcb_export_controls',dict(controls=results,facts=dict(passed=True,deliberate_controls=len(results),all_rejected_for_expected_reason=True)))
