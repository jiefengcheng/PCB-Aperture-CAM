import copy
import pytest
from shapely.geometry import box
from shapely.affinity import scale
from src import t04_width_fence as fence
from src.gerber_u05 import pipeline as p
from src.gerber_u05.width_stage_constraints import require_t02


def fixture(tmp_path,monkeypatch,second=False,y=0):
 store=p.Store(tmp_path/'runtime');ref=lambda g:p.geomref(store,g)
 source=box(-1,-.04,1,.04);trace=box(-1,-.054,1,.054);pad=box(.8,y-.2,1.2,y+.2)
 rows=[dict(source_id='trace',kind='stroke',original_ref=ref(source),geometry_ref=ref(trace),metadata={}),
       dict(source_id='pad',kind='rectangle',original_ref=ref(pad),geometry_ref=ref(pad),metadata={})]
 if second:
  other=box(.3,y-.2,.7,y+.2);rows.append(dict(source_id='pad2',kind='rectangle',original_ref=ref(other),geometry_ref=ref(other),metadata={}))
 accepted=p.unary_union([p.geometry(store,r['geometry_ref'])for r in rows])
 rule=fence.Rule.from_accepted(box(-1.02,-.06,1.02,.06),accepted,source.union(pad),'fixture')
 monkeypatch.setattr(fence,'ACTIVE',rule)
 before=dict(objects=rows,lineage=[dict(t04_width_fence=rule.state(store))]);entry=store.put_json('scene',before)
 after=copy.deepcopy(before);grown=scale(pad,1.25,1.25,origin=pad.centroid);after['objects'][1]['geometry_ref']=ref(grown)
 decisions=[dict(source_id='pad',status='GROWN',shape={'factors':[1.25,1.25]},candidate_ref=ref(grown))]
 if second:decisions.append(dict(source_id='pad2',status='KEEP',shape={},candidate_ref=rows[2]['geometry_ref']))
 originals={r['source_id']:p.geometry(store,r['original_ref'])for r in rows}
 order=lambda s:(originals[s].centroid.y,originals[s].centroid.x,s)
 decisions.sort(key=lambda d:order(d['source_id']))
 value=dict(plan=dict(scene_ref=entry,policy_ref=store.put_json('policy',dict(stage='t02',parameters=p.land_parameters('t02'))),details={'targets':sorted((r['source_id']for r in rows if r['kind']=='rectangle'),key=order)}),
            verification={'passed':True},candidate=dict(decisions=decisions,protected_source_refs={'trace':rows[0]['geometry_ref']},inclusive_candidates=[]),output_scene_ref=store.put_json('scene',after))
 return store,entry,value,after


def test_qualified_pad_can_grow_while_the_trace_stays_at_its_chosen_width(tmp_path,monkeypatch):
 store,entry,value,after=fixture(tmp_path,monkeypatch)
 whole=p.unary_union([p.geometry(store,r['geometry_ref'])for r in after['objects']])
 assert not fence.ACTIVE.remedy(whole,fence.ACTIVE.baseline)['passed'] # Reproduces the former false rejection.
 proof=require_t02(store,entry,value)
 assert proof['passed']and proof['protected_predecessor_rows']==1
 assert proof['ordinary_source_pads'][0]['status']=='GROWN'


@pytest.mark.parametrize('mutation',['trace','identity','cap','target'])
def test_pad_authority_cannot_hide_trace_or_policy_changes(tmp_path,monkeypatch,mutation):
 store,entry,value,after=fixture(tmp_path,monkeypatch)
 if mutation=='trace':after['objects'][0]['geometry_ref']=p.geomref(store,box(-1,-.06,1,.06))
 elif mutation=='identity':after['objects'][0]['kind']='rectangle'
 elif mutation=='target':value['plan']['details']['targets'].append('trace')
 else:value['candidate']['decisions'][0]['shape']['factors']=[1.3,1.25]
 value['output_scene_ref']=store.put_json('scene',after)
 with pytest.raises(ValueError):require_t02(store,entry,value)


def add_fill(store,value,after,*,fragment=False):
 members=['pad','pad2'];rows={r['source_id']:r for r in after['objects']}
 full=box(*p.unary_union([p.geometry(store,rows[s]['geometry_ref'])for s in members]).bounds)
 ordinary=p.unary_union([p.geometry(store,r['geometry_ref'])for r in after['objects']])
 assert full.difference(ordinary).area/full.area<=.20
 g=full.difference(fence.ACTIVE.forbidden)if fragment else full
 ref=p.geomref(store,g);sid='t02-inclusive:'+ref['sha256']
 after['objects'].append(dict(source_id=sid,kind='inclusive_rectangle',original_ref=ref,geometry_ref=ref,metadata={'members':members}))
 value['candidate']['inclusive_candidates']=[dict(status='MERGED',members=members,candidate_ref=ref)]
 value['output_scene_ref']=store.put_json('scene',after)


def test_twenty_percent_inclusive_fill_cannot_restore_denied_trace_width(tmp_path,monkeypatch):
 store,entry,value,after=fixture(tmp_path,monkeypatch,second=True)
 add_fill(store,value,after)
 with pytest.raises(ValueError,match='BYPASSES_FROZEN_WIDTH'):
  require_t02(store,entry,value)


def test_clipped_inclusive_fragments_cannot_bypass_the_complete_fill_rejection(tmp_path,monkeypatch):
 store,entry,value,after=fixture(tmp_path,monkeypatch,second=True)
 add_fill(store,value,after,fragment=True)
 with pytest.raises(ValueError,match='FILL_CHANGED_OR_FRAGMENTED'):
  require_t02(store,entry,value)


def test_unrelated_complete_fill_remains_available(tmp_path,monkeypatch):
 store,entry,value,after=fixture(tmp_path,monkeypatch,second=True,y=1)
 add_fill(store,value,after)
 assert require_t02(store,entry,value)['passed']


def test_missing_width_rule_is_an_explicit_failure(tmp_path,monkeypatch):
 store,entry,value,after=fixture(tmp_path,monkeypatch)
 monkeypatch.setattr(fence,'ACTIVE',None)
 with pytest.raises(ValueError,match='RULE_REQUIRED'):require_t02(store,entry,value)


def test_pad_inventory_uses_existing_spatial_order_instead_of_byte_id_order(tmp_path,monkeypatch):
 store,entry,value,_=fixture(tmp_path,monkeypatch,second=True,y=1)
 assert value['plan']['details']['targets']==['pad2','pad']
 assert require_t02(store,entry,value)['passed']
 value['candidate']['decisions'].reverse()
 with pytest.raises(ValueError,match='PAD_AUTHORITY_CHANGED'):require_t02(store,entry,value)
