"""Opt-in stage-order experiment, never a pipeline/accepted-T03 entry.

The full source remains fixed context. Only explicit route and terminal lists
are mutable. Constructed group interiors retain their existing diagnostics;
assembly does not turn those diagnostics into completed T04 acceptance.
"""
from contextlib import contextmanager
from shapely import STRtree, from_wkb, to_wkb
from shapely.ops import unary_union
from src import component_clearance as cc, source_channel_scope as sc
from src.original_copper_owners import OriginalOwners
from . import pipeline as p
from .profile_intake import BoundStore

SCHEMA = 't04-first-bounded-order-experiment/1'


class ExperimentStore(BoundStore):
    """Revalidate retained as well as newly written artifact bytes at exit."""
    def get(self, ref, *, kind=None):
        raw=super().get(ref,kind=kind)
        self.read_refs[ref['artifact_id']]=dict(ref)
        return raw

    def verify_reads(self):
        for ref in tuple(self.read_refs.values()): self.get(ref)


def prepare_original(directory, store, scene, binding, index):
    """Reusable source preparation explicitly independent of T03 custody."""
    from .source_roles import prepare_or_load
    original = require_source(store, binding, scene)
    roles, native, receipt = prepare_or_load(directory, store, original, p.operands(store, original), index)
    # Coverage/admission is stage-local. A terminal that grows first can cover
    # a route or obstruct a relation; source-only caching cannot erase that.
    if p.canonical(scene) != p.canonical(original):
        native = p.width_admission(store, scene)
    return roles, native, receipt


def require_source(store, binding, scene):
    original = store.get_json(binding['scene_ref'], kind='scene')
    if scene['source_sha256'] != binding['source_ref']['sha256']:
        raise ValueError('ORDER_SOURCE_HASH_CHANGED')
    store.get(binding['source_ref'], kind='gerber-source')
    old = {r['source_id']: r for r in original['objects']}
    now = {r['source_id']: r for r in scene['objects']}
    if not set(old) <= set(now) or any(now[s]['original_ref'] != r['original_ref'] or
            now[s]['metadata'] != r['metadata'] for s, r in old.items()):
        raise ValueError('ORDER_SOURCE_IDENTITY_OR_POSE_METADATA_CHANGED')
    for row in old.values():
        store.get(row['original_ref'], kind='geometry')
    return original


def terminal_scope(rows, original, native_paths, sites, allocation, *, reach=.5):
    """Explicit bounded comparison scope, with canonical circle group closure."""
    route_ids = sorted({s for ss in native_paths.values() for s in ss})
    tree = STRtree([original[s] for s in route_ids])
    def near(g):
        return bool(len(tree.query(g.buffer(reach), predicate='intersects')))
    selected = {s['source_id'] for s in sites if near(s['core'])}
    # Preserve complete canonical competition groups and round priorities for
    # every participating physical component; no resampling after reordering.
    while True:
        old = set(selected)
        for group in allocation['groups']:
            if selected.intersection(group['site_ids']): selected.update(group['site_ids'])
        components = {s['physical_contact_group'] for s in sites if s['source_id'] in selected}
        selected.update(v for k, v in allocation['priorities_by_physical_component'].items() if k in components)
        if old == selected: break
    rectangles = sorted(s for s, r in rows.items() if p.t02_land(r) and near(original[s]))
    return dict(circle_sites=sorted(selected), rectangles=rectangles, reach_mm=reach,
                selection='ORIGINAL_ROUTE_NEIGHBORHOOD; CANONICAL_CIRCLE_GROUP_AND_PRIORITY_CLOSURE',
                fixed_circle_sites=len(sites)-len(selected))


def allocate_original(store, binding, original):
    sites = p.t01_sites(store, original)
    _, material, _ = p.operands(store, original)
    meta = binding['width_metadata_rows']
    raw = store.get(binding['width_metadata_encoding_ref'], kind='kernel-width-data')
    spec = p.specification()
    policy = dict(canonical_t01=p.marker(), family=p.marker()['family'],
                  settings=spec['settings'], diameter_classes_mm=spec['diameter_classes_mm'])
    allocation = p.allocate(raw, meta, [material[r['id']] for r in meta], sites,
                            policy, dict(reviewed_pairs=[], recess_source_ids=[]))
    return sites, allocation


