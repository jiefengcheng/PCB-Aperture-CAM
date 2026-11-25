"""Job-bound angle authority for subtractive T04 boundary transitions."""
import json
import math
from pathlib import Path

REGISTRY=Path(__file__).resolve().parents[1]/'contracts/t04/transitions.json'


def decode(raw):
    from src.t04_settings import _decode
    v=_decode(raw)
    keys={'schema','revision','maximum_transition_angle_degrees','copper_policy'}
    if (type(v)is not dict or not keys<=set(v)or type(v.get('revision'))is not int or
            (v['revision']==1 and set(v)!=keys)or
            (v['revision']in(2,3) and (set(v)!=keys|{'terminal_owner'}or v['terminal_owner']!='T05_SOURCE_LAND_WINDOW'))or
            (v['revision']==4 and(set(v)!=keys|{'terminal_owner','repair_principle'}or
                v['terminal_owner']!='T05_SOURCE_LAND_WINDOW'or v['repair_principle']!='FLEXIBLE_ENDS_PRIMARY'))or
            v['schema']!='pcb-t04-boundary-transitions/1'or v['revision']not in(1,2,3,4)or
            v['copper_policy']!=('BRIDGE_GAPS_WITH_NO_NET_GROWTH_LOSS'if v['revision']>=3 else'SUBTRACT_OPTIONAL_GROWTH_ONLY')or
            type(v['maximum_transition_angle_degrees'])not in(int,float)or
            not math.isfinite(v['maximum_transition_angle_degrees'])or
            not 0<v['maximum_transition_angle_degrees']<45):
        raise ValueError('INVALID_T04_BOUNDARY_TRANSITION_POLICY')
    return v


def capture():
    raw=REGISTRY.read_bytes();decode(raw);return raw
