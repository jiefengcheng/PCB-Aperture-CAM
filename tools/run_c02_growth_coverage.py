#!/usr/bin/env python3
"""Rebuild every rectangle referenced by the saved trace-work candidate records.

The historical source bank is hash-checked and reused as a parser cache. Nothing
in the source board, historical results, or prior focused packet is overwritten.
"""
import sys
sys.dont_write_bytecode = True
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import argparse
import hashlib
import html
import json
import platform
import shutil
from dataclasses import asdict
from shapely import from_wkb, to_wkb
from shapely.affinity import scale
from shapely.geometry import box, Point
from shapely.ops import unary_union
import shapely
from src.crop_circle_sources import verify_assets, path_for
from src.crop_growth_coverage import focused_rectangle_coverage
from src.crop_stage_growth import GrowthContract, GrowthScene, check_proposal, fit_rectangle, fit_round_circle

BASE = ROOT / 'out/crop_dynamic_tasks'
PREVIOUS = BASE / 'c02_valid_stage_growth_20261028_02'
HISTORICAL = BASE / 't02_rectangles_crop_20261025_v69'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def save(path, data):
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + '\n')


def svg_shape(geometry, fill, stroke=None, width=.008):
    if geometry.is_empty:
        return ''
    return (f'<path d="{path_for(geometry)}" fill="{fill}" fill-rule="evenodd"'
            + (f' stroke="{stroke}" stroke-width="{width}"' if stroke else '') + '/>')


