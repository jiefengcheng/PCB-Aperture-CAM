"""C03 selection isolation, policy tampering and physical clearance controls."""
import copy
import json
from pathlib import Path

import pytest
from shapely.geometry import Point, box

from src.c03_input_family import selected, specification, visible_model
from src.c03_recovery import SOURCE_SHA256, CROP_SHA256
from src.c03_round_adapter import compile_policy, english, validate_policy, STRATEGY
from src.c03_round_service import validator
from src.stage_abi.contracts import StageABIError
from src.t01_crop.protocol import request_schema


def reference():
    return dict(artifact_id='a'*64,sha256='a'*64)


def test_matching_source_never_implicitly_selects_family(tmp_path):
    root=tmp_path/'native';root.mkdir()
    (tmp_path/'job.json').write_text(json.dumps(dict(inputs=dict(kicad=dict(sha256=SOURCE_SHA256)),
        crop=dict(sha256=CROP_SHA256))))
    assert selected(root) is False
    spec,_,sha=specification()
    (root/'C03_INPUT_FAMILY.json').write_text(json.dumps(dict(
        schema='c03-input-family-selected/1',contract=spec,contract_sha256=sha)))
    assert selected(root) is True
    (tmp_path/'job.json').write_text(json.dumps(dict(inputs=dict(kicad=dict(sha256=SOURCE_SHA256)),crop=None)))
    with pytest.raises(ValueError,match='JOB_SOURCE_OR_CROP_CHANGED'):
        selected(root)


def test_dangling_marker_cannot_fall_back_to_generic(tmp_path):
    (tmp_path/'C03_INPUT_FAMILY.json').symlink_to(tmp_path/'absent')
    with pytest.raises(ValueError,match='MARKER_UNSAFE'):
        selected(tmp_path)


def test_changed_marker_rejects(tmp_path):
    (tmp_path/'C03_INPUT_FAMILY.json').write_text('{}')
    with pytest.raises(ValueError,match='SELECTION_CHANGED'):
        selected(tmp_path)


@pytest.mark.parametrize('fault',['gap','construction_gap','blocked','source','classes'])
def test_compiled_policy_rejects_semantic_tampering(fault):
    policy=compile_policy(english(),reference(),reference())
    if fault=='gap':policy['settings']['hard_gap']=.001
    elif fault=='construction_gap':policy['surface_contract']['construction_gap_mm']=.001
    elif fault=='blocked':policy['c03_input_contract']['intent_profile']['sha256']='0'*64
    elif fault=='source':policy['c03_input_contract']['source_sha256']='0'*64
    else:policy['diameter_classes_mm'].append(100.)
    with pytest.raises(StageABIError) as error:
        validate_policy(policy)
    assert error.value.code=='T01_CONTRACT_DERIVATION_MISMATCH'


def test_negative_english_does_not_compile():
    with pytest.raises(StageABIError) as error:
        compile_policy(english().replace('hard gap 0.020 mm','hard gap 0.001 mm'),reference(),reference())
    assert error.value.code=='T01_ENGLISH_UNSUPPORTED'


def test_closed_strategy_does_not_mutate_generic_wire():
    def strategy(schema):
        return next(b for b in schema['oneOf'] if b['properties']['operation'].get('const')=='t01_plan')['properties']['payload']['properties']['strategy']
    before=copy.deepcopy(request_schema())
    assert strategy(validator('request').schema)==dict(const=STRATEGY)
    assert request_schema()==before
    assert strategy(before)!=dict(const=STRATEGY)


def test_new_family_keeps_physical_clearance_failure():
    original=Point(0,0).buffer(.1,quad_segs=128)
    grown=Point(0,0).buffer(.15,quad_segs=128)
    site=dict(source_id='circle',aliases=['circle'])
    rows=[dict(id='circle',trace_width_mm=0.),dict(id='foreign',trace_width_mm=.05)]
    good=box(.25,-.02,.35,.02)
    bad=box(.155,-.02,.3,.02)
    def check(obstacle):
        return visible_model(rows,dict(circle=original,foreign=obstacle),
                             dict(circle=grown,foreign=obstacle),[site])
    assert check(good)['passed']
    assert check(bad)['passed'] is False


def test_route_class_preserves_machine_audit_method_resolution():
    from tools.c03_recovery_route import MachineRoute
    from tools.u04_board_route import MachineRoute as U04MachineRoute
    assert issubclass(MachineRoute,U04MachineRoute)
    assert MachineRoute._audit is U04MachineRoute._audit


def test_actual_export_requires_dark_copper_and_additional_control():
    from types import SimpleNamespace
    from src.c03_native_export import require_positive_copper
    from src.u04_board.export import required_export_controls
    dark=SimpleNamespace(objects=[SimpleNamespace(polarity_dark=True)])
    clear=SimpleNamespace(objects=[SimpleNamespace(polarity_dark=False)])
    require_positive_copper(dark)
    with pytest.raises(ValueError,match='C03_FCU_CLEAR_POLARITY_UNSUPPORTED'):
        require_positive_copper(dark,clear)
    measured=dict(changed_native_trace_parts=0,targets=[dict(growing=True)],rectangle_parts=1,inclusive_parts=1)
    original=required_export_controls(measured)
    assert len(original)==5 and 'clear_polarity' not in original
    measured['c03_positive_copper_required']=True
    assert required_export_controls(measured)==dict(original,clear_polarity='C03_FCU_CLEAR_POLARITY_UNSUPPORTED')


def test_complete_contact_ledgers_remain_bound_without_oversizing_audit_mailbox(tmp_path):
    from src.c03_retain_paths import C03RetainPathsAdapter
    from src.stage_abi.store import ArtifactStore,canonical,digest
    from tools.t01_route_client import encode
    from tools.t01_macos_adapter import MAX_BYTES
    adapter=C03RetainPathsAdapter.__new__(C03RetainPathsAdapter)
    adapter.out=tmp_path/'t03';adapter.store=ArtifactStore(tmp_path/'runtime');adapter.binding=dict(test='source-bound')
    rows=[dict(source_id=str(i),pairs=[]) for i in range(153)]
    coverage=dict(source_objects=17849,site_occurrences=154,canonical_sites=153,source_pages=179,
        port_pages=2,source_sha256='a'*64,input_contact_family='c03-exact-round-visible-contact/1',
        input_contract_sha256='b'*64,full_visible_surface_check_sha256='c'*64,
        retained_generic_source_port_failures=[dict(passed=False,evidence='x'*100) for _ in range(49)],
        original_obligations=dict(original_full_coverage_pass=False,blocked_original_positive=1,
            records=[dict(source_id=str(i),evidence='x'*1000) for i in range(153)]))
    adapter.assess=lambda:(rows,coverage)
    result=adapter.inspect()
    assert len(encode(coverage))>MAX_BYTES
    assert len(encode(dict(audit=dict(observed=result['facts']))))<MAX_BYTES
    assert result['coverage']==coverage
    assert result['facts']['complete_coverage_sha256']==digest(canonical(coverage))
    assert result['facts']['retained_generic_failure_pairs']==49
    assert json.loads((adapter.out/'t03_inspect.json').read_bytes())==result
