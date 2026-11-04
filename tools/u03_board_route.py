"""U03: fresh T01 prefix, T03 gates, native-width T04 gates and audited native export gates."""
import sys,uuid,subprocess
from pathlib import Path
from src.stage_abi.store import ArtifactStore,digest
from src.pcb_data_abi.board_custody import ROI,T01,CHECK,FILES,checkpoint
from src.u03_board.custody import CONTRACT,STEPS,T03,T04,PREFIX,THROUGH_T03,THROUGH_T04,CROP,operation_steps,through
from tools.t01_board_export_route import ExportOnlyRoute,initialize as base_initialize
from tools.t01_operator_host import ROOT,read,fresh,check
from tools import t01_board_host as host
from src.u03_board.selection import for_root

PRODUCERS=[*['src/u03_board/'+p.name for p in sorted((ROOT/'src/u03_board').glob('*.py'))],
    *['tools/'+n for n in ('u03_board_route.py','u03_board_jobs.py','u03_machine_audit.py','u03_board_auto_operator.py','pcb_u03_board_abi.py','pcb_u03_board_operator.py','pcb_u03_board_run.py','start_u03_board_operator.py','Run_U03_Board.command')], 'contracts/operator/u03_board.json']
PRODUCERS += ['src/u02_board/'+p.name for p in sorted((ROOT/'src/u02_board').glob('*.py'))]+['tools/u02_machine_audit.py','tools/pcb_workspace.py']
PRODUCERS += [str(p.relative_to(ROOT)) for p in sorted((ROOT/'src').glob('*.py'))]+[str(p.relative_to(ROOT)) for p in sorted((ROOT/'src/stage_abi').glob('*.py'))]
PRODUCERS += ['AGENTS.md','docs/agent_abi/U03_SINGLE_COMMAND.md','tests/test_u03_board.py','tests/test_u03_crops.py']
PRODUCERS=sorted(set(PRODUCERS)|{str(p.relative_to(ROOT)) for folder in ('src','tools','contracts') for p in (ROOT/folder).rglob('*') if p.is_file() and (p.suffix=='.py' or folder=='contracts')})


def initialize(session,mode='AGENT_REVIEWS_EACH_SLICE'):
    from tools.pcb_workspace import configure
    work=configure()
    if not Path(session).absolute().is_relative_to(work):raise ValueError('U03_LACIE_SESSION_REQUIRED')
    root=base_initialize(session,storage_root=work)
    job=read(root.parent/'job.json')
    crop=job.get('crop')
    if crop is not None:
        intake=read(root.parent/'INTAKE_RECEIPT.json');request=read(Path(intake['request']))
        if request.get('crop')!=crop['provided_path'] or digest(Path(crop['path']).read_bytes())!=crop['sha256']:raise ValueError('U03_CROP_JOB_BINDING_CHANGED')
        fresh(root/'U03_CROP_INPUT.json',crop)
    for name in PRODUCERS:
        target=root/'u03_code_snapshot'/name;target.parent.mkdir(parents=True,exist_ok=True)
        with target.open('xb') as stream:stream.write((ROOT/name).read_bytes())
    fresh(root/'U03_START.json',dict(schema='pcb-u03-start/1',mode=mode,crop_input=crop,operations=list(operation_steps(root)),producer_files={p:digest((ROOT/p).read_bytes()) for p in PRODUCERS},owner='PENDING_USER',rendering='NOT_REQUESTED'))
    return root


