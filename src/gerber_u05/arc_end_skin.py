"""Keep grown arc skins at true native joins; original round caps stay fixed."""
import numpy as np
from shapely.geometry import Polygon
from shapely.ops import unary_union
from .arc_membership import tangent
from .finite_profile_union import polygonal
from src.native_inventory import ERROR_MM


def retain_native_end_planes(body,original,points):
    p=np.asarray(points,float); planes=[]
    scale=max(body.bounds[2]-body.bounds[0],body.bounds[3]-body.bounds[1])+1
    for end,center in ((False,p[0]),(True,p[-1])):
        inward=tangent(points,end);n=np.array([-inward[1],inward[0]])
        # Curves that return behind an end plane need a different native cap
        # treatment. Do not clip their interior or make a source-path change.
        if min(float((v-center)@inward)for v in p)<-ERROR_MM:
            return body,dict(applied=False,reason='NATIVE_PATH_RETURNS_BEHIND_TRUE_END')
        planes.append(Polygon([center+inward*u+n*v for u,v in
                      [(-2*ERROR_MM,-scale),(scale,-scale),(scale,scale),(-2*ERROR_MM,scale)]]))
    clipped=body
    for plane in planes:clipped=polygonal(clipped.intersection(plane))
    result=polygonal(unary_union([original,clipped]))
    from .source_trace_floor import preserve
    result,floor_proof=preserve(original,result)
    return result,dict(applied=True,policy='TRUE_NATIVE_END_PLANES; ORIGINAL_ROUND_CAPS_RETAINED',
                       assembly_overlap_mm=2*ERROR_MM,source_path_changed=False,
                       original_floor=floor_proof,
                       optional_end_cap_removed_mm2=body.difference(result).area)
