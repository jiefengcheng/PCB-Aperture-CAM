"""Provisional global trace-growth eligibility; KEEP never edits source copper.

Large fill is identified by a broad interior in the immutable stage-entry
material image. Connected-route protection is provisional and can be disabled
independently of filled-contour preservation. Width exclusion always applies
to the complete native route.
"""
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
import json
import math
from pathlib import Path
from shapely import to_wkb,normalize
from shapely.ops import unary_union
from src.original_copper_owners import OriginalOwners
from src.stage_abi.store import canonical,digest

REGISTRY=Path(__file__).resolve().parents[1]/'contracts/t04/trace_eligibility.json'
SNAPSHOT='TRACE_GROWTH_ELIGIBILITY_SNAPSHOT.json'


@dataclass(frozen=True)
class Policy:
    raw: bytes

    def __post_init__(self):
        value=json.loads(self.raw)
        expected={'schema','revision','status','maximum_eligible_source_width_mm','large_fill_core_radius_mm',
                  'minimum_large_fill_core_area_mm2','preserve_routes_connected_to_large_fill','preserve_complete_large_fill_contours'}
        nominal=type(value.get('revision'))is int and value['revision']>=3
        if nominal:expected|={'nominal_width_resolution_mm','keep_nominal_limit'}
        coverage=type(value.get('revision'))is int and value['revision']>=4
        if coverage:expected|={'minimum_large_fill_coverage_fraction'}
        smooth=type(value.get('revision'))is int and value['revision']>=5
        if smooth:expected|={'smooth_native_route_profiles'}
        candidate=type(value.get('revision'))is int and value['revision']>=6
        if candidate:expected|={'candidate_coverage_mode'}
        pieces=type(value.get('revision'))is int and value['revision']>=7
        if pieces:expected|={'coverage_granularity'}
        broad_pieces=type(value.get('revision'))is int and value['revision']>=8
        if broad_pieces:expected|={'source_coverage_mode'}
        if (set(value)!=expected or value['schema']!='pcb-trace-growth-eligibility/1' or
                type(value['revision'])is not int or value['revision']<1 or value['status']!='PROVISIONAL' or
                type(value['preserve_routes_connected_to_large_fill'])is not bool or value['preserve_complete_large_fill_contours']is not True):
            raise ValueError('TRACE_ELIGIBILITY_POLICY_SCHEMA_CHANGED')
        if nominal and (value['keep_nominal_limit']is not True or
                type(value['nominal_width_resolution_mm'])not in(int,float)or
                not math.isfinite(value['nominal_width_resolution_mm'])or
                not 0<value['nominal_width_resolution_mm']<=value['maximum_eligible_source_width_mm']):
            raise ValueError('INVALID_NOMINAL_WIDTH_POLICY')
        if coverage and (type(value['minimum_large_fill_coverage_fraction'])not in(int,float)or
                not math.isfinite(value['minimum_large_fill_coverage_fraction'])or
                not 0<value['minimum_large_fill_coverage_fraction']<=1):
            raise ValueError('INVALID_LARGE_FILL_COVERAGE_POLICY')
        if smooth and value['smooth_native_route_profiles']is not True:
            raise ValueError('SMOOTH_NATIVE_ROUTE_PROFILES_REQUIRED')
        if candidate and value['candidate_coverage_mode']!='OTHER_ENTRY_COPPER_EXCLUDING_ROUTE_AND_EXACT_ALIASES':
            raise ValueError('INVALID_CANDIDATE_COVERAGE_POLICY')
        if pieces and value['coverage_granularity']!='ROUTE_AND_SOURCE_SEGMENT':
            raise ValueError('INVALID_COVERAGE_GRANULARITY')
        if broad_pieces and value['source_coverage_mode']!='INDEPENDENT_BROAD_FILL':
            raise ValueError('INVALID_SOURCE_COVERAGE_MODE')
        for name in ('maximum_eligible_source_width_mm','large_fill_core_radius_mm','minimum_large_fill_core_area_mm2'):
            if type(value[name])not in(int,float)or not math.isfinite(value[name])or value[name]<=0:
                raise ValueError('INVALID_TRACE_ELIGIBILITY_PARAMETER:'+name)

    @property
    def value(self):return json.loads(self.raw)

    @property
    def sha256(self):return digest(self.raw)

    def too_wide(self,width):
        if type(width)not in(int,float)or not math.isfinite(width)or width<=0:
            raise ValueError('POSITIVE_NATIVE_TRACE_WIDTH_REQUIRED')
        value=self.value;actual=Decimal(str(width));limit=Decimal(str(value['maximum_eligible_source_width_mm']))
        if value.get('keep_nominal_limit'):
            resolution=Decimal(str(value['nominal_width_resolution_mm']))
            nominal=(actual/resolution).quantize(Decimal('1'),rounding=ROUND_HALF_UP)*resolution
            return nominal>=limit
        return actual>limit

    def blocking_reason(self,width):
        if not self.too_wide(width):return None
        if Decimal(str(width))<=Decimal(str(self.value['maximum_eligible_source_width_mm'])):
            return 'NOMINAL_SOURCE_WIDTH_AT_GLOBAL_LIMIT'
        return 'SOURCE_WIDTH_EXCEEDS_GLOBAL_LIMIT'

    def snapshot(self):return dict(schema='pcb-trace-growth-eligibility-snapshot/1',sha256=self.sha256,source_json=self.raw.decode())


