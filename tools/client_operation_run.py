"""Replayable client region challenge, actual execution and independent controls."""
from pathlib import Path
import datetime, hashlib, importlib.metadata, json, shutil, sys, time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from shapely.geometry import box
from src.client_gerber import sha,parse,read_region,locate,move_bytes,break_connection,append_bridge,AdmissionError
from src.client_operation import generate
from src.client_validation import validate
ROOT=Path(__file__).resolve().parents[1]

def clean_report(report,path):
    r=dict(report);g=r.pop('geometry',None)
    if g is not None:(path.parent/'copper.wkb').write_bytes(g.wkb)
    path.write_text(json.dumps(r,indent=2)+'\n');return r

def main():
    source=ROOT/'external/sources/12_copper_layers_pcb_gbr';bottom=source/'vme-wren-Bottom Layer.gbr';mask=source/'vme-wren-Bottom Solder.gbr'
    run=ROOT/'out/client_operation'/datetime.datetime.now(datetime.timezone.utc).strftime('run_%Y%m%dT%H%M%S_%fZ');run.mkdir(parents=True)
    digests={str(p.relative_to(source)):sha(p) for p in source.rglob('*') if p.is_file()}
    anchor=[117.211125,-231.667175];terminal=['R140','1'];g=parse(bottom);pi,pad,li,line=locate(g,terminal,anchor)
    # Author-provided demo challenge; no allegation about the supplied original.
    before_center=[round(pad.x+.35,6),pad.y];before=run/'controlled_before.gbr';before.write_bytes(move_bytes(bottom.read_bytes(),pad,line,before_center))
    shutil.copyfile(mask,run/'fixed_mask.gbr');shutil.copyfile(source/'vme-wren-Edge_Cuts.gbr',run/'outline.gbr')
    contract={'schema':'client-gerber-move-v1','operation':'MovePadWithConnections','intent_basis':'Explicit demonstration policy: preserve the observed original local connection and restore pad-to-opening alignment. Not client manufacturing requirements.','scenario':'Controlled +0.35 mm X offset of supplied R140.1 and its trace endpoint; original already aligned.','source_sha256':sha(bottom),'input_sha256':sha(before),'mask_sha256':sha(mask),'terminal':terminal,'source_net_label':list(pad.attrs['.N']),'opening_anchor_mm':[pad.x,pad.y],'before_center_mm':before_center,'anchor_mm':anchor,'trace_width_mm':line.aperture.diameter,'writable_ordinals':[pi,li],'allowed_region_mm':[115.8,-231.8,118.1,-230.45],'max_move_mm':.4,'center_tolerance_mm':.005,'minimum_connection_width_mm':.18,'minimum_clearance_mm':.1,'area_tolerance_mm2':1e-8,'protected_neighbor':{'terminal':['R140','2'],'source_net_label':['P3V3'],'center_mm':[116.271125,pad.y]},'fixed_anchor_tolerance_mm':1e-6,'electrical_scope':'Declared local same-layer continuity and physical separation only; no schematic/cross-layer/manufacturing acceptance.'}
    (run/'contract.json').write_text(json.dumps(contract,indent=2)+'\n');print('Compose source and controlled input',flush=True)
    reference_image=read_region(bottom,contract['allowed_region_mm']);before_image=read_region(before,contract['allowed_region_mm'])
    (run/'original_region.wkb').write_bytes(reference_image['geometry'].wkb);(run/'before_region.wkb').write_bytes(before_image['geometry'].wkb)
    mask_image=read_region(mask,contract['allowed_region_mm']);(run/'mask_region.wkb').write_bytes(mask_image['geometry'].wkb)
    # Admission evidence: explicit SMD attribute, unique source occurrence, fixed anchor.
    source_check=validate(bottom,bottom,bottom,mask,{**contract,'before_center_mm':[pad.x,pad.y]},reference_image,reference_image)
    clean_report(source_check,run/'original_measurement.json')
    before_check=validate(bottom,before,before,mask,contract,reference_image,before_image)
    clean_report(before_check,run/'before_measurement.json')
    events=[]
    def event(name,**payload):events.append({'event':name,'timestamp_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),**payload})
    event('PLANNED',contract_sha256=sha(run/'contract.json'),input_sha256=sha(before))
    candidate,plan=generate(before,mask,contract,run/'staging');event('STAGED',candidate_sha256=sha(candidate))
    event('EXPORTED',candidate_file='accepted/candidate.gbr',candidate_sha256=sha(candidate))
    print('Validate produced Gerber',flush=True)
    positive=validate(bottom,before,candidate,run/'staging/mask.gbr',contract,reference_image,before_image)
    positive_report=clean_report(positive,run/'staging/validation.json');event('VALIDATED',status=positive_report['status'],report_sha256=sha(run/'staging/validation.json'))
    if positive_report['status']!='PASS':
        (run/'failure.json').write_text(json.dumps(positive_report,indent=2));raise RuntimeError('Produced candidate failed; staging retained, no publication')
    (run/'staging').rename(run/'accepted');event('COMMITTED',candidate_sha256=sha(run/'accepted/candidate.gbr'))
    accepted_hash=sha(run/'accepted/candidate.gbr');(run/'execution.json').write_text(json.dumps({'operation':plan,'events':events,'state':'COMMITTED','source_unchanged':sha(bottom)==contract['source_sha256'],'candidate_sha256':accepted_hash},indent=2)+'\n')
    positives=run/'accepted/candidate.gbr';cg=parse(positives);_,cp,_,cl=locate(cg,terminal,anchor)
    controls={}
    for name in ['open','bridge']:
        folder=run/name;folder.mkdir();path=folder/'candidate.gbr'
        if name=='open':data=break_connection(positives.read_bytes(),cl,[cl.x1,-231.55])
        else:data=append_bridge(positives.read_bytes(),[cp.x,cp.y],contract['protected_neighbor']['center_mm'],cl.aperture.original_number)
        path.write_bytes(data);print('Validate',name,'control',flush=True)
        result=clean_report(validate(bottom,before,path,mask,contract,reference_image,before_image),folder/'validation.json')
        expected='connection' if name=='open' else 'separation'
        assert result['status']=='FAIL' and next(c for c in result['checks'] if c['id']==expected)['status']=='FAIL'
        controls[name]={'status':'EXPECTED_REJECTION_DETECTED','required_failed_check':expected,'candidate_sha256':sha(path),'report_sha256':sha(folder/'validation.json'),'failed_checks':[c['id'] for c in result['checks'] if c['status']=='FAIL'],'publication':'REJECTED','prior_accepted_unchanged':sha(positives)==accepted_hash}
        (folder/'execution.json').write_text(json.dumps({'state':'REJECTED','validation_status':'FAIL','source_unchanged':True,'previous_accepted_sha256':accepted_hash,'previous_accepted_unchanged':sha(positives)==accepted_hash,'events':['PLANNED','STAGED','EXPORTED','VALIDATED','REJECTED']},indent=2)+'\n')
    # The failed open control is retained as rejected staging evidence; it never
    # replaces the already committed candidate. Recheck the accepted bytes now.
    rollback={'attempt':'Stage the disconnected control against the accepted source revision','staged_candidate':'open/candidate.gbr','validation_report':'open/validation.json','state':'REJECTED','published_as_accepted':False,'previous_accepted_sha256':accepted_hash,'previous_accepted_unchanged':sha(positives)==accepted_hash,'rejected_control_sha256':sha(run/'open/candidate.gbr')}
    (run/'rollback.json').write_text(json.dumps(rollback,indent=2)+'\n')
    # Exercise a fail-before-export boundary and retain the actual exception.
    bad={**contract,'max_move_mm':.01}
    try:generate(before,mask,bad,run/'forbidden_staging');raise AssertionError('movement admission unexpectedly succeeded')
    except AdmissionError as exc:admission={'status':'EXPECTED_REJECTION_DETECTED','error':str(exc),'candidate_published':(run/'forbidden_staging').exists(),'previous_accepted_unchanged':sha(positives)==accepted_hash}
    assert not admission['candidate_published'] and admission['previous_accepted_unchanged']
    after={str(p.relative_to(source)):sha(p) for p in source.rglob('*') if p.is_file()};assert digests==after
    result={'schema':'client-operation-evidence-v1','status':'PASS','scope':contract['electrical_scope'],'run_id':run.name,'contract_sha256':sha(run/'contract.json'),'source_unchanged':True,'source_sha256':digests,'original_aligned':source_check['status'],'controlled_before':before_check['status'],'positive':positive_report,'controls':controls,'admission_failure':admission,'rollback':rollback,'candidate_byte_identical_to_supplied_original':accepted_hash==sha(bottom),'versions':{p:importlib.metadata.version(p) for p in ['gerbonara','shapely']},'implementation_sha256':{p:sha(ROOT/p) for p in ['src/client_gerber.py','src/client_operation.py','src/client_validation.py','tools/client_operation_run.py']},'independent_cursor_review':'NOT_RUN: CHANNEL_UNAVAILABLE','manufacturing':'NOT_ESTABLISHED'}
    (run/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    (ROOT/'out/client_operation/current.txt').write_text(str(run)+'\n');print(run,flush=True)
if __name__=='__main__':main()
