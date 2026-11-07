"""Source-model treatment never substitutes for actual new copper or coverage."""
import pytest
from shapely.geometry import box
from src.gerber_u05.exporter import treated_attachment_outcome
from src.u05_board.attachment_export import obligation_check


def test_normal_visible_treatment_keeps_its_original_positive_effect_check():
    before=box(0,0,1,1);required=box(1,.2,1.1,.4)
    actual=treated_attachment_outcome(required,required,before,[required])
    assert actual['status']=='TREATED_VERIFIED'
    assert actual['check']['effective_actual_addition_mm2']>1e-8
    assert 'native_predecessor_reconciliation'not in actual


def test_exact_native_predecessor_coverage_has_no_new_growth_credit():
    before=box(0,0,1,1);required=box(.1,.2,.3,.4);maximum=box(.05,.15,.35,.45)
    with pytest.raises(ValueError,match='ACTUAL_ATTACHMENT_NO_EFFECT'):
        obligation_check(required,before,[required])
    actual=treated_attachment_outcome(required,maximum,before,[required])
    assert actual['status']=='ALREADY_SATISFIED_VERIFIED'
    assert actual['check']['passed']
    proof=actual['native_predecessor_reconciliation']
    assert proof['exact_before_covers_complete_unclipped_maximum']
    assert not proof['buffer_used_for_classification']
    assert not proof['new_growth_credited']
    assert actual['check']['effective_actual_addition_mm2']==0


def test_covered_clipped_fragment_cannot_replace_the_complete_maximum():
    before=box(0,0,1,1);required=box(.1,.2,.3,.4);maximum=box(.1,.2,1.1,.4)
    with pytest.raises(ValueError,match='ACTUAL_ATTACHMENT_NO_EFFECT'):
        treated_attachment_outcome(required,maximum,before,[required])


def test_file_uncertainty_halo_cannot_authorize_the_classification():
    before=box(0,0,1,1);required=box(.1,.2,.3,.4);maximum=box(.1,.2,1.000001,.4)
    assert obligation_check(maximum,before,[],already=True)['passed']
    with pytest.raises(ValueError,match='ACTUAL_ATTACHMENT_NO_EFFECT'):
        treated_attachment_outcome(required,maximum,before,[required])


def test_real_but_subthreshold_growth_remains_rejected():
    # A one-grid-wide addition remains material even below the area threshold.
    before=box(0,0,1,1);required=box(1,.2,1.000001,.201)
    with pytest.raises(ValueError,match='ACTUAL_ATTACHMENT_NO_EFFECT'):
        treated_attachment_outcome(required,required,before,[required])


def test_unresolvable_source_sliver_has_identical_complete_native_material():
    before=box(0,0,1,1);required=box(1,.2,1.00000005,.5)
    assert required.area>1e-8
    actual=treated_attachment_outcome(required,required,before,[before])
    assert actual['status']=='ALREADY_SATISFIED_VERIFIED'
    proof=actual['native_predecessor_reconciliation']
    assert not proof['exact_before_covers_complete_unclipped_maximum']
    assert proof['declared_native_grid_witness']['status']=='EXACT_DECLARED_NATIVE_GRID_MATERIAL'
    assert not proof['buffer_used_for_classification']and not proof['new_growth_credited']


def test_even_a_tiny_resolvable_hole_cannot_be_declared_already_filled():
    hole=box(.5,.5,.500001,.501);maximum=box(0,0,1,1);before=maximum.difference(hole)
    required=box(.1,.2,.3,.4)
    assert obligation_check(maximum,before,[],already=True)['passed']
    with pytest.raises(ValueError,match='ACTUAL_ATTACHMENT_NO_EFFECT'):
        treated_attachment_outcome(required,maximum,before,[required])


def test_missing_required_copper_is_never_reclassified():
    before=box(0,0,1,1);required=box(1,.2,1.1,.4)
    with pytest.raises(ValueError,match='ACTUAL_ATTACHMENT_EXTENT_MISSING'):
        treated_attachment_outcome(required,required,before,[])


def test_candidate_copper_cannot_supply_an_already_satisfied_maximum():
    before=box(0,0,1,1);required=box(.1,.2,.3,.4);maximum=box(.1,.2,1.1,.4)
    # Even a region that supplies the maximum is not predecessor evidence.
    with pytest.raises(ValueError,match='ACTUAL_ATTACHMENT_NO_EFFECT'):
        treated_attachment_outcome(required,maximum,before,[maximum])
