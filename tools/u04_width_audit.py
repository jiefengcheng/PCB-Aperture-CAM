"""U04 source-role-aware width predicates, independently re-evaluated before every advancement."""
from pathlib import Path
from src.stage_abi.store import canonical,digest
from src.stage_abi.scene import validate_scene
from src.pcb_data_abi.machine_audit import evaluate as t01_evaluate,Evidence,TrackedStore,MODE
from tools.u02_machine_audit import evaluate as t03_evaluate
from tools.t01_native_route import verify_attempt
from tools.t01_operator_host import read
from src.pcb_data_abi.board_custody import FILES
from src.u04_board.custody import CONTRACT,STEPS,T03,T04,CROP,operation_steps
from src.u04_board.width import WidthGates,PROFILE
from src.u04_board.roles import qualify,require_admitted
from src.u03_board.selection import for_root
from src.t01_crop.paging import read_pages
from src.u03_board.paging import get as get_pages


def evaluate(root,attempt):
    root=Path(root);proof=_evaluate(root,attempt);selection=for_root(root)
    crop=read(root.parent/'job.json').get('crop')
    if crop is not None:
        evidence=Evidence(root);value=evidence.read(root/'U03_CROP_INPUT.json')
        evidence.eq('crop_input_bound_at_native_start',value,evidence.read(root/'U03_START.json')['crop_input'])
        evidence.eq('actual_staged_crop_bytes',digest(Path(value['path']).read_bytes()),value['sha256'])
        proof['evidence'][str(Path(value['path']))]=value['sha256']
        if selection is not None:
            value=evidence.read(root/'U03_SELECTION.json')
            evidence.eq('crop_source_binding',value['source_sha256'],evidence.read(root/'board_inputs.json')['kicad']['sha256'])
            evidence.eq('crop_image_binding',value['crop_sha256'],crop['sha256'])
            for field in ('location','verification'):
                evidence.eq('crop_'+field+'_hash',digest(Path(value[field+'_path']).read_bytes()),value[field+'_sha256'])
        proof['checks'].extend(evidence.checks);proof['evidence'].update(evidence.files)
        proof['status']='PASS' if all(p['passed'] for p in proof['checks']) else 'FAIL'
    return proof


