"""Explicit constant-width source path proposals, without copper edits.

Unlike the historical endpoint-component filter, width transitions are recorded
as original source boundaries instead of rejecting all visible copper in the
mixed-width component. Branches remain complete networks, never silently split
into independently accepted paths. These are geometric source definitions only.
"""
import hashlib
from collections import defaultdict
from decimal import Decimal
from .trace_endpoint_inventory import endpoint_components


def point(values):return tuple(Decimal(v) for v in values)


def uniform_source_paths(rows,seed_ids):
    objects={r['source_id']:r for r in rows}
    if len(objects)!=len(rows) or not set(seed_ids)<=objects.keys():raise ValueError('INVALID_TRACE_IDENTITIES')
    by_width=defaultdict(list);nodes=defaultdict(set)
    for r in rows:
        by_width[r['width_mm']].append(r)
        for xy in r['endpoints_decimal_mm']:nodes[point(xy)].add(r['source_id'])
    paths=[]
    for width,subset in sorted(by_width.items()):
        seeds=set(seed_ids)&{r['source_id'] for r in subset}
        if not seeds:continue
        for c in endpoint_components(subset,seeds):
            members=set(c['source_ids']);ports=[]
            for xy in sorted({point(p) for sid in members for p in objects[sid]['endpoints_decimal_mm']}):
                others=nodes[xy]-members
                if not others:continue
                assert all(objects[sid]['width_mm']!=width for sid in others)
                ports.append(dict(point_decimal_mm=[str(v) for v in xy],
                    own_source_ids=sorted(nodes[xy]&members),
                    other_width_source_ids=sorted(others),
                    other_original_widths_mm=sorted({objects[sid]['width_mm'] for sid in others}),
                    evidence='EXACT_ORIGINAL_ENDPOINT_WIDTH_TRANSITION; not an arbitrary crop cut'))
            identity='\n'.join(c['source_ids']).encode()
            paths.append(dict(**c,path_id='UP-'+hashlib.sha256(identity).hexdigest()[:16],
                uniform_original_width_mm=width,original_width_transition_ports=ports,
                boundary_rule='Maximal exact-endpoint-connected source network with one original width; all width-transition neighbors retained explicitly',
                path_status='PROPOSED_COMPLETE_UNIFORM_SOURCE_PATH' if not c['unresolved_reasons'] else 'COMPLETE_UNIFORM_NETWORK_REQUIRES_JUNCTION_ASSESSMENT',
                width_construction='NOT_RUN',electrical_intent='NOT_ESTABLISHED'))
    assigned=[sid for p in paths for sid in p['source_ids']]
    assert len(set(assigned))==len(assigned) and set(seed_ids)<=set(assigned)
    return sorted(paths,key=lambda p:p['path_id'])
