"""Conservative, source-bound geometric correspondence for copper traces/polygons.

These relations describe geometric overlap after a supplied board transform. They
do not assert semantic identity, electrical connectivity, or editing intent.
"""
from __future__ import annotations

from collections import defaultdict, deque
import hashlib
import math
from shapely.geometry import box
from shapely.ops import unary_union
from shapely.strtree import STRtree

from src.native_inventory import ERROR_MM, steps


def _region_comparison(before_geometry, after_geometry):
    """Compare two filled copper regions without changing candidate identity."""
    intersection = before_geometry.intersection(after_geometry)
    difference = before_geometry.symmetric_difference(after_geometry)
    before_area = before_geometry.area
    after_area = after_geometry.area
    return {
        'status': 'MEASURED',
        'before_copper_area_mm2': before_area,
        'after_copper_area_mm2': after_area,
        'signed_area_delta_mm2': after_area - before_area,
        'intersection_area_mm2': intersection.area,
        'before_covered_fraction': intersection.area / before_area if before_area else None,
        'after_covered_fraction': intersection.area / after_area if after_area else None,
        'symmetric_difference_area_mm2': difference.area,
        # These identify the computed regions for review; they are not semantic IDs.
        'before_region_wkb_sha256': hashlib.sha256(before_geometry.wkb).hexdigest(),
        'after_region_wkb_sha256': hashlib.sha256(after_geometry.wkb).hexdigest(),
        'symmetric_difference_wkb_sha256': hashlib.sha256(difference.wkb).hexdigest(),
    }


def _stroke_footprint(item):
    width = item.get('width_mm')
    if width is None or not math.isfinite(width) or width <= 0:
        return None
    radius = width / 2
    return item['geometry'].buffer(radius, quad_segs=steps(radius),
                                   cap_style='round', join_style='round')


def _attach_trace_footprint_metrics(before, after, relations):
    """Attach width-aware metrics as a second channel beside centerline links."""
    before_footprints = {item['identity']: _stroke_footprint(item) for item in before}
    after_footprints = {item['identity']: _stroke_footprint(item) for item in after}
    for relation in relations:
        for edge in relation['candidate_edges']:
            left = before_footprints.get(edge['before_identity'])
            right = after_footprints.get(edge['after_identity'])
            if left is None or right is None:
                edge['copper_footprint_comparison'] = {
                    'status': 'NOT_AVAILABLE', 'reason': 'MISSING_OR_NONPOSITIVE_WIDTH'}
            else:
                edge['copper_footprint_comparison'] = _region_comparison(left, right)

        left_regions = [before_footprints[identity]
                        for identity in relation['before_identities']
                        if before_footprints.get(identity) is not None]
        right_regions = [after_footprints[identity]
                         for identity in relation['after_identities']
                         if after_footprints.get(identity) is not None]
        if (len(left_regions) != len(relation['before_identities'])
                or len(right_regions) != len(relation['after_identities'])):
            relation['copper_footprint_comparison'] = {
                'status': 'NOT_AVAILABLE', 'reason': 'MISSING_OR_NONPOSITIVE_WIDTH'}
        else:
            relation['copper_footprint_comparison'] = _region_comparison(
                unary_union(left_regions), unary_union(right_regions))


def _attach_polygon_footprint_metrics(before, after, relations):
    """Compare filled polygon areas at both edge and connected-component scope."""
    before_by_id = {item['identity']: item['geometry'] for item in before}
    after_by_id = {item['identity']: item['geometry'] for item in after}
    for relation in relations:
        for edge in relation['candidate_edges']:
            edge['copper_footprint_comparison'] = _region_comparison(
                before_by_id[edge['before_identity']], after_by_id[edge['after_identity']])
        relation['copper_footprint_comparison'] = _region_comparison(
            unary_union([before_by_id[identity] for identity in relation['before_identities']]),
            unary_union([after_by_id[identity] for identity in relation['after_identities']]))


