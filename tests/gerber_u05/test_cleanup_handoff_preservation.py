import pytest
from shapely.geometry import box
from tools.run_t04_after_cleanup import verify_preserved_contributions


def test_eligible_growth_may_enter_trimmed_space_without_changing_fixed_copper():
    before={'fill':box(0,0,1,1),'trace':box(1,.4,2,.5)}
    after=dict(before,trace=box(1,.4,2,.55))
    proof=verify_preserved_contributions(before,after,{'fill'},set(),{'trace'},box(1,.5,1.1,.6))
    assert proof['passed'] and proof['fixed_occurrences_byte_preserved']==1
    assert proof['eligible_growth_reentry_mm2']==pytest.approx(.005)


def test_preservation_rejects_changes_to_the_cleaned_fixed_object():
    before={'fill':box(0,0,1,1)}
    with pytest.raises(ValueError,match='FIXED_CLEANUP_CONTRIBUTION_CHANGED'):
        verify_preserved_contributions(before,{'fill':box(0,0,1,1.1)},{'fill'},set(),set(),box(0,1,1,1.1))


def test_restoration_by_an_unadmitted_contribution_still_fails():
    before={'trace':box(0,0,1,.1)}
    with pytest.raises(ValueError,match='UNADMITTED_CONTRIBUTION_CHANGED'):
        verify_preserved_contributions(before,{'trace':box(0,0,1,.2)},set(),set(),set(),box(0,.1,1,.2))


def test_byte_scope_proof_needs_no_geometry_search_or_removal_mask():
    before={'fill':box(0,0,1,1),'trace':box(1,.4,2,.5)}
    proof=verify_preserved_contributions(before,dict(before,trace=box(1,.4,2,.55)),{'fill'},set(),{'trace'})
    assert proof['passed']and proof['all_changes_admitted']and proof['changed_occurrences']==1
    assert proof['eligible_growth_reentry_mm2']is None and proof['reentry_measurement']=='NOT_RUN_INFORMATIONAL_ONLY'
    with pytest.raises(ValueError,match='UNADMITTED_CONTRIBUTION_CHANGED'):
        verify_preserved_contributions(before,dict(before,trace=box(1,.4,2,.55)),{'fill'},set(),set())
