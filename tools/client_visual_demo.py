"""Local client Gerber inspection using the existing workbench; no edit/acceptance."""
from pathlib import Path
import base64, collections, datetime, gzip, hashlib, json, shutil, subprocess, sys, time, warnings
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gerbonara.rs274x import GerberFile
from gerbonara import graphic_objects as go
from shapely import affinity
from src.gerber_image import read_image, compose, object_geometry
from src.client_gerber import read_region, parse, sha as source_sha
from src.visual_scene import ROOT, svg_path, bounds, sha
from tools.visual_report import embed_scene


def main():
    source = ROOT/'external/sources/12_copper_layers_pcb_gbr'
    base = Path((ROOT/'out/consolidation/current_visual.txt').read_text().strip())
    run = ROOT/'out/visual'/datetime.datetime.now(datetime.timezone.utc).strftime('client_%Y%m%dT%H%M%S_%fZ')
    run.mkdir(parents=True)
    before = {str(p.relative_to(source)):sha(p) for p in sorted(source.rglob('*')) if p.is_file()}
    scene = json.loads((base/'scene.json').read_text())
    operation_run=Path((ROOT/'out/client_operation/current.txt').read_text().strip())
    operation_result=json.loads((operation_run/'result.json').read_text())
    operation_contract=json.loads((operation_run/'contract.json').read_text())
    if operation_result.get('status')!='PASS' or sha(operation_run/'contract.json')!=operation_result['contract_sha256']:
        raise RuntimeError('Latest client operation lacks a hash-bound PASS result')
    # Retain all existing relative evidence links without changing the prior bundle.
    for p in base.iterdir():
        if p.is_dir(): shutil.copytree(p,run/p.name)
        elif p.name not in ('index.html','scene.json','build_receipt.json','consolidation_seal.json'): shutil.copy2(p,run/p.name)
    evdir=run/'evidence/client'; evdir.mkdir(parents=True)
    shutil.copy2(base/'consolidation_seal.json',run/'evidence/prior_consolidation_seal.json')
    scene['prior_seal_snapshot']='evidence/prior_consolidation_seal.json'
    receipt={'scope':'Client Gerber inspection plus bounded local operation replay','source_sha256':before,'layers':{},'electrical':'Whole-board NOT_ESTABLISHED','internal_copper_layers':'10 inventoried; not rendered in this minimum demo','drills':'Not rendered or registered; original inch units retained','base_scene_sha256':sha(base/'scene.json'),'operation_run':str(operation_run.relative_to(ROOT))}
    geometries={}; parsed={}
    mapping={'F.Cu':'Top Layer','B.Cu':'Bottom Layer','F.Mask':'Top Solder','B.Mask':'Bottom Solder','Edge.Cuts':'Edge_Cuts'}
    for layer,name in mapping.items():
        p=source/f'vme-wren-{name}.gbr'; start=time.perf_counter(); print('Rendering',layer,flush=True)
        strict_error=None; warning_text=[]
        try:
            r=read_image(p); g=r['geometry']; objects=r['objects']; attrs=r['file_attrs']
        except Exception as exc:
            strict_error=str(exc)
            # Presentation-only fallback, explicitly restricted to this observed warning.
            if 'D01 interpolation with a zero-size aperture' not in strict_error: raise
            with warnings.catch_warnings(record=True) as ws:
                warnings.simplefilter('always'); gerber=GerberFile.open(p)
            warning_text=[str(w.message) for w in ws]
            if not warning_text or any('D01 interpolation with a zero-size aperture' not in w for w in warning_text):
                raise RuntimeError('Unexpected display parser warning')
            objects=gerber.objects; attrs=gerber.file_attrs; g=compose(objects)
        if not g.is_valid: raise RuntimeError('Invalid composed display geometry')
        if '.Mask' in layer and tuple(attrs.get('.FilePolarity',()))!=('Negative',): raise RuntimeError('Mask opening convention not established')
        geometries[layer]=g; parsed[layer]=objects
        (evdir/(layer+'.wkb')).write_bytes(g.wkb)
        receipt['layers'][layer]={'source':str(p.relative_to(ROOT)),'sha256':sha(p),'composition':'DISPLAY_ONLY_WITH_WARNINGS' if strict_error else 'STRICT_COMPOSITION_COMPLETED','strict_error':strict_error,'warnings':warning_text,'object_types':dict(collections.Counter(type(o).__name__ for o in objects)),'area_mm2':g.area,'file_attributes':attrs,'seconds':time.perf_counter()-start,'geometry_sha256':sha(evdir/(layer+'.wkb'))}
    def register(g):
        display=affinity.scale(g,1,-1,origin=(0,0)); key='client_'+hashlib.sha256(g.wkb).hexdigest()[:20]
        scene['geometry'][key]={'path':svg_path(display),'bounds':bounds(display,0),'basis':'Observed client Gerber; Y flipped for display; inspection only'}
        return key
    keys={layer:register(g) for layer,g in geometries.items()}
    operation_copy=evdir/'operation'; shutil.copytree(operation_run,operation_copy)
    operation_report='evidence/client/operation/result.json'
    def region_for(path):return read_region(path,operation_contract['allowed_region_mm'])
    opfiles={'input':operation_run/'controlled_before.gbr','source':source/'vme-wren-Bottom Layer.gbr','accepted':operation_run/'accepted/candidate.gbr','open':operation_run/'open/candidate.gbr','bridge':operation_run/'bridge/candidate.gbr'}
    op_images={k:region_for(p) for k,p in opfiles.items()}
    def opkey(g):
        display=affinity.scale(g,1,-1,origin=(0,0));key='clientop_'+hashlib.sha256(g.wkb).hexdigest()[:20]
        scene['geometry'][key]={'path':svg_path(display),'bounds':bounds(display,0),'basis':'Composed client Gerber geometry clipped to the declared operation region'}
        return key
    op_layers={k:opkey(v['geometry']) for k,v in op_images.items()}
    target_ordinal,trace_ordinal=operation_contract['writable_ordinals']
    # Contract records writable feature ordinals in parser order; identify pad/trace by type.
    from gerbonara import graphic_objects as opgo
    source_objects=parse(opfiles['source']).objects
    target_ordinal=next(i for i in operation_contract['writable_ordinals'] if isinstance(source_objects[i],opgo.Flash))
    trace_ordinal=next(i for i in operation_contract['writable_ordinals'] if isinstance(source_objects[i],opgo.Line))
    pad=source_objects[target_ordinal];trace=source_objects[trace_ordinal]
    neighbor=next(o for o in source_objects if isinstance(o,opgo.Flash) and tuple(o.attrs.get('.P',())[:2])==tuple(operation_contract['protected_neighbor']['terminal']))
    def opobjects(which):
        objs=parse(opfiles[which]).objects;out=[]
        for ordinal,name,role in [(target_ordinal,'R140.1','target'),(trace_ordinal,'Connected trace','dependent')]:
            obj=objs[ordinal]; shape=object_geometry(obj)
            x,y=(obj.x,obj.y) if isinstance(obj,opgo.Flash) else ((obj.x1+obj.x2)/2,(obj.y1+obj.y2)/2)
            out.append({'id':'target' if role=='target' else 'trace','name':name,'role':role,'layer':'B.Cu','center':[x,-y],'shape':opkey(shape),'net':operation_contract['source_net_label'][0],'basis':'Contract-selected Gerber occurrence; X2 label is source metadata'})
        nshape=object_geometry(neighbor)
        out.append({'id':'protected','name':'R140.2 · protected nearby pad','role':'protected','layer':'B.Cu','center':[neighbor.x,-neighbor.y],'shape':opkey(nshape),'net':','.join(neighbor.attrs.get('.N',())),'basis':'Nearby original copper with a distinct Gerber X2 label'})
        return out
    states=[]
    state_specs=[('controlled','Controlled input · deliberate +0.35 mm offset','input','before_measurement.json'),('original','Supplied original · aligned reference','source','original_measurement.json'),('accepted','Generated candidate · accepted','accepted','accepted/validation.json'),('open','Control · trace disconnected','open','open/validation.json'),('bridge','Control · bridge to protected copper','bridge','bridge/validation.json')]
    for sid,label,filekey,reportfile in state_specs:
        report=json.loads((operation_run/reportfile).read_text())
        validation=report.get('checks',[])
        highlights={}
        if sid=='open':highlights={'connection':opkey(op_images['accepted']['geometry'].difference(op_images['open']['geometry']))}
        if sid=='bridge':highlights={'separation':opkey(op_images['bridge']['geometry'].difference(op_images['accepted']['geometry'])),'protected_objects':opkey(op_images['bridge']['geometry'].difference(op_images['accepted']['geometry']))}
        checks=[{'id':item['id'],'label':item['id'].replace('_',' ').title(),'status':item['status'],'metric':item.get('actual',{}),'expected':item.get('requirement','See bounded operation contract'),'source_ids':['R140.1','B.Cu'],'focus':[operation_contract['before_center_mm'][0]-1.2,-operation_contract['before_center_mm'][1]-0.7,2.4,1.4],'evidence':{'snapshot':operation_report,'sha256':source_sha(operation_run/'result.json')},'highlight':highlights.get(item['id'])} for item in validation]
        state={'id':sid,'label':label,'layers':{'B.Cu':op_layers[filekey],'B.Mask':keys['B.Mask']},'candidate_verdict':report.get('status','NOT_EVALUATED'),'checks':checks,'evidence':{'snapshot':operation_report,'sha256':source_sha(operation_run/'result.json')},'objects':opobjects(filekey),'pairs':[{'a':'target','b':'trace','net':operation_contract['source_net_label'][0],'layer':'B.Cu','status':next((x['status'] for x in validation if x['id']=='connection'),'NOT_EVALUATED')}],'control_test':None,'replay':[],'delta':{},'metrics':{'controlled_move_mm':.35,'candidate_sha256':report.get('candidate_sha256'),'state':sid}}
        states.append(state)
    for st in states:
        baseline=op_images['input']['geometry'];candidate=op_images[st['id'] if st['id'] in op_images else 'accepted']['geometry']
        st['delta']['B.Cu']={'added':opkey(candidate.difference(baseline)),'removed':opkey(baseline.difference(candidate))}
    x0,y0,x1,y1=operation_contract['allowed_region_mm']
    operation_focus=[operation_contract['before_center_mm'][0]-1.2,-operation_contract['before_center_mm'][1]-0.7,2.4,1.4]
    outline_key=register(geometries['Edge.Cuts'])
    board_bounds=bounds(affinity.scale(geometries['Edge.Cuts'],1,-1,origin=(0,0)),1)
    opcase={'id':'clientop','kind':'operation','name':'Client region · contract-driven copper move','story':'A real client Gerber region, a declared 0.35 mm controlled offset, an automatically generated candidate, and two rejection controls. The original client file is already aligned; the offset is a labelled demonstration challenge.','run_id':operation_run.name,'code_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'profile_id':'client-gerber-movepad-region-v1','basis':'Actual bottom-copper Gerber bytes produced from a hash-bound local operation contract; candidate independently reparsed and checked in the declared region','limitations':['This is a controlled local demonstration policy, not client manufacturing requirements.','The accepted output returns to copper bytes identical to the supplied original because the original already satisfies the stated objective.','Checks establish only this pad, trace, permitted region and nearby separation; whole-board and cross-layer electrical correctness remain NOT_ESTABLISHED.','The bridge fault also adds unauthorized plot geometry, so both protected-object preservation and local separation reject it.','The board locator shows only the supplied Edge_Cuts outline and region marker; it is not a full-board copper interpretation.','No manufacturing approval or production authorization.'],'electrical':'LOCAL_SAME_LAYER_ONLY','aggregate':'NOT_APPLICABLE','source_aware':'NOT_APPLICABLE','states':states,'focus':operation_focus,'fit':operation_focus,'overview':{'outline':outline_key,'bounds':board_bounds,'region':[x0,-y1,x1,-y0],'label':'R140.1 operation region'},'scope':[x0,-y1,x1,-y0],'physical_group':['target','trace','protected'],'default_state':'accepted','focus_object':'target'}
    keys={layer:register(g) for layer,g in geometries.items()}
    fit=bounds(affinity.scale(geometries['Edge.Cuts'],1,-1,origin=(0,0)),1)
    case={'id':'client12','kind':'inspection','name':'Client 12-layer board · aperture inspection','story':'Inspect actual copper against fixed solder-mask openings. Select a labelled flash to see measured exposure; no defect or repair is assumed.','run_id':run.name,'code_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'profile_id':'client-outer-layer-inspection-v1','basis':'Client-supplied Gerbers, millimetres; positive copper, negative soldermask represented as openings','limitations':['Client artwork appears in Cases; Processing and Storage retain the previously qualified native-board datasets.','This minimum view renders two outer copper layers, two mask-opening layers and the outline; ten internal copper layers and drills are not displayed.','Top copper has 304 zero-width interpolation warnings: display-only fallback; strict validator import remains unsupported.','X2 pin/net labels are observed export metadata, not independently qualified electrical intent.','Selected flash exposure is a geometric measurement; no minimum rim, clearance or modification rule was supplied.','Duplicate adhesive artwork is not loaded; its intended manufacturing role remains unresolved.'],'electrical':'NOT_ESTABLISHED','aggregate':'NOT_APPLICABLE','source_aware':'NOT_RUN','states':[],'fit':fit,'default_state':'bottom','focus':fit}
    for side,prefix in [('bottom','B'),('top','F')]:
        cu=prefix+'.Cu'; mask=prefix+'.Mask'; objects=[]; samples=[]
        for ordinal,o in enumerate(parsed[cu]):
            if not isinstance(o,go.Flash) or not o.attrs.get('.P'): continue
            shape=object_geometry(o); pin=o.attrs['.P']; net=o.attrs.get('.N',()); name='.'.join(pin[:2]); identity=f'{cu}:{ordinal}'
            obj={'id':identity,'name':name,'center':[o.x,-o.y],'role':'observed Gerber flash','layer':cu,'shape':register(shape),'net':','.join(net) or None,'basis':'Gerber .P/.N metadata; source-file hash and parsed-object ordinal','source_id':identity,'assignment_basis':'Observed Gerber X2 label, not independent net intent'}
            objects.append(obj)
            samples.append({'id':identity,'name':name,'flash_area_mm2':shape.area,'exposed_flash_mm2':shape.intersection(geometries[mask]).area,'covered_flash_mm2':shape.difference(geometries[mask]).area})
            if len(objects)==32:break
        state={'id':side,'label':side.title()+' copper + mask openings','layers':{cu:keys[cu],mask:keys[mask],'Edge.Cuts':keys['Edge.Cuts']},'candidate_verdict':'NOT_EVALUATED','checks':[],'evidence':{'snapshot':'evidence/client/receipt.json'},'objects':objects,'pairs':[],'control_test':None,'replay':[],'delta':{},'metrics':{'selected_flashes':len(objects)},'samples':samples}
        for obj,metric in zip(objects,samples):
            x,y=obj['center']; state['checks'].append({'id':obj['id'],'label':obj['name']+' · copper exposure','status':'MEASURED','metric':metric,'objects':[obj['id']],'source_ids':[obj['id']],'focus':[x-2,y-2,4,4],'evidence':state['evidence'],'expected':'No acceptance threshold supplied; measure this flash intersected with mask openings.'})
        receipt[side+'_samples']=samples; case['states'].append(state)
    first=case['states'][0]['objects'][0]; x,y=first['center'];case['focus']=[x-2,y-2,4,4];case['focus_object']=first['id']
    assert before=={str(p.relative_to(source)):sha(p) for p in sorted(source.rglob('*')) if p.is_file()}
    receipt['source_unchanged']=True
    (evdir/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    for state in case['states']:state['evidence']['sha256']=sha(evdir/'receipt.json')
    scene['cases'][0:0]=[opcase,case]
    scene['provenance'].append({'path':str(source.relative_to(ROOT)),'snapshot':'evidence/client/receipt.json','sha256':sha(evdir/'receipt.json')})
    sources=['tools/client_visual_demo.py','tools/client_operation_run.py','src/client_gerber.py','src/client_operation.py','src/client_validation.py','src/gerber_image.py','web/workbench.js','web/workbench.html','web/replay_model.js','web/pipeline_views.js','web/backend_model.js']
    scene['build']={'code_commit':case['code_commit'],'working_tree_dirty':True,'source_sha256':{p:sha(ROOT/p) for p in sources},'base_scene_sha256':sha(base/'scene.json')}
    raw=embed_scene(scene);digest=hashlib.sha256(raw.encode()).hexdigest();encoded=raw;transport='plain-json'
    if len(raw.encode())>32*1024*1024:
        transport='gzip-base64';encoded=base64.b64encode(gzip.compress(raw.encode(),mtime=0)).decode()
    app='\n'.join((ROOT/p).read_text() for p in ['web/replay_model.js','web/backend_model.js','web/pipeline_views.js','web/workbench.js'])
    template=(ROOT/'web/workbench.html').read_text()
    if transport=='gzip-base64':template=template.replace('id="scene-data"','id="scene-data" data-encoding="gzip-base64"')
    page=template.replace('__SCENE__',encoded).replace('__DIGEST__',digest).replace('__APP__',app)
    (run/'scene.json').write_text(raw);(run/'index.html').write_text(page)
    # Small static preview of the default focus, using the same composed paths.
    view=' '.join(map(str,case['focus'])); s=case['states'][0]
    svg=f'<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="700" viewBox="{view}"><rect x="{x-2}" y="{y-2}" width="4" height="4" fill="#102634"/>'
    for layer,color in [('B.Cu','#c8ab77'),('B.Mask','#73d8ee')]:
        attrs=f'fill="{color}"' if layer=='B.Cu' else f'fill="none" stroke="{color}" stroke-width=".025"'
        svg+=f'<path d="{scene["geometry"][s["layers"][layer]]["path"]}" fill-rule="evenodd" {attrs}/>'
    (run/'client_overview.svg').write_text(svg+'</svg>')
    (run/'build_receipt.json').write_text(json.dumps({'scope':receipt['scope'],'scene_sha256':digest,'scene_bytes':len(raw.encode()),'html_sha256':sha(run/'index.html'),'html_bytes':len(page.encode()),'embedded_transport':transport,'source_unchanged':True,'client_receipt_sha256':sha(evdir/'receipt.json'),'operation_result_sha256':sha(operation_run/'result.json'),'source_sha256':scene['build']['source_sha256']},indent=2)+'\n')
    (ROOT/'out/client_demo/current.txt').write_text(str(run)+'\n')
    print(run,flush=True)

if __name__=='__main__': main()
