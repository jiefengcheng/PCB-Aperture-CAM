from src.component_distance import distance as exact_distance
"""Original connected-copper ownership for growth-only finite-copper checks.

Source occurrence identities and family bounds remain separate. Components are
frozen before any growth; an accidental bridge can never create an exemption.
"""
from collections import OrderedDict
import hashlib,weakref
from shapely import STRtree,to_wkb
from shapely.geometry import Polygon
from shapely.ops import unary_union
from src.original_copper_owners import OriginalOwners
from src.stage_abi.store import canonical,digest

ACTIVE=None
POLICY=dict(schema='original-connected-copper-clearance/1',internal_clearance='NOT_APPLICABLE_SAME_ORIGINAL_OWNER',foreign_clearance='NEW_COPPER_TO_ALL_CURRENT_FOREIGN_ORIGINAL_COMPONENTS',ownership='FROZEN_BEFORE_GROWTH',source_ports='Not required for continuous original copper; no new foreign contact permission')

def surfaces(g):
    if g.is_empty:return []
    if not g.is_valid:raise ValueError('INVALID_COMPONENT_COPPER')
    if g.geom_type=='Polygon':return [g]
    if g.geom_type=='MultiPolygon':return list(g.geoms)
    if g.geom_type=='GeometryCollection':return [p for child in g.geoms for p in surfaces(child)]
    if g.area==0:return []
    raise ValueError('NONPOLYGONAL_COMPONENT_COPPER')

def joined(values):
    values=list(values);return unary_union(values)if values else Polygon()

