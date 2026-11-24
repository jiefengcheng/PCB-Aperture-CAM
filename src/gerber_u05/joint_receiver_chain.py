"""Extend a joint taper through native source seams without moving its path."""
from shapely.geometry import LineString
from shapely.ops import unary_union


def extend(rows, sources, descriptors, target, endpoint, required_length):
    """Stop at branches, changed widths, shared-member interiors or true ends.

    The actual frozen skins and their fields are retained. This only supplies
    more of the same native route to the existing bounded taper constructor.
    """
    from .corner_transition import oriented,corners
    def key(pt):return tuple(round(float(v), 10) for v in pt)
    def pieces(desc, end):
        length=LineString(desc['points']).length
        fields=desc.get('fields')
        if fields is None:
            fields=[dict(first_mm=0., last_mm=length,
                         controls=[[v]*4 for v in desc['offsets_mm']])]
        if end==0:return fields
        return [dict(first_mm=length-p['last_mm'], last_mm=length-p['first_mm'],
                     controls=[[-v for v in c[::-1]] for c in p['controls'][::-1]])
                for p in fields[::-1]]
    first=descriptors[target]
    if first.get('member_id')and not first.get('real_endpoints',[True,True])[endpoint]:return None
    start_corners,start_normal=corners(first,endpoint,skin=False)
    points=list(oriented(first, endpoint)); fields=pieces(first, endpoint)
    width=first['source_width_mm']; length=LineString(points).length
    skins=[first['support']] if 'support' in first else []
    visited=list(first.get('member_source_ids',[target]))
    if endpoint==1:visited.reverse()
    initial_count=len(visited)
    while length+1e-12<required_length:
        join=key(points[-1]); incident=[]
        for sid in sources:
            pts=rows[sid]['metadata']['route_points_mm']
            if join in (key(pts[0]), key(pts[-1])):incident.append(sid)
        if len(incident)!=2:break
        others=[s for s in incident if s not in visited]
        if len(others)!=1:break
        sid=others[0]; desc=descriptors.get(sid)
        if desc is None or abs(desc['source_width_mm']-width)>1e-12:break
        # A maximal shared member may expose an internal custody endpoint;
        # joining there would duplicate or reverse part of its native path.
        ends=[e for e in (0,1) if key(desc['points'][0 if e==0 else -1])==join
              and desc.get('real_endpoints',[True,True])[e]]
        if len(ends)!=1:break
        end=ends[0]; more=oriented(desc,end); segment_length=LineString(more).length
        if segment_length<=0 or key(more[-1]) in {key(p) for p in points}:break
        fields.extend(dict(p, first_mm=p['first_mm']+length,
                           last_mm=p['last_mm']+length) for p in pieces(desc,end))
        added=list(desc.get('member_source_ids',[sid]))
        if end==1:added.reverse()
        if set(added).intersection(visited):break
        points.extend(more[1:]); length+=segment_length; visited.extend(added)
        if 'support' in desc:skins.append(desc['support'])
    if len(visited)==initial_count:return None
    end_corners,end_normal=corners(desc,1-end,skin=False)
    result=dict(first, points=points, fields=fields,
                joint_receiver_source_ids=visited, real_endpoints=[True,True],
                endpoint_sections=[dict(normal=start_normal.tolist(),lower_mm=start_corners[0].tolist(),upper_mm=start_corners[1].tolist()),
                                   dict(normal=(-end_normal).tolist(),lower_mm=end_corners[1].tolist(),upper_mm=end_corners[0].tolist())])
    result.pop('stabilize_joint_frame',None)
    if skins:result['support']=unary_union(skins)
    return result
