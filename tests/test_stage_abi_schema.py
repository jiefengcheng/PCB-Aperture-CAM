import json
from pathlib import Path
import pytest
from jsonschema import Draft202012Validator,ValidationError
from src.stage_abi.schema import request_schema
from tests.test_stage_abi_contracts import request,CASES
SCHEMA=request_schema();VALIDATOR=Draft202012Validator(SCHEMA)

def test_checked_in_schema_matches_source():
 assert json.loads((Path(__file__).resolve().parents[1]/'contracts/stage_abi/v1/request.schema.json').read_text())==SCHEMA
 Draft202012Validator.check_schema(SCHEMA)

@pytest.mark.parametrize('stage,verb',CASES)
def test_all_35_selectors_have_closed_machine_contract(stage,verb):VALIDATOR.validate(request(stage,verb))

@pytest.mark.parametrize('mutation',[lambda r:r.update(unknown='x'),lambda r:r['payload'].update(page_size=True),lambda r:r['payload'].update(source_ids=[]),lambda r:r.update(authorization_ref=r['scene_ref'])])
def test_schema_rejects_invalid_scope_and_selection(mutation):
 r=request('t04','inspect');mutation(r)
 with pytest.raises(ValidationError):VALIDATOR.validate(r)
