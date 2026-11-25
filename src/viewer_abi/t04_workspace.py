"""Dedicated T04 display from authenticated saved input/output and findings.

This module prepares display data only. It imports no treatment constructors,
search context, clearance verifier or cleanup algorithm.
"""
import base64
import gzip
import json
from pathlib import Path
from shapely import from_wkb, to_wkb, union_all
from .publisher import atomic_write, bounds, digest, encode, path_data, read_current
from .live import artifact_reader, construction_map, display, load_connection, read_bound


def saved_input(report, report_path, originals):
    ref=report.get('inputs',{}).get('trimmed_entry_scene_ref')
    if ref is None:return originals,report['inputs']['scene_ref']['sha256']
    folder=Path(report_path).parent/'runtime/artifacts'
    def read(ref,kind):
        if ref['artifact_id']!=kind+':'+ref['sha256']:raise ValueError('T04_VIEW_INPUT_REFERENCE_INVALID')
        path=folder/ref['artifact_id']
        if path.is_symlink():raise ValueError('T04_VIEW_INPUT_LINK_FORBIDDEN')
        return read_bound(path,ref['sha256'])
    scene=json.loads(read(ref,'scene'))
    rows=scene['objects']
    if [r['source_id']for r in rows]!=list(originals):raise ValueError('T04_VIEW_INPUT_INVENTORY_CHANGED')
    result={}
    for row in rows:
        s=row['source_id'];g=originals[s];geometry=row['geometry_ref']
        result[s]=g if digest(to_wkb(g))==geometry['sha256'] else from_wkb(read(geometry,'geometry'))
    return result,ref['sha256']


