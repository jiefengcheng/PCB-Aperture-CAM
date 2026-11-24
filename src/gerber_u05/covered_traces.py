"""Immutable stage-entry eligibility of individual trace occurrences.

Reuse the full-copper classifier and its source-bound fill witness. Partial
exposure in the interior and exact aliases cannot suppress a trace. An excluded occurrence stays in native custody
and in the fixed copper scene; only its independent growth work is removed.
"""
from pathlib import Path
from time import perf_counter
import math
from shapely import STRtree,to_wkb
from shapely.geometry import LineString
from shapely.ops import unary_union
import shapely
from src import trace_growth_eligibility as eligibility
from src.stage_abi.store import canonical,digest
from .durable_groups import retain


def prepare(directory,scene,rows,current,paths,*,source_boundary_noise_fraction=.01,original=None,keep_source_ids=(),fixed_source_reasons=None,authorized_empty_ids=()):
    if not math.isfinite(source_boundary_noise_fraction)or not 0<=source_boundary_noise_fraction<.1:
        raise ValueError('VALID_SOURCE_BOUNDARY_NOISE_FRACTION_REQUIRED')
    started=perf_counter();ids=sorted(s for s,g in current.items()if not g.is_empty)
    tree=None;reports={};bindings={};hits=0;raster=None
    keep_source_ids=set(keep_source_ids)
    authorized_empty_ids=set(authorized_empty_ids)
    if any(not current[s].is_empty for s in authorized_empty_ids):
        raise ValueError('T04_AUTHORIZED_EMPTY_MUST_REMAIN_EMPTY')
    fixed_source_reasons={}if fixed_source_reasons is None else fixed_source_reasons
    if not keep_source_ids <= {s for ss in paths.values()for s in ss}:
        raise ValueError('T04_KEEP_REQUIRES_SELECTED_NATIVE_SOURCE')
    from . import raster_fill
    key=dict(schema='t04-stage-entry-covered-traces/2',scene_sha256=digest(canonical(scene)),
             algorithm_sha256=digest(Path(__file__).read_bytes()+Path(eligibility.__file__).read_bytes()+Path(raster_fill.__file__).read_bytes()),
             original_geometry_sha256=None if original is None else digest(canonical({s:digest(to_wkb(g))for s,g in sorted(original.items())})),
             owner_keep_source_ids=sorted(keep_source_ids),
             authorized_empty_ids=sorted(authorized_empty_ids),
             fixed_source_reasons=fixed_source_reasons,
             classifier_version=eligibility.VERSION,coverage='COMPLETE_FINITE_STROKE; OTHER_STAGE_ENTRY_COPPER',
             source_boundary_noise_fraction=source_boundary_noise_fraction,
             shapely_version=shapely.__version__,geos_version=shapely.geos_version_string)
    for s in sorted({s for ss in paths.values()for s in ss}):
        md=rows[s]['metadata']
        def build():
            nonlocal tree,raster
            if current[s].is_empty:
                if s not in authorized_empty_ids:
                    raise ValueError('T04_EMPTY_SOURCE_AUTHORITY_REQUIRED')
                return dict(source_id=s,fully_covered=True,growth_excluded=True,
                    disposition='KEEP_VERIFIED_CLEANUP_TOMBSTONE',
                    reasons=['VERIFIED_CLEANUP_ZERO_CONTRIBUTION'],ignored_exact_alias_ids=[],
                    source_geometry_sha256=digest(to_wkb(current[s])),exposed_area_mm2=0.)
            if tree is None:tree=STRtree([current[k]for k in ids])
            near_ids=sorted(ids[int(i)]for i in tree.query(current[s],predicate='intersects')if ids[int(i)]!=s)
            neighbors=[]
            for k in near_ids:
                other=rows[k];metadata=other.get('metadata',{})
                neighbors.append(dict(id=k,geometry=current[k],kind=metadata.get('route_kind',other['kind']),
                                      trace_width_mm=metadata.get('minimum_caliper_mm',0.)))
            report=eligibility.classify_stroke(s,current[s],md['minimum_caliper_mm'],md['route_kind'],neighbors)
            report['growth_excluded']=report['fully_covered']
            if s in keep_source_ids:
                report.update(growth_excluded=True,owner_requested_keep=True)
                report['reasons'].append('OWNER_REQUESTED_KEEP_ORIGINAL_WIDTH')
            if s in fixed_source_reasons:
                report.update(growth_excluded=True,global_eligibility_keep=fixed_source_reasons[s])
                report['reasons'].extend(fixed_source_reasons[s])
            if not report['growth_excluded']and original is not None and md['route_kind']=='arc':
                if raster is None:raster=raster_fill.RasterFill(rows,original)
                witness=raster.witness(s)
                if witness is not None:
                    report.update(growth_excluded=True,raster_fill_witness=witness)
                    report['reasons'].append('ORIGINAL_RASTER_FILL_CURVED_BOUNDARY')
            # Group-fit noise is not a coverage proof. Record a boundary
            # fringe, but retain partial-exposure eligibility unless a
            # separate source-bound fill witness proves its bulk role.
            tolerance=md['minimum_caliper_mm']*source_boundary_noise_fraction
            if not report['fully_covered']and tolerance:
                other=unary_union([n['geometry']for n in neighbors if n['id']not in report['ignored_exact_alias_ids']])
                exposed=current[s].difference(other)
                fringe=exposed.difference(current[s].boundary.buffer(tolerance,quad_segs=128))
                within_noise=other.buffer(tolerance,quad_segs=128).covers(current[s])
                report['source_boundary_noise']=dict(tolerance_mm=tolerance,interior_exposed_area_mm2=fringe.area,
                    complete_stroke_within_cover_noise=within_noise,selection_only=True)
                if within_noise and fringe.is_empty:
                    report.update(boundary_noise_observed=True)
                    report['coverage_notes']=['BOUNDARY_FRINGE_IS_PARTIAL_EXPOSURE; NOT_AN_EXCLUSION_PROOF']
            # Reuse the existing long-overlap witness for plotted fill bundles.
            # These strokes build one copper area rather than separate traces.
            pts=md.get('route_points_mm')
            if not report['growth_excluded']and md['route_kind']=='segment'and pts and len(pts)==2:
                a=dict(id=s,geometry=current[s],start_mm=pts[0],end_mm=pts[-1],width_mm=md['minimum_caliper_mm'])
                for k in near_ids:
                    om=rows[k].get('metadata',{});op=om.get('route_points_mm')
                    if om.get('route_kind')!='segment'or not op or len(op)!=2:continue
                    witness=eligibility.overlapping_parallel_fill_witness(a,dict(id=k,geometry=current[k],
                        start_mm=op[0],end_mm=op[-1],width_mm=om['minimum_caliper_mm']))
                    if witness is not None and witness['longitudinal_overlap_mm']>=math.dist(*pts)-2*md['minimum_caliper_mm']:
                        report.update(growth_excluded=True,fill_witness=witness)
                        report['reasons'].append('OVERLAPPING_SOURCE_STROKES_FORM_FILLED_COPPER');break
                if not report['growth_excluded']and math.dist(*pts)<=md['minimum_caliper_mm']:
                    # Tiny plotting connectors inside a witnessed fill bundle
                    # are fill constituents too. Retain their exact caps; do
                    # not independently enlarge them into a bump on the bulk.
                    long=[]
                    for k in near_ids:
                        om=rows[k].get('metadata',{});op=om.get('route_points_mm')
                        if om.get('route_kind')=='segment'and op and len(op)==2 and math.dist(*op)>.1:
                            long.append(dict(id=k,geometry=current[k],start_mm=op[0],end_mm=op[-1],width_mm=om['minimum_caliper_mm']))
                    for first in long:
                        partner_ids=sorted(ids[int(i)]for i in tree.query(first['geometry'],predicate='intersects')if ids[int(i)]not in(s,first['id']))
                        for k in partner_ids:
                            om=rows[k].get('metadata',{});op=om.get('route_points_mm')
                            if om.get('route_kind')!='segment'or not op or len(op)!=2:continue
                            second=dict(id=k,geometry=current[k],start_mm=op[0],end_mm=op[-1],width_mm=om['minimum_caliper_mm'])
                            witness=eligibility.overlapping_parallel_fill_witness(first,second)
                            if witness and unary_union([first['geometry'],second['geometry']]).covers(LineString(pts)):
                                report.update(growth_excluded=True,fill_connector_witness=witness)
                                report['reasons'].append('SHORT_SOURCE_CONNECTOR_INSIDE_WITNESSED_FILL');break
                        if report['growth_excluded']:break
            if report['growth_excluded']:report['disposition']='FIXED_OWNER_REQUESTED_KEEP'if s in keep_source_ids else 'FIXED_EMBEDDED_OR_FILL'
            return report
        report,binding,hit=retain(directory,dict(key,source_id=s,
            source_geometry_sha256=digest(to_wkb(current[s]))),'ELIGIBILITY.json.gz',build)
        reports[s]=report;bindings[s]=binding;hits+=hit
    covered={s for s,r in reports.items()if r['growth_excluded']}
    active={r:[s for s in ss if s not in covered]for r,ss in paths.items()}
    active={r:ss for r,ss in active.items()if ss}
    ledger=dict(schema='t04-covered-source-projection/2',source_key=key,reports=reports,
                artifact_bindings=bindings,covered_source_ids=sorted(covered),
                native_source_ids_by_route=paths,growth_source_ids_by_route=active,
                keep_routes=sorted(set(paths)-set(active)),
                exactly_covered_source_ids=sorted(s for s,r in reports.items()if r['fully_covered']),
                boundary_noise_covered_source_ids=[],
                boundary_noise_observed_source_ids=sorted(s for s,r in reports.items()if r.get('boundary_noise_observed')),
                fixed_fill_source_ids=sorted(s for s,r in reports.items()if r.get('fill_witness')),
                fixed_fill_connector_source_ids=sorted(s for s,r in reports.items()if r.get('fill_connector_witness')),
                fixed_raster_fill_source_ids=sorted(s for s,r in reports.items()if r.get('raster_fill_witness')),
                owner_keep_source_ids=sorted(keep_source_ids),
                global_eligibility_keep_source_ids=sorted(fixed_source_reasons),
                copper_action='KEEP_EXACT_STAGE_ENTRY_GEOMETRY; NO_INDEPENDENT_GROWTH',
                partial_coverage='RETAIN_ELIGIBILITY; NO_CLIPPING',source_ids_deleted=[],
                containment_is_clearance_exemption=False)
    return active,ledger,dict(wall_s=perf_counter()-started,hits=hits,misses=len(reports)-hits)
