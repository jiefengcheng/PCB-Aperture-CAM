"""Verified edge restoration before bounded T04 admission and obstacle setup.

The first integrated family is an identified circular cap over an unchanged
large Region. Requests name complete source occurrences, never cut windows or
board coordinates. Original inputs remain immutable. The working ownership is
separate and lives only for this bounded T04 call; outputs carry a receipt and
are explicitly not qualified as ordinary additive pipeline predecessors.
"""
from contextlib import contextmanager
import copy
import time

from shapely.geometry import Point, box
from shapely.ops import unary_union

from src import component_clearance as cc, source_channel_scope as sc, pin_separation as pin
from src import t04_width_fence as fence
from src.bulk_edge_restore import propose, fingerprint, topology
from src.edge_restoration_settings import capture
from src.copper_corner_workspace import CutPolicy, qualify_bulk_region
from . import pipeline as p


def reject_unqualified_predecessor(scene):
    """Old positive-only export/prior paths must not silently restore a cap."""
    if scene and any(row.get('stage') in ('t04-translated-profile-published','t04-limiting-entry-v2') for row in scene['lineage']):
        raise ValueError('T04_PROFILE_DOWNSTREAM_REPLAY_EXPORT_NOT_QUALIFIED')
    if scene and any(row.get('stage') == 't04-edge-entry-bounded' for row in scene['lineage']):
        raise ValueError('T04_EDGE_ENTRY_DOWNSTREAM_REPLAY_NOT_QUALIFIED')


def _working_context(physical, functional, changed, ledger):
    """Prove source membership correspondence before using a new partition.

    Restrict the first integration to integral sources without frame splits or
    retained native floors. Dropping those floors, or merging a functional
    partition into a physical partition, would change the safety contract.
    """
    if (functional is None or functional.frame_ids or physical.reserved or
            functional.reserved or physical.approved_partial_pockets or
            functional.approved_partial_pockets or
            getattr(physical,'checking_envelopes',{}) or
            getattr(functional,'checking_envelopes',{})):
        raise ValueError('T04_EDGE_ENTRY_UNQUALIFIED_CONTEXT_OR_RETAINED_FLOOR')
    if (set(physical.originals) != set(functional.originals) or
            any(tuple(physical.ids[s]) != tuple(functional.ids[s])
                for s in physical.originals)):
        raise ValueError('T04_EDGE_ENTRY_FUNCTIONAL_PARTITION_DIFFERS')
    replacement=dict(physical.originals, **changed)
    source=unary_union(list(replacement.values()))
    working=cc.Context(source,physical.source_hash,replacement)
    correspondence={}
    for sid in replacement:
        old,new=physical.ids[sid],working.ids[sid]
        if len(old)!=1 or len(new)!=1:
            raise ValueError('T04_EDGE_ENTRY_SOURCE_NOT_ONE_COMPONENT')
        if old[0] in correspondence and correspondence[old[0]]!=new[0]:
            raise ValueError('T04_EDGE_ENTRY_COMPONENT_SPLIT')
        correspondence[old[0]]=new[0]
    if not (len(correspondence)==len(set(correspondence.values()))==
            len(physical.cores)==len(working.cores)):
        raise ValueError('T04_EDGE_ENTRY_COMPONENT_MERGE_OR_LOSS')
    if any(topology(physical.cores[o])!=topology(working.cores[n])
           for o,n in correspondence.items()):
        raise ValueError('T04_EDGE_ENTRY_OWNER_HOLE_TOPOLOGY_CHANGED')
    scope=copy.copy(functional)
    scope.ids={s:tuple(v) for s,v in working.ids.items()}
    scope.index=working.index;scope.cores=working.cores
    scope.originals=replacement;scope.source_objects=replacement
    scope.channels=copy.copy(functional.channels)
    scope.channels.original=working.cores;scope.channels.analytic_source=source
    authority=p.digest(p.canonical(ledger))
    scope.binding=p.digest(p.canonical([functional.binding,authority,working.index.fingerprint]))
    working.binding=p.digest(p.canonical([working.binding,authority]))
    working.functional=scope;scope.physical_context=working
    return working,scope,dict(original_components=len(physical.cores),
        working_components=len(working.cores),component_and_hole_correspondence=True,
        original_to_working_owners=correspondence,
        unchanged_source_occurrences=len(replacement)-len(changed))


