"""Export-only route with a verified machine proof at every existing audit gate."""
from pathlib import Path
from tools.t01_board_export_route import ExportOnlyRoute,initialize as base_initialize
from tools.t01_operator_host import ROOT,read,fresh
from tools.t01_route_client import encode,decode
from src.stage_abi.store import digest
from src.pcb_data_abi.machine_audit import evaluate,proof_note,CONTRACT,MODE

PRODUCERS=['tools/t01_board_auto_route.py','tools/t01_board_auto_operator.py','tools/pcb_t01_board_run.py','tools/Run_T01_Board.command','src/pcb_data_abi/machine_audit.py','contracts/operator/t01_board_auto.json']

def initialize(session):
    root=base_initialize(session);fresh(root/'MACHINE_START.json',dict(mode=MODE,producer_files={p:digest((ROOT/p).read_bytes())for p in PRODUCERS},human_or_agent_observations='NOT_RUN',owner='PENDING_USER'));return root

class MachineRoute(ExportOnlyRoute):
    def _prior_integrity(self):
        super()._prior_integrity()
        for p,h in read(self.session/'MACHINE_START.json')['producer_files'].items():
            if digest((ROOT/p).read_bytes())!=h:raise ValueError('MACHINE_AUDITOR_PRODUCER_CHANGED:'+p)
    def _audit(self,args,caller):
        self._valid_args(args,audit=True)
        try:
            if not self.pending or args['attempt_id']!=self.pending['attempt_id']:raise ValueError('MACHINE_AUDIT_PENDING_ATTEMPT_REQUIRED')
            proof=self.session/'audits'/f'machine-{self.position+1:03d}'/'proof.json';blob=proof.read_bytes();record=decode(blob)
            if record['status']!='PASS'or record!=evaluate(self.session,args['attempt_id']):raise ValueError('MACHINE_AUDIT_PROOF_INVALID')
            if args['audit']['note']!=proof_note(digest(blob)):raise ValueError('MACHINE_AUDIT_PROOF_REFERENCE_INVALID')
            # The original checkpoint builder includes every file in audits/.
            # Subsequent native operations also verify this independent hash.
            self.audit_hashes[str(proof)]=digest(blob)
            result=super()._audit(args,caller)
            return dict(result,audit_mode=MODE,human_or_agent_observation='NOT_RUN')
        except Exception:
            self.halted=True;raise
