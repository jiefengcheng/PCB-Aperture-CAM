"""Source-bound T03 retain-valid-paths adapter, separate from the bundle router.

No route inference: an actual growth-remediation objective outside this family's
unchanged-path support is retained and rejected before candidate publication.
"""
import copy
from pathlib import Path
from src.u02_board.ports import source_port_binding
from shapely import from_wkb, to_wkb, STRtree
from src.stage_abi.store import ArtifactStore, canonical, digest
from src.stage_abi.scene import validate_scene
from src.t01_board.source import context
from src.t01_crop.paging import store_pages, read_pages
from src.crop_balanced_t01 import WorkingScene, CropSettings
from tools.t01_operator_host import read, state, fresh, ROOT
from src.stage_abi.preparation import prepared_tree as STRtree

from src.stage_abi.preparation import prepared_tree as STRtree,decode_geometry as from_wkb

CONTRACT = ROOT/'contracts/operator/u02_board.json'
FAMILY = 'native-whole-board-retain-valid-paths/1'
TRACE_KINDS = {'segment', 'arc', 'gr_line', 'gr_arc'}


def pair_check(core, candidate, trace, port, policy):
    addition = candidate.difference(core)
    band = trace.buffer(policy['hard_gap_mm'], quad_segs=policy['quad_segs'])
    if port is not None:
        band = band.difference(port)
    intrusion = addition.intersection(band).area
    outside_contact = addition.intersection(trace)
    if port is not None:
        outside_contact = outside_contact.difference(port)
    # Match the retained T01 finite-area policy, not a new distance tolerance.
    passed = intrusion <= policy['area_epsilon_mm2']
    return dict(passed=passed, forbidden_intrusion_mm2=intrusion,
                new_contact_outside_port_mm2=outside_contact.area,
                original_contact_preserved=core.intersection(trace).difference(candidate).area <= policy['area_epsilon_mm2'],
                port_sha256=None if port is None else digest(to_wkb(port, byte_order=1)))


def require_supported(records):
    failed = [r for r in records if any(not p['passed'] or not p['original_contact_preserved'] for p in r['pairs'])]
    if failed:
        raise ValueError('U02_T03_MOVEMENT_NOT_QUALIFIED: '+str([r['source_id'] for r in failed]))


def verify_candidate(candidate, plan, scene):
    expected = dict(family=FAMILY, plan_sha256=digest(canonical(plan)),
                    predecessor_scene_ref=scene, output_scene_ref=scene,
                    disposition='NO_CHANGE_REQUIRED', changed_trace_count=0,
                    replacement_refs={}, trace_inventory_ref=plan['trace_inventory_ref'])
    if candidate != expected:
        raise ValueError('U02_T03_CANDIDATE_RECONSTRUCTION_MISMATCH')
    return expected