def render(path, title, copper, addition, bounds, rows, cores, notes, *, detail=None):
    x0, y0, x1, y1 = bounds
    w, h = x1-x0, y1-y0
    ph = 1720*h/w
    height = int(ph + 390)
    markup = svg_shape(copper.intersection(box(*bounds)), '#ed4260')
    markup += svg_shape(addition.intersection(box(*bounds)), '#21bda8')
    for row in rows:
        core = cores[row['source_id']]
        if not core.intersects(box(*bounds)):
            continue
        color = '#ffe463' if row['selected'] else '#adbdca'
        markup += svg_shape(core, 'none', color, .004 if detail else .006)
        c = core.centroid
        size = .035 if detail else .07
        markup += f'<text x="{c.x}" y="{c.y}" font-family="Arial" font-size="{size}" text-anchor="middle" fill="{color}">{row["key"]}</text>'
    if detail:
        # Exact source contour and complete proposed rectangle; no approximate boxes.
        markup += svg_shape(detail['candidate'], 'none', '#ffffff', .003)
    result = (f'<svg xmlns="http://www.w3.org/2000/svg" width="1800" height="{height}" viewBox="0 0 1800 {height}">'
              f'<rect width="1800" height="{height}" fill="#edf3f7"/>'
              f'<text x="40" y="50" font-family="Arial" font-size="28" fill="#142a3f">{html.escape(title)}</text>'
              '<text x="40" y="82" font-family="Arial" font-size="18" fill="#354d61">Actual ORG finite-width copper · 850c4c74d55717a7 · source-bound geometric candidate</text>'
              f'<svg x="40" y="110" width="1720" height="{ph}" viewBox="{x0} {y0} {w} {h}">'
              f'<rect x="{x0}" y="{y0}" width="{w}" height="{h}" fill="#071621"/>{markup}</svg>')
    for i, line in enumerate(notes):
        result += f'<text x="40" y="{ph+151+i*28}" font-family="Arial" font-size="18" fill="#243b50">{html.escape(line)}</text>'
    path.write_text(result+'</svg>')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    out = args.output.resolve()
    if out.exists() or not out.is_relative_to(ROOT/'out'):
        raise ValueError('FRESH_PROJECT_OUTPUT_REQUIRED')
    assets = verify_assets()
    prior = json.loads((PREVIOUS/'result.json').read_text())
    source_path = ROOT/'dataset/szu-comm_3020301113B_intake_ready_20261021_v2/raw/ORG/top.kicad_pcb'
    source = source_path.read_bytes()
    assert digest(source) == prior['source_sha256']
    assert source == (PREVIOUS/'inputs/ORG_source.kicad_pcb').read_bytes()
    inventory = json.loads((HISTORICAL/'t02_decisions.json').read_text())
    work = json.loads((HISTORICAL/'future_trace_work_items.json').read_text())
    assert inventory['source_sha256'] == work['source_sha256'] == prior['source_sha256']
    previous_decisions = json.loads((PREVIOUS/'t02/decisions.json').read_text())
    rows = focused_rectangle_coverage(inventory['decisions'], work, previous_decisions)
    selected = [r for r in rows if r['selected']]
    assert len(rows) == 80 and len(selected) == 74
    assert all(r['selected'] for r in rows if r['previous_eleven_site_key'])
    out.mkdir(parents=True)
    for d in ('inputs', 'source_baseline', 't01', 't02', 'sites', 'implementation'):
        (out/d).mkdir()
    for name in ('t02_decisions.json', 'future_trace_work_items.json', 'feature_dispositions.json'):
        shutil.copy2(HISTORICAL/name, out/'inputs'/name)
    for name in ('source_manifest.json', 'ORG_source.kicad_pcb'):
        shutil.copy2(PREVIOUS/'inputs'/name, out/'inputs'/name)
    shutil.copytree(PREVIOUS/'inputs/source_wkb', out/'inputs/source_wkb')
    bank = json.loads((out/'inputs/source_manifest.json').read_text())
    objects = []
    for row in bank['objects']:
        blob = (out/'inputs/source_wkb'/f'{row["geometry_sha256"]}.wkb').read_bytes()
        assert digest(blob) == row['geometry_sha256']
        objects.append({'source_id': row['id'], 'geometry': from_wkb(blob),
                        'trace_width_mm': row['trace_width_mm']})
    contract = GrowthContract()
    scene = GrowthScene(objects, contract)
    crop = box(*prior['viewport_mm'])
    source_union = from_wkb((PREVIOUS/'source_baseline/copper.wkb').read_bytes())
    current_union = source_union
    circle = json.loads((PREVIOUS/'t01/decision.json').read_text())
    sid = circle['source_id']
    core = scene.objects[sid]['geometry']
    center = (core.centroid.x, core.centroid.y)
    cap = Point(*center).buffer(1.5*circle['original_radius_mm'], quad_segs=contract.quad_segs)
    candidate, radius, check = fit_round_circle(core, center, circle['original_radius_mm'],
        circle['desired_radius_mm'], scene.neighbors(sid, cap, circle['aliases']), crop, contract=contract)
    assert check['passed']
    scene.accept(sid, candidate)
    t01_addition = candidate.difference(core)
    current_union = current_union.union(t01_addition)
    t01_union = current_union
    circle.update(actual_radius_mm=radius, check=check)
    save(out/'t01/decision.json', circle)
    for name, geom in [('candidate', candidate), ('added_copper', t01_addition), ('cumulative', t01_union)]:
        (out/f't01/{name}.wkb').write_bytes(to_wkb(geom))
    (out/'source_baseline/copper.wkb').write_bytes(to_wkb(source_union))
    decisions = []
    for ordinal, row in enumerate(selected, 1):
        sid = row['source_id']
        core = scene.objects[sid]['geometry']
        assert core.equals(box(*core.bounds))
        cap = scale(core, 1.25, 1.25, origin=core.centroid)
        assert crop.covers(cap)
        neighbors = scene.neighbors(sid, cap)
        candidate, factors, check = fit_rectangle(core, neighbors, crop, contract=contract)
        assert check['passed'], (row['key'], check)
        added = candidate.difference(core)
        exposed = candidate.difference(current_union)
        full_cap_check = check_proposal(core, cap, neighbors, crop=crop, cap=cap, contract=contract)
        near_failures = {}
        for axis, factors_probe in [('X', (min(1.25, factors[0]+.001), factors[1])),
                                    ('Y', (factors[0], min(1.25, factors[1]+.001)))]:
            if factors_probe != factors:
                probe = scale(core, *factors_probe, origin=core.centroid)
                near_failures[axis] = check_proposal(core, probe, neighbors, crop=crop, cap=cap, contract=contract)
        x0,y0,x1,y1 = core.bounds
        d = {**row, 'source_bounds_mm': list(core.bounds), 'candidate_bounds_mm': list(candidate.bounds),
             'source_size_xy_mm': [x1-x0,y1-y0], 'candidate_size_xy_mm': [(x1-x0)*factors[0], (y1-y0)*factors[1]],
             'axis_factors_xy': list(factors), 'candidate_sha256': digest(to_wkb(candidate)),
             'target_added_area_mm2': added.area, 'new_exposed_copper_area_mm2': exposed.area,
             'objective_completed': exposed.area > 1e-10,
             'disposition': ('POSITIVE_EXPOSED_GROWTH' if exposed.area > 1e-10 else 'NO_EXPOSED_GROWTH_NOT_COMPLETED'),
             'check': check, 'full_1p25_cap_check': full_cap_check,
             'next_axis_increment_diagnostics': near_failures,
             'search_limit': 'Two deterministic centered-axis orders, 36 bisections; not global area maximality.'}
        decisions.append(d)
        scene.accept(sid, candidate)
        current_union = current_union.union(added)
        (out/f't02/{row["key"]}_candidate.wkb').write_bytes(to_wkb(candidate))
        (out/f't02/{row["key"]}_added.wkb').write_bytes(to_wkb(added))
        save(out/f'sites/{row["key"]}.json', d)
        print(json.dumps({'site': row['key'], 'done': ordinal, 'total': len(selected),
                          'factors': factors, 'exposed_added_mm2': exposed.area}), flush=True)
    final_checks = []
    for sid, candidate in sorted(scene.replacements.items()):
        core = scene.objects[sid]['geometry']
        is_circle = sid == circle['source_id']
        cap = Point(*center).buffer(1.5*circle['original_radius_mm'], quad_segs=128) if is_circle else scale(core,1.25,1.25,origin=core.centroid)
        check = check_proposal(core, candidate, scene.neighbors(sid, cap, circle['aliases'] if is_circle else ()),
                               crop=crop, cap=cap, contract=contract)
        assert check['passed'], (sid, check)
        final_checks.append({'source_id': sid, 'check': check})
    addition = current_union.difference(t01_union)
    assert source_union.difference(current_union).area <= 1e-12
    assert t01_union.difference(current_union).area <= 1e-12
    save(out/'coverage.json', rows)
    save(out/'t02/decisions.json', decisions)
    save(out/'t02/final_scene_checks.json', final_checks)
    (out/'t02/cumulative.wkb').write_bytes(to_wkb(current_union))
    (out/'t02/added_copper.wkb').write_bytes(to_wkb(addition))
    result = {**prior, 'schema': 'focused-growth-coverage/2', 'asset_integrity': assets,
              'contract': asdict(contract), 'eligible_rectangle_count': len(rows),
              'focused_rectangle_count': len(selected), 'context_only_rectangle_count': len(rows)-len(selected),
              'previously_displayed_rectangle_count': 11, 'newly_covered_rectangle_count': len(selected)-11,
              'source_selection_records': {'clearance_issues': len(work['clearance_issues']), 'items': len(work['items'])},
              'selection_basis': 'All exact rectangle source IDs referenced by saved v69 trace-work records. Membership does not establish a defect.',
              't01_added_area_mm2': t01_addition.area, 't02_added_area_mm2': addition.area,
              't02_completed_targets': sum(d['objective_completed'] for d in decisions),
              't02_uncompleted_targets': [d['key'] for d in decisions if not d['objective_completed']],
              'freeze_status': 'NOT_FROZEN_COVERAGE_AND_CLASSIFIER_AUDIT_PENDING',
              'historical_ledger_dispositions_changed': False,
              'environment': {'python': platform.python_version(), 'shapely': shapely.__version__, 'geos': shapely.geos_version_string},
              'limitations': ['Conservative primitive-pair checker; source-supported adjacent attachment portions may be overconstrained.',
                              'Known former R11 classifier issue is preserved; not a physical impossibility proof.',
                              'No T03, T04, native board write, electrical applicability or manufacturing qualification.']}
    # Avoid carrying stale eleven-target evidence counts into this larger run.
    for name in ('historical_growth_caused_witness_count', 'historical_proposals_rejected_under_revised_contract', 'inherited_exclusion'):
        result.pop(name, None)
    save(out/'result.json', result)
    cores = {r['source_id']: scene.objects[r['source_id']]['geometry'] for r in rows}
    common = ['74 selected rectangles: every source ID referenced by saved trace-work records. 6 gray rectangles are context only.',
              'Red = source/predecessor copper. Teal = exact exposed addition. Gold = selected original contours and IDs.',
              'Complete rectangles, fixed centers; each axis at most 1.25x. All sides, corners and endpoints checked.',
              '20.00 µm hard surface floor; 20.10 µm added-copper guard outside explicit original local attachment ports.',
              'Conservative model-space result; NOT FROZEN. Attachment-classifier limitations remain disclosed.']
    for folder, title, copper, delta in [
        ('source_baseline', 'C02 / 00 — all focused rectangle candidates on actual ORG', source_union, Point().buffer(0)),
        ('t01', 'C02 / 01 — source plus focused round C013 growth', t01_union, t01_addition),
        ('t02', f'C02 / 02 — cumulative legal growth · {result["t02_completed_targets"]}/74 exposed-growth objectives', current_union, addition),
    ]:
        render(out/f'{folder}/full_crop.svg', title, copper, delta, prior['viewport_mm'], rows, cores, common)
    for d in decisions:
        core = cores[d['source_id']]
        cap = scale(core, 1.25, 1.25, origin=core.centroid)
        x0,y0,x1,y1 = cap.bounds
        pad = max(.18, (x1-x0)*.25, (y1-y0)*.25)
        bounds = [x0-pad, y0-pad, x1+pad, y1+pad]
        candidate = scene.replacements[d['source_id']]
        sx,sy = d['axis_factors_xy']
        width,height = d['source_size_xy_mm']; cw,ch = d['candidate_size_xy_mm']
        reasons = sorted({f['reason'] for q in d['next_axis_increment_diagnostics'].values() for f in q['failures']})
        gaps = [q['added_copper_gap_outside_port_mm'] for q in d['check']['pairs']
                if q['added_copper_gap_outside_port_mm'] is not None]
        minimum = f'{min(gaps)*1000:.3f} µm' if gaps else 'not applicable (no checked added portion)'
        notes = [f'{d["key"]}: original {width:.6f} × {height:.6f} mm → {cw:.6f} × {ch:.6f} mm; factors {sx:.6f}, {sy:.6f}.',
                 f'New exposed copper: {d["new_exposed_copper_area_mm2"]:.9f} mm². {d["disposition"]}.',
                 'Gold = exact source outline; white = complete proposed rectangle. Teal = exposed addition in cumulative scene.',
                 f'Minimum checked added-copper gap outside original ports: {minimum}.',
                 'Next increment: '+('rejected by recorded surface-gap checks' if reasons else '1.25 ceiling / no rejection'),
                 f'Native source span: {d["source_id"].split(":bytes:")[1]}; {len(d["trace_work_references"])} exact historical trace-work references.',
                 'No-growth is not a proof of physical infeasibility. Model-space result pending designated audit.']
        render(out/f'sites/{d["key"]}.svg', f'C02 / {d["key"]} — focused rectangle legal-growth detail',
               current_union, candidate.difference(t01_union), bounds, rows, cores, notes, detail={'candidate':candidate})
    table = []
    by_id = {d['source_id']: d for d in decisions}
    for row in rows:
        d = by_id.get(row['source_id'])
        status = d['disposition'] if d else 'CONTEXT_ONLY_NOT_REBUILT'
        sizes = (' → '.join(' × '.join(f'{v:.5f}' for v in d[k]) for k in ('source_size_xy_mm','candidate_size_xy_mm')) if d else 'unchanged context')
        key = f'<a href="sites/{row["key"]}.png">{row["key"]}</a>' if d else row['key']
        table.append(f'<tr><td>{key}</td><td>{status}</td><td>{sizes}</td><td>{len(row["trace_work_references"])}</td><td>{row["previous_eleven_site_key"] or "—"}</td><td>{html.escape(row["source_id"].split(":bytes:")[1])}</td></tr>')
    page = '<!doctype html><meta charset="utf-8"><title>C02 focused rectangle coverage</title><style>body{font:17px system-ui;background:#edf3f7;color:#142a3f;margin:32px}img{width:100%}td,th{padding:8px;border-bottom:1px solid #bcc}table{border-collapse:collapse}section{margin:35px 0}</style><h1>C02 — complete focused candidate coverage</h1>'
    page += f'<p>Previously 11 sites; now all 74 trace-work-referenced rectangles are rebuilt. All 80 eligible rectangles are accounted for: 6 are context only. {result["t02_completed_targets"]} show positive exposed copper growth. T02 NOT FROZEN; no revised T03/T04 execution.</p>'
    page += '<p>Membership in an old trace-work record selects a candidate; it does not establish a clearance defect. Original attachments and inherited unchanged relationships are not automatically repair targets. Conservative attachment classification remains under investigation.</p>'
    for folder, title in [('source_baseline','00 / exact ORG and all candidate IDs'),('t01','01 / focused T01'),('t02','02 / cumulative focused T01 + T02')]:
        page += f'<section><h2>{title}</h2><a href="{folder}/full_crop.png"><img src="{folder}/full_crop.png"></a></section>'
    page += '<h2>Every eligible rectangle</h2><p>Click a selected ID for a geometry-derived close-up. Dimensions are in mm.</p><table><tr><th>Site</th><th>Result</th><th>Source → proposed width × height</th><th>Trace-work records</th><th>Old eleven-site ID</th><th>Source bytes</th></tr>'+''.join(table)+'</table><p>Exact checks: result.json, coverage.json, t02/decisions.json, sites/Rxxx.json. Full source bank and immutable source copy are bundled.</p>'
    (out/'index.html').write_text(page)
    for name in ('src/crop_stage_growth.py','src/crop_growth_coverage.py','tools/run_c02_growth_coverage.py','tools/verify_c02_valid_stage_growth.py','tests/test_crop_stage_growth.py','tests/test_crop_growth_coverage.py'):
        dest = out/'implementation'/name; dest.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(ROOT/name,dest)
    print(json.dumps({'output':str(out), 'selected':len(selected), 'positive_exposed_growth':result['t02_completed_targets'],
                      'uncompleted':result['t02_uncompleted_targets'],'cumulative_checks':'PASS_MODEL_SPACE'}), flush=True)


if __name__ == '__main__':
    main()