class Context:
    def __init__(self,source,source_hash,originals):
        self.index=OriginalOwners(source);self.source_hash=source_hash
        self.reserved={};self.reservation_sha256=None
        self.originals=dict(originals);self.ids={s:self.index.membership(g)for s,g in originals.items()}
        self.approved_partial_pockets={}
        if any(not v for v in self.ids.values()):raise ValueError('SOURCE_OWNER_MISSING')
        self.cores=dict(zip(self.index.ids,self.index.owners))
        self.binding=digest(canonical(dict(policy=POLICY,source_sha256=source_hash,ownership_sha256=self.index.fingerprint)))
    def assign(self,sid,g,owners=None):
        owners=tuple(owners if owners is not None else self.index.membership(g))
        if not owners:raise ValueError('MATERIAL_OWNER_UNBOUND:'+sid)
        if sid in self.ids and tuple(self.ids[sid])!=owners:raise ValueError('FROZEN_OWNER_CHANGED:'+sid)
        if any(o not in self.cores for o in owners):raise ValueError('UNKNOWN_ORIGINAL_OWNER')
        self.ids[sid]=owners
        return owners
    def owner(self,sid,g=None):
        owners=self.ids.get(sid)
        if owners is None:owners=self.assign(sid,g)
        if len(owners)!=1:raise ValueError('ONE_ORIGINAL_OWNER_REQUIRED:'+sid)
        return owners[0]
    def iter_project(self,material):
        buckets={o:[self.cores[o]]for o in self.index.ids}
        for sid,g in material.items():
            if sid in self.originals and to_wkb(g)==to_wkb(self.originals[sid]):continue
            owners=self.ids.get(sid)
            if owners is None:owners=self.assign(sid,g)
            if len(owners)==1:buckets[owners[0]].append(g)
            else:
                if sid not in self.originals or to_wkb(g)!=to_wkb(self.originals[sid]):raise ValueError('MULTI_OWNER_OCCURRENCE_CHANGED')
                for o in owners:buckets[o].append(g.intersection(self.cores[o]))
        for o,values in buckets.items():yield o,joined(values)
    def project(self,material):return dict(self.iter_project(material))
    def register_scene(self,store,scene):
        pending_lineage=[];validated_partials={}
        from src.stage_abi.scene import geometry
        for row in scene['objects']:
            sid=row['source_id'];md=row['metadata']
            if sid in self.originals:
                if row['original_ref']['sha256']!=digest(to_wkb(self.originals[sid])):raise ValueError('ORIGINAL_SOURCE_CORE_REFERENCE_CHANGED')
                continue
            if row['kind']=='inclusive_rectangle'and 'original_component_owner_id'in md:
                members=md['members'];own=md['original_component_owner_id']
                if md.get('original_source_sha256')!=self.source_hash or not members or any(m not in self.originals for m in members):raise ValueError('INCLUSIVE_ORIGINAL_SOURCE_MEMBERS_CHANGED')
                if set(o for m in members for o in self.ids[m])!={own}:raise ValueError('INCLUSIVE_ORIGINAL_OWNER_CHANGED')
                expected={m:digest(to_wkb(self.originals[m]))for m in members}
                if md.get('original_member_wkb_sha256')!=expected:raise ValueError('INCLUSIVE_ORIGINAL_MEMBER_WITNESS_CHANGED')
                support=joined([self.originals[m]for m in members]);current=geometry(store,row['geometry_ref']);original=geometry(store,row['original_ref'])
                if not current.covers(support)or not(original.equals(current)or original.equals(support)):raise ValueError('INCLUSIVE_ORIGINAL_SUPPORT_CHANGED')
                self.assign(sid,current,[own])
            elif 'original_owner_id'in md:
                o=md['original_owner_id']
                if md.get('original_source_sha256')!=self.source_hash or o not in self.cores:raise ValueError('DERIVED_OWNER_SOURCE_CHANGED')
                if store.get(row['original_ref'],kind='geometry')!=to_wkb(self.cores[o]):raise ValueError('DERIVED_OWNER_WITNESS_CHANGED')
                self.assign(sid,geometry(store,row['geometry_ref']),[o])
            elif row['kind']=='junction_addition':
                route=md['owner_trace'];self.assign(sid,geometry(store,row['geometry_ref']),self.ids[route])
            elif sid not in self.ids:self.assign(sid,geometry(store,row['original_ref']))
            for spec in md.get('approved_partial_pockets',[]):
                from src.partial_pocket_remedy import validate,STRATEGY
                from src.gerber_u05.component_policy import read_job
                policy,contracts=read_job(store.root.parent)
                if policy['settings'].get('large_pocket_strategy')!=STRATEGY or spec['original_source_sha256']!=self.source_hash or spec['original_owner_id']!=self.owner(sid):raise ValueError('PARTIAL_POCKET_ORIGINAL_OWNER_BINDING_CHANGED')
                initial,remaining,carrier,ring=validate(spec,contracts[0])
                from src.growth_void_remedy_v09 import holes
                if initial.intersection(self.index.source).area>contracts[0].area_epsilon_mm2:raise ValueError('PARTIAL_POCKET_ORIGINAL_SOURCE_VOID_OR_COPPER_CHANGED')
                scope=getattr(self,'functional',None);channel=spec.get('original_channel_id');lineage_core=self.cores[spec['original_owner_id']]
                if scope is not None:
                    if channel not in scope.cores or md.get('original_channel_id')!=channel or scope.ids.get(sid,(channel,))!=(channel,) or md.get('original_channel_witness_sha256')!=digest(to_wkb(scope.cores[channel])):raise ValueError('PARTIAL_POCKET_FUNCTIONAL_OWNER_BINDING_CHANGED')
                    lineage_core=scope.cores[channel]
                if ring.intersection(joined(holes(lineage_core))).area>0:pending_lineage.append((spec,initial,contracts[0],lineage_core))
                old=self.approved_partial_pockets.get(spec['pocket_id'])
                if old is not None and canonical(old['spec'])!=canonical(spec):raise ValueError('FROZEN_PARTIAL_POCKET_BUDGET_CHANGED')
                validated_partials[spec['pocket_id']]=dict(spec=spec,initial=initial,remaining=remaining,protected_core=remaining.buffer(-contracts[0].file_uncertainty_mm),carrier=carrier,contract=contracts[0])

        if pending_lineage:
            from src.component_hole_lineage import classify,hole_polygons,identity
            from src.indexed_hausdorff import distance as boundary_distance
            current=self.project({r['source_id']:geometry(store,r['geometry_ref'])for r in scene['objects']})
            for spec,initial,contract,lineage_core in pending_lineage:
                own=spec['original_owner_id'];body=current[own]
                if getattr(self,'functional',None)is not None:body=self.functional.project({r['source_id']:geometry(store,r['geometry_ref'])for r in scene['objects']})[spec['original_channel_id']]
                before=joined(surfaces(body.difference(initial)))
                lineage=classify(lineage_core,before)
                candidates=[h for h in hole_polygons(before)if h.intersection(initial).area>contract.area_epsilon_mm2]
                if len(candidates)!=1 or identity(candidates[0])in lineage['keeper_ids']:raise ValueError('PARTIAL_POCKET_IS_PROTECTED_ORIGINAL_HOLE')
                gap,_=boundary_distance(candidates[0],initial,tolerance=contract.file_uncertainty_mm)
                if gap>contract.file_uncertainty_mm or candidates[0].symmetric_difference(initial).area>2*initial.length*contract.file_uncertainty_mm:raise ValueError('PARTIAL_POCKET_NOT_COMPLETE_SPLIT_DESCENDANT')
                if any(not r['source_hole_survives']for r in lineage['source_holes']):raise ValueError('PARTIAL_POCKET_SOURCE_HOLE_IDENTITY_LOST')
        self.approved_partial_pockets.update(validated_partials)
        if getattr(self,'functional',None)is not None:self.functional.register_scene(store,scene)

    def partial_pocket_failures(self,after):
        failures=[]
        for key,value in sorted(self.approved_partial_pockets.items()):
            spec=value['spec'];own=spec['original_owner_id'];body=after[own];amount=body.intersection(value['initial']).area;maximum=spec['decision']['maximum_added_area_mm2'];occupied=body.intersection(value['protected_core']).area
            if amount>maximum or occupied>value['contract'].area_epsilon_mm2:failures.append(dict(owner=own,pocket_id=key,reason='FROZEN_PARTIAL_POCKET_BUDGET_OR_OPENING_CHANGED',added_area_mm2=amount,maximum_added_area_mm2=maximum,protected_opening_occupied_mm2=occupied))
        return failures

    def complete_clearance(self,material,gap):
        if not set(self.originals)<=set(material):raise ValueError('ORIGINAL_SOURCE_OCCURRENCE_MISSING')
        # The complete occurrence ledger is the constructive source proof.
        # Large Boolean unions can report covers=False with zero lost area;
        # that diagnostic cannot replace the retained original plot operands.
        preserved={s:material[s].covers(g)for s,g in self.originals.items()}
        if not all(preserved.values()):raise ValueError('ORIGINAL_SOURCE_OCCURRENCE_CORE_REMOVED')
        after=self.project(material);ids=list(after);tree=STRtree([after[o]for o in ids]);pairs=[];failures=[]
        for o,whole in sorted(after.items()):
            added=joined(surfaces(whole.difference(self.cores[o])))
            if added.is_empty:continue
            for i in sorted(map(int,tree.query(added.buffer(gap).envelope))):
                other=ids[i]
                if other==o:continue
                distance=exact_distance(added,after[other]);passed=distance+1e-12>=gap
                pairs.append(dict(owner=o,foreign_original_owner=other,gap_mm=distance,passed=passed))
                if not passed:failures.append(dict(owner=o,foreign_original_owner=other,reason='FOREIGN_ORIGINAL_COMPONENT_CLEARANCE',gap_mm=distance))
        failures.extend(self.partial_pocket_failures(after))
        diagnostics=[dict(owner=o,union_covers_original=after[o].covers(g),overlay_missing_area_mm2=g.difference(after[o]).area)for o,g in self.cores.items()]
        return dict(passed=not failures,failures=failures,pairs=pairs,ownership_policy=POLICY,source_occurrences_preserved=len(preserved),source_proof='COMPLETE_IMMUTABLE_ORIGINAL_OCCURRENCE_LEDGER_AND_COVERING_CURRENT_CONTRIBUTIONS',union_diagnostics=diagnostics,scope='Every new owner surface to all current foreign original owners; no internal component clearance.')

