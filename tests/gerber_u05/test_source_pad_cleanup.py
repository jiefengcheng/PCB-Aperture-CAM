import pytest
from shapely.geometry import Point,box
from shapely.ops import unary_union
from src.gerber_u05.source_pad_cleanup import trim_original_pads,apply_to_construction


def fixture(height=.11):
    circle=Point(2,height).buffer(.15,quad_segs=128)
    rows=dict(fill=dict(kind='region',metadata={}),pad=dict(kind='circle',metadata=dict(center_mm=[2,height],gerber_ordinal=7)))
    return rows,dict(fill=box(0,0,4,4),pad=circle),{}


def test_exposed_source_pad_cap_is_trimmed_but_contact_and_center_remain():
    rows,g,paths=fixture();before={s:v.wkb for s,v in g.items()}
    changes,proof=trim_original_pads(rows,g,paths,['pad'])
    assert g['fill'].covers(changes['pad'])
    assert changes['pad'].covers(Point(2,.1))
    assert changes['pad'].equals(g['pad'].intersection(g['fill']))
    assert proof['records'][0]['removed_area_mm2']>0
    assert proof['records'][0]['added_area_mm2']==0
    assert proof['records'][0]['original_contacts_preserved']
    assert before=={s:v.wkb for s,v in g.items()}


def test_larger_source_cap_is_kept_for_review_under_ten_percent_rule():
    rows,g,paths=fixture(height=.1)
    assert g['pad'].difference(g['fill']).area/g['pad'].area>.1
    with pytest.raises(ValueError,match='NOT_BELOW_NOISE_AREA_LIMIT'):
        trim_original_pads(rows,g,paths,['pad'])


def test_contact_to_trace_outside_fill_cannot_be_trimmed():
    rows,g,paths=fixture();rows['trace']=dict(kind='stroke',metadata={})
    g['trace']=box(1.98,-1,2.02,.05);paths['r']=['trace']
    changes,_=trim_original_pads(rows,g,paths,['pad'])
    assert changes['pad'].covers(g['pad'].intersection(g['trace']))
    assert changes['pad'].difference(g['fill']).area>0


def test_duplicate_pad_cannot_hide_the_cap_or_be_left_unchanged():
    rows,g,paths=fixture();rows['alias']=rows['pad'];g['alias']=g['pad']
    with pytest.raises(ValueError,match='ALL_PAD_ALIASES'):
        trim_original_pads(rows,g,paths,['pad'])
    changes,_=trim_original_pads(rows,g,paths,['pad','alias'])
    assert changes['pad'].equals(changes['alias'])
    assert changes['pad'].area<g['pad'].area


def test_ordinary_pad_on_trace_is_not_mistaken_for_a_fill_pad():
    rows,g,paths=fixture();g['pad']=Point(5,.1).buffer(.15)
    rows['pad']['metadata']['center_mm']=[5,.1]
    rows['trace']=dict(kind='stroke',metadata={});g['trace']=box(3,.075,5,.125);paths['r']=['trace']
    with pytest.raises(ValueError,match='CENTER_NOT_INSIDE_BROAD'):
        trim_original_pads(rows,g,paths,['pad'])


def test_no_fill_or_missing_target_rejects():
    rows,g,paths=fixture()
    with pytest.raises(ValueError,match='TARGETS_REQUIRED'):trim_original_pads(rows,g,paths,[])
    with pytest.raises(ValueError,match='TARGETS_REQUIRED'):trim_original_pads(rows,g,paths,['foreign'])
    with pytest.raises(ValueError,match='PLOTTED_FILL_REQUIRED'):
        trim_original_pads({'pad':rows['pad']},{'pad':g['pad']},{},['pad'])


def test_actual_constructed_trace_contact_is_retained_and_unselected_bytes_stay_exact():
    from shapely import from_wkb
    rows,g,paths=fixture();rows['trace']=dict(kind='stroke',metadata={})
    g['trace']=box(1.99,-1,2.01,-.2);paths['r']=['trace']
    grown=box(1.98,-1,2.02,.02)
    stage=dict(input_binding=dict(context='original',accepted_t03=False),
        trace_eligibility_policy=dict(complete_native_route_inventory=paths),
        hybrid_components=dict(continuous_source_bodies={'trace':dict(wkb_hex=grown.wkb.hex())},changed_bulk_copper={}))
    trace_bytes=stage['hybrid_components']['continuous_source_bodies']['trace']['wkb_hex']
    proof=apply_to_construction(rows,g,g,stage,['pad'])
    pad=from_wkb(bytes.fromhex(stage['hybrid_components']['continuous_source_bodies']['pad']['wkb_hex']))
    assert pad.intersection(grown).area>0
    assert stage['hybrid_components']['continuous_source_bodies']['trace']['wkb_hex']==trace_bytes
    assert proof['physical_component_count_preserved']and proof['material_added_mm2']==0
    assert proof['unselected_source_bytes_preserved']


def test_trimming_a_pad_bridge_between_trace_and_fill_is_rejected():
    rows,g,paths=fixture();rows['trace']=dict(kind='stroke',metadata={})
    g['trace']=box(1.98,-1,2.02,-.02);paths['r']=['trace']
    with pytest.raises(ValueError,match='CONNECTED_CENTER'):
        trim_original_pads(rows,g,paths,['pad'])


def test_pad_cleanup_rejects_retained_t03_context_and_previously_grown_pad():
    rows,g,paths=fixture()
    stage=dict(input_binding=dict(context='retained_t03',accepted_t03=True))
    with pytest.raises(ValueError,match='DIRECTLY_ON_SOURCE'):
        apply_to_construction(rows,g,g,stage,['pad'])
    stage=dict(input_binding=dict(context='original',accepted_t03=False),
        hybrid_components=dict(continuous_source_bodies={'pad':dict(wkb_hex=g['pad'].buffer(.01).wkb.hex())},changed_bulk_copper={}))
    with pytest.raises(ValueError,match='UNMODIFIED_SOURCE_PAD'):
        apply_to_construction(rows,g,g,stage,['pad'])
