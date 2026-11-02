"""Native qualification of every explicitly supplied Gerber layer; no display work."""
from pathlib import Path
from src.stage_abi.store import digest
from .board_scope import BoardScopeService
from .input_directory import verify_snapshot,layer_role
from .roi import local,read,fresh,CLI
from .gerber import parse,protected_counter

class DirectoryScopeService(BoardScopeService):
    def __init__(self,host):
        if set(host)!={'schema','inputs','output','directory_manifest','directory_manifest_sha256'}or host['schema']!='pcb-board-directory-host/1':raise ValueError('DIRECTORY_SOURCE_HOST_INVALID')
        path=local(host['directory_manifest'])
        if digest(path.read_bytes())!=host['directory_manifest_sha256']:raise ValueError('INPUT_DIRECTORY_MANIFEST_CHANGED')
        self.directory=read(path);self.paths=verify_snapshot(self.directory,path.parent/'raw_inputs')
        if {k:dict(path=str(self.paths[v]),sha256=digest(self.paths[v].read_bytes()))for k,v in [('kicad','kicad'),('gerber','F.Cu')]}!=host['inputs']:raise ValueError('INPUT_DIRECTORY_SOURCE_BINDING_CHANGED')
        super().__init__(dict(schema='pcb-board-source-host/1',inputs=host['inputs'],output=host['output']))

    def command(self,argv,stem):
        # KiCad may write .kicad_prl beside an input board while exporting. Keep
        # that native workspace outside the immutable raw-input snapshot.
        argv=list(argv);work=None
        if argv[1:4]==['pcb','export','gerbers']and Path(argv[-1])==self.inputs['kicad']:
            directory=self.out/'native_source_work';directory.mkdir(exist_ok=True);work=directory/'board.kicad_pcb'
            original=self.inputs['kicad'].read_bytes()
            if not work.exists():
                with work.open('xb')as stream:stream.write(original)
            if work.read_bytes()!=original:raise ValueError('DIRECTORY_NATIVE_WORK_COPY_CHANGED')
            argv[-1]=work
        result=super().command(argv,stem)
        if work is not None and work.read_bytes()!=original:raise ValueError('DIRECTORY_NATIVE_EXPORT_CHANGED_BOARD')
        return result

    def verify_inputs(self):
        if getattr(self,'directory',{}).get('schema')=='pcb-raw-input-directory/2':return self.verify_raw_inputs()
        result=super().verify_inputs();provided={k:v for k,v in self.paths.items()if k!='kicad'}
        matches=[dict(layer='F.Cu',supplied=str(provided['F.Cu']),generated=result['generated_source_gerber'],passed=True)]
        extra=set(provided)-{'F.Cu'}
        if extra:
            out=self.out/'additional_source_layers';out.mkdir()
            self.command([CLI,'pcb','export','gerbers','--layers',','.join(sorted(extra)),'--precision','6','--no-protel-ext','-o',str(out)+'/',self.inputs['kicad']],'additional_source_export')
            generated={}
            for path in out.glob('*.gbr'):
                role=layer_role(path.read_bytes())
                if role in generated:raise ValueError('DIRECTORY_NATIVE_EXPORT_ROLE_AMBIGUOUS')
                generated[role]=path
            if set(generated)!=extra:raise ValueError('DIRECTORY_NATIVE_EXPORT_LAYER_SET_MISMATCH')
            for layer in sorted(extra):
                a,b=parse(provided[layer]),parse(generated[layer])
                attrs=lambda g:{k:v for k,v in g.file_attrs.items()if k not in('.CreationDate','.ProjectId')}
                if attrs(a)!=attrs(b)or protected_counter(a.objects,set())!=protected_counter(b.objects,set()):raise ValueError('INPUT_DIRECTORY_KICAD_GERBER_MISMATCH:'+layer)
                matches.append(dict(layer=layer,supplied=str(provided[layer]),generated=str(generated[layer]),passed=True))
        result=dict(result,facts=dict(result['facts'],provided_gerber_files=len(provided),all_supplied_layers_verified=True,source_origin='Explicit directory; fresh staged raw bytes; no project defaults'),directory_layer_matches=matches)
        fresh(self.out/'directory_inputs_verified.json',result);return result

    def verify_raw_inputs(self):
        """Recheck original raw bytes against a separate fresh native plot.

        This profile does not relax or replace the original exact-X2 route.
        Companions have no geometry authority and are separately accounted for.
        """
        import sexpdata
        from shapely import affinity
        from shapely.geometry import Point,GeometryCollection
        from src.native_inventory import inventory
        from src.native_reference import one
        from .raw_directory import parse_raw,image,compare_images
        from .service import plot_name
        self.out.mkdir();raw=self.inputs['kicad'].read_bytes();inv=inventory(raw)
        rows=[r for r in inv['objects']if 'F.Cu'in r['layers']]
        allowed={'segment','arc','gr_line','gr_arc','gr_circle','gr_rect','gr_poly'}
        if not rows:raise ValueError('PCB_ROI_NO_FCU_SOURCE')
        for row in rows:
            if not row['geometry_sha256']or row['kind']not in allowed or row['parent_id']is not None or row['unresolved_layers']:raise ValueError('PCB_BOARD_NATIVE_PROFILE_UNSUPPORTED:'+row['id'])
            node=sexpdata.loads(raw[slice(*row['source_span'])].decode())
            width=one(node,'width',None)if row['kind']in('segment','arc')else one(one(node,'stroke',[]),'width',None)
            row['trace_width_mm']=float(width[0])if width else 0.
            if row['kind']in('segment','arc')and row['trace_width_mm']<=0:raise ValueError('PCB_ROI_SOURCE_TRACE_WIDTH_UNSUPPORTED')
        (self.out/'source_wkb').mkdir()
        for h in sorted({r['geometry_sha256']for r in rows}):(self.out/'source_wkb'/(h+'.wkb')).write_bytes(inv['payloads'][h])
        fresh(self.out/'source_manifest.json',dict(source_sha256=inv['source_sha256'],objects=rows))
        provided={k:v for k,v in self.paths.items()if k!='kicad'};plot=self.out/'source_plot';plot.mkdir()
        if self.command([CLI,'version'],'version')!='10.99.0':raise ValueError('KICAD_VERSION_CHANGED')
        self.command([CLI,'pcb','export','gerbers','--layers',','.join(sorted(provided)),'--precision','6','--no-protel-ext','-o',str(plot)+'/',self.inputs['kicad']],'source_export')
        if {p.name for p in plot.glob('*.gbr')}!={plot_name(l)for l in provided}:raise ValueError('DIRECTORY_NATIVE_EXPORT_LAYER_SET_MISMATCH')
        matches=[];controls=[]
        for layer,path in sorted(provided.items()):
            _,objects,profile=parse_raw(path.read_bytes(),str(path));_,native_objects,_=parse_raw((plot/plot_name(layer)).read_bytes(),plot_name(layer))
            a,b=image(objects),image(native_objects);measurement=compare_images(a,b,profile['correspondence_tolerance_mm'])
            proof=next(r for r in self.directory['identification']['matches']if r['layer']==layer)
            if profile!=proof['profile']or not measurement['passed']:raise ValueError('INPUT_DIRECTORY_KICAD_GERBER_MISMATCH:'+layer)
            matches.append(dict(layer=layer,supplied=str(path),generated=str(plot/plot_name(layer)),passed=True,profile=profile,measurement=measurement))
            if layer=='F.Cu':
                for name,changed in [('empty_source',GeometryCollection()),('shifted_source',affinity.translate(a,xoff=max(.02,10*profile['correspondence_tolerance_mm']))),('added_remote_feature',a.union(Point(a.bounds[2]+1,a.bounds[3]+1).buffer(.01)))]:
                    result=compare_images(changed,b,profile['correspondence_tolerance_mm'])
                    if result['passed']:raise ValueError('RAW_SOURCE_CONTROL_NOT_REJECTED:'+name)
                    controls.append(dict(name=name,status='PASS_EXPECTED_REJECTION',measurement=result))
        companions=[r for r in self.directory['files']if r['kind']=='companion']
        if len(matches)+len(companions)+1!=len(self.directory['files']):raise ValueError('RAW_SOURCE_COVERAGE_ACCOUNTING_FAILED')
        result=dict(facts=dict(passed=True,source_objects=len(rows),source_gerber_correspondence=True,registration_fit_used=False,layer='F.Cu',construction_status='NOT_RUN',provided_gerber_files=len(provided),all_supplied_layers_verified=True,total_raw_gerber_files=len(provided)+len(companions),all_participating_layers_verified=True,excluded_companion_files=len(companions),companion_geometry_qualification='NOT_ESTABLISHED; explicitly excluded',complete_input_accounting=True,source_origin='Explicit directory; original raw bytes; native geometry identification; excluded companions retained unchanged'),inputs=self.host['inputs'],manifest_sha256=digest((self.out/'source_manifest.json').read_bytes()),generated_source_gerber=str(plot/plot_name('F.Cu')),generated_source_gerber_sha256=digest((plot/plot_name('F.Cu')).read_bytes()),scope='Source-image correspondence within recorded input coordinate/arc bounds; no frame fitting or electrical intent; companions excluded',directory_layer_matches=matches,excluded_companions=companions,correspondence_controls=controls)
        fresh(self.out/'inputs.json',result);fresh(self.out/'directory_inputs_verified.json',result);return result

