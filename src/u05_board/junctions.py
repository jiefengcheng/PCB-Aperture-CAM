"""U05 source-bound T05 admission, bounded construction and exact replay."""
import copy
from dataclasses import asdict
from pathlib import Path
from shapely import from_wkb,to_wkb,STRtree
from shapely.geometry import box
from shapely.ops import unary_union
from src.stage_abi.store import canonical,digest
from src.stage_abi.scene import composed
from src.stage_abi.spindle import SpindleAdapter,filled_circle
from src.junction_spindle_stage import CONTRACT
from src.u04_board.search import FastRectangleAdapter
from src.u03_board.selection import for_root
from src.u03_board.paging import put,get
from tools.t01_operator_host import read,fresh
from .store import OverlayStore
from .custody import session


def parameters():return dict(asdict(CONTRACT),radius_scales=list(CONTRACT.radius_scales))

def make_gates(root,evidence=None):
    if session(root).get('reference'):
        from .attachment_gates import AttachmentGates
        return AttachmentGates(root,evidence)
    return JunctionGates(root,evidence)

class NativeSpindleAdapter(SpindleAdapter):
    def describe(self):
        value=super().describe();value['implementation']=digest(canonical(value)+Path(__file__).read_bytes()+Path(__file__).with_name('scene.py').read_bytes());return value
    def _context(self,store,scene,policy,details):
        key=(id(store),digest(canonical(dict(scene=scene,policy=policy))))
        if getattr(self,'_source_key',None)==key:
            references={r[field]['artifact_id']:r[field] for r in scene['objects'] for field in ('geometry_ref','original_ref')}
            for reference in references.values():store.get(reference,kind='geometry')
            return self._source_context
        value=super()._context(store,scene,policy,details);self._source_context=value;self._source_key=key;return value
    def plan(self,store,scene,policy,selection,bounds):
        if set(selection)!={'stage','scene_ref','source_ids'} or selection['stage']!='t05' or set(bounds)!={'max_source_objects','max_targets','max_evaluations','max_output_bytes','max_seconds'} or any(type(v) is not int or v<=0 for v in bounds.values()):raise ValueError('U05_SELECTION_OR_BOUNDS_INVALID')
        ids=selection['source_ids']
        if type(ids) is not list or len(ids)!=len(set(ids)) or len(ids)>bounds['max_targets'] or len(scene['objects'])>bounds['max_source_objects']:raise ValueError('U05_SELECTION_COVERAGE_INVALID')
        objects,current,original,crop=self._context(store,scene,policy,None);ordered=list(current);tree=STRtree([current[s] for s in ordered]);original_tree=STRtree([original[s] for s in ordered]);routes=[];covered_cache={}
        for sid in sorted(ids):
            if sid not in objects or objects[sid]['kind']!='trace':raise ValueError('U05_NATIVE_TRACE_REQUIRED')
            declared=objects[sid]['metadata'].get('land_ids')
            if type(declared) is not list or len(declared)!=len(set(declared)):raise ValueError('U05_EXPLICIT_SOURCE_CONTACTS_REQUIRED')
            lands=[];skipped=[]
            for lid in declared:
                if lid not in objects or not objects[lid]['metadata'].get('qualified_land') or objects[lid]['kind'] not in ('circle','rectangle','inclusive_rectangle'):raise ValueError('U05_UNQUALIFIED_LAND')
                core=original[lid];g=current[lid]
                if original[sid].intersection(core).area<=1e-12 or current[sid].intersection(g).area<=1e-12:raise ValueError('U05_ORIGINAL_CONTACT_NOT_ESTABLISHED')
                if objects[lid]['kind']=='circle' and not filled_circle(core):raise ValueError('U05_UNSUPPORTED_FILLED_CIRCLE')
                if objects[lid]['kind'] in ('rectangle','inclusive_rectangle') and not g.equals(box(*g.bounds)):raise ValueError('U05_UNSUPPORTED_RECTANGLE')
                for oi in original_tree.query(core.envelope):
                    other=ordered[int(oi)]
                    if other!=lid and core.equals(original[other]) and not g.equals(current[other]):raise ValueError('U05_LAND_ALIAS_CONFLICT')
                aliases=set(objects[lid]['metadata']['alias_source_ids'])
                if any(not original[a].equals(core) or not current[a].equals(g) for a in aliases):raise ValueError('U05_LAND_ALIAS_CHANGED')
                if lid not in covered_cache:covered_cache[lid]=FastRectangleAdapter.covered(g,lid,current,ordered,tree,aliases)
                (skipped if covered_cache[lid] else lands).append(lid)
            routes.append(dict(source_id=sid,land_ids=lands,covered_lands=skipped))
        return dict(routes=routes,bounds=bounds,protected_source_ids=sorted(objects),family=CONTRACT.family)

