"""Rounded qualified trace ends must remain real, immutable gap boundaries."""
import pytest
from shapely import from_wkb, set_precision
from shapely.geometry import LineString, box
from shapely.affinity import scale, rotate
from shapely.ops import unary_union
from src import t02_shared_gaps as gaps
from src.shared_gap_projection import complete_parts
from test_t02_shared_gaps import fixture, contexts


def curved_entry(tmp_path, rotation=False):
 original,scene,store=fixture(tmp_path)
 path=LineString([(2.05,.5),(2.5,.8)])
 original['joint']=path.buffer(.05,quad_segs=128)
 scene['objects'].append(dict(source_id='joint',kind='trace',metadata={}))
 current=dict(original,joint=path.buffer(.065,quad_segs=128))
 if rotation:
  original={s:rotate(g,90,origin=(0,0))for s,g in original.items()}
  current={s:rotate(g,90,origin=(0,0))for s,g in current.items()}
 spec=gaps.records(scene,original,current)
 proposed={s:scale(original[s],1.1,1.1,origin=original[s].centroid)for s in('a','b')}
 return original,current,spec,proposed


@pytest.mark.parametrize('rotation',[False,True])
def test_real_curved_entry_uses_whole_span_minimum_spacing_and_keeps_all_copper(tmp_path,rotation):
 original,current,spec,proposed=curved_entry(tmp_path,rotation)
 wall=[w for w in spec['entry_walls']if w.get('maximum_intrusion_mm',0)>0]
 assert len(wall)==1 and wall[0]['maximum_intrusion_mm']==pytest.approx(.015,abs=1e-6)
 result,proof=gaps.project(spec,original,current,proposed)
 parts=list(dict(current,**result).values());whole=unary_union(parts)
 assert gaps.complete(proof,whole)['passed']
 assert complete_parts(proof,parts)['passed']
 assert len(proof['zones'])==2
 assert max(z['gap_mm']for z in proof['zones'])-min(z['gap_mm']for z in proof['zones'])<gaps.EPS
 for s,g in result.items():
  assert g.covers(current[s])and g.difference(proposed[s]).area<=gaps.EPS
 assert unary_union(list(current.values())).difference(whole).area<=gaps.EPS
 assert gaps.frozen(spec,dict(current,**result))['zones']==proof['zones']
 assert gaps.complete(proof,set_precision(whole,1e-6),tolerance_mm=2e-6)['passed']


def test_curved_entry_does_not_allow_new_copper_between_envelope_and_actual_wall(tmp_path):
 original,current,spec,proposed=curved_entry(tmp_path)
 result,proof=gaps.project(spec,original,current,proposed)
 whole=unary_union(list(dict(current,**result).values()))
 # Behind the closest-point envelope, but in an originally empty part of the
 # complete protected corridor: retaining an old bulge grants no fresh budget.
 bad=box(1.99,.1,2.001,.2)
 assert not gaps.check(proof,bad)['passed']
 assert not gaps.fill_check(dict(shared_neighbor_gaps=spec),dict(current,**result),bad)['passed']
 with pytest.raises(ValueError,match='UNIFORMITY'):gaps.complete(proof,whole.union(bad))


def test_curved_entry_complete_middle_boundary_cannot_be_removed(tmp_path):
 original,current,spec,proposed=curved_entry(tmp_path)
 result,proof=gaps.project(spec,original,current,proposed)
 whole=unary_union(list(dict(current,**result).values()))
 with pytest.raises(ValueError,match='UNIFORMITY'):
  gaps.complete(proof,whole.difference(box(1.98,.49,2.001,.51)))


def test_curved_compensation_cannot_exceed_offered_growth_or_change_a_keep(tmp_path):
 original,current,spec,proposed=curved_entry(tmp_path)
 before={s:g.wkb for s,g in current.items()}
 with pytest.raises(ValueError,match='COMPENSATION_INFEASIBLE'):
  gaps.project(spec,original,current,dict(a=original['a'],b=original['b']))
 assert {s:g.wkb for s,g in current.items()}==before


def test_curved_gap_proof_keeps_exact_footprint_not_a_tolerance_buffer(tmp_path):
 original,current,spec,proposed=curved_entry(tmp_path)
 wall=next(w for w in spec['entry_walls']if 'maximum_intrusion_mm'in w)
 footprint=from_wkb(bytes.fromhex(wall['retained_material_wkb_hex']))
 assert footprint.difference(current['joint'].union(current['wall'])).area<=gaps.EPS
 assert footprint.area>gaps.EPS
 assert wall['measurement']=='MINIMUM_AXIS_GAP_OVER_COMPLETE_SOURCE_SPAN'