def findings(stage):
    h=stage['hybrid_components'];result=[]
    for record in (h.get('boundary_transitions')or{}).get('marked_review',{}).get('cases',[]):
        result.append(dict(id='t04-marked:'+record['id'],kind='marked',routeID=record['image'],sourceIDs=[],
            bounds=record['bounds'],reasons=[record['disposition']],missingSectionMM=None,
            description=('Saved comparison at the marked place. '+record['disposition'].replace('_',' ').capitalize()+
                '. Added %.9f mm²; adjusted %.9f mm²; net %.9f mm². '%
                (record['added_area_mm2'],record['removed_area_mm2'],record['net_area_mm2'])+
                ('Original pad attachments remain pending T05 teardrops. 'if record.get('deferred_terminal_corners_mm')else'')+
                'Use Previous widening to compare the same location before and after the shoulder repairs.')))
    explanations={
        'NO_LARGER_EXPOSED_CORNER':'The saved constructor found no larger exposed corner it could extend.',
        'CORNER_TRANSITION_TOO_SHORT':'Too little trace length was available for the allowed transition.',
        'CORNER_TRANSITION_REACH_OUTLIER':'The proposed transition exceeded the allowed local reach.',
        'FROZEN_END_SECTION_NOT_REALIZED_BY_EMITTED_ROUTE':'The saved route does not fully reach its required endpoint width.'}
    records=[('corner',r)for r in (h.get('corner_smoothing')or{}).get('reports',[])if r['status']=='KEEP_UNRESOLVED']
    records += [('endpoint',r)for r in h.get('frozen_endpoint_obligations',{}).get('failures',[])]
    for kind,r in records:
        point=r['endpoint_mm'];codes=list(dict.fromkeys([r['reason']]if 'reason'in r else
            [reason for a in r.get('attempts',[])for reason in a.get('reasons',[])]))
        sources=list(dict.fromkeys(r[k]for k in ('source_id','donor_source_id')if r.get(k)))
        result.append(dict(id='t04-finding:'+str(len(result)),kind=kind,routeID=r['route_id'],sourceIDs=sources,
            bounds=dict(x=point[0]-.12,y=point[1]-.12,width=.24,height=.24),
            reasons=codes,description=' '.join(explanations.get(c,c.replace('_',' ').capitalize())for c in codes) or 'Unresolved in the saved result.',
            missingSectionMM=r.get('missing_section_length_mm')))
    transition= h.get('boundary_transitions') or {}
    withdrawal_reasons={s:r['reason']for r in transition.get('withdrawn_growth',[])for s in r['source_ids']}
    for record in transition.get('reports',[]):
        point=record['point_mm'];angle=transition['maximum_transition_angle_degrees']
        if transition.get('schema')=='t04-retained-widening-bridges/1':
            text=('Flexible-end bridge. Added %.9f mm²; adjusted %.9f mm²; net gain %.9f mm². '
                'Original copper is retained. The %g° width-alignment limit applies outside source-qualified native junction mouths.'%
                (record['added_area_mm2'],record['removed_area_mm2'],record['net_growth_area_mm2'],angle)
                if record['status']=='BRIDGED'else
                'Finished by a neighbouring bridge; checked against the combined saved copper.'
                if record['status']=='RESOLVED_BY_COUPLED_BRIDGE'else
                'No direct repair was accepted at this place. '+bridge_reason(record.get('reason','UNRESOLVED')))
            result.append(dict(id='t04-transition:'+str(len(result)),kind='transition',routeID=record['route_id'],
                sourceIDs=record.get('source_ids',[]),bounds=dict(x=point[0]-.2,y=point[1]-.2,width=.4,height=.4),
                reasons=[record['status']],missingSectionMM=None,description=text))
            continue
        if transition.get('schema')=='t04-growth-gap-bridges/1':
            text=('Straight-to-bend gap bridged at a maximum '+str(angle)+' degree taper. '
                'Previous widening is retained except for any measured local adjustment inside this bridge. '
                'Added %.9f mm²; removed %.9f mm²; net gain %.9f mm². Original copper remains.'%
                (record['added_area_mm2'],record['removed_area_mm2'],record['net_growth_area_mm2'])
                if record['status']=='BRIDGED'else
                'Gap remains unresolved; previous widening is unchanged. '+bridge_reason(record.get('reason','No admissible bridge.')))
            result.append(dict(id='t04-transition:'+str(len(result)),kind='transition',routeID=record['route_id'],
                sourceIDs=record.get('source_ids',[]),bounds=dict(x=point[0]-.2,y=point[1]-.2,width=.4,height=.4),
                reasons=[record['status']],missingSectionMM=None,description=text))
            continue
        result.append(dict(id='t04-transition:'+str(len(result)),kind='transition',routeID=record['route_id'],
            sourceIDs=record.get('source_ids',[]),bounds=dict(x=point[0]-.2,y=point[1]-.2,width=.4,height=.4),
            reasons=[record['status']]+(['GROWTH_WITHDRAWN']if record.get('optional_growth_withdrawn')else []),missingSectionMM=None,description=(
                'Saved '+record['kind'].lower().replace('_',' ')+' transition. Maximum width slope '+str(angle)+' degrees. '
                'The complete native section was treated together; only preceding optional growth was removed. '
                'Original copper and fixed contacts remain. '+
                ('Optional growth was withdrawn here because the finished outline could not retain it smoothly. '
                 +' '.join(dict.fromkeys(withdrawal_reasons.get(s,'').replace('_',' ').capitalize()+'.' for s in record.get('source_ids',[])if withdrawal_reasons.get(s)))+' '
                 if record.get('optional_growth_withdrawn')else '')+
                ('Finished outline has no additional shoulders.'if record['status']=='SMOOTHED'else record.get('reason','Unresolved in the saved result.')))))
    for record in transition.get('deferred_terminals',[]):
        for point in record['points_mm']:
            result.append(dict(id='t04-terminal:'+str(len(result)),kind='terminal',routeID=record['route_id'],
                sourceIDs=record['source_ids']+record['land_ids'],bounds=dict(x=point[0]-.2,y=point[1]-.2,width=.4,height=.4),
                reasons=['DEFERRED_TO_T05'],missingSectionMM=None,
                description='Deferred to teardrop. This shoulder lies in an exact source-qualified pad attachment window owned by T05. '
                'T04 keeps admitted trace growth and original copper. T05 must complete the junction and verify the saved obligation; '
                'it stays pending until actual teardrop copper resolves it. This is not a completed final-board shape.'))
    return result


