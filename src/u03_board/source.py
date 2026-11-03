"""Whole-source T04 admission. No crop, route fitting or electrical inference."""
import math
from collections import Counter
import sexpdata
from shapely import STRtree, from_wkb, to_wkb
from shapely.geometry import LineString
from shapely.ops import unary_union
from src.native_inventory import arc_points
from src.native_reference import one
from src.source_junction_paths import junction_source_paths
from src.parallel_trace_relations import parallel_relation, relation_groups
from src.stage_abi.store import canonical, digest
from src.stage_abi.contracts import finite_json

TRACE_KINDS = {'segment', 'arc', 'gr_line', 'gr_arc'}


def route_evidence(value):
    """Translate the native helper's tuple pairs at the U03 evidence boundary.

    This changes representation only. The shared artifact validator remains
    strict; arbitrary Python objects, sets and nonfinite values still reject.
    """
    if type(value) in (list,tuple):value=[route_evidence(v) for v in value]
    elif type(value) is dict:value={k:route_evidence(v) for k,v in value.items()}
    finite_json(value)
    return value


def native_rows(raw, manifest):
    rows = []
    for m in manifest:
        if m['kind'] not in TRACE_KINDS:
            continue
        sid = m['id']; start, end = m['source_span']
        if sid != f'{digest(raw)}:bytes:{start}:{end}':
            raise ValueError('U03_NATIVE_SOURCE_ID_CHANGED:' + sid)
        fragment = raw[start:end]; node = sexpdata.loads(fragment.decode())
        kind = str(node[0]); a, b = one(node, 'start'), one(node, 'end')
        width = float(one(node, 'width', one(one(node, 'stroke', []), 'width', [0]))[0])
        # Graphic strokes use the nested stroke syntax.
        if kind.startswith('gr_'):
            stroke = next((n for n in node if isinstance(n, list) and str(n[0]) == 'stroke'), [])
            width = float(one(stroke, 'width', [0])[0])
        if kind != m['kind'] or list(map(str, one(node, 'layer'))) != ['F.Cu'] or not math.isfinite(width) or width <= 0 or width != m['trace_width_mm']:
            raise ValueError('U03_NATIVE_WIDTH_OR_ROLE_CHANGED:' + sid)
        points = arc_points(tuple(a), tuple(one(node, 'mid')), tuple(b)) if kind.endswith('arc') else [a, b]
        rows.append(dict(source_id=sid, kind=kind, width_mm=width,
                         endpoints_decimal_mm=[[str(v) for v in p] for p in (a, b)],
                         route_points_mm=[list(p) for p in points],
                         source_wkb_sha256=m['geometry_sha256'],
                         native_bytes_sha256=digest(fragment)))
    if not rows:
        raise ValueError('U03_NATIVE_TRACE_INVENTORY_EMPTY')
    return rows


