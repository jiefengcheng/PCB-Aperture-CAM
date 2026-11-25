import json
from shapely.ops import unary_union
from src.shared_copper_context import CopperContext
from src.gerber_u05.boundary_prepare import supports
from src.gerber_u05.retained_boundary import run
from tests.gerber_u05.test_shoulder_bridge import straight


def test_joined_local_passes_keep_one_source_index_and_verify_final_dependencies(tmp_path):
    rows,paths,before,original,caps=straight()
    eligibility=dict(policy=dict(source_json=json.dumps(dict(large_fill_core_radius_mm=.2,
        minimum_large_fill_core_area_mm2=1.))),large_fill_coverage_support_source_ids=['s'],
        complete_native_route_inventory=paths)
    with CopperContext(original,source_binding=dict(source='retained-boundary'),frame=dict(units='mm'),
                       root=tmp_path/'prepared')as context:
        contacts=supports(rows,paths,original,context.source,with_sources=True,admitted=before)
        args=dict(material=before,covered=set(),contacts=contacts,revision=context.source,eligibility=eligibility)
        after,changes,sections,report=run(rows,paths,before,original,caps,**args)
        assert report['schema']=='t04-retained-widening-bridges/1'
        assert report['final_dependency_checks']['passed'] and not report['partial']
        assert report['smoothed'] and not report['unresolved'] and changes
        assert report['initial_gap_phase']['smoothed']==0
        assert not original['s'].difference(after['s']).area
        assert unary_union(list(after.values())).area>unary_union(list(before.values())).area
        repeated,_,_,second=run(rows,paths,before,original,caps,**args)
        assert repeated['s'].wkb==after['s'].wkb and second['final_dependency_checks']['passed']
        assert context.stats['source_index_builds']==1
        assert context.stats['broad_fill_resident_hits']>=1


def test_final_dependency_check_rejects_source_loss_after_local_success(tmp_path,monkeypatch):
    from shapely.geometry import box
    import src.gerber_u05.shoulder_bridge as shoulders
    local_run=shoulders.run
    def damaged(*args,**kwargs):
        bodies,changes,sections,report=local_run(*args,**kwargs)
        bodies['s']=bodies['s'].difference(box(-.02,-.1,.02,.1))
        return bodies,changes,sections,report
    monkeypatch.setattr(shoulders,'run',damaged)
    rows,paths,before,original,caps=straight()
    eligibility=dict(policy=dict(source_json=json.dumps(dict(large_fill_core_radius_mm=.2,
        minimum_large_fill_core_area_mm2=1.))),large_fill_coverage_support_source_ids=['s'],
        complete_native_route_inventory=paths)
    with CopperContext(original,source_binding=dict(source='negative-final-boundary'),frame=dict(units='mm'),
                       root=tmp_path/'prepared')as context:
        contacts=supports(rows,paths,original,context.source,with_sources=True,admitted=before)
        _,_,_,report=run(rows,paths,before,original,caps,material=before,covered=set(),
            contacts=contacts,revision=context.source,eligibility=eligibility)
        assert report['partial'] and not report['final_dependency_checks']['passed']
        assert any(r['source_floor_loss_mm2']>0 for r in report['final_dependency_checks']['groups'])


def test_construction_headroom_uses_actual_dense_two_face_widths(tmp_path,monkeypatch):
    from shapely.geometry import box
    import src.gerber_u05.shoulder_bridge as shoulders
    # This is a construction hint, not the independently prepared foreign
    # barrier. An admissible original-frame bridge can occupy that headroom.
    monkeypatch.setattr(shoulders,'width_barrier',lambda *a,**k:box(-.9,.05,.2,.08))
    rows,paths,before,original,caps=straight()
    eligibility=dict(policy=dict(source_json=json.dumps(dict(large_fill_core_radius_mm=.2,
        minimum_large_fill_core_area_mm2=1.))),large_fill_coverage_support_source_ids=['s'],
        complete_native_route_inventory=paths)
    with CopperContext(original,source_binding=dict(source='dense-two-face'),frame=dict(units='mm'),
                       root=tmp_path/'prepared')as context:
        contacts=supports(rows,paths,original,context.source,with_sources=True,admitted=before)
        after,_,_,report=run(rows,paths,before,original,caps,material=before,covered=set(),
            contacts=contacts,revision=context.source,eligibility=eligibility)
        dense=[r for r in report['reports']if r.get('section_validation')=='DENSE_ORIGINAL_TWO_FACE_FRAMES']
        assert dense and all(r['prepared_native_sections']>100 for r in dense)
        assert report['final_dependency_checks']['passed'] and not report['partial']
        assert original['s'].difference(after['s']).area==0
        assert after['s'].area>=before['s'].area


def test_dependency_group_classifies_final_points_once_for_all_members(monkeypatch):
    from shapely.geometry import box
    import src.gerber_u05.boundary_finish as geometry
    from src.gerber_u05.retained_boundary import verify_dependencies
    from src.native_inventory import ERROR_MM
    rows,paths,before,original,caps=straight();clip=box(-2,-2,2,2)
    target=before['s'].simplify(ERROR_MM/10,preserve_topology=True)
    calls=[];raw=geometry.sharp_vertices
    def counted(body,angle):
        if body.equals(target):calls.append(True)
        return raw(body,angle)
    monkeypatch.setattr(geometry,'sharp_vertices',counted)
    records=[dict(plan_index=i,point_mm=[0.,0.],height_mm=.015,status='UNRESOLVED',source_ids=['s'])for i in range(3)]
    plans=[dict(record=r)for r in records];local={i:dict(clip=clip,neighbors=['s'])for i in range(3)}
    report=dict(reports=records,copper_budgets=dict(groups=[dict(id=0,members=[0,1,2])]))
    verify_dependencies(plans,local,report,before,before,original,10)
    assert calls==[True] and report['final_dependency_checks']['passed']
    assert len({tuple(tuple(p)for p in r['final_remaining_points_mm'])for r in records})==1
