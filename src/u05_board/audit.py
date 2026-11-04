"""Separate deterministic predicates over actual U05 native evidence."""
from pathlib import Path
from src.stage_abi.store import digest
from tools.t01_operator_host import read
from tools.t01_native_route import verify_attempt
from .custody import T05,FILES,STEPS,verify_u04,session,CONTRACT
from .junctions import make_gates,parameters

def evaluate(root,attempt):
    root=Path(root);folder=root/'attempts'/attempt;receipt=read(folder/'receipt.json');verify_attempt(folder);op=receipt['tool'];start=session(root);response=read(folder/'abi/stdout.json');evidence={};checks=[]
    def eq(name,a,b):
        from src.stage_abi.store import canonical
        def compact(x):return dict(sha256=digest(canonical(x)),records=len(x)) if isinstance(x,(dict,list)) else x
        checks.append(dict(predicate=name,passed=type(a) is type(b) and a==b,observed=compact(a),expected=compact(b)))
    request=read(folder/'abi/request.json');eq('response_correlation',[response.get(k) for k in ('abi_version','request_id','operation')],[request[k] for k in ('abi_version','request_id','operation')]);eq('permitted_operation',op in STEPS,True)
    eq('native_exit',read(folder/'abi/completed.json')['returncode'],0);eq('native_status',response['status'],'OK');eq('native_error',response['error'],None);result=response['result'];eq('native_facts_passed',result['facts']['passed'],True)
    if op=='u04_predecessor_verify':eq('retained_complete_U04_receipts_and_artifacts',result['facts'],verify_u04(start['predecessor']))
    else:
        g=make_gates(root,evidence);scene,report=g.inspection();eq('complete_native_source_partition',report['native_source_ids'],g.native_ids)
        eq('actual_native_gate_result',result,read((g.out if op in T05 else root/'data_output')/(op+'.json')))
        if op!='t05_inspect':eq('exact_native_U04_admission',g.store.get_json(read(g.out/'t05_admit.json')['scene_ref'],kind='scene'),scene)
        if op not in ('t05_inspect','t05_admit'):
            scene,policy,plan,_=g.context();eq('fixed_spindle_policy',policy,dict(stage='t05',parameters=parameters()));eq('all_qualified_route_targets',[r['source_id'] for r in plan['details']['routes']],report['target_ids'])
        if op not in ('t05_inspect','t05_admit','t05_plan'):
            saved=read(g.out/'t05_run.json');c=g.store.get_json(saved['candidate_ref'],kind='candidate');eq('native_candidate_artifact',c,saved['candidate']);eq('fresh_full_attempt_reconstruction_including_KEEP',c,g.reconstruct());q=g.check_candidate(c);eq('all_final_spindles_checked',q['passed'],True);eq('no_predecessor_removal',q['removed_area_mm2']<=1e-12,True)
            if hasattr(g,'reference'):
                required=[a for d in c['decisions'] for a in d['attachment_outcomes'] if a['required_reference']]
                eq('frozen_required_attachment_inventory',len(required),162);eq('required_attachment_identities_unique',len({a['id'] for a in required}),162);eq('reference_positive_clusters',sum(d['reference_status']=='GROWN' for d in c['decisions']),85);eq('every_required_attachment_fulfilled',all(a['status'] in ('TREATED_VERIFIED','ALREADY_SATISFIED_VERIFIED') for a in required),True)
            if op=='t05_verify':eq('actual_direct_patch_verification',q,result['check'])
            elif op=='t05_compare':
                from src.u03_board.paging import get
                rows,_=get(g.store,result['pagination_ref'],binding=g.binding,kind='u05-junction-comparison',identity=lambda r:r['source_id']);eq('all_route_comparisons',[r['source_id'] for r in rows],[d['source_id'] for d in c['decisions']]);eq('protected_sources',c['protected_source_refs'],{r['source_id']:r['geometry_ref'] for r in scene['objects']})
            elif op=='t05_review':eq('no_invented_owner_review',result['records'],[]);eq('owner_pending',result['facts']['owner_status'],'PENDING_USER')
            elif op=='t05_controls':
                eq('all_required_controls',sorted(r['name'] for r in result['controls']),sorted(['wrong_predecessor','missing_route','changed_policy','changed_patch','changed_protected_source']+[name for name,_ in getattr(g,'extra_controls',lambda:[])()]))
                for control in result['controls']:
                    path=Path(control['mutation']);evidence[str(path)]=digest(path.read_bytes())
                    try:g.check_candidate(read(path))
                    except ValueError as error:eq('actual_rejection:'+control['name'],str(error),control['error'])
                    else:eq('control_rejected:'+control['name'],False,True)
            elif op in FILES:
                from .export import U05DataService
                service=U05DataService(root,gates=g)
                for native_path in (service.board,service.before):
                    if native_path.exists():evidence[str(native_path)]=digest(native_path.read_bytes())
                exported=root/'data_output/pcb_gerber_export.json'
                if exported.exists():
                    for path,h in read(exported)['output_sha256'].items():evidence[path]=digest(Path(path).read_bytes());eq('sealed_export:'+path,evidence[path],h)
                if op in ('pcb_kicad_write','pcb_kicad_verify'):
                    check=service.native_check(service.board.read_bytes());eq('actual_native_saved_file',check['passed'],True);eq('all_U04_nodes_unchanged',check['all_U04_nodes_equal'],True);eq('every_native_patch',check['junction_parts'],len(service.targets))
                elif op=='pcb_gerber_export':
                    eq('nine_layers',result['facts']['layers'],9);eq('eighteen_actual_plot_files',len(result['output_sha256']),18)
                    for path,h in result['output_sha256'].items():eq('actual_export_hash:'+path,digest(Path(path).read_bytes()),h);evidence[path]=h
                    for stem in ('before_export','candidate_export'):eq('actual_native_export_exit:'+stem,read(root/'data_output'/(stem+'.command.json'))['exit_status'],0)
                    if hasattr(g,'reference'):
                        from .owner_plot import binding
                        owner=binding(service);eq('fresh_native_owner_source_occurrences',owner['source_nodes'],len(owner['bindings']));eq('fresh_native_owner_source_coverage',owner['all_source_occurrences_bound'],True)
                        for name,h in owner['files'].items():evidence[str(service.out/name)]=digest((service.out/name).read_bytes());eq('owner_source_plot_file:'+name,evidence[str(service.out/name)],h)
                elif op=='pcb_gerber_verify':
                    measured,_,_=service.plot_check();eq('actual_Gerber_reparse_and_hard_gap',measured,result['verification']);eq('all_U04_layers_preserved',len(measured['protected_layers_equal']),8)
                    eq('all_actual_FCu_primitives_positive',measured['all_fcu_primitives_positive'],True)
                    if hasattr(g,'reference'):
                        coverage=measured['attachment_coverage'];eq('actual_export_required_attachment_denominator',coverage['required_reference_attachments'],162);eq('actual_export_every_required_attachment_verified',coverage['verified_required_attachments'],162);eq('actual_export_complete_attachment_ledger',len(coverage['records']),180);eq('actual_export_reference_comparisons',len(coverage['reference_witnesses']),85)
                else:
                    names=['units','role','protected_U04']+(['missing_spindle'] if service.targets else [])+(['clear_polarity'] if service.targets and hasattr(g,'reference') else []);eq('all_required_export_faults',sorted(r['name'] for r in result['controls']),sorted(names))
                    for control in result['controls']:
                        path=Path(control['path']);eq('fault_file_hash:'+control['name'],digest(path.read_bytes()),control['sha256']);evidence[str(path)]=control['sha256']
                        try:
                            if control['name']=='units':__import__('src.pcb_data_abi.gerber',fromlist=['parse']).parse(path)
                            elif control['name']=='protected_U04':service.native_check(path.read_bytes())
                            else:service.plot_check(path)
                        except ValueError as error:eq('actual_export_fault:'+control['name'],str(error),control['error'])
                        else:eq('export_fault_rejected:'+control['name'],False,True)
    for path in folder.rglob('*'):
        if path.is_file():evidence[str(path)]=digest(path.read_bytes())
    return dict(schema='pcb-u05-machine-audit/1',mode='DETERMINISTIC_MACHINE_AUDIT',operation=op,attempt_id=attempt,contract_sha256=digest(CONTRACT.read_bytes()),status='PASS' if all(c['passed'] for c in checks) else 'FAIL',checks=checks,evidence=evidence,retained_U04_receipt_sha256=start['predecessor']['receipt_sha256'],human_or_agent_observations='NOT_RUN',owner='PENDING_USER',independent='NOT_RUN: CHANNEL_UNAVAILABLE',electrical_manufacturing='NOT_ESTABLISHED',rendering='NOT_REQUESTED')
