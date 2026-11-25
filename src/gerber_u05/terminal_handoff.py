"""Source-qualified T04 terminal obligations consumed by additive T05.

Preparation borrows the contact batch: no tree, foreign search or owner rebuild.
The ledger delegates shape completion, never source removal or clearance approval.
"""
import numpy as np
from shapely import from_wkb,to_wkb,points as geometry_points,covers,distance
from shapely.geometry import Point,Polygon
from shapely.ops import unary_union
from src.stage_abi.store import canonical,digest
from src.native_inventory import ERROR_MM
from src.junction_spindle_stage import CONTRACT
from .source_catalogue import t05_land

SCHEMA='t04-t05-terminal-handoff/1'


def prepare(rows,paths,entry,contacts,bodies):
    records=[]
    for route,members in sorted(paths.items()):
        carrier=unary_union([entry[s]for s in members])
        lands=[s for s in contacts.get(route,{})if s in rows and t05_land(rows[s])and
               carrier.intersection(entry[s]).area>1e-12]
        if not lands:continue
        radius=min(min(entry[s].bounds[2]-entry[s].bounds[0],entry[s].bounds[3]-entry[s].bounds[1])/2 for s in lands)
        if radius<=0:raise ValueError('T04_TERMINAL_LAND_SIZE_INVALID')
        window=unary_union([entry[s].buffer(CONTRACT.window_land_radii*radius,
            quad_segs=CONTRACT.buffer_quad_segs)for s in sorted(lands)])
        floor=unary_union([carrier,*[entry[s]for s in lands],*contacts[route].values()]).intersection(window)
        optional=unary_union([bodies[s].difference(entry[s])for s in members]).intersection(window)
        if optional.is_empty:continue
        records.append(dict(route_id=route,source_ids=list(members),land_ids=sorted(lands),
            window_wkb_hex=to_wkb(window).hex(),floor_wkb_hex=to_wkb(floor).hex(),
            optional_scope_wkb_hex=to_wkb(optional).hex(),
            land_original_sha256={s:digest(to_wkb(entry[s]))for s in sorted(lands)},
            policy='EXACT_POSITIVE_SOURCE_CONTACT; EXISTING_T05_MIN_LAND_RADIUS_WINDOW',
            status='DEFERRED_TO_T05',points_mm=[]))
    return records


def window(records):
    return unary_union([from_wkb(bytes.fromhex(r['window_wkb_hex']))for r in records])if records else Polygon()


def interior(points,records):
    if not records or not points:return points
    scopes=[(from_wkb(bytes.fromhex(r['window_wkb_hex'])),
             from_wkb(bytes.fromhex(r['optional_scope_wkb_hex'])))for r in records]
    locations=geometry_points(points);deferred=np.zeros(len(points),dtype=bool)
    for w,g in scopes:
        indices=np.flatnonzero(covers(w,locations)&~deferred)
        deferred[indices]=distance(g,locations[indices])<=2*ERROR_MM
    return [p for i,p in enumerate(points)if not deferred[i]]


def attachment_scopes(records,rows,entry,caps):
    """Separate actual source attachments from the larger T05 search window.

    The contact is original positive copper. Its collar uses the already
    admitted T04 width budget, rather than claiming every bend near a land.
    Existing T05 verification keeps its complete search window unchanged.
    """
    result=[]
    for record in records:
        contacts=[];bindings=[]
        for source in record['source_ids']:
            width=rows[source]['metadata']['minimum_caliper_mm']
            collar=max(0.,caps.get(source,width)-width)+2*ERROR_MM
            for land in record['land_ids']:
                contact=entry[source].intersection(entry[land])
                if contact.area<=1e-12:continue
                contacts.append(contact.buffer(collar,quad_segs=CONTRACT.buffer_quad_segs))
                bindings.append(dict(source_id=source,land_id=land,
                    source_sha256=digest(to_wkb(entry[source])),land_sha256=digest(to_wkb(entry[land])),
                    original_contact_sha256=digest(to_wkb(contact)),collar_mm=collar))
        if not contacts:raise ValueError('T04_T05_ORIGINAL_ATTACHMENT_NOT_ESTABLISHED')
        scope=unary_union(contacts).intersection(from_wkb(bytes.fromhex(record['window_wkb_hex'])))
        result.append(dict(record,attachment_scope_wkb_hex=to_wkb(scope).hex(),attachment_dependencies=bindings,
            t04_ownership='ORIGINAL_POSITIVE_CONTACT_PLUS_ADMITTED_WIDTH_BUDGET; SEARCH_WINDOW_IS_NOT_A_KEEPOUT'))
    return result


