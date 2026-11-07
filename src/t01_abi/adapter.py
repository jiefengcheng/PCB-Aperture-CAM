"""Canonical full-source interaction behind plan/run/verify operations.

Reuses the legacy priority/companion construction and retains its numerical
checks, with one uniform stronger full-surface guard. No file paths, saved targets or historical candidate geometry enter
this adapter. Verification recomputes allocation and contours, then checks the
assembled current surfaces separately from the construction-time scene.
"""
from collections import Counter
from pathlib import Path
from shapely import to_wkb
from shapely.geometry import Point
from shapely.ops import unary_union
from src.crop_balanced_t01 import CropSettings, WorkingScene, choose_priorities, local_groups, execute
from src.crop_diameter_selection import select_targets, promote_round_priorities
from src.crop_circle_sources import site_record
from src.crop_square_neighbor_experiment import verify_addition, construct
from src.stage_abi.contracts import closed, fail
from src.stage_abi.store import canonical, digest
from src.stage_abi.runtime import bounds_check, Budget, output_scene, check_output
from src.stage_abi.scene import composed
from src.stage_abi.journal import journalled
from . import FAMILY
from .contract import validate_policy
from .source import discover

class InteractionAdapter:
    def describe(self):
        root=Path(__file__).resolve().parents[1]
        files=sorted([*Path(__file__).parent.glob('*.py'), *root.glob('*.py')])
        return dict(family=FAMILY,implementation=digest(b''.join(str(p.relative_to(root)).encode()+p.read_bytes() for p in files)),
                    operations=['discover','plan','run','verify'],source_support='Complete bound original F.Cu cache; priority/companion interaction, physical classes, A-square/B-envelope and named recesses',
                    input_support=['literal-English','content-addressed-English-specification','source-selection-reference'],
                    english_dialect='T01 controlled English version 1',
                    clearance_model='Production .040 mm hard gap plus .04010 mm full-source visible-surface guard; no case-specific substitute')

    def _context(self,store,scene,policy):
        validate_policy(policy)
        binding=store.get_json(policy['binding_ref'],kind='t01-binding')
        raw,rows,shapes,sites=discover(store,scene,binding)
        return binding,raw,rows,shapes,sites

    def discovery(self,store,scene,policy,bounds):
        bounds_check(bounds,scene,dict(source_ids=[scene['objects'][0]['source_id']]))
        binding,raw,rows,shapes,sites=self._context(store,scene,policy)
        selection=dict(stage='t01',source_ids=[s['source_id'] for s in sites])
        bounds_check(bounds,scene,selection)
        return dict(source_ids=selection['source_ids'],sites=[site_record(s) for s in sites],
                    source_objects=len(rows),unique_sites=len(sites),occurrences=sum(len(s['aliases']) for s in sites),
                    policy_english_sha256=policy['english_sha256'],source_sha256=binding['source_sha256'])

    def _allocate(self,raw,rows,shapes,sites,policy,binding):
        settings=CropSettings(**policy['settings'])
        initial=WorkingScene(raw,rows,shapes,sites,settings)
        groups=local_groups(sites,binding['reviewed_pair'],settings.construction_gap)
        priorities,exceptions=choose_priorities(sites,initial)
        square=set(binding['recess_source_ids'])
        for component,sid in list(priorities.items()):
            if sid in square:
                del priorities[component]
                exceptions.append(dict(component_id=component,source_id=sid,reason='OWNER_REQUESTED_SQUARE_GUIDED_RECESS',previous_round_priority=sid))
        targets,records,limits=select_targets(sites,groups,priorities,initial,settings,policy['diameter_classes_mm'])
        promotions=promote_round_priorities(sites,groups,priorities,initial,settings,targets,records)
        limits.extend(dict(reason='FEASIBLE_ROUND_CLASS_PROMOTION',**p) for p in promotions)
        allocation=dict(groups=groups,priorities_by_physical_component=priorities,priority_exceptions=exceptions,
                        factor_limits=limits,size_classes=records,sites=[site_record(s) for s in sites],
                        ports={sid:{oid:to_wkb(g,byte_order=1).hex() for oid,g in zones.items()} for sid,zones in initial.ports.items()})
        return settings,allocation,targets,square

    def plan(self,store,scene,policy,selection,bounds):
        from src.t01_canonical import require
        require(policy)
        closed(selection,{'stage','scene_ref','source_ids'},'interaction selection')
        bounds_check(bounds,scene,selection)
        binding,raw,rows,shapes,sites=self._context(store,scene,policy)
        if selection['stage']!='t01' or set(selection['source_ids'])!={s['source_id'] for s in sites}:
            fail('T01_COMPLETE_CROP_SELECTION_REQUIRED','Every discovered site is required')
        _,allocation,_,_=self._allocate(raw,rows,shapes,sites,policy,binding)
        return dict(family=FAMILY,targets=[s['source_id'] for s in sites],bounds=bounds,
                    english_sha256=policy['english_sha256'],allocation=allocation,
                    specification='Every plan allocation field is derived from the English contract and original source, not historical results')

    def _compute(self,store,scene,policy,plan,checkpoint):
        from src.t01_canonical import require
        require(policy)
        budget=Budget(plan['details']['bounds']);budget.evaluation()
        binding,raw,rows,shapes,sites=self._context(store,scene,policy)
        settings,allocation,targets,square=self._allocate(raw,rows,shapes,sites,policy,binding)
        if canonical(allocation)!=canonical(plan['details']['allocation']) or plan['details']['targets']!=[s['source_id'] for s in sites]:
            fail('T01_PLAN_DERIVATION_MISMATCH','source-computed allocation or complete target order')
        from src.t01_canonical_surface import SurfaceGuard
        surface_guard=SurfaceGuard(rows,shapes,sites)
        result=execute(raw,rows,shapes,sites,allocation['groups'],allocation['priorities_by_physical_component'],
                       settings=settings,targets=targets,square_guided_ids=square,counterfactuals=True,surface_guard=surface_guard)
        for d in result['decisions']:
            if allocation['containment'][d['source_id']]['contained']:
                site=next(s for s in sites if s['source_id']==d['source_id'])
                if to_wkb(result['scene'].accepted[d['source_id']],byte_order=1)!=to_wkb(site['core'],byte_order=1):
                    fail('T01_CONTAINED_SOURCE_CHANGED',d['source_id'])
                d['keep_reason']='KEEP_CONTAINED'
            elif d['source_id'] in allocation.get('circle_overlap_keep_source_ids',[]):
                site=next(s for s in sites if s['source_id']==d['source_id'])
                if to_wkb(result['scene'].accepted[d['source_id']],byte_order=1)!=to_wkb(site['core'],byte_order=1):
                    fail('T01_OVERLAP_KEEP_SOURCE_CHANGED',d['source_id'])
                d['keep_reason']='KEEP_EXPOSED_CIRCUMFERENCE_BELOW_LIMIT'
            if d['priority'] and d['proposed_radius_mm']>d['source_radius_mm'] and d['decision']!='ROUND_GROW_PRIORITY':
                fail('T01_ROUND_ALLOCATION_NOT_CONSTRUCTIBLE',d['source_id'])
        if result['failed_patches']:
            # Retain failed hypotheses explicitly even though the legacy engine
            # keeps exact source after rejection. No hidden retry or acceptance.
            rejected=[]
            for f in result['failed_patches']:
                rejected.append({**{k:v for k,v in f.items() if k!='candidate'},'geometry_ref':store.put('geometry',to_wkb(f['candidate'],byte_order=1))})
        else:rejected=[]
        decisions=[];replacements={};byid={s['source_id']:s for s in sites};keys={s['source_id']:f'S{i+1:02d}' for i,s in enumerate(sites)};source_rows={r['source_id']:r for r in scene['objects']}
        for d in result['decisions']:
            budget.evaluation();sid=d['source_id'];g=result['scene'].accepted[sid];blob=to_wkb(g,byte_order=1);budget.output(blob)
            candidate_ref=source_rows[sid]['geometry_ref']if (allocation['containment'][sid]['contained']or sid in allocation.get('circle_overlap_keep_source_ids',[]))else store.put('geometry',blob)
            for alias in byid[sid]['aliases']:replacements[alias]=candidate_ref
            decisions.append(dict(d,key=keys[sid],candidate_ref=candidate_ref,size_class=allocation['size_classes'][sid],containment=allocation['containment'][sid]))
            checkpoint(dict(completed_sources=len(decisions),source_id=sid,candidate_ref=candidate_ref))
        events=[]
        for e in result['events']:
            budget.evaluation()
            event={k:v for k,v in e.items() if k not in ('counterfactual','earlier_copper')}
            for k in ('counterfactual','earlier_copper'):
                blob=to_wkb(e[k],byte_order=1);budget.output(blob);event[k+'_ref']=store.put('geometry',blob)
            events.append(event)
        # Restore one selected earlier neighbor at a time in execute(); separately
        # disable only the named recess, holding radius and current scene fixed.
        controls=[]
        for d in decisions:
            if not d['square_guided']:continue
            budget.evaluation();sid=d['source_id'];site=byid[sid]
            context=WorkingScene(raw,rows,shapes,sites,settings)
            for prior in decisions[:d['input_revision']]:
                context.commit(byid[prior['source_id']],result['scene'].accepted[prior['source_id']],context.revision)
            obs=context.obstacles(site,context.revision)
            plain=construct(site['core'],site['center'],targets[sid],obs,square_enabled=False,settings=settings.kernel())['candidate']
            plain=surface_guard.limit(site,plain,context,record=False)
            controls.append(dict(source_id=sid,key=keys[sid],radius_mm=targets[sid],input_revision=d['input_revision'],
                                 disabled_ref=store.put('geometry',to_wkb(plain,byte_order=1)),
                                 symmetric_difference_mm2=plain.symmetric_difference(result['scene'].accepted[sid]).area))
        # Check the completed scene, not just each feature's earlier prefix.
        final=[]
        for s in sites:
            budget.evaluation();sid=s['source_id'];g=result['scene'].accepted[sid]
            env=unary_union([s['core'],Point(*s['center']).buffer(targets[sid],quad_segs=settings.qsegs)])
            q=verify_addition(s['core'],g,env,result['scene'].obstacles(s,result['scene'].revision),settings=settings.kernel())
            final.append(dict(source_id=sid,check=q))
        if any(not r['check']['passed'] for r in final):fail('T01_ASSEMBLED_CLEARANCE_FAILED','final current scene')
        if len(controls)!=len(square) or any(c['symmetric_difference_mm2']<=settings.event_epsilon for c in controls):
            fail('T01_RECESS_CONTROL_NOT_ESTABLISHED','Each bound exception must have a measured effect')
        budget.evaluation()
        from src.prepared_land_scene import PreparedLandScene
        lands=[dict(id=s['source_id'],original=s['core'],candidate=result['scene'].accepted[s['source_id']],native_source_kind='gr_circle',native_stroke_width_mm=0.)for s in sites]
        aliases={a for s in sites for a in s['aliases']}
        fixed=[dict(id=r['id'],geometry=g,trace_width_mm=r.get('trace_width_mm') or 0.)for r,g in zip(rows,shapes)if r['id']not in aliases]
        surface=PreparedLandScene(lands,fixed).check(lands,materialize_scene=True,fail_fast=False)
        if not surface['passed']:fail('T01_CANONICAL_FULL_SURFACE_FAILED',str(surface['failures'][:10]))
        computed=dict(decisions=decisions,replacements=replacements,allocation=allocation,events=events,
                    full_surface_check=surface,construction_surface_limits=surface_guard.records,
                    square_disabled_controls=controls,rejected_hypotheses=rejected,final_checks=final,
                    counts=dict(Counter(d['decision'] for d in decisions)),evaluations=budget.evaluations,
                    source_objects=len(rows),unique_sites=len(sites),source_occurrences=sum(len(s['aliases']) for s in sites),
                    neighbor_response_sites=len({e['target_source_id'] for e in events}),
                    evolving_companion_response_sites=len({e['target_source_id'] for e in events if e['neighbor_role']=='earlier accepted companion'}))
        from src.t01_canonical import marker,fingerprint
        return dict(computed,canonical_t01=marker(),canonical_result_sha256=fingerprint(binding['source_sha256'],computed))

    def run(self,store,scene,policy,plan,checkpoint):
        # Journalling replays only this attempt's exact bound semantic event.
        computed=journalled('t01-interaction-construction',dict(plan_sha256=digest(canonical(plan))),
                            lambda:self._compute(store,scene,policy,plan,checkpoint))
        replacements=computed['replacements']
        out_ref,out=output_scene(store,scene,plan,replacements=replacements)
        return dict(status='CONSTRUCTED',family=FAMILY,**computed,output_scene_ref=out_ref,
                    before_ref=store.put('geometry',to_wkb(composed(store,scene))),
                    after_ref=store.put('geometry',to_wkb(composed(store,out))),
                    protected_source_map_sha256=digest(canonical({r['source_id']:r['geometry_ref'] for r in scene['objects'] if r['source_id'] not in replacements})))

    def verify(self,store,scene,policy,plan,candidate,proof_scope,checkpoint):
        if proof_scope!={'scope':'complete-c01-priority-companion-source-reconstruction'}:
            fail('PROOF_SCOPE_UNSUPPORTED','complete C01 interaction replay required')
        if candidate.get('family')!=FAMILY or candidate.get('status')!='CONSTRUCTED':
            fail('T01_SEMANTIC_RECONSTRUCTION_MISMATCH','family/status')
        expected=journalled('t01-interaction-verification-reconstruction',dict(plan_sha256=digest(canonical(plan))),
                           lambda:self._compute(store,scene,policy,plan,checkpoint))
        for key,value in expected.items():
            if canonical(candidate.get(key))!=canonical(value):
                fail('T01_SEMANTIC_RECONSTRUCTION_MISMATCH',key)
        for r in expected['decisions']:
            if store.get(r['candidate_ref'],kind='geometry') is None:fail('T01_CANDIDATE_MISSING',r['source_id'])
        check_output(store,scene,plan,candidate,replacements=expected['replacements'])
        protected=digest(canonical({r['source_id']:r['geometry_ref'] for r in scene['objects'] if r['source_id'] not in expected['replacements']}))
        if candidate.get('protected_source_map_sha256')!=protected:
            fail('T01_PROTECTED_SOURCE_MAP_CHANGED','non-selected original contributions')
        return dict(passed=True,failures=[],family=FAMILY,reconstructed_sites=expected['unique_sites'],
                    reconstructed_alias_occurrences=expected['source_occurrences'],final_assembled_checks=len(expected['final_checks']),
                    neighbor_response_sites=expected['neighbor_response_sites'],evolving_companion_response_sites=expected['evolving_companion_response_sites'],
                    scope='Full bound C01 source/allocation/contour reconstruction and assembled legacy-policy finite-surface checks; same parser/kernel, no independent/native/electrical/manufacturing qualification')
