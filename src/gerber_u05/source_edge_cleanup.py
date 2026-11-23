"""Owner-requested physical boundary noise, across overlapping source draws.

The area denominator is the original causing pad/trace, never the whole fill.
The numerator includes the entire supported physical protrusion. Tiny plotted
fragments are not independent pads and cannot hide copper after the trim.
"""
import hashlib
from copy import deepcopy
from types import MappingProxyType
from shapely import to_wkb
from shapely.geometry import Point,LineString
from shapely.ops import unary_union
from src.bulk_edge_restore import propose,topology
from src.edge_restoration_settings import capture
from src.original_copper_owners import OriginalOwners
from src.native_inventory import ERROR_MM
from .finite_profile_union import polygonal


def legacy_trim_supported_feature(rows,current,original,causing_id,domain,smooth_edge,
                           reference_evidence,backing_point,*,policy=None):
    policy=capture()if policy is None else policy
    if causing_id not in rows or rows[causing_id]['kind']not in('circle','stroke'):
        raise ValueError('ORIGINAL_CAUSING_PAD_OR_TRACE_REQUIRED')
    if set(current)!=set(original)or set(current)!=set(rows):
        raise ValueError('COMPLETE_SOURCE_CONTRIBUTIONS_REQUIRED')
    core=original[causing_id];image=polygonal(unary_union(list(current.values())))
    owners=OriginalOwners(image);own=owners.membership(current[causing_id])
    if len(own)!=1:raise ValueError('ONE_PHYSICAL_BOUNDARY_OWNER_REQUIRED')
    owner=own[0];body=dict(zip(owners.ids,owners.owners))[owner]
    if body.area<1 or not body.covers(Point(backing_point).buffer(.125,quad_segs=128)):
        raise ValueError('LOCAL_BROAD_COPPER_BACKING_REQUIRED')
    reference=body.difference(domain)
    foreign=[(o,g)for o,g in zip(owners.ids,owners.owners)if o!=owner and g.intersects(domain)]
    candidate,cut,added,geometry=propose(body,reference,domain,protected=foreign,
        reference_evidence=reference_evidence,smooth_edge=smooth_edge,policy=policy)
    if not geometry['passed']or cut.is_empty or not added.is_empty:
        raise ValueError('SOURCE_BOUNDARY_NOISE_GEOMETRY_REJECTED:'+str(geometry['failures']))
    parts=[cut]if cut.geom_type=='Polygon'else list(cut.geoms)
    if any(p.intersection(core).area<=0 for p in parts):
        raise ValueError('UNRELATED_FEATURE_IN_NOISE_WINDOW')
    # The smooth edge is the only window boundary the complete feature may
    # reach. A wire crossing the other boundaries is a connection, not a cap.
    outer=domain.boundary.difference(smooth_edge.buffer(2*ERROR_MM,quad_segs=128))
    if cut.distance(outer)<=ERROR_MM:
        raise ValueError('FEATURE_WINDOW_CROPS_CONNECTION')
    if current[causing_id].difference(core).area>1e-12:
        raise ValueError('ORIGINAL_SOURCE_NOISE_REQUIRED; GROWN_TRACE_NEEDS_SEPARATE_REVIEW')
    prior=core.difference(current[causing_id]).area
    total=cut.area+prior;fraction=total/core.area
    if not 0<total<policy.maximum_noise_area_fraction*core.area:
        raise ValueError('WHOLE_PHYSICAL_PROTRUSION_NOT_BELOW_AREA_LIMIT')
    after=dict(current);changed=[];terminal_contacts=[]
    for sid,g in current.items():
        if not g.intersects(domain):continue
        removal=polygonal(g.intersection(domain))
        if removal.area==0:continue
        # The rectangular inspection window can contain nearby independent
        # copper. The proposal protects that owner; never subtract its source
        # occurrence merely because it shares this window.
        if owners.membership(g)!=own:continue
        row=rows[sid]
        if row['kind']in('circle','rectangle')or row['metadata'].get('rectangle_terminal'):
            raise ValueError('TERMINAL_SHAPE_TOUCHED:'+sid)
        new=polygonal(g.difference(domain))
        if not new.is_valid:raise ValueError('INVALID_TRIMMED_SOURCE_CONTRIBUTION')
        after[sid]=new;changed.append(sid)
    if causing_id not in changed:raise ValueError('CAUSING_SOURCE_NOT_TRIMMED')
    for sid,row in rows.items():
        if row['kind']not in('circle','rectangle')and not row['metadata'].get('rectangle_terminal'):continue
        before_contact=current[causing_id].intersection(current[sid]).area
        if before_contact<=0:continue
        remaining=after[causing_id].intersection(after[sid]).area
        if remaining<=0:raise ValueError('ORIGINAL_TERMINAL_CONTACT_LOST:'+sid)
        terminal_contacts.append(dict(source_id=sid,before_mm2=before_contact,after_mm2=remaining))
    result=polygonal(unary_union(list(after.values())))
    if topology(result)!=topology(image):raise ValueError('PHYSICAL_COMPONENT_OR_HOLE_TOPOLOGY_CHANGED')
    actual_cut=polygonal(image.difference(result));actual_add=polygonal(result.difference(image))
    if actual_add.area>1e-12 or actual_cut.symmetric_difference(cut).area>1e-12:
        raise ValueError('OVERLAPPING_SOURCE_TRIM_MATERIAL_MISMATCH')
    removed_paths=[]
    for sid in changed:
        md=rows[sid]['metadata']
        if md.get('route_points_mm'):
            path=LineString(md['route_points_mm']);lost=path.difference(after[sid].buffer(ERROR_MM,quad_segs=128))
            if lost.length>0:removed_paths.append(dict(source_id=sid,removed_source_path_mm=lost.length,
                whole_derived_occurrence_removed=after[sid].is_empty))
    return after,dict(schema='owner-supported-physical-boundary-noise/1',passed=True,
        causing_source_id=causing_id,original_feature_sha256=hashlib.sha256(to_wkb(core)).hexdigest(),
        original_feature_area_mm2=core.area,whole_physical_protrusion_area_mm2=cut.area,
        prior_causing_source_removal_mm2=prior,conservative_area_fraction=fraction,
        area_basis='WHOLE_PHYSICAL_BUMP / ORIGINAL_CAUSING_PAD_OR_TRACE',
        overlapping_draw_fragments_are_not_separate_denominators=True,
        changed_source_ids=changed,empty_derived_source_ids=[s for s in changed if after[s].is_empty],
        owner_authorized_free_source_end_retreats=removed_paths,terminal_contact_checks=terminal_contacts,
        physical_topology_before=list(topology(image)),physical_topology_after=list(topology(result)),
        actual_removed_mm2=actual_cut.area,actual_added_mm2=actual_add.area,
        geometry_checks=geometry,policy=policy.resolved(),source_bytes_edited=False,
        qualification='BOUNDED_GEOMETRY_ONLY; NO ELECTRICAL_OR_MANUFACTURING_ACCEPTANCE')


