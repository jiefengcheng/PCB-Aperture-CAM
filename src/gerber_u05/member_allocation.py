"""Width-optimal two-face budgets across unequal-length parallel members.

Extension of group_allocation's integer budget model: one face can have several
neighbors along its length. The dual is a bipartite minimum-cost edge cover,
solved as a lower-bound circulation. No geometry or candidate search is used.
"""
from .group_allocation import units,mm


def maximum_pair_packing(caps,pairs):
    """Exact general pair-budget packing through a bipartite double cover.

    x_i=(left_i+right_i)/2. Both directed copies of every pair imply
    x_i+x_j<=budget; every feasible x has the lift left=right=x. Thus the
    projected feasible set and maximum sum objective are unchanged.
    """
    keys=sorted(caps)
    if len(keys)<2:raise ValueError('AT_LEAST_TWO_PACKING_VARIABLES_REQUIRED')
    doubled=[(a,b,v)for a,b,v in pairs]+[(b,a,v)for a,b,v in pairs]
    proof=maximum_faces(keys,{r:2*caps[r]for r in keys},doubled,
                        face_caps={r:dict(left=caps[r],right=caps[r])for r in keys})
    growth={r:mm(sum(proof['face_growth_units'][r].values()))/2 for r in keys}
    return dict(schema='t04-general-pair-budget-packing/1',growth_mm=growth,
        total_growth_mm=proof['total_width_growth_mm']/2,
        primal_objective_doubled_units=proof['total_width_growth_units'],
        dual_bound_doubled_units=proof['dual_cost_units'],double_cover=proof,
        physical_quantum_mm=5e-10,geometry_audit=False)


