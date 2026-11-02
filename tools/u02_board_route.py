"""U02: fresh T01 prefix, seven T03 gates and five audited native export gates."""
import sys,uuid,subprocess
from pathlib import Path
from src.stage_abi.store import ArtifactStore,digest
from src.pcb_data_abi.board_custody import ROI,T01,CHECK,FILES,checkpoint
from src.u02_board.custody import CONTRACT,STEPS,T03,PREFIX,THROUGH_T03
from tools.t01_board_export_route import ExportOnlyRoute,initialize as base_initialize
from tools.t01_operator_host import ROOT,read,fresh,check
from tools import t01_board_host as host

PRODUCERS=[*['src/u02_board/'+p.name for p in sorted((ROOT/'src/u02_board').glob('*.py'))],
    *['tools/'+n for n in ('u02_board_route.py','u02_board_jobs.py','u02_machine_audit.py','u02_board_auto_operator.py','pcb_u02_board_abi.py','pcb_u02_board_operator.py','pcb_u02_board_run.py','start_u02_board_operator.py','Run_U02_Board.command')], 'contracts/operator/u02_board.json']


def initialize(session,mode='AGENT_REVIEWS_EACH_SLICE'):
    from tools.pcb_workspace import configure
    work=configure()
    if not Path(session).absolute().is_relative_to(work):raise ValueError('U02_LACIE_SESSION_REQUIRED')
    root=base_initialize(session,storage_root=work)
    fresh(root/'U02_START.json',dict(schema='pcb-u02-start/1',mode=mode,operations=list(STEPS),producer_files={p:digest((ROOT/p).read_bytes()) for p in PRODUCERS},owner='PENDING_USER',rendering='NOT_REQUESTED'))
    return root


