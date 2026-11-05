"""Machine-audited, append-only C03 recovery gates; no predecessor resealing."""
import copy,json,sys
from pathlib import Path
from datetime import datetime,timezone
from shapely import from_wkb,to_wkb
from shapely.geometry import LineString
from shapely.ops import unary_union
from src.stage_abi import ABI_VERSION
from src.stage_abi.store import canonical,digest
from src.stage_abi.registry import TrustedRegistry
from src.stage_abi.service import StageService
from src.stage_abi.contracts import StageABIError
from src.stage_abi.scene import validate_scene
from src.stage_abi.width import width_parameters
from src.u03_board.inspection import inspect_all,validate as validate_inspection
from src.u03_board.solver import validate_ledger
from src.trace_width_stage import validate_width_partition
from src.prepared_width_scene import PreparedWidthScene
from src.u03_board.paging import put as put_pages,get as get_pages
from src.c03_width_continuation import WidthContinuation
from src.c03_width_export import WidthExport
from src.crop_circle_sources import verify_assets
from tools.t01_native_route import verify_attempt
ROOT=Path(__file__).resolve().parents[1]
STEPS=('retained_prefix_verify','source_admission','current_native_context','width_plan','width_construct','width_verify','coverage_compare','width_controls','pcb_kicad_write','pcb_kicad_verify','pcb_gerber_export','pcb_gerber_verify','pcb_export_controls','preservation_finalize')

def read(p):return json.loads(Path(p).read_bytes())
def fresh(p,x):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('xb')as f:f.write(canonical(x))
def code_files():
    files=[ROOT/'AGENTS.md',ROOT/'requirements.lock.txt',*[p for folder in ('src','tools','contracts','tests')for p in (ROOT/folder).rglob('*')if p.is_file()and(p.suffix=='.py'or folder=='contracts')]]
    return {str(p.relative_to(ROOT)):digest(p.read_bytes())for p in files}
def inventory(root):
    root=Path(root);result={}
    for p in sorted(root.rglob('*')):
        if p.is_symlink():raise ValueError('C03_PREDECESSOR_SYMLINK_REJECTED')
        if p.is_file():result[str(p.relative_to(root))]=dict(sha256=digest(p.read_bytes()),bytes=p.stat().st_size,mtime_ns=p.stat().st_mtime_ns)
    return result

