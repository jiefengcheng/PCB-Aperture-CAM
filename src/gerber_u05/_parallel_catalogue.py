"""Read-only local parallel-run assessment on saved source centre lines."""
from collections import Counter, defaultdict
from decimal import Decimal
import gzip
import hashlib
import json
import math
from pathlib import Path
from time import perf_counter

from shapely import STRtree
from shapely.geometry import LineString, box

from src.parallel_trace_relations import parallel_relation, relation_groups

ROOT = Path(__file__).resolve().parent
rows = json.loads(gzip.decompress((ROOT/'segments.json.gz').read_bytes()))
admission = json.loads(gzip.decompress((ROOT/'admission.json.gz').read_bytes()))
inputs = json.loads((ROOT/'INPUTS.json').read_text())
objects = {r['source_id']: r for r in rows}
decision_by_source = {member: decision['disposition']
                      for decision in admission['paths']
                      for member in decision['path']['source_ids']}
route_by_source = {member: decision['path']['path_id']
                   for decision in admission['paths']
                   for member in decision['path']['source_ids']}

def dec_point(values):
    return tuple(Decimal(v) for v in values)

def collinear(a,b,c):
    u = tuple(b[i]-a[i] for i in (0,1))
    v = tuple(c[i]-b[i] for i in (0,1))
    return u[0]*v[1] == u[1]*v[0] and u[0]*v[0]+u[1]*v[1] > 0

start = perf_counter()
runs = []
degenerate = []
def save(run):
    if run is None:
        return
    if run['start_decimal'] == run['end_decimal']:
        degenerate.extend(run['source_ids'])
        return
    run['start'] = [float(v) for v in run.pop('start_decimal')]
    run['end'] = [float(v) for v in run.pop('end_decimal')]
    run['length_mm'] = math.dist(run['start'],run['end'])
    run['angle_degrees'] = math.degrees(math.atan2(run['end'][1]-run['start'][1],
                                                 run['end'][0]-run['start'][0])) % 180
    run['run_id'] = 'SR-'+hashlib.sha256('\n'.join(run['source_ids']).encode()).hexdigest()[:16]
    runs.append(run)

for decision in admission['paths']:
    path = decision['path']
    active = None
    for edge in path['ordered_source_edges']:
        row = objects[edge['representative_source_id']]
        if row['metadata']['route_kind'] != 'segment':
            save(active)
            active = None
            continue
        a, b = dec_point(edge['start_decimal_mm']), dec_point(edge['end_decimal_mm'])
        if a == b:
            degenerate.extend(edge['source_alias_ids'])
            continue
        if active is not None and active['end_decimal'] == a and collinear(active['start_decimal'],a,b):
            active['end_decimal'] = b
            active['source_ids'].extend(edge['source_alias_ids'])
        else:
            save(active)
            active = dict(route_id=path['path_id'], disposition=decision['disposition'],
                          width_mm=row['metadata']['minimum_caliper_mm'],
                          start_decimal=a,end_decimal=b,source_ids=list(edge['source_alias_ids']))
    save(active)

all_straight = {r['source_id'] for r in rows if r['metadata']['route_kind']=='segment'}
assigned = [sid for run in runs for sid in run['source_ids']] + degenerate
assert set(assigned) == all_straight and len(assigned) == len(set(assigned))
assert len({r['run_id'] for r in runs}) == len(runs)
geometry = [LineString([r['start'],r['end']]) for r in runs]
tree = STRtree(geometry)
candidates = tree.query(geometry,predicate='dwithin',distance=.5)
pairs = []
counts = Counter()
for i,j in zip(*candidates):
    i,j = int(i),int(j)
    if i >= j:
        continue
    counts['nearby_pairs'] += 1
    a,b = runs[i],runs[j]
    rel = parallel_relation([a['start'],a['end']], [b['start'],b['end']],
                            min_shared_length_mm=.05)
    if rel is None:
        continue
    # Genuine side-by-side trace bodies, with source finite widths retained.
    # Existing pad/junction/obstacle questions remain separate from grouping.
    if geometry[i].distance(geometry[j]) <= (a['width_mm']+b['width_mm'])/2:
        counts['touching_overlapping_or_alias_pairs'] += 1
        continue
    pairs.append(dict(a=i,b=j,**rel))

def connected(edges, members):
    return [[int(v) for v in group] for group in
            relation_groups([str(i) for i in members], [(str(e['a']),str(e['b'])) for e in edges])]

