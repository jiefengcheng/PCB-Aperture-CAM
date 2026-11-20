"""Assess spatial translation and uniform scale of saved original arc centre lines."""
from collections import Counter, defaultdict
import gzip
import hashlib
import json
import math
from pathlib import Path
from time import perf_counter

import numpy as np
from shapely import STRtree, distance, get_coordinates, line_interpolate_point, line_locate_point, points
from shapely.geometry import LineString


ROOT = Path(__file__).resolve().parent
BASE = ROOT
MINIMUMS = (.05, .1, .25)
SAMPLES = 129
FIT_TOLERANCE = .01
PROXIMITY_MM = .5

def sample_curve(coords):
    p = np.asarray(coords,dtype=float)
    cumulative = np.r_[0.,np.cumsum(np.linalg.norm(np.diff(p,axis=0),axis=1))]
    if cumulative[-1]<=0:
        raise ValueError('ZERO_LENGTH_CURVE')
    target = np.linspace(0,cumulative[-1],SAMPLES)
    return np.column_stack([np.interp(target,cumulative,p[:,i]) for i in (0,1)])

def fit_model(source,target):
    """Least-squares positive uniform scale, followed by maximum residual."""
    p = source-source.mean(axis=0)
    best = None
    for reverse in (False,True):
        aligned = target[::-1] if reverse else target
        q = aligned-aligned.mean(axis=0)
        scale = float(np.sum(p*q)/np.sum(p*p))
        if scale<=0:
            continue
        translation = aligned.mean(axis=0)-scale*source.mean(axis=0)
        errors = np.linalg.norm(source*scale+translation-aligned,axis=1)
        result = dict(scale=scale,translation_mm=translation.tolist(),reverse=reverse,
                      max_error_mm=float(errors.max()),rms_error_mm=float(np.sqrt(np.mean(errors**2))))
        if best is None or result['max_error_mm']<best['max_error_mm']:
            best=result
    return best

def station_arrays(coords):
    pts=np.asarray(coords,dtype=float)
    lengths=np.r_[0.,np.cumsum(np.linalg.norm(np.diff(pts,axis=0),axis=1))]
    return pts,lengths/lengths[-1]

def full_residual(source_coords,target_coords,fit):
    p,ts=station_arrays(source_coords)
    q,us=station_arrays(target_coords)
    if fit['reverse']:
        q=q[::-1]
        us=1.-us[::-1]
    knots=np.union1d(ts,us)
    a=np.column_stack([np.interp(knots,ts,p[:,i]) for i in (0,1)])
    b=np.column_stack([np.interp(knots,us,q[:,i]) for i in (0,1)])
    residual=np.linalg.norm(a*fit['scale']+fit['translation_mm']-b,axis=1)
    return float(residual.max())

