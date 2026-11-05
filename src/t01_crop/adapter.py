"""Generic ROI adapter using the existing T01 geometry kernel, not shared lands."""
import math
from pathlib import Path
from shapely import to_wkb
from shapely.geometry import box
from src.stage_abi.store import canonical,digest
from src.stage_abi.contracts import fail
from src.stage_abi.journal import journalled
from src.stage_abi.runtime import check_output
from src.crop_balanced_t01 import CropSettings,WorkingScene,choose_priorities
from src.crop_diameter_selection import select_targets,promote_round_priorities
from src.crop_circle_sources import site_record
from src.t01_abi.adapter import InteractionAdapter
from .policy import validate_policy,HEADER,CONCENTRIC_CENTER_EPS_MM
from .source import context

def groups_for(sites,pairs,boundary,gap):
    byid={s['source_id']:s for s in sites};used=set(boundary);groups=[]
    for pair in pairs:
        if set(pair)<=byid.keys() and not set(pair)&boundary:groups.append((list(pair),'source-identity reviewed pair'));used.update(pair)
    edges=[]
    for i,a in enumerate(sites):
        for b in sites[i+1:]:
            distance=math.dist(a['center'],b['center'])
            if distance-1.5*(a['radius']+b['radius'])<=gap:
                edges.append((distance/(a['radius']+b['radius']),min(a['source_id'],b['source_id']),max(a['source_id'],b['source_id'])))
    for _,a,b in sorted(edges):
        if a not in used and b not in used:groups.append(([a,b],'nearest available competing pair'));used.update((a,b))
    groups.extend(([s['source_id']],'ROI boundary KEEP' if s['source_id'] in boundary else 'unpaired singleton') for s in sites if s['source_id'] not in used or s['source_id'] in boundary)
    result=[dict(group_id=f'G{i+1:02d}',site_ids=ids,rule=rule) for i,(ids,rule) in enumerate(groups)]
    for group in result:
        if len(group['site_ids'])!=2:continue
        a,b=(byid[sid] for sid in group['site_ids'])
        distance=math.dist(a['center'],b['center'])
        if distance>CONCENTRIC_CENTER_EPS_MM:continue
        outer,inner=sorted((a,b),key=lambda s:(-s['radius'],s['source_id']))
        if (outer['radius']<=inner['radius'] or not outer['core'].contains(inner['core']) or not outer['core'].boundary.disjoint(inner['core'])
            or outer['core'].area<=inner['core'].area):
            fail('T01_CONCENTRIC_NESTING_NOT_ESTABLISHED','No source-proven strictly nested concentric pair')
        group.update(apply_square_bound=False,concentric_source_proof=dict(
            outer_source_id=outer['source_id'],inner_source_id=inner['source_id'],
            center_distance_mm=distance,center_epsilon_mm=CONCENTRIC_CENTER_EPS_MM,
            outer_core_sha256=digest(to_wkb(outer['core'],byte_order=1)),
            inner_core_sha256=digest(to_wkb(inner['core'],byte_order=1)),
            original_containment=True,
            reason='No defined facing direction; both distinct sources retain all ordinary constraints'))
    return result

class CropAdapter(InteractionAdapter):
    def describe(self):
        v=super().describe();files=sorted(Path(__file__).parent.glob('*.py'))
        v.update(implementation=digest(canonical(dict(kernel=v['implementation'],crop_sources={p.name:digest(p.read_bytes()) for p in files}))),
                 source_support='PCB data ABI verified ROI; dynamic complete graphic-circle inventory; full original source context',
                 pagination='100 records per content-addressed source/inspection/comparison page; counts derive from actual source inventory, no fixed target/source count caps',
                 english_dialect=HEADER)
        return v
    def _context(self,store,scene,policy):
        validate_policy(policy);return context(store,scene,policy)
    def _allocate(self,raw,rows,shapes,sites,policy,binding):
        from src.t01_canonical import allocate
        return allocate(raw,rows,shapes,sites,policy,binding)
    def verify(self,store,scene,policy,plan,candidate,proof_scope,checkpoint):
        if proof_scope!={'scope':'complete-crop-t01-source-reconstruction'}:fail('PROOF_SCOPE_UNSUPPORTED','Crop T01 reconstruction required')
        expected=journalled('t01-interaction-verification-reconstruction',dict(plan_sha256=digest(canonical(plan))),lambda:self._compute(store,scene,policy,plan,checkpoint))
        for k,v in expected.items():
            if canonical(candidate.get(k))!=canonical(v):fail('T01_SEMANTIC_RECONSTRUCTION_MISMATCH',k)
        check_output(store,scene,plan,candidate,replacements=expected['replacements'])
        protected=digest(canonical({r['source_id']:r['geometry_ref'] for r in scene['objects'] if r['source_id'] not in expected['replacements']}))
        if candidate.get('protected_source_map_sha256')!=protected:fail('T01_PROTECTED_SOURCE_MAP_CHANGED','Unselected source')
        return dict(passed=True,failures=[],family=self.describe()['family'],reconstructed_sites=expected['unique_sites'],
            reconstructed_alias_occurrences=expected['source_occurrences'],final_assembled_checks=len(expected['final_checks']),
            neighbor_response_sites=expected['neighbor_response_sites'],evolving_companion_response_sites=expected['evolving_companion_response_sites'],
            scope='Data-ABI-bound crop; complete source/ROI coverage, allocation, contour reconstruction and assembled finite-surface checks; no independent or manufacturing qualification')