def bridge_reason(reason):
    explanations={
        'SOURCE_FLOOR_POSITIVE_COPPER_STILL_MISSING':'The proposed overlay could not preserve every required copper edge within the existing precision limits, so it was rejected.',
        'LOCAL_GROWTH_LOSS':'This proposal would remove more existing widening than it adds.',
        'OUTSIDE_PREPARED_GROWTH_ALLOWANCE':'This proposal enters space reserved for other copper or a protected pin void.',
        'OUTSIDE_RESERVED_BRIDGE_ENVELOPE':'This alternative extends beyond the area prepared for this batch.',
        'BRIDGE_OUTLINE_HAS_SHOULDER':'The proposed bridge would leave another abrupt step.',
        'PREPARED_TOTAL_WIDTH_CAP':'This proposal exceeds an existing trace-width limit.',
        'EMITTED_BRIDGE_WIDTH_CAP':'The emitted bridge exceeds an existing trace-width limit.'}
    codes=reason.removeprefix('BASELINE_RETAINED; ').split(',')
    return ' '.join(explanations.get(code,
        'This proposed bridge does not fit the allowed transition angle.'if 'ANGLE'in code else code.replace('_',' ').capitalize()+'.')for code in codes)


def review_places(stage, inputs):
    """Navigate saved decisions and admitted profiles, never execute either."""
    if inputs is None:return []
    result=[];ledger=stage.get('trace_eligibility_policy',{})
    paths=stage.get('native_trace_source_ids_by_route',{})
    def add(kind,route,sources,reasons,description):
        rectangles=[inputs[s].bounds for s in sources if s in inputs and not inputs[s].is_empty]
        if not rectangles:return
        x=min(b[0]for b in rectangles);y=min(b[1]for b in rectangles)
        result.append(dict(id='t04-review:'+str(len(result)),kind=kind,routeID=route,sourceIDs=list(sources),
            bounds=dict(x=x-.04,y=y-.04,width=max(b[2]for b in rectangles)-x+.08,height=max(b[3]for b in rectangles)-y+.08),
            reasons=reasons,description=description,missingSectionMM=None))
    for route in stage.get('requested_routes',[]):
        reasons=ledger.get('kept_routes',{}).get(route)
        if not reasons or route not in paths:continue
        measurement=ledger.get('large_fill_route_coverage',{}).get(route,{})
        fraction=measurement.get('large_fill_coverage_fraction')
        text='Entire route retained at its input copper contours.'
        if 'LARGELY_COVERED_BY_LARGE_FILLED_COPPER'in reasons and fraction is not None:
            text+=' Independent broad fill covers %.3f%% of its input area.'%(100*fraction)
        if 'LARGELY_COVERED_BY_OTHER_ENTRY_COPPER'in reasons:
            fraction=ledger.get('candidate_route_coverage',{}).get(route,{}).get('other_entry_coverage_fraction')
            if fraction is not None:
                text+=' Other input copper covers %.3f%% of its input area; its own segments and exact aliases are excluded.'%(100*fraction)
        add('eligibility',route,paths[route],reasons,text)
    for route in stage.get('requested_routes',[]):
        if route in ledger.get('kept_routes',{}):continue
        for source,record in ledger.get('candidate_source_coverage',{}).get(route,{}).items():
            if not record['keep']:continue
            fraction=record['other_entry_coverage_fraction']
            broad=record.get('basis')=='INDEPENDENT_BROAD_FILL'
            reason=('LARGELY_COVERED_SOURCE_SEGMENT_BY_LARGE_FILLED_COPPER'if broad else
                    'LARGELY_COVERED_SOURCE_SEGMENT_BY_OTHER_ENTRY_COPPER')
            text=('Large filled copper'if broad else'Other input copper')+' covers %.3f%% of this segment’s own area. '%(100*fraction)
            text+='The covered segment stays unchanged; exposed neighbours can still grow.'
            if broad:text+=' Ordinary pad overlap does not establish this exclusion.'
            add('eligibility',route,[source],[reason],text)
    transitions=stage['hybrid_components'].get('boundary_transitions')
    retained=transitions is not None and transitions.get('schema')in('t04-growth-gap-bridges/1','t04-retained-widening-bridges/1')
    active_sources=None if transitions is None or retained else{s for chain in transitions['chains']if chain['recipe']is not None for s in chain['source_ids']}
    processed_sources=set()if transitions is None else{s for chain in transitions['chains']for s in chain['source_ids']}
    for record in stage['hybrid_components'].get('residual_end_matching',{}).get('reports',[]):
        if not record.get('optional_floor_replaced')or'shared_contour_sha256'not in record:continue
        if active_sources is not None and processed_sources.intersection(record['source_ids'])and not active_sources.intersection(record['source_ids']):continue
        add('continuity',record['route_id'],record['source_ids'],['SHARED_NATIVE_CHAIN_PROFILE'],
            ('Admitted widening remains on this native section. Local straight-to-bend bridges and unresolved gaps have separate saved records.'
             if retained else
             'The final subtractive field tapers admitted growth across this native section. Original copper remains; the saved edge-angle and finished-outline checks passed.'
             if transitions is not None else
             'One smooth field spans these source segments. Original copper is retained; preceding optional shoulders are replaced. Saved positive-addition and differential pocket checks passed.'))
    return result


