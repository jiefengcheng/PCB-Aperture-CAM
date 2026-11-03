"""U03 crop T03 proofs; unchanged retained-path predicates and full trace coverage."""
from pathlib import Path
from src.stage_abi.store import canonical,digest
from src.pcb_data_abi.machine_audit import evaluate as t01_evaluate,Evidence,TrackedStore,MODE
from tools.t01_native_route import verify_attempt
from tools.t01_operator_host import read,state
from src.u02_board.adapter import verify_candidate,require_supported
from src.u03_board.selection import retain_paths as RetainPathsAdapter
from src.u02_board.custody import CONTRACT,STEPS,T03
from src.t01_crop.paging import read_pages


def evaluate(root,attempt):
    root=Path(root);folder=root/'attempts'/attempt;receipt=read(folder/'receipt.json');op=receipt['tool']
    if op not in STEPS:raise ValueError('U02_MACHINE_OPERATION_UNSUPPORTED')
    if op not in T03:
        proof=t01_evaluate(root,attempt)
        proof.update(schema='pcb-u02-machine-audit/1',contract_sha256=digest(CONTRACT.read_bytes()))
        return proof
    verified=verify_attempt(folder);e=Evidence(root)
    receipt=e.read(folder/'receipt.json');raw=e.read(folder/'abi/stdout.json');req=e.read(folder/'abi/request.json');process=e.read(folder/'abi/completed.json');saved=e.read(folder/'result.json')
    e.eq('actual_process_exit',process['returncode'],0);e.eq('response_status',raw['status'],'OK');e.eq('native_error',raw['error'],None);e.eq('saved_error',saved['error'],None)
    e.all('response_correlation',(raw[k]==req[k] for k in ('abi_version','request_id','operation')))
    result=raw['result'];e.yes('native_check_passed',result['facts']['passed']);e.eq('actual_saved_result',result,e.read(root/'u02_t03'/(op+'.json')))
    adapter=RetainPathsAdapter(root);adapter.store=TrackedStore(root/'runtime',e)
    e.read(root/'RECEIPT.json');e.read(Path(state(root)['registry_path']))
    inspection=e.read(root/'u02_t03/t03_inspect.json');e.eq('exact_predecessor_binding',inspection['binding'],adapter.binding)
    rows,index=read_pages(adapter.store,inspection['trace_inventory_ref'],binding=adapter.binding,kind='u02-traces',identity=lambda r:r['source_id'])
    source=e.read(root/'data_board/source_manifest.json');traces=[r for r in source['objects'] if r['kind'] in ('segment','arc','gr_line','gr_arc')]
    e.ids('every_native_trace',[r['source_id'] for r in rows],[r['id'] for r in traces]);e.eq('trace_page_count',len(index['pages']),inspection['facts']['trace_pages'])
    original={r['id']:r for r in traces}
    e.all('every_trace_geometry_and_width',(r['geometry_sha256']==original[r['source_id']]['geometry_sha256'] and r['original_width_mm']==original[r['source_id']]['trace_width_mm'] for r in rows))
    if op=='t03_inspect':
        e.eq('trace_count',result['facts']['trace_occurrences'],len(traces));e.eq('source_count',result['coverage']['source_objects'],len(source['objects']));e.yes('full_source_coverage',result['facts']['complete_source_coverage'])
    else:
        require_supported(rows);plan=e.read(root/'u02_t03/t03_plan.json')['plan']
        e.eq('plan_predecessor',plan['binding'],adapter.binding);e.eq('plan_trace_inventory',plan['trace_inventory_ref'],inspection['trace_inventory_ref']);e.eq('unchanged_policy',plan['policy'],read(CONTRACT)['policy'])
        if op=='t03_plan':e.eq('no_movement_objectives',plan['movement_objectives'],0);e.eq('all_planned_traces',plan['source_count'],len(rows))
        else:
            candidate=e.read(root/'u02_t03/t03_search.json')['candidate'];verify_candidate(candidate,plan,adapter.scene_ref)
            e.eq('no_trace_changes',candidate['changed_trace_count'],0);e.eq('exact_output_predecessor',candidate['output_scene_ref'],adapter.scene_ref)
            if op=='t03_verify':
                actual,coverage=adapter.assess();e.eq('fresh_complete_trace_reconstruction',actual,rows);e.eq('fresh_coverage',coverage,inspection['coverage']);e.eq('verified_candidate_hash',result['candidate_sha256'],digest(canonical(candidate)))
            elif op=='t03_compare':
                changes,ci=read_pages(adapter.store,result['pagination_ref'],binding=adapter.binding,kind='u02-comparison',identity=lambda r:r['source_id']);e.ids('every_comparison',[r['source_id']for r in changes],original);e.all('no_hidden_changes',(r['left_sha256']==r['right_sha256']==original[r['source_id']]['geometry_sha256'] and r['added_area_mm2']==0 and r['removed_area_mm2']==0 for r in changes))
            elif op=='t03_review':e.eq('no_invented_reviews',result['records'],[]);e.eq('owner_pending',result['facts']['owner_status'],'PENDING_USER');e.eq('independent_not_run',result['facts']['independent_status'],'NOT_RUN')
            elif op=='t03_controls':
                e.eq('three_corruptions',len(result['controls']),3);e.all('expected_rejections',(r['status']=='PASS_EXPECTED_REJECTION'and r['error'].startswith(r['expected'])for r in result['controls']))
                for control in result['controls']:e.read(root/'u02_t03/controls'/control['name']/'mutation.json')
    return dict(schema='pcb-u02-machine-audit/1',mode=MODE,operation=op,attempt_id=attempt,status='PASS'if all(q['passed'] for q in e.checks)else'FAIL',contract_sha256=digest(CONTRACT.read_bytes()),native_receipt_sha256=verified['receipt_sha256'],raw_response_sha256=digest((folder/'abi/stdout.json').read_bytes()),checks=e.checks,evidence=e.files,owner='PENDING_USER',human_or_agent_observation='NOT_RUN',independent='NOT_RUN: CHANNEL_UNAVAILABLE',rendering='NOT_REQUESTED')
