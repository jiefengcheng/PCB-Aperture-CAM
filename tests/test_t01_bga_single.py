"""Explicit-clear isolated islands are distinct from paired or attached pads."""
import copy
import pytest
from shapely.geometry import Point, box
from shapely import to_wkb
from src.stage_abi.store import digest
from src.t01_bga_single import qualify, eligible_sites, capture

SOURCE = 'b'*64


def source_case():
    circles=[]
    for y in range(3):
        for x in range(3):
            i=3*y+x;g=Point(x*.4,y*.4).buffer(.125,quad_segs=128)
            circles.append(dict(source_id=f'{SOURCE}:bytes:{100+i}:{200+i}',
                                ordinal=i+2,center=[x*.4,y*.4],radius=.125,core=g))
    clears=[dict(source_id=f'{SOURCE}:bytes:0:99',ordinal=1,
                 removed=box(-1,-1,2,2))]
    return circles,clears


def operands(circles,markers):
    rows=[dict(id=c['source_id'],kind='gr_circle',trace_width_mm=0.,source_span=[0,0],
               t01_bga_single=markers[c['source_id']])for c in circles]
    sites=[dict(source_id=c['source_id'],aliases=[c['source_id']],indexes=[i],
                center=c['center'],radius=c['radius'],core=c['core'],
                enlarged_radius=1.5*c['radius'],geometry_sha256=digest(to_wkb(c['core'])),
                physical_contact_group=f'isolated-{i}')for i,c in enumerate(circles)]
    return rows,[c['core']for c in circles],sites


def test_original_clear_then_restoring_dark_grid_is_qualified():
    circles,clears=source_case();q=qualify(SOURCE,circles,clears,coordinate_grid_mm=.00001)
    rows,shapes,sites=operands(circles,q)
    assert len(q)==9 and set(eligible_sites(sites,rows,shapes))==set(q)
    assert len({v['array_sha256']for v in q.values()})==1
    assert all(v['witness']['policy']==capture() for v in q.values())
    assert q==qualify(SOURCE,list(reversed(circles)),clears,coordinate_grid_mm=.00001)


@pytest.mark.parametrize('fault',['no_clear','late_clear','no_removed_material','irregular','incomplete','two_rows'])
def test_ordinary_or_unproven_arrays_do_not_acquire_the_exception(fault):
    circles,clears=source_case()
    if fault=='no_clear':clears=[]
    elif fault=='late_clear':clears[0]['ordinal']=1000
    elif fault=='no_removed_material':clears[0]['removed']=box(3,3,4,4)
    elif fault=='irregular':circles[-1]['center'][0]+=.00001
    elif fault=='incomplete':circles.pop(4)
    elif fault=='two_rows':circles=circles[:6]
    assert qualify(SOURCE,circles,clears,coordinate_grid_mm=.00001)=={}


@pytest.mark.parametrize('attachment',['trace','region','other_pad'])
def test_existing_pair_or_long_feed_is_not_an_isolated_array_circle(attachment):
    circles,clears=source_case();q=qualify(SOURCE,circles,clears,coordinate_grid_mm=.00001)
    rows,shapes,sites=operands(circles,q)
    shapes.append(box(0,-.02,.3,.02) if attachment!='other_pad'
                  else Point(.2,0).buffer(.125,quad_segs=128))
    rows.append(dict(id='other',kind=attachment))
    got=eligible_sites(sites,rows,shapes)
    assert sites[0]['source_id']not in got
    assert sites[-1]['source_id']in got


