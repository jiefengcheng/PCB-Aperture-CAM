"""A fresh worker binds a derived rim before checking its frozen channel budget."""
import copy
import pytest
from shapely import to_wkb,from_wkb
from shapely.geometry import box,LineString
from shapely.affinity import scale,translate
from src import component_clearance as cc,source_channel_scope as functional
from src.source_common_frame import discover
from src.source_channel_guard import SourceChannels
from src.component_voids import plan,joined
from src.partial_pocket_remedy import STRATEGY
from src.gerber_u05 import pipeline as p
from src.gerber_u05.component_policy import capture_job
from tests.gerber_u05.test_source_channels import frame_scene

def setup_reload(tmp_path):
 store,scene,source=frame_scene(tmp_path);pocket=box(2,1,8,9);carrier=box(0,0,10,10).difference(pocket);raw_source=carrier.difference(box(4.5,9,5.5,10.1))
 def place(g):return translate(scale(g,.2,.2,origin=(0,0)),4,4)
 u=place(raw_source);closure=place(carrier.difference(raw_source));twig=LineString([(6,4.5),(8,4.5)]).buffer(.04,quad_segs=64)
 for sid,g in [('u',u),('twig',twig)]:
  ref=p.geomref(store,g);scene['objects'].append(dict(source_id=sid,kind='fixed_source',original_ref=ref,geometry_ref=ref,metadata={}));source=source.union(g)
 frame,cert=discover(source,'a'*64,scene,store);channels=SourceChannels(source,'a'*64,frame,cert,store=store);objects={r['source_id']:p.geometry(store,r['original_ref'])for r in scene['objects']};scope=functional.Scope(channels,cert,objects);physical=cc.Context(source,'a'*64,objects);physical.functional=scope;scope.physical_context=physical;channel=scope.owner('u');own=physical.owner('u')
 report,fills,after=plan(channels.analytic_source,channels.analytic_source.union(closure),partial_strategy=STRATEGY);assert len(report['approved_partial_pockets'])==1
 spec=copy.deepcopy(report['approved_partial_pockets'][0]);spec.update(original_channel_id=channel,original_owner_id=own,original_source_sha256='a'*64);capture_job(tmp_path)
 def derived(sid,g,partials):
  return dict(source_id=sid,kind='component_remedy',original_ref=p.geomref(store,physical.cores[own]),geometry_ref=p.geomref(store,g),metadata=dict(original_owner_id=own,original_channel_id=channel,original_channel_witness_sha256=p.digest(to_wkb(scope.cores[channel])),original_source_sha256='a'*64,approved_partial_pockets=partials))
 closure_row=derived('closure',closure,[]);rim=derived('new-rim',joined([r['geometry']for r in fills]),[spec]);return store,scene,physical,scope,rim,closure_row,spec

def test_fresh_worker_registers_the_rim_and_preserves_one_budget(tmp_path):
 store,scene,physical,scope,rim,closure,spec=setup_reload(tmp_path)
 assert 'new-rim'not in scope.ids
 physical.register_scene(store,dict(objects=scene['objects']+[closure,rim]))
 assert scope.owner('new-rim')==spec['original_channel_id']
 assert set(scope.approved_partial_pockets)=={spec['pocket_id']}
 assert physical.approved_partial_pockets[spec['pocket_id']]['spec']==spec

@pytest.mark.parametrize('field',['original_channel_id','original_channel_witness_sha256'])
def test_fresh_worker_rejects_changed_channel_binding(tmp_path,field):
 store,scene,physical,scope,rim,closure,spec=setup_reload(tmp_path);rim['metadata'][field]='forged'
 with pytest.raises(ValueError,match='FUNCTIONAL_OWNER_BINDING_CHANGED'):physical.register_scene(store,dict(objects=scene['objects']+[closure,rim]))