@contextmanager
def prepared(store,scene,source_ids,settings,*,policy=None):
    """Capture once, restore once, then let admission/indexing/ladder run.

    All proposed features are checked before publishing working contexts. Any
    failed feature rejects this bounded request as a whole. The complete input
    scene is retained in the receipt; no previous proof is treated as authority
    to skip a fresh geometry or relationship check.
    """
    started=time.perf_counter()
    reject_unqualified_predecessor(scene)
    if not source_ids or len(source_ids)!=len(set(source_ids)):
        raise ValueError('T04_EDGE_ENTRY_EXPLICIT_UNIQUE_FEATURES_REQUIRED')
    old_cc,old_sc,old_fence=cc.ACTIVE,sc.ACTIVE,fence.ACTIVE
    if old_cc is None or old_sc is None or pin.ACTIVE is None:
        raise ValueError('T04_EDGE_ENTRY_SOURCE_AND_PIN_CONTEXT_REQUIRED')
    policy=capture() if policy is None else policy
    rows,current,original=p.operands(store,scene)
    if not set(source_ids)<=set(rows) or set(rows)!=set(old_cc.originals):
        raise ValueError('T04_EDGE_ENTRY_COMPLETE_SOURCE_OCCURRENCES_REQUIRED')
    binding=p.load(store.root.parent/'source.json')
    if binding['source_ref']['sha256']!=scene['source_sha256'] or old_cc.source_hash!=scene['source_sha256']:
        raise ValueError('T04_EDGE_ENTRY_SOURCE_BINDING_CHANGED')
    source=store.get_json(binding['scene_ref'],kind='scene')
    source_rows={r['source_id']:r for r in source['objects']}
    if (set(rows)!=set(source_rows) or any(
            rows[s]['original_ref']!=source_rows[s]['original_ref'] or
            p.digest(p.to_wkb(old_cc.originals[s]))!=source_rows[s]['original_ref']['sha256']
            for s in rows)):
        raise ValueError('T04_EDGE_ENTRY_ORIGINAL_SOURCE_REFERENCE_CHANGED')
    catalogue=store.get_json(binding['source_catalogue_ref'],kind='source-catalogue')
    cut_policy=CutPolicy.from_t04(box(*scene['viewport_mm']),settings,protected_margin_mm=p.CONSTRUCTION_GAP_MM)
    declared={s for slot in pin.ACTIVE.slots for s in slot.pin_ids}
    routes={s for s,r in source_rows.items() if p.t04_trace(r)}
    bulk={};eligibility={}
    for sid,row in source_rows.items():
        g=original[sid]
        if row['metadata'].get('source_kind')!='Region' or g.area<=cut_policy.outline_area_mm2*.05:
            continue
        proof=qualify_bulk_region(row,g,cut_policy,catalogue=catalogue,
            route_members=routes,declared_pin_ids=declared,source_sha256=scene['source_sha256'])
        if proof['established']:
            if not current[sid].equals_exact(g,0):
                raise ValueError('T04_EDGE_ENTRY_REFERENCE_REGION_CHANGED')
            bulk[sid]=g;eligibility[sid]=proof
    if not bulk:raise ValueError('T04_EDGE_ENTRY_NO_QUALIFIED_REFERENCE_REGION')
    reference_body=unary_union(list(bulk.values()))
    changes={};ledger={}
    protected=[('pin:'+str(i),slot.domain)for i,slot in enumerate(pin.ACTIVE.slots)]
    # Requests are bounded by occurrence ids; each window is the WHOLE feature,
    # so no caller can pass a cropped sliver and evade the shared depth limit.
    for sid in sorted(source_ids):
        row=rows[sid];md=row['metadata'];g=current[sid]
        if (row['kind']!='circle' or not md.get('qualified_land') or
                sid in declared or sid in routes or md.get('rectangle_terminal') or
                not g.equals_exact(original[sid],0) or
                any(md.get(k)!=source_rows[sid]['metadata'].get(k)
                    for k in ('qualified_land','center_mm','source_kind','rectangle_terminal'))):
            raise ValueError('T04_EDGE_ENTRY_CAP_FAMILY_NOT_QUALIFIED:'+sid)
        if not reference_body.covers(Point(md['center_mm'])):
            raise ValueError('T04_EDGE_ENTRY_LAND_CENTER_OUTSIDE_BULK')
        window=box(*g.bounds);reference=g.intersection(reference_body)
        contacts=[(s,changes.get(s,c))for s,c in current.items()
                  if s!=sid and c.intersects(g)]
        evidence=dict(kind='UNCHANGED_ELIGIBLE_SOURCE_REGION_EDGE',
                      source_sha256=scene['source_sha256'],eligibility=eligibility)
        after,removed,added,proof=propose(g,reference,window,contacts=contacts,
            protected=protected,reference_evidence=evidence,
            smooth_edge=reference_body.boundary.intersection(window.buffer(policy.maximum_depth_mm)),
            policy=policy)
        if not proof['passed'] or not added.is_empty or removed.is_empty:
            raise ValueError('T04_EDGE_ENTRY_FEATURE_REJECTED:'+sid+':'+str(proof['failures']))
        changes[sid]=after;ledger[sid]=dict(proof,removal_ref=p.geomref(store,removed),
            addition_ref=p.geomref(store,added),before_ref=row['geometry_ref'],after_ref=p.geomref(store,after))
    working,scope,relations=_working_context(old_cc,old_sc,changes,ledger)
    material=dict(current,**changes)
    pin_proof=pin.ACTIVE.check_parts(material.values())
    if not pin_proof['passed']:raise ValueError('T04_EDGE_ENTRY_PIN_CHECK_FAILED')
    # Keep original_ref as immutable source provenance. The isolated contexts
    # carry the explicitly authorized working baselines for T04's predicates.
    objects=[dict(r,geometry_ref=ledger[r['source_id']]['after_ref'])
             if r['source_id'] in changes else r for r in scene['objects']]
    receipt=dict(schema='t04-edge-entry-bounded/1',source_sha256=scene['source_sha256'],
        input_scene_ref=store.put_json('scene',scene),policy=policy.resolved(),
        ledger=ledger,relations=relations,pin_checks=pin_proof,
        preparation_seconds=time.perf_counter()-started,
        order='BEFORE_ROUTE_ADMISSION_AND_T04_OBSTACLE_INDEXING',
        qualification='BOUNDED_T04_ONLY; downstream replay and native subtraction export NOT_QUALIFIED')
    receipt_ref=store.put_json('t04-edge-entry',receipt)
    output=dict(scene,objects=objects,lineage=scene['lineage']+[
        dict(stage='t04-edge-entry-bounded',receipt_ref=receipt_ref)])
    cc.ACTIVE,sc.ACTIVE=working,scope
    try:
        yield output,dict(receipt_ref=receipt_ref,**receipt)
    finally:
        # Failed admission or final verification cannot leak a different source
        # partition into another job in this interpreter.
        cc.ACTIVE,sc.ACTIVE,fence.ACTIVE=old_cc,old_sc,old_fence