def verify_prefix(predecessor):
    predecessor=Path(predecessor)
    if (predecessor/'C03_WIDTH_RECOVERY_RECEIPT.json').is_file():
        receipt=read(predecessor/'C03_WIDTH_RECOVERY_RECEIPT.json');start=read(predecessor/'START.json');cp=read(predecessor/'checkpoints/014.json')
        if receipt['status']!='PASS_APPEND_ONLY_C03_WIDTH_RECOVERY' or digest((predecessor/'checkpoints/014.json').read_bytes())!=receipt['checkpoint_sha256'] or receipt['producer_files']!=start['producer_files'] or [a['operation']for a in cp['accepted']]!=list(STEPS):raise ValueError('C03_RETAINED_WIDTH_PREFIX_CHANGED')
        from src.c03_width_profile import marker
        spec=marker()['contract'];snapshot=spec['qualified_predecessor_source'];directory=ROOT/snapshot['path'];saved=read(directory/'SOURCE_RECEIPT.json')
        if digest((directory/'SOURCE_RECEIPT.json').read_bytes())!=snapshot['sha256'] or saved['files']!=receipt['producer_files'] or digest((predecessor/'C03_WIDTH_RECOVERY_RECEIPT.json').read_bytes())!=saved['native_receipt_sha256']:raise ValueError('C03_RETAINED_PRODUCER_SNAPSHOT_CHANGED')
        for p,h in saved['files'].items():
            if digest((directory/p).read_bytes())!=h:raise ValueError('C03_RETAINED_PRODUCER_COPY_CHANGED:'+p)
        predicates=0;start_sha=digest((predecessor/'START.json').read_bytes())
        for a in cp['accepted']:
            verify_attempt(predecessor/'attempts'/a['attempt']);proofpath=predecessor/'audits'/a['proof'];proof=read(proofpath)
            if digest(proofpath.read_bytes())!=a['proof_sha256'] or proof['status']!='PASS' or proof['operation']!=a['operation'] or proof['start_sha256']!=start_sha or proof['native_result_sha256']!=a['native_result_sha256'] or digest((predecessor/'operations'/(a['operation']+'.json')).read_bytes())!=a['native_result_sha256'] or not proof['checks'] or not all(c['passed']is True for c in proof['checks']):raise ValueError('C03_RETAINED_WIDTH_MACHINE_PROOF_CHANGED')
            for p,h in proof['input_sha256'].items():
                if digest(Path(p).read_bytes())!=h:raise ValueError('C03_RETAINED_WIDTH_INPUT_CHANGED:'+p)
            audits=[read(proofpath.parent/str(i)/'stdout.json')for i in (1,2)]
            if audits[0]['pid']==audits[1]['pid'] or any(r['proof']!=proof for r in audits):raise ValueError('C03_RETAINED_TWO_PROCESS_AUDIT_CHANGED')
            predicates+=len(proof['checks'])
        for p,h in read(predecessor/'data_output/pcb_gerber_export.json')['output_sha256'].items():
            if digest(Path(p).read_bytes())!=h:raise ValueError('C03_RETAINED_WIDTH_EXPORT_CHANGED')
        board=read(predecessor/'data_output/pcb_kicad_write.json')
        if digest(Path(receipt['kicad']).read_bytes())!=board['board_sha256']:raise ValueError('C03_RETAINED_WIDTH_NATIVE_CHANGED')
        return dict(passed=True,upstream=verify_prefix(receipt['retained_predecessor']),retained_C03_width_gates=len(cp['accepted']),retained_C03_width_predicates=predicates,retained_producer_snapshot_sha256=snapshot['sha256'],prefix_execution='RETAINED_VERIFIED_NOT_REEXECUTED',owner='PENDING_USER',independent='NOT_RUN: CHANNEL_UNAVAILABLE')
    predecessor=Path(predecessor);receipt=read(predecessor/'U05_RECEIPT.json');cp=read(predecessor/'U05_CHECKPOINT.json');start=read(predecessor/'U05_START.json')
    if digest((predecessor/'U05_CHECKPOINT.json').read_bytes())!=receipt['checkpoint_sha256']or receipt['status']!='PASS_U05_RETAINED_CONTINUATION_EXPORT':raise ValueError('C03_U05_RECEIPT_CHANGED')
    from src.u05_board.custody import verify_u04,STEPS as U05_STEPS
    u04=verify_u04(start['predecessor']);accepted=cp['accepted']
    if [a['operation']for a in accepted]!=list(U05_STEPS):raise ValueError('C03_U05_REQUIRED_GATE_PREFIX_INCOMPLETE')
    predicates=0
    for a in accepted:
        verify_attempt(predecessor/'attempts'/a['attempt']);p=predecessor/'audits'/a['proof'];proof=read(p)
        if digest(p.read_bytes())!=a['proof_sha256']or proof['status']!='PASS'or proof['operation']!=a['operation']or not all(c['passed']for c in proof['checks']):raise ValueError('C03_U05_MACHINE_PROOF_CHANGED')
        predicates+=len(proof['checks'])
    for p,h in read(predecessor/'data_output/pcb_gerber_export.json')['output_sha256'].items():
        if digest(Path(p).read_bytes())!=h:raise ValueError('C03_U05_EXPORT_CHANGED')
    return dict(passed=True,retained_U04=u04,retained_U05_gates=len(accepted),retained_U05_predicates=predicates,prefix_execution='RETAINED_VERIFIED_NOT_REEXECUTED',owner='PENDING_USER',independent='NOT_RUN: CHANNEL_UNAVAILABLE')


