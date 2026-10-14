"""One end-to-end V1.5 completion command; fresh exports, no old receipts overwritten."""
from pathlib import Path
import datetime,hashlib,importlib.metadata,json,math,os,shutil,subprocess,sys
from shapely.geometry import Point
from shapely.ops import unary_union
from gerbonara.graphic_objects import Line,Flash
from .gerber_image import read_image,object_geometry
from .native_reference import terminals,routing_references,physical_segments
from .completion_checks import summary,equivalent,anchors,intent_check,physical_connections
from .fc1_run import custody
from .fc1_oracle import placed_polygons,analytic_scene
from tools.qualify_public import command
import numpy as np
from shapely import contains_xy

ROOT=Path(__file__).resolve().parents[1]
CLI=Path('/Users/geoffcheng/Projects/client/misc_repo/KiCAD_PCB_CAM/build/release/kicad/KiCad.app/Contents/MacOS/kicad-cli')
LAYERS=('F.Cu','B.Cu','F.Mask','B.Mask','Edge.Cuts','F.SilkS','B.SilkS','F.Paste','B.Paste')
ROLES={'F.Cu':('Copper','L1','Top'),'B.Cu':('Copper','L2','Bot'),'F.Mask':('Soldermask','Top'),'B.Mask':('Soldermask','Bot'),'Edge.Cuts':('Profile','NP'),'F.SilkS':('Legend','Top'),'B.SilkS':('Legend','Bot'),'F.Paste':('Paste','Top'),'B.Paste':('Paste','Bot')}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def role(image):
    value=image['file_attrs'].get('.FileFunction')
    for key,expected in ROLES.items():
        if value==expected:return key
    raise ValueError('layer function outside declared profile: '+str(value))

def source_copy(name,dest):
    rec=json.loads((ROOT/'out/v1_5'/name/'qualification.json').read_text());work=dest/'work'
    if name=='GlowStitch':
        import zipfile
        work.mkdir()
        with zipfile.ZipFile(ROOT/'external/sources'/name/rec['selection']['archive']) as z:
            (work/rec['selection']['board']).write_bytes(z.read(rec['selection']['board']))
    else:shutil.copytree(ROOT/'external/sources'/name,work,ignore=shutil.ignore_patterns('.git'))
    board=work/rec['selection']['board'];assert sha(board)==rec['selection']['source_board_sha256']
    return board,rec

def find_images(folder):
    result={}
    for p in sorted(folder.glob('*.gbr')):
        img=read_image(p);key=role(img)
        if key in result:raise ValueError('duplicate layer role '+key)
        expected=('Negative',) if 'Mask' in key else ('Positive',)
        polarity=img['file_attrs'].get('.FilePolarity')
        if polarity!=expected and not (key=='Edge.Cuts' and polarity is None):raise ValueError('unexpected layer polarity '+key)
        img['path']=p;result[key]=img
    if set(result)!=set(LAYERS):raise ValueError('incomplete/extra layer set')
    return result

def append_rect(raw,rect,dark=False):
    x1,y1,x2,y2=rect
    code=('%LP'+('D' if dark else 'C')+'*%\nG36*\n'+f'X{round(x1*1e6)}Y{round(y1*1e6)}D02*\n'+f'X{round(x2*1e6)}Y{round(y1*1e6)}D01*\n'+f'X{round(x2*1e6)}Y{round(y2*1e6)}D01*\n'+f'X{round(x1*1e6)}Y{round(y2*1e6)}D01*\n'+f'X{round(x1*1e6)}Y{round(y1*1e6)}D01*\nG37*\n')
    return raw.replace('M02*',code+'M02*')

