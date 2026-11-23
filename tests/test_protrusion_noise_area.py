import pytest
from shapely.geometry import box
from src.edge_restoration_settings import capture, classify_protrusion, EdgeRestorationPolicy


@pytest.mark.parametrize('area,noise',[(.099999,True),(.1,False),(.100001,False),(0,False)])
def test_ten_percent_is_a_strict_original_feature_area_cutoff(area,noise):
    p=box(0,0,area,1)if area else box(0,0,1,1).difference(box(0,0,1,1))
    result=classify_protrusion(p,box(0,0,1,1),source_id='original-pad')
    assert result['is_noise']==noise
    assert result['original_feature_area_mm2']==1
    assert result['policy']['noise_area_basis']=='ORIGINAL_CAUSING_PAD_OR_TRACE'


def test_big_connected_fill_cannot_replace_the_causing_feature():
    with pytest.raises(ValueError,match='OUTSIDE_CAUSING'):
        classify_protrusion(box(1,0,2,1),box(0,0,1,1),source_id='pad')


@pytest.mark.parametrize('fraction',[0,1,-.1,float('nan'),True,'0.1'])
def test_invalid_fraction_is_rejected(fraction):
    with pytest.raises(ValueError,match='NOISE_AREA'):
        EdgeRestorationPolicy(.1,'test',fraction)


def test_captured_rule_cannot_drift_with_registry_change(tmp_path):
    import json
    p=tmp_path/'policy.json'
    value=dict(schema='pcb-edge-restoration-settings/2',status='PROVISIONAL',maximum_depth_mm=.1,
               maximum_noise_area_fraction=.1,noise_area_basis='ORIGINAL_CAUSING_PAD_OR_TRACE')
    p.write_text(json.dumps(value));saved=capture(p)
    value['maximum_noise_area_fraction']=.05;p.write_text(json.dumps(value))
    bump=box(0,0,.075,1);pad=box(0,0,1,1)
    assert classify_protrusion(bump,pad,source_id='pad',policy=saved)['is_noise']
    assert not classify_protrusion(bump,pad,source_id='pad',policy=capture(p))['is_noise']
