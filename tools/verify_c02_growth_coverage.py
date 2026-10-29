#!/usr/bin/env python3
"""Portable author-side replay of source-bound coverage and growth decisions."""
import sys
sys.dont_write_bytecode = True
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import hashlib
import json
from shapely import from_wkb, to_wkb
from shapely.affinity import scale
from shapely.geometry import box, Point
from shapely.ops import unary_union
from src.crop_growth_coverage import focused_rectangle_coverage
from src.crop_stage_growth import GrowthContract, GrowthScene, fit_round_circle, fit_rectangle, check_proposal


def verify(path):
    p = Path(path)
    result = json.loads((p/'result.json').read_text())
    contract = GrowthContract(**result['contract'])
    source = (p/'inputs/ORG_source.kicad_pcb').read_bytes()
    assert hashlib.sha256(source).hexdigest() == result['source_sha256']
    bank = json.loads((p/'inputs/source_manifest.json').read_text())
    objects = []
    for row in bank['objects']:
        blob = (p/'inputs/source_wkb'/f'{row["geometry_sha256"]}.wkb').read_bytes()
        assert hashlib.sha256(blob).hexdigest() == row['geometry_sha256']
        assert row['id'] == f'{result["source_sha256"]}:bytes:{row["source_span"][0]}:{row["source_span"][1]}'
        objects.append({'source_id':row['id'], 'geometry':from_wkb(blob), 'trace_width_mm':row['trace_width_mm']})
    inventory = json.loads((p/'inputs/t02_decisions.json').read_text())['decisions']
    work = json.loads((p/'inputs/future_trace_work_items.json').read_text())
    assert work['source_sha256'] == bank['source_sha256'] == result['source_sha256']
    assert json.loads((p/'inputs/t02_decisions.json').read_text())['source_sha256'] == result['source_sha256']
    expected = focused_rectangle_coverage(inventory, work)
    coverage = json.loads((p/'coverage.json').read_text())
    assert len(coverage) == 80
    for saved, computed in zip(coverage, expected):
        for key in ('key','source_id','selected','selection_reason','trace_work_references'):
            assert saved[key] == computed[key], (key, saved['key'])
    selected = [r for r in coverage if r['selected']]
    assert len(selected) == 74
    decisions = json.loads((p/'t02/decisions.json').read_text())
    assert [d['source_id'] for d in decisions] == [r['source_id'] for r in selected]
    assert len({d['source_id'] for d in decisions}) == len(decisions)
    scene = GrowthScene(objects, contract)
    crop = box(*result['viewport_mm'])
    source_union = unary_union([r['geometry'].intersection(crop) for r in objects if r['geometry'].intersects(crop)])
    saved_source = from_wkb((p/'source_baseline/copper.wkb').read_bytes())
    assert saved_source.symmetric_difference(source_union).area <= 1e-12
    circle = json.loads((p/'t01/decision.json').read_text())
    sid = circle['source_id']; core = scene.objects[sid]['geometry']
    center = (core.centroid.x, core.centroid.y)
    cap = Point(*center).buffer(1.5*circle['original_radius_mm'], quad_segs=128)
    candidate, radius, check = fit_round_circle(core, center, circle['original_radius_mm'], circle['desired_radius_mm'],
                                              scene.neighbors(sid, cap, circle['aliases']), crop, contract=contract)
    assert check['passed']
    assert abs(radius-circle['actual_radius_mm']) < 1e-12
    assert candidate.symmetric_difference(from_wkb((p/'t01/candidate.wkb').read_bytes())).area <= 1e-12
    scene.accept(sid, candidate)
    t01 = source_union.union(candidate.difference(core))
    current = t01
    completed = 0
    for d in decisions:
        sid = d['source_id']; core = scene.objects[sid]['geometry']
        cap = scale(core, 1.25, 1.25, origin=core.centroid)
        candidate, factors, check = fit_rectangle(core, scene.neighbors(sid, cap), crop, contract=contract)
        assert check['passed']
        assert max(abs(a-b) for a,b in zip(factors,d['axis_factors_xy'])) < 1e-12
        saved_blob = (p/f't02/{d["key"]}_candidate.wkb').read_bytes()
        assert hashlib.sha256(saved_blob).hexdigest() == d['candidate_sha256']
        assert candidate.symmetric_difference(from_wkb(saved_blob)).area <= 1e-12
        assert candidate.equals(box(*candidate.bounds)) and not candidate.interiors
        assert core.difference(candidate).area <= 1e-12
        assert candidate.centroid.distance(core.centroid) <= 1e-12
        assert min(factors) >= 1 and max(factors) <= 1.25
        exposed = candidate.difference(current)
        assert abs(exposed.area-d['new_exposed_copper_area_mm2']) < 1e-10
        assert (exposed.area > 1e-10) == d['objective_completed']
        completed += d['objective_completed']
        scene.accept(sid, candidate)
        current = current.union(candidate.difference(core))
    for sid,candidate in scene.replacements.items():
        core = scene.objects[sid]['geometry']; is_circle = sid == circle['source_id']
        cap = Point(*center).buffer(1.5*circle['original_radius_mm'],quad_segs=128) if is_circle else scale(core,1.25,1.25,origin=core.centroid)
        check = check_proposal(core,candidate,scene.neighbors(sid,cap,circle['aliases'] if is_circle else ()),crop=crop,cap=cap,contract=contract)
        assert check['passed'], (sid,check)
    saved = from_wkb((p/'t02/cumulative.wkb').read_bytes())
    assert current.symmetric_difference(saved).area <= 1e-12
    assert source_union.difference(saved).area <= 1e-12
    assert t01.difference(saved).area <= 1e-12
    assert completed == result['t02_completed_targets']
    assert len(scene.replacements) == len(selected)+1
    print(json.dumps({'status':'PASS_AUTHOR_SIDE_REPLAY', 'source_objects':len(objects),
                      'eligible_rectangles_accounted_for':len(coverage),'focused_rectangles_replayed':len(selected),
                      'positive_exposed_growth':completed,'unchanged_uncompleted':len(selected)-completed,
                      'all_final_scene_checks':'PASS_MODEL_SPACE','freeze_status':result['freeze_status']}))


if __name__ == '__main__':
    verify(sys.argv[1])
