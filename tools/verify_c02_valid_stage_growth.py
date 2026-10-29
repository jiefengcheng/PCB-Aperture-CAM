#!/usr/bin/env python3
"""Replay the saved focused C02 construction and verify complete final geometry.

Accepts a standalone packet directory; no external project path is required.
This is author-side reproducibility evidence, not independent review.
"""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import hashlib,json
from shapely import from_wkb,to_wkb
from shapely.affinity import scale
from shapely.geometry import box,Point
from shapely.ops import unary_union
from src.crop_stage_growth import GrowthContract,GrowthScene,check_proposal,fit_rectangle,fit_round_circle

def main(path):
    p=Path(path);report=json.loads((p/'result.json').read_text());contract=GrowthContract(**report['contract'])
    source=(p/'inputs/ORG_source.kicad_pcb').read_bytes()
    assert hashlib.sha256(source).hexdigest()==report['source_sha256']
    bank=json.loads((p/'inputs/source_manifest.json').read_text());objects=[]
    for r in bank['objects']:
        b=(p/'inputs/source_wkb'/f"{r['geometry_sha256']}.wkb").read_bytes()
        assert hashlib.sha256(b).hexdigest()==r['geometry_sha256']
        assert r['id']==f"{report['source_sha256']}:bytes:{r['source_span'][0]}:{r['source_span'][1]}"
        objects.append({'source_id':r['id'],'geometry':from_wkb(b),'trace_width_mm':r['trace_width_mm']})
    scene=GrowthScene(objects,contract);byid=scene.objects;crop=box(*report['viewport_mm'])
    d=json.loads((p/'t01/decision.json').read_text());sid=d['source_id'];core=byid[sid]['geometry'];center=(core.centroid.x,core.centroid.y)
    cap=Point(*center).buffer(1.5*d['original_radius_mm'],quad_segs=contract.quad_segs)
    candidate,radius,check=fit_round_circle(core,center,d['original_radius_mm'],d['desired_radius_mm'],scene.neighbors(sid,cap,d['aliases']),crop,contract=contract)
    saved=from_wkb((p/'t01/candidate.wkb').read_bytes())
    assert check['passed'] and candidate.symmetric_difference(saved).area<=1e-12
    assert abs(radius-d['actual_radius_mm'])<1e-12
    scene.accept(sid,saved)
    outcomes=[]
    for d in json.loads((p/'t02/decisions.json').read_text()):
        rid=d['source_id'];core=byid[rid]['geometry'];cap=scale(core,1.25,1.25,origin=core.centroid)
        candidate,factors,check=fit_rectangle(core,scene.neighbors(rid,cap),crop,contract=contract)
        saved=from_wkb((p/f"t02/{d['key']}_candidate.wkb").read_bytes())
        assert check['passed'] and candidate.symmetric_difference(saved).area<=1e-12
        assert hashlib.sha256(to_wkb(saved)).hexdigest()==d['candidate_sha256']
        assert len(saved.exterior.coords)==5 and not saved.interiors
        assert max(factors)<=1.25 and min(factors)>=1.0
        assert (candidate.difference(core).area>1e-10)==d['objective_completed']
        scene.accept(rid,saved);outcomes.append(d['objective_completed'])
    for rid,g in scene.replacements.items():
        core=byid[rid]['geometry']
        cap=Point(*center).buffer(1.5*json.loads((p/'t01/decision.json').read_text())['original_radius_mm'],quad_segs=contract.quad_segs) if rid==sid else scale(core,1.25,1.25,origin=core.centroid)
        assert check_proposal(core,g,scene.neighbors(rid,cap),crop=crop,cap=cap,contract=contract)['passed']
    original=from_wkb((p/'source_baseline/copper.wkb').read_bytes())
    t01=from_wkb((p/'t01/cumulative.wkb').read_bytes());t02=from_wkb((p/'t02/cumulative.wkb').read_bytes())
    assert original.difference(t01).area<=1e-12 and t01.difference(t02).area<=1e-12
    rebuilt=original.union(unary_union([g.difference(byid[r]['geometry']) for r,g in scene.replacements.items()]))
    assert rebuilt.symmetric_difference(t02).area<=1e-12
    print(json.dumps({'status':'PASS_AUTHOR_SIDE_REPLAY','source_objects':len(objects),'replayed_circle_targets':1,
          'replayed_rectangle_targets':len(outcomes),'growth_objectives_met':sum(outcomes),
          'growth_objectives_unmet':len(outcomes)-sum(outcomes),'final_scene_checks':'PASS_MODEL_SPACE',
          'freeze_status':report['freeze_status']}))

if __name__=='__main__':main(sys.argv[1])
