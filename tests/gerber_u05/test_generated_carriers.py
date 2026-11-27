import json
from pathlib import Path

import pytest
from shapely import from_wkb
from shapely.geometry import MultiPolygon,box

from src.gerber_u05.boundary_finish import component_count
from src.gerber_u05.native_contact_support import retain_generated_carriers,contribution_count,assemble


CASES=json.loads((Path(__file__).parent/'fixtures/l35_generated_carriers.json').read_text())


@pytest.mark.parametrize('case',CASES,ids=lambda case:case['route_id'])
def test_exact_failed_routes_keep_original_and_all_attached_widening(case):
    floors={r['source']:from_wkb(bytes.fromhex(r['floor_wkb_hex']))for r in case['sources']}
    bodies={r['source']:from_wkb(bytes.fromhex(r['body_wkb_hex']))for r in case['sources']}
    baseline=from_wkb(bytes.fromhex(case['baseline_wkb_hex']))
    assembled=from_wkb(bytes.fromhex(case['assembled_wkb_hex']))
    updates,result,proof=retain_generated_carriers(list(bodies),bodies,{},floors,baseline,assembled)
    assert component_count(assembled)>1
    assert proof['passed'] and component_count(result)==1
    assert proof['original_positive_copper_removed_mm2']==0
    assert proof['attached_widening_removed_mm2']==0
    assert proof['net_gain_over_entry_mm2']>0
    attached=max(assembled.geoms,key=lambda g:g.area)
    assert attached.difference(result).area==0
    for source,after in updates.items():
        before=bodies[source]
        original_faces={part.wkb for part in before.geoms}
        kept=[after]if after.geom_type=='Polygon'else list(after.geoms)
        assert all(part.wkb in original_faces for part in kept)
        removed=[part for part in before.geoms if part.wkb not in {g.wkb for g in kept}]
        assert all(part.intersection(floors[source]).area==0 for part in removed)


def test_real_source_gap_remains_a_failure():
    floor=box(0,0,3,1)
    body=MultiPolygon([box(0,0,1,1),box(2,0,3,1)])
    updates,result,proof=retain_generated_carriers(['s'],{'s':body},{},{'s':floor},floor,body)
    assert not updates and proof is None
    assert result is body and component_count(result)==2


def test_disjoint_original_island_is_retained():
    floor=MultiPolygon([box(0,0,1,1),box(3,0,4,1)])
    body=MultiPolygon([box(0,0,1.1,1),box(3,0,4.1,1),box(6,0,6.1,.1)])
    updates,result,proof=retain_generated_carriers(['s'],{'s':body},{},{'s':floor},floor,body)
    assert proof['passed'] and component_count(result)==2
    assert result.covers(floor)
    assert proof['discarded_generated_faces']==1


def test_native_union_hides_detached_face_that_owner_union_retains():
    """The real final-board failure must be found at native route custody."""
    from shapely.ops import unary_union
    case=json.loads((Path(__file__).parent/'fixtures/l35_owner_contacts.json').read_text())
    floors={r['source']:from_wkb(bytes.fromhex(r['floor_wkb_hex']))for r in case['sources']}
    bodies={r['source']:from_wkb(bytes.fromhex(r['body_wkb_hex']))for r in case['sources']}
    sources=case['paths']['JR-17c54c64fdc6822d']
    baseline=unary_union([floors[s]for s in sources]);joined=assemble(sources,bodies,{})
    assert component_count(joined)==1
    assert contribution_count(sources,bodies,{})==2
    assert component_count(unary_union(list(bodies.values())))==2
    updates,result,proof=retain_generated_carriers(sources,bodies,{},floors,baseline,joined)
    assert proof['passed'] and proof['discarded_generated_faces']==1
    assert proof['attached_copper_proof']=='UNCHANGED_COMPLETE_FINITE_CONTACT_GROUPS'
    bodies.update(updates)
    assert contribution_count(bodies,bodies,{})==1
    assert component_count(unary_union(list(bodies.values())))==1
    assert result.area>=baseline.area


def test_interface_edit_contact_refresh_rejects_only_detached_generated_faces():
    case=json.loads((Path(__file__).parent/'fixtures/l35_interface_contacts.json').read_text())
    floors={r['source']:from_wkb(bytes.fromhex(r['floor_wkb_hex']))for r in case['sources']}
    bodies={r['source']:from_wkb(bytes.fromhex(r['body_wkb_hex']))for r in case['sources']}
    baseline=from_wkb(bytes.fromhex(case['baseline_wkb_hex']))
    joined=from_wkb(bytes.fromhex(case['assembled_wkb_hex']))
    assert contribution_count(bodies,bodies,{})==3
    updates,result,proof=retain_generated_carriers(list(bodies),bodies,{},floors,baseline,joined)
    assert proof['passed'] and proof['discarded_generated_faces']==2
    assert proof['original_positive_copper_removed_mm2']==0
    assert proof['attached_widening_removed_mm2']==0
    bodies.update(updates)
    assert contribution_count(bodies,bodies,{})==1
    assert result.area>=baseline.area


@pytest.mark.parametrize('second,count',[(box(.5,0,2,1),1),(box(1,0,2,1),1),
    (box(1,1,2,2),1),(box(1.000001,0,2,1),2)])
def test_independent_source_faces_use_exact_contacts(second,count):
    assert contribution_count(['a','b'],{'a':box(0,0,1,1),'b':second},{})==count


def test_holes_are_not_filled_by_contact_counting():
    from shapely.geometry import Polygon
    ring=Polygon([(0,0),(4,0),(4,4),(0,4)],holes=[[(1,1),(3,1),(3,3),(1,3)]])
    assert contribution_count(['ring','island'],{'ring':ring,'island':box(1.5,1.5,2.5,2.5)},{})==2
    assert contribution_count(['ring','touch'],{'ring':ring,'touch':box(1,1.5,2,2.5)},{})==1


def test_invalid_source_is_not_repaired_by_contact_counting():
    invalid=MultiPolygon([box(0,0,2,2),box(1,0,3,2)])
    with pytest.raises(ValueError,match='VALID_FILLED_SOURCE_REQUIRED'):
        contribution_count(['bad'],{'bad':invalid},{})
