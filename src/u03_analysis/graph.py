"""Deterministic graph measurements with checkable decomposition certificates."""
from collections import Counter, deque
import heapq
import math
import sys
sys.setrecursionlimit(max(20000,sys.getrecursionlimit()))


def components(adj, nodes=None):
    unseen=set(adj if nodes is None else nodes);result=[]
    while unseen:
        root=min(unseen);unseen.remove(root);stack=[root];part=[]
        while stack:
            v=stack.pop();part.append(v)
            for w in sorted(adj[v]&unseen):unseen.remove(w);stack.append(w)
        result.append(sorted(part))
    return sorted(result,key=lambda x:(-len(x),x[0]))


def blocks(adj):
    clock=0;seen={};low={};stack=[];cuts=set();bridges=[];bags=[]
    def visit(v,parent=None):
        nonlocal clock
        clock+=1;seen[v]=low[v]=clock;children=0
        for w in sorted(adj[v]):
            if w not in seen:
                children+=1;stack.append((v,w));visit(w,v);low[v]=min(low[v],low[w])
                if low[w]>=seen[v]:
                    if parent is not None or children>1:cuts.add(v)
                    bag=set()
                    while stack:
                        edge=stack.pop();bag.update(edge)
                        if edge==(v,w):break
                    bags.append(sorted(bag))
                if low[w]>seen[v]:bridges.append(sorted((v,w)))
            elif w!=parent and seen[w]<seen[v]:
                stack.append((v,w));low[v]=min(low[v],seen[w])
    for v in sorted(adj):
        if v not in seen:
            visit(v)
            if not adj[v]:bags.append([v])
    return dict(articulation_vertices=sorted(cuts),bridges=sorted(bridges),blocks=sorted(bags,key=lambda b:(-len(b),b)))


def elimination(adj):
    """Min-degree fill gives an upper bound, not an exact minimum treewidth."""
    g={v:set(n) for v,n in adj.items()};heap=[(len(n),v) for v,n in g.items()];heapq.heapify(heap);bags={};order=[]
    while g:
        degree,v=heapq.heappop(heap)
        if v not in g or degree!=len(g[v]):continue
        neighbors=sorted(g[v]);bags[v]=[v,*neighbors];order.append(v)
        for w in neighbors:
            g[w].remove(v);g[w].update(set(neighbors)-{w});heapq.heappush(heap,(len(g[w]),w))
        del g[v]
    pos={v:i for i,v in enumerate(order)}
    parents={v:min(bags[v][1:],key=pos.get) if len(bags[v])>1 else None for v in order}
    # Verify original-edge coverage and connected bags for every original vertex.
    occurrences=Counter(x for bag in bags.values() for x in bag);links=Counter()
    for v,p in parents.items():
        if p is not None:
            assert pos[p]>pos[v]
            links.update(set(bags[v])&set(bags[p]))
    assert all(links[v]==n-1 for v,n in occurrences.items())
    assert all(w in bags[v] if pos[v]<pos[w] else v in bags[w] for v in adj for w in adj[v])
    return dict(width=max((len(b)-1 for b in bags.values()),default=0),order=order,bags=bags,parents=parents,certificate_verified=True)


def minor_lower_bound(adj):
    """Every contraction creates a minor; its minimum degree bounds treewidth."""
    g={v:set(n) for v,n in adj.items()};bound=0;steps=[]
    while g:
        v=min(g,key=lambda x:(len(g[x]),x));bound=max(bound,len(g[v]))
        if not g[v]:steps.append([v,None,0]);del g[v];continue
        w=min(g[v],key=lambda x:(len(g[v]&g[x]),len(g[x]),x));steps.append([v,w,len(g[v])])
        neighbors=(g[v]|g[w])-{v,w}
        for x in g[v]:g[x].discard(v)
        for x in neighbors:g[x].add(w)
        g[w]=neighbors;del g[v]
    return dict(width=bound,contractions=steps)


