#!/usr/bin/env python3
"""Rebuild continuation-aware C02 source eligibility without diagnostic caches.

Read-only source qualification. Output paths are proposals, not acceptance.
The land scene and original source/path definitions remain immutable.
"""
import argparse
import hashlib
import json
import platform
import sys
from importlib.metadata import version
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from shapely import STRtree, to_wkb
from shapely.geometry import box
from shapely.ops import unary_union
from sexpdata import loads
import shapely
from src.crop_circle_sources import verify_assets
from src.native_inventory import arc_points
from src.trace_growth_eligibility import classify_stroke, overlapping_parallel_fill_witness, VERSION
from src.filled_copper_source_role import buried_route_witness, bulk_boundary_route_witness, ROLE_VERSION
from src.source_bulk_components import bind_bulk_regions, source_bulk_role
from tools.run_c02_four_attachment_diagnostic_v2 import compute


def select_complete_parent_runs(paths):
    """Crop selects original traces, never independently scales remote fragments."""
    active={r['parent_route_id'] for r in paths if r['definition_status'].startswith('VISIBLE')}
    for row in paths:
        visible=row['definition_status'].startswith('VISIBLE')
        if row['parent_route_id'] in active:
            row['definition_status']='VISIBLE_COMPLETE_UNIFORM_PATH_PROPOSAL_CONTACT_CHECKS_RETAINED'
            row['selection_role']='CROP_EXPOSED_RUN' if visible else 'REMOTE_ELIGIBLE_RUN_OF_CROP_SELECTED_ORIGINAL_TRACE'
        else:
            row['selection_role']='REMOTE_UNRELATED_CONTEXT_NOT_SELECTED'
    return paths


def digest(blob):
    return hashlib.sha256(blob).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def native_rows(source, manifest, identities):
    """Parse pinned native fragments; never reconstruct cached source copper."""
    source_hash = digest(source)
    result = {}
    for sid in sorted(identities):
        prefix, start, end = sid.rsplit(':', 2)
        if prefix != source_hash + ':bytes':
            raise ValueError('SOURCE_HASH_OR_ID_MISMATCH')
        a, b = int(start), int(end)
        if not 0 <= a < b <= len(source):
            raise ValueError('INVALID_NATIVE_SOURCE_SPAN')
        node = loads(source[a:b].decode())
        kind = str(node[0])
        attrs = {str(v[0]): v[1:] for v in node[1:] if isinstance(v, list) and v}
        if (kind not in ('segment', 'arc') or kind != manifest[sid]['kind']
                or list(map(str, attrs.get('layer', []))) != ['F.Cu']):
            raise ValueError('SUPPORTED_NATIVE_FCU_TRACE_REQUIRED')
        width = float(attrs['width'][0])
        if width != manifest[sid]['trace_width_mm'] or width <= 0:
            raise ValueError('ORIGINAL_WIDTH_NOT_VERIFIED')
        result[sid] = dict(kind=kind, attrs=attrs, width=width,
                           fragment_sha256=digest(source[a:b]))
    return result


def edge_runs(parent, eligible):
    runs, run = [], []
    for edge in parent['ordered_source_edges']:
        flags = {sid in eligible for sid in edge['source_alias_ids']}
        if len(flags) != 1:
            raise ValueError('ALIAS_ELIGIBILITY_CONFLICT')
        if True in flags:
            run.append(edge)
        elif run:
            runs.append(run)
            run = []
    if run:
        runs.append(run)
    if (parent['route_type'] == 'CLOSED_UNIFORM_SOURCE_ROUTE' and len(runs) > 1
            and runs[-1][-1] == parent['ordered_source_edges'][-1]
            and runs[0][0] == parent['ordered_source_edges'][0]):
        runs = [runs[-1] + runs[0]] + runs[1:-1]
    return runs