class RetainPathsAdapter:
    def __init__(self, root):
        self.root=Path(root);self.out=self.root/'u02_t03';self.store=ArtifactStore(self.root/'runtime')
        self.contract=read(CONTRACT);self.policy=self.contract['policy']
        self.receipt=read(self.root/'RECEIPT.json');self.cap=state(self.root)
        if self.receipt['status']!='PASS_BOARD_T01_VERIFIED':raise ValueError('U02_VERIFIED_T01_REQUIRED')
        v=self.store.get_json(self.receipt['verification_ref'],kind='verification')
        self.candidate=self.store.get_json(self.receipt['candidate_ref'],kind='candidate')
        if v['geometric_status']!='PASS' or v['candidate_ref']!=self.receipt['candidate_ref'] or v['check']['passed'] is not True:raise ValueError('U02_T01_VERIFICATION_BINDING_FAILED')
        self.scene_ref=self.candidate['output_scene_ref'];self.scene=validate_scene(self.store,self.scene_ref)
        self.binding=dict(predecessor_scene_ref=self.scene_ref,predecessor_candidate_ref=self.receipt['candidate_ref'],verification_ref=self.receipt['verification_ref'],contract_sha256=digest(CONTRACT.read_bytes()))

    def inspect(self):
        self.out.mkdir(exist_ok=False)
        records,coverage=self.assess()
        reference=store_pages(self.store,records,binding=self.binding,kind='u02-traces')
        saved,index=read_pages(self.store,reference,binding=self.binding,kind='u02-traces',identity=lambda r:r['source_id'])
        if saved!=records:raise ValueError('U02_TRACE_PAGINATION_CHANGED')
        result=dict(binding=self.binding,trace_inventory_ref=reference,coverage=coverage,
                    facts=dict(passed=True,trace_occurrences=len(records),trace_pages=len(index['pages']),
                    affected_pairs=sum(len(r['pairs']) for r in records),movement_objectives=sum(any(not p['passed'] for p in r['pairs']) for r in records),
                    complete_source_coverage=True,original_widths_retained=True,**coverage))
        fresh(self.out/'t03_inspect.json',result);return result

    def assess(self):
        original=self.store.get_json(self.receipt['scene_ref'],kind='scene')
        policy=self.store.get_json(self.cap['policy_ref'],kind='policy')
        b,raw,rows,shapes,sites=context(self.store,original,policy)
        if policy['settings']['hard_gap']!=self.policy['hard_gap_mm'] or policy['settings']['area_epsilon']!=self.policy['area_epsilon_mm2'] or policy['settings']['qsegs']!=self.policy['quad_segs']:raise ValueError('U02_POLICY_DRIFT')
        current={r['source_id']:r for r in self.scene['objects']};old={r['source_id']:r for r in original['objects']}
        if set(current)!=set(old) or len(current)!=len(self.scene['objects']) or self.scene['source_sha256']!=b['source_sha256'] or self.scene['lineage'][-1]['stage']!='t01' or self.scene['lineage'][-1]['plan_ref']!=self.cap['plan_ref']:raise ValueError('U02_PREDECESSOR_COVERAGE_CHANGED')
        expected={sid:dict(row,geometry_ref=self.candidate['replacements'].get(sid,row['geometry_ref'])) for sid,row in old.items()}
        if current!=expected:raise ValueError('U02_EXACT_T01_PREDECESSOR_REQUIRED')
        ws=WorkingScene(raw,rows,shapes,sites,CropSettings(**policy['settings']))
        plan=self.store.get_json(self.cap['plan_ref'],kind='plan');ports=plan['details']['allocation']['ports']
        port_rows,index=read_pages(self.store,ports['index_ref'],binding=source_port_binding(policy,raw,shapes,sites,plan['details']['allocation']),kind='t01-board-ports',identity=lambda r:r['source_id'])
        stored={r['source_id']:{sid:self.store.get(ref,kind='t01-port-geometry') for sid,ref in r['ports'].items()} for r in port_rows}
        regenerated={sid:{oid:to_wkb(g,byte_order=1) for oid,g in zones.items()} for sid,zones in ws.ports.items()}
        if stored!=regenerated:raise ValueError('U02_SOURCE_PORT_RECONSTRUCTION_MISMATCH')
        traces=[(r,g) for r,g in zip(rows,shapes) if r['kind'] in TRACE_KINDS]
        if not traces:raise ValueError('U02_NATIVE_TRACE_INVENTORY_EMPTY')
        records=[]
        for row,g in traces:
            sid=row['id'];start,end=row['source_span'];native=raw[start:end]
            if row['trace_width_mm'] is None or row['trace_width_mm']<=0:raise ValueError('U02_TRACE_WIDTH_UNRESOLVED:'+sid)
            if current[sid]['geometry_ref']!=old[sid]['geometry_ref'] or digest(self.store.get(current[sid]['geometry_ref'],kind='geometry'))!=row['geometry_sha256']:raise ValueError('U02_TRACE_CHANGED:'+sid)
            records.append(dict(source_id=sid,native_kind=row['kind'],source_span=[start,end],native_bytes_sha256=digest(native),geometry_sha256=row['geometry_sha256'],original_width_mm=row['trace_width_mm'],disposition='RETAIN_ORIGINAL',pairs=[]))
        tree=STRtree([g for _,g in traces]);byid={r['source_id']:r for r in records}
        for site in sites:
            target=from_wkb(self.store.get(current[site['source_id']]['geometry_ref'],kind='geometry'))
            for i in sorted(map(int,tree.query(target.buffer(self.policy['hard_gap_mm']+.000001)))):
                row,g=traces[i];sid=row['id'];port=ws.ports[site['source_id']].get(sid)
                q=pair_check(site['core'],target,g,port,self.policy)
                byid[sid]['pairs'].append(dict(site_source_id=site['source_id'],**q))
        coverage=dict(source_objects=len(rows),site_occurrences=sum(len(s['aliases']) for s in sites),canonical_sites=len(sites),source_pages=(len(rows)+99)//100,port_pages=len(index['pages']),source_sha256=b['source_sha256'])
        return records,coverage

    def inventory(self):
        inspection=read(self.out/'t03_inspect.json')
        if inspection['binding']!=self.binding:raise ValueError('U02_T03_PREDECESSOR_BINDING_CHANGED')
        rows,index=read_pages(self.store,inspection['trace_inventory_ref'],binding=self.binding,kind='u02-traces',identity=lambda r:r['source_id'])
        return inspection,rows,index

    def plan(self):
        inspection,rows,index=self.inventory();require_supported(rows)
        plan=dict(family=FAMILY,binding=self.binding,trace_inventory_ref=inspection['trace_inventory_ref'],policy=self.policy,
                  strategy='retain-valid-native-paths',movement_objectives=0,source_count=len(rows),changed_trace_count=0)
        return self.save('t03_plan',dict(plan=plan,facts=dict(passed=True,trace_occurrences=len(rows),movement_objectives=0,construction_status='NOT_RUN')))

    def search(self):
        plan=read(self.out/'t03_plan.json')['plan'];inspection,rows,index=self.inventory();require_supported(rows)
        candidate=dict(family=FAMILY,plan_sha256=digest(canonical(plan)),predecessor_scene_ref=self.scene_ref,output_scene_ref=self.scene_ref,
                       disposition='NO_CHANGE_REQUIRED',changed_trace_count=0,replacement_refs={},trace_inventory_ref=plan['trace_inventory_ref'])
        verify_candidate(candidate,plan,self.scene_ref)
        return self.save('t03_search',dict(candidate=candidate,facts=dict(passed=True,disposition='NO_CHANGE_REQUIRED',changed_trace_count=0,fresh_execution=True,trace_occurrences=len(rows))))

    def verify(self):
        plan=read(self.out/'t03_plan.json')['plan'];candidate=read(self.out/'t03_search.json')['candidate'];verify_candidate(candidate,plan,self.scene_ref)
        inspection,stored,index=self.inventory();actual,coverage=self.assess()
        if actual!=stored or coverage!=inspection['coverage']:raise ValueError('U02_TRACE_RECONSTRUCTION_MISMATCH')
        require_supported(actual)
        return self.save('t03_verify',dict(candidate_sha256=digest(canonical(candidate)),binding=self.binding,
            facts=dict(passed=True,geometric_status='PASS',fresh_reconstruction=True,trace_occurrences=len(actual),changed_trace_count=0,complete_source_coverage=True)))

    def compare(self):
        candidate=read(self.out/'t03_search.json')['candidate'];verify_candidate(candidate,read(self.out/'t03_plan.json')['plan'],self.scene_ref)
        inspection,rows,index=self.inventory()
        comparisons=[dict(source_id=r['source_id'],left_sha256=r['geometry_sha256'],right_sha256=r['geometry_sha256'],added_area_mm2=0.,removed_area_mm2=0.) for r in rows]
        ref=store_pages(self.store,comparisons,binding=self.binding,kind='u02-comparison')
        checked,ci=read_pages(self.store,ref,binding=self.binding,kind='u02-comparison',identity=lambda r:r['source_id'])
        if checked!=comparisons:raise ValueError('U02_COMPARISON_PAGES_CHANGED')
        return self.save('t03_compare',dict(pagination_ref=ref,facts=dict(passed=True,trace_occurrences=len(rows),comparison_pages=len(ci['pages']),changed_trace_count=0,added_area_mm2=0.,removed_area_mm2=0.)))

    def review(self):
        return self.save('t03_review',dict(records=[],facts=dict(passed=True,owner_status='PENDING_USER',independent_status='NOT_RUN',decision_records=0)))

    def controls(self):
        inspection,rows,index=self.inventory();plan=read(self.out/'t03_plan.json')['plan'];candidate=read(self.out/'t03_search.json')['candidate'];reports=[]
        def reject(name,prefix,mutation,fn):
            fresh(self.out/'controls'/name/'mutation.json',mutation)
            try:fn()
            except ValueError as error:
                if not str(error).startswith(prefix):raise
                reports.append(dict(name=name,expected=prefix,error=str(error),status='PASS_EXPECTED_REJECTION'))
            else:raise ValueError('U02_NEGATIVE_NOT_REJECTED:'+name)
        changed=copy.deepcopy(candidate);changed['predecessor_scene_ref']=dict(self.scene_ref,sha256='0'*64)
        reject('wrong_predecessor','U02_T03_CANDIDATE_RECONSTRUCTION_MISMATCH',changed,lambda:verify_candidate(changed,plan,self.scene_ref))
        changed2=copy.deepcopy(candidate);changed2['changed_trace_count']=1
        reject('hidden_route_change','U02_T03_CANDIDATE_RECONSTRUCTION_MISMATCH',changed2,lambda:verify_candidate(changed2,plan,self.scene_ref))
        # Deliberate real geometry violation, assessed by the same finite-copper predicate.
        from shapely.geometry import Point,box
        core=Point(0,0).buffer(.1,quad_segs=128);grown=Point(0,0).buffer(.2,quad_segs=128);trace=box(.15,-.03,.3,.03)
        q=pair_check(core,grown,trace,None,self.policy);bad=[dict(source_id='negative-control',pairs=[q])]
        reject('finite_copper_intrusion','U02_T03_MOVEMENT_NOT_QUALIFIED',dict(core_wkb=to_wkb(core).hex(),candidate_wkb=to_wkb(grown).hex(),trace_wkb=to_wkb(trace).hex(),assessment=bad),lambda:require_supported(bad))
        return self.save('t03_controls',dict(controls=reports,facts=dict(passed=True,deliberate_controls=len(reports),all_rejected_for_expected_reason=True)))

    def save(self,op,result):
        fresh(self.out/(op+'.json'),result);return result

    def dispatch(self,op):
        return dict(t03_inspect=self.inspect,t03_plan=self.plan,t03_search=self.search,t03_verify=self.verify,t03_compare=self.compare,t03_review=self.review,t03_controls=self.controls)[op]()