def qualify(raw, manifest, original_blobs, current_blobs, *, selection=None):
    """Account for every stroke and geometrically bind paths, coverage and groups.

    Reuse the established junction-path definition: maximal native uniform
    continuation, with exact original junction and width-transition boundaries.
    No source primitive is split. Ambiguous branch continuations terminate at
    the original junction and remain explicit; no electrical path is inferred.
    """
    meta = {r['id']: r for r in manifest}
    if len(meta) != len(manifest) or set(original_blobs) != set(meta) or set(current_blobs) != set(meta):
        raise ValueError('U03_COMPLETE_CURRENT_SCENE_REQUIRED')
    for sid, row in meta.items():
        if digest(original_blobs[sid]) != row['geometry_sha256']:
            raise ValueError('U03_SOURCE_GEOMETRY_CHANGED:' + sid)
    native = native_rows(raw, manifest)
    for r in native:
        if original_blobs[r['source_id']] != current_blobs[r['source_id']]:
            raise ValueError('U03_CHANGED_T03_ROUTES_NOT_QUALIFIED:' + r['source_id'])
    ids = sorted(meta); shapes = [from_wkb(current_blobs[s]) for s in ids]
    tree = STRtree(shapes); byid = dict(zip(ids, shapes)); bynative = {r['source_id']: r for r in native}
    supported = [r for r in native if r['kind'] in ('segment', 'arc')]
    paths = route_evidence(junction_source_paths(supported, [r['source_id'] for r in supported])) if supported else []
    dispositions = []; admitted = []; unsupported = []
    for path in paths:
        members = set(path['source_ids']); core = unary_union([byid[s] for s in sorted(members)])
        neighbors = [ids[int(i)] for i in tree.query(core, predicate='intersects') if ids[int(i)] not in members]
        # Exact geometry aliases in a route are represented together. They can
        # never conceal that same route's independently exposed copper.
        covering = unary_union([byid[s] for s in neighbors])
        covered = covering.covers(core)
        reason = 'FULLY_COVERED_BY_OTHER_PREDECESSOR_COPPER' if covered else None
        status = 'KEEP_FULLY_COVERED' if covered else 'ADMIT_COMPLETE_NATIVE_ROUTE'
        if not covered and path['route_type'] == 'DEGENERATE_SOURCE_STROKE_CONTEXT':
            status = 'UNSUPPORTED'; reason = 'DEGENERATE_EXPOSED_STROKE_NOT_A_COMPLETE_ROUTE'
        record = dict(path=path, disposition=status, reason=reason,
                      original_core_sha256=digest(to_wkb(core)), original_core_area_mm2=core.area,
                      exposed_area_mm2=core.difference(covering).area,
                      coverage_source_ids=neighbors,
                      coverage_union_sha256=digest(to_wkb(covering)))
        dispositions.append(record)
        if status == 'ADMIT_COMPLETE_NATIVE_ROUTE': admitted.append(path)
        elif status == 'UNSUPPORTED': unsupported.append(record)
    for r in native:
        if r['kind'] in ('segment', 'arc'): continue
        record = dict(source_ids=[r['source_id']], disposition='UNSUPPORTED', reason='GRAPHIC_STROKE_WIDTH_FAMILY_NOT_QUALIFIED')
        dispositions.append(record); unsupported.append(record)
    # Source-derived immediate parallel relationships, with finite-copper
    # cross-section blockers. Curves remain full-route clearance operands.
    owner = {sid: p['path_id'] for p in admitted for sid in p['source_ids']}
    entries = [r for r in native if r['kind'] == 'segment' and r['source_id'] in owner
               and r['route_points_mm'][0] != r['route_points_mm'][-1]]
    lines = [LineString(r['route_points_mm']) for r in entries]; lt = STRtree(lines)
    relations = []; blocked = []; edges = set()
    path_members = {p['path_id']: set(p['source_ids']) for p in admitted}
    for i, a in enumerate(entries):
        aid = a['source_id']; pa = owner[aid]
        for j in sorted(int(v) for v in lt.query(lines[i].buffer(.5)) if int(v) > i):
            b = entries[j]; bid = b['source_id']; pb = owner[bid]
            if pa == pb or byid[aid].intersects(byid[bid]): continue
            rel = parallel_relation(a['route_points_mm'], b['route_points_mm'])
            if rel is None: continue
            cross = LineString(rel['midpoint_cross_section_mm']).difference(byid[aid].union(byid[bid]))
            excluded = path_members[pa] | path_members[pb]
            blockers = sorted(ids[int(k)] for k in tree.query(cross, predicate='intersects') if ids[int(k)] not in excluded)
            row = dict(source_a=aid, source_b=bid, path_a=pa, path_b=pb, **rel,
                       blocker_source_ids=blockers, finite_source_gap_mm=byid[aid].distance(byid[bid]))
            (blocked if blockers else relations).append(row)
            if not blockers: edges.add(tuple(sorted((pa, pb))))
    groups = [dict(group_id='WG-' + digest(canonical(members))[:20], members=['route:' + p for p in members])
              for members in relation_groups([p['path_id'] for p in admitted], sorted(edges))]
    assigned = [s for p in paths for s in p['source_ids']] + [r['source_id'] for r in native if r['kind'] not in ('segment', 'arc')]
    if sorted(assigned) != sorted(bynative) or len(assigned) != len(set(assigned)):
        raise ValueError('U03_TRACE_PARTITION_INCOMPLETE')
    result=dict(schema='u03-native-width-admission/1', source_sha256=digest(raw), native_rows=native,
                source_objects=len(meta), trace_occurrences=len(native), paths=dispositions,
                admitted_paths=admitted, groups=groups, relations=relations, blocked_relations=blocked,
                unsupported=unsupported, classifications=dict(Counter(p['disposition'] for p in dispositions)),
                complete_trace_coverage=True, protected_source_ids=sorted(set(meta) - set(owner)),
                route_definition='Existing source_junction_paths; exact native boundaries, no fitting or electrical inference',
                scope='Complete current F.Cu; fixed paths, uniform original widths, full nominal/envelope checking; no general router')
    if selection is not None:
        from .selection import restrict_width
        result=restrict_width(result,current_blobs,selection)
    return result


def require_admitted(report):
    if report['unsupported']:
        raise ValueError('U03_T04_SOURCE_FAMILY_NOT_QUALIFIED:' + str(report['unsupported']))
    if not report['admitted_paths']:
        raise ValueError('U03_T04_NO_EXPOSED_COMPLETE_ROUTES')
