"""Explicit C03 round-intent adapter on the existing immutable stage runtime."""
from collections import Counter
from dataclasses import asdict
from pathlib import Path

from shapely import to_wkb

from src.c03_input_family import specification, visible_model
from src.c03_recovery import (circle_obligations, load_intent, permitted_rounds,
    assess_round_output, scope_round_assessment)
from src.crop_balanced_t01 import CropSettings, WorkingScene
from src.crop_circle_sources import site_record
from src.stage_abi.contracts import fail, ref
from src.stage_abi.journal import journalled
from src.stage_abi.runtime import Budget, output_scene, check_output
from src.stage_abi.scene import composed
from src.stage_abi.store import canonical, digest
from src.t01_board.adapter import BoardAdapter, PORT_STORE
from src.t01_board.source import context as board_context
from src.t01_crop.paging import store_pages, read_pages
from src.trace_width_clearance import TraceWidthContract
from src.u03_board.selection import validate as validate_selection, window


PROFILE = 'c03-source-bound-round-recovery-v1'
FAMILY = 'c03-native-round-class-intent/1'
STRATEGY = 'c03_source_round_recovery'
HEADER = 'C03 source-bound round recovery controlled English version 1.'
CLAUSES = [
    'Use the verified original native source and every source occurrence as context; bind the exact C03 source and crop SHA-256.',
    'Select the independently pinned 153 original circle obligations with complete native aliases, not a generator-selected positive set.',
    'Read centers, radii, filled form, layer and zero stroke from exact original native spans; preserve source cores and identities.',
    'Construct complete round circles from the pinned semantic diameter intents, with a 1.5 factor cap and 128 buffer quadrants; copy no historical candidate copper.',
    'This separate C03 round-only family imports neither generic priority/companion clipping nor C01 square/recess directives; generic profiles stay unchanged.',
    'Keep the existing verified crop inset unchanged; retain C028 as an untouched blocked original positive, never recovered coverage.',
    'Preserve the hard gap 0.020 mm and the existing 0.02010 mm construction guard; do not infer electrical intent or grant a foreign-contact exemption.',
    'Use the existing complete source-filled-land visible-surface model with original native contact widths and original-only visibility; never let new growth hide another boundary.',
    'Regenerate every original generic source port with its unchanged parameters and retain all raw stencil results without promoting their failures.',
    'Use only the owner-authorized exact C03 input/contact family to qualify unchanged native routes; no movement, port widening or partial-width authority is supplied.',
    'Retain every nonselected original source and every blocked target unchanged; update complete alias sets together.',
    'Keep all 121 original positive obligations and all 32 reference KEEP records; an owner-blocked obligation stays in the original denominator.',
    'Record native centroid Y, X and source-ID order and all complete simultaneous checks; no hidden reduced-extent success or target compensation.',
    'Reconstruct the full candidate, source partitions, aliases, ports, permissions and finite scene independently during verification and machine evaluations.',
    'Require actual native write/reread, nine-layer export/reparse, positive F.Cu primitives, per-source contours and corruption controls before native qualification.',
    'Keep owner review pending, independent review not run and electrical/manufacturing not established; retain every failure and blocked finding.',
]


def english():
    return HEADER+'\n'+'\n'.join(f'R{i:02d}: {t}' for i,t in enumerate(CLAUSES,1))+'\n'


def compile_policy(text, binding_ref, selection_ref):
    ref(binding_ref, 'binding_ref')
    ref(selection_ref, 'selection_ref')
    if type(text) is not str or text.replace('\r\n','\n').strip() != english().strip():
        fail('T01_ENGLISH_UNSUPPORTED', 'Exact C03 round/contact family wording required')
    spec, profile, sha = specification()
    definitions = load_intent(Path(__file__).resolve().parents[1], profile)['T01_DECISIONS']
    return dict(stage='t01', family=FAMILY, dialect=HEADER, english=english(),
        english_sha256=digest(english().encode()), binding_ref=binding_ref,
        u03_selection_ref=selection_ref, c03_input_contract=spec,
        c03_input_contract_sha256=sha, settings=asdict(CropSettings()),
        surface_contract=asdict(TraceWidthContract()),
        diameter_classes_mm=sorted({r['selected_diameter_mm'] for r in definitions if r['positive_growth']}),
        clause_trace=[dict(clause=f'R{i:02d}', english=t,
                           contract_field='c03_clause_'+str(i), value=True)
                      for i,t in enumerate(CLAUSES,1)],
        rules={f'R{i:02d}':t for i,t in enumerate(CLAUSES,1)})


