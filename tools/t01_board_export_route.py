"""Eighteen source/T01/export gates. No renderer, display budget or fixed input pair."""
from pathlib import Path
from datetime import datetime,timezone
import sys,subprocess,threading,uuid
from src.stage_abi.store import ArtifactStore,digest
from src.pcb_data_abi.roi import local
from src.pcb_data_abi.board_custody import ROI,T01,CHECK,FILES,checkpoint
from src.pcb_data_abi.input_directory import verify_snapshot
from src.t01_board.adapter import BoardAdapter
from tools.t01_board_route import BoardRoute,initialize as board_initialize
from tools.t01_native_route import require_native,closed
from tools.t01_operator_host import ROOT,read,fresh,check
from tools import t01_board_host as host

STEPS=(*ROI,*T01,CHECK,*FILES)
CONTRACT=ROOT/'contracts/operator/t01_board_export.json'
PRODUCERS=['tools/t01_board_export_route.py','tools/t01_board_export_jobs.py','tools/t01_directory_intake_worker.py','tools/pcb_t01_board_export_operator.py','tools/start_t01_board_export_operator.py','tools/pcb_directory_data_abi.py','src/pcb_data_abi/input_directory.py','src/pcb_data_abi/directory_scope.py','src/pcb_data_abi/raw_directory.py','contracts/operator/t01_board_export.json']

def initialize(session):
    root=board_initialize(session)
    fresh(root/'EXPORT_ONLY_START.json',dict(rendering='NOT_REQUESTED',producer_files={p:digest((ROOT/p).read_bytes())for p in PRODUCERS}))
    return root