def _components(before, after, candidate_edges, relation):
    left_edges = defaultdict(set)
    right_edges = defaultdict(set)
    evidence_by_edge = {}
    for left, right, evidence in candidate_edges:
        left_edges[left].add(right)
        right_edges[right].add(left)
        evidence_by_edge[left, right] = evidence
    visited_left, visited_right, results = set(), set(), []
    for start in range(len(before)):
        if start in visited_left or not left_edges[start]:
            continue
        pending = deque([('before', start)])
        component_left, component_right, component_edges = set(), set(), []
        while pending:
            side, index = pending.popleft()
            if side == 'before':
                if index in visited_left:
                    continue
                visited_left.add(index); component_left.add(index)
                for target in sorted(left_edges[index]):
                    pending.append(('after', target))
            else:
                if index in visited_right:
                    continue
                visited_right.add(index); component_right.add(index)
                for target in sorted(right_edges[index]):
                    pending.append(('before', target))
        for left in component_left:
            component_edges.extend(evidence_by_edge[left, right]
                                   for right in sorted(left_edges[left])
                                   if right in component_right)
        component_edges.sort(key=lambda edge: (edge['before_identity'], edge['after_identity']))
        before_count, after_count = len(component_left), len(component_right)
        if before_count == after_count == 1:
            classification = 'one_to_one_geometric_candidate'
        elif before_count == 1:
            classification = 'one_to_many_overlap'
        elif after_count == 1:
            classification = 'many_to_one_overlap'
        else:
            classification = 'many_to_many_ambiguous_overlap'
        results.append({
            'relation_id': f'{relation}-{len(results) + 1:06d}',
            'classification': classification,
            'before_identities': sorted(before[i]['identity'] for i in component_left),
            'after_identities': sorted(after[i]['identity'] for i in component_right),
            'candidate_edges': component_edges,
        })
    return results, left_edges, right_edges


def _graph_accounting(before, after, left_edges, right_edges, relations, edges):
    """Return a source-identity inventory for every matched and isolated vertex."""
    before_candidates = sorted(before[index]['identity'] for index, targets in left_edges.items() if targets)
    after_candidates = sorted(after[index]['identity'] for index, sources in right_edges.items() if sources)
    unmatched_before = sorted(before[index]['identity'] for index in range(len(before))
                              if not left_edges[index])
    unmatched_after = sorted(after[index]['identity'] for index in range(len(after))
                             if not right_edges[index])
    classification_counts = defaultdict(int)
    for relation in relations:
        classification_counts[relation['classification']] += 1
    return {
        'before_object_count': len(before),
        'after_object_count': len(after),
        'before_candidate_object_count': len(before_candidates),
        'after_candidate_object_count': len(after_candidates),
        'unmatched_before_count': len(unmatched_before),
        'unmatched_after_count': len(unmatched_after),
        'candidate_edge_count': len(edges),
        'relation_component_count': len(relations),
        'component_classification_counts': dict(sorted(classification_counts.items())),
        'candidate_before_identities': before_candidates,
        'candidate_after_identities': after_candidates,
        'unmatched_before_identities': unmatched_before,
        'unmatched_after_identities': unmatched_after,
    }


