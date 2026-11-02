"""Complete tiled native display of audited whole-board T01 exports."""
import html,json,math,time,xml.etree.ElementTree as ET
from importlib.metadata import version
from pathlib import Path
from PIL import Image,ImageDraw,ImageOps
from shapely.geometry import box
from shapely import affinity
from shapely.ops import unary_union
from src.stage_abi.store import digest,canonical
from src.pcb_data_abi.board_custody import validate_host
from .service import RenderService,read,fresh,local,bound_bytes,CLI,SIPS,ROOT
from .geometry import native_copper,gerber_copper
from .view import crop_svg,verify_svg_view,raster_fidelity,FOREGROUND,BACKGROUND
from .board_tiles import tile_plan
from .board_gerber_svg import gerber_svg


def audit_tile(path,geometry,bounds,size,error):
    # The old crop audit intentionally rejects uniform images. Board partitions
    # can be provably empty or fully covered; permit only those analytic cases.
    if geometry.geom_type=='GeometryCollection':
        # Rectangle clipping may leave zero-area tangencies alongside polygons.
        # A collection's boundary is undefined: audit the exact finite-area set,
        # never permit NaN distances to stand for a successful boundary check.
        def polygons(g):
            if g.geom_type=='Polygon':return [g]
            return [p for child in getattr(g,'geoms',[])for p in polygons(child)]
        surface=unary_union(polygons(geometry))
        if geometry.symmetric_difference(surface).area!=0:raise ValueError('BOARD_RASTER_REFERENCE_AREA_CHANGED')
        geometry=surface
    if not geometry.is_valid:raise ValueError('BOARD_RASTER_REFERENCE_INVALID')
    with Image.open(path)as image:
        if image.size!=tuple(size)or image.format!='PNG':raise ValueError('RASTER_DIMENSIONS_OR_FORMAT_MISMATCH')
        import numpy as np
        rgba=np.asarray(image.convert('RGBA'),dtype=np.int16)
    if np.any(rgba[:,:,3]!=255):raise ValueError('OPAQUE_RASTER_REQUIRED')
    foreground=(rgba[:,:,0]>100)&(rgba[:,:,0]-rgba[:,:,2]>50)
    window=box(*bounds)
    if geometry.is_empty or geometry.area==0:
        if foreground.any():raise ValueError('RASTER_FIDELITY_EXCEEDED:foreground_without_finite_copper')
        uniform_proven=True
    else:
        uniform_proven=(not foreground.any()and geometry.disjoint(window) or foreground.all()and geometry.covers(window))
    if uniform_proven:
        return dict(passed=True,pixels_checked=size[0]*size[1],foreground_pixels=int(foreground.sum()),mismatch_pixels=0,maximum_mismatch_distance_mm=0.,allowed_boundary_error_mm=error,mismatches_outside_band=0,pixel_pitch_mm=[(bounds[2]-bounds[0])/size[0],(bounds[3]-bounds[1])/size[1]],uniform_tile_analytic_proof=True)
    return raster_fidelity(path,geometry,bounds,size,error)


def tile_page(folder,tile):
    b=html.escape(str(tile['bounds_mm']))
    (folder/'index.html').write_text('''<!doctype html><meta charset="utf-8"><title>T01 board detail</title><style>body{font:16px system-ui;background:#eef3f7;color:#152a40}.pair{display:grid;grid-template-columns:1fr 1fr;gap:16px}.view{overflow:hidden;touch-action:none}.view img{width:100%;display:block;transform-origin:0 0;pointer-events:none}</style><h1>T01 board detail / '''+tile['id']+'''</h1><p>Candidate KiCad versus candidate Gerber. Native mm bounds: '''+b+'''</p><p><a href="../../index.html">Board overview and complete tile index</a> · <a href="audit.json">Separate pixel audit</a>. Owner PENDING_USER.</p><label>Linked zoom <input id="zoom" type="range" min="1" max="6" step=".25" value="1"></label><button id="reset">Reset</button><div class="pair"><section><h2>KiCad / native SVG</h2><div class="view"><img src="kicad.png"></div></section><section><h2>Gerber / parsed SVG</h2><div class="view"><img src="gerber.png"></div></section></div><script>const vs=[...document.querySelectorAll('.view')],z=document.querySelector('#zoom');let s=1,x=0,y=0,drag=null;function apply(){x=Math.min(0,Math.max(1-s,x));y=Math.min(0,Math.max(1-s,y));vs.forEach(v=>v.firstElementChild.style.transform=`translate(${x*100}%,${y*100}%) scale(${s})`)}z.oninput=()=>{s=Number(z.value);apply()};document.querySelector('#reset').onclick=()=>{s=1;x=y=0;z.value=1;apply()};vs.forEach(v=>{v.onpointerdown=e=>{drag=[e.clientX,e.clientY,x,y];v.setPointerCapture(e.pointerId)};v.onpointerup=v.onpointercancel=()=>drag=null;v.onpointermove=e=>{if(drag){const r=v.getBoundingClientRect();x=drag[2]+(e.clientX-drag[0])/r.width;y=drag[3]+(e.clientY-drag[1])/r.height;apply()}}});</script>''')


