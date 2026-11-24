from shapely.geometry import LineString
from src.gerber_u05.joint_receiver_chain import extend


def example(branch=False, width=.05):
    pts={'a':[[.02,0],[0,0]], 'b':[[.02,0],[.12,0]]}
    if branch:pts['c']=[[.02,0],[.02,.1]]
    rows={s:dict(metadata=dict(route_points_mm=p)) for s,p in pts.items()}
    desc={s:dict(points=p, source_width_mm=width if s=='b' else .05,
                 offsets_mm=[-.025,.025],support=LineString(p).buffer(.025))
          for s,p in pts.items()}
    return rows,desc


def test_reversed_short_occurrence_uses_contiguous_native_span_and_skin():
    rows,desc=example(); q=extend(rows,list(rows),desc,'a',1,.08)
    assert q['points']==[[0,0],[.02,0],[.12,0]]
    assert q['joint_receiver_source_ids']==['a','b']
    assert q['fields'][-1]['last_mm']==.12
    assert q['support'].covers(desc['a']['support'])
    assert desc['a']['points']==[[.02,0],[0,0]]


def test_branch_changed_width_and_shared_member_internal_seam_stop():
    rows,desc=example(branch=True); assert extend(rows,list(rows),desc,'a',1,.08) is None
    rows,desc=example(width=.06); assert extend(rows,list(rows),desc,'a',1,.08) is None
    rows,desc=example();desc['b'].update(real_endpoints=[False,True])
    assert extend(rows,list(rows),desc,'a',1,.08) is None
