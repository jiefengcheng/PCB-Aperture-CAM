"""U03 crop T01 predicates, preserving the frozen whole-board auditor.

This audit does not author prose observations, grant owner approval, reconstruct
copper, or change policy. Native verifiers still execute through the original ABI.
"""
from pathlib import Path
import math
from src.stage_abi.store import ArtifactStore,digest,canonical
from src.t01_crop.paging import read_pages,inspection_binding
from src.stage_abi.service import runtime_fingerprint
from src.u03_board.crop_t01 import ImageCropAdapter as BoardAdapter,context
from src.pcb_data_abi.input_directory import verify_snapshot
from src.pcb_data_abi.board_custody import ROI,T01,CHECK,FILES
from tools.t01_native_route import verify_attempt
from tools.t01_route_client import decode,safe_id

ROOT=Path(__file__).resolve().parents[1]
CONTRACT=ROOT/'contracts/operator/u03_board.json'
STEPS=(*ROI,*T01,CHECK,*FILES)
MODE='DETERMINISTIC_MACHINE_AUDIT'

def proof_note(sha):return f'MACHINE predicate audit sha256:{sha}; evidence in audits/machine-NNN/proof.json. No human/agent observation or owner approval.'

class Evidence:
    def __init__(self,root):self.root=Path(root);self.files={};self.checks=[]
    def read(self,path):
        p=Path(path)
        if '..'in p.parts or not p.is_relative_to(self.root)or any(q.is_symlink()for q in(p,*p.parents)if q.is_relative_to(self.root)):raise ValueError('MACHINE_AUDIT_EVIDENCE_PATH_INVALID')
        blob=p.read_bytes();self.files[str(p.relative_to(self.root))]=digest(blob);return decode(blob)
    def eq(self,name,observed,expected):
        passed=type(observed)is type(expected)and observed==expected
        def compact(value):
            if isinstance(value,(dict,list)):
                blob=canonical(value);return dict(sha256=digest(blob),records=len(value),bytes=len(blob))
            return value
        self.checks.append(dict(predicate=name,observed=compact(observed),expected=compact(expected),passed=passed))
    def yes(self,name,value):self.eq(name,value,True)
    def ids(self,name,observed,expected):self.eq(name,digest(canonical(sorted(observed))),digest(canonical(sorted(expected))))
    def all(self,name,values):
        values=list(values);self.checks.append(dict(predicate=name,observed=dict(records=len(values),passed=sum(v is True for v in values)),expected=dict(records=len(values),passed=len(values)),passed=bool(values)and all(v is True for v in values)))

class TrackedStore(ArtifactStore):
    def __init__(self,root,evidence):super().__init__(root);self.evidence=evidence
    def get(self,ref,*,kind=None):
        blob=super().get(ref,kind=kind);self.evidence.files[str((self.root/'artifacts'/ref['artifact_id']).relative_to(self.evidence.root))]=digest(blob);return blob

