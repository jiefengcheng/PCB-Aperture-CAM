#!/usr/bin/env python3
"""Bind maximal source routes to original junctions, preserving all source IDs."""
import sys,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.uniform_source_paths import uniform_source_paths
from src.source_junction_paths import junction_source_paths
from src.native_inventory import arc_points
from tools.build_c02_uniform_source_paths import main


def build(rows,seeds,source):
    allowed={sid for network in uniform_source_paths(rows,seeds) for sid in network['source_ids']}
    augmented=[]
    for r in rows:
        points=[list(map(float,p)) for p in r['endpoints_decimal_mm']]
        if r['kind']=='arc':
            start,end=map(int,r['source_id'].rsplit(':',2)[-2:]);fragment=source[start:end]
            middle=re.search(rb'\(mid\s+([^\s()]+)\s+([^\s()]+)\)',fragment);assert middle
            points=arc_points(points[0],[float(x) for x in middle.groups()],points[1])
        augmented.append(dict(r,route_points_mm=points))
    paths=junction_source_paths(augmented,allowed)
    assert {sid for r in paths for sid in r['source_ids']}==allowed
    for r in paths:
        r['path_status']='PROPOSED_COMPLETE_UNIFORM_SOURCE_PATH' if r['route_type']!='DEGENERATE_SOURCE_STROKE_CONTEXT' else 'DEGENERATE_SOURCE_STROKE_CONTEXT'
        r['width_construction']='NOT_RUN'
        r['electrical_intent']='NOT_ESTABLISHED'
        r['boundary_rule']='Maximal native route through degree2 nodes and unique straight branch continuations; other branches end at exact original junctions. No primitive trimming.'
    return paths


if __name__=='__main__':main(build)
