"""Source-only setup; data ABI locates an attachment before T01 receives any ROI."""
from src.clearance_policy import weakened_english
from datetime import datetime,timezone
from pathlib import Path
import sys,threading,subprocess,uuid,shutil
from src.stage_abi.store import ArtifactStore,digest
from src.pcb_data_abi.roi import local,bound
from src.pcb_data_abi.crop_custody import ROI,T01,CHECK,FILES,RENDER,STEPS,checkpoint
from src.t01_crop.adapter import CropAdapter
from src.t01_crop.paging import read_pages,inspection_binding
from src.render_abi.crop_pixels import choose_pixels
from src.crop_circle_sources import verify_assets
from src.trace_first_pipeline import frozen_fingerprint
from tools.t01_native_route import NativeRoute,RouteError,closed,require_native,producer_files
from tools.t01_c01_route import C01Route
from tools.t01_operator_host import ROOT,HANDOFF,read,fresh,check
from tools import t01_crop_host as host

def initialize(session):
    session=local(session,True)
    if session.exists():raise ValueError('FRESH_PROJECT_OUTPUT_REQUIRED')
    if shutil.disk_usage(ROOT).free < 2_000_000_000:
        raise ValueError('CROP_STORAGE_PREFLIGHT_FAILED: at least 2 GB free required')
    identity=require_native();session.mkdir(parents=True)
    files=producer_files()+list((ROOT/'src/t01_crop').glob('*.py'))+list((ROOT/'contracts/t01_crop').glob('*'))+[ROOT/'tools'/n for n in ('t01_crop_route.py','t01_crop_host.py','t01_crop_abi.py','pcb_crop_candidate_check.py','pcb_t01_operator.py','start_t01_crop_operator.py','t01_crop_jobs.py','t01_crop_attachments.py','t01_crop_launcher.py','Start_T01_Native_Launcher.command')]
    fresh(session/'START.json',dict(status='CROP_SOURCE_ONLY_SETUP_NO_ROI',assets=verify_assets(),protected_freezes=[frozen_fingerprint(ROOT,e) for e in read(HANDOFF/'PROTECTED_FREEZES.json')],T01_delivery_files={str(p.relative_to(ROOT)):digest(p.read_bytes()) for p in files},runtime_fingerprint=identity['shared_runtime'],T01_implementation=identity['implementation']))
    (session/'attempts').mkdir();return session

