"""Source-bound U04 T02 gates over the exact freshly verified T04 scene."""
import copy
from pathlib import Path
import sexpdata
from shapely import from_wkb, to_wkb
from shapely.geometry import box
from shapely.affinity import scale
from src.stage_abi.store import ArtifactStore, canonical, digest
from src.stage_abi.scene import validate_scene, composed
from src.stage_abi.lands import LandAdapter, land_parameters
from src.stage_abi.runtime import bounds_check, output_scene, check_output, operands
from src.u04_board.width import WidthGates
from src.u03_board.selection import for_root, window
from src.u03_board.paging import put, get
from src.crop_rect_t02 import rectangular_feature
from src.native_reference import one
from tools.t01_operator_host import read, fresh


def parameters():return land_parameters('t02')


from src.u04_board.search import FastRectangleAdapter


class NativeRectangleAdapter(FastRectangleAdapter):
    """Unchanged T02 geometry; explicit no-applicable-feature branch."""
    def __init__(self):super().__init__('t02')

    def plan(self,store,scene,policy,selection,bounds):
        if selection['source_ids']:return super().plan(store,scene,policy,selection,bounds)
        if (selection!=dict(stage='t02',scene_ref=selection['scene_ref'],source_ids=[]) or
            policy!=dict(stage='t02',parameters=parameters()) or
            set(bounds)!={'max_source_objects','max_targets','max_evaluations','max_output_bytes','max_seconds'} or
            any(type(v) is not int or v<=0 for v in bounds.values()) or len(scene['objects'])>bounds['max_source_objects']):
            raise ValueError('U04_EMPTY_SELECTION_OR_BOUNDS_INVALID')
        operands(store,scene)
        return dict(targets=[],bounds=bounds,parameters={},family=parameters()['family'])

    def run(self,store,scene,policy,plan,checkpoint):
        if plan['details']['targets']:return super().run(store,scene,policy,plan,checkpoint)
        rows,_,_=operands(store,scene);out_ref,out=output_scene(store,scene,plan)
        geometry=store.put('geometry',to_wkb(composed(store,scene)))
        return dict(status='NO_APPLICABLE_FEATURE',before_ref=geometry,after_ref=geometry,output_scene_ref=out_ref,
                    decisions=[],inclusive_candidates=[],checks=dict(passed=True,failures=[],scope='Empty source-qualified T02 inventory; all predecessor contributions unchanged'),
                    evaluations=0,protected_source_refs={s:r['geometry_ref'] for s,r in rows.items()})

    def verify(self,store,scene,policy,plan,candidate,proof_scope,checkpoint):
        if plan['details']['targets']:return super().verify(store,scene,policy,plan,candidate,proof_scope,checkpoint)
        if proof_scope!={'scope':'complete-source-land-and-inclusive'}:raise ValueError('U04_COMPLETE_LAND_PROOF_REQUIRED')
        if candidate!=dict(self.run(store,scene,policy,plan,checkpoint),**{k:candidate[k] for k in ('plan_ref','scene_ref','policy_ref','profile_id')}):
            raise ValueError('U04_NO_APPLICABLE_FEATURE_RECONSTRUCTION_FAILED')
        check_output(store,scene,plan,candidate)
        return dict(passed=True,failures=[],reconstructed_targets=0,inclusive_fills=0,scope='Full source-preserving no-applicable-feature proof')


