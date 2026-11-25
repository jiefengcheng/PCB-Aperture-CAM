"""Batch fixed-contact preparation borrowing the board's existing source index."""
from shapely.geometry import LineString
from shapely.ops import unary_union
from shapely.geometry import box,Polygon
from .limiting_math import GUARD,MARGIN
from .profile_refinement import clearance_barrier
from src.native_inventory import ERROR_MM


def supports(rows, paths, entry, revision, *, covered=(),with_sources=False,admitted=None):
    result={}
    for route,sources in sorted(paths.items()):
        domain=unary_union([LineString(rows[s]['metadata']['route_points_mm']).buffer(
            rows[s]['metadata']['minimum_caliper_mm']/2+.15,quad_segs=32) for s in sources])
        if admitted is not None:
            domain=unary_union([domain,*[admitted[s]for s in sources]])
        nearby=revision.sources(domain)
        owners={owner for s in sources for owner in revision.membership[s]}
        carrier=unary_union([(entry if admitted is None else admitted)[s]for s in sources])
        contacts={s:entry[s].intersection(domain) for s in nearby if s not in sources
            and owners.intersection(revision.membership[s]) and entry[s].intersects(carrier)}
        # Keep native contact identities until components are compiled. Their
        # immutable floors matter even when their other sections can grow.
        result[route]=contacts if with_sources else unary_union(list(contacts.values()))
    return result


def bridge_allowances(plans,material,revision,*,protected_voids=()):
    """One shared query-view batch, including proposals outside old bounds.

    The native constructor receives only local geometric operands. Other
    proposals reserve their complete possible addition; rejecting one cannot
    make an already accepted bridge unsafe. Original owner identities govern
    contact exemptions. Protected pin voids have no owner exemption.
    """
    from .finite_profile_union import polygonal
    before=dict(revision.context.stats);upper={};bounds=dict(material)
    for plan in plans:
        patch=plan['patch']
        if patch is None:continue
        for s in plan['chain']['source_ids']:upper.setdefault(s,[]).append(patch)
    for s,patches in upper.items():
        extent=unary_union([material[s].envelope,*[g.envelope for g in patches]]).bounds
        bounds[s]=box(*extent)
    view=revision.context.query_view(bounds)
    upper={s:polygonal(unary_union([material[s],*patches]))for s,patches in upper.items()}
    result={};required=GUARD+2*MARGIN
    for i,plan in enumerate(plans):
        patch=plan['patch']
        if patch is None:continue
        sources=set(plan['chain']['source_ids']);owners={o for s in sources for o in revision.membership[s]}
        window=patch.envelope.buffer(required+2*ERROR_MM)
        clip=window.buffer(required);foreign=[];context=[];hits=view.sources(window)
        for sid in hits:
            if sid in sources:continue
            if material[sid].intersects(clip):context.append(material[sid].intersection(clip))
            # A split source can contain both a contacting owner and foreign
            # copper. Exempt it only when all of its owners are ours; otherwise
            # retain the complete local operand conservatively.
            if set(revision.membership[sid]).issubset(owners):continue
            obstacle=upper.get(sid,material[sid]).intersection(clip)
            if not obstacle.is_empty:foreign.append(clearance_barrier(obstacle,required))
        pins=[g.intersection(clip)for g in protected_voids if g.intersects(clip)]
        barrier=polygonal(unary_union([*foreign,*pins]))
        result[i]=dict(forbidden=barrier,context=polygonal(unary_union(context)),
            neighbors=list(hits),foreign_operands=len(foreign),pin_operands=len(pins),
            required_gap_mm=required)
    after=dict(revision.context.stats)
    return result,dict(scope='PREPARED_LOCAL_BRIDGE_DEPENDENCIES',queries=after.get('source_queries',0)-before.get('source_queries',0),
        source_index_builds=after.get('source_index_builds',0)-before.get('source_index_builds',0),
        overlay_index_builds=after.get('revision_overlay_index_builds',0)-before.get('revision_overlay_index_builds',0),
        private_indexes=0,owner_reconstructions=0,complete_board_unions=0,
        proposal_bound_policy='ALL_PROPOSALS_RESERVED; SOURCE_OWNER_IDENTITIES_UNCHANGED')