def validate_policy(policy):
    if canonical(policy) != canonical(compile_policy(policy['english'],
            policy['binding_ref'], policy['u03_selection_ref'])):
        fail('T01_CONTRACT_DERIVATION_MISMATCH', 'C03 round/contact family')


def context(store, scene, policy):
    validate_policy(policy)
    binding, raw, rows, shapes, all_sites = board_context(store, scene, policy)
    selection = validate_selection(store.get_json(policy['u03_selection_ref'],
                                                 kind='u03-crop-selection'), digest(raw))
    spec, profile, _ = specification()
    if (selection['source_sha256'] != spec['source_sha256'] or
            selection['crop_sha256'] != spec['crop_sha256']):
        raise ValueError('C03_EXPLICIT_INPUT_PROFILE_REQUIRED')
    manifest = store.get_json(binding['manifest_ref'], kind='native-manifest')
    blobs = {r['source_id']:store.get(r['original_ref'], kind='geometry') for r in scene['objects']}
    obligations = circle_obligations(raw, manifest, blobs,
        load_intent(Path(__file__).resolve().parents[1], profile)['T01_DECISIONS'],
        spec['source_sha256'])
    by_alias = {a:s for s in all_sites for a in s['aliases']}
    sites, inventory = [], []
    for row in obligations:
        if row.source_id not in by_alias:
            raise ValueError('C03_ORIGINAL_CIRCLE_NOT_DISCOVERED')
        site = dict(by_alias[row.source_id], source_id=row.source_id,
                    center=list(row.center), radius=row.original_radius)
        if sorted(site['aliases']) != list(row.aliases):
            raise ValueError('C03_DISCOVERED_ALIAS_SET_CHANGED')
        sites.append(site)
        blocked = 'T01:'+row.key in profile['execution_permissions']['blocked_original_obligations']
        inventory.append(dict(source_id=row.source_id, aliases=list(row.aliases),
            disposition='BLOCKED_WRITE_BOUNDARY_OWNER_RETAINED' if blocked else 'SELECT_ORIGINAL_ROUND_INTENT',
            selected_for_treatment_model=True, original_positive=row.positive))
    sites.sort(key=lambda s:(s['center'][1],s['center'][0],s['source_id']))
    return dict(binding, u03_selection=selection, u03_site_inventory=inventory,
        c03_intent_sha256=policy['c03_input_contract_sha256']), raw, rows, shapes, sites


