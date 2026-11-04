"""Fresh canonical source-port page binding for downstream T03 consumers."""
from src.stage_abi.store import canonical,digest
from src.t01_canonical import require,marker,full_bounds

def source_port_binding(policy,raw,shapes,sites,allocation):
    # Recompute from complete verified source shapes, never accept the stored
    # allocation bounds or presentation window as their own authority.
    require(policy)
    expected=full_bounds(shapes)
    if allocation.get('canonical_t01')!=marker() or allocation.get('analysis_bounds_mm')!=expected:
        raise ValueError('U02_T01_CANONICAL_PORT_BINDING_CHANGED')
    return dict(source_sha256=digest(raw),site_ids_sha256=digest(canonical(sorted(s['source_id'] for s in sites))),viewport_mm=expected)