def local_bands(edges):
    by_component = connected(edges, sorted({e[k] for e in edges for k in ('a','b')}))
    adjacency = defaultdict(list)
    for edge in edges:
        adjacency[edge['a']].append(edge)
    bands = []
    unresolved = []
    for component in by_component:
        anchor = max(component,key=lambda i:runs[i]['length_mm'])
        a,b = runs[anchor]['start'],runs[anchor]['end']
        length = math.dist(a,b)
        u = ((b[0]-a[0])/length,(b[1]-a[1])/length)
        angles = []
        for i in component:
            dx = runs[i]['end'][0]-runs[i]['start'][0]
            dy = runs[i]['end'][1]-runs[i]['start'][1]
            angle = math.degrees(math.atan2(dy,dx)-math.atan2(u[1],u[0]))
            angles.append((angle+90)%180-90)
        # Connected near-parallel edges can drift in direction. Surface those
        # components explicitly until an angular subdivision is qualified.
        if max(angles)-min(angles) > 1.+1e-9:
            unresolved.append(dict(members=component,reason='TRANSITIVE_DIRECTION_SPAN'))
            continue
        project = lambda point: point[0]*u[0]+point[1]*u[1]
        spans = {i:sorted((project(runs[i]['start']),project(runs[i]['end']))) for i in component}
        component_edges = [edge for i in component for edge in adjacency[i]]
        events = sorted({value for span in spans.values() for value in span})
        previous = {}
        for lo,hi in zip(events,events[1:]):
            if hi-lo <= 1e-10:
                continue
            mid = (lo+hi)/2
            active = {i for i,(first,last) in spans.items() if first < mid < last}
            live = [edge for edge in component_edges if edge['a'] in active and edge['b'] in active]
            current = {}
            if live:
                groups = connected(live, sorted(active))
                for group in groups:
                    if len(group)<2:
                        continue
                    key = tuple(sorted(group))
                    if key in previous and abs(previous[key]['last']-lo)<1e-8:
                        band = previous[key]
                        band['last'] = hi
                    else:
                        band = dict(members=list(key),first=lo,last=hi,axis=list(u),
                                    anchor=anchor)
                        bands.append(band)
                    current[key] = band
            previous = current
    # Require the actual local common span to meet the same minimum as the pair.
    bands = [b for b in bands if b['last']-b['first'] >= .05-1e-10]
    return bands, unresolved

summaries = {}
outputs = {}
for minimum in (.05,.1,.25):
    for scope in ('all','admitted'):
        edges = [e for e in pairs if e['shared_projected_length_mm'] >= minimum
                 and (scope=='all' or all(runs[e[k]]['disposition']=='ADMIT_COMPLETE_GERBER_ROUTE' for k in ('a','b')))]
        members = {e[k] for e in edges for k in ('a','b')}
        components = connected(edges,sorted(members))
        bands,unresolved = local_bands(edges)
        # A narrower threshold applies to each shared band as well.
        bands = [b for b in bands if b['last']-b['first'] >= minimum-1e-10]
        band_members = {m for band in bands for m in band['members']}
        sources = {sid for m in band_members for sid in runs[m]['source_ids']}
        routes = {runs[m]['route_id'] for m in band_members}
        group_stats = dict(Counter(len(b['members']) for b in bands))
        key = scope+'_'+str(minimum)
        summaries[key] = dict(confirmed_pair_relations=len(edges),pair_graph_components=len(components),
                             largest_pair_graph_component=max(map(len,components),default=0),
                             local_groups=len(bands),runs_in_local_groups=len(band_members),
                             source_segments_in_local_groups=len(sources),routes_in_local_groups=len(routes),
                             local_group_sizes=group_stats, unresolved_direction_components=len(unresolved),
                             cohort_routes_in_local_groups=len(routes & set(inputs['cohort_routes'])))
        outputs[key] = dict(bands=bands,unresolved=unresolved,edges=edges)

counts_by_kind = Counter(r['metadata']['route_kind'] for r in rows)
counts_by_disposition = Counter(decision_by_source[s] for s in all_straight)
summary = dict(scope='Saved accepted T03 source, read-only geometric assessment',
               source_sha256=inputs['source_sha256'],input_scene=inputs['scene_ref'],
               source_straight_segments=counts_by_kind['segment'],source_arcs=counts_by_kind['arc'],
               degenerate_source_segments=len(degenerate),straight_runs=len(runs),
               straight_dispositions=counts_by_disposition,
               exact_collinear_combination='Source-native Decimal collinearity and original route adjacency',
               thresholds=dict(maximum_angle_degrees=1.,maximum_centerline_distance_mm=.5,
                               minimum_shared_run_sweep_mm=[.05,.1,.25]),
               old_route_group_count=len(admission['groups']),
               old_route_groups_of_two_or_more=sum(len(g['members'])>=2 for g in admission['groups']),
               old_largest_route_group=max(len(g['members']) for g in admission['groups']),
               all_straight_source_ids_accounted_for=True,source_copper_changed=False,
               growth_run=False,replay=False,timing_seconds=perf_counter()-start,
               pair_screen_counts=counts,summaries=summaries)
(ROOT/'SUMMARY.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')
(ROOT/'GROUPS.json.gz').write_bytes(gzip.compress(json.dumps(dict(runs=runs,cases=outputs),separators=(',',':')).encode(),mtime=0))
print(json.dumps(summary,indent=2))