def circles(store, scene, binding, sites, prepared, target_ids):
    """Existing canonical allocation/execute/guard, explicit bounded targets."""
    require_source(store, binding, scene)
    settings, allocation, targets, square = prepared
    wanted = set(target_ids)
    selected = [s for s in sites if s['source_id'] in wanted]
    if len(selected) != len(wanted): raise ValueError('ORDER_CIRCLE_TARGET_MISSING')
    groups = [g for g in allocation['groups'] if wanted.intersection(g['site_ids'])]
    if any(not set(g['site_ids']) <= wanted for g in groups):
        raise ValueError('ORDER_CANONICAL_GROUP_TRUNCATED')
    priorities = {k:v for k,v in allocation['priorities_by_physical_component'].items() if v in wanted}
    _, current, _ = p.operands(store, scene)
    meta = binding['width_metadata_rows']
    raw = store.get(binding['width_metadata_encoding_ref'], kind='kernel-width-data')
    shapes = [current[r['id']] for r in meta]
    result = p.execute(raw, meta, shapes, selected, groups, priorities, dynamic=True,
        settings=settings, counterfactuals=True, targets=targets, square_guided_ids=square,
        surface_guard=p.SurfaceGuard(meta, shapes, selected))
    after = dict(current)
    for site in selected:
        for sid in site['aliases']: after[sid] = result['scene'].accepted[site['source_id']]
    lands = [dict(id=s['source_id'], original=s['core'], candidate=after[s['source_id']],
                  native_source_kind='gr_circle', native_stroke_width_mm=0.) for s in selected]
    omitted = {a for s in selected for a in s['aliases']}
    widths = {r['id']:r['trace_width_mm'] for r in meta}
    fixed = [dict(id=s, geometry=g, trace_width_mm=widths[s]) for s,g in current.items() if s not in omitted]
    checker = p.PreparedLandScene(lands, fixed)
    from src.t01_region_contacts import install_prepared_ports
    ports = install_prepared_ports(checker, meta)
    proof = checker.check(lands, materialize_scene=True)
    if ports: proof['original_region_attachment_ports'] = ports
    if not proof['passed'] or any(not d['verification']['passed'] for d in result['decisions']):
        raise ValueError('ORDER_T01_COMPLETE_LAND_CHECK_FAILED')
    for site in selected:
        if site['source_id'] in set(allocation['contained_keep_source_ids']+allocation['circle_overlap_keep_source_ids']):
            if to_wkb(after[site['source_id']]) != to_wkb(site['core']):
                raise ValueError('ORDER_T01_KEEP_CHANGED')
    return dict(output_scene_ref=p.artifact_scene(store, scene, after, 'bounded-order-t01'),
                decisions=result['decisions'], full_surface_check=proof,
                events=[{k:v for k,v in e.items() if k not in ('counterfactual','earlier_copper')} for e in result['events']],
                rejected_hypotheses=[{k:v for k,v in e.items() if k!='candidate'} for e in result['failed_patches']],
                allocation_sha256=p.digest(p.canonical(allocation)), target_ids=sorted(wanted),
                canonical_allocation='COMPLETE_ORIGINAL_SOURCE; BOUNDED_EXECUTION')


@contextmanager
def physical_context(store, binding):
    previous = cc.ACTIVE
    if previous is None:
        source = store.get_json(binding['scene_ref'], kind='scene')
        _, material, _ = p.operands(store, source)
        raw = store.get(binding['source_ref'], kind='gerber-source')
        parsed, _, _ = p.source_profile.parse_source(raw)
        whole = p.affine_scale(p.source_profile.ordered((p.source_profile.object_geometry(o)[0],o.polarity_dark)
                               for o in parsed.objects), 1, -1, origin=(0,0))
        cc.ACTIVE = cc.Context(whole, binding['source_ref']['sha256'], material)
    try: yield
    finally: cc.ACTIVE = previous


def rectangles(store, scene, binding, target_ids):
    require_source(store, binding, scene)
    if not target_ids:
        return dict(output_scene_ref=store.put_json('scene', scene), verification=dict(passed=True),
                    target_ids=[], disposition='EMPTY_BOUNDED_TARGET_INVENTORY')
    with physical_context(store, binding):
        adapter = p.FastRectangleAdapter('t02')
        try:
            policy = dict(stage='t02', parameters=p.land_parameters('t02'))
            selection = dict(stage='t02', scene_ref=store.put_json('scene', scene), source_ids=list(target_ids))
            details = adapter.plan(store, scene, policy, selection, p.bounds(scene))
            plan = dict(stage='t02', scene_ref=selection['scene_ref'], policy_ref=store.put_json('policy',policy),
                        implementation=adapter.describe()['implementation'], details=details)
            candidate = adapter.run(store, scene, policy, plan, lambda _:None)
            proof = adapter.verify(store, scene, policy, plan, candidate,
                                   dict(scope='COMPLETE_CONTEXT; EXPLICIT_BOUNDED_TERMINALS'), lambda _:None)
            if not proof['passed']: raise ValueError('ORDER_T02_RECONSTRUCTION_FAILED')
            return dict(output_scene_ref=candidate['output_scene_ref'], candidate=candidate,
                        plan=plan, verification=proof, target_ids=list(target_ids))
        finally: adapter.close()