def _evaluate(root,attempt):
    root=Path(root);folder=root/'attempts'/attempt;receipt=read(folder/'receipt.json');op=receipt['tool']
    if op not in operation_steps(root):raise ValueError('U03_MACHINE_OPERATION_UNSUPPORTED')
    if op in CROP:return crop_proof(root,attempt)
    if op not in T04 and op not in FILES:
        evaluator=t03_evaluate if op in T03 else t01_evaluate
        if for_root(root) is not None:
            if op in T03:
                from tools.u03_crop_t03_audit import evaluate as evaluator
            elif op.startswith('t01_') or op=='board_candidate_check':
                from tools.u03_crop_t01_audit import evaluate as evaluator
        proof=evaluator(root,attempt)
        proof.update(schema='pcb-u03-machine-audit/1',contract_sha256=digest(CONTRACT.read_bytes()));return proof
    verified=verify_attempt(folder);e=Evidence(root)
    receipt=e.read(folder/'receipt.json');raw=e.read(folder/'abi/stdout.json');request=e.read(folder/'abi/request.json');process=e.read(folder/'abi/completed.json');saved=e.read(folder/'result.json')
    e.eq('actual_process_exit',process['returncode'],0);e.eq('native_status',raw['status'],'OK');e.eq('native_error',raw['error'],None);e.eq('saved_error',saved['error'],None)
    e.all('response_correlation',(raw[k]==request[k] for k in ('abi_version','request_id','operation')))
    result=raw['result'];e.yes('native_facts_passed',result['facts']['passed'])
    gates=WidthGates(root);gates.store=TrackedStore(root/'runtime',e)
    e.read(root/'RECEIPT.json');e.read(root/'u02_t03/t03_verify.json');inspection=e.read(root/'u03_t04/t04_inspect.json')
    e.eq('exact_T03_predecessor',inspection['binding'],gates.binding)
    report=gates.store.get_json(inspection['report_ref'],kind='u03-admission')
    for field,kind,key,expected in [('source','u03-width-sources','source_id',report['native_rows']),
        ('path','u03-width-paths','record_id',inspection['path_records']),('group','u03-width-groups','group_id',report['groups']),
        ('relation','u03-width-relations','record_id',inspection['relation_records'])]:
        rows,index=get_pages(gates.store,inspection[field+'_pages_ref'],binding=gates.binding,kind=kind,identity=lambda r:r[key])
        e.eq('every_'+field+'_page',rows,expected)
    manifest=e.read(root/'data_board/source_manifest.json');traces=[r for r in manifest['objects'] if r['kind'] in ('segment','arc','gr_line','gr_arc')]
    e.ids('every_native_trace',[r['source_id'] for r in report['native_rows']],[r['id'] for r in traces])
    if op=='t04_inspect':
        actual=qualify(gates.raw,gates.manifest['objects'],gates.original,gates.current,selection=for_root(root))
        e.eq('fresh_source_admission',report,actual);e.eq('trace_count',result['facts']['trace_occurrences'],len(traces))
    else:
        require_admitted(report);admitted=e.read(root/'u03_t04/t04_admit.json')
        e.eq('admission_predecessor',admitted['binding'],gates.binding)
        scene=validate_scene(gates.store,admitted['imported']['scene_ref'])
        members=[s for r in scene['objects'] for s in r['metadata']['native_source_ids']]
        e.ids('complete_current_scene_partition',members,[r['id'] for r in manifest['objects']]);e.eq('unique_source_partition',len(members),len(set(members)))
        if op=='t04_admit':e.yes('exact_T03_copper',result['facts']['exact_T03_copper_preserved'])
        else:
            planned=e.read(root/'u03_t04/t04_plan.json');plan=gates.store.get_json(planned['plan_ref'],kind='plan')
            e.eq('exact_plan',plan,planned['plan']);e.eq('source_disjoint_groups',plan['details']['groups'],report['groups'])
            from src.u03_board.inspection import validate as validate_inspection
            complete=validate_inspection(gates.store,planned['inspection_ref'])
            e.ids('all_batched_ABI_inspection_records',[r['record']['source_id'] for r in complete['records']],plan['details']['targets'])
            e.eq('actual_ABI_inspection_page_count',len(complete['u03_complete_inspection_pages']),planned['facts']['inspection_pages'])
            from src.stage_abi.width import width_parameters
            policy=gates.store.get_json(plan['policy_ref'],kind='policy');e.eq('unchanged_T04_numeric_policy',policy,dict(stage='t04',parameters=width_parameters()))
            if op=='t04_plan':
                e.eq('all_admitted_targets',len(plan['details']['targets']),len(report['admitted_paths']));e.yes('all_ABI_inspection_pages',result['facts']['complete_ABI_inspection'])
            else:
                ran=e.read(root/'u03_t04/t04_run.json');candidate=gates.store.get_json(ran['result']['candidate_ref'],kind='candidate')
                e.eq('candidate_artifact',candidate,ran['result']['candidate']);e.eq('candidate_exact_plan',candidate['plan_ref'],planned['plan_ref'])
                e.yes('nominal_complete_check',candidate['nominal_check']['passed']);e.yes('envelope_complete_check',candidate['envelope_check']['passed']);e.yes('coordinatewise_proof',candidate['solution']['maximum_established'])
                factors=candidate['solution']['selected_scales'];e.ids('each_group_factor',factors,[r['group_id'] for r in report['groups']]);e.all('bounded_uniform_factors',(1<=v<=1.5 for v in factors.values()))
                e.ids('each_native_part',candidate['parts'],[s for p in report['admitted_paths'] for s in p['source_ids']])
                for sid,refs in candidate['parts'].items():
                    for ref in refs.values():gates.store.get(ref,kind='geometry')
                e.all('final_upper_proofs',(p['proved'] for p in candidate['solution']['maximum_proofs']))
                from src.u03_board.solver import validate_ledger
                e.eq('all_actual_solver_check_reports',validate_ledger(gates.store,candidate),candidate['solution']['evaluation_count'])
                if op=='t04_verify':
                    actual=qualify(gates.raw,gates.manifest['objects'],gates.original,gates.current,selection=for_root(root));e.eq('fresh_whole_source_admission',actual,report)
                    verification=gates.store.get_json(result['result']['verification_ref'],kind='verification')
                    e.eq('actual_verification',verification,result['result']['verification']);e.eq('verified_candidate',verification['candidate_ref'],ran['result']['candidate_ref']);e.eq('geometry_verdict',verification['geometric_status'],'PASS')
                    e.eq('reconstructed_native_parts',verification['check']['reconstructed_native_parts'],len(candidate['parts']))
                    e.all('fresh_final_neighbor_proofs',(p['proved'] for p in verification['check']['maximum_proofs']))
                elif op=='t04_compare':
                    rows,index=read_pages(gates.store,result['pagination_ref'],binding=gates.binding,kind='u03-width-comparison',identity=lambda r:r['source_id'])
                    e.ids('all_trace_comparisons',[r['source_id'] for r in rows],[r['id'] for r in traces]);e.all('all_source_cores_retained',(r['removed_area_mm2']<=1e-10 and r['route_change']=='NONE' for r in rows))
                elif op=='t04_review':e.eq('no_invented_reviews',result['records'],[]);e.eq('owner_pending',result['facts']['owner_status'],'PENDING_USER')
                elif op=='t04_controls':
                    e.eq('width_control_count',len(result['controls']),7);e.all('width_expected_rejections',(r['status']=='PASS_EXPECTED_REJECTION' and r['error'].startswith(r['expected']) for r in result['controls']))
                    for r in result['controls']:e.read(root/'u03_t04/controls'/r['name']/'mutation.json')
                elif op in FILES:
                    from src.u03_board.export import U03DataService
                    host=e.read(root/'u03_data_host.json');service=U03DataService(host)
                    e.eq('actual_native_export_result',result,e.read(root/'data_output'/(op+'.json')))
                    if op in ('pcb_kicad_write','pcb_kicad_verify'):
                        checked=service.native_check(service.board.read_bytes(),e.read(root/'data_output/TARGET_MAP.json'),e.read(root/'data_output/WIDTH_TARGET_MAP.json'))
                        e.yes('fresh_actual_native_reread',checked['passed']);e.eq('all_written_width_parts',checked['changed_native_trace_parts'],ran['facts']['changed_native_parts'])
                    elif op=='pcb_gerber_export':
                        e.eq('actual_export_exit',result['facts']['native_export_exit'],0);e.eq('nine_layers',result['facts']['layers'],9)
                        e.eq('eighteen_fresh_exports',len(result['output_sha256']),18)
                        for path,h in result['output_sha256'].items():e.eq('export_hash:'+path,digest(Path(path).read_bytes()),h)
                        for stem in ('kicad_version','before_export','candidate_export'):
                            p=root/'data_output'/(stem+'.command.json')
                            if p.exists():e.eq('actual_process:'+stem,e.read(p)['exit_status'],0)
                    elif op=='pcb_gerber_verify':
                        measured,geometries,parsed=service.plot_check();e.eq('fresh_actual_Gerber_measurements',measured,result['verification']);e.eq('every_width_plot_part',len(measured['width_targets']),ran['facts']['changed_native_parts'])
                    elif op=='pcb_export_controls':
                        e.eq('export_control_count',len(result['controls']),3);e.all('export_expected_rejections',(r['status']=='PASS_EXPECTED_REJECTION' and r['error'].startswith(r['expected']) for r in result['controls']))
    return dict(schema='pcb-u03-machine-audit/1',mode=MODE,operation=op,attempt_id=attempt,status='PASS' if all(q['passed'] for q in e.checks) else 'FAIL',
        contract_sha256=digest(CONTRACT.read_bytes()),native_receipt_sha256=verified['receipt_sha256'],raw_response_sha256=digest((folder/'abi/stdout.json').read_bytes()),
        checks=e.checks,evidence=e.files,owner='PENDING_USER',human_or_agent_observation='NOT_RUN',independent='NOT_RUN: CHANNEL_UNAVAILABLE',rendering='NOT_REQUESTED')


