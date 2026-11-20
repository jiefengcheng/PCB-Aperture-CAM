import pytest
from src.gerber_u05.prefix import retained_stages,operation_keys,connected_visual_evidence
from src.gerber_u05.incremental import stages_before
from src.gerber_u05 import hole_policy_prefix as transition


def test_reference_boundary_preserves_23_native_operations_and_no_connected_stage():
 assert stages_before('reference')==retained_stages(())==()
 keys=operation_keys(())
 assert len(keys)==23 and len(set(keys))==23
 assert not any(k.startswith('connected_')for k in keys)
 assert {'reference_remedy_construct','reference_remedy_1','reference_remedy_2'}<=set(keys)
 text=connected_visual_evidence(dict(reused_stages=[],retained_operation_count=23))
 assert '23'in text and 'T01, T03, T04, T02 and T05'in text


def test_t04_boundary_leaves_t02_and_t05_for_fresh_execution():
 assert stages_before('t04')==('t01','t03','t04')
 assert all(f'connected_{stage}_construct' not in operation_keys(stages_before('t04'))
            for stage in ('t02','t05'))


@pytest.mark.parametrize('boundary',['t01','bogus'])
def test_partial_connected_boundaries_still_rejected(boundary):
 with pytest.raises(ValueError,match='BOUNDARY_UNSUPPORTED'):stages_before(boundary)


def test_hole_policy_reuse_has_no_connected_geometry_at_reference_boundary():
 name='src/t04_topology.py';before,after=transition.PAIRS[name]
 assert transition.allowed_delta(name,before,after,())
 assert not transition.allowed_delta(name,before,'bad',())
 assert not transition.allowed_delta(name,before,after,('t01',))
