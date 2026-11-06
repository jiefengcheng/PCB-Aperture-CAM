import pytest
from shapely.geometry import box,Polygon
from src.component_hole_lineage import classify,identity,hole_polygons
from src.component_voids import proposal_check,RemedyContract,joined
from src import component_clearance as cc
from src.gerber_u05.native_component_checks_final import final_inventory

def example():
 source=box(0,0,30,30).difference(box(3,3,27,27))
 grown=source.union(box(4,3,4.1,27))
 return source,grown

def test_one_source_hole_keeps_one_principal_descendant():
 source,grown=example();report=classify(source,grown)
 assert len(report['source_holes'])==1
 assert len(report['source_holes'][0]['descendant_holes'])==2
 assert len(report['keeper_ids'])==1
 principal=next(h for h in hole_polygons(grown)if identity(h)in report['keeper_ids'])
 assert principal.bounds[0]==4.1

def test_new_split_off_pocket_passes_existing_complete_pocket_guards():
 source,grown=example();report=classify(source,grown);keepers=set(report['keeper_ids']);allholes=hole_polygons(grown)
 patch=next(h for h in allholes if identity(h)not in keepers);protected=joined([h for h in allholes if identity(h)in keepers])
 legacy=proposal_check(patch,grown,source,[],RemedyContract())
 assert 'INHERITED_SOURCE_VOID'in legacy['reasons']
 result=proposal_check(patch,grown,source,[],RemedyContract(),source_void=protected)
 assert result['passed'] and result['shortage']<=.20
 assert len(hole_polygons(grown.union(patch)))==1

def test_foreign_copper_inside_a_split_pocket_is_never_exempt():
 source,grown=example();report=classify(source,grown);keepers=set(report['keeper_ids']);allholes=hole_polygons(grown)
 patch=next(h for h in allholes if identity(h)not in keepers);protected=joined([h for h in allholes if identity(h)in keepers])
 result=proposal_check(patch,grown,source,[(1,box(3.2,10,3.8,11))],RemedyContract(),source_void=protected)
 assert not result['passed'] and 'FOREIGN_CLEARANCE_FAILED'in result['reasons']

def test_two_distinct_original_holes_both_remain_protected():
 original=box(0,0,20,10).difference(box(1,1,9,9).union(box(11,1,19,9)))
 current=original.buffer(.1)
 report=classify(original,current)
 assert len(report['source_holes'])==2 and len(report['keeper_ids'])==2

def test_no_new_hole_is_inherited_when_source_has_none():
 source=box(0,0,10,1).union(box(0,0,1,10)).union(box(9,0,10,10))
 current=source.union(box(0,9,10,10));report=classify(source,current)
 assert not report['keeper_ids'] and len(hole_polygons(current))==1

def test_missing_original_hole_is_still_reported_missing():
 original=box(0,0,10,10).difference(box(2,2,8,8));report=classify(original,box(0,0,10,10))
 assert not report['source_holes'][0]['source_hole_survives']

def test_lineage_is_deterministic_under_ring_reversal():
 source,grown=example();reverse=Polygon(list(grown.exterior.coords)[::-1],[list(r.coords)[::-1]for r in grown.interiors])
 assert classify(source,grown)==classify(source,reverse)

def test_native_inventory_rejects_the_extra_descendant_and_accepts_its_repair(monkeypatch):
 frame,grown=example();foreign=box(10,10,11,11);source=frame.union(foreign);context=cc.Context(source,'test-source',{'frame':frame,'foreign':foreign});monkeypatch.setattr(cc,'ACTIVE',context)
 actual=context.project({'frame':grown,'foreign':foreign})
 with pytest.raises(ValueError,match='NATIVE_UNREPAIRED_GROWTH_CREATED_EMPTY_POCKET'):final_inventory(source,actual)
 report=classify(frame,grown);daughter=next(h for h in hole_polygons(grown)if identity(h)not in report['keeper_ids']);corrected=context.project({'frame':grown.union(daughter),'foreign':foreign})
 result=final_inventory(source,corrected)
 assert result['passed'] and result['new_resolvable_empty_pockets']==0


def test_foreign_bounded_pocket_retains_the_full_foreign_clearance():
 from src.component_voids import foreign_bounded_pocket
 source,grown=example();report=classify(source,grown);allholes=hole_polygons(grown);keepers=set(report['keeper_ids']);parent=next(h for h in allholes if identity(h)not in keepers);protected=joined([h for h in allholes if identity(h)in keepers]);foreign=[(1,box(3.2,10,3.8,11))];contract=RemedyContract();full=proposal_check(parent,grown,source,foreign,contract,source_void=protected)
 assert set(full['reasons'])=={'FOREIGN_CLEARANCE_FAILED'}
 result=foreign_bounded_pocket(parent,grown,source,foreign,contract,full,protected,(allholes,__import__('shapely').STRtree(allholes)))
 assert result is not None
 patch,check,assembled=result
 assert check['passed'] and patch.distance(foreign[0][1])+1e-12>=contract.construction_gap_mm
 assert assembled[0][0].geom_type=='Polygon' and check['shortage']<=.20
 assert parent.difference(patch).intersects(foreign[0][1])

