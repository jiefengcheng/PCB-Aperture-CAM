"""Original local circle/Region ports, using existing attachment bounds.

Only Gerber Regions explicitly bound by native intake participate. Neither
current contact, net identity nor connected-component membership grants a port.
"""
from shapely import to_wkb
from src.stage_abi.store import digest
from src.clearance_policy import CONTACT_BUFFER_MM
from shapely.ops import unary_union
from functools import lru_cache

SCHEMA='t01-original-gerber-region-contact/1'

@lru_cache(maxsize=1)
def port_buffer_mm():
    # A frozen verified source/contract owns this process. The same existing
    # construction guard and reserve must fit inside an integral joint port;
    # using only the smaller finished/contact gap would create a false sliver
    # of internal clearance and veto every complete-round nomination.
    from src.t01_canonical import specification
    policy=specification()['full_surface_guard']
    return policy['construction_gap_mm']+policy['construction_reserve_mm']


def source_marker(source_sha256,source_id,geometry_sha256):
    return dict(schema=SCHEMA,source_sha256=source_sha256,
                source_id=source_id,geometry_sha256=geometry_sha256,
                source_kind='Region',basis='RESOLVED_ORIGINAL_POSITIVE_SOURCE_CONTRIBUTION')


def original_port(site,row,original,*,quad_segs):
    marker=row.get('t01_original_region')
    if marker is None:return None
    if (row['kind']!='gr_poly' or type(marker)is not dict
            or set(marker)!={'schema','source_sha256','source_id','geometry_sha256','source_kind','basis'}
            or marker['schema']!=SCHEMA or marker['source_kind']!='Region'
            or marker['basis']!='RESOLVED_ORIGINAL_POSITIVE_SOURCE_CONTRIBUTION'
            or marker['source_id']!=row['id']
            or not row['id'].startswith(marker['source_sha256']+':bytes:')
            or digest(to_wkb(original))!=marker['geometry_sha256']):
        raise ValueError('T01_ORIGINAL_REGION_CONTACT_BINDING_CHANGED')
    # Boundary touching and proximity alone do not establish an attachment.
    contact=site['core'].intersection(original)
    if contact.is_empty or contact.area<=0:return None
    # Match the existing trace-port family: a source conductor corridor inside
    # the half-source-radius pad window. A fixed Region can include another arm
    # joined far away: split locally and permit only parts originally attached
    # to this circle. Nearby nonattached arms retain their clearance barriers.
    window=site['core'].buffer(.5*site['radius'],quad_segs=quad_segs)
    buffer=port_buffer_mm()
    local=original.intersection(window.buffer(buffer,quad_segs=quad_segs))
    def parts(g):
        if g.is_empty:return []
        if g.geom_type=='Polygon':return [g]
        return [p for child in getattr(g,'geoms',[])for p in parts(child)]
    attached=[];other=[]
    for part in parts(local):
        (attached if part.intersection(site['core']).area>0 else other).append(part)
    if not attached:raise ValueError('T01_ORIGINAL_REGION_LOCAL_ATTACHMENT_MISSING')
    corridor=unary_union(attached).buffer(buffer,quad_segs=quad_segs)
    barriers=unary_union([p.buffer(buffer,quad_segs=quad_segs)for p in other])
    return corridor.intersection(window).difference(barriers)


def integral_trace_ports(site,rows,shapes,*,quad_segs):
    """Follow only the original local joint, never a remote component path.

    A native trace can join the pad through an original filled Region. The
    legacy primitive checker must recognize that attachment chain as well.
    Other pads and locally disconnected arms remain barriers.
    """
    original_regions=[(r,g)for r,g in zip(rows,shapes)if 't01_original_region'in r]
    if not any(original_port(site,r,g,quad_segs=quad_segs)is not None
               for r,g in original_regions):return {}
    window=site['core'].buffer(.5*site['radius'],quad_segs=quad_segs)
    context=window.buffer(port_buffer_mm(),quad_segs=quad_segs)
    def parts(g):
        if g.is_empty:return []
        if g.geom_type=='Polygon':return [g]
        return [p for c in getattr(g,'geoms',[])for p in parts(c)]
    pieces=[];foreign=[];aliases=set(site.get('aliases',[site.get('source_id')]))
    for row,shape in zip(rows,shapes):
        if row['id']in aliases:continue
        local=shape.intersection(context)
        if local.is_empty:continue
        if row['kind']in('segment','arc')or 't01_original_region'in row:
            pieces.extend((row['id'],g)for g in parts(local))
        else:foreign.extend(parts(local))
    joined=site['core'];pending=list(pieces);attached=[]
    while pending:
        newly=[(s,g)for s,g in pending if g.intersection(joined).area>0]
        if not newly:break
        taken={id(g)for _,g in newly}
        pending=[(s,g)for s,g in pending if id(g)not in taken]
        attached.extend(newly);joined=unary_union([joined,*[g for _,g in newly]])
    foreign.extend(g for _,g in pending)
    corridor=unary_union([g for _,g in attached]).buffer(port_buffer_mm(),quad_segs=quad_segs).intersection(window)
    barrier=unary_union([g.buffer(port_buffer_mm(),quad_segs=quad_segs)for g in foreign])
    permission=corridor.difference(barrier)
    # Only native traces whose original local material actually joins the seed
    # gain this permission. Region and nominal foreign predicates still run.
    trace_ids={r['id']for r in rows if r['kind']in('segment','arc')}
    return{s:permission for s,_ in attached if s in trace_ids}


def install_prepared_ports(checker,rows):
    """Derive identical T01 ports for complete and actual-file land checks."""
    indexed={r['id']:r for r in rows}
    proofs=[]
    for sid in sorted(checker.trace_ids):
        if checker.kinds.get(sid)!='gr_circle':continue
        core=checker.original[sid]
        radius=((core.bounds[2]-core.bounds[0])+(core.bounds[3]-core.bounds[1]))/4
        for oid in sorted(checker.original):
            row=indexed.get(oid)
            if row is None or 't01_original_region'not in row:continue
            original=checker.original[oid]
            if not original.intersects(core):continue
            port=original_port(dict(core=core,radius=radius),row,original,
                               quad_segs=checker.contract.port_quad_segs)
            if port is None:continue
            checker.ports[(sid,oid)]=(port,True,core.distance(original))
            proofs.append(dict(source_circle_id=sid,source_region_id=oid,
                               original_circle_sha256=digest(to_wkb(core)),
                               original_region_sha256=digest(to_wkb(original)),
                               local_port_sha256=digest(to_wkb(port)),
                               policy=SCHEMA))
    return proofs