def trace_correspondence(before, after, tolerance_mm=0.001,
                         minimum_covered_fraction=0.90,
                         minimum_overlap_length_mm=0.02):
    """Group F.Cu centerline overlaps, retaining split/merge and ambiguity.

    The after geometries must already be transformed into the before coordinate
    frame. A candidate requires at least 90% of the shorter line to lie within the
    declared tolerance of the other line and at least the declared absolute
    overlap length. Stroke width is deliberately excluded from the link key and
    reported as separate evidence.
    """
    before = [item for item in before if item['geometry'].is_valid
              and item['geometry'].length > 0]
    after = [item for item in after if item['geometry'].is_valid
             and item['geometry'].length > 0]
    tree = STRtree([item['geometry'] for item in before]) if before else None
    edges = []
    for ai, right in enumerate(after):
        line = right['geometry']
        minx, miny, maxx, maxy = line.bounds
        query = box(minx - tolerance_mm, miny - tolerance_mm,
                    maxx + tolerance_mm, maxy + tolerance_mm)
        if tree is None:
            continue
        for bi_value in tree.query(query):
            bi = int(bi_value)
            left = before[bi]['geometry']
            # Buffer tolerance may extend beyond a line's endpoints; coverage is
            # still a fraction of the source object's finite centerline length.
            left_covered = min(left.length, left.intersection(line.buffer(tolerance_mm)).length)
            right_covered = min(line.length, line.intersection(left.buffer(tolerance_mm)).length)
            shorter = min(left.length, line.length)
            overlap = min(left_covered, right_covered)
            fraction = overlap / shorter if shorter else 0.0
            if fraction < minimum_covered_fraction or overlap < minimum_overlap_length_mm:
                continue
            edges.append((bi, ai, {
                'before_identity': before[bi]['identity'],
                'after_identity': right['identity'],
                'covered_fraction_of_shorter': fraction,
                'before_length_mm': left.length,
                'after_length_mm': line.length,
                'before_covered_fraction': left_covered / left.length,
                'after_covered_fraction': right_covered / line.length,
                'before_width_mm': before[bi].get('width_mm'),
                'after_width_mm': right.get('width_mm'),
                'width_delta_mm': (right.get('width_mm') - before[bi].get('width_mm')
                                   if right.get('width_mm') is not None
                                   and before[bi].get('width_mm') is not None else None),
            }))
    relations, left_edges, right_edges = _components(before, after, edges, 'trace')
    _attach_trace_footprint_metrics(before, after, relations)
    accounting = _graph_accounting(before, after, left_edges, right_edges, relations, edges)
    for relation in relations:
        if relation['classification'] == 'many_to_many_ambiguous_overlap':
            relation['status'] = 'ambiguous_geometric_candidate'
        elif (relation['classification'] == 'one_to_one_geometric_candidate'
              and all(edge['before_covered_fraction'] >= minimum_covered_fraction
                      and edge['after_covered_fraction'] >= minimum_covered_fraction
                      for edge in relation['candidate_edges'])):
            relation['status'] = 'one_to_one_geometric_candidate'
        else:
            relation['status'] = 'partial_geometric_correspondence_candidate'
    return {
        'relations': relations,
        'graph_accounting': accounting,
        'summary': {
            'before_trace_count': len(before), 'after_trace_count': len(after),
            'candidate_edge_count': len(edges), 'relation_component_count': len(relations),
            'one_to_one_count': sum(r['classification'] == 'one_to_one_geometric_candidate' for r in relations),
            'one_to_one_full_coverage_count': sum(r['status'] == 'one_to_one_geometric_candidate' for r in relations),
            'one_to_one_partial_coverage_count': sum(r['classification'] == 'one_to_one_geometric_candidate'
                                                     and r['status'] != 'one_to_one_geometric_candidate' for r in relations),
            'one_to_many_count': sum(r['classification'] == 'one_to_many_overlap' for r in relations),
            'many_to_one_count': sum(r['classification'] == 'many_to_one_overlap' for r in relations),
            'many_to_many_ambiguous_count': sum(r['classification'] == 'many_to_many_ambiguous_overlap' for r in relations),
            'unmatched_before_count': sum(not left_edges[i] for i in range(len(before))),
            'unmatched_after_count': sum(not right_edges[i] for i in range(len(after))),
            'tolerance_mm': tolerance_mm,
            'minimum_covered_fraction_of_shorter': minimum_covered_fraction,
            'minimum_overlap_length_mm': minimum_overlap_length_mm,
            'copper_footprint_metrics_available': sum(
                relation['copper_footprint_comparison']['status'] == 'MEASURED'
                for relation in relations),
            'copper_footprint_metric_scope': 'per candidate edge and per relation-component union; not a board-wide copper-area delta',
        },
        'copper_footprint_method': {
            'model': 'Shapely/GEOS round-capped, round-joined buffer of each registered source centerline by half its declared width; component metrics compare unions to avoid overlap double-counting within a component.',
            'arc_centerline_max_chord_error_mm': ERROR_MM,
            'buffer_rounding_max_sagitta_mm': ERROR_MM,
            'buffer_quad_segments': 'steps(width_mm / 2) from native_inventory/2',
            'matching_role': 'measurement only; does not create, reject, or relabel centerline correspondence candidates',
            'wkb_hash_role': 'identifies the computed geometry bytes under this runtime; not a canonical semantic identity',
        },
    }