def native_edge_points(edge, native):
    row = native[edge['representative_source_id']]
    attrs = row['attrs']
    a, b = list(map(float, attrs['start'])), list(map(float, attrs['end']))
    start, end = list(map(float, edge['start_decimal_mm'])), list(map(float, edge['end_decimal_mm']))
    if not ((a == start and b == end) or (a == end and b == start)):
        raise ValueError('NATIVE_EDGE_ENDPOINT_BINDING_CHANGED')
    points = arc_points(a, list(map(float, attrs['mid'])), b) if row['kind'] == 'arc' else [a, b]
    if a != start:
        points = list(reversed(points))
    points = [list(v) for v in points]
    points[0], points[-1] = start, end
    return points


def build(pre, source_paths, out, *, exclude_buried_routes=False, exclude_bulk_boundary_builders=False, fixed_bulk_regions=None):
    if not pre.resolve().is_relative_to(ROOT) or not source_paths.resolve().is_relative_to(ROOT):
        raise ValueError('PROJECT_LOCAL_INPUTS_REQUIRED')
    if out.exists() or not out.resolve().is_relative_to(ROOT / 'out'):
        raise ValueError('FRESH_PROJECT_OUTPUT_REQUIRED')
    integrity = verify_assets()
    report, context = compute(pre)
    scene, raw = context['scene'], context['base']['source']
    original = json.loads(source_paths.read_text())
    if (original['source_sha256'] != report['source_sha256']
            or original['cumulative_land_scene_sha256'] != report['cumulative_sha256']):
        raise ValueError('SOURCE_PATH_SCENE_BINDING_MISMATCH')
    manifest = {r['id']: r for r in json.loads((pre / 'inputs/source_manifest.json').read_text())['objects']}
    parents = {sid: p for p in original['paths'] for sid in p['source_ids']}
    if len(parents) != sum(len(p['source_ids']) for p in original['paths']):
        raise ValueError('DUPLICATE_PARENT_SOURCE_MEMBERSHIP')
    segment_ids = {sid for sid, r in manifest.items() if r['kind'] == 'segment'}
    parsed = native_rows(raw, manifest, segment_ids | set(parents))
    if any(p['uniform_original_width_mm'] != parsed[sid]['width'] for sid, p in parents.items()):
        raise ValueError('PARENT_UNIFORM_WIDTH_BINDING_CHANGED')
    ids = sorted(scene.objects)
    geometries = [scene.replacements.get(sid, scene.objects[sid]['geometry']) for sid in ids]
    tree = STRtree(geometries)
    segments = {}
    for sid in sorted(segment_ids):
        row = parsed[sid]
        segments[sid] = dict(id=sid, start_mm=list(map(float, row['attrs']['start'])),
                            end_mm=list(map(float, row['attrs']['end'])), width_mm=row['width'],
                            geometry=scene.objects[sid]['geometry'])
    segment_order = sorted(segments)
    segment_tree = STRtree([segments[sid]['geometry'] for sid in segment_order])
    scope = box(*context['base']['bounds'])
    filled_ids = [sid for sid in ids if manifest[sid]['kind'] in ('gr_poly', 'gr_circle') and manifest[sid]['trace_width_mm'] == 0]
    original_fills = [scene.objects[sid]['geometry'] for sid in filled_ids]
    fill_tree = STRtree(original_fills)
    original_copper = unary_union([scene.objects[sid]['geometry'] for sid in ids]) if exclude_bulk_boundary_builders else None
    bulk_regions, bulk_bindings = {}, []
    if fixed_bulk_regions is not None:
        specification = json.loads(fixed_bulk_regions.read_text())
        if specification['source_sha256'] != report['source_sha256']:
            raise ValueError('BULK_ROLE_SOURCE_HASH_MISMATCH')
        if specification.get('viewport_mm') != list(context['base']['bounds']):
            raise ValueError('BULK_ROLE_VIEWPORT_BINDING_MISMATCH')
        bulk_regions, bulk_bindings = bind_bulk_regions([scene.objects[sid]['geometry'] for sid in ids], specification['seeds'], scope=scope)
    ledger, witnesses = [], {}
    for sid, parent in sorted(parents.items()):
        core = scene.objects[sid]['geometry']
        if digest(to_wkb(core)) != manifest[sid]['geometry_sha256']:
            raise ValueError('SOURCE_GEOMETRY_CACHE_MISMATCH')
        witness = None
        if sid in segments:
            candidates = sorted(segment_order[int(i)] for i in segment_tree.query(core, predicate='intersects'))
            for other in candidates:
                if other != sid:
                    witness = overlapping_parallel_fill_witness(segments[sid], segments[other])
                    if witness is not None:
                        witnesses[sid] = witness
                        break
        neighbor_indices = sorted(int(i) for i in tree.query(core, predicate='intersects') if ids[int(i)] != sid)
        neighbors = [dict(id=ids[i], geometry=geometries[i], kind=manifest[ids[i]]['kind'],
                          trace_width_mm=manifest[ids[i]]['trace_width_mm']) for i in neighbor_indices]
        row = classify_stroke(sid, core, manifest[sid]['trace_width_mm'], manifest[sid]['kind'], neighbors,
                              fill_witness=witness, eligibility_scope=scope,
                              continuation_source_ids=parent['source_ids'])
        if bulk_regions and row['disposition'] == 'ELIGIBLE_EXPOSED_SOURCE_STROKE':
            role = source_bulk_role(sid, core, bulk_regions, scope=scope)
            if role is not None:
                row['disposition'] = 'FIXED_EMBEDDED_OR_FILL'
                row['reasons'].append('SOURCE_CONTRIBUTES_TO_OWNER_IDENTIFIED_FIXED_BULK_REGION')
                row['owner_bulk_role_witness'] = role
        if exclude_buried_routes and row['disposition'] == 'ELIGIBLE_EXPOSED_SOURCE_STROKE':
            attrs = parsed[sid]['attrs']
            start, end = list(map(float, attrs['start'])), list(map(float, attrs['end']))
            points = arc_points(start, list(map(float, attrs['mid'])), end) if parsed[sid]['kind'] == 'arc' else [start, end]
            fill_indices = sorted(int(i) for i in fill_tree.query(core, predicate='intersects'))
            role = buried_route_witness(sid, points, [dict(id=filled_ids[i], geometry=original_fills[i],
                kind=manifest[filled_ids[i]]['kind'], trace_width_mm=0) for i in fill_indices])
            if role is not None:
                row['disposition'] = 'FIXED_EMBEDDED_OR_FILL'
                row['reasons'].append('ENTIRE_NATIVE_ROUTE_BURIED_IN_ORIGINAL_FILLED_COPPER')
                row['buried_route_role_witness'] = role
        if exclude_bulk_boundary_builders and row['disposition'] == 'ELIGIBLE_EXPOSED_SOURCE_STROKE':
            attrs = parsed[sid]['attrs']
            start, end = list(map(float, attrs['start'])), list(map(float, attrs['end']))
            points = arc_points(start, list(map(float, attrs['mid'])), end) if parsed[sid]['kind'] == 'arc' else [start, end]
            role = bulk_boundary_route_witness(sid, points, parsed[sid]['width'], original_copper)
            if role is not None:
                row['disposition'] = 'FIXED_EMBEDDED_OR_FILL'
                row['reasons'].append('ORIGINAL_BULK_COPPER_COVERS_COMPLETE_TWO_WIDTH_SIDE_STRIP')
                row['bulk_boundary_role_witness'] = role
        if parent['route_type'] == 'DEGENERATE_SOURCE_STROKE_CONTEXT':
            row['disposition'] = 'FIXED_EMBEDDED_OR_FILL'
            row['reasons'].append('DEGENERATE_SOURCE_STROKE_NOT_TRACE_ROUTE')
        row.update(parent_route_id=parent['path_id'], crop_seed=core.intersects(scope),
                   fragment_sha256=parsed[sid]['fragment_sha256'], fill_witness=witness)
        ledger.append(row)
    eligible = {r['source_id'] for r in ledger if r['disposition'] == 'ELIGIBLE_EXPOSED_SOURCE_STROKE'}
    paths, ports, exposed_blobs = [], [], {}
    for parent in original['paths']:
        for edges in edge_runs(parent, eligible):
            members = sorted(sid for e in edges for sid in e['source_alias_ids'])
            pid = 'ER-' + digest('\n'.join(members).encode())[:16]
            points = []
            for edge in edges:
                part = native_edge_points(edge, parsed)
                if points and points[-1] != part[0]:
                    raise ValueError('DISCONTINUOUS_NATIVE_EDGE_RUN')
                points.extend(part if not points else part[1:])
            core = unary_union([scene.objects[s]['geometry'] for s in members])
            near = sorted(int(i) for i in tree.query(core, predicate='intersects') if ids[int(i)] not in members)
            exposed = core.difference(unary_union([geometries[i] for i in near])).intersection(scope)
            exposed_blobs[pid] = to_wkb(exposed)
            start, end = edges[0]['start_decimal_mm'], edges[-1]['end_decimal_mm']
            own_ports = []
            for point in (start, end):
                for edge in parent['ordered_source_edges']:
                    if edge in edges or point not in (edge['start_decimal_mm'], edge['end_decimal_mm']):
                        continue
                    for sid in edge['source_alias_ids']:
                        if sid not in eligible:
                            if not core.intersects(scene.objects[sid]['geometry']):
                                raise ValueError('ORIGINAL_EMBEDDED_PORT_CONTACT_MISSING')
                            port = dict(eligible_path_id=pid, point_decimal_mm=point,
                                        fixed_embedded_source_id=sid, geometric_contact_observed=True)
                            own_ports.append(port)
                            ports.append(port)
            paths.append(dict(path_id=pid, component_id=pid, parent_route_id=parent['path_id'],
                              source_ids=members, source_sha256=report['source_sha256'],
                              uniform_original_width_mm=parent['uniform_original_width_mm'],
                              ordered_source_edges=edges, ordered_route_points_mm=points,
                              terminal_points_decimal_mm=[start, end], primitive_trimming='NONE',
                              route_type='CLOSED_UNIFORM_SOURCE_ROUTE' if start == end else 'OPEN_UNIFORM_SOURCE_ROUTE',
                              definition_status='VISIBLE_COMPLETE_UNIFORM_PATH_PROPOSAL_CONTACT_CHECKS_RETAINED' if not exposed.is_empty else 'SOURCE_PATH_VISIBLE_ONLY_OUTSIDE_CROP_CONTEXT',
                              original_core_sha256=digest(to_wkb(core)), original_core_area_mm2=core.area,
                              exposed_in_crop_wkb_sha256=digest(exposed_blobs[pid]),
                              independently_exposed_in_crop_area_mm2=exposed.area,
                              original_junction_ports=own_ports,
                              original_width_transition_ports=parent.get('original_width_transition_ports', []),
                              boundary_rule='Original native junctions at fixed embedded sources or original parent endpoints; no primitive trimming or crop cut'))
    select_complete_parent_runs(paths)
    assigned = [sid for p in paths for sid in p['source_ids']]
    if len(assigned) != len(set(assigned)) or set(assigned) != eligible:
        raise ValueError('ELIGIBLE_SOURCE_ASSIGNMENT_INCOMPLETE')
    crop_seeds = {sid for sid, r in manifest.items() if r['kind'] in ('segment', 'arc') and scene.objects[sid]['geometry'].intersects(scope)}
    if not crop_seeds <= parents.keys():
        raise ValueError('CROP_SOURCE_MISSING_FROM_PARENT_DEFINITIONS')
    result = dict(schema='c02-reproducible-source-eligibility/1', classifier_version=VERSION,
                  buried_source_role_version=ROLE_VERSION if exclude_buried_routes else None,
                  bulk_boundary_source_role_version='native-bulk-boundary-source-role/1' if exclude_bulk_boundary_builders else None,
                  owner_bulk_role_specification_sha256=digest(fixed_bulk_regions.read_bytes()) if fixed_bulk_regions is not None else None,
                  owner_bulk_role_module_sha256=digest((ROOT/'src/source_bulk_components.py').read_bytes()) if fixed_bulk_regions is not None else None,
                  buried_source_role_module_sha256=digest((ROOT/'src/filled_copper_source_role.py').read_bytes()) if (exclude_buried_routes or exclude_bulk_boundary_builders) else None,
                  asset_integrity=integrity, source_sha256=report['source_sha256'],
                  cumulative_land_scene_sha256=report['cumulative_sha256'], viewport_mm=context['base']['bounds'],
                  paths=paths, crop_seed_count=len(crop_seeds), full_source_closure_accounted=len(parents),
                  source_members_after_same_width_expansion=len(eligible), embedded_fixed_source_count=len(parents)-len(eligible),
                  all_source_objects=len(scene.objects), source_path_input_sha256=digest(source_paths.read_bytes()),
                  source_manifest_sha256=digest((pre/'inputs/source_manifest.json').read_bytes()),
                  source_eligibility_module_sha256=digest((ROOT/'src/trace_growth_eligibility.py').read_bytes()),
                  builder_sha256=digest(Path(__file__).read_bytes()),
                  runtime=dict(python=platform.python_version(), shapely=shapely.__version__,
                               geos=shapely.geos_version_string, sexpdata=version('sexpdata')),
                  diagnostic_witness_cache_dependency='NONE; native geometry measured anew',
                  selection_rule='Crop selects original parent traces; all their eligible native runs, including remote runs, share construction and scale; fully covered source objects remain fixed',
                  qualification='SOURCE_ELIGIBILITY_PROPOSAL; no copper editing, clearance or independent acceptance')
    out.mkdir(parents=True)
    (out/'exposed_source_paths').mkdir()
    save(out/'SOURCE_ELIGIBILITY.json', ledger)
    save(out/'FILL_WITNESSES.json', witnesses)
    save(out/'FIXED_EMBEDDED_PORTS.json', ports)
    if fixed_bulk_regions is not None:
        save(out/'OWNER_BULK_ROLE_BINDINGS.json', bulk_bindings)
        (out/'OWNER_BULK_ROLE_SPECIFICATION.json').write_bytes(fixed_bulk_regions.read_bytes())
    save(out/'UNIFORM_SOURCE_PATHS.json', result)
    for pid, blob in exposed_blobs.items():
        (out/'exposed_source_paths'/f'{pid}.wkb').write_bytes(blob)
    print(json.dumps(dict(paths=len(paths), visible=sum(p['definition_status'].startswith('VISIBLE') for p in paths),
                          eligible_source_primitives=len(eligible), fixed_embedded=len(parents)-len(eligible),
                          crop_seeds=len(crop_seeds), original_fill_witnesses=len(witnesses))))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('pre', type=Path)
    parser.add_argument('source_paths', type=Path)
    parser.add_argument('out', type=Path)
    parser.add_argument('--exclude-buried-routes', action='store_true', help='Proposed source-role exclusion; retain original copper, require full native route inside original filled land')
    parser.add_argument('--exclude-bulk-boundary-builders', action='store_true', help='Proposed source-role heuristic; original copper must cover complete one-sided strip twice native width')
    parser.add_argument('--fixed-bulk-regions', type=Path, help='Source-bound owner-identified original bulk objects; role only, never clearance exemption')
    args = parser.parse_args()
    build(args.pre, args.source_paths, args.out, exclude_buried_routes=args.exclude_buried_routes,
          exclude_bulk_boundary_builders=args.exclude_bulk_boundary_builders, fixed_bulk_regions=args.fixed_bulk_regions)
