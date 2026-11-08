"""Explicit source-bound PCB selection; preserve native atoms and drawing order.

This intake transformation removes drawing-sheet operations, not copper within
the PCB. It neither flattens polarity nor clips, grows or repairs any geometry.
"""
import re
from shapely import to_wkb
from shapely.geometry import LineString, Polygon
from shapely.ops import polygonize, unary_union
from shapely.prepared import prep
from . import pipeline as p

POLICY = 'EXPLICIT_NATIVE_OUTLINE_PCB_ARTWORK_ONLY/1'
REGISTERED = {
    '3020212866': dict(
        selected='a-top.art.gbr',
        source_sha256='9638cf0abfb784c473d2d53e54ba79e593e37ecd74f8b9af433913cb4eb32188',
        outline_name='a-outline.art.gbr',
        outline_source_sha256='8aa58ccd17d4755478e3d25f7c6e896b7f6ae6430753d8dc956a01a5d0d964a9',
        outline_geometry_sha256='7652211583c64a60c0a5dee7fe95194a8a59af820cfc7ec46602f2e9fef4c9ce',
        authorization='PCB artwork only; exclude drawing sheet',
    ),
}


def capture(run, root, blobs, inventory):
    matches = [spec for board, spec in REGISTERED.items()
               if root.name == board or p.digest(blobs[inventory['selected']]) == spec['source_sha256']]
    if not matches:
        return
    if len(matches) != 1:
        raise ValueError('PCB_SCOPE_SOURCE_INTENT_AMBIGUOUS')
    spec = matches[0]
    if (inventory['selected'] != spec['selected'] or
            p.digest(blobs[inventory['selected']]) != spec['source_sha256'] or
            spec['outline_name'] not in blobs or
            p.digest(blobs[spec['outline_name']]) != spec['outline_source_sha256']):
        raise ValueError('PCB_SCOPE_APPROVED_INPUT_OR_OUTLINE_CHANGED')
    (run / 'pcb_outline.gbr').write_bytes(blobs[spec['outline_name']])
    p.save(run / 'PCB_SCOPE.json', dict(policy=POLICY, contract=spec))


def captured(run):
    path = run / 'PCB_SCOPE.json'
    outline = run / 'pcb_outline.gbr'
    if not path.exists() and not outline.exists():
        return None
    value = p.load(path)
    if value.get('policy') != POLICY or value.get('contract') not in REGISTERED.values():
        raise ValueError('PCB_SCOPE_CAPTURED_AUTHORIZATION_CHANGED')
    body = outline.read_bytes()
    if p.digest(body) != value['contract']['outline_source_sha256']:
        raise ValueError('PCB_SCOPE_CAPTURED_OUTLINE_CHANGED')
    return value['contract'], body


def outline_geometry(raw, expected):
    native, _, _ = p.source_profile.parse_source(raw)
    lines = []
    for obj in native.objects:
        # Validate every primitive, including excluded drawing-sheet objects.
        p.source_profile.object_geometry(obj)
        if not obj.polarity_dark:
            continue
        if isinstance(obj, p.go.Line):
            lines.append(LineString([(obj.x1, obj.y1), (obj.x2, obj.y2)]))
        elif isinstance(obj, p.go.Arc):
            primitive = next(iter(obj.to_primitives()))
            points, _ = p.source_profile.arc_points(
                (primitive.x1, primitive.y1), (primitive.x2, primitive.y2),
                (primitive.cx, primitive.cy), primitive.clockwise)
            lines.append(LineString(points))
    matches = {}
    for poly in polygonize(unary_union(lines)):
        shell = Polygon(poly.exterior)
        body = to_wkb(shell)
        if p.digest(body) == expected:
            matches[body] = shell
    if len(matches) != 1:
        raise ValueError('PCB_SCOPE_BOUND_NATIVE_OUTLINE_NOT_UNIQUE')
    return next(iter(matches.values()))


def boundary_stroke(obj, outline):
    """Only the original native stroke centered on the mechanical boundary.

    It must subsequently be removed by the existing confirmed-frame predicate;
    this admits no copper extension, electrical trace or arbitrary boundary pad.
    """
    if isinstance(obj, p.go.Line):
        line = LineString([(obj.x1, obj.y1), (obj.x2, obj.y2)])
    elif isinstance(obj, p.go.Arc):
        primitive = next(iter(obj.to_primitives()))
        points, _ = p.source_profile.arc_points(
            (primitive.x1, primitive.y1), (primitive.x2, primitive.y2),
            (primitive.cx, primitive.cy), primitive.clockwise)
        line = LineString(points)
    else:
        return False
    return line.difference(outline.boundary.buffer(p.source_profile.SAG)).is_empty


