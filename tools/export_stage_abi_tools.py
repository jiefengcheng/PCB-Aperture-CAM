#!/usr/bin/env python3
"""Host-neutral operation projections; does not install or register tools."""
from pathlib import Path
import copy
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.stage_abi import ABI_VERSION
from src.stage_abi.schema import request_schema


def projection():
    schema = request_schema()
    tools = []
    for branch in schema['oneOf']:
        operation = branch['properties']['operation']['const']
        verb = operation.split('_', 1)[1]
        parameters = copy.deepcopy(branch)
        parameters['$defs'] = copy.deepcopy(schema['$defs'])
        tools.append(dict(name=operation, input_schema=parameters, local_dispatch_operation=operation, effect='New immutable local candidate/evidence; registered authority and idempotency required' if verb in ('run', 'search', 'verify') else 'Bounded local inspection/plan/comparison/recorded-review evidence; no acceptance promotion'))
    return dict(abi_version=ABI_VERSION, format='host-neutral-operation-projections/1', installed_tools=False, transport='tools/stage_agent_abi.py one JSON request/response', tools=tools)


if __name__ == '__main__':
    print(json.dumps(projection(), indent=2, sort_keys=True))
