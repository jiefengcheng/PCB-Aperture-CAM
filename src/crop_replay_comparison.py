"""Reviewed diagnostic-area receipt comparison; never a clearance predicate."""
import math

AREA_EPSILON_MM2 = 1e-12
POLICY = 'r080-diagnostic-area-receipt/1'


def _allowed(path):
    return (len(path)==5 and type(path[0]) is int and path[1:3]==('check','pairs')
            and type(path[3]) is int and path[4]=='attachment_port_area_mm2')


def _path(parts):
    return '$'+''.join(f'[{v}]' if type(v) is int else '.'+v for v in parts)


def compare_final_scene_checks(saved,recomputed):
    """Only finite diagnostic port areas may differ by the declared area epsilon.

    Identical nulls retain the original no-port representation. Nulls, booleans
    and strings never receive a numerical allowance. All differences are logged.
    """
    admitted=[];rejected=[]

    def reject(path,a,b,reason):
        rejected.append({'path':_path(path),'saved':a,'recomputed':b,'reason':reason})

    def walk(a,b,path=()):
        if type(a) is not type(b):
            reject(path,a,b,'TYPE_DIFFERENCE');return
        if isinstance(a,float) and (not math.isfinite(a) or not math.isfinite(b)):
            reject(path,a,b,'NON_FINITE_NUMBER');return
        if _allowed(path):
            if a is None and b is None:
                return  # Exact unchanged original no-port value; no tolerance.
            if type(a) not in (int,float):
                reject(path,a,b,'DIAGNOSTIC_AREA_NOT_A_FINITE_JSON_NUMBER');return
            if a<0 or b<0:
                reject(path,a,b,'NEGATIVE_DIAGNOSTIC_AREA');return
            if a!=b:
                delta=b-a
                item={'path':_path(path),'saved':a,'recomputed':b,'signed_delta_mm2':delta,
                      'absolute_delta_mm2':abs(delta),'absolute_tolerance_mm2':AREA_EPSILON_MM2}
                if abs(delta)<=AREA_EPSILON_MM2:admitted.append(item)
                else:reject(path,a,b,'DIAGNOSTIC_AREA_EXCEEDS_ABSOLUTE_TOLERANCE')
            return
        if isinstance(a,dict):
            for key in sorted(set(a)-set(b)):reject(path+(key,),a[key],None,'MISSING_RECOMPUTED_KEY')
            for key in sorted(set(b)-set(a)):reject(path+(key,),None,b[key],'UNEXPECTED_RECOMPUTED_KEY')
            for key in sorted(set(a)&set(b)):walk(a[key],b[key],path+(key,))
        elif isinstance(a,list):
            if len(a)!=len(b):reject(path,len(a),len(b),'LIST_LENGTH_DIFFERENCE')
            for i,(av,bv) in enumerate(zip(a,b)):walk(av,bv,path+(i,))
        elif a!=b:
            reject(path,a,b,'EXACT_VALUE_DIFFERENCE')

    walk(saved,recomputed)
    return {'policy':POLICY,'passed':not rejected,'original_exact_equality':saved==recomputed,
            'admitted_differences':admitted,'rejected_differences':rejected,
            'allowed_path':'$[record].check.pairs[pair].attachment_port_area_mm2',
            'absolute_area_tolerance_mm2':AREA_EPSILON_MM2,
            'distance_tolerance':'NONE; exact receipt equality required'}