def main():
    custody();frozen=json.loads((ROOT/'out/v15_completion/required_matrix_freeze.json').read_text());assert sha(ROOT/frozen['path'])==frozen['sha256']
    run=ROOT/'out/v15_completion'/datetime.datetime.now(datetime.timezone.utc).strftime('run_%Y%m%dT%H%M%S_%fZ');run.mkdir()
    pinned=json.loads((ROOT/'out/native_exports/20261014T140617_287308Z/run_receipt.json').read_text())
    if sha(CLI)!=pinned['cli_sha256']:raise ValueError('KiCad binary differs from pinned export build')
    report={'required_matrix':frozen,'run':str(run),'tool_versions':{x:importlib.metadata.version(x) for x in ('gerbonara','shapely','sexpdata','pypdf')},'cli_sha256':sha(CLI),'boards':{},'cursor_review':{'status':'NOT_RUN','reason':'CHANNEL_UNAVAILABLE'},'factory_acceptance':'NOT_ESTABLISHED'}
    try:
        oracle_file=ROOT/'out/fc1/run_001/Block_with_different_orientations.gbr'
        prod=read_image(oracle_file)['geometry'];oracle=unary_union(placed_polygons());xx,yy=np.meshgrid(np.arange(-3.5,13.5,.025),np.arange(-2,11,.025));expect,margin=analytic_scene(xx,yy);stable=margin>2e-5
        mismatch=int(np.sum(stable&(contains_xy(prod,xx,yy)!=expect)))
        diff=prod.symmetric_difference(oracle).area;haus=prod.hausdorff_distance(oracle)
        report['raw_parser_to_fc1']={'status':'PASS' if mismatch==0 and diff<=4e-4 and haus<=1e-5 else 'FAIL','shape_difference_mm2':diff,'boundary_distance_mm':haus,'analytic_grid_mismatches':mismatch,'area_mm2':prod.area,'geometry':summary(prod)}
        for name in ('GlowStitch','HALPI2-HDMI-FPC'):
            dest=run/name;dest.mkdir();board,old=source_copy(name,dest);commands=[]
            commands.append(command([CLI,'version'],dest/'version.log'))
            if '10.99.0' not in (dest/'version.log').read_text():raise ValueError('pinned KiCad version mismatch')
            commands.append(command([CLI,'pcb','drc','--format','json','--severity-all','--exit-code-violations','-o',dest/'drc.json',board],dest/'drc.log'))
            for i in (1,2):
                output=dest/f'export_{i}';output.mkdir()
                c=command([CLI,'pcb','export','gerbers','--layers',','.join(LAYERS),'--precision','6','--no-protel-ext','-o',str(output)+'/',board],dest/f'export_{i}.log');commands.append(c)
                if c['exit_code']!=0:raise ValueError('native export failed; no stale outputs reused')
                commands.append(command([CLI,'pcb','export','drill','-o',str(output)+'/',board],dest/f'drill_{i}.log'))
            if sha(board)!=old['selection']['source_board_sha256']:raise ValueError('native copy changed during no-edit export')
            a=find_images(dest/'export_1');b=find_images(dest/'export_2');history=find_images(ROOT/'out/v1_5'/name/'export_1')
            pads=terminals(board);routes,unknown_routing=routing_references(board,pads);source_segments=physical_segments(board)
            result={'commit':old['commit'],'source_board_sha256':sha(board),'commands':commands,'layers':{},'source_terminals':[{k:v for k,v in p.items() if k!='shape'} for p in pads],'anchors':{},'intent':{},'physical_connections':{},'unknown_native_routing':unknown_routing}
            for key in LAYERS:
                img=a[key];g=img['geometry'];r=equivalent(g,b[key]['geometry']);oldmatch=equivalent(history[key]['geometry'],g)
                (dest/(key.replace('.','_')+'.wkb')).write_bytes(g.wkb)
                result['layers'][key]={'sha256':sha(img['path']),'path':str(img['path']),'inventory':img['inventory'],'object_types':img['object_types'],'file_attributes':img['file_attrs'],'geometry':summary(g),'replay':r,'historical_geometry_preservation':oldmatch}
                if key in ('F.Cu','B.Cu'):
                    result['anchors'][key]=anchors(img,pads,key);result['intent'][key]=intent_check(g,pads,routes,key);result['physical_connections'][key]=physical_connections(g,source_segments,key)
            nominal=a['F.Cu']['geometry'].intersection(a['F.Mask']['geometry']);replayed=b['F.Cu']['geometry'].intersection(b['F.Mask']['geometry'])
            result['nominal_exposure']={'geometry':summary(nominal),'no_edit_preservation':equivalent(nominal,replayed),'required_rim':None,'meaning':'Nominal source/export exposure preserved; no factory overlap rule imposed.'}
            report['boards'][name]=result
            faults=[];fd=dest/'faults';fd.mkdir()
            # A translated complete mask must fail fixed-opening and exposure shape preservation.
            mask=a['F.Mask']['path'].read_text();import re
            moved=re.sub(r'(?m)^[XY][^\n]*\*',lambda line:re.sub(r'X(-?\d+)',lambda m:'X'+str(int(m[1])+100000),line[0]),mask)
            file=fd/'moved_mask.gbr';file.write_text(moved);mg=read_image(file)['geometry']
            mr=equivalent(a['F.Mask']['geometry'],mg);ex=equivalent(nominal,a['F.Cu']['geometry'].intersection(mg))
            faults.append({'name':'moved_mask','check':'fixed_opening_and_exposure','status':'PASS' if mr['status']==ex['status']=='FAIL' else 'FAIL','observed':[mr['status'],ex['status']],'file':str(file),'sha256':sha(file)})
            raw=a['F.Cu']['path'].read_text();bound=a['F.Cu']['geometry'].bounds
            file=fd/'protected_copper_changed.gbr';file.write_text(append_rect(raw,(bound[0]-2,bound[1]-2,bound[0]-1,bound[1]-1),True));cg=read_image(file)['geometry'];cr=equivalent(a['F.Cu']['geometry'],cg)
            faults.append({'name':'protected_copper_changed','check':'whole_layer_scope_preservation','status':'PASS' if cr['status']=='FAIL' else 'FAIL','observed':cr['status'],'file':str(file),'sha256':sha(file)})
            # Try a source-derived conductor cut across its local center, keeping the
            # obligation attached to independent native pair intent, not image labels.
            cut_receipts=[]
            source_pair=next((s for s in source_segments if s['layer']=='F.Cu' and math.dist(s['a'],s['b'])>.5),None)
            if source_pair:
                aa,bb=source_pair['a'],source_pair['b'];x,y=(aa[0]+bb[0])/2,(aa[1]+bb[1])/2
                rect=(bound[0]-1,y-.05,bound[2]+1,y+.05) if abs(aa[1]-bb[1])>abs(aa[0]-bb[0]) else (x-.05,bound[1]-1,x+.05,bound[3]+1)
                file=fd/'connection_cut.gbr';file.write_text(append_rect(raw,rect));cut=read_image(file)['geometry'];ci=physical_connections(cut,source_segments,'F.Cu')
                cut_receipts.append({'file':str(file),'sha256':sha(file),'connections':ci['status'],'source_conductor':source_pair})
            faults.append({'name':'broken_connection','check':'native_source_physical_conductor_continuity','status':'PASS' if cut_receipts and cut_receipts[-1]['connections']=='FAIL' else 'NOT_ESTABLISHED','attempts':cut_receipts,'meaning':'Physical nominal source relation; named electrical intent is reported separately.'})
            # Bridge distinct source-labeled terminals. Net identity comes from the native board.
            pair=next(((p,q) for p in pads for q in pads if p['net'] and q['net'] and p['net']!=q['net'] and 'F.Cu' in p['layers'] and 'F.Cu' in q['layers']),None)
            if pair:
                p,q=pair;file=fd/'new_bridge.gbr';x1,y1=p['center_mm'];x2,y2=q['center_mm'];code=f'%ADD999C,0.500000*%\n%LPD*%\nD999*\nX{round(x1*1e6)}Y{round(y1*1e6)}D02*\nX{round(x2*1e6)}Y{round(y2*1e6)}D01*\nM02*'
                file.write_text(raw.replace('M02*',code));bridge=read_image(file)['geometry'];bi=intent_check(bridge,pads,routes,'F.Cu')
                faults.append({'name':'new_bridge','check':'independent_native_net_short','status':'PASS' if bi['no_short']=='FAIL' else 'FAIL','observed':bi['no_short'],'file':str(file),'sha256':sha(file)})
            else:
                # Missing net names are not replaced by invented N1/N2. Challenge
                # baseline physical separation of source-mapped pad centers instead.
                bg=history['F.Cu']['geometry'];parts=list(bg.geoms) if bg.geom_type=='MultiPolygon' else [bg]
                def part(p):return next((i for i,g in enumerate(parts) if g.covers(Point(p['center_mm']))),None)
                physical_pair=next(((p,q) for p in pads for q in pads if part(p) is not None and part(q) is not None and part(p)!=part(q)),None)
                if physical_pair:
                    p,q=physical_pair;file=fd/'new_physical_bridge.gbr';x1,y1=p['center_mm'];x2,y2=q['center_mm']
                    code=f'%ADD999C,0.500000*%\n%LPD*%\nD999*\nX{round(x1*1e6)}Y{round(y1*1e6)}D02*\nX{round(x2*1e6)}Y{round(y2*1e6)}D01*\nM02*'
                    file.write_text(raw.replace('M02*',code));bridge=read_image(file)['geometry'];bp=list(bridge.geoms) if bridge.geom_type=='MultiPolygon' else [bridge]
                    merged=any(g.covers(Point(p['center_mm'])) and g.covers(Point(q['center_mm'])) for g in bp)
                    faults.append({'name':'new_bridge','check':'immutable_baseline_physical_separation_preservation','status':'PASS' if merged else 'FAIL','observed':'FAIL' if merged else 'PASS','file':str(file),'sha256':sha(file),'source_pads':[p['source_id'],q['source_id']],'electrical_short_acceptance':'NOT_ESTABLISHED','meaning':'Baseline/source-anchored physical preservation, not named-net intent.'})
                else:faults.append({'name':'new_bridge','status':'NOT_ESTABLISHED','reason':'No independently anchored baseline-separated pads'})
            # Valid-but-wrong layer polarity/order must fail geometry preservation,
            # while unknown syntax is refused as NOT_ESTABLISHED, not interpreted.
            file=fd/'polarity_order.gbr';file.write_text(raw.replace('%LPD*%','%LPC*%',1))
            pg=read_image(file)['geometry'];pr=equivalent(a['F.Cu']['geometry'],pg)
            faults.append({'name':'polarity_order','check':'ordered_copper_image_preservation','status':'PASS' if pr['status']=='FAIL' else 'FAIL','observed':pr['status'],'file':str(file),'sha256':sha(file)})
            file=fd/'unknown_operation.gbr';file.write_text(raw.replace('M02*','G999*\nM02*'))
            try:read_image(file);refusal=False;reason=None
            except Exception as exc:refusal=True;reason=str(exc)
            faults.append({'name':'unknown_operation','check':'unsupported_syntax_refusal','status':'PASS' if refusal else 'FAIL','interpreted_geometry':'NOT_ESTABLISHED','reason':reason,'file':str(file),'sha256':sha(file)})
            result['faults']=faults
            geometry_statuses=[status for x in result['layers'].values() for status in (x['replay']['status'],x['historical_geometry_preservation']['status'])]+[x['status'] for x in result['anchors'].values()]+[result['nominal_exposure']['no_edit_preservation']['status']]+[x['status'] for x in result['physical_connections'].values()]
            result['geometry_profile']='FAIL' if 'FAIL' in geometry_statuses else 'NOT_ESTABLISHED' if any(x!='PASS' for x in geometry_statuses) else 'PASS'
            result['electrical_profile']='NOT_ESTABLISHED' if not any(p['net'] for p in pads) else 'FAIL' if any(x['no_short']=='FAIL' or x['connections']=='FAIL' for x in result['intent'].values()) else 'PASS'
            report['boards'][name]=result
            (run/'checkpoint.json').write_text(json.dumps(report,indent=2)+'\n')
            print(name,result['geometry_profile'],result['electrical_profile'],[(f['name'],f['status']) for f in faults],flush=True)
        custody();prior=json.loads((ROOT/'out/v15_completion/prior_evidence_hashes.json').read_text());changed=[p for p,h in prior.items() if not (ROOT/p).is_file() or sha(ROOT/p)!=h]
        report['historical_evidence_integrity']={'status':'PASS' if not changed else 'FAIL','changed':changed,'files_checked':len(prior)}
        report['overall']='FAIL' if changed or report['raw_parser_to_fc1']['status']=='FAIL' or any(r['geometry_profile']=='FAIL' or r['electrical_profile']=='FAIL' or any(f['status']=='FAIL' for f in r['faults']) for r in report['boards'].values()) else 'NOT_ESTABLISHED' if any(r['geometry_profile']=='NOT_ESTABLISHED' or r['electrical_profile']=='NOT_ESTABLISHED' or any(f['status']=='NOT_ESTABLISHED' for f in r['faults']) for r in report['boards'].values()) else 'PASS'
    except Exception as exc:
        report['overall']='NOT_ESTABLISHED';report['unresolved_error']=repr(exc);raise
    finally:
        (run/'report.json').write_text(json.dumps(report,indent=2)+'\n');print('RUN:',run,flush=True)
    return run

if __name__=='__main__':
    from .completion_finalize import finalize
    finalize(main())
