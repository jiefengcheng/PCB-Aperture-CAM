"""Owner-requested removal of existing pad caps beyond plotted large fill.

Separate from trace widening. Immutable source bytes and pad identities remain
in custody; only explicit derived pad candidates change. Ordinary trace/land
contacts cannot be removed to flatten a fill boundary.
"""
from shapely import STRtree, to_wkb, from_wkb
from shapely.geometry import Point
from shapely.ops import unary_union
from src.original_copper_owners import OriginalOwners
from src.stage_abi.store import digest
from src.edge_restoration_settings import capture, classify_protrusion


def trim_original_pads(rows, original, native_paths, targets, *, contact_material=None, copper=None):
    from src.shared_copper_context import ACTIVE,for_board,geometry_key
    shared=copper or ACTIVE.get()
    if shared is not None:
        if tuple(original)!=tuple(shared.source.values) or any(geometry_key(g)!=geometry_key(shared.source.values[s]) for s,g in original.items()):
            raise ValueError('PAD_CLEANUP_SHARED_SOURCE_MISMATCH')
        return _trim_original_pads(rows,original,native_paths,targets,contact_material=contact_material,copper=shared)
    with for_board(original) as shared:
        return _trim_original_pads(rows,original,native_paths,targets,contact_material=contact_material,copper=shared)


def _trim_original_pads(rows, original, native_paths, targets, *, contact_material=None, copper):
    noise_policy=capture()
    targets=set(targets)
    if not targets or not targets<=set(rows):
        raise ValueError('EXPLICIT_SOURCE_PAD_TARGETS_REQUIRED')
    native={s for ss in native_paths.values()for s in ss}
    fill_ids=sorted(s for s,r in rows.items()if s not in native and r['kind']not in('circle','rectangle'))
    key=tuple(fill_ids);cache=getattr(copper,'pad_fill_preparation',{})
    if key not in cache:
        fill=unary_union([original[s]for s in fill_ids])
        if fill.is_empty:raise ValueError('SOURCE_PLOTTED_FILL_REQUIRED')
        owners=OriginalOwners(fill)
        broad=[body for body in owners.owners if body.area>=1 and body.buffer(-.125,quad_segs=128).area>=1]
        cache[key]=(fill,broad);copper.pad_fill_preparation=cache
        copper.stats['pad_fill_preparations']+=1
    fill,broad=cache[key]
    material=original if contact_material is None else contact_material
    if set(material)!=set(original):raise ValueError('PAD_CLEANUP_CONTACT_INVENTORY_CHANGED')
    revision=copper.acquire({s:g for s,g in material.items() if to_wkb(g)!=to_wkb(original[s])})
    changes={};records=[]
    for sid in sorted(targets):
        row=rows[sid];core=original[sid]
        if row['kind']!='circle':raise ValueError('SOURCE_CIRCLE_PAD_REQUIRED')
        center=Point(row['metadata']['center_mm'])
        if not any(g.contains(center)and g.intersection(core).area>0 for g in broad):
            raise ValueError('PAD_CENTER_NOT_INSIDE_BROAD_PLOTTED_FILL:'+sid)
        neighbors=[s for s in revision.sources(core) if s!=sid]
        aliases={t for t in neighbors if rows[t]['kind']=='circle'and to_wkb(original[t])==to_wkb(core)}
        if not aliases<=targets:raise ValueError('ALL_PAD_ALIASES_MUST_BE_SELECTED')
        contacts={t:core.intersection(material[t])for t in neighbors if t not in aliases}
        support=unary_union([material[t]for t in contacts])
        candidate=core.intersection(support)
        if candidate.is_empty or not candidate.is_valid or candidate.geom_type!='Polygon' or not candidate.covers(center):
            raise ValueError('PAD_TRIM_LOSES_CONNECTED_CENTER')
        # Re-evaluate every positive native contact on the actual candidate.
        # Unchanged other operands still retain their full copper. Exact
        # containment of an independently overlaid contact polygon is not a
        # connectivity predicate (GEOS may change its boundary subdivision).
        contact_checks=[dict(source_id=t,before_area_mm2=g.area,
                             after_area_mm2=candidate.intersection(material[t]).area)
                        for t,g in contacts.items()if g.area>0]
        lost=[r['source_id']for r in contact_checks if r['after_area_mm2']<=0]
        if lost:raise ValueError('PAD_TRIM_LOSES_ORIGINAL_CONTACT:'+str(lost[:5]))
        if candidate.difference(core).area>0:raise ValueError('PAD_TRIM_ADDS_COPPER')
        removed=core.difference(candidate)
        noise=classify_protrusion(removed,core,source_id=sid,policy=noise_policy)
        if removed.area>0 and not noise['is_noise']:
            raise ValueError('PAD_PROTRUSION_NOT_BELOW_NOISE_AREA_LIMIT:'+sid)
        changes[sid]=candidate
        records.append(dict(source_id=sid,ordinal=row['metadata']['gerber_ordinal'],
            before_sha256=digest(to_wkb(core)),after_sha256=digest(to_wkb(candidate)),
            removed_area_mm2=removed.area,added_area_mm2=candidate.difference(core).area,
            noise_area_check=noise,
            original_positive_contacts_checked=sum(g.area>0 for g in contacts.values()),
            contact_checks=contact_checks,
            original_contacts_preserved=True,connected_pad_center_preserved=True,
            original_outline_changed=to_wkb(core)!=to_wkb(candidate),aliases=sorted(aliases)))
    return changes,dict(schema='t04-owner-source-pad-protrusion-cleanup/1',
        status='BOUNDED_DERIVED_PAD_CANDIDATES; NOT_EXPORT_QUALIFIED',
        source_bytes_edited=False,targets=sorted(targets),records=records,
        fill_source_ids=fill_ids,fill_geometry_sha256=digest(to_wkb(fill)),
        qualification='EXPLICIT_OWNER_PAD_OUTLINE_EXCEPTION; NOT_TERMINAL_INTENT_OR_MANUFACTURING_ACCEPTANCE')


