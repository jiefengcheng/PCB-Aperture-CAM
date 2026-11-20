import pytest
from shapely.geometry import LineString
from src.gerber_u05.corner_transition import offsets
from src.gerber_u05.smooth_transition import value


def legacy(desc,t,endpoint):
    length=LineString(desc['points']).length;at=t if endpoint==0 else length-t
    fields=desc.get('fields')
    if fields:
        piece=next((p for p in fields if at<=p['last_mm']+1e-12),fields[-1])
        u=min(1.,max(0.,(at-piece['first_mm'])/(piece['last_mm']-piece['first_mm'])))
        low,high=[value(c,u) for c in piece['controls']]
    else:low,high=desc['offsets_mm']
    return (low,high) if endpoint==0 else (-high,-low)


@pytest.mark.parametrize('endpoint',[0,1])
@pytest.mark.parametrize('fields',[False,True])
def test_prepared_length_keeps_exact_offset_float_bits(endpoint,fields):
    desc={'points':[[0.,0.],[.1,.3],[.21,.37],[.7,.9]],'offsets_mm':[-.03,.06]}
    length=LineString(desc['points']).length
    if fields:desc['fields']=[{'first_mm':0.,'last_mm':length,'controls':[[-.03,-.03,-.04,-.04],[.04,.04,.06,.06]]}]
    for t in (0.,.01,length/3,length):
        expected=legacy(desc,t,endpoint)
        assert [v.hex() for v in offsets(desc,t,endpoint)]==[v.hex() for v in expected]
        assert [v.hex() for v in offsets(desc,t,endpoint,length_mm=length)]==[v.hex() for v in expected]
