"""Geometric width-target routes through original native junctions.

No primitive is trimmed. Exact aliases retain all source identities. A unique
near-straight continuation may cross a branch node; other branches terminate at
that original junction. Ambiguous continuations are never inferred electrically.
"""
from collections import defaultdict
from decimal import Decimal
import hashlib,math


def key(p):
    v=tuple(Decimal(x) for x in p)
    if len(v)!=2 or not all(x.is_finite() for x in v):raise ValueError('INVALID_ENDPOINT')
    return v


def junction_source_paths(rows,selected_ids,*,maximum_turn_degrees=5.):
    objects={r['source_id']:r for r in rows}
    if len(objects)!=len(rows) or not set(selected_ids)<=objects.keys():raise ValueError('INVALID_SOURCE_IDENTITIES')
    if not 0<=maximum_turn_degrees<=10:raise ValueError('UNBOUNDED_CONTINUATION_SELECTION')
    alias_groups=defaultdict(list)
    for sid,r in objects.items():
        if not math.isfinite(r['width_mm']) or r['width_mm']<=0:raise ValueError('INVALID_SOURCE_WIDTH')
        if len(r['endpoints_decimal_mm'])!=2:raise ValueError('INVALID_ENDPOINTS')
        ends=tuple(key(p) for p in r['endpoints_decimal_mm'])
        signature=(r['width_mm'],tuple(sorted(ends)),r.get('source_wkb_sha256',sid))
        alias_groups[signature].append(sid)
    aliases={min(sids):sorted(sids) for sids in alias_groups.values()}
    representatives={rep:objects[rep] for rep in aliases}
    endpoints={rep:[key(p) for p in r['endpoints_decimal_mm']] for rep,r in representatives.items()}
    closed_edges={rep:endpoints[rep][0]==endpoints[rep][1] and any(tuple(point)!=tuple(r['route_points_mm'][0]) for point in r['route_points_mm'][1:]) for rep,r in representatives.items()}
    nodes=defaultdict(set);all_nodes=defaultdict(set)
    for rep,r in representatives.items():
        for p in endpoints[rep]:nodes[(r['width_mm'],p)].add(rep);all_nodes[p].add(rep)
    def tangent(rep,p):
        points=representatives[rep]['route_points_mm']
        if p==endpoints[rep][1]:points=list(reversed(points))
        for a,b in zip(points,points[1:]):
            dx,dy=b[0]-a[0],b[1]-a[1];n=math.hypot(dx,dy)
            if n:return dx/n,dy/n
        return None
    links={};junctions={};limit=-math.cos(math.radians(maximum_turn_degrees))
    for (width,p),edges in sorted(nodes.items()):
        edges=sorted(edges)
        if len(edges)==2 and all(endpoints[e][0]!=endpoints[e][1] for e in edges):
            a,b=edges;links[(a,p)]=b;links[(b,p)]=a
        elif len(edges)>2:
            vectors={e:None if closed_edges[e] else tangent(e,p) for e in edges};best={}
            for a in edges:
                candidates=[]
                for b in edges:
                    if a==b or not vectors[a] or not vectors[b]:continue
                    dot=sum(x*y for x,y in zip(vectors[a],vectors[b]))
                    if dot<=limit:candidates.append((dot,b))
                candidates.sort()
                if candidates and (len(candidates)==1 or candidates[1][0]-candidates[0][0]>1e-12):best[a]=candidates[0][1]
            for a,b in best.items():
                if best.get(b)==a:links[(a,p)]=b;links[(b,p)]=a
            junctions[(width,p)]=dict(paired_continuations=sorted({tuple(sorted((a,links[(a,p)]))) for a in edges if (a,p) in links}),
                terminating_edges=[e for e in edges if (e,p) not in links],
                selection='Unique mutual near-straight tangent continuation; unpaired branches end at this exact original junction')
    selected_reps={rep for rep,sids in aliases.items() if set(sids)&set(selected_ids)}
    unseen=set(selected_reps);paths=[]
    while unseen:
        todo=[min(unseen)];members=set()
        while todo:
            rep=todo.pop()
            if rep in members:continue
            members.add(rep)
            todo.extend(links[(rep,p)] for p in endpoints[rep] if (rep,p) in links and links[(rep,p)] not in members)
        unseen-=members
        source_ids=sorted(sid for rep in members for sid in aliases[rep]);ports=[];terminals=[]
        width=representatives[min(members)]['width_mm'];assert all(representatives[e]['width_mm']==width for e in members)
        for p in sorted({p for e in members for p in endpoints[e]}):
            own={e for e in members if p in endpoints[e]};other=all_nodes[p]-members
            if other:
                ports.append(dict(point_decimal_mm=[str(v) for v in p],
                    own_source_ids=sorted(s for e in own for s in aliases[e]),
                    neighboring_source_ids=sorted(s for e in other for s in aliases[e]),
                    other_original_widths_mm=sorted({representatives[e]['width_mm'] for e in other}),
                    continuation=junctions.get((width,p)),
                    basis='Exact original native junction/width transition; no crop cut or primitive trimming'))
            for e in own:
                if (e,p) not in links and not closed_edges[e]:terminals.append([str(v) for v in p])
        degenerate=all(endpoints[e][0]==endpoints[e][1] and not closed_edges[e] for e in members)
        # Traverse native edges, rather than letting native fragmentation define
        # parallel membership. This polyline is selection evidence only: source
        # WKB, actual copper checks and original route construction are unchanged.
        starts=sorted((e,p) for e in members for p in endpoints[e] if (e,p) not in links)
        edge,node=starts[0] if starts else (min(members),min(endpoints[min(members)]))
        ordered=[];points=[];visited=set()
        while edge not in visited:
            visited.add(edge)
            a,b=endpoints[edge]
            route=list(representatives[edge]['route_points_mm'])
            if node==b and a!=b:route=list(reversed(route))
            other=b if node==a else a
            # Decimal native junctions bind adjacency; sampled arc endpoints may
            # differ by floating point roundoff, and are anchored for selection.
            route[0]=[float(v) for v in node];route[-1]=[float(v) for v in other]
            if points:assert points[-1]==route[0]
            points.extend(route if not points else route[1:])
            ordered.append(dict(representative_source_id=edge,source_alias_ids=aliases[edge],
                start_decimal_mm=[str(v) for v in node],end_decimal_mm=[str(v) for v in other]))
            if (edge,other) not in links:break
            edge,node=links[(edge,other)],other
        assert visited==members,'INCOMPLETE_NATIVE_ROUTE_TRAVERSAL'
        paths.append(dict(path_id='JR-'+hashlib.sha256('\n'.join(source_ids).encode()).hexdigest()[:16],
            source_ids=source_ids,source_alias_sets={e:aliases[e] for e in sorted(members)},
            ordered_source_edges=ordered,ordered_route_points_mm=points,
            ordered_route_role='SOURCE_SELECTION_ONLY; native junction endpoints anchor sampled arc endpoints; copper WKB unchanged',
            uniform_original_width_mm=width,terminal_points_decimal_mm=terminals,
            original_junction_ports=ports,original_width_transition_ports=[p for p in ports if any(w!=width for w in p['other_original_widths_mm'])],
            route_type='DEGENERATE_SOURCE_STROKE_CONTEXT' if degenerate else 'CLOSED_UNIFORM_SOURCE_ROUTE' if not terminals else 'OPEN_UNIFORM_SOURCE_ROUTE',
            path_status='PROPOSED_JUNCTION_BOUND_SOURCE_ROUTE',
            original_native_source_members_retained=True,primitive_trimming='NONE',
            construction_authority='SOURCE_DEFINITION_ONLY; no width growth or electrical continuation claim'))
    assigned=[sid for p in paths for sid in p['source_ids']]
    assert len(assigned)==len(set(assigned)) and set(selected_ids)<=set(assigned)
    return sorted(paths,key=lambda p:p['path_id'])
