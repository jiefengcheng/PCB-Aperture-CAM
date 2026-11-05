"""Separate, hash-bound U04 predicates, re-evaluated by the native route."""
from pathlib import Path
from src.stage_abi.store import digest
from src.pcb_data_abi.machine_audit import Evidence, TrackedStore, MODE
from tools.t01_native_route import verify_attempt
from tools.t01_operator_host import read
from tools.u03_machine_audit import evaluate as inherited_evaluate
from src.u04_board.custody import CONTRACT, T02, T04, operation_steps
from src.pcb_data_abi.board_custody import FILES

from src.stage_abi.preparation import native_operation


@native_operation
def evaluate(root,attempt):
    proof=_evaluate(root,attempt)
    marker=Path(root)/'C03_BASELINE_CUSTODY.json'
    if marker.exists() or marker.is_symlink():
        from tools.c03_custody_audit import augment
        proof=augment(root,proof)
    return proof


def _evaluate(root,attempt):
    root=Path(root);folder=root/'attempts'/attempt;op=read(folder/'receipt.json')['tool']
    if op not in operation_steps(root):raise ValueError('U04_MACHINE_OPERATION_UNSUPPORTED')
    if op not in (*T02,*FILES):
        if op in T04:
            from tools.u04_width_audit import evaluate as width_evaluate
            proof=width_evaluate(root,attempt)
            from src.u04_board.roles import CONTRACT as ROLE_CONTRACT
            proof['evidence'][str(ROLE_CONTRACT)]=digest(ROLE_CONTRACT.read_bytes())
            for profile in read(ROLE_CONTRACT)['profiles']:
                from tools.t01_operator_host import ROOT
                authority=ROOT/profile['review_receipt']
                proof['evidence'][str(authority)]=digest(authority.read_bytes())
        else:proof=inherited_evaluate(root,attempt)
        proof.update(schema='pcb-u04-machine-audit/1',contract_sha256=digest(CONTRACT.read_bytes()))
        proof['evidence'][str(CONTRACT)]=digest(CONTRACT.read_bytes())
        return proof
    verified=verify_attempt(folder);e=Evidence(root)
    response=e.read(folder/'abi/stdout.json');request=e.read(folder/'abi/request.json');process=e.read(folder/'abi/completed.json')
    e.eq('actual_process_exit',process['returncode'],0);e.eq('native_status',response['status'],'OK');e.eq('native_error',response['error'],None)
    e.all('response_correlation',(response[k]==request[k] for k in ('abi_version','request_id','operation')))
    result=response['result'];e.yes('native_facts',result['facts']['passed'])
    from src.u04_board.rectangles import RectangleGates
    gates=RectangleGates(root);gates.store=TrackedStore(root/'runtime',e)
    e.read(root/'U04_START.json');e.read(root/'U04_T04_CHECKPOINT.json')
    e.eq('exact_native_gate_result',result,e.read(root/('u04_t02' if op in T02 else 'data_output')/(op+'.json')))
    report=gates.inspection();scene=gates.scene;e.yes('full_source_partition',len(report['native_source_ids'])>0)
    e.read(root/'u04_t02/t02_inspect.json')
    if op!='t02_inspect':
        admitted=e.read(root/'u04_t02/t02_admit.json')
        e.eq('exact_T04_predecessor_scene',gates.store.get_json(admitted['scene_ref'],kind='scene'),scene)
    if op not in ('t02_inspect','t02_admit'):
        scene,policy,plan,ref=gates.context();e.eq('fixed_rectangle-inclusive_family',policy,dict(stage='t02',parameters=read(CONTRACT)['land_policy']))
        e.ids('all_source_qualified_rectangles',plan['details']['targets'],report['target_ids'])
    if op not in ('t02_inspect','t02_admit','t02_plan'):
        ran=e.read(root/'u04_t02/t02_run.json');candidate=gates.store.get_json(ran['candidate_ref'],kind='candidate')
        e.eq('exact_candidate',candidate,ran['candidate'])
        e.eq('fresh_full_construction_including_KEEP',candidate,gates.reconstruct())
        check=gates.check_candidate(candidate);e.yes('all_simultaneous_rectangle_checks',check['passed']);e.yes('predecessor_preserved_with_fixed_area_bound',check['removed_area_mm2']<=1e-12)
        if op=='t02_verify':e.eq('actual_source_replay_check',check,result['check'])
        elif op=='t02_compare':
            from src.u03_board.paging import get
            rows,index=get(gates.store,result['pagination_ref'],binding=gates.binding,kind='u04-rectangle-comparison',identity=lambda r:r['source_id'])
            e.ids('every_route_comparison',[r['source_id'] for r in rows],[r['source_id'] for r in candidate['decisions']])
            e.yes('all_rectangle_cores_preserved',all(r['removed_area_mm2']<=1e-12 for r in rows));e.eq('inclusive_comparison_ledger',result['inclusive_candidates'],candidate['inclusive_candidates'])
        elif op=='t02_review':e.eq('no_invented_reviews',result['records'],[]);e.eq('owner_pending',result['facts']['owner_status'],'PENDING_USER')
        elif op=='t02_controls':
            e.eq('required_rectangle_controls',len(result['controls']),6)
            for control in result['controls']:
                mutation=e.read(Path(control['mutation']))
                try:gates.check_candidate(mutation)
                except ValueError as error:e.eq('actual_control:'+control['name'],str(error),control['error'])
                else:e.yes('control_must_reject:'+control['name'],False)
        elif op in FILES:
            from src.c03_native_export import data_service
            service=data_service(root,e.read(root/'u04_data_host.json'))
            if op in ('pcb_kicad_write','pcb_kicad_verify'):
                checked=service.native_check(service.board.read_bytes(),e.read(root/'data_output/TARGET_MAP.json'),e.read(root/'data_output/WIDTH_TARGET_MAP.json'))
                e.yes('fresh_native_reread',checked['passed']);e.eq('every_native_rectangle_part',checked['rectangle_parts'],len(service.rectangle_targets));e.eq('every_native_inclusive_part',checked['inclusive_parts'],len(service.inclusive_targets))
            elif op=='pcb_gerber_export':
                e.eq('actual_native_exit',result['facts']['native_export_exit'],0);e.eq('all_nine_layers',result['facts']['layers'],9)
                e.eq('eighteen_fresh_export_files',len(result['output_sha256']),18)
                for path,h in result['output_sha256'].items():e.eq('actual_export:'+path,digest(Path(path).read_bytes()),h)
                for stem in ('before_export','candidate_export'):e.eq('actual_export_process:'+stem,e.read(root/'data_output'/(stem+'.command.json'))['exit_status'],0)
            elif op=='pcb_gerber_verify':
                measured,_,_=service.plot_check();e.eq('actual_Gerber_reparse',measured,result['verification']);e.eq('every_Gerber_rectangle_part',measured['rectangle_parts'],len(service.rectangle_targets));e.eq('every_Gerber_inclusive_part',measured['inclusive_parts'],len(service.inclusive_targets))
            elif op=='pcb_export_controls':
                from src.u04_board.export import required_export_controls,validate_export_controls
                measured,_,_=service.plot_check()
                validate_export_controls(result,measured)
                expected=required_export_controls(measured)
                e.eq('all_required_export_faults',{r['name']:r['expected'] for r in result['controls']},expected)
                e.eq('export_control_count',len(result['controls']),3+bool(service.rectangle_targets)+bool(service.inclusive_targets)+bool(measured.get('c03_positive_copper_required')))
                from src.pcb_data_abi import gerber
                paths=root/'data_output/controls'
                for control in result['controls']:
                    name=control['name']
                    try:
                        if name=='clear_polarity':service.plot_check(paths/'clear_polarity.gbr')
                        elif name=='gerber_units':gerber.parse(paths/'wrong_units.gbr')
                        elif name=='native_protected_object':service.native_check((paths/'protected_changed.kicad_pcb').read_bytes(),read(root/'data_output/TARGET_MAP.json'),read(root/'data_output/WIDTH_TARGET_MAP.json'))
                        else:service.plot_check(paths/('missing_rectangle.gbr' if name=='missing_rectangle_copper' else 'missing_inclusive.gbr' if name=='missing_inclusive_copper' else 'wrong_role.gbr' if name=='wrong_layer_role' else 'missing_width.gbr'))
                    except ValueError as error:e.yes('actual_export_control:'+name,str(error).startswith(control['expected']))
                    else:e.yes('actual_export_control:'+name,False)
    return dict(schema='pcb-u04-machine-audit/1',mode=MODE,operation=op,attempt_id=attempt,status='PASS' if all(q['passed'] for q in e.checks) else 'FAIL',
                contract_sha256=digest(CONTRACT.read_bytes()),native_receipt_sha256=verified['receipt_sha256'],raw_response_sha256=digest((folder/'abi/stdout.json').read_bytes()),
                checks=e.checks,evidence=e.files,owner='PENDING_USER',human_or_agent_observation='NOT_RUN',independent='NOT_RUN: CHANNEL_UNAVAILABLE',rendering='NOT_REQUESTED')