def build(stage, report, before, after, *, layer, source_sha, input_sha,input_shapes=None):
    from .board_growth import partition
    parts=[];areas={};error=0.
    for kind,g in partition(before,after):
        areas[kind]=g.area
        for polygon in ([]if g.is_empty else[g]if g.geom_type=='Polygon'else g.geoms):
            if polygon.geom_type!='Polygon' or polygon.area==0:continue
            physical=polygon.area;shown,e=display(polygon);error=max(error,e)
            parts.append(dict(id='growth:t04:'+str(len(parts)),sourceID=source_sha+':display-growth:t04:'+str(len(parts)),
                kind=kind,layer=layer,path=path_data(shown),bounds=bounds(shown),attributes={'physical_area_mm2':[repr(physical)]}))
    settings=report.get('settings',{});policy=json.loads(settings.get('trace_eligibility',{}).get('source_json','{}'))
    return dict(schema=1,fullBoard=stage.get('full_board_run',True),
        largeFillCoverageFraction=policy.get('minimum_large_fill_coverage_fraction'),
        inputSceneSHA256=input_sha,beforeWkbSHA256=digest(to_wkb(before)),afterWkbSHA256=digest(to_wkb(after)),
        parts=parts,bounds=bounds(union_all([before.envelope,after.envelope])),addedAreaMM2=areas['added'],removedAreaMM2=areas['removed'],displayHausdorffMM=error,
        findings=findings(stage)+review_places(stage,input_shapes),grownRoutes=stage['summary']['routes'],keptRoutes=stage['summary']['keep_covered_routes'],
        connectionChecks=report['checks']['native_connections'],
        nominalCutoffMM=policy.get('maximum_eligible_source_width_mm',.25),maximumFactor=settings.get('maximum_factor',1.5),
        maximumWidthIncreaseMM=settings.get('maximum_total_width_increase_mm',.03),
        maximumTransitionAngleDegrees=settings.get('boundary_transitions',{}).get('maximum_transition_angle_degrees'),
        summary='T04 only · cleaned input compared with saved T04 result · grey copper',
        note='Saved diagnostic result. Findings and controls only navigate prepared display data; they do not execute treatment or change acceptance.')


