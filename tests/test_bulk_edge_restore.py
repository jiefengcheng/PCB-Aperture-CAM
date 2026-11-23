import pytest
from shapely.geometry import box,Point
from src.bulk_edge_restore import fit_straight_flanks,propose


def fitted(domain):
    return fit_straight_flanks([(-.2,0),(-.1,0)],[(.1,0),(.2,0)],(0,-.1),domain)


def test_full_bump_is_removed_to_supported_edge():
    base=box(-1,-1,1,0);material=base.union(Point(0,-.01).buffer(.06))
    window=box(-.1,-.1,.1,.1);reference,evidence=fitted(window)
    after,cut,add,proof=propose(material,reference,window,reference_evidence=evidence)
    assert proof['passed'] and after.equals(base) and cut.area>0 and add.is_empty
    assert material.hausdorff_distance(after)>.03  # Explicit full-feature exception.


def test_recess_is_filled_to_supported_edge():
    base=box(-1,-1,1,0);material=base.difference(Point(0,0).buffer(.03))
    window=box(-.1,-.1,.1,.1);reference,evidence=fitted(window)
    after,cut,add,proof=propose(material,reference,window,reference_evidence=evidence)
    assert proof['passed'] and after.equals(base) and cut.is_empty and add.area>0


def test_fill_cannot_bridge_a_foreign_conductor():
    base=box(-1,-1,1,0);window=box(-.1,-.1,.1,.1)
    material=base.difference(box(-.02,-.06,.02,.1));reference,evidence=fitted(window)
    proof=propose(material,reference,window,foreign=[('trace',box(-.01,-.04,.01,-.01))],reference_evidence=evidence)[3]
    assert 'ADDED_COPPER_CLEARANCE:trace' in proof['failures']


def test_declared_protected_recess_remains_unfilled():
    window=box(-.1,-.1,.1,.1);slot=box(-.02,-.06,.02,.1)
    reference,evidence=fitted(window)
    proof=propose(box(-1,-1,1,0).difference(slot),reference,window,protected=[('pin_slot',slot)],reference_evidence=evidence)[3]
    assert 'PROTECTED_FEATURE_CHANGED:pin_slot' in proof['failures']


def test_bump_attachment_cannot_be_severed():
    base=box(-1,-1,1,0);window=box(-.1,-.1,.1,.1)
    material=base.union(Point(0,-.01).buffer(.06));reference,evidence=fitted(window)
    proof=propose(material,reference,window,contacts=[('wire',box(-.01,.035,.01,.045))],reference_evidence=evidence)[3]
    assert 'CONTACT_LOST:wire' in proof['failures']


def test_ambiguous_or_curved_flanks_reject():
    with pytest.raises(ValueError,match='AMBIGUOUS'):
        fit_straight_flanks([(-.2,0),(-.1,0)],[(.1,.02),(.2,0)],(0,-.1),box(-1,-1,1,1))


def test_unknown_reference_and_removing_whole_component_reject():
    base=box(-1,-1,1,0)
    with pytest.raises(ValueError,match='REFERENCE_EVIDENCE'):
        propose(base,base,base)
    proof=propose(base,box(2,2,3,3),base,reference_evidence={'fixture':'empty target'},smooth_edge=base.boundary)[3]
    assert 'CONNECTED_COMPONENT_OR_HOLE_TOPOLOGY_CHANGED' in proof['failures']


@pytest.mark.parametrize('depth,passed',[(.099,True),(.100,True),(.101,False)])
@pytest.mark.parametrize('recess',[False,True])
def test_shared_100um_limit_for_both_directions(depth,passed,recess):
    base=box(-1,-1,1,0);feature=box(-.02,-depth,.02,depth)
    material=base.difference(feature) if recess else base.union(feature)
    window=box(-.2,-.2,.2,.2);reference,evidence=fitted(window)
    proof=propose(material,reference,window,reference_evidence=evidence)[3]
    assert proof['passed'] == passed
    assert proof['policy']['maximum_depth_mm'] == .100


def test_adjustment_is_captured_and_does_not_change_global_default(tmp_path):
    from src.edge_restoration_settings import capture
    import json
    path=tmp_path/'settings.json'
    data={'schema':'pcb-edge-restoration-settings/1','status':'PROVISIONAL','maximum_depth_mm':.050}
    path.write_text(json.dumps(data));policy=capture(path)
    data['maximum_depth_mm']=.025;path.write_text(json.dumps(data))
    assert policy.maximum_depth_mm==.050 and capture(path).maximum_depth_mm==.025
    assert capture().maximum_depth_mm==.100
    window=box(-.2,-.2,.2,.2);reference,evidence=fitted(window)
    material=box(-1,-1,1,0).union(box(-.02,0,.02,.075))
    assert not propose(material,reference,window,reference_evidence=evidence,policy=policy)[3]['passed']


@pytest.mark.parametrize('value',[0,-1,float('nan'),float('inf'),True,'0.1'])
def test_invalid_setting_rejects(value):
    from src.edge_restoration_settings import EdgeRestorationPolicy
    with pytest.raises(ValueError,match='INVALID_EDGE_RESTORATION_DEPTH'):
        EdgeRestorationPolicy(value,'test')
