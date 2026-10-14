"""Consolidate retained electrical evidence and add only a named-net open control."""
from pathlib import Path
import datetime,hashlib,json,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.fc1_run import custody
from src.native_reference import terminals,routing_references
from src.completion_checks import intent_check,anchors
from src.gerber_image import read_image
from src.completion_run import append_rect
from shapely.geometry import Point
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    custody()
    manifest_path=ROOT/'contracts/halpi2_electrical_case_v1.json';m=json.loads(manifest_path.read_text())
    old=ROOT/m['baseline_report'];assert sha(old)==m['baseline_report_sha256']
    report=json.loads(old.read_text());b=report['boards']['HALPI2-HDMI-FPC']
    for key in ('implementation_hashes','input_reference_bindings'):
        for path,digest in report[key].items():assert sha(ROOT/path)==digest,path
    for path,digest in report['output_hashes'].items():assert sha(old.parent/path)==digest,path
    native=ROOT/'external/sources/HALPI2-HDMI-FPC/HALPI2-HDMI-FPC.kicad_pcb'
    assert sha(native)==m['source_board_sha256']
    pads=terminals(native);routes,unknown=routing_references(native,pads)
    encoded=json.loads(json.dumps([{k:v for k,v in p.items() if k!='shape'} for p in pads]))
    assert encoded==m['terminals']
    assert len(pads)==64 and len({p['source_id'] for p in pads})==64 and all(p['net'] for p in pads)
    run=ROOT/'out/halpi2_case'/datetime.datetime.now(datetime.timezone.utc).strftime('run_%Y%m%dT%H%M%S_%fZ');run.mkdir()
    results={};mapping=[]
    for layer in m['required_layers']:
        image=read_image(Path(b['layers'][layer]['path']))
        a=anchors(image,pads,layer);i=intent_check(image['geometry'],pads,routes,layer)
        assert a['status']=='PASS' and len(a['terminals'])==32
        assert i['connections']=='PASS' and i['no_short']=='PASS' and len(i['terminal_mappings'])==32
        pairs=[{k:v for k,v in p.items() if k!='status'} for p in i['source_justified_same_layer_pairs']]
        assert pairs==m['required_pairs'][layer] and len(pairs)==120
        results[layer]={'positive':i,'anchors':a}
        mapping.extend([{'layer':layer,**t} for t in a['terminals']])
    c=m['open_control'];pad=next(p for p in pads if p['source_id']==c['terminal'])
    bounds=pad['shape'].bounds;x1,y1,x2,y2=bounds
    # Native pad bounds specify the cut; no candidate components choose expected intent.
    inner=(x1-.02,y1-.02,x2+.02,y2+.02);outer=(x1-.15,y1-.15,x2+.15,y2+.15)
    ix1,iy1,ix2,iy2=inner;ox1,oy1,ox2,oy2=outer
    rectangles=[(ox1,oy1,ix1,oy2),(ix2,oy1,ox2,oy2),(ix1,oy1,ix2,iy1),(ix1,iy2,ix2,oy2)]
    raw=Path(b['layers'][c['layer']]['path']).read_text()
    for rect in rectangles:raw=append_rect(raw,rect)
    fault=run/'J22_1_GND_isolated.gbr';fault.write_text(raw)
    image=read_image(fault);opened=intent_check(image['geometry'],pads,routes,c['layer'])
    anchor=anchors(image,pads,c['layer'])
    failed=[p for p in opened['source_justified_same_layer_pairs'] if p['status']=='FAIL']
    assert anchor['status']=='PASS' and image['geometry'].covers(pad['shape'])
    assert opened['connections']=='FAIL' and opened['no_short']=='PASS' and len(failed)==15
    assert all(c['terminal'] in (p['a'],p['b']) for p in failed)
    bridge_rec=next(f for f in b['faults'] if f['name']=='new_bridge')
    bridge=Path(bridge_rec['file']);assert sha(bridge)==bridge_rec['sha256']
    shorted=intent_check(read_image(bridge)['geometry'],pads,routes,'F.Cu')
    assert shorted['no_short']=='FAIL' and shorted['shorts']
    prior=json.loads((ROOT/'out/halpi2_case/history_before.json').read_text())
    for path,digest in prior.items():assert sha(ROOT/path)==digest,path
    result={'case':m['case_id'],'status':'PASS','manifest_sha256':sha(manifest_path),'baseline_sha256':sha(old),'source_revision':m['source_commit'],'reference_class':m['reference_class'],'positives':results,'terminal_export_mapping':mapping,'named_open_control':{'status':'PASS','observed_connections':opened['connections'],'observed_no_short':opened['no_short'],'anchors':anchor,'pad_shape_fully_retained':True,'cut_rectangles_mm':rectangles,'failed_expected_pairs':failed,'file':str(fault),'sha256':sha(fault)},'bridge_control':{'status':'PASS','file':str(bridge),'sha256':sha(bridge),'observed':shorted},'history_files_unchanged':len(prior),'original_aggregate':'NOT_ESTABLISHED','GlowStitch_electrical':'NOT_ESTABLISHED','source_aware_profile':'PASS (preserved 2e004b1 result)','Cursor':'NOT_RUN: CHANNEL_UNAVAILABLE','factory':'NOT_ESTABLISHED','remaining_gap':'No missing prerequisite within this same-layer native-intent case. Cross-layer, schematic agreement, unlabelled copper and process approval are excluded and remain unestablished.','script_sha256':sha(Path(__file__))}
    (run/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'run':str(run),'case':'PASS','pairs_per_layer':120,'terminals':64,'named_open_failed_pairs':len(failed),'short_nets':shorted['shorts'],'history_files_unchanged':len(prior)}))
if __name__=='__main__':main()