class ExportOnlyRoute(BoardRoute):
    OPERATION_AUTHORITY='Explicit raw directory → complete F.Cu source → T01 → audited KiCad/Gerber export; no rendering or T02-T05'
    def __init__(self,session,runner=subprocess.run):
        self.session=local(session,True);self.identity=dict(require_native(),board_implementation=BoardAdapter().describe()['implementation'])
        self.route_id='route-'+uuid.uuid4().hex;self.lock=threading.RLock();self.receipt_hashes={};self.runner=self._bounded_runner(runner)
        self.cap={};self.operations=list(STEPS);self.position=0;self.pending=None;self.responses={};self.accepted=[];self.audit_hashes={};self.bound_outputs={};self.submitted=False;self.halted=False
        (self.session/'audits').mkdir();(self.session/'operator').mkdir();fresh(self.session/'DECISION_POLICY.json',read(CONTRACT))
    def _bounded_runner(self,runner):
        def run(argv,**kwargs):
            budget=read(CONTRACT)['native_timeout_seconds'];kwargs['timeout']=budget.get(self.operations[self.position],budget['default'])
            return runner(argv,**kwargs)
        return run
    def info(self):
        return dict(route_id=self.route_id,native=self.identity,scope=self.OPERATION_AUTHORITY,source_snapshot_sha256=digest((self.session/'START.json').read_bytes()),sequence=self.operations,accepted_operations=self.accepted,pending_audit=self.pending['attempt_id']if self.pending else None,next_operation=self.operations[self.position]if self.position<len(self.operations)else None,status='HALTED'if self.halted else'COMPLETE_AUDITED_BOARD_EXPORT_SEQUENCE'if self.position==len(self.operations)else'READY_FOR_AUDIT'if self.pending else'READY_FOR_OPERATION'if self.submitted else'BOARD_INPUTS_REQUIRED',rendering='NOT_REQUESTED')
    def _prior_integrity(self):
        super()._prior_integrity()
        for p,h in read(self.session/'EXPORT_ONLY_START.json')['producer_files'].items():
            if digest((ROOT/p).read_bytes())!=h:raise ValueError('EXPORT_ONLY_PRODUCER_CHANGED:'+p)
    def submit(self,args,caller):
        if self.submitted or self.position or self.halted:raise ValueError('EXPORT_ONLY_INTAKE_CLOSED')
        closed(args,{'kicad','gerber'});check(self.session)
        job=read(self.session.parent/'job.json')
        if job.get('task_scope')!='full-board-export-only'or args!=job['staged']:raise ValueError('EXPLICIT_DIRECTORY_JOB_REQUIRED')
        manifest=local(job['input_directory'])
        if digest(manifest.read_bytes())!=job['input_directory_sha256']:raise ValueError('INPUT_DIRECTORY_MANIFEST_CHANGED')
        paths=verify_snapshot(read(manifest),manifest.parent/'raw_inputs')
        if args!={'kicad':str(paths['kicad']),'gerber':str(paths['F.Cu'])}:raise ValueError('INPUT_DIRECTORY_PAIR_MISMATCH')
        inputs={k:dict(path=v,sha256=digest(Path(v).read_bytes()))for k,v in args.items()}
        fresh(self.session/'board_inputs.json',inputs);fresh(self.session/'board_intake.json',dict(arguments=args,caller=caller,inputs=inputs,directory_manifest=str(manifest),directory_manifest_sha256=job['input_directory_sha256'],source_origin='Explicit supplied directory, freshly staged; no predecessor/crop/candidate reuse'))
        reg=self.session/'board_source_host.json';fresh(reg,dict(schema='pcb-board-directory-host/1',inputs=inputs,output=str(self.session/'data_board'),directory_manifest=str(manifest),directory_manifest_sha256=job['input_directory_sha256']))
        self.cap=dict(registry_path=str(reg),registry_sha256=digest(reg.read_bytes()));self.submitted=True
        self.bound_outputs[str(manifest)]=digest(manifest.read_bytes());self.bound_outputs[str(self.session.parent/'job.json')]=digest((self.session.parent/'job.json').read_bytes())
        if read(manifest).get('schema')=='pcb-raw-input-directory/2':
            receipt=local(self.session.parent/'INTAKE_RECEIPT.json');intake=read(receipt)
            if intake.get('schema')!='pcb-native-directory-intake/1'or intake.get('job')!=str(self.session.parent)or intake.get('rendering')!='NOT_REQUESTED':raise ValueError('NATIVE_DIRECTORY_INTAKE_RECEIPT_REQUIRED')
            self.bound_outputs[str(receipt)]=digest(receipt.read_bytes())
            for key in('request','identification'):
                path=local(intake[key])
                if digest(path.read_bytes())!=intake[key+'_sha256']:raise ValueError('NATIVE_DIRECTORY_INTAKE_EVIDENCE_CHANGED')
                self.bound_outputs[str(path)]=intake[key+'_sha256']
            if intake['identification_sha256']!=job['input_directory_sha256']:raise ValueError('NATIVE_DIRECTORY_IDENTIFICATION_BINDING_CHANGED')
        for row in read(manifest)['files']:
            path=manifest.parent/'raw_inputs'/row['relative_path'];self.bound_outputs[str(path)]=digest(path.read_bytes())
        self.bound_outputs[str(reg)]=digest(reg.read_bytes())
        return dict(status='BOARD_INPUTS_BOUND',inputs=inputs,scope='NOT_VERIFIED',construction='NOT_RUN',rendering='NOT_REQUESTED')
    def _argv(self,path):
        op=self.operations[self.position]
        if op in ROI:return [sys.executable,'-B',str(ROOT/'tools/pcb_directory_data_abi.py'),'--registry',self.cap['registry_path'],'--registry-sha256',self.cap['registry_sha256'],'--input',str(path)]
        return super()._argv(path)
    def _facts(self,op,response,code,path):
        facts=super()._facts(op,response,code,path)
        if op==ROI[0]:
            manifest=read(Path(read(self.session.parent/'job.json')['input_directory']))
            count=sum(row['kind']=='gerber'for row in manifest['files'])
            if facts.get('all_supplied_layers_verified')is not True or facts.get('provided_gerber_files')!=count:raise ValueError('ALL_DIRECTORY_LAYERS_MUST_BE_VERIFIED')
            if manifest.get('schema')=='pcb-raw-input-directory/2':
                excluded=sum(row['kind']=='companion'for row in manifest['files'])
                if facts.get('excluded_companion_files')!=excluded or facts.get('complete_input_accounting')is not True:raise ValueError('ALL_DIRECTORY_COMPANIONS_MUST_BE_ACCOUNTED')
        return facts
    def _audit(self,args,caller):
        self._valid_args(args,audit=True);folder=self.session/'audits'/uuid.uuid4().hex;folder.mkdir();fresh(folder/'request.json',dict(arguments=args,caller=caller))
        try:
            check(self.session);self._prior_integrity();p=self.pending
            if not p or args['attempt_id']!=p['attempt_id']:raise ValueError('NO_MATCHING_PENDING_AUDIT')
            a=args['audit'];closed(a,{'verdict','response_sha256','observed','note'})
            if a['verdict']!='PASS'or a['response_sha256']!=p['result']['raw_response_sha256']or a['observed']!=p['result']['facts']or type(a['note'])is not str or not 1<=len(a['note'])<=300:raise ValueError('OPERATOR_AUDIT_MISMATCH')
            op=p['operation'];self.responses[op]=p['response'];self.accepted.append(op);self.position+=1;self.pending=None
            result=dict(status='PASS_SLICE_OBSERVATION_AUDIT',accepted_operation=op,next_operation=self.operations[self.position]if self.position<len(self.operations)else None,authority='Technical observation only; owner PENDING_USER',native=self.identity,route_id=self.route_id)
            fresh(folder/'decision.json',result)
            for file in folder.iterdir():self.audit_hashes[str(file)]=digest(file.read_bytes())
            if op==ROI[-1]:
                self.cap=host.prepare(self.session);self.store=ArtifactStore(Path(self.cap['store_path']));self.negative=self.store.put('english-spec',(ROOT/'contracts/t01_board/english.txt').read_bytes().replace(b'hard gap 0.020 mm',b'hard gap 0.001 mm'))
            elif op=='t01_compile':self.cap=host.register(self.session,p['path']/'abi/stdout.json')
            elif op=='t01_plan':self.cap=host.grant(self.session,p['path']/'abi/stdout.json')
            elif op==CHECK:
                extras=[self.session/n for n in('RECEIPT.json','board_inputs.json','data_board/verified.json','data_board/scope.json')]
                proof=checkpoint(self.session,'T01_CHECKPOINT.json',(*ROI,*T01,CHECK),extras);self._set_host(dict(schema='pcb-board-data-host/1',output=str(self.session/'data_output'),**proof),'pipeline_data_host.json')
            elif op==FILES[-1]:
                extras=[p for p in(self.session/'data_output').rglob('*')if p.is_file()]+[self.session/n for n in('RECEIPT.json','data_board/verified.json','T01_CHECKPOINT.json','board_intake.json','EXPORT_ONLY_START.json')]
                proof=checkpoint(self.session,'EXPORT_CHECKPOINT.json',STEPS,extras)
                fresh(self.session/'EXPORT_ONLY_RECEIPT.json',dict(status='PASS_FRESH_DIRECTORY_T01_EXPORT',operations=list(STEPS),source_origin='Explicit raw-input directory; fresh source construction and reconstruction',rendering='NOT_REQUESTED',owner='PENDING_USER',independent='NOT_RUN',**proof))
            return result
        except Exception as error:
            self.halted=True
            name='handoff_failure.json'if(folder/'decision.json').exists()else'decision.json'
            fresh(folder/name,dict(status='FAIL',error=str(error)));raise
