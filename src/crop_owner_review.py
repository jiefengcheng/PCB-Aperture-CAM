"""Apply hash-bound, named owner edits to frozen T01 target radii."""
from __future__ import annotations
import math
from src.crop_diameter_selection import admissible_diameters
from src.crop_square_neighbor_experiment import inscribed_square, facing_square_side


def select_owner_review_targets(root, policy, sites):
    """Freeze reviewed radii, then apply only the owner's named sizing edits."""
    import copy, hashlib, json
    root=root.resolve()
    def read_bundle(relative, expected):
        folder=(root/relative).resolve()
        if not folder.is_relative_to(root/'out'):raise ValueError('REVIEW_BUNDLE_OUTSIDE_PROJECT_OUT')
        raw=(folder/'report.json').read_bytes()
        if hashlib.sha256(raw).hexdigest()!=expected:raise ValueError('REVIEW_REPORT_HASH_MISMATCH')
        report=json.loads(raw)
        if report['source_sha256']!=policy['source_sha256']:raise ValueError('REVIEW_SOURCE_MISMATCH')
        return report
    reviewed=read_bundle(policy['previous_bundle'],policy['previous_report_sha256'])
    undo=read_bundle(policy['undo_reference_bundle'],policy['undo_reference_report_sha256'])
    bykey={d['key']:d for d in reviewed['decisions']};oldkeys={d['key']:d for d in undo['decisions']}
    byid={s['source_id']:s for s in sites}
    if set(byid)!={d['source_id'] for d in reviewed['decisions']}:raise ValueError('REVIEW_SITE_IDENTITY_MISMATCH')
    targets={d['source_id']:d['proposed_radius_mm'] for d in reviewed['decisions']}
    records={d['source_id']:copy.deepcopy(d['size_class']) for d in reviewed['decisions']}
    changes=[]
    for key in policy['undo_sites']:
        current,old=bykey[key],oldkeys[key]
        if current['source_id']!=old['source_id'] or old['proposed_radius_mm']>current['proposed_radius_mm']:raise ValueError('INVALID_OWNER_UNDO_REFERENCE')
        targets[current['source_id']]=old['proposed_radius_mm']
        changes.append({'key':key,'source_id':current['source_id'],'reason':'OWNER_CONFIRMED_UNDO','diameter_mm':2*old['proposed_radius_mm']})
    for key,neighbor_key in policy['square_recess_neighbors'].items():
        sid=bykey[key]['source_id'];s=byid[sid]
        targets[sid]=max(admissible_diameters(s['radius'],policy['diameter_classes_mm']))/2
        s['square_recess_neighbor_id']=bykey[neighbor_key]['source_id']
        changes.append({'key':key,'source_id':sid,'reason':'OWNER_SPECIFIC_SQUARE_GUIDED_RECESS','neighbor_key':neighbor_key,'diameter_mm':2*targets[sid]})
    groups=copy.deepcopy(reviewed['groups'])
    for group in groups:
        if len(group['site_ids'])!=2:continue
        a,b=(byid[group[key]] for key in ['square_anchor_id','square_follower_id'])
        side=facing_square_side(inscribed_square(a['center'],targets[a['source_id']],orientation_degrees=policy['orientation']),a['center'],b['center'])
        group['square_radius_bound_mm']=sum(side['normal'][j]*(b['center'][j]-a['center'][j]) for j in range(2))-policy['construction_gap']-policy['safety']-targets[a['source_id']]/math.sqrt(2)
    for sid,s in byid.items():
        radius=targets[sid]
        if not s['radius']<=radius<=1.5*s['radius']:raise ValueError('OWNER_EDIT_EXCEEDS_HARD_CAP_OR_SHAVES_CORE')
        record=records[sid];record.pop('round_opportunity',None)
        record.update(proposed_radius_mm=radius,selected_diameter_mm=2*radius,category_mm=2*radius if radius>s['radius'] else None,
            original_keep=radius==s['radius'],limits=[{'reason':'FROZEN_REVIEW_TARGET'}],desired_diameter_mm=max(record['desired_diameter_mm'],2*radius))
        for change in changes:
            if change['source_id']==sid:record['limits'].append(change)
    return targets,records,groups,changes