def evaluate(root,attempt):
    root=Path(root);safe_id(attempt);e=Evidence(root);contract=decode(CONTRACT.read_bytes());folder=root/'attempts'/attempt
    verified=verify_attempt(folder);receipt=e.read(folder/'receipt.json');op=receipt['tool']
    if op not in STEPS:raise ValueError('MACHINE_AUDIT_OPERATION_UNSUPPORTED')
    raw=e.read(folder/'abi/stdout.json');request=e.read(folder/'abi/request.json');completed=e.read(folder/'abi/completed.json');saved=e.read(folder/'result.json')
    e.eq('attempt_identity',receipt['attempt_id'],attempt);e.eq('native_error_absent',saved['error'],None)
    e.all('abi_response_correlation',(raw[k]==request[k]for k in('abi_version','request_id','operation')))
    negative=op=='t01_negative_compile'
    e.eq('actual_process_exit',completed['returncode'],2 if negative else 0)
    e.eq('abi_status',raw['status'],'REJECTED'if negative else'OK')
    e.eq('response_digest_bound',saved['result']['raw_response_sha256'],digest((folder/'abi/stdout.json').read_bytes()))
    e.eq('operation_bound',saved['result']['operation'],op)
    if negative:
        e.eq('expected_semantic_rejection',raw['error']['code'],'T01_ENGLISH_UNSUPPORTED');e.eq('negative_policy_absent',raw['result'],None)
    else:
        e.eq('abi_error_absent',raw['error'],None);r=raw['result'];f=r.get('facts',{})
        if op in(*ROI,CHECK,*FILES):e.yes('native_facts_passed',f['passed'])
        job=decode((root.parent/'job.json').read_bytes())
        manifest_path=Path(job['input_directory']);manifest=decode(manifest_path.read_bytes())
        e.eq('raw_manifest_hash',digest(manifest_path.read_bytes()),job['input_directory_sha256'])
        if op in ROI:
            source=e.read(root/'data_board/source_manifest.json');ids=[q['id']for q in source['objects']]
            e.eq('source_inventory_hash',source['source_sha256'],job['inputs']['kicad']['sha256'])
        if op==ROI[0]:
            verify_snapshot(manifest,manifest_path.parent/'raw_inputs')
            e.eq('source_object_count',f['source_objects'],len(ids));e.yes('source_correspondence',f['source_gerber_correspondence']);e.eq('no_frame_fit',f['registration_fit_used'],False)
            participating=[q for q in manifest['files']if q['kind']=='gerber'];companions=[q for q in manifest['files']if q['kind']=='companion']
            e.eq('participating_layer_count',f['provided_gerber_files'],len(participating));e.yes('participating_layers_verified',f['all_supplied_layers_verified'])
            e.ids('participating_layer_set',[q['layer']for q in r['directory_layer_matches']],[q['layer']for q in participating]);e.all('each_layer_verified',(q['passed']for q in r['directory_layer_matches']))
            e.eq('generated_source_hash',digest(Path(r['generated_source_gerber']).read_bytes()),r['generated_source_gerber_sha256'])
            if manifest['schema'].endswith('/2'):
                e.eq('excluded_companion_count',f['excluded_companion_files'],len(companions));e.yes('complete_input_accounting',f['complete_input_accounting'])
                e.eq('correspondence_control_count',len(r['correspondence_controls']),3);e.all('correspondence_controls_rejected',(q['status']=='PASS_EXPECTED_REJECTION'and q['measurement']['passed']is False for q in r['correspondence_controls']))
        elif op in ROI[1:]:
            e.ids('all_source_ids',r['all_source_ids'],ids);e.eq('complete_source_count',r['source_objects'],len(ids));e.eq('no_image_geometry',r['image_used'],False)
            e.eq('occurrence_count',len(r['eligible_occurrence_ids']),r['source_occurrences']);e.eq('unique_occurrences',len(set(r['eligible_occurrence_ids'])),r['source_occurrences']);e.yes('nonempty_site_scope',r['canonical_sites']>0)
            if op==ROI[1]:e.yes('complete_growth_window',f['complete_source_window'])
            else:
                e.yes('complete_source_coverage',f['complete_source_coverage']);e.eq('scope_control_count',len(r['controls']),3);e.all('scope_controls_rejected',(q['status']=='PASS_EXPECTED_REJECTION'for q in r['controls']))
        else:
            scope=e.read(root/'data_board/verified.json');total=scope['source_objects']
            store=TrackedStore(root/'runtime',e)
            capsule=e.read(sorted(root.glob('capsule_*.json'))[-1])
            policy=r['policy'] if op=='t01_compile' else store.get_json(capsule['policy_ref'],kind='policy')
            scene=store.get_json(capsule['scene_ref'],kind='scene')
            binding,source,native_rows,shapes,sites=context(store,scene,policy)
            n=len(sites);aliases=sum(len(s['aliases']) for s in sites)
            e.ids('complete_crop_circle_pool',[s['source_id'] for s in sites],[r['source_id'] for r in binding['u03_site_inventory'] if r['disposition']=='SELECT_COMPLETE_GROWTH_ENVELOPE'])
            def prior(name):
                matches=[]
                for p in(root/'attempts').glob('*/receipt.json'):
                    value=decode(p.read_bytes())
                    if value['tool']==name:matches.append(p.parent)
                if len(matches)!=1:raise ValueError('MACHINE_AUDIT_PRIOR_ATTEMPT_AMBIGUOUS:'+name)
                return e.read(matches[0]/'abi/stdout.json')['result']
            if op=='t01_compile':
                policy=r['policy'];e.eq('sixteen_clauses',len(policy['clause_trace']),16);e.eq('hard_gap_unchanged',policy['settings']['hard_gap'],.02);e.eq('policy_artifact_matches',store.get_json(r['policy_ref'],kind='policy'),policy);e.eq('compile_no_construction',r['construction_status'],'NOT_RUN')
                e.eq('binding_matches_request',policy['binding_ref'],request['payload']['binding_ref'])
            elif op=='t01_discover':
                d=r['discovery'];e.eq('discovery_site_count',d['unique_sites'],n);e.eq('discovery_occurrences',d['occurrences'],aliases);e.eq('discovery_source_count',d['source_objects'],total);e.eq('unique_site_ids',len(set(d['source_ids'])),n)
                # Source inventory pages are referenced by the current capsule's
                # source binding, independently of the discovery summary.
                capsule=e.read(sorted(root.glob('capsule_*.json'))[-1]);b=store.get_json(capsule['binding_ref'],kind='t01-binding')
                rows,index=read_pages(store,b['source_inventory_ref'],binding=dict(source_sha256=b['source_sha256'],manifest_sha256=b['manifest_sha256']),kind='t01-source-inventory',identity=lambda q:q['source_id'])
                e.eq('source_pages_exhausted',len(rows),total);e.eq('discovery_artifact_matches',store.get_json(r['discovery_ref'],kind='t01-discovery'),d)
            elif op=='t01_inspect':
                d=prior('t01_discover')['discovery'];rows,index=read_pages(store,r['pagination_ref'],binding=inspection_binding(request,request['payload']['selection_ref']),kind='t01-inspection',identity=lambda q:q['record']['source_id'])
                e.eq('inspection_count',len(rows),n);e.eq('inspection_records_match',rows,r['records']);e.ids('inspection_id_set',[q['record']['source_id']for q in rows],d['source_ids']);e.eq('inspection_cursor_exhausted',r['next_cursor'],None);e.eq('inspection_page_count',r['page_count'],len(index['pages']))
            elif op=='t01_plan':
                p=r['plan'];d=prior('t01_discover')['discovery'];e.eq('plan_artifact_matches',store.get_json(r['plan_ref'],kind='plan'),p);e.ids('plan_target_set',p['details']['targets'],d['source_ids']);e.eq('plan_runtime_unchanged',p['runtime'],runtime_fingerprint());e.eq('plan_implementation_unchanged',p['implementation'],BoardAdapter().describe()['implementation']);e.eq('plan_no_construction',r['construction_status'],'NOT_RUN');e.eq('port_site_count',p['details']['allocation']['ports']['sites'],n)
                capsule=e.read(sorted(root.glob('capsule_*.json'))[-1]);b=store.get_json(capsule['binding_ref'],kind='t01-binding');ports=p['details']['allocation']['ports']
                port_rows,port_index=read_pages(store,ports['index_ref'],binding=dict(source_sha256=b['source_sha256'],site_ids_sha256=digest(canonical(sorted(d['source_ids']))),viewport_mm=b['viewport_mm']),kind='t01-board-ports',identity=lambda q:q['source_id'])
                e.eq('port_pages_exhausted',len(port_rows),n);e.eq('port_page_count',len(port_index['pages']),ports['pages']);e.ids('port_id_set',[q['source_id']for q in port_rows],d['source_ids']);e.eq('port_zone_count',sum(len(q['ports'])for q in port_rows),ports['zones'])
                for q in port_rows:
                    for ref in q['ports'].values():store.get(ref,kind='t01-port-geometry')
            elif op in('t01_run','t01_verify'):
                e.eq('fresh_job_completed',r['job']['status'],'COMPLETED');e.eq('no_reuse',r['reused'],False);e.eq('fresh_execution_mode',r['result']['execution_evidence']['mode'],'FRESH_EXECUTION')
                if op=='t01_run':
                    c=r['result']['candidate'];e.eq('candidate_artifact_matches',store.get_json(r['result']['candidate_ref'],kind='candidate'),c);e.eq('candidate_site_count',c['unique_sites'],n);e.eq('candidate_occurrences',c['source_occurrences'],aliases);e.eq('candidate_source_count',c['source_objects'],total);e.eq('assembled_check_count',len(c['final_checks']),n);e.all('assembled_checks_pass',(q['check']['passed']for q in c['final_checks']));e.eq('candidate_owner_pending',c['owner_status'],'PENDING');e.eq('candidate_independent_not_run',c['independent_status'],'NOT_RUN')
                else:
                    v=r['result']['verification'];e.eq('verification_artifact_matches',store.get_json(r['result']['verification_ref'],kind='verification'),v);e.eq('fresh_geometry_verified',v['geometric_status'],'PASS');e.eq('verified_candidate_binding',v['candidate_ref'],prior('t01_run')['result']['candidate_ref']);e.eq('verified_owner_pending',v['owner_status'],'PENDING');e.eq('verified_independent_not_run',v['independent_status'],'NOT_RUN')
            elif op=='t01_compare':
                binding=dict(scene_ref=request['scene_ref'],policy_ref=request['policy_ref'],profile_id=request['profile_id'],**{k:v for k,v in request['payload'].items()if k!='page_size'})
                rows,index=read_pages(store,r['pagination_ref'],binding=binding,kind='t01-comparison',identity=lambda q:q['source_id']);e.eq('comparison_count',len(rows),n);e.eq('comparison_records_match',rows,r['source_changes']);e.ids('comparison_id_set',[q['source_id']for q in rows],prior('t01_discover')['discovery']['source_ids']);e.eq('comparison_page_count',r['page_count'],len(index['pages']));e.yes('growth_only',math.isfinite(r['removed_area_mm2'])and r['removed_area_mm2']<=1e-10);e.yes('finite_added_area',math.isfinite(r['added_area_mm2'])and r['added_area_mm2']>=0)
            elif op=='t01_review':
                e.eq('owner_not_approved',r['owner_status'],'PENDING');e.eq('independent_not_approved',r['independent_status'],'NOT_RUN');e.eq('no_invented_decision_records',r['records'],[]);e.eq('review_cursor_exhausted',r['next_cursor'],None)
            elif op==CHECK:
                for k in('complete_source_coverage','full_reconstruction_passed','protected_sources_unchanged'):e.yes(k,f[k])
                e.eq('no_historical_candidate',f['historical_candidate_read'],False);e.eq('handoff_sites',f['canonical_sites'],n);e.eq('handoff_occurrences',f['aliases'],aliases);e.eq('handoff_receipt_hash',digest((root/'RECEIPT.json').read_bytes()),r['receipt_sha256'])
            elif op in('pcb_kicad_write','pcb_kicad_verify','pcb_gerber_verify'):
                e.eq('export_site_count',f['canonical_sites'],n);e.eq('export_occurrence_count',f['source_occurrences'],aliases)
                if op=='pcb_kicad_write':e.eq('candidate_board_hash',digest(Path(r['board']).read_bytes()),r['board_sha256'])
                if op=='pcb_kicad_verify':e.yes('protected_nodes_equal',f['protected_nodes_equal']);e.yes('all_native_contours_pass',f['all_target_contours_pass'])
                if op=='pcb_gerber_verify':e.yes('protected_fcu_atoms',f['protected_fcu_atoms_equal']);e.eq('eight_other_layers_protected',f['protected_other_layers'],8)
            elif op=='pcb_gerber_export':
                e.eq('native_export_exit',f['native_export_exit'],0);e.eq('nine_native_layers',f['layers'],9);e.eq('pinned_version',f['kicad_version'],'10.99.0');e.eq('six_decimal_export',f['precision_decimals'],6);e.eq('before_candidate_sets',set_digest(r['exports'].keys()),set_digest(['before','candidate']))
                e.eq('eighteen_export_files',len(r['output_sha256']),18)
                for p,h in r['output_sha256'].items():e.eq('gerber_file_hash:'+Path(p).name+':'+Path(p).parent.parent.name,digest(Path(p).read_bytes()),h)
            elif op=='pcb_export_controls':
                e.eq('export_control_count',len(r['controls']),3);e.yes('all_export_controls_rejected',f['all_rejected_for_expected_reason']);e.all('export_control_reasons',(q['status']=='PASS_EXPECTED_REJECTION'and q['error'].startswith(q['expected'])for q in r['controls']))
            else:raise ValueError('MACHINE_AUDIT_GATE_MISSING')
    status='PASS'if all(q['passed']for q in e.checks)else'FAIL'
    return dict(schema='pcb-t01-machine-audit/1',mode=MODE,operation=op,attempt_id=attempt,status=status,contract_sha256=digest(CONTRACT.read_bytes()),native_receipt_sha256=verified['receipt_sha256'],raw_response_sha256=digest((folder/'abi/stdout.json').read_bytes()),checks=e.checks,evidence=e.files,owner='PENDING_USER',human_or_agent_observation='NOT_RUN',independent='NOT_RUN: CHANNEL_UNAVAILABLE',rendering='NOT_REQUESTED')

def set_digest(values):return digest(canonical(sorted(values)))
