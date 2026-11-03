"""Deterministic evidence audits; no invented human/agent observation records."""
from pathlib import Path
from tools.pcb_u03_board_operator import U03Operator as ExportOperator,U03Client
from tools.pcb_t01_board_operator import BoardClient
from tools.pcb_c01_operator import scoped,sha,decode,encode,publish,now,replace_state
from tools.t01_route_client import verify_files
from src.pcb_data_abi.machine_audit import proof_note,MODE
from tools.u03_machine_audit import evaluate

class MachineOperator(ExportOperator):
    machine=True
    def __init__(self,binding):
        super().__init__(binding);self.client=U03Client(self.client.root/'agent_setup.json','Terminal-Automation')
    def start(self):
        if self.state_path.exists():raise ValueError('MACHINE_FRESH_JOB_REQUIRED')
        self.ui.mkdir();publish(self.ui/'binding.json',self.binding_blob);publish(self.ui/'started.json',encode(dict(at=now(),mode=MODE,human_or_agent_observations='NOT_RUN')))
        return self.offer(0)
    def summary_details(self,index,raw):
        return dict(super().summary_details(index,raw),status='MACHINE_AUDIT_REQUIRED',audit_mode=MODE,next_action='Evaluate actual retained evidence with deterministic predicates; no human observation or acceptance claimed.')
    def audit_current(self,*,advance=True):
        state=self.state()
        if state['status']!='REVIEW_REQUIRED':raise ValueError('MACHINE_PENDING_SLICE_REQUIRED')
        result=self.load_bound(state['result'],state['result_sha256']);summary=self.load_bound(state['summary'],state['summary_sha256'])
        verified=self.client.call('native_route.verify_receipt',dict(route_id=self.client.setup['route_id'],attempt_id=state['attempt']))
        if verified['receipt_sha256']!=result['receipt_sha256']or summary['facts']!=result['result']['facts']:raise ValueError('MACHINE_PENDING_EVIDENCE_CHANGED')
        verify_files(Path(result['receipt_path']),result['receipt_sha256'])
        info=self.info()
        if info['pending_audit']!=state['attempt']or info['next_operation']!=self.steps[state['index']]:raise ValueError('MACHINE_PENDING_SEQUENCE_CHANGED')
        folder=self.client.root/'audits'/f'machine-{state["index"]+1:03d}';folder.mkdir()
        proof=evaluate(self.client.root,state['attempt']);path=folder/'proof.json';publish(path,encode(proof))
        if proof['status']!='PASS':raise ValueError('MACHINE_PREDICATE_FAILED: '+str(path))
        audit=dict(result['result']['audit_required'],note=proof_note(sha(path.read_bytes())),verdict='PASS')
        accepted=self.client.invoke('native_route.audit',state['attempt'],audit)
        if accepted['status']!='PASS_SLICE_OBSERVATION_AUDIT'or accepted.get('audit_mode')!=MODE:raise ValueError('MACHINE_AUDIT_NOT_ACCEPTED')
        self.verify_observations()
        if not advance:return accepted
        if state['index']<len(self.steps)-1:return self.offer(state['index']+1)
        return self.finish()
    def verify_observations(self):
        native={}
        for path in(self.client.root/'audits').glob('*/request.json'):
            request=decode(path.read_bytes())['arguments'];decision=decode((path.parent/'decision.json').read_bytes())
            if request['attempt_id']in native or decision['status']!='PASS_SLICE_OBSERVATION_AUDIT':raise ValueError('MACHINE_NATIVE_AUDIT_SEQUENCE_CHANGED')
            native[request['attempt_id']]=(request,decision)
        proofs=sorted((self.client.root/'audits').glob('machine-*/proof.json'))
        expected=len(self.steps)if self.state()['status']=='COMPLETE'else len(native)
        if len(proofs)!=expected or len(native)!=expected or list(self.ui.glob('review-*.json')):raise ValueError('MACHINE_AUDIT_COUNT_OR_FALSE_OBSERVATION')
        for i,path in enumerate(proofs):
            proof=decode(path.read_bytes());request,decision=native[proof['attempt_id']]
            if path.parent.name!=f'machine-{i+1:03d}'or proof['operation']!=self.steps[i]or proof['mode']!=MODE or proof['status']!='PASS'or not all(c['passed']is True for c in proof['checks'])or request['audit']['note']!=proof_note(sha(path.read_bytes()))or decision['accepted_operation']!=self.steps[i]:raise ValueError('MACHINE_AUDIT_BINDING_CHANGED')