def bind(source,source_hash,originals):
    global ACTIVE
    ACTIVE=Context(source,source_hash,originals);return ACTIVE

class OwnerCheck:
    def __init__(self,parent,*,context=None,active_test=None):
        self.parent=parent;self.ctx=ACTIVE if context is None else context
        self.active_test=(lambda c:ACTIVE is c)if active_test is None else active_test
        self.binding=self.ctx.binding
        self.row_owners={s:self.ctx.assign(s,g)if s not in self.ctx.ids else self.ctx.ids[s]for s,g in parent.original.items()}
        self.before=self.ctx.project(parent.original)
        self.cache=OrderedDict();self.weight=0;self.limit=64*1024**2
        self.signatures=OrderedDict()
    def signature(self,g):
        key=id(g);old=self.signatures.get(key)
        if old is not None and old[0]()is g:self.signatures.move_to_end(key);return old[1]
        h=digest(to_wkb(g))
        if len(self.signatures)>=8192:self.signatures.popitem(last=False)
        self.signatures[key]=(weakref.ref(g),h);return h
    def remember(self,key,value,extra,size):
        if size>self.limit:return
        if key in self.cache:self.weight-=self.cache.pop(key)[2]
        while self.cache and (self.weight+size>self.limit or len(self.cache)>=4096):
            _,(_,_,old_size)=self.cache.popitem(last=False);self.weight-=old_size
        self.cache[key]=(value,extra,size);self.weight+=size
    def check(self,traces,materialize_scene=False,fail_fast=False):
        p=self.parent;c=p.contract
        if not self.active_test(self.ctx)or self.binding!=self.ctx.binding:raise ValueError('ORIGINAL_OWNER_CONTEXT_CHANGED')
        if len(traces)!=len(p.trace_ids)or{r['id']for r in traces}!=set(p.trace_ids):raise ValueError('COMPLETE_TRACE_IDENTITIES_CHANGED')
        failures=[];active={};current=dict(p.original);results=[];versions={}
        for r in traces:
            sid=r['id'];candidate=r['candidate'];p.valid_geometry(candidate)
            if self.signature(r['original'])!=p.trace_ids[sid]or r['verified_original_width_mm']!=p.widths[sid]:raise ValueError('ORIGINAL_TRACE_BINDING_CHANGED')
            preserved=p.source_core_preserved(sid,r['original'],candidate)if hasattr(p,'source_core_preserved')else candidate.covers(r['original'])
            if not preserved:failures.append(dict(trace_id=sid,reason='ORIGINAL_TRACE_CORE_REMOVED'))
            signature=self.signature(candidate);current[sid]=candidate;versions[sid]=signature
            o=self.ctx.owner(sid,r['original'])
            if signature!=p.trace_ids[sid]:active.setdefault(o,[]).append(sid)
            results.append(dict(trace_id=sid,original_trace_wkb_sha256=p.trace_ids[sid],candidate_trace_wkb_sha256=signature,unchanged_source_identity=signature==p.trace_ids[sid],original_owner_id=o,original_core_preserved=preserved,failures=[]if preserved else['ORIGINAL_TRACE_CORE_REMOVED'],pairs=[],passed=preserved))
        after=dict(self.before);deltas={};versions_by_owner={o:'base:'+o for o in self.before}
        for o,ids in active.items():
            key=(o,tuple((s,versions[s])for s in sorted(ids)))
            if key in self.cache:
                whole,delta,size=self.cache[key];self.cache.move_to_end(key)
            else:
                whole=joined([self.before[o],*[current[s]for s in sorted(ids)]])
                added_material=getattr(p,'owner_added_material',None)
                delta=(added_material(self.before[o],[current[s]for s in sorted(ids)])
                       if added_material is not None else joined(surfaces(whole.difference(self.before[o]))))
                size=2*(len(to_wkb(whole))+len(to_wkb(delta)))+512
                if size<=self.limit:
                    while self.cache and(self.weight+size>self.limit or len(self.cache)>=4096):
                        _,(_,_,old_size)=self.cache.popitem(last=False);self.weight-=old_size
                    self.cache[key]=(whole,delta,size);self.weight+=size
            after[o]=whole;deltas[o]=delta;versions_by_owner[o]=digest(canonical([key[0],[[sid,h]for sid,h in key[1]]]))
        constraint={}
        for o,g in after.items():
            key=('constraint',o,versions_by_owner[o])
            if key in self.cache:
                fixed,_,_=self.cache[key];self.cache.move_to_end(key)
            else:
                from src.gerber_u05.checking_envelopes import constraint as foreign_constraint
                fixed=foreign_constraint(self.ctx,o,g)
                size=2*len(to_wkb(fixed))+512
                self.remember(key,fixed,None,size)
            constraint[o]=fixed
        owners=list(constraint);tree=STRtree([constraint[o]for o in owners]);pairs=[]
        gap=p.required_new_copper_gap()if hasattr(p,'required_new_copper_gap')else c.construction_gap_mm
        for o,delta in sorted(deltas.items()):
            if delta.is_empty:continue
            query_key=('query',o,versions_by_owner[o],gap,c.comparison_epsilon_mm)
            if query_key in self.cache:
                query,_,_=self.cache[query_key];self.cache.move_to_end(query_key)
            else:
                query=delta.buffer(gap+c.comparison_epsilon_mm).envelope;self.remember(query_key,query,None,2*len(to_wkb(query))+512)
            for j in sorted(map(int,tree.query(query))):
                other=owners[j]
                if other==o:continue
                pair_key=('distance',o,versions_by_owner[o],other,versions_by_owner[other],gap)
                if pair_key in self.cache:
                    distance,_,_=self.cache[pair_key];self.cache.move_to_end(pair_key)
                else:
                    distance=exact_distance(delta,constraint[other]);self.remember(pair_key,distance,None,len(canonical(list(pair_key)))+256)
                passed=distance+c.comparison_epsilon_mm>=gap
                pair=dict(owner=o,foreign_original_owner=other,gap_mm=distance,passed=passed);pairs.append(pair)
                if not passed:failures.append(dict(trace_id=active[o][0],owner=o,foreign_original_owner=other,reason='NEW_COPPER_BELOW_FOREIGN_COMPONENT_GAP',gap_mm=distance))
                if fail_fast and not passed:break
            if fail_fast and failures:break
        failures.extend(self.ctx.partial_pocket_failures(after))
        failed_owners={r.get('owner')for r in failures}
        for r in results:
            r['passed']=r['passed']and r['original_owner_id']not in failed_owners
            r['foreign_owner_pair_indexes']=[i for i,q in enumerate(pairs)if q['owner']==r['original_owner_id']]
        image=joined(current.values())if materialize_scene else None
        binding_vector=digest(canonical(results))
        recorded=results if materialize_scene else []
        return dict(schema='source-growth-original-copper-ownership/1',passed=not failures,failures=failures,traces=recorded,verified_source_vector_sha256=binding_vector,trace_count=len(traces),checked_trace_count=len(traces),fixed_object_count=p.fixed_count,scene_object_count=len(p.ids),evaluation_complete=not(fail_fast and failures),scene_union_materialized=materialize_scene,candidate_union_wkb_sha256=None if image is None else digest(to_wkb(image)),original_ownership_sha256=self.ctx.index.fingerprint,ownership_policy=getattr(self.ctx,'ownership_policy',POLICY),reserved_prior_positive_sha256=self.ctx.reservation_sha256,required_gap_mm=gap,foreign_owner_pairs=pairs,internal_clearance='NOT_APPLICABLE_SAME_ORIGINAL_OWNER',preparation_cache_bounds=dict(limit_bytes=self.limit,entry_limit=4096,signature_limit=8192),scope='Complete original source identities and all changed-owner versus current foreign-owner surfaces. Source growth caps and export/reparse remain mandatory.')
