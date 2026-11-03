"""Native U03 T04 gates, backed by the executable stage ABI and exact T03."""
import copy
from pathlib import Path
from shapely import from_wkb, to_wkb
from src.stage_abi import ABI_VERSION
from src.stage_abi.store import ArtifactStore,canonical,digest
from src.stage_abi.registry import TrustedRegistry
from src.stage_abi.service import StageService
from src.stage_abi.scene import composed,validate_scene
from src.stage_abi.native_import import import_width_scene
from src.stage_abi.width import width_parameters
from src.t01_crop.paging import store_pages,read_pages
from src.u02_board.adapter import RetainPathsAdapter,verify_candidate
from tools.t01_operator_host import read,fresh
from .source import qualify,require_admitted
from .width import WholeBoardWidthAdapter
from .paging import put as put_pages,get as get_pages
from .inspection import inspect_all,validate as validate_inspection
from .selection import for_root,retain_paths

PROFILE='u03-native-whole-board-width-v1'


class WidthGates:
    def __init__(self,root):
        self.root=Path(root);self.out=self.root/'u03_t04';self.store=ArtifactStore(self.root/'runtime')
        t03=retain_paths(root);self.t03=t03
        candidate=read(root/'u02_t03/t03_search.json')['candidate']
        verify_candidate(candidate,read(root/'u02_t03/t03_plan.json')['plan'],t03.scene_ref)
        proof=read(root/'u02_t03/t03_verify.json')
        if proof['binding']!=t03.binding or proof['candidate_sha256']!=digest(canonical(candidate)) or proof['facts']['passed'] is not True:
            raise ValueError('U03_EXACT_VERIFIED_T03_REQUIRED')
        self.predecessor_ref=candidate['output_scene_ref'];self.predecessor=validate_scene(self.store,self.predecessor_ref)
        binding=self.store.get_json(t03.receipt['binding_ref'],kind='t01-binding')
        self.raw=self.store.get(binding['source_ref'],kind='native-source')
        self.manifest=read(root/'data_board/source_manifest.json')
        if digest(self.raw)!=self.manifest['source_sha256']:
            raise ValueError('U03_NATIVE_SOURCE_CHANGED')
        self.original={r['source_id']:self.store.get(r['original_ref'],kind='geometry') for r in self.predecessor['objects']}
        self.current={r['source_id']:self.store.get(r['geometry_ref'],kind='geometry') for r in self.predecessor['objects']}
        self.binding=dict(predecessor_scene_ref=self.predecessor_ref,t03_candidate_sha256=digest(canonical(candidate)),
                          t03_verification_sha256=digest((root/'u02_t03/t03_verify.json').read_bytes()),
                          source_sha256=digest(self.raw))

    def save(self,op,result):
        fresh(self.out/(op+'.json'),result);return result

    def inspection(self):
        saved=read(self.out/'t04_inspect.json')
        if saved['binding']!=self.binding:raise ValueError('U03_WIDTH_PREDECESSOR_CHANGED')
        report=self.store.get_json(saved['report_ref'],kind='u03-admission')
        for field,kind,key in [('source_pages_ref','u03-width-sources','source_id'),('path_pages_ref','u03-width-paths','record_id'),('group_pages_ref','u03-width-groups','group_id'),('relation_pages_ref','u03-width-relations','record_id')]:
            rows,index=get_pages(self.store,saved[field],binding=self.binding,kind=kind,identity=lambda r:r[key])
            expected={'source_pages_ref':report['native_rows'],'path_pages_ref':saved['path_records'],
                      'group_pages_ref':report['groups'],'relation_pages_ref':saved['relation_records']}[field]
            if rows!=expected:raise ValueError('U03_WIDTH_PAGE_COVERAGE_CHANGED:'+field)
        return saved,report

    def inspect(self):
        self.out.mkdir()
        report=qualify(self.raw,self.manifest['objects'],self.original,self.current,selection=for_root(self.root))
        paths=[dict(record_id=str(i),**r) for i,r in enumerate(report['paths'])]
        relations=[dict(record_id=str(i),**r) for i,r in enumerate([*report['relations'],*report['blocked_relations']])]
        refs={};counts={}
        for field,kind,rows in [('source','u03-width-sources',report['native_rows']),('path','u03-width-paths',paths),('group','u03-width-groups',report['groups']),('relation','u03-width-relations',relations)]:
            ref=put_pages(self.store,rows,binding=self.binding,kind=kind);refs[field+'_pages_ref']=ref
            counts[field+'_pages']=(len(rows)+99)//100
        return self.save('t04_inspect',dict(binding=self.binding,report_ref=self.store.put_json('u03-admission',report),
            path_records=paths,relation_records=relations,**refs,
            facts=dict(passed=True,trace_occurrences=report['trace_occurrences'],source_objects=report['source_objects'],
                       paths=len(paths),admitted_paths=len(report['admitted_paths']),groups=len(report['groups']),unsupported=len(report['unsupported']),
                       classifications=report['classifications'],complete_source_coverage=True,**counts)))

    def admit(self):
        saved,report=self.inspection();require_admitted(report)
        qualification=dict(**self.binding,admission_sha256=saved['report_ref']['sha256'],
                           scope='Complete native junction paths; uniform original widths; all fixed T03 source contributions retained')
        chains=[dict(component_id=p['path_id'],source_ids=p['source_ids'],source_sha256=digest(self.raw)) for p in report['admitted_paths']]
        imported=import_width_scene(self.store,source=self.raw,manifest=self.manifest,original_blobs=self.original,
            current_blobs={s:b for s,b in self.current.items() if b!=self.original[s]},chains=chains,
            viewport_mm=self.predecessor['viewport_mm'],qualification=qualification)
        scene=validate_scene(self.store,imported['scene_ref'])
        a=composed(self.store,self.predecessor);b=composed(self.store,scene)
        if a.symmetric_difference(b).area>1e-10:raise ValueError('U03_T03_WIDTH_IMPORT_COPPER_CHANGED')
        policy=self.store.put_json('policy',dict(stage='t04',parameters=width_parameters()))
        bounds=self.store.put_json('bounds',dict(max_source_objects=len(scene['objects']),max_targets=len(imported['target_ids']),
            max_evaluations=30*len(report['groups'])+10,max_output_bytes=12_000_000_000,max_seconds=14400))
        verifier=self.store.put_json('verifier',dict(family=width_parameters()['family']))
        registry=dict(schema='stage-agent-registry/1',profiles={PROFILE:dict(stage='t04',adapter='native-width-v1',policy_ref=policy,
            scene_refs=[imported['scene_ref']],bounds_ref=bounds,verifier_ref=verifier)},authorization_refs=[],decision_refs=[])
        return self.save('t04_admit',dict(binding=self.binding,imported=imported,registry=registry,
            qualification_ref=self.store.put_json('verification',dict(scene_ref=imported['scene_ref'],geometric_status='PASS',**qualification)),
            facts=dict(passed=True,exact_T03_copper_preserved=True,source_members=report['trace_occurrences'],selected_native_members=imported['selected_native_members'],
                       protected_native_members=imported['unchanged_native_members'],groups=len(report['groups']),source_disjoint=True)))

    def context(self):
        admitted=read(self.out/'t04_admit.json');registry=copy.deepcopy(admitted['registry'])
        if (self.out/'t04_plan.json').exists():registry['authorization_refs']=[read(self.out/'t04_plan.json')['authorization_ref']]
        service=StageService(self.store,TrustedRegistry(self.store,registry),{'native-width-v1':WholeBoardWidthAdapter()})
        return admitted,registry,service

    def call(self,verb,payload,**refs):
        admitted,registry,service=self.context();profile=registry['profiles'][PROFILE]
        request=dict(abi_version=ABI_VERSION,request_id='u03-'+verb+'-'+digest(canonical(payload))[:16],operation='t04_'+verb,
            profile_id=PROFILE,scene_ref=admitted['imported']['scene_ref'],policy_ref=profile['policy_ref'],
            plan_ref=refs.get('plan_ref'),authorization_ref=refs.get('authorization_ref'),idempotency_key=refs.get('idempotency_key'),payload=payload)
        response=service.dispatch(request)
        folder=self.out/'abi'/verb;folder.mkdir(parents=True,exist_ok=True)
        number=len(list(folder.glob('*.json')))//2
        fresh(folder/f'{number:04d}-request.json',request);fresh(folder/f'{number:04d}-response.json',response)
        if response['status']!='OK':raise ValueError('U03_WIDTH_ABI_REJECTED:'+str(response['error']))
        return response['result']

    def plan(self):
        saved,report=self.inspection();require_admitted(report);admitted,registry,service=self.context()
        ids=admitted['imported']['target_ids']
        inspection_ref,page_count=inspect_all(self.store,ids,self.call)
        validate_inspection(self.store,inspection_ref)
        selection=self.store.put_json('selection',dict(stage='t04',scene_ref=admitted['imported']['scene_ref'],source_ids=ids,groups=report['groups']))
        profile=registry['profiles'][PROFILE]
        planned=self.call('plan',dict(inspection_ref=inspection_ref,selection_ref=selection,
            predecessor_qualification_ref=admitted['qualification_ref'],bounds_ref=profile['bounds_ref'],strategy='collective_uniform_width'))
        output=self.store.put_json('output-scope',dict(kind='immutable-local-artifacts'))
        auth=self.store.put_json('authorization',dict(profile_id=PROFILE,scene_ref=admitted['imported']['scene_ref'],policy_ref=profile['policy_ref'],
            plan_ref=planned['plan_ref'],operations=['t04_run','t04_verify'],authority='User-authorized fresh U03; fixed source paths, uniform widths; no owner acceptance',output_scope_ref=output))
        return self.save('t04_plan',dict(**planned,inspection_ref=inspection_ref,authorization_ref=auth,output_scope_ref=output,
            facts=dict(passed=True,complete_ABI_inspection=True,inspection_pages=page_count,inspection_batches=(len(ids)+999)//1000,complete_routes=len(ids),groups=len(report['groups']),construction_status='NOT_RUN')))

    def run(self):
        p=read(self.out/'t04_plan.json');result=self.call('run',dict(output_scope_ref=p['output_scope_ref']),plan_ref=p['plan_ref'],authorization_ref=p['authorization_ref'],idempotency_key='fresh-u03-width')
        if result['reused'] or result['job']['status']!='COMPLETED':raise ValueError('U03_FRESH_WIDTH_CONSTRUCTION_REQUIRED')
        c=result['result']['candidate']
        return self.save('t04_run',dict(result=result['result'],facts=dict(passed=True,fresh_construction=True,
            groups=len(c['solution']['selected_scales']),evaluations=c['solution']['evaluation_count'],maximum_established=c['solution']['maximum_established'],
            changed_routes=sum(r['factor']>1 for r in c['construction']),changed_native_parts=sum(len(r['complete_source_ids']) for r in c['construction'] if r['factor']>1))))

    def verify(self):
        saved,report=self.inspection();actual=qualify(self.raw,self.manifest['objects'],self.original,self.current,selection=for_root(self.root))
        if actual!=report:raise ValueError('U03_WIDTH_FRESH_ADMISSION_RECONSTRUCTION_FAILED')
        p=read(self.out/'t04_plan.json');run=read(self.out/'t04_run.json')
        from .solver import validate_ledger
        validate_ledger(self.store,run['result']['candidate'])
        proof=self.store.put_json('proof-scope',dict(scope='complete-source-nominal-envelope-and-upper-proofs'))
        result=self.call('verify',dict(candidate_ref=run['result']['candidate_ref'],verifier_ref=read(self.out/'t04_admit.json')['registry']['profiles'][PROFILE]['verifier_ref'],proof_scope_ref=proof),
            plan_ref=p['plan_ref'],authorization_ref=p['authorization_ref'],idempotency_key='fresh-u03-width-verification')
        v=result['result']['verification']
        if result['reused'] or v['geometric_status']!='PASS' or not all(r['proved'] for r in v['check']['maximum_proofs']):raise ValueError('U03_WIDTH_VERIFICATION_FAILED')
        return self.save('t04_verify',dict(result=result['result'],binding=self.binding,
            facts=dict(run['facts'],passed=True,fresh_reconstruction=True,nominal_pass=True,envelope_pass=True,
                       complete_source_coverage=True,coordinatewise_maximum=True,owner='PENDING_USER')))

    def compare(self):
        saved,report=self.inspection();candidate=read(self.out/'t04_run.json')['result']['candidate'];records=[]
        group_by_route={sid:g['group_id'] for g in report['groups'] for sid in g['members']}
        limits={r['group_id']:r['status'] for r in candidate['solution']['decisions']}
        for c in candidate['construction']:
            for p in c['primitives']:
                sid=p['source_id'];g=from_wkb(self.store.get(candidate['parts'][sid]['nominal_ref'],kind='geometry'));before=from_wkb(self.current[sid])
                records.append(dict(source_id=sid,route_id=c['component_id'],factor=c['factor'],original_width_mm=c['verified_original_width_mm'],candidate_width_mm=c['uniform_nominal_width_mm'],
                    group_id=group_by_route[c['component_id']],disposition='WIDTH_INCREASE' if c['factor']>1 else 'KEEP_AT_ORIGINAL_WIDTH',limit=limits[group_by_route[c['component_id']]],
                    left_sha256=digest(self.current[sid]),right_sha256=digest(to_wkb(g)),added_area_mm2=g.difference(before).area,removed_area_mm2=before.difference(g).area,route_change='NONE'))
        selected={r['source_id'] for r in records}
        dispositions={s:r['disposition'] for r in report['paths'] for s in (r['path']['source_ids'] if 'path' in r else r['source_ids'])}
        for row in report['native_rows']:
            sid=row['source_id']
            if sid not in selected:records.append(dict(source_id=sid,factor=1.,left_sha256=digest(self.current[sid]),right_sha256=digest(self.current[sid]),added_area_mm2=0.,removed_area_mm2=0.,disposition=dispositions[sid],route_change='NONE'))
        ref=store_pages(self.store,records,binding=self.binding,kind='u03-width-comparison')
        rows,index=read_pages(self.store,ref,binding=self.binding,kind='u03-width-comparison',identity=lambda r:r['source_id'])
        if rows!=records or {r['source_id'] for r in rows}!={r['source_id'] for r in report['native_rows']}:raise ValueError('U03_WIDTH_COMPARISON_INCOMPLETE')
        return self.save('t04_compare',dict(pagination_ref=ref,facts=dict(passed=True,trace_occurrences=len(rows),comparison_pages=len(index['pages']),
            added_area_mm2=sum(r['added_area_mm2'] for r in rows),removed_area_mm2=sum(r['removed_area_mm2'] for r in rows),all_paths_unchanged=True)))

    def review(self):
        return self.save('t04_review',dict(records=[],facts=dict(passed=True,owner_status='PENDING_USER',independent_status='NOT_RUN',decision_records=0)))

    def controls(self):
        from src.stage_abi.contracts import StageABIError
        from src.stage_abi.width import WidthAdapter
        saved,report=self.inspection();p=read(self.out/'t04_plan.json');run=read(self.out/'t04_run.json');candidate=run['result']['candidate']
        admitted=read(self.out/'t04_admit.json');scene=validate_scene(self.store,admitted['imported']['scene_ref']);policy=self.store.get_json(p['plan']['policy_ref'],kind='policy')
        controls=[]
        def reject(name,bad,fn):
            fresh(self.out/'controls'/name/'mutation.json',bad)
            try:fn()
            except (ValueError,StageABIError) as error:
                code=error.code if isinstance(error,StageABIError) else str(error).split(':')[0]
                expected={'wrong_predecessor':'U03_WIDTH_PREDECESSOR_CHANGED','duplicate_group':'TRACE_GROUP_PARTITION_INVALID',
                          'missing_route':'TRACE_GROUP_PARTITION_INCOMPLETE' if len(report['groups'])>1 or len(report['groups'][0]['members'])>1 else 'COMPLETE_TRACES_AND_GROUPS_REQUIRED','narrowed_scale':'WIDTH_SCALE_OUT_OF_SCOPE',
                          'changed_native_part':'WIDTH_RECONSTRUCTION_MISMATCH','false_covered':'U03_FALSE_COVERED_PROOF',
                          'unsafe_finite_copper':'U03_WIDTH_CLEARANCE_REJECTED'}[name]
                if code!=expected:raise ValueError('U03_WRONG_CONTROL_REJECTION:'+name+':'+str(error))
                controls.append(dict(name=name,expected=expected,error=code+': '+str(error),status='PASS_EXPECTED_REJECTION'))
            else:raise ValueError('U03_WIDTH_NEGATIVE_NOT_REJECTED:'+name)
        def predecessor(bad):
            if bad!=self.binding:raise ValueError('U03_WIDTH_PREDECESSOR_CHANGED')
        wrong=dict(self.binding,predecessor_scene_ref={})
        reject('wrong_predecessor',wrong,lambda:predecessor(wrong))
        from src.trace_width_stage import validate_width_partition
        chains={r['component_id']:dict(source_ids=r['complete_source_ids']) for r in candidate['construction']}
        groups=copy.deepcopy(p['plan']['details']['groups']);groups[0]['members'].append(groups[0]['members'][0])
        reject('duplicate_group',groups,lambda:validate_width_partition(chains,groups))
        groups2=copy.deepcopy(p['plan']['details']['groups']);groups2[0]['members'].pop()
        # If a singleton becomes empty, preserve a valid nonempty group list
        # and make coverage incomplete by dropping that entire group.
        groups2=[g for g in groups2 if g['members']]
        reject('missing_route',groups2,lambda:validate_width_partition(chains,groups2))
        bad=copy.deepcopy(candidate);bad['solution']['selected_scales'][next(iter(bad['solution']['selected_scales']))]=.99
        reject('narrowed_scale',bad,lambda:WholeBoardWidthAdapter().verify(self.store,scene,policy,p['plan'],bad,dict(scope='complete-source-nominal-envelope-and-upper-proofs'),lambda x:None))
        bad2=copy.deepcopy(candidate);sid=next(iter(bad2['parts']));bad2['parts'][sid]['nominal_ref']=self.store.put('geometry',self.current[sid])
        if bad2['parts'][sid]==candidate['parts'][sid]:bad2['parts'][sid]['nominal_ref']=self.store.put('geometry',b'corrupt-width-control')
        reject('changed_native_part',bad2,lambda:WholeBoardWidthAdapter().verify(self.store,scene,policy,p['plan'],bad2,dict(scope='complete-source-nominal-envelope-and-upper-proofs'),lambda x:None))
        from shapely.ops import unary_union
        chosen=next(r for r in report['paths'] if r['disposition']=='ADMIT_COMPLETE_NATIVE_ROUTE')
        core=unary_union([from_wkb(self.current[s]) for s in chosen['path']['source_ids']])
        cover=unary_union([from_wkb(self.current[s]) for s in chosen['coverage_source_ids']])
        def require_covered():
            if not cover.covers(core):raise ValueError('U03_FALSE_COVERED_PROOF')
        reject('false_covered',dict(source_ids=chosen['path']['source_ids'],core_wkb=to_wkb(core).hex(),cover_wkb=to_wkb(cover).hex(),false_disposition='KEEP_FULLY_COVERED'),require_covered)
        from shapely.geometry import LineString
        from src.prepared_width_scene import PreparedWidthScene
        a=LineString([(0,0),(1,0)]).buffer(.05);b=LineString([(0,.13),(1,.13)]).buffer(.05)
        rows=[dict(id='negative-a',original=a,candidate=a.buffer(.025),verified_original_width_mm=.1),dict(id='negative-b',original=b,candidate=b.buffer(.025),verified_original_width_mm=.1)]
        q=PreparedWidthScene(rows,[]).check(rows)
        def require_clearance():
            if not q['passed']:raise ValueError('U03_WIDTH_CLEARANCE_REJECTED')
        reject('unsafe_finite_copper',dict(source_wkb=[to_wkb(a).hex(),to_wkb(b).hex()],candidate_wkb=[to_wkb(r['candidate']).hex() for r in rows],assessment=q),require_clearance)
        return self.save('t04_controls',dict(controls=controls,facts=dict(passed=True,deliberate_controls=len(controls),all_rejected_for_expected_reason=True)))

    def dispatch(self,op):
        return dict(t04_inspect=self.inspect,t04_admit=self.admit,t04_plan=self.plan,t04_run=self.run,t04_verify=self.verify,t04_compare=self.compare,t04_review=self.review,t04_controls=self.controls)[op]()
