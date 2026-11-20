import math
import pytest
from src.gerber_u05.arc_membership import maximal_members,catalogue


def arc(s,r,first,last,route='r'):
    points=[[r*math.cos(t),r*math.sin(t)]for t in[first+(last-first)*i/100 for i in range(101)]]
    return dict(source_id=s,route_id=route,width_mm=.05,points=points,length_mm=abs(last-first)*r)


def test_native_arc_seams_do_not_cut_a_maximal_member():
    curves=dict(arcs=[arc('a',1.,0.,.4),arc('b',1.,.4,.9)])
    members,mapping,_=maximal_members(dict(runs=[]),curves)
    assert len(members)==1 and mapping[0]==mapping[1]
    assert members[0]['source_ids']==['a','b']
    assert members[0]['member_domain_mm'][1]==pytest.approx(.9,rel=1e-5)
    assert members[0]['reference_points_mm']==curves['arcs'][0]['points']+curves['arcs'][1]['points'][1:]
    assert not members[0]['reference_refitted']


def test_reversed_native_plot_direction_keeps_one_bend():
    first=arc('a',1.,0.,.4);second=arc('b',1.,.4,.9);second['points'].reverse()
    members,_,_=maximal_members(dict(runs=[]),dict(arcs=[first,second]))
    assert len(members)==1
    assert [v['direction']for v in members[0]['source_intervals_mm']]==[1,-1]


def test_native_endpoint_noise_is_not_mistaken_for_a_real_tangent_corner():
    first=arc('a',1.,0.,.4);second=arc('b',1.,.4,.9)
    seam=[first['points'][-1][0]+.0001,first['points'][-1][1]-.0001]
    first['points'][-1]=seam;second['points'][0]=seam
    members,_,_=maximal_members(dict(runs=[]),dict(arcs=[first,second]))
    assert len(members)==1 and seam in members[0]['reference_points_mm']


def test_branch_and_actual_tangent_corner_are_not_silently_merged():
    a=arc('a',1.,0.,.4);b=arc('b',1.,.4,.9)
    straight=dict(runs=[dict(route_id='r',start=a['points'][-1],end=[2.,2.])])
    assert len(maximal_members(straight,dict(arcs=[a,b]))[0])==2
    start=b['points'][0];b['points']=[[start[0]-(p[1]-start[1]),start[1]+p[0]-start[0]]for p in b['points']]
    b['points'][0]=start
    members,_,rejected=maximal_members(dict(runs=[]),dict(arcs=[a,b]))
    assert len(members)==2 and rejected


def test_parallel_members_keep_unequal_whole_bends_not_shared_windows():
    arcs=[arc('a',1.,0.,.4),arc('b',1.,.4,.9),arc('neighbor',1.1,.08,.82,route='other')]
    q=catalogue(dict(runs=[]),dict(arcs=arcs))
    assert len(q['curve_groups'])==1
    members=q['curve_groups'][0]['members']
    assert len(members)==2 and sorted(len(v['source_ids'])for v in members)==[1,2]
    assert len({round(m['length_mm'],3)for m in members})==2
    assert not q['source_members_split']and not q['geometry_audit']
    assert q['curve_groups'][0]['relationship_witnesses'][0]['shared_sampled_run_mm']<max(m['length_mm']for m in members)


def test_translated_identical_bends_do_not_need_nearest_point_tangent_agreement():
    first=arc('a',1.,0.,1.5,route='A');second=arc('b',1.,0.,1.5,route='B')
    second['points']=[[x+.12,y+.08]for x,y in second['points']]
    q=catalogue(dict(runs=[]),dict(arcs=[first,second]))
    assert len(q['curve_groups'])==1
    witness=q['curve_groups'][0]['relationship_witnesses'][0]
    assert witness['fit_scope']=='FULL_MEMBERS'and witness['normalized_error']<1e-12