def balanced_separator(adj,nodes):
    """Validated <=2/3 separators from BFS layers; heuristic, never minimum claim."""
    nodes=set(nodes)
    if len(nodes)<=1:return dict(vertices=sorted(nodes),size=len(nodes),remaining_component_sizes=[],balanced=True,method='singleton')
    def distances(seed):
        d={seed:0};q=deque([seed])
        while q:
            v=q.popleft()
            for w in sorted(adj[v]&nodes):
                if w not in d:d[w]=d[v]+1;q.append(w)
        assert set(d)==nodes
        return d
    first=min(nodes);d=distances(first);far=max(d,key=lambda v:(d[v],v));d2=distances(far);other=max(d2,key=lambda v:(d2[v],v))
    seeds=sorted({first,far,other,min(nodes,key=lambda v:(len(adj[v]),v)),max(nodes,key=lambda v:(len(adj[v]),v)),*sorted(nodes)[::max(1,len(nodes)//4)]})
    candidates=[]
    for seed in seeds:
        d=distances(seed);layers={}
        for v,level in d.items():layers.setdefault(level,[]).append(v)
        before=0
        for level,layer in sorted(layers.items()):
            after=len(nodes)-before-len(layer)
            if 3*max(before,after)<=2*len(nodes):candidates.append((len(layer),sorted(layer),seed,level))
            before+=len(layer)
    _,cut,seed,level=min(candidates);parts=components(adj,nodes-set(cut));sizes=[len(p) for p in parts]
    assert 3*max(sizes,default=0)<=2*len(nodes)
    return dict(vertices=cut,size=len(cut),remaining_component_sizes=sizes,balanced=True,method='BFS-layer heuristic',seed=seed,layer=level,minimum_established=False)


def analyze(adj):
    parts=components(adj);b=blocks(adj);details=[]
    for p in parts:
        g={v:adj[v]&set(p) for v in p};upper=elimination(g);lower=minor_lower_bound(g);assert lower['width']<=upper['width']
        details.append(dict(nodes=p,size=len(p),edges=sum(map(len,g.values()))//2,treewidth_lower=lower['width'],treewidth_upper=upper['width'],decomposition=upper,lower_certificate=lower,separator=balanced_separator(g,p)))
    degrees=sorted(map(len,adj.values()))
    return dict(nodes=len(adj),edges=sum(degrees)//2,component_count=len(parts),component_sizes=[len(p) for p in parts],component_size_histogram=dict(sorted(Counter(map(len,parts)).items())),isolated_nodes=sum(not n for n in adj.values()),degree=dict(median=degrees[len(degrees)//2] if degrees else 0,p95=degrees[min(len(degrees)-1,math.ceil(.95*len(degrees))-1)] if degrees else 0,maximum=max(degrees,default=0)),articulation_count=len(b['articulation_vertices']),bridge_count=len(b['bridges']),block_sizes=[len(x) for x in b['blocks']],blocks=b,components=details)


def verify_minor_certificate(adj,certificate):
    g={v:set(n) for v,n in adj.items()};bound=0
    for v,w,degree in certificate['contractions']:
        assert v in g and degree==len(g[v])==min(map(len,g.values()))
        bound=max(bound,degree)
        if w is None:assert not g[v];del g[v];continue
        assert w in g[v]
        neighbors=(g[v]|g[w])-{v,w}
        for x in g[v]:g[x].discard(v)
        for x in neighbors:g[x].add(w)
        g[w]=neighbors;del g[v]
    assert not g and bound==certificate['width']
    return True


def decomposition_separator(adj,decomposition):
    """Balanced bags/adhesions in a checked tree decomposition; not minimum cuts."""
    bags=decomposition['bags'];parents=decomposition['parents'];tree={v:set() for v in bags}
    for v,p in parents.items():
        if p is not None:tree[v].add(p);tree[p].add(v)
    root=min(tree);parent={root:None};order=[root]
    for v in order:
        for w in sorted(tree[v]):
            if w!=parent[v]:parent[w]=v;order.append(w)
    assert len(order)==len(adj)
    size=dict.fromkeys(tree,1)
    for v in reversed(order[1:]):size[parent[v]]+=size[v]
    total=len(adj);centroids=[v for v in tree if max([total-size[v],*[size[w] for w in tree[v] if parent.get(w)==v]])*2<=total]
    candidates={tuple(sorted(bags[v])) for v in centroids}
    for v in order[1:]:
        if 3*max(size[v],total-size[v])<=2*total:candidates.add(tuple(sorted(set(bags[v])&set(bags[parent[v]]))))
    for cut in sorted(candidates,key=lambda c:(len(c),c)):
        parts=components(adj,set(adj)-set(cut));sizes=list(map(len,parts))
        if 3*max(sizes,default=0)<=2*total:
            result=dict(vertices=list(cut),size=len(cut),remaining_component_sizes=sizes,balanced=True,method='Verified decomposition bag/adhesion',minimum_established=False)
            if len(cut)==1:result.update(minimum_established=True,minimum_proof='Connected nonempty graph has no balanced empty separator')
            elif len(cut)==2:
                singles=blocks(adj)['articulation_vertices'];balanced=[]
                for v in singles:
                    largest=max(map(len,components(adj,set(adj)-{v})),default=0)
                    if 3*largest<=2*len(adj):balanced.append(v)
                result['single_vertex_candidates_checked']=len(singles)
                if not balanced:result.update(minimum_established=True,minimum_proof='All articulation vertices exhausted; no balanced size-one cut; size-two witness verified')
            return result
    raise ValueError('DECOMPOSITION_BALANCED_SEPARATOR_MISSING')


def recursive_partition(adj,leaf_limit=64):
    records=[]
    def split(nodes,ancestors,depth):
        nodes=set(nodes);g={v:adj[v]&nodes for v in nodes};boundary=sorted(set().union(*(adj[v]&ancestors for v in nodes)))
        record=dict(nodes=sorted(nodes),size=len(nodes),depth=depth,boundary=boundary,boundary_size=len(boundary));records.append(record)
        if len(nodes)<=leaf_limit:record['leaf']=True;return
        d=elimination(g);cut=decomposition_separator(g,d);record.update(leaf=False,separator=cut)
        for p in components(g,nodes-set(cut['vertices'])):split(p,ancestors|set(cut['vertices']),depth+1)
    for p in components(adj):split(p,set(),0)
    cuts=[r['separator']['size'] for r in records if not r['leaf']];leaves=[r for r in records if r['leaf']]
    selected=set(v for r in records if not r['leaf'] for v in r['separator']['vertices']);remaining=set(v for r in leaves for v in r['nodes'])
    assert not selected&remaining and selected|remaining==set(adj)
    assert sum(r['size'] for r in leaves)+len(selected)==len(adj)
    return dict(leaf_limit=leaf_limit,separator_count=len(cuts),separator_sizes=sorted(cuts,reverse=True),separator_vertices_total=len(selected),leaf_count=len(leaves),leaf_sizes=sorted([r['size'] for r in leaves],reverse=True),maximum_leaf_boundary=max([r['boundary_size'] for r in leaves],default=0),records=records)
