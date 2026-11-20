"""Batch an operation-local owner filter without caching permission decisions.

The existing `_foreign_for` resolves the immutable owner fingerprint on every
call. Applying it once to the ordered accepted prefix is exactly the same
filter as applying it separately to each member. Stored patch bytes are still
read/hash-checked/decoded, policy and owner are resolved afresh per proposal,
and the certificate issuer still verifies complete prefix accounting.
No state or geometry cache survives this function. It cannot reuse an old
exemption after owner, source policy or accepted copper changes.
"""
from hashlib import sha256
from shapely import from_wkb

def prepare_owner_exemptions(accepted,owner,read,foreign_for,*,with_prefix=False):
    """Return original-order exempt IDs using the EXISTING bound owner filter.

    ``read`` must read actual geometry artifacts with its usual integrity checks;
    the extra fingerprint check also refuses a stale/misbound reader. The policy
    callback must only filter entries, preserving the actual immutable geometry.
    No source ID, owner label or electrical intent is inferred here.
    """
    # The integrated issuer also needs these SAME decoded members for global
    # pin/safety material, even when clearance's owner policy exempts them.
    # Returning the operation-local prefix avoids another read/decode pass.
    if not accepted:return ([],[])if with_prefix else []
    prefix=[];seen=set()
    for entry in accepted:
        sid=entry['source_id']
        if sid in seen:raise ValueError('OWNER_EXEMPTION_DUPLICATE_PREFIX')
        seen.add(sid);raw=read(entry['patch_ref'])
        if sha256(raw).hexdigest()!=entry['patch_ref']['sha256']:
            raise ValueError('OWNER_EXEMPTION_PATCH_CORRUPTED')
        prefix.append((sid,from_wkb(raw)))
    retained=foreign_for(owner,prefix)
    originals=dict(prefix);kept=set()
    for sid,shape in retained:
        if sid not in originals or sid in kept or shape is not originals[sid]:
            raise ValueError('OWNER_EXEMPTION_POLICY_NOT_A_FILTER')
        kept.add(sid)
    exemptions=[sid for sid,_ in prefix if sid not in kept]
    return (exemptions,prefix)if with_prefix else exemptions