@pytest.mark.parametrize('fault',['geometry','source_id','array_hash','policy','drawing_order'])
def test_changed_original_or_provenance_rejects(fault):
    circles,clears=source_case();q=qualify(SOURCE,circles,clears,coordinate_grid_mm=.00001)
    rows,shapes,sites=operands(circles,q);v=rows[0]['t01_bga_single']
    if fault=='geometry':sites[0]['core']=shapes[0].buffer(.000001)
    elif fault=='source_id':v['source_id']='wrong'
    elif fault=='array_hash':v['array_sha256']='wrong'
    elif fault=='policy':v['witness']['policy']['specification']['minimum_axis_sites']=2
    else:v['dark_ordinal']=0
    with pytest.raises(ValueError,match='T01_BGA_SINGLE_SOURCE_BINDING_CHANGED'):
        eligible_sites(sites,rows,shapes)


def test_bga_optional_growth_allocation_preserves_overlap_keep(monkeypatch):
    from src import t01_canonical as tc
    circles,clears=source_case();q=qualify(SOURCE,circles,clears,coordinate_grid_mm=.00001)
    rows,shapes,sites=operands(circles,q)
    # Other copper covers >70% of the first original circle, so it remains
    # exact even with valid BGA provenance. Uncovered sites may clip growth.
    covered=shapes[0].intersection(box(-1,-1,.08,1))
    rows.append(dict(id='cover',kind='gr_poly',trace_width_mm=0.,source_span=[0,0]));shapes.append(covered)
    monkeypatch.setattr(tc,'require',lambda policy:None)
    settings=tc.specification();_,a,targets,_=tc.allocate(b'',rows,shapes,sites,{},dict(reviewed_pairs=[],recess_source_ids=[]))
    assert targets[sites[0]['source_id']]==sites[0]['radius']
    assert sites[0]['source_id']in a['circle_overlap_keep_source_ids']
    assert sites[0]['source_id']not in a['bga_single_circle_growth_source_ids']
    assert sites[-1]['source_id']in a['bga_single_circle_growth_source_ids']
    assert sites[-1]['source_id']not in a['priorities_by_physical_component'].values()
    assert all(len(g['site_ids'])==1 for g in a['groups']
               if set(g['site_ids'])&set(a['bga_single_circle_growth_source_ids']))
    assert targets[sites[-1]['source_id']]<=1.5*sites[-1]['radius']


def test_bga_clips_optional_growth_while_ordinary_single_stays_round(monkeypatch):
    from src import t01_canonical as tc
    from src.crop_balanced_t01 import execute
    from src.t01_canonical_surface import SurfaceGuard
    circles,clears=source_case();q=qualify(SOURCE,circles,clears,coordinate_grid_mm=.00001)
    rows,shapes,sites=operands(circles,q);site=sites[0]
    # The original 0.045 mm gap is retained. New optional copper on this side
    # must satisfy the unchanged 0.040 mm floor; room on other sides can grow.
    rows.append(dict(id='foreign',kind='gr_poly',trace_width_mm=0.,source_span=[0,0]))
    shapes.append(box(.170,-.1,.22,.1))
    monkeypatch.setattr(tc,'require',lambda policy:None)
    settings,a,targets,square=tc.allocate(b'',rows,shapes,[site],{},dict(reviewed_pairs=[],recess_source_ids=[]))
    result=execute(b'',rows,shapes,[site],a['groups'],a['priorities_by_physical_component'],
                   settings=settings,targets=targets,square_guided_ids=square,
                   surface_guard=SurfaceGuard(rows,shapes,[site]))
    candidate=result['scene'].accepted[site['source_id']]
    assert not result['failed_patches']
    assert candidate.covers(site['core'])
    assert candidate.difference(site['core']).area>.001
    assert not candidate.equals(Point(*site['center']).buffer(targets[site['source_id']],quad_segs=128))
    # Removing only the explicit-clear array provenance restores the unchanged
    # ordinary complete-round obligation, without enlarging any source ports.
    ordinary=[{k:v for k,v in r.items()if k!='t01_bga_single'}for r in rows]
    _,a,targets,_=tc.allocate(b'',ordinary,shapes,[site],{},dict(reviewed_pairs=[],recess_source_ids=[]))
    assert site['source_id']in a['priorities_by_physical_component'].values()
    assert targets[site['source_id']]==site['radius']