def assemble(store, scene, stage):
    """Materialize the exact serialized contours; no new group audit or verdict."""
    from .group_board_job import checked
    checked(stage)
    _, material, _ = p.operands(store, scene)
    for key in ('continuous_source_bodies','changed_bulk_copper'):
        for sid, value in stage['hybrid_components'][key].items():
            if sid not in material: raise ValueError('ORDER_ASSEMBLY_UNKNOWN_SOURCE')
            material[sid] = from_wkb(bytes.fromhex(value['wkb_hex']))
    ref = p.artifact_scene(store, scene, material, 'bounded-order-diagnostic-assembly')
    return dict(scene_ref=ref, stage_sha256=p.digest(p.canonical(stage)),
                complete_t04=False, publication_ready=False, export_qualified=False)


def reconcile(store, binding, original, trace_scene, final, stage, terminal_ids):
    """Floor/identity/connection obligations, not unchanged-original T03."""
    require_source(store, binding, final)
    rows, source, _ = p.operands(store, original)
    _, floor, _ = p.operands(store, trace_scene)
    _, material, _ = p.operands(store, final)
    trace_ids = sorted({s for ss in stage['native_trace_source_ids_by_route'].values() for s in ss})
    failures = []
    # Later land algorithms must leave all existing trace operands byte-exact.
    changed = [s for s in trace_ids if to_wkb(floor[s]) != to_wkb(material[s])]
    if changed: failures.append(dict(reason='CONSTRUCTED_TRACE_FLOOR_CHANGED', sources=changed))
    fixed = sorted(set(floor)-set(terminal_ids))
    fixed_changes = [s for s in fixed if to_wkb(floor[s]) != to_wkb(material[s])]
    if fixed_changes: failures.append(dict(reason='NON_TARGET_OPERAND_CHANGED', sources=fixed_changes))
    core_ids = sorted(set(terminal_ids)|{s for s,r in rows.items() if r['kind']=='circle' or p.t02_land(r)})
    core_loss = {s:source[s].difference(material[s]).area for s in core_ids}
    if any(v > p.EPS for v in core_loss.values()): failures.append(dict(reason='TERMINAL_CORE_REMOVED', areas=core_loss))
    connections=[];attachments=[]
    from .native_contact_support import assemble as route_union
    for route, members in stage['native_trace_source_ids_by_route'].items():
        old = route_union(members, {}, source)
        now = route_union(members, {}, material)
        old_count, now_count = len(OriginalOwners(old).owners), len(OriginalOwners(now).owners)
        connections.append(dict(route_id=route, source_components=old_count, assembled_components=now_count,
                                passed=now_count<=old_count))
        for terminal in terminal_ids:
            contact = old.intersection(source[terminal])
            if contact.area <= p.EPS: continue
            area=now.intersection(material[terminal]).area
            attachments.append(dict(route_id=route, terminal_id=terminal, original_contact_area_mm2=contact.area,
                                    final_contact_area_mm2=area, passed=area>p.EPS))
    if not all(v['passed'] for v in connections): failures.append(dict(reason='NATIVE_ROUTE_DISCONNECTED'))
    if not all(v['passed'] for v in attachments): failures.append(dict(reason='ORIGINAL_TERMINAL_ATTACHMENT_LOST'))
    from src import pin_separation as pin
    pin_proof = None
    if pin.ACTIVE is not None:
        pin_proof=pin.ACTIVE.growth_parts(floor.values(), material.values())
        if not pin_proof['passed']: failures.append(dict(reason='PIN_DOMAIN_CHANGED'))
    return dict(schema=SCHEMA, passed=not failures, failures=failures,
                trace_operands_byte_preserved=len(trace_ids)-len(changed), terminal_core_loss_mm2=core_loss,
                non_target_operands_byte_preserved=len(fixed)-len(fixed_changes),
                route_connections=connections, terminal_attachments=attachments, pin_proof=pin_proof,
                accepted_t03=False, complete_t04=False, publication_ready=False,
                inherited_endpoint_diagnostics=stage['hybrid_components']['frozen_endpoint_obligations'],
                inherited_corner_diagnostics=stage['hybrid_components']['corner_smoothing']['unresolved'])
