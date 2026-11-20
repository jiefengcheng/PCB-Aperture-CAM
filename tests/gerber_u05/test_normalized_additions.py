from shapely.geometry import box
from src.gerber_u05.normalized_additions import verify
from src.native_inventory import ERROR_MM
from src.trace_width_clearance import TraceWidthContract


def test_normalization_removes_noise_without_a_false_core_preservation_claim():
    core=box(0,0,1,.05).union(box(.4,-.000001,.6,0))
    actual=box(0,0,1,.06)
    report=verify(core,actual,[dict(id='foreign',geometry=box(0,.11,1,.2))])
    assert report['passed']and report['removed_area_mm2']>0
    assert report['constructed_groups_audited']==0


def test_new_bridge_cannot_hide_behind_another_candidate_or_port_exemption():
    core=box(0,0,1,.05);actual=box(0,0,1,.07)
    report=verify(core,actual,[dict(id='foreign',geometry=box(0,.10,1,.2))])
    assert not report['passed']
    assert report['failures'][0]['reason']=='NEW_EXPOSED_COPPER_BELOW_CONSTRUCTION_GUARD'


def test_unchanged_old_close_copper_is_not_a_new_addition():
    core=box(0,0,1,.05)
    assert verify(core,core,[dict(id='foreign',geometry=box(0,.06,1,.2))])['passed']


def test_default_envelope_has_the_unchanged_error_margin():
    core=box(0,0,1,.05);actual=box(0,0,1,.06)
    guard=TraceWidthContract().construction_gap_mm
    foreign=box(0,.06+guard+ERROR_MM/2,1,.2)
    assert not verify(core,actual,[dict(id='foreign',geometry=foreign)])['passed']