class U03Route(ExportOnlyRoute):
    CONTRACT=CONTRACT
    STEPS=STEPS
    TASK_SCOPE='u03-board'
    OPERATION_AUTHORITY='Explicit raw directory → fresh T01 → source-bound T03 retain-valid-paths → T04 native uniform width → audited native exports; no rendering or later U stages'

    def __init__(self,session,runner=subprocess.run):
        super().__init__(session,runner=runner)
        self.operations=list(operation_steps(self.session))
        self.crop=read(self.session.parent/'job.json').get('crop')
        self.selection=for_root(self.session)
        if self.crop is not None:
            from src.t01_board.adapter import BoardAdapter
            self.identity['board_implementation']=BoardAdapter().describe()['implementation']

    def info(self):
        result=super().info()
        if self.position==len(self.operations):result['status']='COMPLETE_AUDITED_U03_SEQUENCE'
        return result

    def _prior_integrity(self):
        super()._prior_integrity()
        if for_root(self.session)!=self.selection:
            raise ValueError('U03_CROP_SELECTION_CHANGED')
        if self.crop!=read(self.session.parent/'job.json').get('crop') or self.crop!=read(self.session/'U03_START.json').get('crop_input'):raise ValueError('U03_CROP_INPUT_CHANGED')
        if self.crop is not None and (read(self.session/'U03_CROP_INPUT.json')!=self.crop or digest(Path(self.crop['path']).read_bytes())!=self.crop['sha256']):raise ValueError('U03_CROP_INPUT_CHANGED')
        for p,h in read(self.session/'U03_START.json')['producer_files'].items():
            if digest((ROOT/p).read_bytes())!=h:raise ValueError('U03_PRODUCER_CHANGED:'+p)
            if digest((self.session/'u03_code_snapshot'/p).read_bytes())!=h:raise ValueError('U03_PRODUCER_SNAPSHOT_CHANGED:'+p)

    def _request_for(self,op,rid):
        if op in CROP:return dict(abi_version='pcb-u03-crop/1',request_id=rid,operation=op)
        if op in T03 or op in T04 or op in FILES:return dict(abi_version='pcb-u03-board/1',request_id=rid,operation=op)
        return super()._request_for(op,rid)

    def _argv(self,path):
        op=self.operations[self.position]
        if op in CROP:return [sys.executable,'-B',str(ROOT/'tools/u03_crop_roi_abi.py'),'--session',str(self.session),'--input',str(path)]
        if self.selection is not None and (op in T01 or op==CHECK):
            argv=[sys.executable,'-B',str(ROOT/'tools/u03_crop_t01_abi.py'),'--session',str(self.session),'--input',str(path)]
            if op in T01:argv+=['--registry',self.cap['registry_path'],'--registry-sha256',self.cap['registry_sha256'],'--store',self.cap['store_path']]
            return argv
        if op in T03 or op in T04 or op in FILES:
            argv=[sys.executable,'-B',str(ROOT/'tools/pcb_u03_board_abi.py'),'--session',str(self.session),'--input',str(path)]
            if op in FILES:argv+=['--registry',self.cap['registry_path'],'--registry-sha256',self.cap['registry_sha256']]
            return argv
        return super()._argv(path)

    def _facts(self,op,response,code,path):
        if op in CROP:
            if code!=0 or response['status']!='OK' or response['error'] is not None or response['result']['facts']['passed'] is not True:raise ValueError('U03_CROP_LOCATION_FAILED:'+str(response.get('error')))
            if op==CROP[-1]:self.selection=for_root(self.session)
            self._bind(self.session/'data_board')
            return response['result']['facts']
        if op not in (*T03,*T04):return super()._facts(op,response,code,path)
        if code!=0 or response['status']!='OK' or response['error'] is not None or response['result']['facts']['passed'] is not True:raise ValueError('U03_NATIVE_GATE_FAILED:'+str(response.get('error')))
        self._bind(self.session/('u02_t03' if op in T03 else 'u03_t04'))
        return response['result']['facts']

    def _audit(self,args,caller):
        self._valid_args(args,audit=True)
        folder=self.session/'audits'/uuid.uuid4().hex;folder.mkdir();fresh(folder/'request.json',dict(arguments=args,caller=caller))
        try:
            check(self.session);self._prior_integrity();p=self.pending
            if not p or args['attempt_id']!=p['attempt_id']:raise ValueError('U03_PENDING_AUDIT_REQUIRED')
            a=args['audit']
            if set(a)!={'verdict','response_sha256','observed','note'} or a['verdict']!='PASS' or a['response_sha256']!=p['result']['raw_response_sha256'] or a['observed']!=p['result']['facts'] or type(a['note'])is not str or not 1<=len(a['note'])<=300:raise ValueError('U03_AUDIT_MISMATCH')
            op=p['operation'];self.responses[op]=p['response'];self.accepted.append(op);self.position+=1;self.pending=None
            decision=dict(status='PASS_SLICE_OBSERVATION_AUDIT',accepted_operation=op,next_operation=self.operations[self.position]if self.position<len(self.operations)else None,authority='Technical audit only; owner PENDING_USER',native=self.identity,route_id=self.route_id)
            fresh(folder/'decision.json',decision)
            for file in folder.iterdir():self.audit_hashes[str(file)]=digest(file.read_bytes())
            if (op==ROI[-1] and self.crop is None) or op==CROP[-1]:
                selected_host=self._t01_host()
                self.cap=selected_host.prepare(self.session);self.store=ArtifactStore(Path(self.cap['store_path']))
                text=self.store.get(self.cap['english_ref'],kind='english-spec')
                self.negative=self.store.put('english-spec',text.replace(b'hard gap 0.020 mm',b'hard gap 0.001 mm'))
            elif op=='t01_compile':self.cap=self._t01_host().register(self.session,p['path']/'abi/stdout.json')
            elif op=='t01_plan':self.cap=self._t01_host().grant(self.session,p['path']/'abi/stdout.json')
            elif op==CHECK:
                checkpoint(self.session,'T01_CHECKPOINT.json',through(self.session,CHECK),[self.session/n for n in ('RECEIPT.json','board_inputs.json','data_board/verified.json','data_board/scope.json','U03_START.json')]+self._selection_files())
            elif op==T03[-1]:
                extras=[q for q in(self.session/'u02_t03').rglob('*') if q.is_file()]+[self.session/n for n in ('RECEIPT.json','T01_CHECKPOINT.json','U03_START.json')]
                checkpoint(self.session,'U03_T03_CHECKPOINT.json',through(self.session,T03[-1]),extras+self._selection_files())
                self.bound_outputs[str(self.session/'U03_T03_CHECKPOINT.json')]=digest((self.session/'U03_T03_CHECKPOINT.json').read_bytes())
            elif op==T04[-1]:
                extras=[q for d in ('u02_t03','u03_t04','u03_code_snapshot') for q in(self.session/d).rglob('*') if q.is_file()]+[self.session/n for n in ('RECEIPT.json','T01_CHECKPOINT.json','U03_T03_CHECKPOINT.json','U03_START.json')]
                proof=checkpoint(self.session,'U03_CHECKPOINT.json',through(self.session,T04[-1]),extras+self._selection_files())
                self._set_host(dict(schema='pcb-u03-data-host/1',output=str(self.session/'data_output'),**proof),'u03_data_host.json')
            elif op==FILES[-1]:
                extras=[q for d in ('data_output','u02_t03','u03_t04','u03_code_snapshot') for q in(self.session/d).rglob('*') if q.is_file()]+[self.session/n for n in ('RECEIPT.json','data_board/verified.json','T01_CHECKPOINT.json','U03_CHECKPOINT.json','U03_START.json','board_intake.json')]
                proof=checkpoint(self.session,'U03_EXPORT_CHECKPOINT.json',self.operations,extras+self._selection_files())
                fresh(self.session/'U03_RECEIPT.json',dict(status='PASS_FRESH_U03_EXPORT',selection=self.selection,operations=self.operations,t03_disposition='NO_CHANGE_REQUIRED',rendering='NOT_REQUESTED',owner='PENDING_USER',independent='NOT_RUN: CHANNEL_UNAVAILABLE',electrical_manufacturing='NOT_ESTABLISHED',**proof))
            return decision
        except Exception as error:
            self.halted=True
            fresh(folder/('handoff_failure.json'if(folder/'decision.json').exists()else'decision.json'),dict(status='FAIL',error=str(error)))
            raise

    def _t01_host(self):
        # A verified image remains a T04/view scope. Canonical T01 always uses
        # the same complete-source host, English and implementation.
        return host

    def _selection_files(self):
        return [self.session/n for n in ('U03_SELECTION.json','U03_CROP_INPUT.json','data_board/crop_location.json','data_board/crop_location_hypotheses.json','data_board/crop_verified.json','data_board/crop_landmark_witness.json','data_board/crop_mask.npy')] if self.selection is not None else []


class MachineRoute(U03Route):
    def _audit(self,args,caller):
        from tools.u03_machine_audit import evaluate
        from src.pcb_data_abi.machine_audit import proof_note,MODE
        try:
            if not self.pending or args['attempt_id']!=self.pending['attempt_id']:raise ValueError('U03_MACHINE_PENDING_REQUIRED')
            path=self.session/'audits'/f'machine-{self.position+1:03d}'/'proof.json';blob=path.read_bytes()
            if read(path)!=evaluate(self.session,args['attempt_id']) or read(path)['status']!='PASS' or args['audit']['note']!=proof_note(digest(blob)):raise ValueError('U03_MACHINE_PROOF_INVALID')
            self.audit_hashes[str(path)]=digest(blob)
            return dict(super()._audit(args,caller),audit_mode=MODE,human_or_agent_observation='NOT_RUN')
        except Exception:self.halted=True;raise
