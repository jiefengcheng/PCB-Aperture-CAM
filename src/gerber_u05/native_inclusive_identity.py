"""Bind a newly exported inclusive rectangle to its qualified source members.

This supplies the same predecessor used by the legacy native verifier. It
does not treat the new rectangle itself as original copper or skip land checks.
"""
from . import pipeline as p


def bind(stage, sid, row, value, previous, original, wanted, context):
    def reject():
        raise ValueError('NATIVE_T02_INCLUSIVE_PREDECESSOR_UNBOUND:' + sid)
    metadata = row.get('metadata', {})
    members = metadata.get('members', [])
    if (stage != 't02' or row.get('kind') != 'inclusive_rectangle'
            or metadata.get('origin') != 't02-inclusive-fill'
            or len(members) < 2 or len(set(members)) != len(members)
            or any(m not in previous or m not in original or m not in wanted for m in members)):
        reject()
    records = [r for r in value['candidate']['inclusive_candidates']
               if r['status'] == 'MERGED' and 'candidate_ref' in r
               and sid == 't02-inclusive:' + r['candidate_ref']['sha256']]
    if len(records) != 1:
        reject()
    decision = records[0]
    ref = decision['candidate_ref']
    if (decision['members'] != members or decision['reasons'] or not decision['check']['passed']
            or not 0 <= decision['shortage'] <= .20
            or row.get('original_ref') != ref or row.get('geometry_ref') != ref
            or not set(members) <= {r['source_id'] for r in value['candidate']['decisions']}):
        reject()
    logical = p.box(*p.unary_union([wanted[m] for m in members]).bounds)
    if p.digest(p.to_wkb(logical)) != ref['sha256'] or context is None:
        reject()
    owners = {context.owner(m) for m in members}
    if (len(owners) != 1 or context.owner(sid) not in owners
            or decision.get('original_component_owners') != sorted(owners)
            or metadata.get('original_component_owner_id') not in owners
            or metadata.get('original_source_sha256') != context.source_hash
            or metadata.get('original_member_wkb_sha256') != {
                m: p.digest(p.to_wkb(context.originals[m])) for m in members}):
        reject()
    functional = getattr(context, 'functional', None)
    if functional is not None:
        channels = {functional.owner(m) for m in members}
        if (len(channels) != 1 or functional.owner(sid) not in channels
                or metadata.get('original_channel_id') not in channels
                or decision.get('functional_source_channel_ids') != sorted(channels)):
            reject()
    core = p.unary_union([previous[m] for m in members])
    source = p.unary_union([original[m] for m in members])
    return core, source, dict(source_id=sid, members=list(members),
        original_component_owner_id=next(iter(owners)),
        qualified_rectangle_sha256=ref['sha256'],
        predecessor_sha256=p.digest(p.to_wkb(core)),
        original_member_union_sha256=p.digest(p.to_wkb(source)),
        scope='Member-derived predecessor; complete actual land and downstream checks retained')