class CleanupBatch:
    """Prepare neighbours once; local proposals do not rebuild board material.

    Proposals are staged until finish() verifies and publishes their combined
    material. An individual proposal is not an acceptance receipt.
    """
    def __init__(self, rows, original, revision, features, *, policy=None, protected_source_ids=(), protected_domains=(), allow_redundant_flashes=False, allow_causing_pads=False, allow_causing_rectangles=False, preserve_source_paths=False, preserve_all_contacts=False, preserve_causing_paths=False, allow_causing_free_end_trim=False, preserve_reference_flanks=False):
        if tuple(rows) != tuple(original) or set(rows) != set(revision.values):
            raise ValueError('COMPLETE_SOURCE_CONTRIBUTIONS_REQUIRED')
        self.rows, self.original, self.revision = deepcopy(rows), MappingProxyType(dict(original)), revision
        self.policy = capture() if policy is None else policy
        self.protected_source_ids=frozenset(protected_source_ids)
        self.protected_domains=tuple(protected_domains)
        self.allow_causing_pads=allow_causing_pads
        self.allow_causing_rectangles=allow_causing_rectangles
        self.preserve_source_paths=preserve_source_paths
        self.preserve_causing_paths=preserve_causing_paths
        self.allow_causing_free_end_trim=allow_causing_free_end_trim
        self.preserve_reference_flanks=preserve_reference_flanks
        self.preserve_all_contacts=preserve_all_contacts
        self.features = [dict(f,reference_evidence=deepcopy(f['reference_evidence']),
                              backing_point=tuple(f['backing_point'])) for f in features]
        for feature in self.features:
            if 'reference_source_ids' in feature:feature['reference_source_ids']=tuple(feature['reference_source_ids'])
        self.neighbours = [(revision.sources(f['domain']),
                            revision.sources(revision.values[f['causing_id']])) for f in self.features]
        self.prepared=[]
        broad_components={}
        for f,(neighbours,_) in zip(self.features,self.neighbours):
            owner,body=revision.owner(f['causing_id'])
            local=polygonal(body.intersection(f['domain'].buffer(.125,quad_segs=128)))
            removal=f.get('removal_mask',f['domain'])
            if not removal.is_valid or removal.difference(f['domain']).area>1e-12:
                raise ValueError('BOUNDED_REMOVAL_MASK_REQUIRED')
            broad=body.area>=1 and body.covers(Point(f['backing_point']).buffer(.125,quad_segs=128))
            component=f.get('connected_broad_polygon')
            if not broad and component is not None:
                key=(owner,component)
                if key not in broad_components:
                    polygons=[body] if body.geom_type=='Polygon' else list(body.geoms)
                    if type(component) is not int or not 0<=component<len(polygons):
                        raise ValueError('BOUND_CONNECTED_BROAD_COMPONENT_REQUIRED')
                    part=polygons[component]
                    broad_components[key]=(part,part.area>=1 and not part.buffer(-.125,quad_segs=128).is_empty)
                part,eligible=broad_components[key]
                broad=(eligible and part.covers(Point(f['backing_point'])) and
                       removal.intersection(body).difference(part).area<=1e-12 and
                       f['reference_evidence'].get('kind') in ('TWO_COLLINEAR_SOURCE_FLANKS',
                           'CIRCULAR_VOID_FLANKS_AT_NATIVE_PAD_CENTER',
                           'CIRCULAR_VOID_FLANKS_AT_NATIVE_STROKE_ENDPOINT'))
            self.prepared.append((owner,local,local.difference(removal),broad))
        self.working = dict(revision.values)
        from .redundant_plotting_caps import qualify
        possible={s for window,_ in self.neighbours for s in window if self.rows[s]['kind']=='circle'}
        self.redundant_flashes={s:p for s in sorted(possible if allow_redundant_flashes else ())
            if (p:=qualify(self.rows,original,revision,s,protected=self.protected_source_ids)) is not None}
        self.cuts, self.records, self.failures = [], [], []
        self.physical_noise_totals={}
        self.fixed_reference_ids=set()
        self.fixed_flanks=[]
        self.finished = False

    def propose(self, index):
        if self.finished: raise ValueError('CLEANUP_BATCH_ALREADY_FINISHED')
        f = self.features[index]; sid = f['causing_id']; domain = f['domain']; edge = f['smooth_edge']
        reference_owner=f.get('reference_owner')
        owner_ids=self.revision.owner_sources.get(reference_owner,()) if reference_owner is not None else ()
        reference_ids=f.get('reference_source_ids',owner_ids)
        if any(s not in owner_ids for s in reference_ids):
            raise ValueError('REFERENCE_SOURCE_OWNER_BINDING_CHANGED')
        if reference_owner is not None and not reference_ids:
            raise ValueError('AUTHENTICATED_REFERENCE_OWNER_REQUIRED')
        if any(to_wkb(self.working[s])!=to_wkb(self.original[s]) for s in reference_ids):
            raise ValueError('ORIGINAL_REFERENCE_OWNER_ALREADY_CHANGED')
        flanks=[LineString(f['reference_evidence'][k]) for k in ('first','second')] if self.preserve_reference_flanks else []
        if self.preserve_reference_flanks and any(c.intersection(line).length>ERROR_MM for c in self.cuts for line in flanks):
            raise ValueError('ORIGINAL_SOURCE_FLANK_ALREADY_CHANGED')
        if sid not in self.rows or self.rows[sid]['kind'] not in ('circle','stroke','rectangle'):
            raise ValueError('ORIGINAL_CAUSING_PAD_OR_TRACE_REQUIRED')
        if self.rows[sid]['kind']=='rectangle' and not self.allow_causing_rectangles:
            raise ValueError('RECTANGULAR_BUMPS_DEFERRED_BY_POLICY')
        core = self.original[sid]; current = self.working[sid]
        owner,body,reference,broad=self.prepared[index]
        if not broad:
            raise ValueError('LOCAL_BROAD_COPPER_BACKING_REQUIRED')
        candidate, cut, added, geometry = propose(body, reference, domain,
            reference_evidence=f['reference_evidence'], smooth_edge=edge, policy=self.policy,trim_only=True,
            removal_mask=f.get('removal_mask'))
        if not geometry['passed'] or cut.is_empty or not added.is_empty:
            raise ValueError('SOURCE_BOUNDARY_NOISE_GEOMETRY_REJECTED:'+str(geometry['failures']))
        if any(cut.intersects(g) for g in self.protected_domains):
            raise ValueError('PROTECTED_PIN_DOMAIN_TOUCHED')
        if any(cut.intersection(g).area>1e-12 for g in self.cuts):
            raise ValueError('OVERLAPPING_PHYSICAL_FEATURES_REQUIRE_ONE_BATCH_FEATURE')
        if self.preserve_reference_flanks and any(cut.intersection(line).length>ERROR_MM for line in self.fixed_flanks):
            raise ValueError('ACCEPTED_SOURCE_FLANK_MUST_REMAIN_UNCHANGED')
        parts=[cut] if cut.geom_type=='Polygon' else list(cut.geoms)
        if any(p.intersection(core).area<=0 for p in parts): raise ValueError('UNRELATED_FEATURE_IN_NOISE_WINDOW')
        outer=domain.boundary.difference(edge.buffer(2*ERROR_MM,quad_segs=128))
        if cut.distance(outer)<=ERROR_MM: raise ValueError('FEATURE_WINDOW_CROPS_CONNECTION')
        if current.difference(core).area>1e-12:
            raise ValueError('ORIGINAL_SOURCE_NOISE_REQUIRED; GROWN_TRACE_NEEDS_SEPARATE_REVIEW')
        prior=core.difference(current).area
        cause_key=to_wkb(core)
        prior_physical=self.physical_noise_totals.get(cause_key,0.)
        total=cut.area+max(prior,prior_physical)
        rule=f.get('rule','AREA_NOISE')
        shallow=None
        if rule=='SHALLOW_SOURCE_EDGE':
            from src.bulk_edge_restore import shallow_trace_edge_check
            points=self.rows[sid]['metadata'].get('route_points_mm')
            if self.rows[sid]['kind']!='stroke' or not points:
                raise ValueError('SOURCE_SUPPORTED_SHALLOW_TRACE_EDGE_REQUIRED')
            shallow=shallow_trace_edge_check(cut,core,LineString(points),edge,
                self.rows[sid]['metadata'].get('original_width_mm'),f['reference_evidence'],policy=self.policy)
            if not shallow['passed']:raise ValueError('SHALLOW_TRACE_EDGE_REJECTED:'+str(shallow['failures']))
        elif rule!='AREA_NOISE':raise ValueError('UNSUPPORTED_CLEANUP_RULE')
        elif not 0<total<self.policy.maximum_noise_area_fraction*core.area:
            raise ValueError('WHOLE_PHYSICAL_PROTRUSION_NOT_BELOW_AREA_LIMIT')
        pad_aliases=set()
        if self.rows[sid]['kind'] in ('circle','rectangle'):
            if not self.allow_causing_pads:raise ValueError('EXPLICIT_CAUSING_PAD_TRIM_REQUIRED')
            pad_aliases={sid,*self.rows[sid]['metadata'].get('alias_source_ids',[])}
            for alias in pad_aliases:
                md=self.rows[alias]['metadata']
                if (alias in self.protected_source_ids or self.rows[alias]['kind']!=self.rows[sid]['kind'] or
                        not self.original[alias].equals_exact(core,0) or any(md.get(k) for k in
                        ('rectangle_terminal','declared_terminal','declared_pin','protected_pin','terminal_intent_declared'))):
                    raise ValueError('PROTECTED_OR_UNBOUND_CAUSING_PAD:'+alias)
            # A nearby large pad must not supply the denominator for a trace bump.
            if cut.difference(core).area>1e-12:raise ValueError('PHYSICAL_BUMP_NOT_CONTAINED_IN_CAUSING_PAD')
            center=Point(self.rows[sid]['metadata'].get('center_mm',list(core.centroid.coords)[0]))
            if not current.difference(domain).covers(center):raise ValueError('PAD_TRIM_LOSES_CENTER')
        updates={}; contacts=[]; removed_paths=[]
        for other in self.neighbours[index][0]:
            g=self.working[other]
            trim_mask=f.get('removal_mask',domain)
            if not g.intersects(trim_mask) or g.intersection(trim_mask).area==0: continue
            if self.revision.membership[other] != (owner,): continue
            row=self.rows[other]
            if other in self.fixed_reference_ids:
                raise ValueError('ACCEPTED_REFERENCE_OWNER_MUST_REMAIN_UNCHANGED')
            if (other in self.protected_source_ids or any(row['metadata'].get(k) for k in
                    ('rectangle_terminal','declared_terminal','declared_pin','protected_pin','terminal_intent_declared')) or
                    row['kind']=='rectangle' and other not in pad_aliases or
                    row['kind']=='circle' and other not in self.redundant_flashes and other not in pad_aliases):
                raise ValueError('TERMINAL_SHAPE_TOUCHED:'+other)
            value=polygonal(g.difference(f.get('removal_mask',domain)))
            if not value.is_valid: raise ValueError('INVALID_TRIMMED_SOURCE_CONTRIBUTION')
            updates[other]=value
            points=row['metadata'].get('route_points_mm')
            if points:
                lost=LineString(points).difference(value.buffer(ERROR_MM,quad_segs=128))
                if lost.length>0: removed_paths.append(dict(source_id=other,removed_source_path_mm=lost.length,
                    whole_derived_occurrence_removed=value.is_empty))
        if self.preserve_source_paths and removed_paths:
            raise ValueError('ORIGINAL_SOURCE_PATH_LOST')
        free_end_proof=None
        if self.preserve_causing_paths and any(r['source_id']==sid for r in removed_paths):
            path=LineString(self.rows[sid]['metadata']['route_points_mm'])
            remaining=path.difference(f.get('removal_mask',domain))
            if (not self.allow_causing_free_end_trim or rule!='AREA_NOISE' or
                    remaining.is_empty or remaining.geom_type!='LineString'):
                raise ValueError('ORIGINAL_CAUSING_TRACE_PATH_LOST')
            lost=path.difference(remaining)
            pieces=[lost] if lost.geom_type=='LineString' else list(lost.geoms)
            ends=[Point(path.coords[0]),Point(path.coords[-1])]
            if any(min(p.distance(end) for end in ends)>ERROR_MM for p in pieces):
                raise ValueError('CAUSING_PATH_INTERIOR_TRIM_FORBIDDEN')
            free_end_proof=dict(rule='BOUNDED_AREA_NOISE_FREE_SOURCE_END_ONLY',
                removed_path_mm=lost.length,remaining_path_mm=remaining.length,
                original_ends_only=True,whole_physical_area_limit_passed=True)
        strict_contact_checks=[]
        if self.preserve_all_contacts:
            for changed,value in updates.items():
                for other in self.revision.sources(self.original[changed]):
                    if other==changed:continue
                    old=self.original[changed].intersection(self.original[other])
                    new=value.intersection(updates.get(other,self.working[other]))
                    if (not old.is_empty and new.is_empty) or (old.area>0 and new.area<=0):
                        raise ValueError('ORIGINAL_SOURCE_CONTACT_LOST:'+changed+':'+other)
                    if not old.is_empty:
                        strict_contact_checks.append(dict(source_id=changed,neighbour_source_id=other,
                            original_contact_sha256=hashlib.sha256(to_wkb(old)).hexdigest(),
                            retained_contact_sha256=hashlib.sha256(to_wkb(new)).hexdigest(),
                            before_mm2=old.area,after_mm2=new.area))
        if sid not in updates: raise ValueError('CAUSING_SOURCE_NOT_TRIMMED')
        for other in self.neighbours[index][1]:
            row=self.rows[other]
            if pad_aliases:
                if other in pad_aliases:continue
                old=current.intersection(self.working[other]);new=updates[sid].intersection(updates.get(other,self.working[other]))
                if (not old.is_empty and new.is_empty) or (old.area>0 and new.area<=0):
                    raise ValueError('ORIGINAL_PAD_CONTACT_LOST:'+other)
                if not old.is_empty:contacts.append(dict(source_id=other,before_mm2=old.area,after_mm2=new.area))
                continue
            if row['kind'] not in ('circle','rectangle') and not row['metadata'].get('rectangle_terminal'): continue
            if other in self.redundant_flashes:continue
            before_contact=current.intersection(self.working[other]).area
            if before_contact<=0: continue
            remaining=updates[sid].intersection(updates.get(other,self.working[other])).area
            if remaining<=0: raise ValueError('ORIGINAL_TERMINAL_CONTACT_LOST:'+other)
            contacts.append(dict(source_id=other,before_mm2=before_contact,after_mm2=remaining))
        record=dict(schema='owner-supported-physical-boundary-noise/2',causing_source_id=sid,
            original_feature_area_mm2=core.area,whole_physical_protrusion_area_mm2=cut.area,
            prior_causing_source_removal_mm2=prior,conservative_area_fraction=total/core.area,
            prior_whole_physical_noise_mm2=prior_physical,
            changed_source_ids=list(updates),empty_derived_source_ids=[s for s,g in updates.items() if g.is_empty],
            owner_authorized_free_source_end_retreats=removed_paths,terminal_contact_checks=contacts,
            redundant_endpoint_flash_trims=[self.redundant_flashes[s] for s in updates if s in self.redundant_flashes],
            causing_pad_trim=bool(pad_aliases),causing_pad_aliases=sorted(pad_aliases),
            reference_owner=reference_owner,
            fixed_reference_source_ids=list(reference_ids),
            geometry_checks=geometry,policy=self.policy.resolved(),source_bytes_edited=False,
            rule=rule,shallow_edge_check=shallow,disposition='STAGED_REQUIRES_BATCH_VERIFICATION')
        if self.preserve_all_contacts:record['original_source_contact_checks']=strict_contact_checks
        if self.preserve_source_paths:record['original_source_paths_preserved']=not removed_paths
        if self.preserve_causing_paths:
            record['original_causing_path_preserved']=not any(r['source_id']==sid for r in removed_paths)
            record['bounded_free_end_trim']=free_end_proof
        self.working.update(updates);self.cuts.append(cut);self.records.append(record)
        self.physical_noise_totals[cause_key]=prior_physical+cut.area
        self.fixed_reference_ids.update(reference_ids)
        if self.preserve_reference_flanks:self.fixed_flanks.extend(flanks)
        return record

    def finish(self):
        if self.finished: raise ValueError('CLEANUP_BATCH_ALREADY_FINISHED')
        context=self.revision.context
        if any(to_wkb(self.working[s])!=to_wkb(self.original[s]) for s in self.fixed_reference_ids):
            raise ValueError('ACCEPTED_REFERENCE_OWNER_CHANGED')
        before=self.revision.image()
        # Exactly one assembled-board reconstruction/check for the entire batch.
        result=polygonal(unary_union(list(self.working.values())))
        context.stats['cleanup_batch_board_unions']+=1
        cut=polygonal(unary_union(self.cuts))
        actual_cut=polygonal(before.difference(result)); actual_add=polygonal(result.difference(before))
        if topology(result)!=topology(before): raise ValueError('PHYSICAL_COMPONENT_OR_HOLE_TOPOLOGY_CHANGED')
        if actual_add.area>1e-12 or actual_cut.symmetric_difference(cut).area>1e-12:
            raise ValueError('OVERLAPPING_SOURCE_TRIM_MATERIAL_MISMATCH')
        changed={s:g for s,g in self.working.items() if to_wkb(g)!=to_wkb(self.revision.values[s])}
        revision=context.acquire(changed,parent=self.revision);revision._image=result
        for record in self.records:
            record.update(passed=True,disposition='BATCH_VERIFIED_BOUNDED_CORRECTION',
                          physical_topology_before=list(topology(before)),physical_topology_after=list(topology(result)))
        self.finished=True
        return revision,dict(schema='shared-copper-cleanup-batch/1',passed=True,records=self.records,
            kept=self.failures,actual_removed_mm2=actual_cut.area,actual_added_mm2=actual_add.area,
            operation='TRIM_ONLY',clearance_searches=0,clearance_checks=0,
            context=context.key,revision=revision.key,qualification='BOUNDED_GEOMETRY_ONLY')