def publish(root,*,create=False):
    root=Path(root);config=load_connection(root);manifest,snapshot=read_current(root/'session')
    state=json.loads(read_bound(root/'receipts'/(manifest['sha256']+'.state.json'),manifest['producerStateSHA256']))
    events=[json.loads(p.read_bytes())for p in (root/'queue').glob('*.ready.json')]
    matches=[v for v in events if v.get('event_id')==state['event']and v.get('kind')=='construction']
    if len(matches)!=1:raise ValueError('T04_VIEW_REQUIRES_COMMITTED_CONSTRUCTION')
    event=matches[0]
    if event['connection_id']!=config['connection_id'] or digest(encode(dict(connection=config['connection_id'],
        report=event['report'],geometry=event['geometry'],status=event['display_status'])))!=state['event']:
        raise ValueError('T04_VIEW_EVENT_BINDING_CHANGED')
    report=json.loads(read_bound(event['report']['path'],event['report']['sha256']))
    stage=json.loads(gzip.decompress(read_bound(event['geometry']['path'],event['geometry']['sha256'])))
    if (stage.get('schema')!='t04-maximal-member-group-plan/1' or
            stage.get('scope',report.get('scope'))not in('FULL_BOARD_DIAGNOSTIC','BOUNDED') or stage.get('operation')=='TRIM_ONLY'):
        raise ValueError('T04_VIEW_REQUIRES_SAVED_T04_CONSTRUCTION')
    target=root/'session/presentations'/(manifest['sha256']+'.json');presentation=None
    if target.exists()or not create:
        envelope=json.loads(target.read_bytes());raw=base64.b64decode(envelope['payloadBase64'])
        if digest(raw)!=envelope['sha256']:raise ValueError('T04_VIEW_PRESENTATION_CHECKSUM_CHANGED')
        presentation=json.loads(raw)
        if presentation['sceneSHA256']!=manifest['sha256']or presentation['constructionSHA256']!=event['geometry']['sha256']:
            raise ValueError('T04_VIEW_PRESENTATION_REVISION_CHANGED')
    read=artifact_reader(config['legacy']);catalogue=json.loads(read(config['scene_ref']));mapping=construction_map(stage,config)
    originals={r['source_id']:from_wkb(read(r['geometry_ref']))for r in catalogue['objects']}
    current={s:from_wkb(bytes.fromhex(mapping[s]))if s in mapping else g for s,g in originals.items()}
    if {s:digest(to_wkb(g))for s,g in current.items()}!=state['fingerprints']:raise ValueError('T04_VIEW_OUTPUT_FINGERPRINT_CHANGED')
    inputs,input_sha=saved_input(report,event['report']['path'],originals)
    outline=report.get('board_outline')
    if outline is not None:
        if (not outline['passed']or outline['input_scene_sha256']!=input_sha or
                outline['output_scene_sha256']!=report['assembly']['scene_ref']['sha256']):
            raise ValueError('T04_VIEW_BOARD_OUTLINE_BINDING_CHANGED')
        folder=Path(event['report']['path']).parent/'runtime/artifacts'
        images=[]
        for ref in(outline['before_ref'],outline['after_ref']):
            if ref['artifact_id']!='geometry:'+ref['sha256']:raise ValueError('T04_VIEW_BOARD_GEOMETRY_REFERENCE_INVALID')
            images.append(from_wkb(read_bound(folder/ref['artifact_id'],ref['sha256'])))
        before_image,after_image=images
    else:before_image,after_image=union_all(list(inputs.values())),union_all(list(current.values()))
    data=build(stage,report,before_image,after_image,
        layer=snapshot['sources'][0]['layer'],source_sha=config['source_sha256'],input_sha=input_sha,input_shapes=inputs)
    if outline is not None and outline.get('shoulder_baseline_ref'):
        ref=outline['shoulder_baseline_ref']
        if ref['artifact_id']!='geometry:'+ref['sha256']:raise ValueError('T04_VIEW_SHOULDER_REFERENCE_INVALID')
        baseline=from_wkb(read_bound(folder/ref['artifact_id'],ref['sha256']))
        review=build(stage,report,baseline,after_image,layer=snapshot['sources'][0]['layer'],
            source_sha=config['source_sha256'],input_sha=input_sha)
        data['shoulderReview']={key:review[key]for key in('beforeWkbSHA256','afterWkbSHA256','parts','bounds',
            'addedAreaMM2','removedAreaMM2','displayHausdorffMM')}
        data['shoulderReview'].update(summary='T04 shoulders · previous widening compared with repaired result · grey copper',
            note='Saved pre-shoulder widening. Earlier cleanup and initial trace growth are excluded from this comparison.')
    if presentation is None:
        # A fresh T04-only workspace uses the saved trimmed-entry/finished
        # board images directly. Do not first reconstruct a raw-source global
        # comparison that also mixes in cleanup removals.
        presentation=dict(schema=1,job=snapshot['job'],revision=snapshot['revision'],
            sceneSHA256=manifest['sha256'],sourceSHA256=config['source_sha256'],predecessorSHA256=input_sha,
            constructionSHA256=event['geometry']['sha256'],
            **{key:data[key]for key in('beforeWkbSHA256','afterWkbSHA256','parts','bounds','addedAreaMM2',
                                     'removedAreaMM2','displayHausdorffMM','summary','note')})
        target.parent.mkdir(exist_ok=True)
    presentation['t04']=data
    payload=encode(presentation)
    if len(payload)>64*1024*1024:raise ValueError('T04_VIEW_RESOURCE_LIMIT')
    if read_current(root/'session')[0]!=manifest:raise ValueError('T04_VIEW_REVISION_CHANGED')
    atomic_write(target,encode(dict(schema=1,sha256=digest(payload),payloadBase64=base64.b64encode(payload).decode())))
    return dict(status='SAVED_T04_VIEW_PREPARED',revision=snapshot['revision'],path=str(target.resolve()),sha256=digest(target.read_bytes()),
        inputSceneSHA256=input_sha,constructionSHA256=event['geometry']['sha256'],parts=len(data['parts']),
        addedAreaMM2=data['addedAreaMM2'],removedAreaMM2=data['removedAreaMM2'],findings=len(data['findings']),treatmentExecuted=False)