class NativeRoundAdapter(BoardAdapter):
    def __init__(self,*args,**kwargs):
        fail('T01_C03_SUBSTITUTE_RETIRED','C03 round-only construction is historical evidence, not a production T01 engine')

    def describe(self):
        spec, _, sha = specification()
        files = [Path(__file__), Path(__file__).with_name('c03_recovery.py'),
                 Path(__file__).with_name('c03_input_family.py')]
        return dict(family=FAMILY, implementation=digest(canonical(dict(contract=spec,
            contract_sha256=sha, base=super().describe()['implementation'],
            selection=digest((Path(__file__).parent/'u03_board/selection.py').read_bytes()),
            files={p.name:digest(p.read_bytes()) for p in files}))),
            operations=['discover','plan','run','verify'], english_dialect=HEADER,
            source_support='Explicit exact C03 native round intent; complete source context; owner-blocked C028 retained',
            clearance_model='Unchanged complete source-filled-land visible-surface model; generic ports/results retained separately')

    def _context(self, store, scene, policy):
        return context(store, scene, policy)

    def _allocate(self, raw, rows, shapes, sites, policy, binding):
        store = PORT_STORE.get()
        if store is None:
            fail('T01_BOARD_PORT_STORE_REQUIRED', 'C03 native allocation')
        manifest = store.get_json(binding['manifest_ref'], kind='native-manifest')
        blobs = {r['id']:to_wkb(g) for r,g in zip(rows,shapes,strict=True)}
        _, profile, _ = specification()
        obligations = circle_obligations(raw, manifest, blobs,
            load_intent(Path(__file__).resolve().parents[1], profile)['T01_DECISIONS'],
            binding['source_sha256'])
        ws = WorkingScene(raw, rows, shapes, sites, CropSettings())
        records = [dict(source_id=sid, ports={other:store.put('t01-port-geometry',
            to_wkb(g,byte_order=1)) for other,g in zones.items()})
            for sid,zones in sorted(ws.ports.items())]
        page_binding = dict(source_sha256=digest(raw),
            site_ids_sha256=digest(canonical(sorted(ws.ports))), viewport_mm=binding['viewport_mm'])
        ports = store_pages(store,records,binding=page_binding,kind='t01-board-ports')
        reread,index = read_pages(store,ports,binding=page_binding,kind='t01-board-ports',identity=lambda r:r['source_id'])
        if reread != records:
            raise ValueError('C03_COMPLETE_SOURCE_PORT_PAGES_CHANGED')
        allocation = dict(sites=[site_record(s) for s in sites],
            ports=dict(schema='t01-board-port-pages/1',index_ref=ports,sites=len(records),
                       zones=sum(len(r['ports']) for r in records),pages=len(index['pages'])),
            crop_selection=binding['u03_selection'],crop_site_inventory=binding['u03_site_inventory'],
            intent_parameters=[dict(source_id=r.source_id, key=r.key,
                center_mm=list(r.center), original_radius_mm=r.original_radius,
                required_diameter_mm=r.required_diameter, original_positive=r.positive)
                for r in obligations],
            profile_id=PROFILE, generic_priorities='NOT_APPLICABLE_TO_EXPLICIT_ROUND_FAMILY')
        return CropSettings(), allocation, {}, set()

    def plan(self, store, *args):
        result = super().plan(store, *args)
        return dict(result, family=FAMILY,
            specification='Native parameters and complete source/aliases reconstruct explicitly owner-adopted diameter intents; historical candidate copper is never read')

    def _compute(self, store, scene, policy, plan, checkpoint):
        token = PORT_STORE.set(store)
        try:
            return self._construct(store, scene, policy, plan, checkpoint)
        finally:
            PORT_STORE.reset(token)

    def _construct(self, store, scene, policy, plan, checkpoint):
        budget = Budget(plan['details']['bounds'])
        binding, raw, rows, shapes, sites = context(store,scene,policy)
        _, allocation, _, _ = self._allocate(raw,rows,shapes,sites,policy,binding)
        if allocation != plan['details']['allocation'] or plan['details']['targets'] != [s['source_id'] for s in sites]:
            fail('T01_PLAN_DERIVATION_MISMATCH','Complete C03 allocation')
        original = {r['id']:to_wkb(g) for r,g in zip(rows,shapes,strict=True)}
        manifest = store.get_json(binding['manifest_ref'],kind='native-manifest')
        _, profile, _ = specification()
        obligations = circle_obligations(raw,manifest,original,
            load_intent(Path(__file__).resolve().parents[1],profile)['T01_DECISIONS'],digest(raw))
        permitted = permitted_rounds(obligations,original,profile)
        current = dict(original)
        for row in obligations:
            for alias in row.aliases:
                current[alias] = to_wkb(permitted[row.source_id])
        coverage = scope_round_assessment(assess_round_output(obligations,original,current,
            window(binding['u03_selection'])),obligations,original,current,profile)
        if not coverage['scoped_execution_pass']:
            fail('C03_SCOPED_ROUND_COVERAGE_FAILED','Unmet nonblocked original intent')
        original_shapes = {r['id']:g for r,g in zip(rows,shapes,strict=True)}
        actual = dict(original_shapes)
        for row in obligations:
            for alias in row.aliases:
                actual[alias] = permitted[row.source_id]
        full = visible_model(rows,original_shapes,actual,sites)
        if not full['passed'] or not full['evaluation_complete']:
            fail('C03_FULL_VISIBLE_CONTACT_MODEL_FAILED','Complete simultaneous original-source model')
        checks = {r['source_id']:r for r in full['lands']}
        semantic = {r.source_id:r for r in obligations}
        decisions, replacements = [], {}
        for site in sites:
            budget.evaluation()
            sid = site['source_id']
            row = semantic[sid]
            blob = to_wkb(permitted[sid]); budget.output(blob)
            reference = store.put('geometry',blob)
            growing = blob != original[sid]
            for alias in row.aliases:
                replacements[alias] = reference
            decisions.append(dict(source_id=sid,key=row.key,aliases=list(row.aliases),
                center=list(row.center),source_radius_mm=row.original_radius,
                candidate_ref=reference,
                decision='ROUND_GROW_PRIORITY' if growing else 'KEEP_CONSTRAINED',
                construction_family=FAMILY,
                construction_status='ROUND_CLASS_GROWN' if growing else 'SOURCE_KEPT',
                serialization_token='Legacy round-growth token; no generic component-priority allocation',
                factor=row.required_diameter/(2*row.original_radius) if growing else 1.,
                required_positive=row.positive,
                square_guided=False,added_area_mm2=permitted[sid].difference(site['core']).area))
            checkpoint(dict(completed_sources=len(decisions),source_id=sid,candidate_ref=reference))
        return dict(decisions=decisions,replacements=replacements,allocation=allocation,
            events=[],square_disabled_controls=[],rejected_hypotheses=[],
            final_checks=[dict(source_id=s['source_id'],check=dict(passed=checks[s['source_id']]['passed'],
                complete_land_check_sha256=digest(canonical(checks[s['source_id']])))) for s in sites],
            full_visible_surface_check=full,original_coverage=coverage,
            counts=dict(Counter(d['construction_status'] for d in decisions)),
            evaluations=budget.evaluations,source_objects=len(rows),unique_sites=len(sites),
            source_occurrences=sum(len(s['aliases']) for s in sites),
            neighbor_response_sites=0,evolving_companion_response_sites=0)

    def run(self,store,scene,policy,plan,checkpoint):
        computed = journalled('c03-round-construction',dict(plan_sha256=digest(canonical(plan))),
                             lambda:self._compute(store,scene,policy,plan,checkpoint))
        out_ref,out = output_scene(store,scene,plan,replacements=computed['replacements'])
        return dict(status='CONSTRUCTED',family=FAMILY,**computed,output_scene_ref=out_ref,
            before_ref=store.put('geometry',to_wkb(composed(store,scene))),
            after_ref=store.put('geometry',to_wkb(composed(store,out))),
            protected_source_map_sha256=digest(canonical({r['source_id']:r['geometry_ref']
                for r in scene['objects'] if r['source_id'] not in computed['replacements']})))

    def verify(self,store,scene,policy,plan,candidate,proof_scope,checkpoint):
        if proof_scope != {'scope':'complete-board-t01-source-reconstruction'}:
            fail('PROOF_SCOPE_UNSUPPORTED','Full C03 native/source reconstruction required')
        expected = journalled('c03-round-verification',dict(plan_sha256=digest(canonical(plan))),
                              lambda:self._compute(store,scene,policy,plan,checkpoint))
        for key,value in expected.items():
            if canonical(candidate.get(key)) != canonical(value):
                fail('T01_SEMANTIC_RECONSTRUCTION_MISMATCH',key)
        if candidate['family'] != FAMILY or candidate['status'] != 'CONSTRUCTED':
            fail('C03_ROUND_CANDIDATE_FAMILY_CHANGED','Explicit family required')
        check_output(store,scene,plan,candidate,replacements=expected['replacements'])
        protected = digest(canonical({r['source_id']:r['geometry_ref'] for r in scene['objects']
                                      if r['source_id'] not in expected['replacements']}))
        if protected != candidate['protected_source_map_sha256']:
            fail('T01_PROTECTED_SOURCE_MAP_CHANGED','All context contributions')
        return dict(passed=True,failures=[],family=FAMILY,
            reconstructed_sites=expected['unique_sites'],
            reconstructed_alias_occurrences=expected['source_occurrences'],
            final_assembled_checks=len(expected['final_checks']),
            neighbor_response_sites=0,evolving_companion_response_sites=0,
            original_full_coverage_pass=expected['original_coverage']['original_full_coverage_pass'],
            blocked_original_positives=expected['original_coverage']['blocked_original_positive'],
            scope='Complete source, aliases, exact round intent and unchanged full finite-surface model; blocked original obligations remain unmet')