def disable_objects(raw, parser, excluded):
    """Turn excluded plots into moves while keeping coordinates/modal state."""
    body = bytearray(raw)
    for start, end in sorted({tuple(parser.spans[i]) for i in excluded}):
        before = raw[start:end]
        after = re.sub(rb'D(0?)[13]\*', lambda m: b'D' + m[1] + b'2*', before)
        # Region delimiters become comments; all interior plots became moves.
        # Their endpoints and interpolation/aperture/polarity state survive.
        after = after.replace(b'G36*', b'G04*').replace(b'G37*', b'G04*')
        if len(after) != len(before) or after == before:
            raise ValueError('PCB_SCOPE_EXPLICIT_PLOT_REMOVAL_REQUIRED')
        body[start:end] = after
    return bytes(body)


def select(raw, outline_raw, contract):
    if (p.digest(raw) != contract['source_sha256'] or
            p.digest(outline_raw) != contract['outline_source_sha256']):
        raise ValueError('PCB_SCOPE_SOURCE_HASH_CHANGED')
    outline = outline_geometry(outline_raw, contract['outline_geometry_sha256'])
    native, parser, oracle = p.source_profile.parse_source(raw)
    shapes = [p.source_profile.object_geometry(o)[0] for o in native.objects]
    resolved = p.source_profile.ordered((g, o.polarity_dark)
                                       for g, o in zip(shapes, native.objects))
    boundary = prep(outline)
    keep = set()
    boundary_ordinals = []
    for i, (obj, shape) in enumerate(zip(native.objects, shapes)):
        if not obj.polarity_dark:
            continue
        if not boundary.intersects(shape):
            continue
        if boundary.covers(shape):
            keep.add(i)
            continue
        effective = shape.intersection(resolved)
        inside = effective.intersection(outline)
        outside = effective.difference(outline)
        if not inside.is_empty and not outside.is_empty:
            if not boundary_stroke(obj, outline):
                raise ValueError('PCB_SCOPE_POSITIVE_OBJECT_STRADDLES_OUTLINE:' + str(i))
            keep.add(i)
            boundary_ordinals.append(i)
            continue
        if not inside.is_empty:
            keep.add(i)
    if not keep:
        raise ValueError('PCB_SCOPE_NO_RETAINED_POSITIVE_ARTWORK')
    raw_positive = unary_union([shapes[i] for i in sorted(keep)])
    # Retain whole clear objects when needed, even if their footprint extends
    # outside the outline. Only their resolved effect on retained copper matters.
    keep.update(i for i, (obj, shape) in enumerate(zip(native.objects, shapes))
                if not obj.polarity_dark and shape.intersects(raw_positive))
    excluded = set(range(len(native.objects))) - keep
    excluded_spans = {tuple(parser.spans[i]) for i in excluded}
    if any(tuple(parser.spans[i]) in excluded_spans for i in keep):
        raise ValueError('PCB_SCOPE_SHARED_NATIVE_ATOM_HAS_MIXED_DISPOSITION')
    selected = disable_objects(raw, parser, excluded)
    from .source_assembly import prove_atoms
    retained = prove_atoms(raw, selected, excluded)
    actual, _, _ = p.source_profile.parse_source(selected)
    copper = p.source_profile.ordered((p.source_profile.object_geometry(o)[0], o.polarity_dark)
                                     for o in actual.objects)
    # A boundary marker is drawn centered on the contour and therefore has
    # original material on both sides. Keep its entire native atom for the
    # separate, mandatory confirmed-frame removal instead of cutting it in half.
    domain = outline if not boundary_ordinals else outline.union(unary_union([shapes[i]for i in boundary_ordinals]))
    designated = resolved.intersection(domain)
    added = copper.difference(designated).area
    missing = designated.difference(copper).area
    distance = copper.hausdorff_distance(designated)
    # Native atoms above are byte-exact geometry. Overlay comparison also
    # retains the existing numerical limits; no new clearance/fill allowance.
    if added > p.EPS or missing > p.EPS or distance > p.source_profile.SAG:
        raise ValueError(f'PCB_SCOPE_RESOLVED_MATERIAL_CHANGED:{added}:{missing}:{distance}')
    proof = dict(policy=POLICY, authorization=contract['authorization'], contract=contract,
                 source_sha256=p.digest(raw), outline_source_sha256=p.digest(outline_raw),
                 outline_geometry_sha256=p.digest(to_wkb(outline)),
                 selected_source_sha256=p.digest(selected),
                 retained_original_ordinals=sorted(keep), excluded_original_ordinals=sorted(excluded),
                 native_objects=len(native.objects), retained_objects=len(keep),
                 excluded_objects=len(excluded), retained_atom_proofs=retained,
                 boundary_marker_original_ordinals=boundary_ordinals,
                 boundary_marker_disposition='MUST_BE_REMOVED_BY_CONFIRMED_ENCLOSURE_PREDICATE',
                 boundary_centerline_fidelity_mm=p.source_profile.SAG,
                 resolved_geometry_sha256=p.digest(to_wkb(copper)),
                 resolved_comparison=dict(added_area_mm2=added,missing_area_mm2=missing,
                     hausdorff_mm=distance,area_epsilon_mm2=p.EPS,
                     geometry_fidelity_mm=p.source_profile.SAG),
                 exact_retained_native_atoms=True, original_order_preserved=True,
                 source_core_cutting=False, polarity_flattening=False, growth=False)
    return selected, proof
