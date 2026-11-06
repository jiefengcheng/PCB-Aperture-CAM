import copy,json,math
from pathlib import Path
import pytest
from src.source_junction_paths import junction_source_paths

def edge(sid,points,width=.1):
 return dict(source_id=sid,kind='arc',width_mm=width,route_points_mm=points,
  endpoints_decimal_mm=[[str(v)for v in points[0]],[str(v)for v in points[-1]]],source_wkb_sha256=sid)

def test_nonzero_full_circle_is_closed_without_an_open_terminal():
 points=[[math.cos(2*math.pi*i/16),math.sin(2*math.pi*i/16)]for i in range(16)]+[[1.,0.]]
 row=edge('circle',points);before=copy.deepcopy(row);route=junction_source_paths([row],['circle'])[0]
 assert route['route_type']=='CLOSED_UNIFORM_SOURCE_ROUTE'
 assert route['terminal_points_decimal_mm']==[] and route['source_ids']==['circle']
 assert route['ordered_route_points_mm']==points and row==before

def test_a_true_zero_length_stroke_remains_degenerate():
 row=edge('dot',[[1.,2.],[1.,2.]])
 route=junction_source_paths([row],['dot'])[0]
 assert route['route_type']=='DEGENERATE_SOURCE_STROKE_CONTEXT'

def test_full_circle_preserves_explicit_branch_port_and_separate_branch():
 circle=edge('circle',[[1.,0.],[0.,1.],[-1.,0.],[0.,-1.],[1.,0.]])
 branch=edge('branch',[[1.,0.],[2.,0.]],.2)
 routes=junction_source_paths([circle,branch],['circle','branch']);loop=next(r for r in routes if r['source_ids']==['circle'])
 assert loop['route_type']=='CLOSED_UNIFORM_SOURCE_ROUTE' and not loop['terminal_points_decimal_mm']
 assert loop['original_junction_ports'][0]['neighboring_source_ids']==['branch']
 assert len(routes)==2 and sorted(s for r in routes for s in r['source_ids'])==['branch','circle']


@pytest.mark.parametrize("branches", [
 ([[1.,0.],[1.,-2.]], [[1.,0.],[2.,0.]]),
 ([[1.,0.],[1.,-2.]], [[1.,0.],[1.,2.]]),
])
def test_closed_loop_never_becomes_an_open_branch_continuation(branches):
 circle=edge('circle',[[1.,0.],[1.,1.],[0.,1.],[0.,0.],[1.,0.]])
 rows=[circle]+[edge('branch-'+str(i),points)for i,points in enumerate(branches)]
 routes=junction_source_paths(rows,[r['source_id']for r in rows])
 loop=next(r for r in routes if r['source_ids']==['circle'])
 assert loop['route_type']=='CLOSED_UNIFORM_SOURCE_ROUTE' and not loop['terminal_points_decimal_mm']
 assert sorted(s for r in routes for s in r['source_ids'])==['branch-0','branch-1','circle']
 assert loop['original_junction_ports'][0]['neighboring_source_ids']==['branch-0','branch-1']