class BoardRenderService(RenderService):
    def __init__(self,host):
        root=validate_host(host,'render');self.contract_path=local(host['contract_path'])
        if self.contract_path.parent!=root:raise ValueError('BOARD_RENDER_CONTRACT_SCOPE')
        self.contract_blob=bound_bytes(self.contract_path,host['contract_sha256']);self.contract=json.loads(self.contract_blob)
        scope=read(root/'data_board/verified.json');reference=read(ROOT/'contracts/render/board.json');mutable={'bounds_mm','pixels','tiles','inputs'}
        if {k:v for k,v in self.contract.items()if k not in mutable}!={k:v for k,v in reference.items()if k not in mutable}:raise ValueError('BOARD_RENDER_POLICY_CHANGED')
        self.plan=tile_plan(scope['bounds_mm'],reference['tile_policy'])
        if self.contract['tiles']!=self.plan or self.contract['bounds_mm']!=scope['bounds_mm']or self.contract['pixels']is not None:raise ValueError('BOARD_RENDER_COVERAGE_MISMATCH')
        exports={'kicad':root/'data_output/candidate/board.kicad_pcb','gerber':root/'data_output/candidate/gerbers/board-F_Cu.gbr'}
        if self.contract['inputs']!={k:dict(path=str(p.relative_to(ROOT)),sha256=digest(p.read_bytes()))for k,p in exports.items()}:raise ValueError('BOARD_RENDER_EXPORT_MISMATCH')
        self.versions={n:version(n)for n in self.contract['dependencies']}
        if self.versions!=self.contract['dependencies']:raise ValueError('RENDER_DEPENDENCY_VERSION_CHANGED')
        self.out=local(host['output']);self.inputs={k:local(ROOT/v['path'])for k,v in self.contract['inputs'].items()};self.bounds=scope['bounds_mm'];self.check_inputs()
        if digest(CLI.read_bytes())!=self.contract['cli_sha256']:raise ValueError('RENDER_KICAD_EXECUTABLE_CHANGED')
    def progress(self,phase,index):
        # Append-only native progress receipts, never heartbeat claims of work.
        fresh(self.root_out/(f'{phase}-{index:04d}.progress.json'),dict(phase=phase,completed_tiles=index,total_tiles=len(self.plan['tiles']),at=time.time()))
    def render(self):
        self.out.mkdir();self.root_out=self.out
        if self.command([CLI,'version'],'kicad_version')!=self.contract['cli_version']:raise ValueError('RENDER_KICAD_VERSION_CHANGED')
        if self.command([SIPS,'--version'],'sips_version')!=self.contract['sips_version']:raise ValueError('RENDER_SIPS_VERSION_CHANGED')
        gerber_copper(self.inputs['gerber'],self.bounds)
        gerber_source=self.out/'parsed_gerber.svg';gerber_plot=gerber_svg(self.inputs['gerber'],gerber_source)
        fresh(self.out/'gerber_vector.json',gerber_plot)
        self.command([CLI,'pcb','export','svg','--layers','F.Cu','--exclude-drawing-sheet','--page-size-mode','0','--mode-single','-o',self.out/'native_board.svg',self.inputs['kicad']],'kicad_svg')
        source=self.out/'native_board.svg';(self.out/'tiles').mkdir();fresh(self.out/'tile_plan.json',self.plan)
        for index,tile in enumerate(self.plan['tiles'],1):
            self.out=self.root_out/'tiles'/tile['id'];self.out.mkdir();bounds,size=tile['bounds_mm'],tile['pixels']
            crop_svg(source,self.out/'kicad.svg',bounds,size)
            self.command([SIPS,'-s','format','png',self.out/'kicad.svg','--out',self.out/'kicad.png'],'svg_png')
            crop_svg(gerber_source,self.out/'gerber.svg',bounds,size)
            self.command([SIPS,'-s','format','png',self.out/'gerber.svg','--out',self.out/'gerber.png'],'gerber_svg_png')
            tile_page(self.out,tile);self.progress('render',index)
        self.out=self.root_out;self.present();self.check_inputs()
        files={str(p.relative_to(self.out)):digest(p.read_bytes())for p in sorted(self.out.rglob('*'))if p.is_file()}
        facts=dict(gerber_renderer=gerber_plot['renderer'],passed=True,panels=2,tiles=len(self.plan['tiles']),native_commands=3+2*len(self.plan['tiles']),complete_board_coverage=True,geometry_edited=False,common_viewport=True,layer='F.Cu',pixels_per_panel=self.plan['total_pixels_per_panel'],overview='Navigation only; use audited native detail tiles',owner_status='PENDING_USER',construction_status='NOT_RUN')
        result=dict(facts=facts,input_files=self.contract['inputs'],bounds_mm=self.bounds,dependencies=self.versions,coordinate_mapping=self.contract['coordinate_mapping'],files=files,display=str(self.out/'index.html'),comparison_png=str(self.out/'comparison.png'),render_verification='PENDING_SEPARATE_OPERATION')
        fresh(self.out/'render.json',result);return result
    def present(self):
        b=self.bounds;ow=1280;oh=math.ceil(ow*(b[3]-b[1])/(b[2]-b[0]));panels={name:Image.new('RGB',(ow,oh),BACKGROUND)for name in ('kicad','gerber')}
        links=[]
        for tile in self.plan['tiles']:
            x0,y0,x1,y1=tile['bounds_mm'];l=round((x0-b[0])/(b[2]-b[0])*ow);r=round((x1-b[0])/(b[2]-b[0])*ow);t=round((y0-b[1])/(b[3]-b[1])*oh);d=round((y1-b[1])/(b[3]-b[1])*oh)
            for name,panel in panels.items():
                with Image.open(self.out/'tiles'/tile['id']/(name+'.png'))as im:panel.paste(im.convert('RGB').resize((r-l,d-t),Image.Resampling.LANCZOS),(l,t))
            links.append(f'<a href="tiles/{tile["id"]}/index.html">{tile["id"]}</a>')
        im=Image.new('RGB',(2*ow+24,oh+150),'#eef3f7');draw=ImageDraw.Draw(im);draw.text((20,10),'Whole-board T01 / candidate KiCad versus candidate Gerber',fill='#152a40',font_size=27);draw.text((20,47),'Navigation overview. Open complete native detail tiles for audited resolution. Owner PENDING_USER.',fill='#152a40',font_size=19)
        for i,(name,panel)in enumerate(panels.items()):draw.text((i*(ow+24)+15,78),name.title(),fill='#152a40',font_size=22);im.paste(panel,(i*(ow+24),110))
        im.save(self.out/'comparison.png')
        (self.out/'index.html').write_text('<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Whole-board T01 native review</title><style>body{font:17px system-ui;background:#eef3f7;color:#152a40;max-width:1500px;margin:30px auto}img{width:100%}.tiles{display:grid;grid-template-columns:repeat('+str(self.plan['columns'])+',1fr);gap:7px}a{color:#065f9d}</style><h1>Whole-board T01 native review</h1><p>Candidate KiCad versus candidate Gerber. All '+str(len(links))+' source-coordinate tiles cover the full source and maximum growth window. The overview is for navigation; detail tiles retain the unchanged 1 µm KiCad / 5 µm Gerber audit bands. Owner PENDING_USER; independent NOT_RUN; electrical/manufacturing NOT_ESTABLISHED.</p><img src="comparison.png" alt="Whole-board candidate KiCad and Gerber overview"><div class="tiles">'+''.join(links)+'</div><p><a href="verification.json">Complete pixel audits</a> · <a href="controls.json">Deliberate controls</a> · <a href="tile_plan.json">Coverage partition</a> · <a href="../data_output/candidate/board.kicad_pcb">KiCad</a> · <a href="../data_output/candidate/gerbers/board-F_Cu.gbr">F.Cu Gerber</a></p>')
    def integrity(self):
        saved=read(self.out/'render.json')
        if saved['input_files']!=self.contract['inputs']or saved['bounds_mm']!=self.bounds or read(self.out/'tile_plan.json')!=self.plan:raise ValueError('RENDER_RECEIPT_BINDING_MISMATCH')
        for name,h in saved['files'].items():
            p=local(self.out/name)
            if not p.is_relative_to(self.out)or digest(p.read_bytes())!=h:raise ValueError('RENDER_OUTPUT_HASH_MISMATCH:'+name)
        self.check_inputs();return saved
    def surfaces(self):return dict(kicad=native_copper(self.inputs['kicad'],self.bounds),gerber=gerber_copper(self.inputs['gerber'],self.bounds))
    def verify(self):
        saved=self.integrity();surfaces=self.surfaces();self.root_out=self.out;results=[]
        for index,tile in enumerate(self.plan['tiles'],1):
            folder=self.out/'tiles'/tile['id'];b,size=tile['bounds_mm'],tile['pixels'];verify_svg_view(folder/'kicad.svg',b,size);verify_svg_view(folder/'gerber.svg',b,size)
            # Keep nearby copper outside the window for boundary-band distances.
            # An artificial clipping edge is farther away than either error band.
            context=box(b[0]-.01,b[1]-.01,b[2]+.01,b[3]+.01)
            audits={name:audit_tile(folder/(name+'.png'),g.intersection(context),b,size,self.contract['raster_boundary_error_mm'][name])for name,g in surfaces.items()}
            fresh(folder/'audit.json',dict(tile=tile,audits=audits));results.append(dict(tile_id=tile['id'],audits=audits));self.progress('verify',index)
        audits={name:dict(passed=True,pixels_checked=sum(r['audits'][name]['pixels_checked']for r in results),maximum_mismatch_distance_mm=max(r['audits'][name]['maximum_mismatch_distance_mm']for r in results),allowed_boundary_error_mm=self.contract['raster_boundary_error_mm'][name],mismatches_outside_band=0)for name in surfaces}
        if any(v['pixels_checked']!=self.plan['total_pixels_per_panel']for v in audits.values()):raise ValueError('BOARD_RENDER_PIXEL_COVERAGE_INCOMPLETE')
        result=dict(facts=dict(passed=True,panels_checked=2,tiles_checked=len(results),all_pixels_checked=True,complete_board_coverage=True,input_hashes_unchanged=True,output_hashes_unchanged=True,common_frame_verified=True,svg_viewport_verified=True,owner_status='PENDING_USER'),audits=audits,tiles=results,rendered_file_manifest_sha256=digest(canonical(saved['files'])),limits=self.contract['limits']);fresh(self.out/'verification.json',result);return result
    def controls(self):
        self.integrity()
        if not read(self.out/'verification.json')['facts']['passed']:raise ValueError('RENDER_VERIFICATION_REQUIRED')
        surfaces=self.surfaces();geometry=surfaces['gerber'];ranked=[]
        for tile in self.plan['tiles']:
            b=tile['bounds_mm'];g=geometry.intersection(box(*b));mirror=affinity.scale(g,xfact=-1,yfact=1,origin=((b[0]+b[2])/2,0));ranked.append((g.symmetric_difference(mirror).area,tile,g))
        score,tile,g=max(ranked,key=lambda r:r[0])
        if score<=.01:raise ValueError('BOARD_RENDER_ASYMMETRIC_CONTROL_NOT_ESTABLISHED')
        folder=self.out/'controls';folder.mkdir();source=self.out/'tiles'/tile['id'];b,size=tile['bounds_mm'],tile['pixels'];reports=[]
        def expect(name,prefix,action):
            try:action()
            except ValueError as error:
                if not str(error).startswith(prefix):raise ValueError('RENDER_WRONG_CONTROL_REJECTION:'+str(error))from error
                reports.append(dict(name=name,status='PASS_EXPECTED_REJECTION',error=str(error),tile_id=tile['id']))
            else:raise ValueError('RENDER_CONTROL_NOT_REJECTED:'+name)
        with Image.open(source/'gerber.png')as im:ImageOps.mirror(im).save(folder/'mirrored_gerber.png')
        expect('mirrored_gerber','RASTER_FIDELITY_EXCEEDED',lambda:audit_tile(folder/'mirrored_gerber.png',g,b,size,.005))
        Image.new('RGB',size,BACKGROUND).save(folder/'blank_kicad.png');expect('blank_kicad','RASTER_EMPTY_OR_SOLID',lambda:audit_tile(folder/'blank_kicad.png',g,b,size,.005))
        root=ET.fromstring((source/'kicad.svg').read_bytes());root.set('viewBox','0 0 3 3');(folder/'wrong_viewport.svg').write_bytes(ET.tostring(root));expect('wrong_svg_viewport','SVG_VIEWPORT_MISMATCH',lambda:verify_svg_view(folder/'wrong_viewport.svg',b,size))
        (folder/'changed_input.gbr').write_bytes(self.inputs['gerber'].read_bytes()+b'\nG04 changed copy*\n');expect('changed_input_hash','RENDER_INPUT_HASH_MISMATCH',lambda:bound_bytes(folder/'changed_input.gbr',self.contract['inputs']['gerber']['sha256']))
        self.check_inputs();result=dict(facts=dict(passed=True,deliberate_controls=4,all_rejected_for_expected_reason=True),controls=reports);fresh(self.out/'controls.json',result);return result
    def dispatch(self,operation):return dict(render_compare=self.render,render_verify=self.verify,render_controls=self.controls)[operation]()