def interior_t04(points,records):
    narrowed=[]
    for record in records:
        if 'attachment_scope_wkb_hex'not in record:narrowed.append(record);continue
        scope=from_wkb(bytes.fromhex(record['optional_scope_wkb_hex'])).intersection(
            from_wkb(bytes.fromhex(record['attachment_scope_wkb_hex'])))
        narrowed.append(dict(record,optional_scope_wkb_hex=to_wkb(scope).hex()))
    return interior(points,narrowed)


def refresh_attachments(records,material,contacts,angle):
    """Re-evaluate pending terminal points against the final T04 geometry."""
    from .boundary_finish import sharp_points
    result=[]
    for record in records:
        support=contacts.get(record['route_id'],{});extras=list(support.values())if isinstance(support,dict)else[support]
        image=unary_union([material[s]for s in record['source_ids']]+extras)
        floor=from_wkb(bytes.fromhex(record['floor_wkb_hex']));window=from_wkb(bytes.fromhex(record['window_wkb_hex']))
        updated=dict(record,optional_scope_wkb_hex=to_wkb(image.difference(floor).intersection(window)).hex())
        points=sharp_points(image,floor,angle);outside={tuple(p)for p in interior_t04(points,[updated])}
        updated['points_mm']=[p for p in points if tuple(p)not in outside]
        if updated['points_mm']:result.append(updated)
    return result


def seal(records,material,source_sha256,angle):
    records=[dict(r)for r in records]
    for r in records:
        floor=from_wkb(bytes.fromhex(r['floor_wkb_hex']))
        scope=unary_union([material[s]for s in r['source_ids']]).difference(floor).intersection(from_wkb(bytes.fromhex(r['window_wkb_hex'])))
        r['optional_scope_wkb_hex']=to_wkb(scope).hex()
    value=dict(schema=SCHEMA,source_sha256=source_sha256,records=records,
        source_geometry_sha256={s:digest(to_wkb(material[s]))for r in records for s in r['source_ids']},
        maximum_transition_angle_degrees=angle,final_acceptance=False,owner='T05',permission='ADDITIVE_COMPLETION_ONLY')
    return dict(value,sha256=digest(canonical(value)))


def authenticate(value,source_sha256,material):
    body={k:v for k,v in value.items()if k!='sha256'}
    if (value.get('schema')!=SCHEMA or value.get('source_sha256')!=source_sha256 or
            value.get('sha256')!=digest(canonical(body))or value.get('owner')!='T05'or
            value.get('permission')!='ADDITIVE_COMPLETION_ONLY'or value.get('final_acceptance')is not False):
        raise ValueError('T05_TERMINAL_HANDOFF_BINDING_CHANGED')
    if any(s not in material or digest(to_wkb(material[s]))!=h for s,h in value['source_geometry_sha256'].items()):
        raise ValueError('T05_TERMINAL_TRACE_PREDECESSOR_CHANGED')
    for r in value['records']:
        if any(s not in material for s in r['land_ids']):raise ValueError('T05_TERMINAL_LAND_MISSING')
    return value


def pending(store,scene,material):
    references=[r['terminal_handoff_ref']for r in scene['lineage']if 'terminal_handoff_ref'in r]
    if not references:return None
    return authenticate(store.get_json(references[-1],kind='t04-terminal-handoff'),scene['source_sha256'],material)


def finish(value,after,land_material=None):
    """Resolve only from actual final copper; KEEP/plan alone cannot clear it."""
    from .boundary_finish import sharp_points
    records=[]
    for r in value['records']:
        if not r['points_mm']:continue
        domain=from_wkb(bytes.fromhex(r['window_wkb_hex']))
        floor=from_wkb(bytes.fromhex(r['floor_wkb_hex']))
        if land_material is not None:
            floor=unary_union([floor,*[land_material[s].intersection(domain)for s in r['land_ids']]])
        optional=from_wkb(bytes.fromhex(r['optional_scope_wkb_hex']))
        if floor.difference(after).area>1e-12 or optional.difference(after).area>1e-12:
            raise ValueError('T05_TERMINAL_PREDECESSOR_COPPER_REMOVED')
        local=after.intersection(domain.buffer(4*ERROR_MM))
        points=sharp_points(local,floor,value['maximum_transition_angle_degrees'])
        outside={tuple(p)for p in interior(points,[r])};inner=domain.buffer(-2*ERROR_MM)
        remaining=[p for p in points if inner.covers(Point(p))and tuple(p)not in outside]
        records.append(dict(route_id=r['route_id'],land_ids=r['land_ids'],
            status='UNRESOLVED'if remaining else'RESOLVED_IN_T05_OUTPUT',remaining_shoulders_mm=remaining))
    return dict(handoff_sha256=value['sha256'],passed=all(r['status']=='RESOLVED_IN_T05_OUTPUT'for r in records),
                records=records,resolved=sum(r['status']=='RESOLVED_IN_T05_OUTPUT'for r in records))
