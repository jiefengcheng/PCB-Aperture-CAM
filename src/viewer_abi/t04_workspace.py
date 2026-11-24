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
    return result


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
    for record in stage['hybrid_components'].get('residual_end_matching',{}).get('reports',[]):
        if not record.get('optional_floor_replaced')or'shared_contour_sha256'not in record:continue
        add('continuity',record['route_id'],record['source_ids'],['SHARED_NATIVE_CHAIN_PROFILE'],
            'One smooth field spans these source segments. Original copper is retained; preceding optional shoulders are replaced. '
            'Saved positive-addition and differential pocket checks passed.')
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
        summary='T04 only · cleaned input compared with saved T04 result · grey copper',
        note='Saved diagnostic result. Findings and controls only navigate prepared display data; they do not execute treatment or change acceptance.')


def publish(root):
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
    target=root/'session/presentations'/(manifest['sha256']+'.json');envelope=json.loads(target.read_bytes())
    raw=base64.b64decode(envelope['payloadBase64'])
    if digest(raw)!=envelope['sha256']:raise ValueError('T04_VIEW_PRESENTATION_CHECKSUM_CHANGED')
    presentation=json.loads(raw)
    if presentation['sceneSHA256']!=manifest['sha256']or presentation['constructionSHA256']!=event['geometry']['sha256']:
        raise ValueError('T04_VIEW_PRESENTATION_REVISION_CHANGED')
    read=artifact_reader(config['legacy']);catalogue=json.loads(read(config['scene_ref']));mapping=construction_map(stage,config)
    originals={r['source_id']:from_wkb(read(r['geometry_ref']))for r in catalogue['objects']}
    current={s:from_wkb(bytes.fromhex(mapping[s]))if s in mapping else g for s,g in originals.items()}
    if {s:digest(to_wkb(g))for s,g in current.items()}!=state['fingerprints']:raise ValueError('T04_VIEW_OUTPUT_FINGERPRINT_CHANGED')
    inputs,input_sha=saved_input(report,event['report']['path'],originals)
    data=build(stage,report,union_all(list(inputs.values())),union_all(list(current.values())),
        layer=snapshot['sources'][0]['layer'],source_sha=config['source_sha256'],input_sha=input_sha,input_shapes=inputs)
    presentation['t04']=data
    payload=encode(presentation)
    if len(payload)>64*1024*1024:raise ValueError('T04_VIEW_RESOURCE_LIMIT')
    if read_current(root/'session')[0]!=manifest:raise ValueError('T04_VIEW_REVISION_CHANGED')
    atomic_write(target,encode(dict(schema=1,sha256=digest(payload),payloadBase64=base64.b64encode(payload).decode())))
    return dict(status='SAVED_T04_VIEW_PREPARED',revision=snapshot['revision'],path=str(target.resolve()),sha256=digest(target.read_bytes()),
        inputSceneSHA256=input_sha,constructionSHA256=event['geometry']['sha256'],parts=len(data['parts']),
        addedAreaMM2=data['addedAreaMM2'],removedAreaMM2=data['removedAreaMM2'],findings=len(data['findings']),treatmentExecuted=False)