def polygon_correspondence(before, after, minimum_covered_fraction=0.90,
                          maximum_centroid_distance_mm=0.50,
                          minimum_overlap_area_mm2=0.000001):
    """Group filled F.Cu polygon overlaps; geometry is already in one frame."""
    before = [item for item in before if item['geometry'].is_valid
              and not item['geometry'].is_empty and item['geometry'].area > 0]
    after = [item for item in after if item['geometry'].is_valid
             and not item['geometry'].is_empty and item['geometry'].area > 0]
    tree = STRtree([item['geometry'] for item in before]) if before else None
    edges = []
    for ai, right in enumerate(after):
        poly = right['geometry']
        minx, miny, maxx, maxy = poly.bounds
        query = box(minx, miny, maxx, maxy)
        if tree is None:
            continue
        for bi_value in tree.query(query):
            bi = int(bi_value)
            left = before[bi]['geometry']
            intersection = left.intersection(poly).area
            smaller_area = min(left.area, poly.area)
            fraction = intersection / smaller_area if smaller_area else 0.0
            centroid_distance = left.centroid.distance(poly.centroid)
            if (intersection < minimum_overlap_area_mm2
                    or fraction < minimum_covered_fraction
                    or centroid_distance > maximum_centroid_distance_mm):
                continue
            edges.append((bi, ai, {
                'before_identity': before[bi]['identity'],
                'after_identity': right['identity'],
                'intersection_area_mm2': intersection,
                'before_area_mm2': left.area,
                'after_area_mm2': poly.area,
                'area_delta_mm2': poly.area - left.area,
                'before_covered_fraction': intersection / left.area,
                'after_covered_fraction': intersection / poly.area,
                'fraction_of_smaller_polygon_overlapped': fraction,
                'centroid_distance_mm': centroid_distance,
            }))
    relations, left_edges, right_edges = _components(before, after, edges, 'polygon')
    _attach_polygon_footprint_metrics(before, after, relations)
    accounting = _graph_accounting(before, after, left_edges, right_edges, relations, edges)
    for relation in relations:
        if relation['classification'] == 'many_to_many_ambiguous_overlap':
            relation['status'] = 'ambiguous_geometric_candidate'
        elif (relation['classification'] == 'one_to_one_geometric_candidate'
              and all(edge['before_covered_fraction'] >= minimum_covered_fraction
                      and edge['after_covered_fraction'] >= minimum_covered_fraction
                      for edge in relation['candidate_edges'])):
            relation['status'] = 'one_to_one_geometric_candidate'
        else:
            relation['status'] = 'partial_geometric_correspondence_candidate'
    return {
        'relations': relations,
        'graph_accounting': accounting,
        'summary': {
            'before_filled_polygon_count': len(before), 'after_filled_polygon_count': len(after),
            'candidate_edge_count': len(edges), 'relation_component_count': len(relations),
            'one_to_one_count': sum(r['classification'] == 'one_to_one_geometric_candidate' for r in relations),
            'one_to_one_full_coverage_count': sum(r['status'] == 'one_to_one_geometric_candidate' for r in relations),
            'one_to_one_partial_coverage_count': sum(r['classification'] == 'one_to_one_geometric_candidate'
                                                     and r['status'] != 'one_to_one_geometric_candidate' for r in relations),
            'one_to_many_count': sum(r['classification'] == 'one_to_many_overlap' for r in relations),
            'many_to_one_count': sum(r['classification'] == 'many_to_one_overlap' for r in relations),
            'many_to_many_ambiguous_count': sum(r['classification'] == 'many_to_many_ambiguous_overlap' for r in relations),
            'unmatched_before_count': sum(not left_edges[i] for i in range(len(before))),
            'unmatched_after_count': sum(not right_edges[i] for i in range(len(after))),
            'minimum_fraction_of_smaller_polygon_overlapped': minimum_covered_fraction,
            'maximum_centroid_distance_mm': maximum_centroid_distance_mm,
            'minimum_overlap_area_mm2': minimum_overlap_area_mm2,
            'copper_footprint_metrics_available': sum(
                relation['copper_footprint_comparison']['status'] == 'MEASURED'
                for relation in relations),
            'copper_footprint_metric_scope': 'per candidate edge and per relation-component union; not a board-wide copper-area delta',
        },
        'copper_footprint_method': {
            'model': 'Existing filled source polygons, compared by GEOS intersection and symmetric difference; component metrics compare unions to avoid overlap double-counting within a component.',
            'matching_role': 'measurement only; does not create, reject, or relabel polygon correspondence candidates',
            'wkb_hash_role': 'identifies the computed geometry bytes under this runtime; not a canonical semantic identity',
        },
    }