def test_foreign_clipping_does_not_bypass_an_unrelated_failed_guard():
 from src.component_voids import foreign_bounded_pocket
 source,grown=example();parent=hole_polygons(grown)[0]
 assert foreign_bounded_pocket(parent,grown,source,[],RemedyContract(),dict(reasons=['SHORTAGE_ABOVE_20_PERCENT','FOREIGN_CLEARANCE_FAILED']),Polygon(),None)is None

def test_native_completion_distinguishes_new_descendants_from_the_real_source_void(tmp_path,monkeypatch):
 from src.gerber_u05 import pipeline as p
 from src.gerber_u05.native_component_checks_final import completion
 frame,grown=example();foreign=box(10,10,11,11);source=frame.union(foreign);context=cc.Context(source,'test-source',{'frame':frame,'foreign':foreign});monkeypatch.setattr(cc,'ACTIVE',context);store=p.Store(tmp_path/'runtime');before=context.project({'frame':grown,'foreign':foreign});own=context.owner('frame');keepers=set(classify(frame,grown)['keeper_ids']);daughter=next(h for h in hole_polygons(grown)if identity(h)not in keepers)
 ref=p.geomref(store,daughter);record=dict(source_id='new-pocket',original_owner_id=own,logical_patch_ref=ref,kind='hole');result={'intra':{'fills':[record]}};after=dict(before);after[own]=grown.union(daughter)
 assert completion(store,result,{'new-pocket':[daughter]},before,after)['passed']
 bad=box(20,20,20.1,20.1);ref=p.geomref(store,bad);record=dict(source_id='bad-source-fill',original_owner_id=own,logical_patch_ref=ref,kind='hole');result={'intra':{'fills':[record]}};after=dict(before);after[own]=grown.union(bad)
 with pytest.raises(ValueError,match='NATIVE_INHERITED_SOURCE_VOID_FILLED'):completion(store,result,{'bad-source-fill':[bad]},before,after)

def partial_scene(tmp_path,which='daughter',incomplete=False):
 from src.gerber_u05 import pipeline as p
 from src.gerber_u05.component_policy import capture_job
 from src.partial_pocket_remedy import propose
 source=box(0,0,10,10).difference(box(1,1,9,9));grown=source.union(box(4,1,4.1,9))
 context=cc.Context(source,'a'*64,{'source':source});own=context.owner('source');contract=RemedyContract();keepers=set(classify(source,grown)['keeper_ids'])
 selected=next(h for h in hole_polygons(grown)if (identity(h)in keepers)==(which=='principal'))
 # Construct an otherwise valid size-limited proposal. Registration must
 # independently prove source ancestry and complete-pocket identity.
 check=proposal_check(selected,grown,source,[],contract,source_void=Polygon())
 assert check['reasons']==['SHORTAGE_ABOVE_20_PERCENT']
 ring,_,spec=propose(selected,grown,contract,check)
 if incomplete:
  # A forged incomplete carrier can be internally budget-consistent. Scene
  # registration must still reject its missing complete-pocket witness.
  from src.partial_pocket_remedy import construct,shape,digest
  from shapely import to_wkb
  selected=selected.intersection(box(0,0,10,8));carrier=shape(spec,'carrier_hex');ring,remaining,decision=construct(selected,carrier,contract)
  spec.update(pocket_id=digest(selected),initial_pocket_hex=to_wkb(selected).hex(),remaining_hex=to_wkb(remaining).hex(),selected_rim_hex=to_wkb(ring).hex(),decision=decision)
 spec.update(original_owner_id=own,original_source_sha256=context.source_hash)
 store=p.Store(tmp_path/'runtime');capture_job(tmp_path)
 rows=[dict(source_id='grown-owner',kind='component_remedy',geometry_ref=p.geomref(store,grown),original_ref=p.geomref(store,context.cores[own]),metadata=dict(original_owner_id=own,original_source_sha256=context.source_hash)),dict(source_id='partial-rim',kind='component_remedy',geometry_ref=p.geomref(store,ring),original_ref=p.geomref(store,context.cores[own]),metadata=dict(original_owner_id=own,original_source_sha256=context.source_hash,approved_partial_pockets=[spec]))]
 return context,store,dict(objects=rows),grown.union(ring),own,spec

def test_split_pocket_partial_rim_registers_without_exempting_the_source_hole(tmp_path):
 context,store,scene,body,own,spec=partial_scene(tmp_path)
 context.register_scene(store,scene)
 assert list(context.approved_partial_pockets)==[spec['pocket_id']]
 assert not context.partial_pocket_failures({own:body})
 assert all(r['source_hole_survives']for r in classify(context.cores[own],body)['source_holes'])

def test_partial_rim_cannot_be_registered_in_the_principal_source_opening(tmp_path):
 context,store,scene,_,_,_=partial_scene(tmp_path,which='principal')
 with pytest.raises(ValueError,match='PARTIAL_POCKET_IS_PROTECTED_ORIGINAL_HOLE'):context.register_scene(store,scene)
 assert not context.approved_partial_pockets

def test_partial_rim_registration_rejects_a_fragment_of_the_complete_pocket(tmp_path):
 context,store,scene,_,_,_=partial_scene(tmp_path,incomplete=True)
 with pytest.raises(ValueError,match='PARTIAL_POCKET_NOT_COMPLETE_SPLIT_DESCENDANT'):context.register_scene(store,scene)
 assert not context.approved_partial_pockets