class Gates:
    def __init__(self,root):
        self.root=Path(root);self.start=read(self.root/'START.json')
        if code_files()!=self.start['producer_files']:raise ValueError('C03_WIDTH_PRODUCER_CHANGED')
        from src.c03_width_profile import selected,marker
        expected=(ROOT/marker()['contract']['predecessor']['receipt']).absolute().parent
        if Path(self.start['predecessor']).absolute()!=expected:raise ValueError('C03_WIDTH_PREDECESSOR_CHANGED')
        if not selected(self.root):raise ValueError('C03_EXPLICIT_WIDTH_PROFILE_REQUIRED')
        self.wc=WidthContinuation(self.start['predecessor'],self.root)
        from src.c03_baseline_custody import check
        from tools.t01_operator_host import HANDOFF
        self.baseline=check(ROOT,self.root,HANDOFF/'CODE_BASELINE_SHA256.json')
    def require_operation(self,op):
        checkpoints=sorted((self.root/'checkpoints').glob('*.json')) if (self.root/'checkpoints').exists() else []
        accepted=[]
        for i,p in enumerate(checkpoints,1):
            value=read(p)
            if p.name!=f'{i:03d}.json' or value['operations']!=list(STEPS) or len(value['accepted'])!=i or value['accepted'][:-1]!=accepted:raise ValueError('C03_AUDITED_PREFIX_CHANGED')
            accepted=value['accepted']
        if len(accepted)>=len(STEPS) or op!=STEPS[len(accepted)]:raise ValueError('C03_AUDITED_OPERATION_ORDER_REQUIRED')
        for a in accepted:
            verify_attempt(self.root/'attempts'/a['attempt']);p=self.root/'audits'/a['proof'];proof=read(p)
            if digest(p.read_bytes())!=a['proof_sha256'] or proof['operation']!=a['operation'] or proof['status']!='PASS' or not all(q['passed']is True for q in proof['checks']) or digest((self.root/'operations'/(a['operation']+'.json')).read_bytes())!=a['native_result_sha256']:raise ValueError('C03_AUDITED_PREFIX_CHANGED')

    def output(self,op):return read(self.root/'operations'/(op+'.json'))
    def admission(self):return self.output('source_admission')['admission']
    def context(self):
        p=self.root/'operations/width_plan.json'
        return read(p)['context'] if p.exists()else self.output('current_native_context')['context']
    def candidate(self):return self.output('width_construct')['result']['candidate']
    def export(self):return WidthExport(self.wc,self.context(),self.candidate())
    def stage(self,context,verb,payload,*,plan_ref=None,authorization_ref=None):
        store=self.wc.store;policy=store.put_json('policy',context['policy']);bounds=store.put_json('bounds',context['plan']['details']['bounds']);verifier=store.put_json('verifier',dict(family=width_parameters()['family']));profile=context['plan']['profile_id']
        registry=dict(schema='stage-agent-registry/1',profiles={profile:dict(stage='t04',adapter='native-width-v1',policy_ref=policy,scene_refs=[context['scene_ref']],bounds_ref=bounds,verifier_ref=verifier)},authorization_refs=[]if authorization_ref is None else[authorization_ref],decision_refs=[])
        service=StageService(store,TrustedRegistry(store,registry),{'native-width-v1':self.wc.adapter});request=dict(abi_version=ABI_VERSION,request_id='c03-width-'+verb+'-'+digest(canonical(payload))[:16],operation='t04_'+verb,profile_id=profile,scene_ref=context['scene_ref'],policy_ref=policy,plan_ref=plan_ref,authorization_ref=authorization_ref,idempotency_key='c03-width-'+verb if verb in ('run','verify')else None,payload=payload)
        response=service.dispatch(request)
        folder=self.root/'abi'/verb;folder.mkdir(parents=True,exist_ok=True);i=len(list(folder.glob('*-request.json')));fresh(folder/f'{i:04d}-request.json',request);fresh(folder/f'{i:04d}-response.json',response)
        if response['status']!='OK':raise ValueError('C03_WIDTH_STAGE_ABI_REJECTED:'+str(response['error']))
        return response['result']

    def pages(self,sets):
        binding=dict(original_source_sha256=digest(self.wc.original_raw),retained_native_sha256=digest(self.wc.raw));refs={}
        for name,rows in sets.items():refs[name]=put_pages(self.wc.store,[dict(record_id=str(i),record=r)for i,r in enumerate(rows)],binding=binding,kind='cw-'+digest(name.encode())[:12])
        return dict(binding=binding,references=refs)
    def check_pages(self,pages,sets):
        for name,expected in sets.items():
            rows,index=get_pages(self.wc.store,pages['references'][name],binding=pages['binding'],kind='cw-'+digest(name.encode())[:12],identity=lambda r:r['record_id'])
            if [r['record']for r in rows]!=expected:raise ValueError('C03_COMPLETE_PAGE_COVERAGE_CHANGED:'+name)
    def comparison(self):
        candidate=self.candidate();factors=dict(self.wc.prior_factors);parts=dict(self.wc.prior_part_sha256)
        for row in candidate['construction']:
            for s in row['complete_source_ids']:
                if row['factor']>=factors.get(s,1.):factors[s]=row['factor'];parts[s]=candidate['parts'][s]['nominal_ref']['sha256']
        return [dict(source_id=r['id'],prior_factor=self.wc.prior_factors.get(r['id'],1.),current_factor=factors.get(r['id'],1.),candidate_part_sha256=parts.get(r['id'],r['geometry_sha256']),original_part_sha256=r['geometry_sha256'],route_change='NONE')for r in self.wc.manifest['objects']if r['kind']in ('segment','arc')]

    def controls(self,*,save):
        candidate=self.candidate();context=self.context();admission=self.admission();controls=[];store=self.wc.store;scene=validate_scene(store,context['scene_ref']);plan=context['plan'];policy=context['policy']
        def reject(name,expected,bad,fn):
            p=self.root/'controls'/name/'mutation.json'
            if save:fresh(p,bad)
            elif read(p)!=bad:raise ValueError('C03_WIDTH_CONTROL_MUTATION_CHANGED')
            try:fn()
            except (ValueError,StageABIError)as e:
                code=e.code if isinstance(e,StageABIError)else str(e).split(':')[0]
                if code!=expected:raise ValueError('C03_WRONG_WIDTH_CONTROL_REJECTION:'+name+':'+str(e))
                controls.append(dict(name=name,expected=expected,error=code,status='PASS_EXPECTED_REJECTION',mutation=str(p),mutation_sha256=digest(p.read_bytes())))
            else:raise ValueError('C03_WIDTH_CONTROL_NOT_REJECTED:'+name)
        bad=dict(context,current_native_source_sha256='0'*64)
        def original():
            if bad['current_native_source_sha256']!=digest(self.wc.raw):raise ValueError('C03_WIDTH_PREDECESSOR_CHANGED')
        reject('wrong_predecessor','C03_WIDTH_PREDECESSOR_CHANGED',bad,original)
        chains={r['component_id']:dict(source_ids=r['complete_source_ids'])for r in candidate['construction']};groups=copy.deepcopy(plan['details']['groups']);groups[0]['members'].append(groups[0]['members'][0]);reject('duplicate_group','TRACE_GROUP_PARTITION_INVALID',groups,lambda:validate_width_partition(chains,groups))
        groups=copy.deepcopy(plan['details']['groups']);groups[0]['members'].pop();groups=[g for g in groups if g['members']];reject('missing_route','TRACE_GROUP_PARTITION_INCOMPLETE',groups,lambda:validate_width_partition(chains,groups))
        bad=copy.deepcopy(candidate);bad['solution']['selected_scales'][next(iter(bad['solution']['selected_scales']))]=.99
        reject('narrowed_scale','WIDTH_SCALE_OUT_OF_SCOPE',bad,lambda:self.wc.adapter.verify(store,scene,policy,plan,bad,dict(scope='complete-source-nominal-envelope-and-upper-proofs'),lambda x:None))
        bad=copy.deepcopy(candidate);sid=next(iter(bad['parts']));bad['parts'][sid]['nominal_ref']=dict(artifact_id='geometry:'+'0'*64,sha256='0'*64)
        reject('changed_native_part','WIDTH_RECONSTRUCTION_MISMATCH',bad,lambda:self.wc.adapter.verify(store,scene,policy,plan,bad,dict(scope='complete-source-nominal-envelope-and-upper-proofs'),lambda x:None))
        row=next(r for r in admission['paths']if r['disposition']=='ADMIT_COMPLETE_NATIVE_ROUTE'and r['exposed_area_mm2']>1e-12);core=unary_union([from_wkb(self.wc.t01_current[s])for s in row['path']['source_ids']]);cover=unary_union([from_wkb(self.wc.t01_current[s])for s in row['coverage_source_ids']])
        def covered():
            if not cover.covers(core):raise ValueError('U03_FALSE_COVERED_PROOF')
        reject('false_covered','U03_FALSE_COVERED_PROOF',dict(core=to_wkb(core).hex(),cover=to_wkb(cover).hex()),covered)
        a=LineString([(0,0),(1,0)]).buffer(.05);b=LineString([(0,.13),(1,.13)]).buffer(.05);traces=[dict(id='a',original=a,candidate=a.buffer(.025),verified_original_width_mm=.1),dict(id='b',original=b,candidate=b.buffer(.025),verified_original_width_mm=.1)];q=PreparedWidthScene(traces,[]).check(traces)
        def clearance():
            if not q['passed']:raise ValueError('U03_WIDTH_CLEARANCE_REJECTED')
        reject('unsafe_finite_copper','U03_WIDTH_CLEARANCE_REJECTED',q,clearance)
        bad=copy.deepcopy(admission);bad['continuation_paths'][0]['source_ids'].pop()
        def partial():
            if bad!=admission:raise ValueError('C03_COMPLETE_NATIVE_ADMISSION_CHANGED')
        reject('partial_native_run','C03_COMPLETE_NATIVE_ADMISSION_CHANGED',bad,partial)
        selected=next(iter(chains));fixed=[chains[selected]['source_ids'][0]]
        reject('fixed_source_selected','PROTECTED_SOURCE_SELECTED_FOR_WIDTH',dict(fixed=fixed),lambda:validate_width_partition(chains,plan['details']['groups'],fixed_source_ids=fixed))
        return dict(passed=True,controls=controls,deliberate_controls=len(controls))

    def execute(self,op):
        w=self.wc
        if op=='retained_prefix_verify':return dict(facts=verify_prefix(w.predecessor),baseline=self.baseline)
        if op=='source_admission':
            a=w.admission();pages=self.pages(dict(source_manifest=w.manifest['objects'],native_traces=a['native_rows'],paths=a['paths'],groups=a['continuation_groups'],relations=[*a['relations'],*a['blocked_relations']]));return dict(admission=a,pages=pages,facts=dict(passed=True,source_traces=a['trace_occurrences'],original_positive=sum(r['required_positive']for r in a['reference_width_obligations']),new_complete_paths=len(a['continuation_paths']),new_complete_groups=len(a['continuation_groups']),previous_widths_protected=len(w.prior_factors)))
        if op=='current_native_context':
            context=w.model(self.admission());scene=validate_scene(w.store,context['scene_ref']);pages=self.pages(dict(current_scene_sources=scene['objects']));return dict(context=context,pages=pages,facts=dict(passed=True,current_native_copper_occurrences=context['current_native_copper_occurrences'],all_current_sources_partitioned=True,all_selected_original_nodes_equal=True))
        if op=='width_plan':
            context=self.context();ids=context['plan']['details']['targets'];ref,count=inspect_all(w.store,ids,lambda verb,payload:self.stage(context,verb,payload));checked=validate_inspection(w.store,ref)
            selection=w.store.put_json('selection',dict(stage='t04',scene_ref=context['scene_ref'],source_ids=ids,groups=context['plan']['details']['groups']));qualification=w.store.put_json('verification',dict(scene_ref=context['scene_ref'],geometric_status='PASS',scope='Complete current native context; original complete-run/source partition; retained qualified U05 prefix'))
            bounds=w.store.put_json('bounds',context['plan']['details']['bounds']);planned=self.stage(context,'plan',dict(inspection_ref=ref,selection_ref=selection,predecessor_qualification_ref=qualification,bounds_ref=bounds,strategy='collective_uniform_width'))
            context=dict(context,plan=planned['plan']);scope=w.store.put_json('output-scope',dict(kind='immutable-local-artifacts'));auth=w.store.put_json('authorization',dict(profile_id=context['plan']['profile_id'],scene_ref=context['scene_ref'],policy_ref=context['plan']['policy_ref'],plan_ref=planned['plan_ref'],operations=['t04_run','t04_verify'],authority='Owner-authorized exact C03 append-only width recovery; all predecessor native nodes protected; no acceptance grant',output_scope_ref=scope))
            return dict(context=context,inspection_ref=ref,plan_ref=planned['plan_ref'],authorization_ref=auth,output_scope_ref=scope,facts=dict(passed=True,complete_ABI_inspection=True,inspection_pages=count,targets=len(checked['records']),groups=len(context['plan']['details']['groups'])))
        if op=='width_construct':
            p=self.output('width_plan');result=self.stage(self.context(),'run',dict(output_scope_ref=p['output_scope_ref']),plan_ref=p['plan_ref'],authorization_ref=p['authorization_ref'])
            if result['reused']or result['job']['status']!='COMPLETED':raise ValueError('C03_FRESH_WIDTH_CONSTRUCTION_REQUIRED')
            return dict(result=result['result'],facts=dict(passed=True,fresh_construction=True,evaluations=result['result']['candidate']['solution']['evaluation_count']))
        if op=='width_verify':
            p=self.output('width_plan');proof=w.store.put_json('proof-scope',dict(scope='complete-source-nominal-envelope-and-upper-proofs'));verifier=w.store.put_json('verifier',dict(family=width_parameters()['family']));result=self.stage(self.context(),'verify',dict(candidate_ref=self.output('width_construct')['result']['candidate_ref'],verifier_ref=verifier,proof_scope_ref=proof),plan_ref=p['plan_ref'],authorization_ref=p['authorization_ref']);v=result['result']['verification']
            if result['reused']or v['geometric_status']!='PASS':raise ValueError('C03_WIDTH_RECONSTRUCTION_REJECTED')
            return dict(result=result['result'],facts=dict(passed=True,fresh_reconstruction=True,nominal_and_envelope=True,upper_proofs=len(v['check']['maximum_proofs'])))
        if op=='coverage_compare':return dict(coverage=w.coverage(self.admission(),self.candidate()),comparison_pages=self.pages(dict(source_comparisons=self.comparison())),facts=dict(passed=True,previous_width_factors_preserved=True,blocked_source_nodes_protected=True))
        if op=='width_controls':
            q=self.controls(save=True);return dict(q,facts=dict(passed=q['passed'],deliberate_controls=q['deliberate_controls']))
        if op in ('pcb_kicad_write','pcb_kicad_verify','pcb_gerber_export','pcb_gerber_verify','pcb_export_controls'):
            service=self.export();return dict(pcb_kicad_write=service.write_kicad,pcb_kicad_verify=service.verify_kicad,pcb_gerber_export=service.export_gerber,pcb_gerber_verify=service.verify_gerber,pcb_export_controls=service.controls)[op]()
        if op=='preservation_finalize':
            unchanged={p:inventory(p)==expected for p,expected in self.start['predecessor_inventories'].items()}
            if not all(unchanged.values()):raise ValueError('C03_PREDECESSOR_EVIDENCE_CHANGED')
            from src.trace_first_pipeline import frozen_fingerprint
            freezes=[frozen_fingerprint(ROOT,e)for e in self.start['protected_freezes']]
            return dict(facts=dict(passed=True,all_predecessor_files_sha_bytes_mtime_equal=True,predecessors=unchanged,assets=verify_assets(),protected_freezes=freezes))
        raise ValueError('C03_WIDTH_OPERATION_UNKNOWN')

    def audit(self,op,value):
        checks=[]
        def yes(name,value):
            checks.append(dict(id=name,passed=bool(value)))
            if not value:raise ValueError('C03_WIDTH_MACHINE_PREDICATE_FAILED:'+name)
        yes('saved_native_success',value['facts']['passed'])
        if op=='retained_prefix_verify':
            yes('exact_retained_prefix',value['facts']==verify_prefix(self.wc.predecessor));yes('unchanged_full_baseline_custody_check',value['baseline']==self.baseline)
        elif op=='source_admission':
            a=self.wc.admission();yes('fresh_complete_source_admission',value['admission']==a);self.check_pages(value['pages'],dict(source_manifest=self.wc.manifest['objects'],native_traces=a['native_rows'],paths=a['paths'],groups=a['continuation_groups'],relations=[*a['relations'],*a['blocked_relations']]));yes('every_source_path_group_relation_page',True)
        elif op=='current_native_context':
            yes('fresh_complete_current_native_context',value['context']==self.wc.model(self.admission()));self.check_pages(value['pages'],dict(current_scene_sources=validate_scene(self.wc.store,value['context']['scene_ref'])['objects']));yes('every_current_native_scene_page',True)
        elif op=='width_plan':
            context=value['context'];inspection=validate_inspection(self.wc.store,value['inspection_ref']);yes('every_ABI_inspection_page',inspection['selected_source_ids']==context['plan']['details']['targets']);yes('unchanged_numeric_policy',context['policy']==dict(stage='t04',parameters=width_parameters()));yes('exact_groups',context['plan']['details']['groups']==self.admission()['continuation_groups']);yes('exact_plan_artifact',self.wc.store.get_json(value['plan_ref'],kind='plan')==context['plan'])
        elif op in ('width_construct','width_verify'):
            candidate=self.candidate();yes('actual_candidate_artifact',self.wc.store.get_json(self.output('width_construct')['result']['candidate_ref'],kind='candidate')==candidate);yes('complete_width_evaluation_ledger',validate_ledger(self.wc.store,candidate)==candidate['solution']['evaluation_count']);q=self.wc.verify(self.context(),candidate);yes('fresh_nominal_and_envelope',q['passed']);yes('every_fresh_final_neighbor_upper_proof',all(p['proved']for p in q['maximum_proofs']))
            if op=='width_verify':yes('actual_ABI_verification',value['result']['verification']['check']==q)
        elif op=='coverage_compare':
            self.check_pages(value['comparison_pages'],dict(source_comparisons=self.comparison()));yes('every_source_comparison_page',True);yes('independent_original_width_denominator',value['coverage']==self.wc.coverage(self.admission(),self.candidate()));yes('prior_widths_never_reduced',value['coverage']['previous_width_factors_preserved'])
        elif op=='width_controls':yes('all_nine_deliberate_rejections',value['controls']==self.controls(save=False)['controls']and value['deliberate_controls']==9)
        elif op in ('pcb_kicad_write','pcb_kicad_verify'):yes('actual_native_reread',self.export().native_check(self.export().board.read_bytes())['passed']);yes('before_native_bytes_exact',self.export().before.read_bytes()==self.wc.raw)
        elif op=='pcb_gerber_export':
            yes('actual_pinned_native_export_exit',value['facts']['native_export_exit']==0 and value['facts']['layers']==9 and len(value['output_sha256'])==18)
            for p,h in value['output_sha256'].items():yes('fresh_export:'+p,digest(Path(p).read_bytes())==h)
            for name in ('before_export','candidate_export','kicad_version'):yes('native_process:'+name,read(self.export().out/(name+'.command.json'))['exit_status']==0)
        elif op=='pcb_gerber_verify':yes('actual_export_complete_reparse_and_hard_floor',value['verification']==self.export().plot_check())
        elif op=='pcb_export_controls':
            service=self.export();directory=service.out/'controls';yes('five_original_native_export_controls',len(value['controls'])==5)
            operations={'wrong_units':lambda:__import__('src.pcb_data_abi.gerber',fromlist=['parse']).parse(directory/'wrong_units.gbr'),'clear_polarity':lambda:service.plot_check(directory/'clear_polarity.gbr'),'wrong_role':lambda:service.plot_check(directory/'wrong_role.gbr'),'missing_width':lambda:service.plot_check(directory/'missing_width.gbr'),'protected_native_node':lambda:service.native_check((directory/'protected_changed.kicad_pcb').read_bytes())}
            operands=service.control_operands()
            for r in value['controls']:
                path,expected=operands[r['name']];yes('exact_control_operand:'+r['name'],str(path)==r['mutation']and digest(expected)==r['mutation_sha256']and path.read_bytes()==expected)
                try:operations[r['name']]()
                except ValueError as e:yes('actual_export_rejection:'+r['name'],str(e).startswith(r['expected']))
                else:yes('actual_export_rejection:'+r['name'],False)
        elif op=='preservation_finalize':
            for p,expected in self.start['predecessor_inventories'].items():yes('complete_predecessor_inventory:'+p,inventory(p)==expected)
            yes('all_immutable_assets',verify_assets()==value['facts']['assets'])
            from src.trace_first_pipeline import frozen_fingerprint
            yes('all_frozen_C01_C02_C03_files',[frozen_fingerprint(ROOT,e)for e in self.start['protected_freezes']]==value['facts']['protected_freezes'])
        else:raise ValueError('C03_MACHINE_OPERATION_UNKNOWN')
        self.wc.verify_inputs();yes('read_operand_hashes_stable',True)
        return dict(schema='c03-width-native-machine-proof/1',operation=op,status='PASS',checks=checks,native_result_sha256=digest(canonical(value)),start_sha256=digest((self.root/'START.json').read_bytes()) if (self.root/'START.json').exists() else None,input_sha256=self.wc.inputs,owner='PENDING_USER',independent='NOT_RUN: CHANNEL_UNAVAILABLE',human_or_agent_observations=0)
