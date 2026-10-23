#!/usr/bin/env python3
"""Build one source-bound ORG contact-group comparison for manual review.

The grouping comes from the persisted ORG F.Cu contact-component map. EDIT
objects are attached only through the existing geometric relation evidence;
missing or ambiguous matches remain explicit. This is a review aid, not an
electrical or engineering acceptance check.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import math
from pathlib import Path
import re
import sqlite3
import sys

from shapely import from_wkb
from shapely.geometry import box

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.native_inventory import inventory as build_inventory

DATASET = ROOT / 'dataset/szu-comm_3020301113B_intake_ready_20261021_v1/raw'
ORG_HASH = '850c4c74d55717a721d4bbed7ec876ee086f475efd97f69bb5b5164ef77533a0'
EDIT_HASH = 'ec141305a9d93db87709124ba5aa9378135485ae5458f019e47a342d099496a5'
ORG_REVISION = 'a6456452a162db04b776fcd4e3b9da2813f5d2a491125d5b4e6ad9976054cfd8'
MAP_REVISION = '2e3a279a5f0db97937d3a2374806910d02eeb8d4aa1df522cde232ff8cb1300c'
MAP_DB = ROOT / 'out/ingestion/org_family_map_materializations/szu-comm_20261022_org_recognition_v1/run-32cecd4cc6cd4ff1a7e3dd869366aacb/store/catalog.sqlite'
RELATIONS = ROOT / 'out/ingestion/audits/20261024_width_aware_copper_footprint_v1/evidence/groups.json'
REGION = ROOT / 'out/ingestion/copper_enhancement_review'


def _load_inventory(path: Path, expected_hash: str):
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != expected_hash:
        raise ValueError(f'SOURCE_HASH_MISMATCH: {path} ({digest})')
    return raw, build_inventory(raw)


def _file_sha256(path: Path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _geometry_lookup(inv):
    rows = {row['id']: row for row in inv['objects']}
    geometries = {}
    for identity, row in rows.items():
        key = row.get('geometry_sha256')
        if key:
            geometries[identity] = from_wkb(inv['payloads'][key])
    return rows, geometries


def _load_component(component_id: str):
    connection = sqlite3.connect(f'file:{MAP_DB}?mode=ro', uri=True)
    try:
        row = connection.execute(
            'select record_json from objects where revision=? and object_id=?',
            (MAP_REVISION, component_id),
        ).fetchone()
    finally:
        connection.close()
    if not row:
        raise ValueError('CONTACT_GROUP_NOT_FOUND_IN_PINNED_MAP')
    record = json.loads(row[0])
    if record.get('entity_type') != 'physical_group' or record.get('layer') != 'F.Cu':
        raise ValueError('SELECTED_RECORD_IS_NOT_AN_F_CU_PHYSICAL_GROUP')
    member_refs = [ref for ref in record.get('source_refs', [])
                   if ref.get('role') == 'physical_group_member']
    if any(ref.get('source_revision') != ORG_REVISION for ref in member_refs):
        raise ValueError('CONTACT_GROUP_MEMBER_REVISION_MISMATCH')
    members = sorted({ref['object_id'] for ref in member_refs})
    if any(not object_id.startswith(f'{ORG_HASH}:bytes:') for object_id in members):
        raise ValueError('CONTACT_GROUP_MEMBER_SOURCE_HASH_MISMATCH')
    if not members:
        raise ValueError('CONTACT_GROUP_HAS_NO_MEMBERS')
    return record, members


def _load_local_seed_cohort(component_id: str, anchor_id: str, radius_mm: float):
    """Select one local cohort of seeds and their stored incident traces."""
    connection = sqlite3.connect(f'file:{MAP_DB}?mode=ro', uri=True)
    try:
        rows = connection.execute(
            'select object_id,record_json from objects where revision=?',
            (MAP_REVISION,),
        ).fetchall()
    finally:
        connection.close()
    group = None
    candidates = []
    for object_id, raw in rows:
        record = json.loads(raw)
        if object_id == component_id:
            group = record
        if record.get('entity_type') == 'candidate_member':
            candidates.append((object_id, record))
    if not group or group.get('entity_type') != 'physical_group' or group.get('layer') != 'F.Cu':
        raise ValueError('LOCAL_COHORT_PARENT_IS_NOT_A_PINNED_F_CU_CONTACT_GROUP')
    if any(ref.get('source_revision') != ORG_REVISION for ref in group.get('source_refs', [])):
        raise ValueError('LOCAL_COHORT_PARENT_REVISION_MISMATCH')
    physical_key = group.get('physical_group_key')
    scoped = [(oid, row) for oid, row in candidates
              if row.get('physical_group_key') == physical_key]
    anchor = None
    for oid, row in scoped:
        seed_refs = [ref for ref in row.get('source_refs', [])
                     if ref.get('role') == 'local_land_candidate_seed']
        if oid == anchor_id or any(ref.get('object_id') == anchor_id for ref in seed_refs):
            anchor = (oid, row, seed_refs)
            break
    if anchor is None:
        raise ValueError('FOCUS_SEED_NOT_IN_PINNED_CONTACT_GROUP')
    ax, ay = anchor[1]['geometry']['center_mm']
    selected = []
    for oid, row in scoped:
        seed_refs = [ref for ref in row.get('source_refs', [])
                     if ref.get('role') == 'local_land_candidate_seed']
        if not seed_refs:
            continue
        x, y = row['geometry']['center_mm']
        if math.hypot(x - ax, y - ay) <= radius_mm:
            selected.append((oid, row, seed_refs))
    if anchor not in selected:
        selected.append(anchor)
    source_ids = set()
    for _, row, seed_refs in selected:
        source_ids.update(ref['object_id'] for ref in seed_refs)
        source_ids.update(ref['object_id'] for ref in row.get('trace_associations', {}).get('nominal_contacts', []))
    if any(not object_id.startswith(f'{ORG_HASH}:bytes:') for object_id in source_ids):
        raise ValueError('LOCAL_COHORT_SOURCE_HASH_MISMATCH')
    return group, sorted(source_ids), {
        'anchor_candidate_id': anchor[0],
        'anchor_seed_identity': anchor[2][0]['object_id'],
        'radius_mm': radius_mm,
        'selected_candidate_ids': sorted(item[0] for item in selected),
        'selected_seed_identities': sorted(ref['object_id'] for _, _, refs in selected for ref in refs),
    }


def _candidate_map(manifest):
    """Map each ORG identity to candidate EDIT identities and evidence labels."""
    result = {}
    for row in manifest.get('round_feature_pairs', []):
        result.setdefault(row['before_identity'], []).append({
            'after_identity': row['after_identity'],
            'status': 'mutual_unique_registered_center',
            'evidence_kind': 'round_feature',
            'metrics': {k: row.get(k) for k in (
                'before_radius_mm', 'after_radius_mm', 'center_displacement_mm',
                'added_area_mm2')},
        })
    topology = manifest.get('trace_polygon_correspondence', {})
    for relation_kind, key in (('trace', 'trace_relations'), ('filled_polygon', 'polygon_relations')):
        for relation in topology.get(key, []):
            classification = relation.get('classification', 'unclassified_candidate')
            edges = relation.get('candidate_edges', [])
            targets_by_source = {}
            for edge in edges:
                targets_by_source.setdefault(edge['before_identity'], set()).add(edge['after_identity'])
            for source_id in relation.get('before_identities', []):
                targets = sorted(targets_by_source.get(source_id, set()))
                if not targets:
                    continue
                result.setdefault(source_id, []).extend({
                    'after_identity': target,
                    'status': classification,
                    'evidence_kind': relation_kind,
                    'relation_id': relation.get('relation_id'),
                } for target in targets)
    for source_id, items in result.items():
        dedup = {(i['after_identity'], i['status'], i['evidence_kind']): i for i in items}
        result[source_id] = [dedup[k] for k in sorted(dedup)]
    return result


def _polygon_paths(geometry, project):
    if geometry.is_empty:
        return []
    if geometry.geom_type == 'Polygon':
        polys = [geometry]
    elif geometry.geom_type == 'MultiPolygon':
        polys = list(geometry.geoms)
    elif geometry.geom_type == 'GeometryCollection':
        polys = [part for part in geometry.geoms if part.geom_type == 'Polygon']
    else:
        return []
    paths = []
    for poly in polys:
        rings = [poly.exterior, *poly.interiors]
        d = []
        for ring in rings:
            coords = list(ring.coords)
            if len(coords) < 4:
                continue
            pts = [project(x, y) for x, y in coords]
            d.append('M ' + ' L '.join(f'{x:.2f},{y:.2f}' for x, y in pts) + ' Z')
        if d:
            paths.append(' '.join(d))
    return paths


def _segment_centerlines(raw: bytes, rows: dict, identities: set[str]):
    """Recover exact native segment centerlines and widths from bound source spans."""
    number = rb'([+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+))'
    pattern = re.compile(
        rb'\(segment\s+\(start\s+' + number + rb'\s+' + number +
        rb'\)\s+\(end\s+' + number + rb'\s+' + number +
        rb'\)\s+\(width\s+' + number + rb'\)'
    )
    found = {}
    for identity in identities:
        row = rows.get(identity, {})
        if row.get('kind') != 'segment':
            continue
        start, end = row.get('source_span', [None, None])
        if start is None or end is None or start < 0 or end > len(raw):
            raise ValueError(f'SEGMENT_SOURCE_SPAN_INVALID: {identity}')
        match = pattern.search(raw[start:end])
        if not match:
            raise ValueError(f'SEGMENT_CENTERLINE_NOT_RECOVERED: {identity}')
        x1, y1, x2, y2, width = (float(value) for value in match.groups())
        found[identity] = {'start': [x1, y1], 'end': [x2, y2], 'width_mm': width}
    return found


def _render_svg(target: Path, title: str, center, bounds, crop, org_rows, org_geoms,
                edit_rows, edit_geoms, org_members, edit_members, pair_rows, summary,
                org_seed_labels=None, edit_seed_labels=None, edit_supplemental_ids=None,
                org_centerlines=None, edit_centerlines=None):
    width, height, margin, gap = 1800, 1080, 34, 28
    pane_w = (width - 2 * margin - gap) / 2
    pane_h = 790
    pane_y = 156
    x0, y0, x1, y1 = crop
    sx = (pane_w - 36) / (x1 - x0)
    sy = (pane_h - 36) / (y1 - y0)
    scale = min(sx, sy)
    ox, oy = (pane_w - (x1 - x0) * scale) / 2, (pane_h - (y1 - y0) * scale) / 2

    def project(px, py, pane_x):
        return pane_x + ox + (px - x0) * scale, pane_y + oy + (py - y0) * scale

    panes = [(margin, 'ORG · before', org_rows, org_geoms, org_members, '#e5464e'),
             (margin + pane_w + gap, 'EDIT · enhanced', edit_rows, edit_geoms, edit_members, '#ee3f49')]
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
           '<rect width="100%" height="100%" fill="#0c1424"/>',
           f'<text x="{margin}" y="42" fill="#eef4ff" font-family="Arial" font-size="25" font-weight="700">{html.escape(title)}</text>',
           f'<text x="{margin}" y="76" fill="#b4c3da" font-family="Arial" font-size="15">Source-coordinate view · bounds X {bounds[0]:.3f}–{bounds[2]:.3f} mm, Y {bounds[1]:.3f}–{bounds[3]:.3f} mm · registered F.Mask fit, F.Cu excluded</text>',
             f'<text x="{margin}" y="105" fill="#b4c3da" font-family="Arial" font-size="14">Local review group: {summary["member_count"]} source objects ({summary["kind_counts"]}). Colors identify source geometry kinds, not semantic roles.</text>']
    org_seed_labels = org_seed_labels or {}
    edit_seed_labels = edit_seed_labels or {}
    edit_supplemental_ids = edit_supplemental_ids or set()
    org_centerlines = org_centerlines or {}
    edit_centerlines = edit_centerlines or {}
    kind_colors = {'gr_circle': '#f7c66a', 'gr_poly': '#57d6de',
                   'segment': '#ed7898', 'arc': '#ed7898'}
    for pane_x, label, rows, geoms, member_ids, color in panes:
        out.append(f'<rect x="{pane_x}" y="{pane_y}" width="{pane_w}" height="{pane_h}" rx="8" fill="#111d30" stroke="#41516b"/>')
        out.append(f'<text x="{pane_x+16}" y="{pane_y+26}" fill="#eef4ff" font-family="Arial" font-size="18" font-weight="700">{label}</text>')
        clip_id = 'clip-org' if label.startswith('ORG') else 'clip-edit'
        out.append(f'<defs><clipPath id="{clip_id}"><rect x="{pane_x}" y="{pane_y}" width="{pane_w}" height="{pane_h}" rx="8"/></clipPath></defs>')
        out.append(f'<g clip-path="url(#{clip_id})" fill-rule="evenodd">')
        for identity, shape in geoms.items():
            if identity in member_ids or not shape.bounds:
                continue
            if shape.intersects(box(*crop)):
                for path in _polygon_paths(shape.intersection(box(*crop)), lambda x, y: project(x, y, pane_x)):
                    out.append(f'<path d="{path}" fill="#92a2b9" opacity="0.10"/>')
        labels = org_seed_labels if label.startswith('ORG') else edit_seed_labels
        centerlines = org_centerlines if label.startswith('ORG') else edit_centerlines
        kind_order = {'segment': 0, 'arc': 0, 'gr_poly': 1, 'gr_circle': 2}
        ordered_members = sorted(member_ids, key=lambda identity: (
            kind_order.get(rows.get(identity, {}).get('kind'), 1), identity))
        deferred_centerlines = []
        for identity in ordered_members:
            shape = geoms.get(identity)
            if shape is None or not shape.intersects(box(*crop)):
                continue
            row = rows[identity]
            if identity in centerlines:
                deferred_centerlines.append(centerlines[identity])
                continue
            fill = kind_colors.get(row.get('kind'), '#e7edf5')
            opacity = '0.96'
            is_seed = identity in labels
            supplemental = identity in edit_supplemental_ids
            stroke = '#ffffff' if supplemental else '#07111f' if is_seed else 'none'
            stroke_width = '2.4' if is_seed else '0'
            dash = ' stroke-dasharray="7 5"' if supplemental else ''
            for path in _polygon_paths(shape.intersection(box(*crop)), lambda x, y: project(x, y, pane_x)):
                out.append(f'<path d="{path}" fill="{fill}" opacity="{opacity}" stroke="{stroke}" stroke-width="{stroke_width}" stroke-linejoin="round"{dash}/>')
        for trace in deferred_centerlines:
            px1, py1 = project(*trace['start'], pane_x)
            px2, py2 = project(*trace['end'], pane_x)
            out.append(f'<line x1="{px1:.2f}" y1="{py1:.2f}" x2="{px2:.2f}" y2="{py2:.2f}" stroke="#ed7898" stroke-width="2.2" stroke-linecap="round" opacity="0.94"/>')
        out.append('</g>')
        for identity, tag in sorted(labels.items()):
            shape = geoms.get(identity)
            if shape is None or not shape.intersects(box(*crop)):
                continue
            px, py = project(*shape.representative_point().coords[0], pane_x)
            out.append(f'<circle cx="{px:.2f}" cy="{py:.2f}" r="13" fill="#07111f" stroke="#f5f7fb" stroke-width="2"/>')
            out.append(f'<text x="{px:.2f}" y="{py+5:.2f}" text-anchor="middle" fill="#ffffff" font-family="Arial" font-size="12" font-weight="700">{html.escape(tag)}</text>')
    legend_y = 976
    out.extend([
        f'<text x="{margin}" y="{legend_y}" fill="#eef4ff" font-family="Arial" font-size="14"><tspan fill="#f7c66a">Gold: gr_circle</tspan> · <tspan fill="#57d6de">cyan: gr_poly</tspan> · <tspan fill="#ed7898">rose: trace centerline</tspan> · muted gray: nearby F.Cu context.</text>',
        f'<text x="{margin}" y="{legend_y+23}" fill="#b4c3da" font-family="Arial" font-size="13">Trace lines are schematic width for legibility; source widths are listed in pair_register.json. S-labels mark stored candidate seeds, not semantic pad/net identities.</text>',
        f'<text x="{margin}" y="{legend_y+50}" fill="#b4c3da" font-family="Arial" font-size="12">White dashed EDIT outlines are nearby registered-center review candidates, not established matches; IDs and distances are in pair_register.json.</text>',
        '</svg>'
    ])
    target.write_text(''.join(out), encoding='utf-8')


def build(component_id: str, output: Path, focus_seed_id: str | None = None,
          focus_radius_mm: float = 0.42):
    org_path = DATASET / 'ORG/top.kicad_pcb'
    edit_path = DATASET / 'EDIT/top_layer.kicad_pcb'
    org_raw, org_inv = _load_inventory(org_path, ORG_HASH)
    edit_raw, edit_inv = _load_inventory(edit_path, EDIT_HASH)
    org_rows, org_geoms = _geometry_lookup(org_inv)
    edit_rows, edit_geoms = _geometry_lookup(edit_inv)
    if focus_seed_id:
        group, members, focus = _load_local_seed_cohort(component_id, focus_seed_id, focus_radius_mm)
    else:
        group, members = _load_component(component_id)
        focus = None
    if any(mid not in org_rows for mid in members):
        raise ValueError('CONTACT_GROUP_MEMBER_NOT_IN_SOURCE_INVENTORY')
    if any(org_rows[mid].get('geometry_sha256') is None for mid in members):
        raise ValueError('CONTACT_GROUP_HAS_UNSUPPORTED_MEMBER_GEOMETRY')
    relation_data = json.loads(RELATIONS.read_text(encoding='utf-8'))
    if relation_data.get('dataset_id') != 'client:szu-comm:3020301113b:intake-20261021:v1':
        raise ValueError('RELATION_EVIDENCE_DATASET_MISMATCH')
    relation_sources = relation_data.get('source_files', {})
    if (relation_sources.get('before', {}).get('sha256') != ORG_HASH or
            relation_sources.get('after', {}).get('sha256') != EDIT_HASH):
        raise ValueError('RELATION_EVIDENCE_SOURCE_HASH_MISMATCH')
    pair_map = _candidate_map(relation_data)
    matches = []
    edit_members = set()
    for oid in members:
        row = org_rows[oid]
        candidates = pair_map.get(oid, [])
        valid_candidates = [item for item in candidates if item['after_identity'] in edit_rows and
                            'F.Cu' in edit_rows[item['after_identity']].get('layers', [])]
        edit_members.update(item['after_identity'] for item in valid_candidates)
        matches.append({
            'org_identity': oid,
            'kind': row['kind'],
            'bounds_mm': row.get('bounds_mm'),
            'correspondence_status': 'NO_CANDIDATE_UNDER_RECORDED_GATES' if not valid_candidates else
                'MUTUAL_UNIQUE' if len(valid_candidates) == 1 and valid_candidates[0]['status'] == 'mutual_unique_registered_center' else
                'GEOMETRIC_CANDIDATE',
            'candidates': valid_candidates,
        })
    visible_ids = [oid for oid in members if org_geoms[oid].intersects(box(*org_geoms[oid].bounds))]
    all_bounds = [org_geoms[oid].bounds for oid in visible_ids]
    bounds = [min(b[0] for b in all_bounds), min(b[1] for b in all_bounds),
              max(b[2] for b in all_bounds), max(b[3] for b in all_bounds)]
    cx, cy = (bounds[0] + bounds[2]) / 2, (bounds[1] + bounds[3]) / 2
    span_x, span_y = bounds[2] - bounds[0], bounds[3] - bounds[1]
    crop_w = max(span_x + 0.30, 1.6)
    crop_h = max(span_y + 0.30, crop_w / 1.38)
    crop = [cx - crop_w / 2, cy - crop_h / 2, cx + crop_w / 2, cy + crop_h / 2]
    kind_counts = dict(sorted(__import__('collections').Counter(org_rows[o]['kind'] for o in members).items()))
    if focus:
        focus['seed_labels'] = {}
        focus['edit_seed_labels'] = {}
        focus['edit_supplemental_identities'] = []
        focus['supplemental_center_candidates'] = []
        focus['seed_correspondences'] = []
        for index, identity in enumerate(focus['selected_seed_identities'], start=1):
            tag = f'S{index}'
            focus['seed_labels'][identity] = tag
            match = next((item for item in matches if item['org_identity'] == identity), None)
            candidates = match['candidates'] if match else []
            official_ids = {candidate['after_identity'] for candidate in candidates}
            for candidate in candidates:
                focus['edit_seed_labels'].setdefault(candidate['after_identity'], tag)
            if org_rows[identity].get('kind') == 'gr_circle':
                before_shape = org_geoms[identity]
                before_center = (before_shape.centroid.x, before_shape.centroid.y)
                near = []
                for edit_id, edit_row in edit_rows.items():
                    if edit_row.get('kind') != 'gr_circle' or 'F.Cu' not in edit_row.get('layers', []):
                        continue
                    edit_shape = edit_geoms.get(edit_id)
                    if edit_shape is None:
                        continue
                    after_center = (edit_shape.centroid.x, edit_shape.centroid.y)
                    displacement = math.dist(before_center, after_center)
                    if displacement <= 0.025:
                        near.append((displacement, edit_id, edit_shape))
                near.sort(key=lambda item: (item[0], item[1]))
                focus['supplemental_center_candidates'].append({
                    'label': tag,
                    'org_identity': identity,
                    'search': 'F.Cu gr_circle center distance after independent F.Mask registration',
                    'display_gate_mm': 0.025,
                    'registered_org_center_mm': list(before_center),
                    'candidates': [{
                        'edit_identity': edit_id,
                        'center_distance_mm': displacement,
                        'edit_center_mm': [shape.centroid.x, shape.centroid.y],
                        'recorded_relation_candidate': edit_id in official_ids,
                    } for displacement, edit_id, shape in near],
                })
                for _, edit_id, _ in near:
                    focus['edit_seed_labels'].setdefault(edit_id, tag)
                    if edit_id not in official_ids:
                        focus['edit_supplemental_identities'].append(edit_id)
            focus['seed_correspondences'].append({
                'label': tag,
                'org_identity': identity,
                'source_kind': org_rows[identity]['kind'],
                'correspondence_status': match['correspondence_status'] if match else 'NOT_IN_LOCAL_OBJECT_REGISTER',
                'candidates': candidates,
            })
        focus['edit_supplemental_identities'] = sorted(set(focus['edit_supplemental_identities']))
    edit_display_members = edit_members | set((focus or {}).get('edit_supplemental_identities', []))
    org_centerlines = _segment_centerlines(org_raw, org_rows, set(members))
    edit_centerlines = _segment_centerlines(edit_raw, edit_rows, edit_display_members)
    for item in matches:
        if item['org_identity'] in org_centerlines:
            item['display_centerline'] = org_centerlines[item['org_identity']]
        for candidate in item['candidates']:
            if candidate['after_identity'] in edit_centerlines:
                candidate['edit_display_centerline'] = edit_centerlines[candidate['after_identity']]
    output.mkdir(parents=True, exist_ok=True)
    svg_path = output / 'contact_group.svg'
    summary = {'member_count': len(members), 'kind_counts': kind_counts}
    _render_svg(svg_path, 'Copper contact group · paired source review', cx, bounds, crop,
                org_rows, org_geoms, edit_rows, edit_geoms, set(members), edit_display_members,
                pair_map, summary,
                {identity: tag for identity, tag in (focus or {}).get('seed_labels', {}).items()},
                {identity: tag for identity, tag in (focus or {}).get('edit_seed_labels', {}).items()},
                set((focus or {}).get('edit_supplemental_identities', [])),
                org_centerlines, edit_centerlines)
    report = {
        'schema': 'org-edit-copper-contact-review-v1',
        'dataset_id': 'client:szu-comm:3020301113b:intake-20261021:v1',
        'source_files': {'ORG': {'sha256': ORG_HASH, 'path': 'ORG/top.kicad_pcb'},
                         'EDIT': {'sha256': EDIT_HASH, 'path': 'EDIT/top_layer.kicad_pcb'}},
        'upstream_evidence': {
            'family_map_catalogue': {
                'path': str(MAP_DB.relative_to(ROOT)),
                'sha256': _file_sha256(MAP_DB),
                'source_revision': ORG_REVISION,
                'map_revision': MAP_REVISION,
            },
            'registered_relation_evidence': {
                'path': str(RELATIONS.relative_to(ROOT)),
                'sha256': _file_sha256(RELATIONS),
                'dataset_id': relation_data['dataset_id'],
                'registration_source_layer': relation_data['registration']['source_layer'],
                'registration_model': relation_data['registration']['transform_model'],
                'registration_support': relation_data['registration']['inlier_count'],
                'registration_tolerance_mm': relation_data['registration']['tolerance_mm'],
            },
        },
        'org_map_revision': ORG_REVISION,
        'group_map_revision': MAP_REVISION,
        'contact_group_id': component_id,
        'local_seed_cohort': focus,
        'contact_predicate': group.get('predicate'),
        'group_bounds_mm': bounds,
        'display_roi_mm': crop,
        'group_member_count': len(members),
        'kind_counts': kind_counts,
        'edit_candidate_member_count': len(edit_members),
        'org_members': matches,
        'edit_candidate_identities': sorted(edit_members),
        'edit_supplemental_identities': (focus or {}).get('edit_supplemental_identities', []),
        'unsupported_neighbor_count': sum(1 for oid, row in edit_rows.items()
            if 'F.Cu' in row.get('layers', []) and not row.get('geometry_sha256')
            and row.get('bounds_mm') and box(*row['bounds_mm']).intersects(box(*crop))),
        'limits': [
            'ORG membership is persisted nominal same-layer geometric contact, not a semantic component or net.',
            'EDIT members are attached by existing geometric relation candidates; candidates are not verified identity.',
            'The preview renders supported source-derived native geometry; it does not use the Gerber plot or establish plot fidelity.',
            'A missing pair means only no candidate passed the recorded matching gates.',
            'No electrical, engineering, enhancement-rule, or manufacturing acceptance is claimed.'
        ],
    }
    (output / 'pair_register.json').write_text(json.dumps(report, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    counts = __import__('collections').Counter(row['correspondence_status'] for row in matches)
    cohort_blurb = ''
    if focus:
        seed_rows = focus.get('seed_correspondences', [])
        seed_counts = __import__('collections').Counter(row['correspondence_status'] for row in seed_rows)
        cohort_blurb = (
            f"The focused cohort uses anchor `{focus['anchor_seed_identity']}` and a {focus['radius_mm']:.3f} mm center radius; "
            f"it includes {len(seed_rows)} stored seed candidates. Seed statuses: {dict(seed_counts)}. "
            f"The extra center-neighborhood search found {len(focus.get('edit_supplemental_identities', []))} EDIT review-only shapes. "
            'That 0.025 mm display gate is exploratory and does not promote those shapes to matches.\n\n'
        )
    (output / 'README.md').write_text(
        '# ORG↔EDIT copper group review\n\n'
        '## What this artifact shows\n\n'
        f'It pairs a local review cohort within stored ORG F.Cu same-layer contact group `{component_id}`. '
        f'The selected ORG cohort has {len(members)} source objects ({kind_counts}) and X/Y bounds {bounds}. '
        f'Existing correspondence evidence links {len(edit_members)} EDIT source objects; the cohort relation statuses are {dict(counts)}.\n\n'
        + cohort_blurb +
        'Gold/cyan shapes in `contact_group.svg` are source `gr_circle`/`gr_poly` fills. Rose lines are source segment centerlines drawn thin for readability; their source widths are retained in `pair_register.json`. Muted gray geometry gives board context. Both panes use the recorded F.Mask-only registration; F.Cu was excluded from alignment.\n\n'
        '## How to read the correspondence\n\n'
        'S-labels identify stored ORG local-seed candidates and their linked EDIT candidate objects. Dark seed outlines show the seed primitives. White dashed EDIT circles are additional nearby-center review candidates only; distances use registered coordinates with a 0.025 mm exploratory display gate. In this crop, two ORG circles have nearby EDIT circles at 0.020 mm and 0.019 mm, and another ORG circle has an extra unlinked EDIT circle 0.002828 mm from the already recorded candidate. Treat those as unresolved alternatives pending manual review.\n\n'
        'The source bytes are hash-bound and unchanged. Geometry contact and candidate matching do not establish pad/terminal identity, net connectivity, enhancement intent, or manufacturing correctness. This cohort was selected by stored geometry and a matched round-feature expansion candidate; it is a representative review candidate, not a claim that it is the exact screenshot crop. See `pair_register.json` for every source byte-span identity, relation label, metric, and limitation.\n', encoding='utf-8')
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--contact-group-id', required=True)
    parser.add_argument('--focus-seed-id', help='Limit the review to nearby stored land candidates and their incident traces')
    parser.add_argument('--focus-radius-mm', type=float, default=0.42)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    output = args.output if args.output.is_absolute() else ROOT / args.output
    report = build(args.contact_group_id, output, args.focus_seed_id, args.focus_radius_mm)
    print(json.dumps({
        'status': 'BUILT',
        'output': str(output),
        'group_member_count': report['group_member_count'],
        'kind_counts': report['kind_counts'],
        'relation_edit_candidate_count': report['edit_candidate_member_count'],
        'supplemental_center_candidate_count': len(report['edit_supplemental_identities']),
        'seed_statuses': {row['label']: row['correspondence_status'] for row in report['local_seed_cohort']['seed_correspondences']} if report['local_seed_cohort'] else None,
    }, sort_keys=True))


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({'status': 'FAIL', 'error': str(exc)}))
        raise SystemExit(1)
