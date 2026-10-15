"""Independent result checks: reparse actual Gerber; no executor imports."""
from pathlib import Path
import math
from shapely.geometry import Point,box
from shapely.ops import unary_union
from gerbonara import graphic_objects as go
from .gerber_image import object_geometry
from .client_gerber import sha,read_region

def polygons(g):return list(g.geoms) if hasattr(g,'geoms') else ([g] if not g.is_empty else [])
def containing(g,p):return next((x for x in polygons(g) if x.covers(Point(p))),None)

def validate(reference,before,candidate,mask,contract,reference_image=None,before_image=None):
    roi_bounds=contract['allowed_region_mm']
    r=reference_image or read_region(reference,roi_bounds);b=before_image or read_region(before,roi_bounds);c=read_region(candidate,roi_bounds);m=read_region(mask,roi_bounds)
    checks=[];threshold=contract['area_tolerance_mm2']
    def check(name,passed,actual,requirement):checks.append({'id':name,'status':'PASS' if passed else 'FAIL','actual':actual,'requirement':requirement})
    pads=[o for o in c['objects'] if isinstance(o,go.Flash) and tuple(o.attrs.get('.P',())[:2])==tuple(contract['terminal'])]
    check('target_identity',len(pads)==1,{'count':len(pads)},'Exactly one declared target .P occurrence')
    if len(pads)!=1:return {'status':'FAIL','checks':checks}
    pad=pads[0];pg=object_geometry(pad);center=(pad.x,pad.y);opening=contract['opening_anchor_mm'];anchor=contract['anchor_mm']
    shift=math.dist(center,opening);exposed=pg.intersection(m['geometry']).area;covered=pg.difference(m['geometry']).area
    check('alignment',shift<=contract['center_tolerance_mm'] and covered<=threshold,{'center_mm':center,'center_error_mm':shift,'pad_area_mm2':pg.area,'exposed_mm2':exposed,'covered_mm2':covered},'Center on the fixed opening and fully expose target within explicit tolerance')
    check('target_label',tuple(pad.attrs.get('.N',()))==tuple(contract['source_net_label']),{'observed':pad.attrs.get('.N')},'Preserve the explicitly declared source net label; no independent schematic claim')
    check('mask_stability',sha(mask)==contract['mask_sha256'],{'sha256':sha(mask)},'Fixed mask bytes unchanged')
    roi=box(*roi_bounds);delta=b['geometry'].symmetric_difference(c['geometry']);outside=delta.difference(roi).area
    ignored=set(contract['writable_ordinals']);changed_bounds=[]
    for ordinal in ignored:
        for rows in (b['objects'],c['objects']):
            obj=rows[ordinal];bb=obj.bounding_box()
            changed_bounds.append({'ordinal':ordinal,'bbox_mm':[bb[0][0],bb[0][1],bb[1][0],bb[1][1]],'within_contract':roi.covers(box(bb[0][0],bb[0][1],bb[1][0],bb[1][1]))})
    scope_ok=outside<=threshold and all(x['within_contract'] for x in changed_bounds)
    check('change_scope',scope_ok,{'outside_local_geometry_mm2':outside,'local_changed_area_mm2':delta.area,'writable_feature_bounds':changed_bounds,'all_unselected_plot_objects_compared':True},'All changed copper geometry is within the declared region; every other parsed object is compared below')
    # Preserve every plotting object except the explicitly identified pad and straight trace.
    ignored=set(contract['writable_ordinals']);protected_ok=len(b['objects'])==len(c['objects']);changed_protected=[]
    for i,(bo,co) in enumerate(zip(b['objects'],c['objects'])):
        if i in ignored:continue
        # Gerbonara Region uses identity equality; compare every parsed field instead.
        if type(bo) is not type(co) or bo.__dict__!=co.__dict__:protected_ok=False;changed_protected.append(i)
    check('protected_objects',protected_ok,{'unselected_changed_ordinals':changed_protected,'before_count':len(b['objects']),'candidate_count':len(c['objects'])},'All unselected parsed plotting objects and attributes unchanged')
    local=c['geometry'].intersection(roi);component=containing(local,center)
    connected=component is not None and component.covers(Point(anchor))
    eroded=local.buffer(-contract['minimum_connection_width_mm']/2)
    robust=containing(eroded,center);width_ok=robust is not None and robust.covers(Point(anchor))
    check('connection',connected and width_ok,{'connected_to_fixed_anchor':connected,'minimum_width_path':width_ok,'minimum_width_mm':contract['minimum_connection_width_mm']},'Preserve a local copper path to the declared fixed trace anchor at required minimum width')
    reference_component=containing(r['geometry'],contract['opening_anchor_mm'])
    if reference_component is None:raise ValueError('Reference anchor absent')
    # Original physically disjoint copper is protected from new contact, irrespective of labels.
    obstacles=unary_union([x.intersection(roi) for x in polygons(r['geometry']) if not x.covers(Point(contract['opening_anchor_mm'])) and x.intersects(roi)])
    gap=component.distance(obstacles) if component is not None and not obstacles.is_empty else None
    overlap=component.intersection(obstacles).area if component is not None else 0
    check('separation',gap is not None and gap+1e-8>=contract['minimum_clearance_mm'] and overlap<=threshold,{'minimum_clearance_mm':gap,'overlap_with_original_disjoint_copper_mm2':overlap},'Do not join originally disjoint nearby copper; preserve explicit demonstration clearance')
    movement=math.dist(contract['before_center_mm'],center)
    check('movement_limit',movement<=contract['max_move_mm']+1e-8,{'movement_mm':movement},'Movement within contract bound')
    return {'status':'PASS' if all(x['status']=='PASS' for x in checks) else 'FAIL','checks':checks,'candidate_sha256':sha(candidate),'electrical_scope':'One explicitly declared same-layer local path and original physical separation; whole-board electrical NOT_ESTABLISHED','geometry':c['geometry']}
