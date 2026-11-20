"""Direct two-face allocation for one ordered parallel group.

This replaces only the allocation policy, not source classification, grouping,
geometry storage or residual clearance processing. A trace supplies a total
width-growth budget. Each adjacent gap accepts the two facing contributions.
Integer max-flow maximizes their sum and supplies a matching minimum cut.
There are no geometry imports, trial shapes or cache-dependent decisions here.
"""
from collections import deque
from decimal import Decimal, ROUND_FLOOR
import math

SCHEMA = 't04-parallel-face-allocation/1'
QUANTUM_MM = Decimal('0.000000001')


def units(value):
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise ValueError('FINITE_NONNEGATIVE_GROUP_BUDGET_REQUIRED')
    return int((Decimal(str(value))/QUANTUM_MM).to_integral_value(rounding=ROUND_FLOOR))


def signed_units(value):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError('FINITE_GROUP_BOUND_REQUIRED')
    return int((Decimal(str(value))/QUANTUM_MM).to_integral_value(rounding=ROUND_FLOOR))


def mm(value):
    return float(value*QUANTUM_MM)


def maximum_faces(members, growth_caps, gap_budgets, *, face_caps=None, recessions=None):
    """Maximize sum(left + right), with stable input order and exact budgets.

    ``members`` is the transverse order, from low to high coordinate. Gap i
    lies between member i's right and member i+1's left. Outer faces have no
    gap restriction unless supplied in face_caps. Zero caps encode fixed
    neighbours. Budgets already reserve clearance and construction margins.
    Each source occurrence must be represented exactly once in this problem.
    """
    keys = list(members)
    if len(keys) < 2 or len(set(keys)) != len(keys) or set(keys) != set(growth_caps):
        raise ValueError('ORDERED_DISTINCT_PARALLEL_MEMBERS_REQUIRED')
    if len(gap_budgets) != len(keys)-1:
        raise ValueError('COMPLETE_ADJACENT_GAP_BUDGETS_REQUIRED')
    if face_caps is not None and (set(face_caps) != set(keys) or
            any(set(v) != {'left', 'right'} for v in face_caps.values())):
        raise ValueError('COMPLETE_TWO_FACE_CAPS_REQUIRED')
    caps = {r: units(growth_caps[r]) for r in keys}
    if recessions is not None and set(recessions) != set(keys):
        raise ValueError('COMPLETE_REPOSITIONING_BOUNDS_REQUIRED')
    recess = {r: units(recessions[r]) if recessions is not None else 0 for r in keys}
    if any(type(v) not in (int, float) or not math.isfinite(v) for v in gap_budgets):
        raise ValueError('FINITE_GROUP_GAPS_REQUIRED')
    gaps = [signed_units(v) for v in gap_budgets]
    shifted_gaps = [g+recess[a]+recess[b] for g, a, b in zip(gaps, keys, keys[1:])]
    if any(g < 0 for g in shifted_gaps):raise ValueError('GROUP_POSITION_BOUNDS_INFEASIBLE')
    faces = {r: {side: min(caps[r]+recess[r], signed_units(face_caps[r][side]))+recess[r]
                  if face_caps is not None else caps[r]+2*recess[r]
                  for side in ('left', 'right')} for r in keys}
    if any(v < 0 for q in faces.values() for v in q.values()):
        raise ValueError('GROUP_POSITION_BOUNDS_INFEASIBLE')
    # source -> trace -> gap -> sink. Outer gaps reserve no shared capacity.
    source, sink = 0, 1
    trace = {r: i+2 for i, r in enumerate(keys)}
    gap = [2+len(keys)+i for i in range(len(keys)+1)]
    regular_nodes = 2+len(keys)+len(gap)
    super_source, super_sink = regular_nodes, regular_nodes+1
    graph = [[] for _ in range(regular_nodes+2)]
    edges = []
    balance = [0]*len(graph)

    def edge(a, b, capacity, lower=0, *, original=True):
        forward = [b, len(graph[b]), capacity-lower]
        backward = [a, len(graph[a]), 0]
        graph[a].append(forward)
        graph[b].append(backward)
        if original:edges.append((a, b, capacity, lower, forward))
        balance[a] -= lower;balance[b] += lower
        return forward

    handles = {}
    for i, r in enumerate(keys):
        edge(source, trace[r], caps[r]+2*recess[r], 2*recess[r])
        for side, j in (('left', i), ('right', i+1)):
            handles[r, side] = edge(trace[r], gap[j], faces[r][side])
    infinity = sum(caps.values())+2*sum(recess.values())
    gap_handles = []
    for j, node in enumerate(gap):
        capacity = infinity if j in (0, len(keys)) else shifted_gaps[j-1]
        gap_handles.append((capacity, edge(node, sink, capacity)))

    # Edmonds-Karp is sufficient for the small, sparse lane graph. Integer
    # residuals give exact termination; there is no tolerance/pivot policy.
    def augment(start, end):
        flow = 0
        while True:
            parent = {start: None};queue = deque([start])
            while queue and end not in parent:
                a = queue.popleft()
                for i, e in enumerate(graph[a]):
                    if e[2] and e[0] not in parent:
                        parent[e[0]] = (a, i);queue.append(e[0])
            if end not in parent:return flow, set(parent)
            delta = infinity;node = end
            while node != start:
                a, i = parent[node];delta = min(delta, graph[a][i][2]);node = a
            node = end
            while node != start:
                a, i = parent[node];e = graph[a][i];e[2] -= delta
                graph[node][e[1]][2] += delta;node = a
            flow += delta

    # Lower bounds keep every plotted width >= its nominal source width even
    # when one face retreats. Feasible circulation precedes maximization.
    auxiliary = [(sink, edge(sink, source, infinity, original=False))]
    required_flow = 0
    for node, demand in enumerate(balance[:regular_nodes]):
        if demand > 0:
            auxiliary.append((super_source, edge(super_source, node, demand, original=False)))
            required_flow += demand
        elif demand < 0:auxiliary.append((node, edge(node, super_sink, -demand, original=False)))
    feasible, _ = augment(super_source, super_sink)
    if feasible != required_flow:raise ValueError('GROUP_POSITION_BOUNDS_INFEASIBLE')
    for a, e in auxiliary:
        graph[e[0]][e[1]][2] = 0;e[2] = 0
    augment(source, sink)
    _, reachable = augment(source, sink)
    flow = sum(hi-e[2] for a, b, hi, lo, e in edges if a == source)
    allocation = {r: {side: faces[r][side]-handles[r, side][2]-recess[r]
                       for side in ('left', 'right')} for r in keys}
    # Width-optimal flows can have arbitrary placement ties. Two scalar
    # passes move each center toward its source position while holding ALL
    # solved widths and all neighbouring face budgets fixed. This is not a
    # geometry search or another width objective; the maximum is unchanged.
    for order in (range(len(keys)), range(len(keys)-1, -1, -1)):
        for i in order:
            r = keys[i];g = sum(allocation[r].values())
            low = max(-recess[r], g-(faces[r]['right']-recess[r]))
            high = min(faces[r]['left']-recess[r], g+recess[r])
            if i:high = min(high, gaps[i-1]-allocation[keys[i-1]]['right'])
            if i+1 < len(keys):low = max(low, g+allocation[keys[i+1]]['left']-gaps[i])
            left = min(high, max(low, g//2))
            if low > high:raise ValueError('GROUP_PLACEMENT_BUDGET_IDENTITY_CHANGED')
            allocation[r] = dict(left=left, right=g-left)
    for r in keys:
        for side in ('left', 'right'):
            e = handles[r, side];f = allocation[r][side]+recess[r]
            e[2] = faces[r][side]-f;graph[e[0]][e[1]][2] = f
    for j, (capacity, e) in enumerate(gap_handles):
        f = ((allocation[keys[j-1]]['right']+recess[keys[j-1]]) if j else 0)
        if j < len(keys):f += allocation[keys[j]]['left']+recess[keys[j]]
        e[2] = capacity-f;graph[e[0]][e[1]][2] = f
    cut = (sum(hi for a, b, hi, lo, _ in edges if a in reachable and b not in reachable)
           -sum(lo for a, b, hi, lo, _ in edges if a not in reachable and b in reachable))
    if cut != flow:
        raise ValueError('GROUP_MAXIMUM_FLOW_CERTIFICATE_MISMATCH')
    return dict(schema=SCHEMA, members=keys, quantum_mm=str(QUANTUM_MM),
                growth_cap_units=caps, gap_budget_units=gaps, recession_units=recess,
                face_cap_units={r: {s: v-recess[r] for s, v in q.items()} for r, q in faces.items()},
                face_growth_units=allocation,
                face_growth_mm={r: {s: mm(v) for s, v in q.items()} for r, q in allocation.items()},
                total_width_growth_mm=mm(flow-2*sum(recess.values())),
                total_width_growth_units=flow-2*sum(recess.values()),
                minimum_cut_units=cut-2*sum(recess.values()), minimum_cut_reachable_nodes=sorted(reachable),
                network_edges=[dict(a=a, b=b, lower=lo, upper=hi, flow=hi-e[2]) for a, b, hi, lo, e in edges],
                source_node=source, sink_node=sink, shifted_objective_constant_units=2*sum(recess.values()),
                objective='MAXIMUM_SUM_WIDTH_GROWTH; NO_PROPORTIONAL_FAIRNESS',
                construction_guarantee='EXACT_INTEGER_BUDGETS_AND_MAX_FLOW_MIN_CUT',
                geometry_audit=False)


def consecutive_widths(proposed, edges, *, deviation=.25):
    """Greatest feasible widths below proposals with LOCAL adjacency limits.

    This is the existing limiting-segment propagation applied to actual route
    adjacency, not an equality or a global route-minimum width band. It does
    not choose geometric neighbours. A chain may increase beyond 25% overall.
    """
    if type(deviation) not in (int, float) or not math.isfinite(deviation) or not 0 <= deviation <= .25:
        raise ValueError('LOCAL_WIDTH_DEVIATION_INVALID')
    value = {r: units(w) for r, w in proposed.items()}
    if any(v <= 0 for v in value.values()):
        raise ValueError('POSITIVE_SEGMENT_WIDTH_REQUIRED')
    ratio = Decimal(1)+Decimal(str(deviation))
    adjacent = {r: set() for r in value}
    for a, b in edges:
        if a == b or a not in value or b not in value:
            raise ValueError('ACTUAL_ROUTE_ADJACENCY_REQUIRED')
        adjacent[a].add(b)
        adjacent[b].add(a)
    queue = deque(sorted(value)); pending = set(value)
    while queue:
        a = queue.popleft(); pending.remove(a)
        ceiling = int((value[a]*ratio).to_integral_value(rounding=ROUND_FLOOR))
        for b in sorted(adjacent[a]):
            if value[b] > ceiling:
                value[b] = ceiling
                if b not in pending:
                    queue.append(b); pending.add(b)
    return {r: mm(v) for r, v in value.items()}
