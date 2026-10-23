"""Build compact, source-bound local copper-neighborhood comparisons for review."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
from collections import Counter, defaultdict
from xml.sax.saxutils import escape
import sexpdata

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.ingestion_files import sha
from tools.build_identity_review import source_object, child, xy
from src.copper_correspondence import trace_correspondence, polygon_correspondence

DATASET_ID = 'client:szu-comm:3020301113b:intake-20261021:v1'
SOURCE_PATHS = {'before': 'ORG/top.kicad_pcb', 'after': 'EDIT/top_layer.kicad_pcb'}
GROUP_RADIUS_MM = 1.8
CONTEXT_RADIUS_MM = 1.9


def center(shape):
    points = shape['points']
    if not points:
        return None
    return (sum(x for x, _ in points) / len(points),
            sum(y for _, y in points) / len(points))


def draw(shape, tx, ty, scale, color, opacity=1.0, selected=False):
    points = shape['points']
    if not points:
        return ''
    coords = [(tx + x * scale, ty + y * scale) for x, y in points]
    width = max(1.0 if selected else 0.65, shape['width'] * scale)
    if shape['shape'] == 'circle' and len(points) > 1:
        cx, cy = coords[0]
        radius = math.dist(points[0], points[1]) * scale
        fill = color if shape.get('fill') in ('yes', 'solid') else 'none'
        stroke = 'none' if fill != 'none' else color
        rendered = (f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{radius:.2f}" fill="{fill}" '
                f'stroke="{stroke}" stroke-width="{width:.2f}" opacity="{opacity}"/>')
    else:
        pts = ' '.join(f'{x:.2f},{y:.2f}' for x, y in coords)
        fill = color if shape.get('fill') in ('yes', 'solid') else 'none'
        if shape['shape'] == 'polygon':
            rendered = (f'<polygon points="{pts}" fill="{fill}" stroke="{color}" '
                        f'stroke-width="{width:.2f}" opacity="{opacity}"/>')
        else:
            rendered = (f'<polyline points="{pts}" fill="none" stroke="{color}" '
                        f'stroke-width="{width:.2f}" stroke-linecap="round" '
                        f'stroke-linejoin="round" opacity="{opacity}"/>')
    identity = shape.get('source_identity')
    side = shape.get('source_side')
    if identity is not None and side is not None:
        escaped_identity = escape(str(identity)).replace('"', '&quot;')
        return (f'<g data-source-identity="{escaped_identity}" '
                f'data-source-side="{escape(str(side))}">{rendered}</g>')
    return rendered


def render_group(group, side_shapes, context_shapes, out_path):
    width, height, pane_w, pane_h = 1600, 900, 744, 720
    x0, y0 = group['center_mm']
    crop = CONTEXT_RADIUS_MM
    min_x, max_x = x0 - crop, x0 + crop
    min_y, max_y = y0 - crop, y0 + crop
    scale = min((pane_w - 52) / (max_x - min_x), (pane_h - 80) / (max_y - min_y))
    pad_x = (pane_w - (max_x - min_x) * scale) / 2
    pad_y = (pane_h - (max_y - min_y) * scale) / 2
    panes = [(24, 112, 'ORG · before', 'before'),
             (832, 112, 'EDIT · enhanced', 'after')]
    bits = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img">',
            '<defs><clipPath id="left-crop"><rect x="24" y="112" width="744" height="720" rx="8"/></clipPath><clipPath id="right-crop"><rect x="832" y="112" width="744" height="720" rx="8"/></clipPath></defs>',
            f'<rect x="0" y="0" width="{width}" height="{height}" fill="#f5f8f9"/>',
            f'<text x="28" y="42" font-family="Arial,sans-serif" font-size="26" font-weight="700" fill="#21323e">{escape(group["title"])}</text>',
            f'<text x="28" y="72" font-family="Arial,sans-serif" font-size="15" fill="#506672">Same source-coordinate crop · X {x0:.3f} mm, Y {y0:.3f} mm · {group["pair_count"]} matched objects · summed object area increase ≈ {group["added_area_mm2"]:.3f} mm²</text>']
    for px, py, label, side in panes:
        bits.append(f'<rect x="{px}" y="{py}" width="{pane_w}" height="{pane_h}" rx="8" fill="#fff" stroke="#c9d5da"/>')
        bits.append(f'<text x="{px + 18}" y="{py + 30}" font-family="Arial,sans-serif" font-size="18" font-weight="700" fill="#25343e">{label}</text>')
        tx = px + pad_x - min_x * scale
        ty = py + pad_y - min_y * scale + 28
        bits.append(f'<g clip-path="url(#{"left-crop" if side == "before" else "right-crop"})">')
        for shape in context_shapes[side]:
            bits.append(draw(shape, tx, ty, scale, '#c4ced2', .55))
        for shape in side_shapes[side]:
            bits.append(draw(shape, tx, ty, scale, '#b9573f' if side == 'before' else '#14828a', .96, True))
        bits.append('</g>')
    bits.extend([
            '<text x="800" y="862" text-anchor="middle" font-family="Arial,sans-serif" font-size="14" fill="#506672">Color: registered round-feature and exact-coordinate trace pairs · gray: nearby F.Cu context</text>',
        '<text x="800" y="884" text-anchor="middle" font-family="Arial,sans-serif" font-size="13" fill="#7b4c34">Round-feature centers are mutual-unique within the stated registration tolerance; radius changes are measured separately. Object-area sums do not subtract overlap.</text>',
        '</svg>'])
    out_path.write_text(''.join(bits))


def _mask_keypoints(raw, rows):
    """Return translation-invariant F.Mask shape descriptors and their centers."""
    anchors = []
    for row in rows:
        if 'F.Mask' not in row.get('layers', []) or row['kind'] not in ('gr_circle', 'gr_poly'):
            continue
        start, end = row['source_span']
        node = sexpdata.loads(raw[start:end].decode('utf-8'))
        if row['kind'] == 'gr_circle':
            center_mm = xy(child(node, 'center'))
            edge = xy(child(node, 'end'))
            radius = math.dist(center_mm, edge)
            descriptor = ('circle', round(radius, 5))
        else:
            pts_node = child(node, 'pts')
            points = [xy(item) for item in pts_node[1:]
                      if isinstance(item, list) and item and str(item[0]) == 'xy']
            if len(points) < 4:
                continue
            xs, ys = [p[0] for p in points], [p[1] for p in points]
            center_mm = ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2)
            # Sorting the extents makes the descriptor independent of a 90-degree
            # width/height ordering while retaining polygon vertex count.
            extents = tuple(sorted((round(max(xs) - min(xs), 5),
                                    round(max(ys) - min(ys), 5))))
            descriptor = ('poly', extents, len(points))
        fill = child(node, 'fill')
        fill_token = str(fill[1]) if fill and len(fill) > 1 else 'none'
        anchors.append({'identity': row['id'], 'descriptor': (*descriptor, fill_token),
                        'center_mm': center_mm})
    return anchors


def _fit_translation_from_anchors(before, after, tolerance_mm=0.001, vote_resolution_mm=0.001):
    """Fit EDIT→ORG translation from shape descriptors that exclude coordinates."""
    before_by, after_by = defaultdict(list), defaultdict(list)
    for anchor in before:
        before_by[anchor['descriptor']].append(anchor)
    for anchor in after:
        after_by[anchor['descriptor']].append(anchor)
    votes = Counter()
    for descriptor, before_rows in before_by.items():
        for left in before_rows:
            for right in after_by.get(descriptor, []):
                bx, by = left['center_mm']
                ax, ay = right['center_mm']
                votes[(round((ax - bx) / vote_resolution_mm) * vote_resolution_mm,
                       round((ay - by) / vote_resolution_mm) * vote_resolution_mm)] += 1
    if not votes:
        raise ValueError('No shared F.Mask geometric keypoint descriptors')
    delta, support = min(votes.items(), key=lambda item: (-item[1], item[0]))
    before_candidates, after_candidates = defaultdict(list), defaultdict(list)
    for descriptor, before_rows in before_by.items():
        for left in before_rows:
            for right in after_by.get(descriptor, []):
                ax, ay = right['center_mm']
                bx, by = left['center_mm']
                residual = math.hypot((ax - delta[0]) - bx, (ay - delta[1]) - by)
                if residual <= tolerance_mm:
                    before_candidates[left['identity']].append((right, residual))
                    after_candidates[right['identity']].append((left, residual))
    inliers = []
    for left in before:
        candidates = before_candidates.get(left['identity'], [])
        if len(candidates) != 1:
            continue
        right, residual = candidates[0]
        reverse = after_candidates.get(right['identity'], [])
        if len(reverse) == 1:
            inliers.append({'before_identity': left['identity'],
                            'after_identity': right['identity'],
                            'residual_mm': residual})
    if len(inliers) < 3:
        raise ValueError('F.Mask registration has fewer than three unique keypoint inliers')
    # A least-squares rigid fit over the translation-selected invariant anchors
    # reports whether any small rotation is visible; scale is intentionally fixed.
    lookup_before = {a['identity']: a for a in before}
    lookup_after = {a['identity']: a for a in after}
    xs = [lookup_before[p['before_identity']]['center_mm'] for p in inliers]
    ys = [lookup_after[p['after_identity']]['center_mm'] for p in inliers]
    mx = sum(p[0] for p in xs) / len(xs); my = sum(p[1] for p in xs) / len(xs)
    nx = sum(p[0] for p in ys) / len(ys); ny = sum(p[1] for p in ys) / len(ys)
    dot = cross = 0.0
    for (bx, by), (ax, ay) in zip(xs, ys):
        bx -= mx; by -= my; ax -= nx; ay -= ny
        dot += ax * bx + ay * by
        cross += ax * by - ay * bx
    angle = math.atan2(cross, dot) if dot or cross else 0.0
    fitted_cos, fitted_sin = math.cos(angle), math.sin(angle)
    tx = mx - (fitted_cos * nx - fitted_sin * ny)
    ty = my - (fitted_sin * nx + fitted_cos * ny)
    residuals = []
    for (bx, by), (ax, ay) in zip(xs, ys):
        mapped = (fitted_cos * ax - fitted_sin * ay + tx,
                  fitted_sin * ax + fitted_cos * ay + ty)
        residuals.append(math.dist((bx, by), mapped))
    return {
        'method': 'F.Mask shape-descriptor translation voting, followed by least-squares rigid fit on mutual-unique keypoint centers',
        'source_layer': 'F.Mask only; F.Cu excluded from transform fitting',
        'descriptor': 'primitive kind, size/extents, vertex count and fill; source coordinates excluded',
        'transform_model': 'rigid 2D transform; scale fixed at 1',
        'translation_vote_mm_after_minus_before': list(delta),
        'fitted_after_to_before': {'rotation_radians': angle, 'translation_mm': [tx, ty]},
        'vote_support': support,
        'inlier_count': len(inliers),
        'before_anchor_count': len(before), 'after_anchor_count': len(after),
        'ambiguous_or_unmatched_before_count': len(before) - len(inliers),
        'max_inlier_residual_mm': max(residuals),
        'median_inlier_residual_mm': sorted(residuals)[len(residuals) // 2],
        'tolerance_mm': tolerance_mm,
        'next_translation_votes': [
            {'after_minus_before_mm': list(offset), 'count': count}
            for offset, count in sorted(votes.items(), key=lambda item: (-item[1], item[0]))[:10]
        ],
        'keypoint_pairs': inliers,
        'limitations': [
            'The fit uses geometric F.Mask landmarks only and does not establish pad, net or electrical identity.',
            'The source files share orientation; scale is fixed and no mirror hypothesis is tested.',
            'F.Mask geometry is used as an invariant registration layer, not as proof of copper identity.'
        ]
    }


def _transform_point(point, registration):
    fit = registration['fitted_after_to_before']
    angle = fit['rotation_radians']
    tx, ty = fit['translation_mm']
    x, y = point
    return (math.cos(angle) * x - math.sin(angle) * y + tx,
            math.sin(angle) * x + math.cos(angle) * y + ty)


def _center_pairing_audit(before_centers, after_centers, before_ids, after_ids, tolerance_mm):
    """Enumerate center candidates and keep duplicate/nearby choices unresolved."""
    left = defaultdict(list); right = defaultdict(list)
    for i, center_mm in enumerate(before_centers):
        for j, other in enumerate(after_centers):
            distance = math.dist(center_mm, other)
            if distance <= tolerance_mm:
                left[i].append((j, distance)); right[j].append((i, distance))
    pairs = [(i, left[i][0][0], left[i][0][1]) for i in range(len(before_centers))
             if len(left[i]) == 1 and len(right[left[i][0][0]]) == 1]
    return pairs, {
        'before_object_count': len(before_centers), 'after_object_count': len(after_centers),
        'mutual_unique_pair_count': len(pairs), 'tolerance_mm': tolerance_mm,
        'ambiguous_before': [before_ids[i] for i in range(len(before_centers)) if len(left[i]) > 1],
        'one_sided_before': [before_ids[i] for i in range(len(before_centers))
                             if len(left[i]) == 1 and len(right[left[i][0][0]]) > 1],
        'unmatched_before': [before_ids[i] for i in range(len(before_centers)) if not left[i]],
        'ambiguous_after': [after_ids[i] for i in range(len(after_centers)) if len(right[i]) > 1],
        'one_sided_after': [after_ids[i] for i in range(len(after_centers))
                            if len(right[i]) == 1 and len(left[right[i][0][0]]) > 1],
        'unmatched_after': [after_ids[i] for i in range(len(after_centers)) if not right[i]],
    }


def _mutual_unique_pairs(before_centers, after_centers, tolerance_mm):
    """Return only one-to-one center candidates; duplicate/nearby choices stay open."""
    pairs, _ = _center_pairing_audit(before_centers, after_centers,
                                     list(range(len(before_centers))),
                                     list(range(len(after_centers))), tolerance_mm)
    return pairs


def _circle_links(raws, probes, registration=None, tolerance_mm=0.001, return_audit=False):
    by_side = {'before': [], 'after': []}
    for side in ('before', 'after'):
        for row in probes[side]:
            if row['kind'] != 'gr_circle' or 'F.Cu' not in row.get('layers', []):
                continue
            start, end = row['source_span']
            node = sexpdata.loads(raws[side][start:end].decode('utf-8'))
            c, edge = xy(child(node, 'center')), xy(child(node, 'end'))
            fill = child(node, 'fill')
            if not fill or len(fill) < 2 or str(fill[1]) not in ('yes', 'solid'):
                continue
            by_side[side].append((row, c, math.dist(c, edge)))
    links = []
    before, after = by_side['before'], by_side['after']
    after_in_before = [_transform_point(row[1], registration) if registration else row[1]
                       for row in after]
    pairs, audit = _center_pairing_audit(
        [row[1] for row in before], after_in_before,
        [row[0]['id'] for row in before], [row[0]['id'] for row in after], tolerance_mm)
    for bi, ai, displacement in pairs:
        br, center_mm, rb = before[bi]
        ar, _, ra = after[ai]
        if rb <= 0 or ra <= 0:
            continue
        links.append({'before_identity': br['id'], 'after_identity': ar['id'],
                      'kind': 'gr_circle',
                      'match_basis': f'mutual-unique registered F.Cu circle center within {tolerance_mm:g} mm; radius excluded from key',
                      'center_displacement_mm': displacement,
                      'before_radius_mm': rb, 'after_radius_mm': ra,
                      'added_area_mm2': math.pi * (ra * ra - rb * rb),
                      'review_class': 'registered-center candidate; radius compared separately',
                      '_center': center_mm})
    return (links, audit) if return_audit else links


def _rectangle_links(raws, probes, registration=None, tolerance_mm=0.001):
    by_side = {'before': [], 'after': []}
    for side in ('before', 'after'):
        for row in probes[side]:
            if row['kind'] != 'gr_poly' or 'F.Cu' not in row.get('layers', []):
                continue
            start, end = row['source_span']
            node = sexpdata.loads(raws[side][start:end].decode('utf-8'))
            pts_node = child(node, 'pts')
            points = [xy(item) for item in pts_node[1:]
                      if isinstance(item, list) and item and str(item[0]) == 'xy']
            if len(points) < 4:
                continue
            min_x, max_x = min(p[0] for p in points), max(p[0] for p in points)
            min_y, max_y = min(p[1] for p in points), max(p[1] for p in points)
            corners = {(min_x, min_y), (min_x, max_y), (max_x, min_y), (max_x, max_y)}
            if not all(any(math.dist(point, corner) < 1e-6 for point in points) for corner in corners):
                continue
            fill = child(node, 'fill')
            if not fill or len(fill) < 2 or str(fill[1]) not in ('yes', 'solid'):
                continue
            center_mm = ((min_x + max_x) / 2, (min_y + max_y) / 2)
            by_side[side].append((row, center_mm, points))
    links = []
    from shapely.geometry import Polygon
    before, after = by_side['before'], by_side['after']
    after_in_before = [_transform_point(row[1], registration) if registration else row[1]
                       for row in after]
    pairs = _mutual_unique_pairs([row[1] for row in before], after_in_before, tolerance_mm)
    for bi, ai, displacement in pairs:
        br, center_mm, bp = before[bi]
        ar, _, ap = after[ai]
        before_area, after_area = Polygon(bp).area, Polygon(ap).area
        links.append({'before_identity': br['id'], 'after_identity': ar['id'],
                      'kind': 'gr_poly',
                      'match_basis': f'mutual-unique registered center within {tolerance_mm:g} mm for filled axis-aligned rectangles',
                      'center_displacement_mm': displacement,
                      'before_area_mm2': before_area, 'after_area_mm2': after_area,
                      'added_area_mm2': after_area - before_area,
                      'review_class': 'registered-center rectangle candidate; bounds compared separately',
                      '_center': center_mm})
    return links


def _registered_trace_inputs(raws, probes, registration):
    """Decode F.Cu centerlines and transform EDIT geometry into ORG coordinates."""
    from shapely.geometry import LineString
    result = {'before': [], 'after': []}
    excluded = {'before': [], 'after': []}
    for side in ('before', 'after'):
        for row in probes[side]:
            if row['kind'] not in ('segment', 'arc') or 'F.Cu' not in row.get('layers', []):
                continue
            try:
                shape = source_object(raws[side], row)
                points = shape['points']
                if side == 'after':
                    points = [_transform_point(point, registration) for point in points]
                geometry = LineString(points)
                if not geometry.is_valid or geometry.length <= 0:
                    raise ValueError('degenerate centerline')
            except (ValueError, TypeError, IndexError, KeyError) as error:
                excluded[side].append({'identity': row['id'], 'reason': str(error)})
                continue
            result[side].append({'identity': row['id'], 'geometry': geometry,
                                 'width_mm': shape['width'], 'kind': row['kind']})
    return result, excluded


def _registered_polygon_inputs(raws, probes, registration):
    """Decode all filled F.Cu gr_poly shapes; do not force rectangle semantics."""
    from shapely.geometry import Polygon
    result = {'before': [], 'after': []}
    excluded = {'before': [], 'after': []}
    for side in ('before', 'after'):
        for row in probes[side]:
            if row['kind'] != 'gr_poly' or 'F.Cu' not in row.get('layers', []):
                continue
            try:
                start, end = row['source_span']
                node = sexpdata.loads(raws[side][start:end].decode('utf-8'))
                fill = child(node, 'fill')
                token = str(fill[1]) if fill and len(fill) > 1 else 'none'
                if token not in ('yes', 'solid'):
                    continue
                pts_node = child(node, 'pts')
                points = [xy(item) for item in pts_node[1:]
                          if isinstance(item, list) and item and str(item[0]) == 'xy']
                if side == 'after':
                    points = [_transform_point(point, registration) for point in points]
                geometry = Polygon(points)
                if not geometry.is_valid or geometry.is_empty or geometry.area <= 0:
                    raise ValueError('invalid or zero-area filled polygon')
            except (ValueError, TypeError, IndexError, KeyError) as error:
                excluded[side].append({'identity': row['id'], 'reason': str(error)})
                continue
            result[side].append({'identity': row['id'], 'geometry': geometry,
                                 'kind': row['kind']})
    return result, excluded


def _trace_area(shape):
    from shapely.geometry import LineString
    if shape['shape'] != 'line' or len(shape['points']) < 2:
        return 0.0
    return LineString(shape['points']).buffer(shape['width'] / 2, quad_segs=8).area


def _trace_touches_terminal(trace, terminal):
    from shapely.geometry import LineString, Point
    shape = trace if trace else None
    if not shape or shape.get('shape') != 'line' or len(shape.get('points', [])) < 2:
        return False
    circle = terminal.get('points', [])
    if len(circle) < 2:
        return False
    center_point = Point(*circle[0])
    radius = math.dist(circle[0], circle[1])
    return LineString(shape['points']).distance(center_point) <= radius + shape['width'] / 2 + 0.015


def choose_groups(entries, circle_links, rectangle_links, shapes, count):
    located = []
    for entry in [*entries, *circle_links, *rectangle_links]:
        shape = shapes.get(('before', entry['before_identity']))
        pos = entry.get('_center') or (center(shape) if shape else None)
        if not pos:
            continue
        if 'added_area_mm2' not in entry:
            entry.setdefault('match_basis', 'same kind, layer, net code and defining coordinates')
            before = _trace_area(shape)
            after = _trace_area(shapes.get(('after', entry['after_identity']), {}))
            entry['added_area_mm2'] = after - before
        located.append((entry, pos[0], pos[1]))
    candidates = []
    for entry, x, y in located:
        members = [row for row in located if math.hypot(row[1] - x, row[2] - y) <= GROUP_RADIUS_MM]
        kinds = {kind: sum(row[0]['kind'] == kind for row in members)
                 for kind in {row[0]['kind'] for row in members}}
        circles = [row for row in members if row[0]['kind'] == 'gr_circle']
        rectangles = [row for row in members if row[0]['kind'] == 'gr_poly']
        if not ((len(circles) >= 12 or (len(circles) >= 5 and len(rectangles) >= 2))
                and kinds.get('segment', 0) >= 3):
            continue
        added_area = sum(row[0]['added_area_mm2'] for row in members)
        circle_area = sum(row[0]['added_area_mm2'] for row in circles)
        # Favor the visible terminal growth that motivated this review, with trace
        # growth as supporting evidence rather than allowing a long route to dominate.
        rank_score = circle_area + 0.15 * (added_area - circle_area)
        candidates.append((rank_score, kinds, x, y, members, circle_area, added_area))
    candidates.sort(key=lambda item: (-item[0], item[2], item[3]))
    selected = []
    for candidate in candidates:
        if any(math.hypot(candidate[2] - old[2], candidate[3] - old[3]) < GROUP_RADIUS_MM * 1.8
               for old in selected):
            continue
        selected.append(candidate)
        if len(selected) >= count:
            break
    return selected


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', type=Path, default=ROOT / 'dataset/szu-comm_3020301113B_intake_ready_20261021_v2')
    parser.add_argument('--identity-review', type=Path, default=ROOT / 'out/ingestion/manual_identity_review_szucomm')
    parser.add_argument('--output', type=Path, default=ROOT / 'out/ingestion/copper_enhancement_review')
    parser.add_argument('--registry-output', type=Path,
                        help='Write the updated registration recipe here instead of replacing the identity-review recipe')
    parser.add_argument('--audit-root', type=Path,
                        default=ROOT / 'out/ingestion/audits/20261024_org_and_screenshot_mapping_v1')
    parser.add_argument('--count', type=int, default=4)
    parser.add_argument('--center-tolerance-mm', type=float, default=0.001)
    args = parser.parse_args(argv)
    out = args.output.resolve()
    args.identity_review = args.identity_review.resolve()
    args.audit_root = args.audit_root.resolve()
    if not out.is_relative_to(ROOT / 'out'):
        raise SystemExit('Output must stay under checkout/out')
    if not args.audit_root.is_relative_to(ROOT / 'out'):
        raise SystemExit('Audit evidence must stay under checkout/out')
    out.mkdir(parents=True, exist_ok=True)
    image_dir = out / 'groups'
    image_dir.mkdir(parents=True, exist_ok=True)
    package = args.package.resolve()
    profile = json.loads((package / 'metadata/profile.json').read_text())
    profile_rows = {row['path']: row for row in profile['files']}
    raws = {}
    for side, rel in SOURCE_PATHS.items():
        raw = (package / 'raw' / rel).read_bytes()
        if hashlib.sha256(raw).hexdigest() != profile_rows[rel]['sha256']:
            raise SystemExit('Sealed source hash mismatch: ' + rel)
        raws[side] = raw
    probes = {side: json.loads((ROOT / f'out/ingestion/profile_materializations/{side}_identity_probe.json').read_text())['rows']
              for side in SOURCE_PATHS}
    probe_by = {side: {row['id']: row for row in rows} for side, rows in probes.items()}
    mask_before = _mask_keypoints(raws['before'], probes['before'])
    mask_after = _mask_keypoints(raws['after'], probes['after'])
    registration = _fit_translation_from_anchors(mask_before, mask_after)
    registration['source_files'] = {
        side: {'path': rel, 'sha256': profile_rows[rel]['sha256']}
        for side, rel in SOURCE_PATHS.items()
    }
    registration_path = out / 'registration.json'
    registration_path.write_text(json.dumps(registration, indent=2) + '\n')
    manifest = json.loads((args.identity_review / 'manifest.json').read_text())
    entries = [item for item in manifest['entries'] if item['review_class'] == 'exact' and item['layer'] == 'F.Cu']
    circle_links, circle_pair_audit = _circle_links(
        raws, probes, registration, args.center_tolerance_mm, return_audit=True)
    rectangle_links = _rectangle_links(raws, probes, registration, args.center_tolerance_mm)
    trace_inputs, invalid_trace_inputs = _registered_trace_inputs(raws, probes, registration)
    trace_result = trace_correspondence(trace_inputs['before'], trace_inputs['after'])
    polygon_inputs, invalid_polygon_inputs = _registered_polygon_inputs(raws, probes, registration)
    polygon_result = polygon_correspondence(polygon_inputs['before'], polygon_inputs['after'])
    shapes = {}
    for entry in [*entries, *circle_links, *rectangle_links]:
        for side, field in (('before', 'before_identity'), ('after', 'after_identity')):
            ident = entry[field]
            shapes[side, ident] = source_object(raws[side], probe_by[side][ident])
    chosen = choose_groups(entries, circle_links, rectangle_links, shapes, args.count)
    if len(chosen) < 3:
        raise SystemExit('Could not select at least three coherent F.Cu neighborhoods')
    group_records = []
    image_bindings = []
    all_ids = set()
    for i, (rank_score, kinds, x, y, located_members, circle_area_gain, score) in enumerate(chosen, 1):
        member_by_id = {row[0]['before_identity']: row[0] for row in located_members}
        terminal_members = [e for e in member_by_id.values() if e['kind'] == 'gr_circle']
        # Include exact trace links that geometrically touch a selected terminal even
        # when the rest of the trace places its centroid outside the seed neighborhood.
        for trace in entries:
            if trace['kind'] not in ('segment', 'arc'):
                continue
            before_shape = shapes.get(('before', trace['before_identity']))
            if any(_trace_touches_terminal(before_shape, shapes.get(('before', terminal['before_identity'])))
                   for terminal in terminal_members):
                member_by_id[trace['before_identity']] = trace
        for rectangle in rectangle_links:
            if math.hypot(rectangle['_center'][0] - x, rectangle['_center'][1] - y) <= GROUP_RADIUS_MM:
                member_by_id[rectangle['before_identity']] = rectangle
        members = sorted(member_by_id.values(),
                         key=lambda e: (e['kind'], e['before_identity']))
        kinds = {kind: sum(e['kind'] == kind for e in members) for kind in {e['kind'] for e in members}}
        score = sum(e.get('added_area_mm2', 0.0) for e in members)
        circle_area_gain = sum(e.get('added_area_mm2', 0.0) for e in members if e['kind'] == 'gr_circle')
        member_ids = {e['before_identity'] for e in members}
        after_ids = {e['after_identity'] for e in members}
        all_ids.update(member_ids)
        title = 'Round-feature and trace neighborhood'
        group = {'group_id': f'copper-{i:02d}', 'title': title,
                 'center_mm': [round(x, 6), round(y, 6)],
                 'grouping_rule': f'Mutual-unique F.Cu circle/rectangle centers after F.Mask registration, plus source-matched traces within {GROUP_RADIUS_MM:.2f} mm.',
                 'pair_count': len(members), 'kind_counts': kinds,
                 'added_area_mm2': round(score, 6),
                 'area_metric': 'Sum of per-object filled-circle and stroked-path area deltas; overlaps are not subtracted.',
                 'terminal_added_area_mm2': round(circle_area_gain, 6),
                 'review_status': 'UNREVIEWED', 'image_file': f'copper-group-{i:02d}.svg',
                 'members': [{k: e[k] for k in ('before_identity', 'after_identity', 'kind', 'review_class', 'match_basis', 'center_displacement_mm', 'before_width_mm', 'after_width_mm', 'stroke_width_changed', 'before_radius_mm', 'after_radius_mm', 'before_area_mm2', 'after_area_mm2', 'added_area_mm2') if k in e}
                             for e in members]}
        # Include all supported nearby primitives in gray so the selected links read as a board region.
        side_draw = {'before': [], 'after': []}; context_draw = {'before': [], 'after': []}
        for side in ('before', 'after'):
            for row in probes[side]:
                if 'F.Cu' not in row.get('layers', []):
                    continue
                ident = row['id']
                try:
                    shape = shapes.get((side, ident)) or source_object(raws[side], row)
                except (ValueError, TypeError, IndexError, KeyError):
                    continue
                if not shape['points']:
                    continue
                shape['source_identity'] = ident
                shape['source_side'] = side
                pts = shape['points']
                bounds = row.get('bounds_mm') or [min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts)]
                if bounds[0] > x + CONTEXT_RADIUS_MM or bounds[2] < x - CONTEXT_RADIUS_MM or bounds[1] > y + CONTEXT_RADIUS_MM or bounds[3] < y - CONTEXT_RADIUS_MM:
                    continue
                if ident in (member_ids if side == 'before' else after_ids):
                    side_draw[side].append(shape)
                else:
                    context_draw[side].append(shape)
        group_records.append(group)
        image_path = image_dir / group['image_file']
        render_group(group, side_draw, context_draw, image_path)
        image_bindings.append({'path': image_path.relative_to(ROOT).as_posix(), 'sha256': sha(image_path)})
    group_manifest = {
        'schema': 'pcb-copper-neighborhood-review-v1', 'dataset_id': DATASET_ID,
        'package_seal_sha256': json.loads((package / 'metadata/manifest.json').read_text()).get('seal_sha256'),
        'source_files': {side: {'path': rel, 'sha256': profile_rows[rel]['sha256']} for side, rel in SOURCE_PATHS.items()},
        'coordinate_basis': 'F.Mask geometric keypoints independently determine an EDIT→ORG rigid transform (scale fixed at 1); F.Cu pairing uses the transformed coordinates.',
        'source_selection': 'Each drawn source primitive carries its exact source identity and ORG/EDIT side as SVG data attributes so the Findings pair table can highlight the selected records in the grouped source-coordinate view.',
        'registration': registration,
        'circle_pairing': {
            'basis': 'Filled F.Cu gr_circle centers after registration; radius excluded from identity; mutual-unique candidates only.',
            **circle_pair_audit,
        },
        'rectangle_pairing': {
            'basis': 'Filled axis-aligned F.Cu gr_poly centers after registration; bounds and area compared separately.',
            'center_tolerance_mm': args.center_tolerance_mm,
            'candidate_pair_count': len(rectangle_links),
        },
        'trace_polygon_correspondence': {
            'schema': 'pcb-trace-polygon-correspondence/3',
            'coordinate_frame': 'All EDIT geometries transformed into ORG coordinates using the F.Mask candidate registration above.',
            'semantic_scope': 'Geometric overlap candidates only; no pad/net identity, electrical continuity, editing intent or complete board coverage.',
            'trace_method': 'Same-layer F.Cu centerline overlap. An edge requires at least 90% of the shorter source centerline within 0.001 mm and at least 0.02 mm covered length. Width is measured separately. Components retain one-to-many, many-to-one, and many-to-many relationships. A one-to-one object count is called full only when both centerlines are at least 90% covered; otherwise it remains a partial candidate. No relation is promoted to semantic identity.',
            'trace_summary': {**trace_result['summary'],
                              'excluded_invalid_before_count': len(invalid_trace_inputs['before']),
                              'excluded_invalid_after_count': len(invalid_trace_inputs['after'])},
            'trace_copper_footprint_method': trace_result['copper_footprint_method'],
            'trace_graph_accounting': trace_result['graph_accounting'],
            'trace_excluded': invalid_trace_inputs,
            'trace_relations': trace_result['relations'],
            'polygon_method': 'Filled F.Cu gr_poly source polygons after EDIT→ORG transform. An edge requires at least 90% of the smaller polygon overlapped, centroid distance at most 0.50 mm, and intersection area at least 0.000001 mm². Both sides’ covered fractions and signed area delta are recorded. A one-to-one object count is called full only when at least 90% of both polygons overlaps; otherwise it remains a partial growth/overlap candidate. Components retain one-to-many and many-to-many alternatives.',
            'polygon_summary': {**polygon_result['summary'],
                                'excluded_invalid_before_count': len(invalid_polygon_inputs['before']),
                                'excluded_invalid_after_count': len(invalid_polygon_inputs['after'])},
            'polygon_copper_footprint_method': polygon_result['copper_footprint_method'],
            'polygon_graph_accounting': polygon_result['graph_accounting'],
            'polygon_excluded': invalid_polygon_inputs,
            'polygon_relations': polygon_result['relations'],
        },
        'round_feature_pairs': [{key: entry[key] for key in (
            'before_identity', 'after_identity', 'center_displacement_mm',
            'before_radius_mm', 'after_radius_mm', 'added_area_mm2',
            'match_basis', 'review_class') if key in entry}
            for entry in circle_links],
        'grouping_basis': 'Spatial review neighborhoods combine registered round/rectangular F.Cu feature candidates with exact-coordinate trace links. They do not infer pad identity, net connectivity, or a common electrical terminal.',
        'scope': 'Representative copper-enhancement neighborhoods only; not a complete mapping of every board object.',
        'groups': group_records,
    }
    manifest_path = out / 'groups.json'
    manifest_path.write_text(json.dumps(group_manifest, indent=2) + '\n')
    registry_source = args.identity_review / 'registry_identity_review.json'
    config = json.loads(registry_source.read_text())
    registry_path = args.registry_output.resolve() if args.registry_output else registry_source
    if not registry_path.is_relative_to(ROOT / 'out'):
        raise SystemExit('Registry output must stay under checkout/out')
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    review = config['identity_reviews'][DATASET_ID]
    review['groups_manifest'] = {'path': manifest_path.relative_to(ROOT).as_posix(), 'sha256': sha(manifest_path)}
    review['group_images'] = image_bindings
    context_path = out / 'DOMAIN_QUESTIONS.md'
    if context_path.exists():
        review['context'] = {'path': context_path.relative_to(ROOT).as_posix(), 'sha256': sha(context_path)}
    audit_root = args.audit_root
    summary_path = audit_root / 'evidence/summary.json'
    joint_path = audit_root / 'evidence/joint_screenshot_source_center_consistency_v2.json'
    pairs_path = audit_root / 'evidence/joint_center_pairs.csv'
    full_search_path = audit_root / 'evidence/full_fcu_search_v1.json'
    closure_path = out / 'joint_pair_closure_v1.json'
    summary_evidence = json.loads(summary_path.read_text())
    joint_evidence = json.loads(joint_path.read_text())
    search_evidence = json.loads(full_search_path.read_text())
    subprocess.run([sys.executable, str(audit_root / 'scripts/validate_shared_pair_closure.py'),
                    '--package', str(args.package), '--groups', str(manifest_path),
                    '--output', str(closure_path)], cwd=ROOT, check=True, capture_output=True, text=True)
    closure_evidence = json.loads(closure_path.read_text())
    if closure_evidence.get('status') != 'PASS' or closure_evidence.get('input_sha256', {}).get(
            manifest_path.relative_to(ROOT).as_posix()) != sha(manifest_path):
        raise ValueError('Joint screenshot pair closure is missing, failed, or stale for this group manifest')
    with pairs_path.open(newline='') as stream:
        pair_rows = list(csv.DictReader(stream))
    registered_pair_by_id = {
        (item['before_identity'], item['after_identity']): item
        for item in circle_links
    }
    for index, pair in enumerate(pair_rows, 1):
        registered = registered_pair_by_id.get((pair['ORG_source_identity'], pair['EDIT_source_identity']))
        if not registered:
            raise ValueError('Screenshot pair is absent from the registered CAD center-pair table')
        pair['CAD_registered_center_displacement_mm'] = registered['center_displacement_mm']
        pair['source_pair_selection_id'] = f'pair-{index:02d}'
    crop = summary_evidence['results']
    screenshot_candidate_review = {
        'status': 'LOCAL_CROP_MATCH_SUPPORTED',
        'method': 'Full-shape F.Cu mask search against each supplied screenshot crop, using independently fitted rotations/reflection, scale and translation; followed by a conditioned source-circle-center consistency check.',
        'priority_group_ids': ['copper-01'],
        'source_selection_group_image': next(
            group['image_file'] for group in group_records if group['group_id'] == 'copper-01'),
        'rationales': {
            'copper-01': (f"Both independently fitted crops land in this source-coordinate neighborhood. "
                          f"ORG IoU {crop['ORG']['best_iou']:.3f} (runner-up {crop['ORG']['runner_up_iou']:.3f}); "
                          f"EDIT IoU {crop['EDIT']['best_iou']:.3f} (runner-up {crop['EDIT']['runner_up_iou']:.3f}). "
                          'This supports the local crop location for manual review; it does not identify semantic terminals or nets.')
        },
        'exact_screenshot_match': 'LOCAL_CROP_MATCH_SUPPORTED; SEMANTIC_OBJECT_IDENTITY_NOT_ESTABLISHED',
        'joint_pairs': pair_rows,
        'limits': {
            'ORG_iou': crop['ORG']['best_iou'],
            'ORG_runner_up_iou': crop['ORG']['runner_up_iou'],
            'EDIT_iou': crop['EDIT']['best_iou'],
            'EDIT_runner_up_iou': crop['EDIT']['runner_up_iou'],
            'ORG_landmarks_associated': joint_evidence['ORG']['associated_one_to_one'],
            'ORG_landmarks_detected': joint_evidence['ORG']['detected_maxima'],
            'EDIT_landmarks_associated': joint_evidence['EDIT']['associated_one_to_one'],
            'EDIT_landmarks_detected': joint_evidence['EDIT']['detected_maxima'],
            'EDIT_landmarks_not_associated_by_this_check': (joint_evidence['EDIT']['detected_maxima'] -
                                                             joint_evidence['EDIT']['associated_one_to_one']),
            'registered_circle_pairs_seen_in_both': len(joint_evidence['mutually_seen_pairs']),
            'joint_pair_closure': closure_evidence['status'],
            'ORG_crop_bounds_mm': crop['ORG']['bounds_mm'],
            'EDIT_crop_bounds_mm': crop['EDIT']['bounds_mm'],
            'ORG_runner_up_bounds_mm': search_evidence['matches']['ORG'][1]['crop_bounds_mm'],
            'EDIT_runner_up_bounds_mm': search_evidence['matches']['EDIT'][1]['crop_bounds_mm'],
            'exact_joint_identity': 'UNPROVEN',
            'global_uniqueness': 'UNPROVEN',
        },
        'joint_pair_closure': {
            'status': closure_evidence['status'],
            'pair_count': closure_evidence['pair_count'],
            'all_pairs_unique_in_registered_table': closure_evidence['all_pairs_unique_in_registered_table'],
            'all_centers_inside_respective_crop_bounds': closure_evidence['all_centers_inside_respective_crop_bounds'],
            'all_source_centers_reproduced_from_byte_spans': closure_evidence['all_source_centers_reproduced_from_byte_spans'],
        },
        'limitations': [
            'IoU scores are mask-overlap scores for this search, not calibrated probabilities.',
            'The two crop transforms were fitted independently; shared-window agreement and center checks are corroborative, not independent validation.',
            'Circle-center relationships are geometric records, not semantic pad, terminal, net, or electrical identities.',
            'The 30 EDIT screenshot maxima not associated by this center check are unmatched by this check; this is not evidence that copper is absent or changed.',
            'Exact joint screenshot-to-board identity and global localization uniqueness are unproven.',
            'The map covers these conspicuous local neighborhoods, not every source object on the board.',
        ],
    }
    screenshot_evidence_files = [
        ('org-screenshot', 'User-provided ORG before crop', 'image', 'inputs/before.png'),
        ('org-overlay', 'ORG full-copper crop fit', 'image', 'evidence/full_fcu_overlay_org_1.png'),
        ('edit-screenshot', 'User-provided EDIT after crop', 'image', 'inputs/after.png'),
        ('edit-overlay', 'EDIT full-copper crop fit', 'image', 'evidence/full_fcu_overlay_edit_1.png'),
        ('org-centers', 'ORG detected crop landmarks', 'image', 'evidence/org_center_associations.png'),
        ('edit-centers', 'EDIT detected crop landmarks', 'image', 'evidence/edit_center_associations.png'),
        ('org-runner-up', 'ORG runner-up crop fit', 'image', 'evidence/full_fcu_overlay_org_2.png'),
        ('edit-runner-up', 'EDIT runner-up crop fit', 'image', 'evidence/full_fcu_overlay_edit_2.png'),
        ('joint-pairs', '16 geometric ORG ↔ EDIT round-feature pairs', 'csv', 'evidence/joint_center_pairs.csv'),
        ('pair-closure', 'Source-bound shared-pair closure audit', 'json', closure_path),
        ('joint-check', 'Joint source-coordinate consistency report', 'json', 'evidence/joint_screenshot_source_center_consistency_v2.json'),
        ('full-search', 'Full F.Cu crop-search report', 'json', 'evidence/full_fcu_search_v1.json'),
        ('sensitivity', 'Aggregate crop, threshold, scale, scramble and arc sensitivity', 'json', 'evidence/summary.json'),
        ('search-sensitivity', 'Mask threshold, scale and crop sensitivity details', 'json', 'evidence/screenshot_fit_sensitivity_v1.json'),
        ('scramble-control', 'Spatial scramble control results', 'json', 'evidence/scrambled_spatial_controls_v1.json'),
        ('arc-sensitivity', 'Unsupported EDIT local-arc sensitivity details', 'json', 'evidence/edit_local_unsupported_arc_sensitivity_v1.json'),
    ]
    review['screenshot_evidence'] = []
    for ident, label, kind, relative in screenshot_evidence_files:
        path = relative if isinstance(relative, Path) else audit_root / relative
        review['screenshot_evidence'].append({
            'id': ident, 'label': label, 'kind': kind,
            'path': path.relative_to(ROOT).as_posix(), 'sha256': sha(path)})
    review['group_summary'] = {'group_count': len(group_records), 'object_pair_count': len(all_ids),
                               'registered_circle_pair_count': len(circle_links),
                               'registered_rectangle_pair_count': len(rectangle_links),
                               'mask_registration_inliers': registration['inlier_count'],
                               'trace_overlap_component_count': trace_result['summary']['relation_component_count'],
                               'trace_overlap_candidate_edge_count': trace_result['summary']['candidate_edge_count'],
                               'filled_polygon_overlap_component_count': polygon_result['summary']['relation_component_count'],
                               'filled_polygon_overlap_candidate_edge_count': polygon_result['summary']['candidate_edge_count'],
                               'scope': group_manifest['scope'],
                               'screenshot_candidate_review': screenshot_candidate_review}
    registry_path.write_text(json.dumps(config, indent=2) + '\n')
    print(json.dumps({'status': 'PASS', 'groups': len(group_records),
                      'object_pair_count': len(all_ids), 'manifest': manifest_path.relative_to(ROOT).as_posix(),
                      'registry': registry_path.relative_to(ROOT).as_posix(),
                      'groups_summary': [{'id': g['group_id'], 'title': g['title'], 'pairs': g['pair_count'], 'kinds': g['kind_counts'], 'center': g['center_mm']} for g in group_records]}))


if __name__ == '__main__':
    main()