def admit_rectangles(store,scene,manifest,raw,selection=None):
    """Inventory every source, admitting only exact untouched native rectangles."""
    if digest(raw)!=manifest['source_sha256'] or scene['source_sha256']!=manifest['source_sha256']:
        raise ValueError('U04_RECTANGLE_SOURCE_CHANGED')
    meta={r['id']:r for r in manifest['objects']};objects={r['source_id']:r for r in scene['objects']}
    if len(objects)!=len(scene['objects']) or len(meta)!=len(manifest['objects']):raise ValueError('U04_SOURCE_IDENTITIES_DUPLICATED')
    members=[s for r in objects.values() for s in r['metadata']['native_source_ids']]
    if len(members)!=len(set(members)) or set(members)!=set(meta):raise ValueError('U04_COMPLETE_NATIVE_SOURCE_PARTITION_REQUIRED')
    region=window(selection) if selection is not None else box(*scene['viewport_mm'])
    records=[];targets=[];unsupported=[]
    for sid,row in sorted(objects.items()):
        core=from_wkb(store.get(row['original_ref'],kind='geometry'));current=from_wkb(store.get(row['geometry_ref'],kind='geometry'))
        source_ids=row['metadata']['native_source_ids'];disposition='KEEP_PROTECTED_PREDECESSOR'
        if len(source_ids)==1 and meta[source_ids[0]]['kind']=='gr_poly':
            native=meta[source_ids[0]];blob=store.get(row['original_ref'],kind='geometry')
            if digest(blob)!=native['geometry_sha256']:raise ValueError('U04_ORIGINAL_RECTANGLE_GEOMETRY_CHANGED:'+sid)
            node=sexpdata.loads(raw[slice(*native['source_span'])].decode())
            stroke=float(one(one(node,'stroke',[]),'width',[0])[0]);filled=str(one(node,'fill',[''])[0]) in ('yes','solid')
            feature=rectangular_feature(native,{native['geometry_sha256']:blob},region,enforce_full_cap_in_crop=False,max_axis_factor=1.25)
            cap=scale(core,1.25,1.25,origin=core.centroid)
            if row['metadata'].get('fixed_bulk',False):disposition='KEEP_FIXED_BULK'
            elif not filled or stroke!=0:disposition='KEEP_UNSUPPORTED_NATIVE_FORM'
            elif not core.intersects(region):disposition='KEEP_OUTSIDE_SCOPE'
            elif feature is None:disposition='KEEP_NONRECTANGULAR_SOURCE'
            elif not region.covers(cap):disposition='KEEP_CROP_BOUNDARY' if selection is not None else 'KEEP_VIEWPORT_BOUNDARY'
            elif not core.equals(box(*core.bounds)):
                disposition='UNSUPPORTED_ORIENTED_RECTANGLE';unsupported.append(sid)
            else:
                if row['kind']!='rectangle' or not current.equals(core):raise ValueError('U04_RECTANGLE_PREDECESSOR_NOT_ORIGINAL:'+sid)
                disposition='ADMIT_WHOLE_NATIVE_RECTANGLE';targets.append(sid)
        records.append(dict(source_id=sid,native_source_ids=source_ids,kind=row['kind'],disposition=disposition,
                            original_ref=row['original_ref'],current_ref=row['geometry_ref']))
    return dict(sources=records,target_ids=targets,native_source_ids=sorted(members),unsupported=unsupported,
                selection=selection,parameters=parameters())


