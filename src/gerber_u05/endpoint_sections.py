"""Check frozen cross sections against the copper actually emitted per route."""
from shapely.geometry import LineString
from shapely.affinity import translate
from src.native_inventory import ERROR_MM


def transition_sites(rows,patches,known=()):
    """Locate native seams inside an admitted moving-frame joint taper."""
    def key(pt):return tuple(round(float(v),10) for v in pt)
    result=set(known)
    for patch in patches:
        recipe=patch.get('recipe',{});sources=recipe.get('joint_receiver_source_ids',[])
        if recipe.get('schema')!='t04-larger-corner-transition/1' or not sources:continue
        station=0.;cursor=key(patch['endpoint_mm']);limit=recipe['length_mm']
        for sid in sources:
            points=rows[sid]['metadata']['route_points_mm']
            if key(points[-1])==cursor:points=points[::-1]
            if key(points[0])!=cursor:break
            if station<=limit+1e-12:result.add((patch['route_id'],cursor))
            station+=LineString(points).length;cursor=key(points[-1])
            if station>limit+1e-12:break
            result.add((patch['route_id'],cursor))
    return result


def audit(route_bodies, obligations,*,buffers=None):
    checks=[];buffers={}if buffers is None else buffers;built=0
    for obligation in obligations:
        section=obligation['section']; body=route_bodies[obligation['route_id']]
        line=LineString([section['lower_mm'],section['upper_mm']])
        # The wider neighbor can cover the endpoint itself while the receiving
        # continuation is still a rejected narrow KEEP. Check just inside that
        # continuation too, against the complete emitted route and joint fills.
        dx,dy=obligation.get('inward_offset_mm',(0.,0.))
        inside=translate(line,xoff=dx,yoff=dy)
        route=obligation['route_id']
        if route not in buffers or buffers[route][0] is not body:
            buffers[route]=(body,body.buffer(ERROR_MM,quad_segs=128));built+=1
        buffered=buffers[route][1]
        # A qualified curved joint transports the section in a moving native
        # frame. Rigidly translating its old cross section across a bend is
        # a different shape and can report a false missing wedge. Its actual
        # endpoint section still has to be present. An unconstructed/narrow
        # default has no such transition proof and keeps the inward check.
        admitted=obligation.get('native_frame_transition_admitted',False)
        missing=max(v.difference(buffered).length for v in ((line,) if admitted else (line,inside)))
        checks.append(dict(route_id=obligation['route_id'],source_id=obligation['source_id'],
                           endpoint_mm=list(obligation['endpoint_mm']),
                           inward_offset_mm=[float(dx),float(dy)],
                           native_frame_transition_admitted=admitted,
                           required_section_mm=[list(section['lower_mm']),list(section['upper_mm'])],
                           missing_section_length_mm=missing,passed=missing<=ERROR_MM,
                           reason='FROZEN_END_SECTION_NOT_REALIZED_BY_EMITTED_ROUTE' if missing>ERROR_MM
                           else 'FROZEN_SECTION_REALIZED_BY_EMITTED_ROUTE'))
    return dict(passed=all(v['passed'] for v in checks),checked=len(checks),checks=checks,
                native_error_buffers_built=built,native_error_buffers_resident=len(buffers),
                failures=[v for v in checks if not v['passed']],
                geometry_scope='EXACT_SERIALIZED_SOURCE_BODIES_AND_RETAINED_ROUTE_CONTEXT')