def shoulder_dependencies(plans,material,revision,*,protected_voids=(),broad_fill=None,native_ids=None,original=None):
    """One neighbor batch before local construction; reuse its exact operands.

    Bounds reserve possible contact completion, while foreign barriers later
    reserve only the actual completed proposals, never rectangular keep-outs.
    """
    from .finite_profile_union import polygonal
    from src.shared_copper_context import geometry_key
    before=dict(revision.context.stats);bounds=dict(material);material_keys={}
    floors=revision.values if original is None else original
    def identity(source):
        if source not in material_keys:material_keys[source]=geometry_key(material[source])
        return material_keys[source]
    for plan in plans:
        envelope=plan.get('envelope',plan['patch'])
        if envelope is None:raise ValueError('SHOULDER_QUERY_ENVELOPE_REQUIRED')
        for s in set(plan['chain']['source_ids'])|set(plan.get('native_seed_sources',())):
            bounds[s]=box(*unary_union([bounds[s].envelope,envelope.envelope.buffer(.75)]).bounds)
    view=revision.context.query_view(bounds);local={};required=GUARD+2*MARGIN
    first_hits={};contacts_by_plan={};expanded=False
    # Reserve every editable carrier before the dependency query is sealed.
    # A common native contour can be carried by a source whose original
    # primitive is elsewhere; later repairs must still see its new extent.
    for i,plan in enumerate(plans):
        clip=plan.get('envelope',plan['patch']).envelope.buffer(.8+required)
        hits=list(view.sources(clip));first_hits[i]=hits
        owners={o for s in plan['chain']['source_ids']for o in revision.membership[s]}
        native=[s for s in hits if set(revision.membership[s]).issubset(owners)and(native_ids is None or s in native_ids)]
        seeds=plan.get('native_seed_sources',plan['chain']['source_ids'])
        carrier=polygonal(unary_union([floors[s].intersection(clip)for s in seeds]))
        contacts={s for s in native if s in seeds or floors[s].intersects(carrier)}
        aliases={identity(s)for s in contacts}
        contacts_by_plan[i]=[s for s in native if s in contacts or identity(s)in aliases]
        envelope=plan.get('envelope',plan['patch']).envelope.buffer(.75)
        for source in contacts_by_plan[i]:
            reserved=box(*unary_union([bounds[source].envelope,envelope]).bounds)
            if reserved.bounds!=bounds[source].bounds:expanded=True;bounds[source]=reserved
    if expanded:view=revision.context.query_view(bounds)
    for i,plan in enumerate(plans):
        clip=plan.get('envelope',plan['patch']).envelope.buffer(.8+required)
        hits=list(view.sources(clip))if expanded else first_hits[i];operands={s:material[s].intersection(clip)for s in hits}
        sources=set(plan['chain']['source_ids']);owners={o for s in sources for o in revision.membership[s]}
        same_owner=[s for s in hits if set(revision.membership[s]).issubset(owners)]
        native=[s for s in same_owner if native_ids is None or s in native_ids]
        native_contacts=contacts_by_plan[i]
        pins=[g.intersection(clip)for g in protected_voids if g.intersects(clip)]
        foreign_parts={s:clearance_barrier(g,required)for s,g in operands.items()if s not in same_owner}
        forbidden=polygonal(unary_union([*foreign_parts.values(),*pins]))
        fill_boundary=Polygon()
        if broad_fill is not None and not broad_fill.is_empty:
            own_fill=polygonal(unary_union([operands[s]for s in same_owner if s not in native]))
            # Keep complete original sections and their order. The local role
            # operands identify ownership without rebuilding physical owners.
            fill_boundary=unary_union([edge for _,edge in revision.context.boundary_sections(broad_fill,clip)
                if not own_fill.is_empty and edge.intersection(own_fill).length>2*ERROR_MM])
        local[i]=dict(operands=operands,context=polygonal(unary_union(list(operands.values()))),clip=clip,
            neighbors=hits,pins=pins,forbidden=forbidden,same_owner=same_owner,native_sources=native,
            fill_boundary=fill_boundary,foreign_parts=foreign_parts,native_contact_sources=native_contacts)
    after=dict(revision.context.stats)
    stats=dict(queries=after.get('source_queries',0)-before.get('source_queries',0),
        source_index_builds=after.get('source_index_builds',0)-before.get('source_index_builds',0),
        overlay_index_builds=after.get('revision_overlay_index_builds',0)-before.get('revision_overlay_index_builds',0),
        dependency_query_batches=2 if expanded else 1,
        private_indexes=0,owner_reconstructions=0,complete_board_unions=0)
    def allowances(completed):
        result={}
        for i,plan in enumerate(completed):
            data=local[i];sources=set(plan['chain']['source_ids']);owners={o for s in sources for o in revision.membership[s]}
            result[i]=dict(context=polygonal(unary_union([g for s,g in data['operands'].items()if s not in sources])),
                forbidden=data['forbidden'],neighbors=data['neighbors'],clip=data['clip'])
            foreign_ids=[s for s in data['neighbors']if s not in sources and not set(revision.membership[s]).issubset(owners)]
            cache={s:(material[s],data['foreign_parts'][s])for s in foreign_ids}
            baseline=data['forbidden']
            def current_barrier(values,ids=foreign_ids,clip=data['clip'],pins=data['pins'],cache=cache,baseline=baseline):
                # The query batch already includes every possible proposal
                # extent. Commit in deterministic order: each later candidate
                # must respect actual earlier copper, including its recession.
                # Rejected alternatives never become permanent keep-outs.
                changed=False
                for sid in ids:
                    geometry=values.get(sid,material[sid])
                    if geometry is not cache[sid][0]:
                        cache[sid]=(geometry,clearance_barrier(geometry.intersection(clip),required));changed=True
                if not changed and all(cache[s][0]is material[s]for s in ids):return baseline
                return polygonal(unary_union([cache[s][1]for s in ids]+pins))
            result[i]['current_barrier']=current_barrier
        stats['proposal_bound_policy']='BATCHED_EXTENTS; ORDERED_COMMITS_AGAINST_ACTUAL_CURRENT_OPERANDS'
        return result,stats
    return local,allowances
