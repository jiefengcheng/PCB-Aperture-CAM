"""Separate numerical regression: source taper noise is not new growth."""
from shapely.geometry import box,Polygon
from src import pin_separation as pin

def test_source_taper_roundoff_uses_existing_epsilon_but_real_growth_and_bridge_fail():
    left=box(0,0,1,2)
    right=Polygon([(1.1,0),(2,0),(2,2),(1.0001,2)])
    source=left.union(right).union(box(0,2,2,2.2))
    domain=box(-.1,-.1,2.1,1.999)
    spacing=box(-.1,-.1,2.1,.8)
    slot=pin.Slot('0'*64,'source-taper',('a','b'),domain,source,(left,right),spacing_domain=spacing)
    rule=pin.Rule([slot],construction_gap=.0401,finished_gap=.040)
    assert rule.check(source)['passed']
    assert rule.check(source.union(left.buffer(1e-15)))['passed']
    assert not rule.check(source.union(left.buffer(1e-8)))['passed']
    bridge=source.union(box(.9999,1.8,1.02,1.80000001))
    result=rule.check(bridge)
    assert not result['passed'] and 'PIN_BRANCH_LOCAL_BRIDGE'in result['checks'][0]['failures']