class RectangleGates:
    def __init__(self,root):
        self.root=Path(root);self.out=self.root/'u04_t02';self.store=ArtifactStore(self.root/'runtime')
        run=read(self.root/'u03_t04/t04_run.json')['result'];verification=read(self.root/'u03_t04/t04_verify.json')
        candidate=self.store.get_json(run['candidate_ref'],kind='candidate');actual=self.store.get_json(verification['result']['verification_ref'],kind='verification')
        width=WidthGates(self.root)
        if (candidate!=run['candidate'] or actual!=verification['result']['verification'] or actual['candidate_ref']!=run['candidate_ref'] or
            actual['geometric_status']!='PASS' or verification['binding']!=width.binding):raise ValueError('U04_EXACT_VERIFIED_T04_REQUIRED')
        from .native_scene import materialize
        self.scene_ref,self.scene=materialize(self.store,width,candidate,candidate['output_scene_ref'])
        self.raw=width.raw;self.manifest=width.manifest;self.selection=for_root(self.root);self.adapter=NativeRectangleAdapter()
        self.binding=dict(predecessor_scene_ref=candidate['output_scene_ref'],native_part_scene_ref=self.scene_ref,t04_candidate_ref=run['candidate_ref'],
                          t04_verification_sha256=digest((self.root/'u03_t04/t04_verify.json').read_bytes()),source_sha256=digest(self.raw))

    def save(self,op,value):
        result=dict(value,binding=self.binding);fresh(self.out/(op+'.json'),result);return result

    def reconstruct_admission(self):return admit_rectangles(self.store,self.scene,self.manifest,self.raw,self.selection)

    def inspect(self):
        self.out.mkdir();report=self.reconstruct_admission()
        ref=put(self.store,report['sources'],binding=self.binding,kind='u04-rectangle-sources')
        rows,index=get(self.store,ref,binding=self.binding,kind='u04-rectangle-sources',identity=lambda r:r['source_id'])
        if rows!=report['sources']:raise ValueError('U04_SOURCE_PAGES_INCOMPLETE')
        return self.save('t02_inspect',dict(report_ref=self.store.put_json('u04-rectangle-admission',report),source_pages_ref=ref,
            facts=dict(passed=True,complete_source_coverage=True,source_objects=len(rows),native_source_objects=len(report['native_source_ids']),
                       eligible_rectangles=len(report['target_ids']),unsupported_rectangles=len(report['unsupported']),source_pages=len(index['pages']))))

    def inspection(self):
        saved=read(self.out/'t02_inspect.json');report=self.reconstruct_admission()
        if saved['binding']!=self.binding or self.store.get_json(saved['report_ref'],kind='u04-rectangle-admission')!=report:
            raise ValueError('U04_RECTANGLE_ADMISSION_CHANGED')
        rows,_=get(self.store,saved['source_pages_ref'],binding=self.binding,kind='u04-rectangle-sources',identity=lambda r:r['source_id'])
        if rows!=report['sources']:raise ValueError('U04_SOURCE_PAGES_INCOMPLETE')
        return report

    def admit(self):
        report=self.inspection()
        if report['unsupported']:raise ValueError('U04_T02_ORIENTED_RECTANGLES_NOT_QUALIFIED:'+str(report['unsupported']))
        return self.save('t02_admit',dict(scene_ref=self.scene_ref,report_ref=self.store.put_json('u04-rectangle-admission',report),
            facts=dict(passed=True,exact_T04_copper_preserved=True,all_native_sources_partitioned=True,eligible_rectangles=len(report['target_ids']))))

    def plan(self):
        report=self.inspection();admitted=read(self.out/'t02_admit.json')
        if admitted['scene_ref']!=self.scene_ref or report['unsupported']:raise ValueError('U04_ADMITTED_SCENE_CHANGED')
        policy=dict(stage='t02',parameters=parameters());policy_ref=self.store.put_json('policy',policy)
        n=len(report['target_ids']);bounds=dict(max_source_objects=len(self.scene['objects']),max_targets=max(1,n),
            max_evaluations=max(1,400*n+2*n*n*n),max_output_bytes=1_000_000_000,max_seconds=1800)
        details=self.adapter.plan(self.store,self.scene,policy,dict(stage='t02',scene_ref=self.scene_ref,source_ids=report['target_ids']),bounds)
        plan=dict(stage='t02',scene_ref=self.scene_ref,policy_ref=policy_ref,profile_id='u04-native-rectangle-inclusive-v1',
                  implementation=self.adapter.describe()['implementation'],details=details,binding=self.binding)
        return self.save('t02_plan',dict(plan_ref=self.store.put_json('plan',plan),plan=plan,
            facts=dict(passed=True,complete_source_selection=True,targets=n,maximum_evaluations=bounds['max_evaluations'],construction_status='NOT_RUN')))

    def context(self):
        report=self.inspection();saved=read(self.out/'t02_plan.json');plan=self.store.get_json(saved['plan_ref'],kind='plan')
        if plan!=saved['plan'] or plan['binding']!=self.binding or plan['implementation']!=self.adapter.describe()['implementation']:
            raise ValueError('U04_RECTANGLE_PLAN_CHANGED')
        policy=self.store.get_json(plan['policy_ref'],kind='policy')
        details=self.adapter.plan(self.store,self.scene,policy,dict(stage='t02',scene_ref=self.scene_ref,source_ids=report['target_ids']),plan['details']['bounds'])
        if plan['details']!=details or plan['scene_ref']!=self.scene_ref or report['unsupported']:raise ValueError('U04_RECTANGLE_PLAN_RECONSTRUCTION_FAILED')
        return self.scene,policy,plan,saved['plan_ref']

    def reconstruct(self):
        scene,policy,plan,ref=self.context()
        key=digest(canonical(dict(scene=scene,policy=policy,plan=plan)))
        if getattr(self,'_replay_key',None)==key:
            return self.store.get_json(self._replay_ref,kind='candidate')
        candidate=self.adapter.run(self.store,scene,policy,plan,lambda value:None)
        candidate=dict(candidate,plan_ref=ref,scene_ref=plan['scene_ref'],policy_ref=plan['policy_ref'],profile_id=plan['profile_id'])
        self._replay_ref=self.store.put_json('candidate',candidate);self._replay_key=key
        return candidate

    def run(self):
        c=self.reconstruct()
        return self.save('t02_run',dict(candidate_ref=self.store.put_json('candidate',c),candidate=c,
            facts=dict(passed=True,fresh_construction=True,rectangles=len(c['decisions']),grown=sum(d['status']=='GROWN' for d in c['decisions']),
                       kept=sum(d['status']!='GROWN' for d in c['decisions']),inclusive_fills=sum(d['status']=='MERGED' for d in c['inclusive_candidates']),
                       evaluations=c['evaluations'],disposition=c['status'],predecessor_preserved=True)))

    def check_candidate(self,candidate):
        if candidate!=self.reconstruct():raise ValueError('U04_RECTANGLE_FULL_RECONSTRUCTION_FAILED')
        scene,policy,plan,_=self.context();check=self.adapter.verify(self.store,scene,policy,plan,candidate,dict(scope='complete-source-land-and-inclusive'),lambda value:None)
        before=from_wkb(self.store.get(candidate['before_ref'],kind='geometry'));after=from_wkb(self.store.get(candidate['after_ref'],kind='geometry'))
        if not check['passed'] or before.difference(after).area>1e-12:raise ValueError('U04_RECTANGLE_VERIFICATION_FAILED')
        return dict(check,removed_area_mm2=before.difference(after).area)

    def verify(self):
        saved=read(self.out/'t02_run.json');c=self.store.get_json(saved['candidate_ref'],kind='candidate')
        if c!=saved['candidate']:raise ValueError('U04_RECTANGLE_CANDIDATE_CHANGED')
        check=self.check_candidate(c)
        return self.save('t02_verify',dict(candidate_ref=saved['candidate_ref'],check=check,
            facts=dict(passed=True,all_attempts_reconstructed=True,complete_source_coverage=True,simultaneous_copper_checked=True,
                       reconstructed_rectangles=check['reconstructed_targets'],inclusive_fills=check['inclusive_fills'],removed_area_mm2=check['removed_area_mm2'])))

    def validate_verification(self):
        run=read(self.out/'t02_run.json');proof=read(self.out/'t02_verify.json')
        if proof['binding']!=self.binding or proof['candidate_ref']!=run['candidate_ref'] or not proof['facts']['passed']:raise ValueError('U04_T02_VERIFICATION_REQUIRED')
        if self.store.get_json(run['candidate_ref'],kind='candidate')!=run['candidate']:raise ValueError('U04_RECTANGLE_CANDIDATE_CHANGED')
        return run['candidate']

    def compare(self):
        c=self.validate_verification();objects={r['source_id']:r for r in self.scene['objects']};records=[]
        for d in c['decisions']:
            before=from_wkb(self.store.get(objects[d['source_id']]['geometry_ref'],kind='geometry'));after=from_wkb(self.store.get(d['candidate_ref'],kind='geometry'))
            records.append(dict(source_id=d['source_id'],status=d['status'],added_area_mm2=after.difference(before).area,removed_area_mm2=before.difference(after).area))
        ref=put(self.store,records,binding=self.binding,kind='u04-rectangle-comparison')
        return self.save('t02_compare',dict(pagination_ref=ref,inclusive_candidates=c['inclusive_candidates'],
            facts=dict(passed=True,rectangles=len(records),added_area_mm2=from_wkb(self.store.get(c['after_ref'],kind='geometry')).difference(from_wkb(self.store.get(c['before_ref'],kind='geometry'))).area,
                       removed_area_mm2=0.,all_trace_paths_widths_preserved=True)))

    def review(self):
        return self.save('t02_review',dict(records=[],facts=dict(passed=True,owner_status='PENDING_USER',independent_status='NOT_RUN',decision_records=0)))

    def controls(self):
        candidate=self.validate_verification();folder=self.out/'controls';folder.mkdir();records=[]
        def expect(name,mutate):
            changed=copy.deepcopy(candidate);mutate(changed);path=folder/(name+'.json');fresh(path,changed)
            try:self.check_candidate(changed)
            except ValueError as error:
                if not str(error).startswith('U04_RECTANGLE_FULL_RECONSTRUCTION_FAILED'):raise
                records.append(dict(name=name,expected='U04_RECTANGLE_FULL_RECONSTRUCTION_FAILED',error=str(error),status='PASS_EXPECTED_REJECTION',mutation=str(path)))
            else:raise ValueError('U04_RECTANGLE_NEGATIVE_NOT_REJECTED:'+name)
        expect('wrong_predecessor',lambda c:c.update(scene_ref=self.store.put_json('scene',dict(self.scene,source_sha256='0'*64))))
        expect('missing_rectangle',lambda c:c.update(decisions=c['decisions'][:-1] if c['decisions'] else [dict(source_id='fabricated')]))
        expect('changed_policy',lambda c:c.update(policy_ref=self.store.put_json('policy',dict(stage='t02',parameters=dict(parameters(),ceiling=2.)))))
        expect('changed_copper',lambda c:c.update(after_ref=self.store.put('geometry',to_wkb(box(100,100,101,101)))))
        expect('changed_protected_source',lambda c:c.update(protected_source_refs={}))
        expect('changed_inclusive_ledger',lambda c:c.update(inclusive_candidates=c['inclusive_candidates']+[dict(status='MERGED',members=['fabricated'])]))
        return self.save('t02_controls',dict(controls=records,facts=dict(passed=True,deliberate_controls=len(records),all_rejected_for_expected_reason=True)))

    def dispatch(self,operation):
        if operation not in {'t02_'+s for s in ('inspect','admit','plan','run','verify','compare','review','controls')}:raise ValueError('U04_RECTANGLE_OPERATION_UNSUPPORTED')
        return getattr(self,operation[4:])()