def candidate_neighbor(a,b,ga,gb):
    shorter=a['length_mm']<=b['length_mm']
    first,second=(ga,gb) if shorter else (gb,ga)
    length=float(first.length)
    stations=np.linspace(0.,length,SAMPLES)
    sampled=line_interpolate_point(first,stations)
    p=get_coordinates(sampled)
    t=line_locate_point(second,sampled)
    q=get_coordinates(line_interpolate_point(second,t))
    def tangents(shape, locations):
        h=min(.002,float(shape.length)/4096)
        before=get_coordinates(line_interpolate_point(shape,np.maximum(0.,locations-h)))
        after=get_coordinates(line_interpolate_point(shape,np.minimum(float(shape.length),locations+h)))
        delta=after-before
        norms=np.linalg.norm(delta,axis=1)
        return delta/np.maximum(norms[:,None],1e-30)
    u=tangents(first,stations)
    v=tangents(second,t)
    delta=q-p
    distances=np.linalg.norm(delta,axis=1)
    signs=u[:,0]*delta[:,1]-u[:,1]*delta[:,0]
    alignment=np.abs(np.sum(u*v,axis=1))
    transverse=np.maximum(np.abs(np.sum(u*delta,axis=1)),np.abs(np.sum(v*delta,axis=1)))
    good=((alignment>=math.cos(math.radians(1.))) & (distances>0)
          & (distances<=PROXIMITY_MM) & (signs!=0)
          & (transverse<=distances*math.sin(math.radians(1.))+1e-12))
    best=None
    begin=None
    for k,okay in enumerate(good):
        if okay and begin is not None and signs[k]*signs[k-1]<=0:
            okay=False
        if okay and begin is None:
            begin=k
        if begin is not None and (not okay or k==len(good)-1):
            end=k if okay else k-1
            if best is None or stations[end]-stations[begin]>stations[best[1]]-stations[best[0]]:
                best=(begin,end)
            begin=None
    if best is None:
        return None
    lo,hi=best
    shared=float(stations[hi]-stations[lo])
    if shared<min(MINIMUMS):
        return None
    first_span=[float(stations[lo]),float(stations[hi])]
    second_span=sorted((float(t[lo]),float(t[hi])))
    a_span,b_span=(first_span,second_span) if shorter else (second_span,first_span)
    return dict(shared_sampled_run_mm=shared,a_stations_mm=a_span,b_stations_mm=b_span,
                alignment_angle_degrees=float(np.degrees(np.arccos(np.clip(alignment[lo:hi+1],0,1))).max()),
                transverse_distances_mm=[float(distances[lo:hi+1].min()),float(distances[lo:hi+1].max())],
                midpoint_cross_section_mm=[p[(lo+hi)//2].tolist(),q[(lo+hi)//2].tolist()],
                selection_samples=SAMPLES)

def grouped_members(groups):
    return {member for group in groups for member in group['members']}

def form_template_groups(edges, arcs, samples, minimum):
    adjacent=defaultdict(list)
    for relation in edges:
        adjacent[relation['a']].append((relation['b'],relation['a_stations_mm']))
        adjacent[relation['b']].append((relation['a'],relation['b_stations_mm']))
    proposed=[]
    for anchor in sorted(adjacent):
        neighbors=adjacent[anchor]
        events=sorted({t for _,span in neighbors for t in span})
        previous={}
        for lo,hi in zip(events,events[1:]):
            if hi-lo<=1e-10:
                continue
            middle=(lo+hi)/2
            members=tuple(sorted({anchor}|{i for i,(first,last) in neighbors if first<=middle<=last}))
            if len(members)<2:
                previous={}
                continue
            if members in previous:
                group=previous[members]
                group['template_stations_mm'][1]=hi
            else:
                group=dict(template=anchor,members=list(members),template_stations_mm=[lo,hi])
                proposed.append(group)
            previous={members:group}
    # Overlapping groups are allowed, but every member fits a single recorded
    # reference curve and has a common side-by-side interval on that reference.
    kept=[]
    for group in sorted(proposed,key=lambda g:(-len(g['members']),g['template'],g['template_stations_mm'])):
        if group['template_stations_mm'][1]-group['template_stations_mm'][0]<minimum-1e-10:
            continue
        if any(set(group['members'])<=set(other['members']) for other in kept):
            continue
        anchor=group['template']
        transforms=[]
        for member in group['members']:
            fit=fit_model(samples[anchor],samples[member])
            maximum=full_residual(arcs[anchor]['points'],arcs[member]['points'],fit)
            normalized=maximum/arcs[member]['length_mm']
            if normalized>FIT_TOLERANCE+1e-12:
                raise ValueError('GROUP_TEMPLATE_RESIDUAL_EXCEEDED')
            fit['max_error_mm']=maximum
            transforms.append(dict(member=member,normalized_error=normalized,**fit))
        template_shape=LineString(arcs[anchor]['points'])
        endpoints=line_interpolate_point(template_shape,np.asarray(group['template_stations_mm']))
        intervals=[]
        for member in group['members']:
            shape=LineString(arcs[member]['points'])
            station=line_locate_point(shape,endpoints)
            interval=sorted(station.tolist())
            intervals.append(dict(member=member,stations_mm=interval))
        # Retain a common physical length on every group member after local
        # overlap intervals have been split by a third curve.
        eligible={i['member'] for i in intervals if i['stations_mm'][1]-i['stations_mm'][0]>=minimum-1e-10}
        if anchor not in eligible or len(eligible)<2:
            continue
        group['members']=[m for m in group['members'] if m in eligible]
        group['transforms']=[t for t in transforms if t['member'] in eligible]
        group['member_intervals_mm']=[i for i in intervals if i['member'] in eligible]
        if any(set(group['members'])<=set(other['members']) for other in kept):
            continue
        group['group_id']='PGC-'+hashlib.sha256(
            '\n'.join(arcs[i]['source_id'] for i in group['members']).encode()).hexdigest()[:16]
        group['minimum_shared_run_mm']=minimum
        kept.append(group)
    return kept

def main():
    inputs=json.loads((ROOT/'INPUTS.json').read_text())
    for name,expected in inputs['selection_input_hashes'].items():
        with (BASE/name).open('rb') as stream:
            assert hashlib.file_digest(stream,'sha256').hexdigest()==expected, name
    rows=json.loads(gzip.decompress((BASE/'segments.json.gz').read_bytes()))
    admission=json.loads(gzip.decompress((BASE/'admission.json.gz').read_bytes()))
    straight=json.loads(gzip.decompress((BASE/'GROUPS.json.gz').read_bytes()))
    disposition={sid:d['disposition'] for d in admission['paths'] for sid in d['path']['source_ids']}
    route={sid:d['path']['path_id'] for d in admission['paths'] for sid in d['path']['source_ids']}
    arc_rows=[r for r in rows if r['metadata']['route_kind']=='arc']
    arcs=[dict(source_id=r['source_id'],route_id=route[r['source_id']],disposition=disposition[r['source_id']],
               width_mm=r['metadata']['minimum_caliper_mm'],points=r['metadata']['route_points_mm'])
          for r in arc_rows]
    shapes=[LineString(a['points']) for a in arcs]
    for a,shape in zip(arcs,shapes):
        a['length_mm']=float(shape.length)
    samples=[sample_curve(a['points']) for a in arcs]
    source_rows={r['source_id']:r for r in rows}
    stats=Counter()
    begin=perf_counter()
    tree=STRtree(shapes)
    pairs=tree.query(shapes,predicate='dwithin',distance=PROXIMITY_MM)
    fit_pairs=[]
    relations=[]
    for i,j in zip(*pairs):
        i,j=int(i),int(j)
        if i>=j:
            continue
        stats['nearby_arc_pairs']+=1
        a,b=arcs[i],arcs[j]
        if min(a['length_mm'],b['length_mm'])<min(MINIMUMS):
            stats['shorter_than_005_mm_pairs']+=1
            continue
        fit=fit_model(samples[i],samples[j])
        if fit is None or fit['max_error_mm']/b['length_mm']>FIT_TOLERANCE:
            stats['fit_rejected_pairs']+=1
            continue
        reverse_fit=fit_model(samples[j],samples[i])
        if reverse_fit is None or reverse_fit['max_error_mm']/a['length_mm']>FIT_TOLERANCE:
            stats['reverse_fit_rejected_pairs']+=1
            continue
        fit['max_error_mm']=full_residual(a['points'],b['points'],fit)
        reverse_fit['max_error_mm']=full_residual(b['points'],a['points'],reverse_fit)
        if (fit['max_error_mm']/b['length_mm']>FIT_TOLERANCE
                or reverse_fit['max_error_mm']/a['length_mm']>FIT_TOLERANCE):
            stats['full_curve_fit_rejected_pairs']+=1
            continue
        stats['shape_fit_pairs']+=1
        fit_pairs.append((i,j))
        if shapes[i].distance(shapes[j])<=(a['width_mm']+b['width_mm'])/2:
            stats['touching_or_overlapping_pairs']+=1
            continue
        relation=candidate_neighbor(a,b,shapes[i],shapes[j])
        if relation is None:
            stats['side_by_side_rejected_pairs']+=1
            continue
        relations.append(dict(a=i,b=j,shape_fit=fit,reverse_shape_fit=reverse_fit,**relation))
    summaries={}
    outputs={}
    for minimum in MINIMUMS:
        for scope in ('all','admitted'):
            usable=[r for r in relations if r['shared_sampled_run_mm']>=minimum
                    and (scope=='all' or all(arcs[r[k]]['disposition']=='ADMIT_COMPLETE_GERBER_ROUTE' for k in ('a','b')))]
            groups=form_template_groups(usable,arcs,samples,minimum)
            members=grouped_members(groups)
            curve_sources={arcs[i]['source_id'] for i in members}
            old=straight['cases'][scope+'_'+str(minimum)]
            run_sources={sid for band in old['bands'] for i in band['members']
                         for sid in straight['runs'][i]['source_ids']}
            straight_sources=set()
            for band in old['bands']:
                axis=np.asarray(band['axis'])
                for i in band['members']:
                    for sid in straight['runs'][i]['source_ids']:
                        endpoints=np.asarray(source_rows[sid]['metadata']['route_points_mm'])
                        lo,hi=sorted((endpoints@axis).tolist())
                        if min(hi,band['last'])-max(lo,band['first'])>1e-10:
                            straight_sources.add(sid)
            all_sources=straight_sources|curve_sources
            # Source segment coverage is distinct from complete route coverage.
            route_sources=defaultdict(set)
            for sid in disposition:
                if scope=='all' or disposition[sid]=='ADMIT_COMPLETE_GERBER_ROUTE':
                    route_sources[route[sid]].add(sid)
            routes_touched={route[s] for s in all_sources}
            complete_routes={rid for rid,members in route_sources.items() if members<=all_sources}
            total_arcs=sum(scope=='all' or a['disposition']=='ADMIT_COMPLETE_GERBER_ROUTE' for a in arcs)
            total_segments=sum(scope=='all' or v=='ADMIT_COMPLETE_GERBER_ROUTE' for v in disposition.values())
            key=scope+'_'+str(minimum)
            summaries[key]=dict(arc_segments=total_arcs,arc_segments_grouped=len(curve_sources),
                               arc_groups=len(groups),arc_pair_relations=len(usable),
                               straight_segments_grouped=len(straight_sources),
                               prior_run_associated_straight_segments=len(run_sources),total_source_segments=total_segments,
                               total_source_segments_grouped=len(all_sources),
                               source_segment_coverage_percent=100*len(all_sources)/total_segments,
                               source_arc_coverage_percent=100*len(curve_sources)/total_arcs,
                               routes_with_grouped_segments=len(routes_touched),
                               routes_with_every_source_segment_participating=len(complete_routes),
                               route_count=len(route_sources),curve_group_sizes=dict(Counter(len(g['members']) for g in groups)),
                               benchmark_routes_with_grouped_segments=len(routes_touched&set(inputs['cohort_routes'])),
                               unmatched_arc_segments=total_arcs-len(curve_sources),
                               arc_pair_member_count=len({r[k] for r in usable for k in ('a','b')}))
            outputs[key]=dict(groups=groups,relations=usable,grouped_source_ids=sorted(all_sources))
    stats['shape_fit_arc_members']=len({i for pair in fit_pairs for i in pair})
    result=dict(source_sha256=inputs['source_sha256'],metric='Maximum full polyline centerline residual / target curve length; sampled least-squares scale fit',
                transforms='Positive uniform scale and spatial translation, source direction reversal allowed',
                tolerance=FIT_TOLERANCE,minimum_shared_run_sweep_mm=list(MINIMUMS),spatial_distance_mm=PROXIMITY_MM,
                source_arcs=len(arcs),source_straight_segments=12116,statistics=stats,summaries=summaries,
                scan_wall_s=perf_counter()-begin,source_copper_changed=False,t04_stage_run=False,replay=False)
    (ROOT/'SUMMARY.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    (ROOT/'CURVE_GROUPS.json.gz').write_bytes(gzip.compress(json.dumps(dict(arcs=arcs,cases=outputs),separators=(',',':')).encode(),mtime=0))
    print(json.dumps(result,indent=2))

if __name__=='__main__':
    main()