def maximum_faces(members,growth_caps,pair_budgets,*,face_caps):
    keys=list(members)
    if len(keys)<2 or len(set(keys))!=len(keys) or set(keys)!=set(growth_caps) or set(keys)!=set(face_caps):
        raise ValueError('COMPLETE_DISTINCT_MEMBER_BUDGETS_REQUIRED')
    caps={r:units(growth_caps[r])for r in keys}
    faces={r:{s:units(face_caps[r][s])for s in('left','right')}for r in keys}
    pairs=[]
    for low,high,budget in pair_budgets:
        if low==high or low not in caps or high not in caps:raise ValueError('DISTINCT_MEMBER_PAIR_REQUIRED')
        pairs.append((low,high,units(budget)))
    count=len(keys);source,sink=0,1;left={r:2+i for i,r in enumerate(keys)};right={r:2+count+i for i,r in enumerate(keys)}
    size=2+2*count;ss,tt=size,size+1;graph=[[]for _ in range(size+2)];balance=[0]*(size+2);edges=[];infinity=2*count+1
    def edge(a,b,cost,lower=0,capacity=infinity,*,record=True):
        e=[b,len(graph[b]),capacity-lower,cost];reverse=[a,len(graph[a]),0,-cost]
        graph[a].append(e);graph[b].append(reverse);balance[a]-=lower;balance[b]+=lower
        if record:edges.append((a,b,cost,lower,capacity,e))
        return e
    for r in keys:
        edge(source,left[r],0,lower=1);edge(right[r],sink,0,lower=1)
        edge(left[r],right[r],caps[r])
        edge(left[r],sink,faces[r]['left']);edge(source,right[r],faces[r]['right'])
    for low,high,budget in pairs:edge(left[high],right[low],budget)
    edge(sink,source,0);edge(source,sink,0)
    auxiliary=[];demand=0
    for node,b in enumerate(balance[:size]):
        if b>0:auxiliary.append((ss,edge(ss,node,0,capacity=b,record=False)));demand+=b
        elif b<0:auxiliary.append((node,edge(node,tt,0,capacity=-b,record=False)))
    sent=0
    while sent<demand:
        distance=[None]*len(graph);distance[ss]=0;parent={}
        for _ in range(len(graph)-1):
            changed=False
            for a,es in enumerate(graph):
                if distance[a]is None:continue
                for i,e in enumerate(es):
                    b,rev,capacity,cost=e
                    if capacity and (distance[b]is None or distance[b]>distance[a]+cost):
                        distance[b]=distance[a]+cost;parent[b]=(a,i);changed=True
            if not changed:break
        if distance[tt]is None:raise ValueError('MEMBER_DUAL_CIRCULATION_INFEASIBLE')
        delta=demand-sent;node=tt
        while node!=ss:
            a,i=parent[node];delta=min(delta,graph[a][i][2]);node=a
        node=tt
        while node!=ss:
            a,i=parent[node];e=graph[a][i];e[2]-=delta;graph[node][e[1]][2]+=delta;node=a
        sent+=delta
    for a,e in auxiliary:graph[e[0]][e[1]][2]=0;e[2]=0
    # Residual difference potentials are the primal face widths. An optimal
    # circulation has no negative residual cycle; this is checked exactly.
    potential=[0]*size
    for iteration in range(size):
        changed=False
        for a in range(size):
            for b,rev,capacity,cost in graph[a]:
                if b<size and capacity and potential[b]>potential[a]+cost:
                    potential[b]=potential[a]+cost;changed=True
        if not changed:break
    else:raise ValueError('MEMBER_DUAL_NEGATIVE_RESIDUAL_CYCLE')
    if potential[source]!=potential[sink]:raise ValueError('MEMBER_ANCHOR_POTENTIAL_CHANGED')
    allocation={r:dict(left=potential[source]-potential[left[r]],right=potential[right[r]]-potential[source])for r in keys}
    for r,a in allocation.items():
        if min(a.values())<0 or sum(a.values())>caps[r]or any(a[s]>faces[r][s]for s in a):
            raise ValueError('MEMBER_PRIMAL_BUDGET_CHANGED')
    if any(allocation[a]['right']+allocation[b]['left']>v for a,b,v in pairs):
        raise ValueError('MEMBER_SHARED_GAP_BUDGET_CHANGED')
    objective=sum(sum(a.values())for a in allocation.values())
    dual=sum(cost*(capacity-e[2])for a,b,cost,lower,capacity,e in edges)
    if objective!=dual:raise ValueError('MEMBER_PRIMAL_DUAL_CERTIFICATE_MISMATCH')
    # Stable, width-preserving balancing retains all pair budgets. It selects
    # a face split without changing the certified primary objective.
    for order in(keys,list(reversed(keys))):
        for r in order:
            total=sum(allocation[r].values());lo=max(0,total-faces[r]['right']);hi=min(total,faces[r]['left'])
            for a,b,budget in pairs:
                if a==r:lo=max(lo,total+allocation[b]['left']-budget)
                if b==r:hi=min(hi,budget-allocation[a]['right'])
            if lo>hi:raise ValueError('MEMBER_WIDTH_PRESERVING_SPLIT_INFEASIBLE')
            x=min(hi,max(lo,total//2));allocation[r]=dict(left=x,right=total-x)
    return dict(schema='t04-unequal-member-face-allocation/1',members=keys,
        face_growth_units=allocation,face_growth_mm={r:{s:mm(v)for s,v in a.items()}for r,a in allocation.items()},
        total_width_growth_units=objective,total_width_growth_mm=mm(objective),dual_cost_units=dual,
        pair_budget_units=[dict(low=a,high=b,budget=v)for a,b,v in pairs],growth_cap_units=caps,face_cap_units=faces,
        dual_edges=[dict(a=a,b=b,cost=cost,lower=lower,capacity=capacity,flow=capacity-e[2])for a,b,cost,lower,capacity,e in edges],
        dual_potentials=potential,construction_guarantee='INTEGER_PRIMAL_BUDGETS_EQUAL_DUAL_EDGE_COVER_COST',
        objective='MAXIMUM_SUM_WIDTH_GROWTH_WITH_ALL_MEMBER_RELATIONSHIPS',geometry_audit=False)
