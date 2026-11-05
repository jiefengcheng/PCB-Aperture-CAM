"""Explicit bounded C03 family on the unchanged U04 gate sequence."""
from pathlib import Path
from src.c03_input_family import selected, specification
from src.c03_round_adapter import NativeRoundAdapter, STRATEGY
from src.stage_abi.store import canonical, digest
from tools import c03_recovery_host
from tools.t01_operator_host import fresh, read
from tools.u04_board_route import U04Route, MachineRoute as U04MachineRoute
from tools.u04_board_route import initialize as initialize_u04


def initialize(session, mode='DETERMINISTIC_MACHINE_AUDIT'):
    raise ValueError('T01_C03_SUBSTITUTE_RETIRED: canonical complete-source qualification required')
    # Validate exact owner-bound inputs before any treatment job starts.
    root = Path(session)
    spec,_,sha = specification()
    marker = dict(schema='c03-input-family-selected/1',contract=spec,contract_sha256=sha)
    # Base initialization creates the native root and seals all producers.
    root = initialize_u04(root,mode=mode)
    fresh(root/'C03_INPUT_FAMILY.json',marker)
    from src.c03_baseline_custody import marker as custody_marker
    fresh(root/'C03_BASELINE_CUSTODY.json',custody_marker())
    if not selected(root):
        raise ValueError('C03_EXPLICIT_JOB_SELECTION_REQUIRED')
    return root


class C03Route(U04Route):
    OPERATION_AUTHORITY = ('Explicit owner-authorized exact C03 native round/contact family; '
        'U04 gates retained; original obligations and generic failures retained; no boundary enlargement')

    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        if not selected(self.session):
            raise ValueError('C03_EXPLICIT_JOB_SELECTION_REQUIRED')
        self.identity['board_implementation'] = NativeRoundAdapter().describe()['implementation']
        self.c03_marker = read(self.session/'C03_INPUT_FAMILY.json')
        self.c03_custody_marker = read(self.session/'C03_BASELINE_CUSTODY.json')

    def _prior_integrity(self):
        super()._prior_integrity()
        if not selected(self.session) or read(self.session/'C03_INPUT_FAMILY.json') != self.c03_marker:
            raise ValueError('C03_INPUT_FAMILY_SELECTION_CHANGED')
        if read(self.session/'C03_BASELINE_CUSTODY.json') != self.c03_custody_marker:
            raise ValueError('C03_CUSTODY_JOB_BINDING_CHANGED')

    def _request_for(self,op,rid):
        result = super()._request_for(op,rid)
        if op=='t01_plan':
            result['payload']['strategy'] = STRATEGY
        return result

    def _facts(self,op,response,code,path):
        if op!='t01_plan':
            return super()._facts(op,response,code,path)
        if code!=0 or response['status']!='OK' or response['error'] is not None:
            raise ValueError('C03_NATIVE_PLAN_FAILED')
        result=response['result'];plan=result['plan'];allocation=plan['details']['allocation']
        if (set(plan['details']['targets'])!=set(self.discovery['source_ids']) or
                plan['implementation']!=self.identity['board_implementation'] or
                plan['runtime']!=self.identity['shared_runtime'] or
                plan['strategy']!=STRATEGY or result['construction_status']!='NOT_RUN' or
                allocation['ports']['schema']!='t01-board-port-pages/1' or
                allocation['ports']['sites']!=self.discovery['unique_sites']):
            raise ValueError('C03_COMPLETE_RUNTIME_BOUND_PLAN_REQUIRED')
        return dict(targets=len(plan['details']['targets']),port_pages=allocation['ports']['pages'],
            port_geometry_zones=allocation['ports']['zones'],port_record_sites=allocation['ports']['sites'],
            original_intents=len(allocation['intent_parameters']),
            explicit_c03_round_family=True,construction_status='NOT_RUN')

    def _t01_host(self):
        return c03_recovery_host

    def _selection_files(self):
        return super()._selection_files()+[self.session/'C03_INPUT_FAMILY.json',self.session/'C03_BASELINE_CUSTODY.json']


class MachineRoute(C03Route, U04MachineRoute):
    pass
