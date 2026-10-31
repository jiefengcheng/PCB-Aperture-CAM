import copy,json
from pathlib import Path
import pytest
from src.stage_abi.responses import response_schema,validate_response
from src.stage_abi.contracts import StageABIError
from tests.test_stage_abi_service import environment


def test_checked_response_schema_matches_source():
 root=Path(__file__).resolve().parents[1];assert json.loads((root/'contracts/stage_abi/v1/response.schema.json').read_text())==response_schema()

def test_operation_specific_response_shape_and_extra_fields_reject(tmp_path):
 _,service,_,req,_,_=environment(tmp_path);r=service.dispatch(req('describe',dict(requested_contract_version=None)));validate_response(r)
 for bad in [dict(r,unexpected=True),dict(r,result={'status':'AVAILABLE'}),dict(r,error={'code':'X','message':'bad'})]:
  with pytest.raises(StageABIError):validate_response(bad)

def test_invalid_request_identifiers_still_get_valid_rejection(tmp_path):
 _,service,_,req,_,_=environment(tmp_path);r=req('describe',dict(requested_contract_version=None));r['request_id']={'not':'a string'};r['operation']=['also invalid'];response=service.dispatch(r);validate_response(response);assert response['status']=='REJECTED' and response['request_id'] is None and response['operation'] is None

def test_backend_cannot_expose_a_malformed_public_response(tmp_path,monkeypatch):
 _,service,_,req,_,_=environment(tmp_path);monkeypatch.setattr(service,'_describe',lambda *a:{'bad':'response'});r=service.dispatch(req('describe',dict(requested_contract_version=None)));assert r['status']=='REJECTED' and r['error']['code']=='INTERNAL_RESPONSE_INVALID'
