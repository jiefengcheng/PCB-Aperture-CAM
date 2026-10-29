#!/usr/bin/env python3
"""Verify the complete source scene with unchanged trace inputs only."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import hashlib,json
from shapely.ops import unary_union
from src.trace_width_clearance import verify_width_scene
from tools.run_c02_four_attachment_diagnostic_v2 import compute


def main():
    pre,inventory,qualification,out=map(Path,sys.argv[1:])
    assert not out.exists()
    report,g=compute(pre);scene=g['scene']
    inv=json.loads((inventory/'TRACE_ENDPOINT_INVENTORY.json').read_text())
    q=json.loads((qualification/'CHAIN_CONTACT_QUALIFICATION.json').read_text())
    allowed={r['component_id'] for r in q['chains'] if r['status']=='SOURCE_CHAIN_GEOMETRICALLY_QUALIFIED_FOR_WIDTH_FEASIBILITY'}
    chains=[r for r in inv['components'] if r['component_id'] in allowed]
    covered={sid for r in chains for sid in r['source_ids']}
    assert len(covered)==sum(len(r['source_ids']) for r in chains)
    traces=[]
    for row in chains:
        original=unary_union([scene.objects[sid]['geometry'] for sid in row['source_ids']])
        traces.append(dict(id=row['component_id'],original=original,candidate=original,
                           verified_original_width_mm=row['original_widths_mm'][0]))
    fixed=[dict(id=sid,geometry=scene.replacements.get(sid,r['geometry']),trace_width_mm=r['trace_width_mm'])
           for sid,r in scene.objects.items() if sid not in covered]
    result=verify_width_scene(traces,fixed)
    assert result['passed'] and result['new_exposed_copper_area_mm2']==0
    out.mkdir(parents=True)
    result.update(source_sha256=report['source_sha256'],source_object_count=len(scene.objects),
        source_primitives_collapsed_into_traces=len(covered),factor=1.,
        source_trace_width_growth='NOT_RUN',stage_acceptance='NONE',T02='PENDING_BATCH_AUDIT_NOT_FROZEN',
        original_unchanged_relationships='Retained, not independently requalified by this no-change growth check')
    (out/'UNCHANGED_FULL_SCENE_CHECK.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps({k:result[k] for k in ['passed','scene_object_count','fixed_object_count','trace_count','source_object_count','source_primitives_collapsed_into_traces','new_exposed_copper_area_mm2']}))


if __name__=='__main__':main()