def crop_proof(root,attempt):
    from src.u03_board.crop_roi import CropLocation
    folder=root/'attempts'/attempt;verified=verify_attempt(folder);e=Evidence(root)
    receipt=e.read(folder/'receipt.json');response=e.read(folder/'abi/stdout.json');request=e.read(folder/'abi/request.json');process=e.read(folder/'abi/completed.json')
    op=receipt['tool'];e.eq('native_exit',process['returncode'],0);e.eq('native_status',response['status'],'OK');e.eq('native_error',response['error'],None)
    e.all('response_correlation',(response[k]==request[k] for k in ('abi_version','request_id','operation')))
    e.yes('native_location_facts',response['result']['facts']['passed'])
    e.eq('actual_image_and_source_measurements',CropLocation(root).audit(op),dict(passed=True,source_sha256=read(root/'data_board/source_manifest.json')['source_sha256'],crop_sha256=read(root/'U03_CROP_INPUT.json')['sha256'],metrics_recomputed=True,mask_reconstructed_from_actual_input=True))
    for name in ('inputs.json','source_manifest.json','crop_location.json','crop_location_hypotheses.json'):
        e.read(root/'data_board'/name)
    e.files['data_board/crop_mask.npy']=digest((root/'data_board/crop_mask.npy').read_bytes())
    if op==CROP[-1]:e.read(root/'data_board/crop_verified.json');e.read(root/'data_board/crop_landmark_witness.json');e.read(root/'U03_SELECTION.json')
    return dict(schema='pcb-u03-machine-audit/1',mode=MODE,operation=op,attempt_id=attempt,status='PASS' if all(r['passed'] for r in e.checks) else 'FAIL',contract_sha256=digest(CONTRACT.read_bytes()),native_receipt_sha256=verified['receipt_sha256'],raw_response_sha256=digest((folder/'abi/stdout.json').read_bytes()),checks=e.checks,evidence=e.files,owner='PENDING_USER',human_or_agent_observation='NOT_RUN',independent='NOT_RUN: CHANNEL_UNAVAILABLE',rendering='NOT_REQUESTED')