def capture(path=REGISTRY):return Policy(Path(path).read_bytes())


def capture_job(run):
    path=Path(run)/SNAPSHOT;policy=capture()
    with path.open('xb')as stream:stream.write(canonical(policy.snapshot()))
    return policy


def read_snapshot(path):
    value=json.loads(Path(path).read_bytes())
    if set(value)!={'schema','sha256','source_json'}or value['schema']!='pcb-trace-growth-eligibility-snapshot/1':
        raise ValueError('TRACE_ELIGIBILITY_SNAPSHOT_SCHEMA_CHANGED')
    policy=Policy(value['source_json'].encode())
    if policy.sha256!=value['sha256']:raise ValueError('TRACE_ELIGIBILITY_SNAPSHOT_CHANGED')
    return policy


def for_job(store):
    if store is None:return capture()
    from src.t04_settings import read_snapshot as read_limits_snapshot,SNAPSHOT_NAME
    settings_path=store.root.parent/SNAPSHOT_NAME
    if settings_path.exists():
        settings=read_limits_snapshot(settings_path)
        if settings._eligibility is not None:return Policy(settings._eligibility)
    path=store.root.parent/SNAPSHOT
    return read_snapshot(path)if path.exists()else capture()


def classify(rows,predecessor,paths,policy,*,copper=None):
    settings=policy.value
    revision=None
    if copper is None:
        index=OriginalOwners(unary_union(list(predecessor.values())))
        memberships={s:index.membership(g)if not g.is_empty else[]for s,g in predecessor.items()}
    else:
        from types import SimpleNamespace
        revision=copper.acquire(predecessor)
        # Reuse the exact revision's physical partition and memberships. Do
        # not reconstruct ownership or a full-board index for eligibility.
        ids=sorted(revision.owners)
        index=SimpleNamespace(ids=ids,owners=[revision.owners[o]for o in ids])
        memberships={s:list(v)for s,v in revision.membership.items()}
    large={}
    for owner,body in zip(index.ids,index.owners):
        if body.area<settings['minimum_large_fill_core_area_mm2']:continue
        core=body.buffer(-settings['large_fill_core_radius_mm'],quad_segs=128)
        if core.area>=settings['minimum_large_fill_core_area_mm2']:
            large[owner]=dict(entry_area_mm2=body.area,broad_core_area_mm2=core.area,
                              broad_core_sha256=digest(to_wkb(core)),entry_geometry_sha256=digest(to_wkb(body)))
    large_members={s for s,owners in memberships.items()if set(owners).intersection(large)}
    native_sources={s for members in paths.values()for s in members}
    # The caller supplies its maintained native trace projection, after plotted
    # fill roles were removed. Disabling connected-route protection must not
    # keep those ordinary traces indirectly through the fixed-source ledger.
    protected=large_members if settings['preserve_routes_connected_to_large_fill'] else large_members-native_sources
    coverage={};support=[];candidate_coverage={};source_coverage={};source_reasons={}
    if 'minimum_large_fill_coverage_fraction'in settings:
        # A broad owner also contains its attached thin branches. It is NOT a
        # coverage operand: that would make every attached route cover itself.
        # Remove the maintained native trace projection and its exact aliases
        # BEFORE preparing the independent filled-copper material.
        normalized={s:digest(to_wkb(normalize(g)))for s,g in predecessor.items()}
        aliases={normalized[s]for s in native_sources}
        support=[s for s in predecessor if s not in native_sources and
                 not predecessor[s].is_empty and normalized[s]not in aliases]
        if copper is not None:
            fill=copper.prepared_broad_fill(revision,support,radius=settings['large_fill_core_radius_mm'],
                minimum_area=settings['minimum_large_fill_core_area_mm2'])
        else:
            material=unary_union([predecessor[s]for s in support])
            faces=[]if material.is_empty else([material]if material.geom_type=='Polygon'else list(material.geoms))
            broad=[g for g in faces if g.area>=settings['minimum_large_fill_core_area_mm2']and
                   g.buffer(-settings['large_fill_core_radius_mm'],quad_segs=128).area>=settings['minimum_large_fill_core_area_mm2']]
            fill=unary_union(broad)
        # All growth candidates must also be measured against independent
        # stage-entry material. Plotted filled artwork can itself be admitted
        # as native strokes, so excluding ALL native paths loses that cover.
        # Exclude the complete candidate route and every exact member alias,
        # borrow the revision's existing contribution index, and union only
        # clipped local intersections. No new scene/owner index is built.
        candidate_mode=settings.get('candidate_coverage_mode')
        if candidate_mode and revision is None:
            from shapely.strtree import STRtree
            source_order=list(predecessor)
            source_tree=STRtree(list(predecessor.values()))
        for route,members in sorted(paths.items()):
            body=unary_union([predecessor[s]for s in members])
            fill_covered=body.intersection(fill)
            overlap=fill_covered.area
            fraction=min(1.,overlap/body.area)if body.area else 0.
            coverage[route]=dict(original_route_area_mm2=body.area,large_fill_covered_area_mm2=overlap,
                large_fill_coverage_fraction=fraction,
                keep=fraction>=settings['minimum_large_fill_coverage_fraction'],
                basis='UNION_OF_ROUTE_CONTRIBUTIONS; INDEPENDENT_BROAD_FILL; NO_NATIVE_TRACES_OR_EXACT_ALIASES')
            if candidate_mode:
                own_aliases={normalized[s]for s in members}
                hits=(revision.sources(body)if revision is not None else
                      [source_order[int(i)]for i in sorted(source_tree.query(body,predicate='intersects'))])
                clips=[];supporting=[]
                for s in hits:
                    if normalized[s]in own_aliases:continue
                    clipped=predecessor[s].intersection(body)
                    if clipped.area>0:clips.append(clipped);supporting.append(s)
                covered=unary_union(clips)
                covered_area=min(body.area,covered.area)
                fraction=max(0.,min(1.,covered_area/body.area))if body.area else 0.
                candidate_coverage[route]=dict(original_route_area_mm2=body.area,
                    other_entry_covered_area_mm2=covered_area,other_entry_coverage_fraction=fraction,
                    keep=fraction>=settings['minimum_large_fill_coverage_fraction'],
                    support_source_ids=supporting,covered_geometry_sha256=digest(to_wkb(covered)),
                    basis=candidate_mode)
                if settings.get('coverage_granularity')=='ROUTE_AND_SOURCE_SEGMENT':
                    # Reuse this route's independent coverage operands. Its
                    # exposed length must not dilute a buried member's area.
                    # Ordinary pad overlap alone is not broad-fill coverage.
                    # No new query, owner build, intersection or board union
                    # is needed to obtain the route's broad-fill operand.
                    broad_only=settings.get('source_coverage_mode')=='INDEPENDENT_BROAD_FILL'
                    source_cover=fill_covered if broad_only else covered
                    basis='INDEPENDENT_BROAD_FILL'if broad_only else candidate_mode
                    reason=('LARGELY_COVERED_SOURCE_SEGMENT_BY_LARGE_FILLED_COPPER'if broad_only else
                            'LARGELY_COVERED_SOURCE_SEGMENT_BY_OTHER_ENTRY_COPPER')
                    pieces={}
                    for s in members:
                        g=predecessor[s]
                        area=min(g.area,g.intersection(source_cover).area)
                        fraction=max(0.,min(1.,area/g.area))if g.area else 0.
                        keep=fraction>=settings['minimum_large_fill_coverage_fraction']
                        pieces[s]=dict(original_source_area_mm2=g.area,
                            other_entry_covered_area_mm2=area,other_entry_coverage_fraction=fraction,
                            keep=keep,basis=basis)
                        if keep:source_reasons[s]=[reason]
                    source_coverage[route]=pieces
    kept={};reasons={s:list(why)for s,why in source_reasons.items()}
    for route,members in sorted(paths.items()):
        why=[]
        if settings['preserve_routes_connected_to_large_fill'] and any(s in large_members for s in members):
            why.append('CONNECTED_TO_LARGE_FILLED_COPPER')
        width_reasons=sorted({policy.blocking_reason(rows[s]['metadata']['minimum_caliper_mm'])for s in members}-{None})
        why.extend(width_reasons)
        if coverage.get(route,{}).get('keep'):why.append('LARGELY_COVERED_BY_LARGE_FILLED_COPPER')
        elif candidate_coverage.get(route,{}).get('keep'):why.append('LARGELY_COVERED_BY_OTHER_ENTRY_COPPER')
        if why:
            kept[route]=why
            for s in members:reasons[s]=list(why)
    fixed=protected|set(reasons)
    ledger=dict(schema='pcb-trace-growth-eligibility-ledger/1',policy=policy.snapshot(),
                predecessor_geometry_sha256=digest(canonical({s:digest(to_wkb(g))for s,g in sorted(predecessor.items())})),
                entry_component_fingerprint=digest(canonical(sorted(index.ids))),
                component_fingerprint_basis='ORDERED_EXACT_OWNER_GEOMETRY_HASHES',large_filled_components=large,
                source_owner_ids=memberships,protected_large_fill_source_ids=sorted(protected),
                kept_routes=kept,keep_source_reasons=reasons,fixed_source_ids=sorted(fixed),
                complete_native_route_inventory={r:list(ss)for r,ss in paths.items()},
                large_fill_route_coverage=coverage,large_fill_coverage_support_source_ids=support,
                copper_action='KEEP_COMPLETE_T04_ENTRY_CONTOURS; NO_BUMPS_RECESSES_OR_INDEPENDENT_TRACE_GROWTH',
                topology_basis='EXACT_GEOMETRIC_CONNECTION; NOT_ELECTRICAL_NET_INTENT',
                connected_route_protection=settings['preserve_routes_connected_to_large_fill'],
                qualification='PROVISIONAL_SOURCE_SELECTION; NOT_T04_OR_MANUFACTURING_ACCEPTANCE')
    if settings.get('candidate_coverage_mode'):ledger['candidate_route_coverage']=candidate_coverage
    if settings.get('coverage_granularity'):
        ledger['candidate_source_coverage']=source_coverage
    return ledger,index


def prepare(directory,scene,rows,current,paths,policy,*,copper=None):
    from src.gerber_u05.durable_groups import retain
    import shapely
    key=dict(schema='pcb-trace-growth-eligibility-cache/1',policy_sha256=policy.sha256,
             scene_sha256=digest(canonical(scene)),paths_sha256=digest(canonical(paths)),
             implementation_sha256=digest(Path(__file__).read_bytes()),
             kernel=dict(shapely=shapely.__version__,geos=shapely.geos_version_string),
             predecessor_sha256=digest(canonical({s:digest(to_wkb(g))for s,g in sorted(current.items())})))
    value,binding,hit=retain(directory,key,'ELIGIBILITY.json.gz',lambda:classify(rows,current,paths,policy,copper=copper)[0])
    return value,dict(binding=binding,cache_hit=hit)
