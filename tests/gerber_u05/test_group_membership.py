import math
from src.gerber_u05.group_membership import catalogue,maximal_members


def fixture(angles=(0.,0.)):
    runs=[dict(run_id=str(i),route_id=str(i),source_ids=[str(i)],start=[0.,i*.1],
               end=[length*math.cos(math.radians(a)),i*.1+length*math.sin(math.radians(a))],
               length_mm=length,angle_degrees=a)
          for i,(a,length)in enumerate(zip(angles,(2.,1.,3.,4.)))]
    edges=[dict(a=i,b=i+1,alignment_angle_degrees=abs(angles[i+1]-angles[i]),shared_projected_length_mm=.1)
           for i in range(len(angles)-1)]
    return dict(runs=runs,cases={'admitted_0.05':dict(edges=edges)}),dict(arcs=[],cases={'admitted_0.05':dict(groups=[])})


def test_members_keep_unequal_full_lengths_instead_of_the_short_overlap():
    straight,curves=fixture();q=catalogue(straight,curves)
    g=q['straight_groups'][0]
    assert sorted(m['length_mm']for m in g['members'])==[1.,2.]
    assert not q['source_members_split'] and not q['overlap_is_member_domain']
    assert g['relationship_witnesses'][0]['shared_projected_length_mm']==.1


def test_transitive_direction_chain_does_not_become_one_invalid_template():
    q=catalogue(*fixture((0.,.4,.8)))
    assert all(len(g['members'])<=2 for g in q['straight_groups'])
    assert len(q['all_straight_relationships'])==2
    assert q['nonprimary_relationships_retained']


def test_one_percent_is_not_one_degree_and_wraps_at_180():
    q=catalogue(*fixture((0.,.8)))
    assert not q['straight_groups'] and len(q['rejected_straight_relationships'])==1
    straight,curves=fixture((179.9,.1))
    straight['cases']['admitted_0.05']['edges'][0]['alignment_angle_degrees']=.2
    assert len(catalogue(straight,curves)['straight_groups'])==1


def test_long_member_crosses_group_events_without_becoming_short_islands():
    straight,curves=fixture()
    a=straight['runs'][0]
    straight['runs']=[dict(a,end=[1.,0.],length_mm=1.,source_ids=['a0']),
                      dict(a,start=[1.,0.],end=[2.,0.],length_mm=1.,run_id='a1',source_ids=['a1']),
                      straight['runs'][1]]
    straight['cases']['admitted_0.05']['edges']=[
        dict(a=i,b=2,alignment_angle_degrees=0.,shared_projected_length_mm=.1)for i in (0,1)]
    q=catalogue(straight,curves)
    assert q['native_run_to_member']['0']==q['native_run_to_member']['1']
    m=next(m for m in q['straight_groups'][0]['members']if len(m['source_ids'])==2)
    assert m['member_domain_mm']==[0.,2.] and m['source_ids']==['a0','a1']
    assert len(q['all_straight_relationships'])==2


def test_small_native_edge_noise_does_not_split_but_real_bends_and_breaks_do():
    runs=[];a=[0.,0.]
    for i,angle in enumerate((0.,.4,.8)):
        b=[a[0]+math.cos(math.radians(angle)),a[1]+math.sin(math.radians(angle))]
        runs.append(dict(run_id=str(i),route_id='r',source_ids=[str(i)],start=a,end=b,
                         angle_degrees=angle,length_mm=1.));a=b
    members,mapping=maximal_members(runs)
    assert len(members)==2 and mapping[0]==mapping[1]!=mapping[2]
    assert members[0]['length_mm']==2. and not members[0]['reference_refitted']
    runs[1]['start']=[1.01,0.]
    _,mapping=maximal_members(runs)
    assert mapping[0]!=mapping[1]