class CropRoute(C01Route):
    OPERATION_STATUS='PASS_CROP_OPERATION_CHECKS'
    OPERATION_AUTHORITY='Data-ABI verified attachment ROI → T01 → exports → display; no T02-T05'
    def __init__(self,session,runner=subprocess.run):
        self.session=local(session,True);self.identity=dict(require_native(),crop_implementation=CropAdapter().describe()['implementation'])
        self.route_id='route-'+uuid.uuid4().hex;self.lock=threading.RLock();self.receipt_hashes={};self.runner=runner
        self.cap={};self.operations=list(STEPS);self.position=0;self.pending=None;self.responses={};self.accepted=[];self.audit_hashes={};self.bound_outputs={};self.submitted=False;self.halted=False
        (self.session/'audits').mkdir();(self.session/'operator').mkdir()
        fresh(self.session/'DECISION_POLICY.json',read(ROOT/'contracts/operator/t01_crop.json'))
    def tools(self):
        ts=[t for t in super().tools() if t['name'] not in ('native_route.conformance','t01_describe')]
        ts.append(dict(name='crop.submit',description='Hash-bind the actual image attachment and optional replacement inputs. No geometry construction.',input_schema=dict(type='object',additionalProperties=False,properties={k:dict(type='string') for k in ('crop','kicad','gerber')},required=['crop'])))
        return ts
    def info(self):
        return dict(route_id=self.route_id,native=self.identity,scope=self.OPERATION_AUTHORITY,source_snapshot_sha256=digest((self.session/'START.json').read_bytes()),sequence=self.operations,accepted_operations=self.accepted,pending_audit=self.pending['attempt_id'] if self.pending else None,next_operation=self.operations[self.position] if self.position<len(STEPS) else None,status='HALTED' if self.halted else 'COMPLETE_AUDITED_CROP_SEQUENCE' if self.position==len(STEPS) else 'READY_FOR_AUDIT' if self.pending else 'READY_FOR_OPERATION' if self.submitted else 'ATTACHMENT_REQUIRED')
    def _bind(self,folder):
        for p in folder.rglob('*'):
            if p.is_file():self.bound_outputs[str(p)]=digest(p.read_bytes())
    def _prior_integrity(self):
        super()._prior_integrity()
        for path,h in self.bound_outputs.items():
            if digest(local(path).read_bytes())!=h:raise ValueError('CROP_BOUND_EVIDENCE_CHANGED:'+path)
    def submit(self,args,caller):
        if self.submitted or self.position or self.halted:raise RouteError('CROP_INTAKE_CLOSED','Fresh session required')
        if type(args)is not dict or not {'crop'}<=set(args)<= {'crop','kicad','gerber'}:raise ValueError('CROP_INPUTS_INVALID')
        check(self.session);defaults=read(ROOT/'contracts/operator/t01_project.json')['inputs'];inputs={}
        for k in ('crop','kicad','gerber'):
            path=local(args[k] if k in args else ROOT/defaults[k]['path'])
            inputs[k]=dict(path=str(path),sha256=digest(path.read_bytes()))
            if k not in args and inputs[k]['sha256']!=defaults[k]['sha256']:raise ValueError('PROJECT_INPUT_CHANGED')
        fresh(self.session/'crop_inputs.json',inputs);fresh(self.session/'crop_intake.json',dict(arguments=args,caller=caller,inputs=inputs))
        reg=self.session/'roi_host.json';fresh(reg,dict(schema='pcb-roi-host/1',inputs=inputs,output=str(self.session/'data_roi')))
        self.cap=dict(registry_path=str(reg),registry_sha256=digest(reg.read_bytes()));self.submitted=True
        for k in inputs:self.bound_outputs[inputs[k]['path']]=inputs[k]['sha256']
        self.bound_outputs[str(reg)]=digest(reg.read_bytes())
        return dict(status='CROP_INPUTS_BOUND',inputs=inputs,roi='NOT_LOCATED',construction='NOT_RUN')
    def _request_for(self,op,rid):
        if op in T01:
            request=super()._request_for(op,rid)
            if op in ('t01_inspect','t01_compare'):
                request['operation']=op+'_all'
                request['payload']=dict(request['payload'],page_size=100)
                request['payload'].pop('cursor',None)
            return request
        return dict(abi_version='pcb-render-abi/1' if op in RENDER else 'pcb-crop-handoff/1' if op==CHECK else 'pcb-data-abi/1',request_id=rid,operation=op)
    def _argv(self,path):
        op=self.operations[self.position]
        if op==CHECK:return [sys.executable,'-B',str(ROOT/'tools/pcb_crop_candidate_check.py'),'--session',str(self.session),'--input',str(path)]
        script='t01_crop_abi.py' if op in T01 else 'pcb_render_abi.py' if op in RENDER else 'pcb_data_abi.py'
        argv=[sys.executable,'-B',str(ROOT/'tools'/script),'--registry',self.cap['registry_path'],'--registry-sha256',self.cap['registry_sha256'],'--input',str(path)]
        if op in T01:argv+=['--store',self.cap['store_path']]
        return argv
    def _facts(self,op,response,code,path):
        r=response.get('result')
        def require(ok,why):
            if not ok:raise RouteError('CROP_OPERATION_CHECK_FAILED',why)
        if op=='t01_negative_compile':
            require(code==2 and response['status']=='REJECTED' and r is None and response['error']['code']=='T01_ENGLISH_UNSUPPORTED','Negative English contract rejected without policy')
            return dict(negative_code=response['error']['code'],policy_emitted=False,construction_status='NOT_RUN')
        require(code==0 and response['status']=='OK' and response['error'] is None,'Actual native response: '+str(response.get('error')))
        if op not in T01:
            f=r['facts'];require(f.get('passed') is True,'Actual facts passed')
            if op==ROI[0]:require(f.get('source_gerber_correspondence') is True and f.get('registration_fit_used') is False and f.get('source_objects',0)>0 and f.get('layer')=='F.Cu','Qualified complete native input correspondence')
            elif op==ROI[1]:require(f.get('located') is True and f.get('unique_in_supported_search') is True and r.get('uncertainty_mm',1)<=.05,'Bounded unambiguous location')
            elif op==ROI[2]:require(f.get('location_verified') is True and f.get('kicad_gerber_correspondence') is True and f.get('matched_landmarks',0)>=6 and f.get('deliberate_controls')==3,'Verified ROI and all location controls')
            elif op==CHECK:require(all(f.get(k) is True for k in ('complete_source_coverage','full_reconstruction_passed','protected_sources_unchanged')) and f.get('historical_candidate_read') is False,'Fresh source handoff without historical oracle')
            elif op in ('pcb_kicad_write','pcb_kicad_verify','pcb_gerber_verify'):
                require(f.get('canonical_sites')==self.discovery['unique_sites'] and f.get('source_occurrences')==self.discovery['occurrences'],'Export covers complete discovered selection and aliases')
                if op=='pcb_kicad_verify':require(f.get('protected_nodes_equal') is True and f.get('all_target_contours_pass') is True,'All native target and protected nodes')
                if op=='pcb_gerber_verify':require(f.get('protected_fcu_atoms_equal') is True and f.get('protected_other_layers')==8,'Copper atoms and eight other layers preserved')
            elif op=='pcb_gerber_export':require(f.get('native_export_exit')==0 and f.get('layers')==9 and f.get('precision_decimals')==6 and f.get('kicad_version')=='10.99.0','Pinned native nine-layer export')
            elif op in ('pcb_export_controls','render_controls'):
                count=3 if op=='pcb_export_controls' else 4
                require(f.get('deliberate_controls')==count and f.get('all_rejected_for_expected_reason') is True and len(r['controls'])==count and all(c['status']=='PASS_EXPECTED_REJECTION' for c in r['controls']),'Every deliberate control rejected for its expected reason')
            elif op=='render_compare':require(f.get('panels')==2 and f.get('native_commands')==5 and f.get('geometry_edited') is False and f.get('common_viewport') is True,'Native two-file rendering without geometry editing')
            elif op=='render_verify':
                require(f.get('panels_checked')==2 and all(f.get(k) is True for k in ('all_pixels_checked','common_frame_verified','input_hashes_unchanged','output_hashes_unchanged','svg_viewport_verified')) and set(r['audits'])=={'kicad','gerber'} and all(a.get('passed') is True and a.get('mismatches_outside_band')==0 for a in r['audits'].values()),'Complete raster, hash and frame audits')
            if op in ROI:self._bind(self.session/'data_roi')
            elif op==CHECK:self.bound_outputs[str(self.session/'RECEIPT.json')]=digest((self.session/'RECEIPT.json').read_bytes())
            elif op in FILES:self._bind(self.session/'data_output')
            else:self._bind(self.session/'render_output')
            return f
        if op=='t01_compile':
            require(r['policy']['binding_ref']==self.cap['binding_ref'] and len(r['policy']['clause_trace'])==16 and r['construction_status']=='NOT_RUN','16 clauses bound to actual source/ROI')
            return dict(clauses=16,hard_gap_mm=r['policy']['settings']['hard_gap'],construction_status='NOT_RUN')
        if op=='t01_discover':
            d=r['discovery'];self.discovery=d
            require(0<d['unique_sites']<=d['source_objects'] and len(set(d['source_ids']))==d['unique_sites'] and d['source_objects']==self.cap['source_objects'],'Complete dynamic source discovery within actual source inventory')
            binding=self.store.get_json(self.cap['binding_ref'],kind='t01-binding')
            objects,index=read_pages(self.store,binding['source_inventory_ref'],binding=dict(source_sha256=binding['source_sha256'],manifest_sha256=binding['manifest_sha256']),kind='t01-source-inventory',identity=lambda x:x['source_id'])
            require(len(objects)==d['source_objects'],'Complete original source pages')
            return dict(source_objects=d['source_objects'],source_pages=len(index['pages']),canonical_sites=d['unique_sites'],aliases=d['occurrences'],construction_status='NOT_RUN')
        n=self.discovery['unique_sites'];a=self.discovery['occurrences']
        if op=='t01_inspect':
            request=self._request_for(op,response['request_id'])
            records,index=read_pages(self.store,r['pagination_ref'],binding=inspection_binding(request,request['payload']['selection_ref']),kind='t01-inspection',identity=lambda x:x['record']['source_id'])
            require(r['total_records']==n and len(records)==n and records==r['records'] and set(r['selected_source_ids'])==set(self.discovery['source_ids']) and {x['record']['source_id'] for x in records}==set(self.discovery['source_ids']) and r['next_cursor'] is None and r['page_count']==len(index['pages']),'Complete paginated inspection')
            return dict(inspected_sites=n,inspection_pages=len(index['pages']),cursor_exhausted=True,construction_status='NOT_RUN')
        if op=='t01_plan':
            p=r['plan'];allocation=p['details']['allocation']
            require(set(p['details']['targets'])==set(self.discovery['source_ids']) and p['implementation']==self.identity['crop_implementation'] and p['runtime']==self.identity['shared_runtime'] and r['construction_status']=='NOT_RUN','Complete runtime-bound plan')
            return dict(targets=n,groups=len(allocation['groups']),concentric_nested_pairs=sum('concentric_source_proof' in g for g in allocation['groups']),boundary_keep_sites=len(allocation['boundary_keep_source_ids']),priority_pool_sites=len(allocation['priority_pool_source_ids']),construction_status='NOT_RUN')
        if op in ('t01_run','t01_verify'):
            require(r['job']['status']=='COMPLETED' and not r['reused'] and r['result']['execution_evidence']['mode']=='FRESH_EXECUTION','Fresh execution')
            if op=='t01_run':
                c=r['result']['candidate'];require(c['unique_sites']==n and c['source_occurrences']==a and len(c['final_checks'])==n and all(q['check']['passed'] for q in c['final_checks']) and c['owner_status']=='PENDING' and c['independent_status']=='NOT_RUN','Complete construction and assembled checks')
                return dict(canonical_sites=n,aliases=a,counts=c['counts'],neighbor_controls=len(c['events']),final_checks_passed=True,fresh_execution=True,owner_status=c['owner_status'],independent_status=c['independent_status'])
            v=r['result']['verification'];q=v['check'];require(v['geometric_status']=='PASS' and q['passed'] and not q['failures'] and q['reconstructed_sites']==n and q['reconstructed_alias_occurrences']==a and q['final_assembled_checks']==n and v['candidate_ref']==self.responses['t01_run']['result']['result']['candidate_ref'],'Complete source reconstruction')
            return dict(geometric_status='PASS',reconstructed_sites=n,aliases=a,assembled_checks=n,fresh_reconstruction=True,owner_status=v['owner_status'],independent_status=v['independent_status'])
        if op=='t01_compare':
            request=self._request_for(op,response['request_id']);payload=request['payload']
            binding=dict(scene_ref=request['scene_ref'],policy_ref=request['policy_ref'],profile_id=request['profile_id'],**{k:v for k,v in payload.items() if k!='page_size'})
            records,index=read_pages(self.store,r['pagination_ref'],binding=binding,kind='t01-comparison',identity=lambda x:x['source_id'])
            require(len(records)==n and records==r['source_changes'] and {x['source_id'] for x in records}==set(self.discovery['source_ids']) and r['removed_area_mm2']<=1e-10 and r['page_count']==len(index['pages']),'Growth-only complete paginated comparison')
            return dict(selected_records=n,comparison_pages=len(index['pages']),added_area_mm2=r['added_area_mm2'],removed_area_mm2=r['removed_area_mm2'])
        require(r['owner_status']=='PENDING' and r['independent_status']=='NOT_RUN' and r['records']==[] and r['next_cursor'] is None,'No invented review acceptance')
        return dict(owner_status='PENDING',independent_status='NOT_RUN',decision_records=0)
    def _step(self,op,args,caller):
        if not self.submitted or self.halted:raise RouteError('CROP_ROUTE_CLOSED','Attachment required or failure retained')
        result=super()._step(op,args,caller)
        if result.get('error'):self.halted=True
        return result
    def _audit(self,args,caller):
        self._valid_args(args,audit=True);folder=self.session/'audits'/uuid.uuid4().hex;folder.mkdir();fresh(folder/'request.json',dict(arguments=args,caller=caller))
        try:
            check(self.session);self._prior_integrity();p=self.pending
            if not p or args['attempt_id']!=p['attempt_id']:raise ValueError('NO_MATCHING_PENDING_AUDIT')
            a=args['audit'];closed(a,{'verdict','response_sha256','observed','note'})
            if a['verdict']!='PASS' or a['response_sha256']!=p['result']['raw_response_sha256'] or a['observed']!=p['result']['facts'] or type(a['note'])is not str or not 1<=len(a['note'])<=300:raise ValueError('OPERATOR_AUDIT_MISMATCH')
            op=p['operation'];self.responses[op]=p['response'];self.accepted.append(op);self.position+=1;self.pending=None
            result=dict(status='PASS_SLICE_OBSERVATION_AUDIT',accepted_operation=op,next_operation=self.operations[self.position] if self.position<len(STEPS) else None,authority='Technical observation only; owner PENDING_USER',native=self.identity,route_id=self.route_id)
            fresh(folder/'decision.json',result)
            for file in folder.iterdir():self.audit_hashes[str(file)]=digest(file.read_bytes())
            if op==ROI[-1]:
                choose_pixels(read(self.session/'data_roi/roi_verified.json')['bounds_mm'],read(ROOT/'contracts/render/crop.json')['pixel_policy'])
                self.cap=host.prepare(self.session);self.store=ArtifactStore(Path(self.cap['store_path']));self.negative=self.store.put('english-spec',weakened_english((ROOT/'contracts/t01_crop/english.txt').read_bytes()))
            elif op=='t01_compile':self.cap=host.register(self.session,p['path']/'abi/stdout.json')
            elif op=='t01_plan':self.cap=host.grant(self.session,p['path']/'abi/stdout.json')
            elif op==CHECK:
                extras=[self.session/'RECEIPT.json',self.session/'crop_inputs.json',self.session/'data_roi/roi_verified.json',self.session/'data_roi/location.json']
                proof=checkpoint(self.session,'T01_CHECKPOINT.json',(*ROI,*T01,CHECK),extras);self._set_host(dict(schema='pcb-crop-data-host/1',output=str(self.session/'data_output'),**proof),'pipeline_data_host.json')
            elif op==FILES[-1]:
                extras=[p for p in (self.session/'data_output').rglob('*') if p.is_file()]+[self.session/'RECEIPT.json',self.session/'data_roi/roi_verified.json',self.session/'T01_CHECKPOINT.json']
                proof=checkpoint(self.session,'EXPORT_CHECKPOINT.json',(*ROI,*T01,CHECK,*FILES),extras)
                c=read(ROOT/'contracts/render/crop.json');b=read(self.session/'data_roi/roi_verified.json')['bounds_mm'];c.update(bounds_mm=b,pixels=choose_pixels(b,c['pixel_policy']),inputs={k:dict(path=str(p.relative_to(ROOT)),sha256=digest(p.read_bytes())) for k,p in {'kicad':self.session/'data_output/candidate/board.kicad_pcb','gerber':self.session/'data_output/candidate/gerbers/board-F_Cu.gbr'}.items()})
                cp=self.session/'pipeline_render_contract.json';fresh(cp,c);self._set_host(dict(schema='pcb-crop-render-host/1',contract_path=str(cp),contract_sha256=digest(cp.read_bytes()),output=str(self.session/'render_output'),**proof),'pipeline_render_host.json')
            return result
        except Exception as e:
            self.halted=True
            if not (folder/'decision.json').exists():fresh(folder/'decision.json',dict(status='FAIL',error=str(e)))
            else:fresh(folder/'handoff_failure.json',dict(status='FAIL_HANDOFF_AFTER_OBSERVATION',error=str(e),construction_authority='NOT_GRANTED_BY_FAILED_HANDOFF'))
            raise
    def _set_host(self,value,name):
        p=self.session/name;fresh(p,value);self.cap=dict(self.cap,registry_path=str(p),registry_sha256=digest(p.read_bytes()));self.bound_outputs[str(p)]=digest(p.read_bytes())
    def call(self,name,args,caller):
        with self.lock:
            if name=='crop.submit':return self.submit(args,caller)
            if name=='native_route.audit':return self._audit(args,caller)
            if name in self.operations:return self._step(name,args,caller)
            if name not in ('native_route.info','native_route.verify_receipt'):raise RouteError('TOOL_NOT_EXPOSED',name)
            return NativeRoute.call(self,name,args,caller)