class JunctionGates:
    def __init__(self,root,evidence=None):
        self.root=Path(root);start=session(self.root);self.predecessor=start['predecessor'];old=Path(self.predecessor['root'])
        self.out=self.root/'u05_t05';self.store=OverlayStore(self.root/'runtime',old/'runtime',evidence)
        from .scene import prepare
        self.scene,self.native_facts=prepare(self.store,self.predecessor);self.scene_ref=self.store.put_json('scene',self.scene)
        self.native_ids=sorted(r['id'] for r in read(old/'data_board/source_manifest.json')['objects']);self.selection=for_root(old);self.adapter=NativeSpindleAdapter()
        self.binding=dict(retained_U04_receipt_sha256=self.predecessor['receipt_sha256'],retained_U04_scene_ref=self.predecessor['scene_ref'],actual_native_U04_sha256=self.predecessor['kicad_sha256'],actual_native_scene_ref=self.scene_ref,source_sha256=self.scene['source_sha256'])

    def save(self,op,value):
        result=dict(value,binding=self.binding);fresh(self.out/(op+'.json'),result);return result

    def reconstruct_admission(self):
        from .scene import admit
        scene,report=admit(self.store,self.scene,self.selection)
        if report['native_source_ids']!=self.native_ids:raise ValueError('U05_COMPLETE_NATIVE_SOURCE_COVERAGE_REQUIRED')
        return scene,report

    def inspect(self):
        self.out.mkdir()
        scene,report=self.reconstruct_admission()
        pages=put(self.store,report['routes'],binding=self.binding,kind='u05-junction-contacts')
        rows,index=get(self.store,pages,binding=self.binding,kind='u05-junction-contacts',identity=lambda r:r['source_id'])
        if rows!=report['routes']:raise ValueError('U05_CONTACT_PAGES_INCOMPLETE')
        return self.save('t05_inspect',dict(report_ref=self.store.put_json('u05-junction-admission',report),contact_pages_ref=pages,
            facts=dict(passed=True,complete_source_coverage=True,source_objects=len(report['source_ids']),native_source_objects=len(report['native_source_ids']),
                       source_routes=len(rows),eligible_routes=len(report['target_ids']),contact_pages=len(index['pages']),source_contacts=sum(len(r['land_ids']) for r in rows))))

    def inspection(self):
        saved=read(self.out/'t05_inspect.json');scene,report=self.reconstruct_admission()
        if saved['binding']!=self.binding or self.store.get_json(saved['report_ref'],kind='u05-junction-admission')!=report:
            raise ValueError('U05_JUNCTION_ADMISSION_CHANGED')
        rows,_=get(self.store,saved['contact_pages_ref'],binding=self.binding,kind='u05-junction-contacts',identity=lambda r:r['source_id'])
        if rows!=report['routes']:raise ValueError('U05_CONTACT_PAGES_INCOMPLETE')
        return scene,report

    def admit(self):
        scene,report=self.inspection();ref=self.store.put_json('scene',scene)
        if composed(self.store,scene).symmetric_difference(composed(self.store,self.scene)).area>1e-12:
            raise ValueError('U05_U04_COPPER_CHANGED_AT_ADMISSION')
        return self.save('t05_admit',dict(scene_ref=ref,report_ref=self.store.put_json('u05-junction-admission',report),
            facts=dict(passed=True,exact_U04_copper_preserved=True,all_native_sources_partitioned=True,eligible_routes=len(report['target_ids']))))

    def plan(self):
        scene,report=self.inspection();admitted=read(self.out/'t05_admit.json')
        if self.store.get_json(admitted['scene_ref'],kind='scene')!=scene:raise ValueError('U05_ADMITTED_SCENE_CHANGED')
        policy=dict(stage='t05',parameters=parameters());policy_ref=self.store.put_json('policy',policy)
        bounds=dict(max_source_objects=len(scene['objects']),max_targets=max(1,len(report['target_ids'])),max_evaluations=max(1,4*len(report['target_ids'])),max_output_bytes=1_000_000_000,max_seconds=1800)
        details=self.adapter.plan(self.store,scene,policy,dict(stage='t05',scene_ref=admitted['scene_ref'],source_ids=report['target_ids']),bounds)
        plan=dict(stage='t05',scene_ref=admitted['scene_ref'],policy_ref=policy_ref,profile_id='u05-native-spindle-v1',
                  implementation=self.adapter.describe()['implementation'],details=details,binding=self.binding)
        return self.save('t05_plan',dict(plan_ref=self.store.put_json('plan',plan),plan=plan,
            facts=dict(passed=True,complete_contact_selection=True,targets=len(details['routes']),maximum_radius_attempts=4*len(details['routes']),construction_status='NOT_RUN')))

    def context_inputs(self):
        return digest(canonical(dict(scene=self.scene,selection=self.selection,binding=self.binding,
            implementation=self.adapter.describe()['implementation'],parameters=parameters(),
            receipts={n:digest((self.out/(n+'.json')).read_bytes()) for n in ('t05_inspect','t05_admit','t05_plan')})))

    def context(self):
        key=self.context_inputs()
        if getattr(self,'_context_key',None)==key:
            self.store.verify_reads()
            if digest(canonical(list(self._context_value)))!=self._context_value_sha:raise ValueError('U05_CONTEXT_CACHE_MUTATED')
            return copy.deepcopy(self._context_value)
        scene,report=self.inspection();saved=read(self.out/'t05_plan.json');plan=self.store.get_json(saved['plan_ref'],kind='plan')
        if plan!=saved['plan'] or plan['binding']!=self.binding or plan['implementation']!=self.adapter.describe()['implementation']:
            raise ValueError('U05_JUNCTION_PLAN_CHANGED')
        policy=self.store.get_json(plan['policy_ref'],kind='policy')
        details=self.adapter.plan(self.store,scene,policy,dict(stage='t05',scene_ref=plan['scene_ref'],source_ids=report['target_ids']),plan['details']['bounds'])
        if plan['details']!=details or self.store.get_json(plan['scene_ref'],kind='scene')!=scene:
            raise ValueError('U05_JUNCTION_PLAN_RECONSTRUCTION_FAILED')
        if key!=self.context_inputs():raise ValueError('U05_CONTEXT_INPUT_CHANGED_DURING_RECONSTRUCTION')
        value=(scene,policy,plan,saved['plan_ref']);self._context_key=key;self._context_value=copy.deepcopy(value);self._context_value_sha=digest(canonical(list(value)))
        return value

    def reconstruct(self):
        scene,policy,plan,ref=self.context()
        key=digest(canonical(dict(scene=scene,policy=policy,plan=plan)))
        if getattr(self,'_replay_key',None)==key:return self.store.get_json(self._replay_ref,kind='candidate')
        candidate=self.adapter.run(self.store,scene,policy,plan,lambda value:None)
        candidate=dict(candidate,plan_ref=ref,scene_ref=plan['scene_ref'],policy_ref=plan['policy_ref'],profile_id=plan['profile_id'])
        self._replay_ref=self.store.put_json('candidate',candidate);self._replay_key=key
        return candidate

    def run(self):
        candidate=self.reconstruct()
        return self.save('t05_run',dict(candidate_ref=self.store.put_json('candidate',candidate),candidate=candidate,
            facts=dict(passed=True,fresh_construction=True,source_routes=len(candidate['decisions']),grown=sum(d['status']=='GROWN' for d in candidate['decisions']),
                       kept=sum(d['status']=='KEEP' for d in candidate['decisions']),radius_evaluations=candidate['evaluations'],predecessor_preserved=True)))

    def check_candidate(self,candidate):
        # Re-run every bounded attempt, including KEEP decisions. A saved KEEP
        # cannot suppress a feasible patch or forge source coverage.
        if candidate!=self.reconstruct():raise ValueError('U05_JUNCTION_FULL_RECONSTRUCTION_FAILED')
        scene,policy,plan,_=self.context()
        check=self.adapter.verify(self.store,scene,policy,plan,candidate,dict(scope='complete-source-and-all-patches'),lambda value:None)
        if not check['passed'] or check['removed_area_mm2']>1e-12:raise ValueError('U05_JUNCTION_VERIFICATION_FAILED')
        return check

    def verify(self):
        saved=read(self.out/'t05_run.json');candidate=self.store.get_json(saved['candidate_ref'],kind='candidate')
        if candidate!=saved['candidate']:raise ValueError('U05_JUNCTION_CANDIDATE_CHANGED')
        check=self.check_candidate(candidate)
        return self.save('t05_verify',dict(candidate_ref=saved['candidate_ref'],check=check,
            facts=dict(passed=True,all_attempts_reconstructed=True,complete_source_coverage=True,all_final_patches_checked=True,
                       reconstructed_patches=check['reconstructed_patches'],removed_area_mm2=check['removed_area_mm2'])))

    def validate_verification(self):
        run=read(self.out/'t05_run.json');proof=read(self.out/'t05_verify.json')
        if proof['binding']!=self.binding or proof['candidate_ref']!=run['candidate_ref'] or not proof['facts']['passed']:
            raise ValueError('U05_T05_VERIFICATION_REQUIRED')
        if self.store.get_json(run['candidate_ref'],kind='candidate')!=run['candidate']:
            raise ValueError('U05_JUNCTION_CANDIDATE_CHANGED')
        return run['candidate']

    def compare(self):
        c=self.validate_verification();records=[]
        for d in c['decisions']:
            patch=from_wkb(self.store.get(d['patch_ref'],kind='geometry')) if d['status']=='GROWN' else None
            records.append(dict(source_id=d['source_id'],status=d['status'],land_ids=d['land_ids'],covered_lands=d['covered_lands'],
                                added_area_mm2=0. if patch is None else patch.area,removed_area_mm2=0.))
        ref=put(self.store,records,binding=self.binding,kind='u05-junction-comparison')
        return self.save('t05_compare',dict(pagination_ref=ref,facts=dict(passed=True,source_routes=len(records),added_area_mm2=sum(r['added_area_mm2'] for r in records),removed_area_mm2=0.)))

    def review(self):
        return self.save('t05_review',dict(records=[],facts=dict(passed=True,owner_status='PENDING_USER',independent_status='NOT_RUN',decision_records=0)))

    def controls(self):
        candidate=self.validate_verification();folder=self.out/'controls';folder.mkdir();records=[]
        def expect(name,mutate):
            changed=copy.deepcopy(candidate);mutate(changed);path=folder/(name+'.json');fresh(path,changed)
            try:self.check_candidate(changed)
            except ValueError as error:
                if not str(error).startswith('U05_JUNCTION_FULL_RECONSTRUCTION_FAILED'):raise
                records.append(dict(name=name,expected='U05_JUNCTION_FULL_RECONSTRUCTION_FAILED',error=str(error),status='PASS_EXPECTED_REJECTION',mutation=str(path)))
            else:raise ValueError('U05_JUNCTION_NEGATIVE_NOT_REJECTED:'+name)
        expect('wrong_predecessor',lambda c:c.update(scene_ref=self.store.put_json('scene',dict(self.scene,source_sha256='0'*64))))
        expect('missing_route',lambda c:c.update(decisions=c['decisions'][:-1] if c['decisions'] else [dict(source_id='fabricated')]))
        expect('changed_policy',lambda c:c.update(policy_ref=self.store.put_json('policy',dict(stage='t05',parameters=dict(parameters(),hard_gap_mm=.001)))))
        expect('changed_patch',lambda c:c.update(after_ref=self.store.put('geometry',to_wkb(box(100,100,101,101)))))
        expect('changed_protected_source',lambda c:c.update(protected_source_refs={}))
        for name,mutation in getattr(self,'extra_controls',lambda:[])():expect(name,mutation)
        return self.save('t05_controls',dict(controls=records,facts=dict(passed=True,deliberate_controls=len(records),all_rejected_for_expected_reason=True)))

    def dispatch(self,operation):
        if operation not in {'t05_'+s for s in ('inspect','admit','plan','run','verify','compare','review','controls')}:
            raise ValueError('U05_JUNCTION_OPERATION_UNSUPPORTED')
        return getattr(self,operation[4:])()
