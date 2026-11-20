"""Clearance-only T04 reservations; never minimum copper or plotted material.

The native reference is prepared before connected growth. Its later stages must
leave room for replaying the source-derived T04 checking envelope, not merely
the narrower nominal body. The extra guard is two existing polygon tolerances;
it is construction headroom for native encoding, not a clearance waiver.
"""
from src.pcb_data_abi.geometry import POLYGON_TOLERANCE_MM
from src.native_inventory import ERROR_MM
from src.stage_abi.store import canonical, digest

NATIVE_HEADROOM_MM = 2 * POLYGON_TOLERANCE_MM
ROLE = 'CLEARANCE_ONLY_NOT_COPPER_NOT_MINIMUM_FLOOR'
CHECKING_PREPARATION_BYTES = 128 * 1024**2


def constraint(context, owner, material, *, shared_memo=None):
    """Use reservations only as foreign obstacles in a clearance predicate."""
    from src.component_clearance import joined
    values = [material]
    if owner in context.reserved: values.append(context.reserved[owner])
    checking = getattr(context, 'checking_envelopes', {})
    if owner in checking: values.append(checking[owner])
    if len(values) == 1: return material
    # Only the exact ordered obstacle construction is reusable. Reservations
    # and checking envelopes can change independently of nominal copper.
    # GeometryMemo binds WKB, SRID and precision, bounds retention and checks
    # the cached output; each caller still evaluates its current predicates.
    from src.stage_abi.loaded_geometry import GeometryMemo
    if shared_memo is not None:
        # The union depends only on the ordered operands. Physical owners and
        # functional channels still perform their own predicates and report IDs.
        return shared_memo.construct('ordered-obstacle-union', values, (), lambda: joined(values))
    memo = getattr(context, '_checking_constraint_memo', None)
    if memo is None:
        memo = context._checking_constraint_memo = GeometryMemo('foreign-owner-checking-obstacle')
    return memo.construct('ordered-obstacle-union', values, (owner,), lambda: joined(values))


def install(context, store, binding, checkpoint_run=None, *, reuse_from=None):
    """Prepare source-bound envelopes once per fresh worker/owner context."""
    from . import pipeline as p
    if context is None: return None
    run = store.root.parent if checkpoint_run is None else checkpoint_run
    checkpoint = p.load(run / 'RAW_WIDTH_CHECKPOINT.json')
    completed=p.load(run/'t04.json')
    if checkpoint!={k:v for k,v in completed.items()if k not in('t04_width_fence','pin_separation')}:
        raise ValueError('CHECKING_ENVELOPE_RAW_CHECKPOINT_CHANGED')
    completed_sha = digest(canonical(completed))
    for mode in('construct','1','2'):
        audit=p.load(run/'audits/t04'/(mode+'.json'))
        if audit['status']!='PASS'or audit['candidate_sha256']!=completed_sha:
            raise ValueError('CHECKING_ENVELOPE_T04_AUDIT_CHANGED')
    if checkpoint['solution'].get('schema') != 'source-route-ten-step-width-ladder/1':
        raise ValueError('CHECKING_ENVELOPE_REQUIRES_QUALIFIED_LADDER')
    producer = p.Store(run / 'runtime')
    source = p.load(run / 'source.json')
    if source['source_ref'] != binding['source_ref']:
        raise ValueError('CHECKING_ENVELOPE_SOURCE_CHANGED')
    scene = producer.get_json(source['scene_ref'], kind='scene')
    # Validate each installation independently. A donor contributes cached
    # geometry only. The receiving context still resolves every owner and
    # groups offsets in source order, so changed partitions form new unions.
    rows, _, original = p.operands(producer, scene)
    from src.stage_abi.loaded_geometry import GeometryMemo
    memo_binding = ('t04-checking-preparation', source['source_ref']['sha256'])
    memo = getattr(reuse_from, '_checking_preparation_memo', None)
    if memo is None or memo.binding != memo_binding:
        # One bounded preparation cache is shared by both contexts. The usual
        # small-overlay budget can evict a full source-offset inventory before
        # its second traversal; eviction still means exact recomputation.
        memo = GeometryMemo(memo_binding, limit=CHECKING_PREPARATION_BYTES)
    context._checking_preparation_memo = memo
    buckets = {}; replay_buckets = {}; records = []
    for sid, factor in sorted(checkpoint['part_factors'].items()):
        if factor == 1: continue
        width = rows[sid]['metadata']['minimum_caliper_mm']
        geometry = p.offset_part(original[sid], width, factor, True,
                                 extra_envelope_mm=NATIVE_HEADROOM_MM,memo=memo)
        owner = context.owner(sid, original[sid])
        buckets.setdefault(owner, []).append(geometry)
        replay_buckets.setdefault(owner, []).append(p.offset_part(original[sid],width,factor,True,memo=memo))
        records.append(dict(source_id=sid, original_ref=rows[sid]['original_ref'],
                            factor=factor, original_width_mm=width,
                            envelope_sha256=digest(p.to_wkb(geometry))))
    # Keep the construction headroom and native replay geometry in separate
    # maps. Neither map is an operand in the actual copper composition.
    context.checking_envelopes = {o:memo.construct('owner-checking-envelope',values,(o,),lambda:p.unary_union(values)) for o,values in buckets.items()}
    context.checking_replay_envelopes = {o:memo.construct('owner-replay-envelope',values,(o,),lambda:p.unary_union(values)) for o,values in replay_buckets.items()}
    receipt = dict(schema='t04-clearance-only-reservations/1', role=ROLE,
                   source_sha256=source['source_ref']['sha256'],
                   checkpoint_sha256=digest(p.canonical(checkpoint)),
                   checking_margin_mm=ERROR_MM, native_headroom_mm=NATIVE_HEADROOM_MM,
                   records=records)
    context.checking_envelope_binding = digest(canonical(receipt))
    context.binding = digest(canonical([context.binding, context.checking_envelope_binding]))
    producer.verify_reads()
    return receipt