def trim_features(rows, original, revision, features, *, policy=None, protected_source_ids=(), protected_domains=(),allow_redundant_flashes=False):
    batch=CleanupBatch(rows,original,revision,features,policy=policy,
                       protected_source_ids=protected_source_ids,protected_domains=protected_domains,allow_redundant_flashes=allow_redundant_flashes)
    for i in range(len(batch.features)):
        try: batch.propose(i)
        except ValueError as exc: batch.failures.append(dict(index=i,reason=str(exc),status='KEEP_UNQUALIFIED'))
    return batch.finish()


def trim_supported_feature(rows,current,original,causing_id,domain,smooth_edge,
                           reference_evidence,backing_point,*,policy=None):
    """Compatibility for a single case; use trim_features for a complete batch."""
    from src.shared_copper_context import for_board
    with for_board(original) as context:
        revision=context.acquire({s:g for s,g in current.items() if to_wkb(g)!=to_wkb(original[s])})
        batch=CleanupBatch(rows,original,revision,[dict(causing_id=causing_id,domain=domain,
            smooth_edge=smooth_edge,reference_evidence=reference_evidence,backing_point=backing_point)],policy=policy)
        record=batch.propose(0);result,proof=batch.finish()
        record.update(actual_removed_mm2=proof['actual_removed_mm2'],actual_added_mm2=proof['actual_added_mm2'])
        return dict(result.values),record
