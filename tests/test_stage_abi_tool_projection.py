import copy
import json
from pathlib import Path
import pytest
from jsonschema import Draft202012Validator, ValidationError
from tools.export_stage_abi_tools import projection
from tests.test_stage_abi_contracts import request, CASES


def test_checked_in_tool_projection_has_all_35_real_selectors():
    document = projection()
    root = Path(__file__).resolve().parents[1]
    assert json.loads((root / 'contracts/stage_abi/v1/tool_projection.json').read_text()) == document
    assert len(document['tools']) == 35 and document['installed_tools'] is False
    assert {r['name'] for r in document['tools']} == {s + '_' + v for s, v in CASES}


@pytest.mark.parametrize('stage,verb', CASES)
def test_operation_projection_accepts_only_its_closed_request(stage, verb):
    operation = stage + '_' + verb
    tool = next(t for t in projection()['tools'] if t['name'] == operation)
    validator = Draft202012Validator(tool['input_schema'])
    value = request(stage, verb)
    validator.validate(value)
    wrong = copy.deepcopy(value)
    wrong['operation'] = 't05_inspect' if operation != 't05_inspect' else 't04_inspect'
    with pytest.raises(ValidationError):
        validator.validate(wrong)
    wrong = dict(value, arbitrary_handler='not-allowed')
    with pytest.raises(ValidationError):
        validator.validate(wrong)