def initialize(store, binding, scene, physical=None, functional=None, *, reuse_from=None):
    """No effect before legacy T04; connected jobs use that checked reference."""
    run = store.root.parent
    if (run / 'LEGACY_REFERENCE_JOB.json').exists():
        if scene is None or not any(row['stage'] == 't04' for row in scene['lineage']):
            return None
        checkpoint_run = run
    elif (run / 'REFERENCE_BINDING.json').exists():
        checkpoint_run = run.parent / 'legacy'
    else: return None
    receipts=[]
    for ctx in (physical, functional):
        if ctx is None: continue
        receipts.append(install(ctx, store, binding, checkpoint_run, reuse_from=reuse_from))
        reuse_from=ctx
    return receipts


def indexed(context, source_parts):
    """Planner obstacles only; do not use these for mandatory fill budgets."""
    values = getattr(context, 'checking_envelopes', {})
    return {i:values[owner] for i,g in enumerate(source_parts)
            if (owner := context.index.membership(g)[0]) in values}


def check_native(context, owned, gap):
    """Check actual parsed additions against the unexpanded replay envelopes."""
    from src.component_distance import distance
    from src.component_clearance import joined,surfaces
    from shapely import STRtree
    checking=getattr(context,'checking_replay_envelopes',{})
    ids=sorted(checking);tree=STRtree([checking[o]for o in ids]);pairs=[]
    if set(owned)!=set(context.cores):raise ValueError('CHECKING_NATIVE_OWNER_INVENTORY_CHANGED')
    for own,g in sorted(owned.items()):
        delta=joined(surfaces(g.difference(context.cores[own])))
        if delta.is_empty:continue
        for i in sorted(map(int,tree.query(delta.buffer(gap).envelope))):
            other=ids[i]
            if other==own:continue
            measured=distance(delta,checking[other]);pairs.append(dict(owner=own,foreign_owner=other,gap_mm=measured,passed=measured+1e-12>=gap))
    result=dict(passed=all(r['passed']for r in pairs),pairs=pairs,required_gap_mm=gap,
                checking_margin_mm=ERROR_MM,native_headroom_mm=NATIVE_HEADROOM_MM,
                role=ROLE,binding=getattr(context,'checking_envelope_binding',None))
    if not result['passed']:raise ValueError('NATIVE_REFERENCE_OCCUPIES_T04_CHECKING_CLEARANCE:'+str([r for r in pairs if not r['passed']][:2]))
    return result
