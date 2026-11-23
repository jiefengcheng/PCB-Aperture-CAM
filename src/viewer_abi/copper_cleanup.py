"""Revision-bound inspection records from saved cleanup evidence only."""
from shapely import STRtree
from shapely.geometry import box, LineString
from shapely.ops import unary_union
from .publisher import bounds, path_data


def cleanup_cases(stage, rows, original, removed, added, display, *, layer='cleanup', source_image=None):
    def line_path(g):
        return 'M '+' L '.join(f'{x:.9f} {y:.9f}' for x,y in g.coords)
    byordinal={r.get('metadata',{}).get('gerber_ordinal'):s for s,r in rows.items()}
    candidates=[]; recesses=[]
    def add(record, rule, geometry=None):
        sid=record.get('causing_source_id',record.get('source_id'))
        if sid is None: sid=byordinal.get(record.get('ordinal',record.get('source_ordinal')))
        if sid not in original: return
        noise=record.get('noise_area_check',record.get('area_noise_check',{}))
        g=geometry or record.get('geometry_checks',record.get('proof',{}))
        candidates.append(dict(sid=sid,record=record,noise=noise,geometry=g,rule=rule))
    for r in stage.get('source_pad_cleanup',{}).get('records',[]): add(r,'AREA_NOISE')
    for r in stage.get('owner_supported_physical_noise_corrections',{}).get('records',[]): add(r,'AREA_NOISE')
    for r in stage.get('owner_detected_supported_edge_cleanup',{}).get('accepted',[]): add(r['proof'],'AREA_NOISE')
    for r in stage.get('owner_marked_shallow_straight_edges',{}).get('records',[]): add(r,'SHALLOW_SOURCE_EDGE')
    generic=stage.get('large_copper_cleanup',{})
    for finding in generic.get('findings',[]):
        if finding['status']!='corrected':continue
        r=finding['proof'];add(r,r['rule'])
        candidates[-1]['saved_domain']=box(*finding['bounds_mm'])
    circular=stage.get('owner_marked_circular_edge_corrections',{})
    for r in circular.get('noise_area_checks',[]):
        geom=next((p['proof'] for p in circular.get('records',[]) if p.get('case')==r.get('case')), {})
        add(dict(r,noise_area_check=r),'AREA_NOISE',geom)
    for r in stage.get('owner_marked_bulk_boundary_corrections',{}).get('records',[]):
        if r.get('physical_added_mm2',0)>1e-12:
            recesses.append(r)
        else:
            for child in r.get('source_contribution_checks',[]):
                noise=child.get('area_noise_check',{})
                add(dict(child,source_id=noise.get('source_id')),
                    'AREA_NOISE' if noise.get('is_noise') else 'SHALLOW_SOURCE_EDGE',r.get('geometry_checks'))
    ids=tuple(original);tree=STRtree(list(original.values()))
    def sections(g):
        evidence=g.get('reference_evidence',{})
        flanks=evidence.get('flank_proofs',[evidence]);out=[]
        for flank in flanks:
            for name in ('first','second'):
                pts=flank.get(name)
                if isinstance(pts,list) and len(pts)>=2 and isinstance(pts[0],list):
                    out.append(LineString(pts))
        return out
    def parts(g): return [] if g.is_empty else [g] if g.geom_type=='Polygon' else list(g.geoms)
    cases=[];held_indices={}
    for shape in parts(removed):
        if shape.area<=1e-12: continue
        hits=set(ids[int(i)] for i in tree.query(shape,predicate='intersects'))
        found=list({(c['sid'],c['rule']):c for c in candidates
                    if c['sid'] in hits and original[c['sid']].intersection(shape).area>1e-12
                    and ('saved_domain' not in c or c['saved_domain'].intersection(shape).area>1e-12)}.values())
        # Keep every evidenced causing contribution; no fill-sized denominator
        # and no invented single cause for overlapping native draw fragments.
        sources=[];refs=[]
        for c in found:
            sid=c['sid'];noise=c['noise'];r=c['record'];core=original[sid]
            area=noise.get('original_feature_area_mm2',r.get('original_feature_area_mm2',core.area))
            protrusion=noise.get('protrusion_area_mm2',r.get('whole_physical_protrusion_area_mm2',core.intersection(shape).area))
            sources.append(dict(sourceID=sid,ordinal=rows[sid].get('metadata',{}).get('gerber_ordinal'),
                originalAreaMM2=area,protrudingAreaMM2=protrusion,areaFraction=protrusion/area if area else None,
                rule=c['rule'],contacts='Saved bounded contact/topology checks; see evidence'))
            refs.extend(sections(c['geometry']))
        view,_=display(shape)
        cases.append(dict(id='cleanup:'+str(len(cases)),kind='bump',status='corrected',bounds=bounds(shape),
            path=path_data(view),areaMM2=shape.area,sources=sources,
            rule=' / '.join(sorted({s['rule'] for s in sources})) or 'SAVED_OWNER_SUPPORTED_CORRECTION',
            referencePath=' '.join(line_path(g) for g in refs),depthLimitMM=.1,
            disposition='Trimmed in saved bounded result; original source unchanged'))
        curve_refs=[c['geometry'].get('reference_evidence',{})for c in found
                    if c['geometry'].get('reference_evidence',{}).get('kind','').startswith('CIRCULAR_VOID_FLANKS')]
        if curve_refs:
            cases[-1]['boundaryKind']='circular'
            endpoints=[e for e in curve_refs if e.get('kind')=='CIRCULAR_VOID_FLANKS_AT_NATIVE_STROKE_ENDPOINT']
            if endpoints:
                e=endpoints[0]
                cases[-1]['disposition']=('Circular-edge protrusion trimmed around the original round endpoint of source trace '
                    +str(e['native_stroke_ordinal'])+'. The smaller inner pad does not define this arc. '
                    +'The reference trace is unchanged; only the surrounding copper is trimmed. '
                    +'Source-flank fit error '+format(e['maximum_radial_fit_error_mm'],'.6f')+' mm; no added copper.')
    for r in recesses:
        sid=r['source_bulk_carrier_id'];refs=sections(r.get('geometry_checks',{}))
        # Actual saved addition on the named carrier, never the entire carrier.
        window=box(*r['geometry_checks'].get('reference_evidence',{}).get('window_mm',original[sid].bounds))
        choices=[g for g in parts(added) if g.area>1e-12 and g.intersects(window) and g.distance(original[sid])<1e-5]
        expected=r['physical_added_mm2']
        choices=sorted(choices,key=lambda g:abs(g.area-expected))
        if not choices or abs(choices[0].area-expected)>1e-9:
            raise ValueError('CLEANUP_RECESS_SAVED_DELTA_NOT_IDENTIFIED')
        shape=choices[0];view,_=display(shape)
        cases.append(dict(id='cleanup:'+str(len(cases)),kind='recess',status='corrected',bounds=bounds(shape),
            path=path_data(view),areaMM2=shape.area,rule='SOURCE_FLANK_RECESS',depthLimitMM=.1,
            sources=[dict(sourceID=sid,ordinal=rows[sid].get('metadata',{}).get('gerber_ordinal'),
                          originalAreaMM2=original[sid].area,rule='SOURCE_FLANK_RECESS',
                          contacts='Saved protected-land, clearance and topology checks')],
            referencePath=' '.join(line_path(g) for g in refs),disposition=r['case']))
    for r in stage.get('owner_detected_supported_edge_cleanup',{}).get('deferred',[]):
        b=r.get('bounds_mm')
        if b:
            shape=box(*b)
            held_indices[len(cases)]=r.get('index')
            cases.append(dict(id='cleanup:'+str(len(cases)),kind='bump',status='unresolved',bounds=bounds(shape),
                path='',areaMM2=0,sources=[],rule='UNQUALIFIED',referencePath='',depthLimitMM=.1,
                disposition=('Touches a terminal; kept unchanged.' if r.get('reason','').startswith('TERMINAL_SHAPE_TOUCHED')
                             else 'Area rule not established; kept unchanged.' if r.get('reason')=='AREA_RULE_NOT_ESTABLISHED'
                             else r.get('reason','Not qualified; retained unchanged'))))
    for r in generic.get('findings',[]):
        if r['status']=='corrected':continue
        sid=r.get('causing_source_id');sources=[]
        if sid in original:
            sources=[dict(sourceID=sid,ordinal=rows[sid].get('metadata',{}).get('gerber_ordinal'),
                originalAreaMM2=original[sid].area,protrudingAreaMM2=r['physical_protrusion_area_mm2'],
                areaFraction=r['physical_protrusion_area_mm2']/original[sid].area,
                rule='IGNORED_RECTANGLE' if r['status']=='ignored' else 'UNQUALIFIED',contacts='Retained unchanged')]
        cases.append(dict(id='cleanup:'+str(len(cases)),kind='bump',status=r['status'],
            bounds=bounds(box(*r['bounds_mm'])),path='',areaMM2=r['physical_protrusion_area_mm2'],sources=sources,
            rule='IGNORED_RECTANGLE' if r['status']=='ignored' else 'UNQUALIFIED',referencePath='',
            depthLimitMM=.1,disposition=r['reason']))
    for review in stage.get('owner_unresolved_place_review',{}).get('records',[]):
        domain=box(*review['bounds_mm'])
        if review['status']=='ignored':
            cases.append(dict(id='cleanup:'+str(len(cases)),kind='bump',status='ignored',bounds=bounds(domain),
                path='',areaMM2=review['whole_physical_protrusion_area_mm2'],sources=[],rule='IGNORED_RECTANGLE',
                referencePath='',depthLimitMM=.1,disposition=review['explanation']))
        matches=[c for i,c in enumerate(cases) if c['status']==review['status'] and
                 ((c['status']=='unresolved' and held_indices.get(i)==review['index']) or
                  (c['status']in('corrected','ignored') and box(c['bounds']['x'],c['bounds']['y'],
                     c['bounds']['x']+c['bounds']['width'],c['bounds']['y']+c['bounds']['height']).intersection(domain).area>1e-12))]
        if len(matches)!=1:raise ValueError('REVIEWED_CLEANUP_PLACE_NOT_UNIQUELY_BOUND')
        case=matches[0];sid=review['causing_source_id']
        if sid not in original or abs(original[sid].area-review['original_feature_area_mm2'])>1e-12:
            raise ValueError('REVIEWED_CAUSING_SOURCE_AREA_CHANGED')
        case.update(reviewNumber=review['review_number'],disposition=review['explanation'])
        if case['status']!='corrected':
            case['areaMM2']=review['whole_physical_protrusion_area_mm2']
            case['sources']=[dict(sourceID=sid,ordinal=review['ordinal'],originalAreaMM2=original[sid].area,
                protrudingAreaMM2=review['whole_physical_protrusion_area_mm2'],areaFraction=review['area_fraction'],
                rule='IGNORED_RECTANGLE' if case['status']=='ignored' else 'UNQUALIFIED',contacts='Retained unchanged. Normal depth '+format(review['depth_mm'],'.6f')+' mm; '+review['reason'])]
            case['referencePath']=' '.join(line_path(g)for g in sections(dict(reference_evidence=review['reference_evidence'])))
    # Isolate actual broad plotted-fill objects. Do not reuse the board-wide
    # T04 partition: it also contains the unrelated widened trace ribbons.
    # A broad copper object can be assembled from many native draws which
    # individually look like traces. Use complete original material objects,
    # not the old non-route classification which omitted the 19 bottom caps.
    fill=unary_union(list(original.values())) if source_image is None else source_image
    broad=[g for g in parts(fill) if g.area>=1 and not g.buffer(-.125,quad_segs=128).is_empty]
    changed=[box(c['bounds']['x'],c['bounds']['y'],c['bounds']['x']+c['bounds']['width'],c['bounds']['y']+c['bounds']['height']) for c in cases]
    objects=[];artwork=[]
    source=next(iter(rows),'').split(':',1)[0]
    nearest=[min((g.distance(w) for g in broad),default=float('inf')) for w in changed]
    for body in broad:
        related=[(c,g) for c,g,d in zip(cases,changed,nearest) if d<=.10001 and body.distance(g)<=d+1e-5]
        if not related:continue
        oid='bulk:'+str(len(objects))
        cuts=unary_union([removed.intersection(g) for c,g in related if c['kind']=='bump' and c['status']=='corrected'])
        additions=unary_union([added.intersection(g) for c,g in related if c['kind']=='recess' and c['status']=='corrected'])
        before=body
        after=before.difference(cuts).union(additions)
        objects.append(dict(id=oid,bounds=bounds(before.union(after)),areaMM2=body.area))
        for c,g in related:c.setdefault('objectIDs',[]).append(oid)
        for kind,material in [('source',before.intersection(after)),('removed',before.difference(after)),('added',after.difference(before))]:
            for g in parts(material):
                if g.area<=1e-12:continue
                view,_=display(g)
                artwork.append(dict(id='growth:bulk:'+str(len(artwork)),sourceID=source+':display-growth:bulk:'+str(len(artwork)),
                                    layer=layer,kind=kind,path=path_data(view),bounds=bounds(view),
                                    attributes=dict(copper_object=[oid])))
    operation='TRIM_ONLY' if stage.get('operation')=='TRIM_ONLY' else 'SAVED_RESTORATION'
    if operation=='TRIM_ONLY' and (added.area>1e-12 or any(c['kind']=='recess' for c in cases)):
        raise ValueError('TRIM_ONLY_PRESENTATION_CONTAINS_ADDITION')
    return dict(schema=1,operation=operation,cases=cases,objects=objects,parts=artwork,areaLimitFraction=.1,depthLimitMM=.1,
                areaComparison='STRICTLY_LESS_THAN',areaBasis='ORIGINAL_CAUSING_PAD_OR_TRACE',
                note='REPLAY: original large connected copper objects and saved cleanup changes. Connected original copper remains grey. T04 trace-growth overlays are excluded.')