def apply_to_construction(rows, current, original, stage, targets):
    """Apply explicit caps after T04, then check the actual combined material.

    Trace construction remains separate evidence. Subtraction cannot reduce a
    clearance; every actual positive contact and the complete material-image
    connected-component inventory are checked after the pad change.
    """
    binding=stage['input_binding']
    if binding.get('context')!='original' or binding.get('accepted_t03')is not False:
        raise ValueError('PAD_CLEANUP_REQUIRES_T04_DIRECTLY_ON_SOURCE')
    h=stage['hybrid_components'];material=dict(current)
    for key in ('continuous_source_bodies','changed_bulk_copper'):
        material.update({s:from_wkb(bytes.fromhex(v['wkb_hex']))for s,v in h[key].items()})
    if any(to_wkb(material[s])!=to_wkb(original[s])for s in targets):
        raise ValueError('PAD_CLEANUP_REQUIRES_UNMODIFIED_SOURCE_PAD')
    paths=stage['trace_eligibility_policy']['complete_native_route_inventory']
    changes,proof=trim_original_pads(rows,original,paths,targets,contact_material=material)
    after=dict(material);after.update(changes)
    before_image=unary_union(list(material.values()));after_image=unary_union(list(after.values()))
    if after_image.difference(before_image).area>0:raise ValueError('PAD_CLEANUP_ADDS_PHYSICAL_COPPER')
    old_count=len(OriginalOwners(before_image).owners);new_count=len(OriginalOwners(after_image).owners)
    if new_count!=old_count:raise ValueError('PAD_CLEANUP_CHANGES_PHYSICAL_CONNECTIONS')
    proof.update(physical_components_before=old_count,physical_components_after=new_count,
        physical_component_count_preserved=True,material_added_mm2=after_image.difference(before_image).area,
        material_removed_mm2=before_image.difference(after_image).area,
        before_material_sha256=digest(to_wkb(before_image)),after_material_sha256=digest(to_wkb(after_image)),
        clearance_cannot_decrease_by_subtraction=True,
        unselected_source_bytes_preserved=all(to_wkb(after[s])==to_wkb(g)for s,g in material.items()if s not in changes),
        trace_checks='Existing T04 checks precede this explicit pad-only subtraction; actual grown-trace contacts rechecked above.')
    for s,g in changes.items():
        record=dict(wkb_hex=to_wkb(g).hex(),display_treatment='Owner-requested original pad protrusion trimmed to surrounding copper; contacts preserved')
        h['continuous_source_bodies'][s]=record
        if s in h['changed_bulk_copper']:h['changed_bulk_copper'][s]=dict(record)
    stage['source_pad_cleanup']=proof
    return proof