class U02Route(ExportOnlyRoute):
    CONTRACT=CONTRACT
    STEPS=STEPS
    TASK_SCOPE='u02-board'
    OPERATION_AUTHORITY='Explicit raw directory → fresh T01 → source-bound T03 retain-valid-paths → audited native exports; no rendering or later U stages'

    def info(self):
        result=super().info()
        if self.position==len(self.operations):result['status']='COMPLETE_AUDITED_U02_SEQUENCE'
        return result

    def _prior_integrity(self):
        super()._prior_integrity()
        for p,h in read(self.session/'U02_START.json')['producer_files'].items():
            if digest((ROOT/p).read_bytes())!=h:raise ValueError('U02_PRODUCER_CHANGED:'+p)

    def _request_for(self,op,rid):
        if op in T03 or op in FILES:return dict(abi_version='pcb-u02-board/1',request_id=rid,operation=op)
        return super()._request_for(op,rid)

    def _argv(self,path):
        op=self.operations[self.position]
        if op in T03 or op in FILES:
            argv=[sys.executable,'-B',str(ROOT/'tools/pcb_u02_board_abi.py'),'--session',str(self.session),'--input',str(path)]
            if op in FILES:argv+=['--registry',self.cap['registry_path'],'--registry-sha256',self.cap['registry_sha256']]
            return argv
        return super()._argv(path)

    def _facts(self,op,response,code,path):
        if op not in T03:return super()._facts(op,response,code,path)
        if code!=0 or response['status']!='OK' or response['error'] is not None or response['result']['facts']['passed'] is not True:raise ValueError('U02_T03_NATIVE_GATE_FAILED:'+str(response.get('error')))
        self._bind(self.session/'u02_t03')
        return response['result']['facts']

    def _audit(self,args,caller):
        self._valid_args(args,audit=True)
        folder=self.session/'audits'/uuid.uuid4().hex;folder.mkdir();fresh(folder/'request.json',dict(arguments=args,caller=caller))
        try:
            check(self.session);self._prior_integrity();p=self.pending
            if not p or args['attempt_id']!=p['attempt_id']:raise ValueError('U02_PENDING_AUDIT_REQUIRED')
            a=args['audit']
            if set(a)!={'verdict','response_sha256','observed','note'} or a['verdict']!='PASS' or a['response_sha256']!=p['result']['raw_response_sha256'] or a['observed']!=p['result']['facts'] or type(a['note'])is not str or not 1<=len(a['note'])<=300:raise ValueError('U02_AUDIT_MISMATCH')
            op=p['operation'];self.responses[op]=p['response'];self.accepted.append(op);self.position+=1;self.pending=None
            decision=dict(status='PASS_SLICE_OBSERVATION_AUDIT',accepted_operation=op,next_operation=self.operations[self.position]if self.position<len(self.operations)else None,authority='Technical audit only; owner PENDING_USER',native=self.identity,route_id=self.route_id)
            fresh(folder/'decision.json',decision)
            for file in folder.iterdir():self.audit_hashes[str(file)]=digest(file.read_bytes())
            if op==ROI[-1]:
                self.cap=host.prepare(self.session);self.store=ArtifactStore(Path(self.cap['store_path']));self.negative=self.store.put('english-spec',(ROOT/'contracts/t01_board/english.txt').read_bytes().replace(b'hard gap 0.020 mm',b'hard gap 0.001 mm'))
            elif op=='t01_compile':self.cap=host.register(self.session,p['path']/'abi/stdout.json')
            elif op=='t01_plan':self.cap=host.grant(self.session,p['path']/'abi/stdout.json')
            elif op==CHECK:
                checkpoint(self.session,'T01_CHECKPOINT.json',PREFIX,[self.session/n for n in ('RECEIPT.json','board_inputs.json','data_board/verified.json','data_board/scope.json','U02_START.json')])
            elif op==T03[-1]:
                extras=[q for q in(self.session/'u02_t03').rglob('*') if q.is_file()]+[self.session/n for n in ('RECEIPT.json','T01_CHECKPOINT.json','U02_START.json')]
                proof=checkpoint(self.session,'U02_CHECKPOINT.json',THROUGH_T03,extras)
                self._set_host(dict(schema='pcb-u02-data-host/1',output=str(self.session/'data_output'),**proof),'u02_data_host.json')
            elif op==FILES[-1]:
                extras=[q for d in ('data_output','u02_t03') for q in(self.session/d).rglob('*') if q.is_file()]+[self.session/n for n in ('RECEIPT.json','data_board/verified.json','T01_CHECKPOINT.json','U02_CHECKPOINT.json','U02_START.json','board_intake.json')]
                proof=checkpoint(self.session,'U02_EXPORT_CHECKPOINT.json',STEPS,extras)
                fresh(self.session/'U02_RECEIPT.json',dict(status='PASS_FRESH_U02_EXPORT',operations=list(STEPS),disposition='NO_CHANGE_REQUIRED',changed_trace_count=0,rendering='NOT_REQUESTED',owner='PENDING_USER',independent='NOT_RUN: CHANNEL_UNAVAILABLE',electrical_manufacturing='NOT_ESTABLISHED',**proof))
            return decision
        except Exception as error:
            self.halted=True
            fresh(folder/('handoff_failure.json'if(folder/'decision.json').exists()else'decision.json'),dict(status='FAIL',error=str(error)))
            raise


class MachineRoute(U02Route):
    def _audit(self,args,caller):
        from tools.u02_machine_audit import evaluate
        from src.pcb_data_abi.machine_audit import proof_note,MODE
        try:
            if not self.pending or args['attempt_id']!=self.pending['attempt_id']:raise ValueError('U02_MACHINE_PENDING_REQUIRED')
            path=self.session/'audits'/f'machine-{self.position+1:03d}'/'proof.json';blob=path.read_bytes()
            if read(path)!=evaluate(self.session,args['attempt_id']) or read(path)['status']!='PASS' or args['audit']['note']!=proof_note(digest(blob)):raise ValueError('U02_MACHINE_PROOF_INVALID')
            self.audit_hashes[str(path)]=digest(blob)
            return dict(super()._audit(args,caller),audit_mode=MODE,human_or_agent_observation='NOT_RUN')
        except Exception:self.halted=True;raise
