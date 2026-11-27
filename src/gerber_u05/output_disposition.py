"""Classify saved T04 checks without changing geometry or running searches.

Finish-quality targets remain findings. Missing evidence, actual material loss,
connections, clearance, protected geometry and growth budgets remain errors.
Raw check verdicts are never rewritten to PASS by this classification.
"""
ENDPOINT_REASON='FROZEN_END_SECTION_NOT_REALIZED_BY_EMITTED_ROUTE'
UNFILLED_POCKET_REASONS=frozenset(('OUTSIDE_ADMITTED_JOINT_CAPS','COVERED_SOURCE_FIXED',
                                 'CLEARANCE_OR_PROTECTED_DOMAIN'))


def outcome(findings):
    return 'COMPLETED_WITH_REVIEW_FINDINGS'if findings else'COMPLETED'


def combine_findings(*batches):
    """One review place per feature; original check receipts stay intact."""
    places={}
    for rows in batches:
        for row in rows:
            location=tuple(round(v,10)for v in row.get('point_mm',row.get('bounds_mm',())))
            key=row['kind'],location,row.get('pocket_sha256')
            if key not in places:places[key]=dict(row,reasons=[row['reason']])
            elif row['reason']not in places[key]['reasons']:places[key]['reasons'].append(row['reason'])
    return list(places.values())


def pocket_findings(check):
    """Only identified, unfilled source-baseline voids are review findings.

    A rejected filling proposal has not changed output copper. Other failed
    pocket checks, including material/attachment failures, remain errors.
    """
    if check.get('passed')is True:return []
    baseline=check.get('original_source_baseline',{})
    records=baseline.get('records',[])
    pending=[r for r in records if r.get('status')!='FILLED']
    if (baseline.get('schema')!='t04-source-baseline-joint-pockets/1'or not pending or
            baseline.get('original_holes_preserved')is not True or
            baseline.get('constructed_group_bytes_changed')is not False or
            check.get('rejected_enclosures')!=0 or
            any(r.get('passed')is not True for r in check.get('reports',[]))or
            any(r.get('status')!='KEEP_UNQUALIFIED'or r.get('reason')not in UNFILLED_POCKET_REASONS for r in pending)):
        return None
    return [dict(kind='unfilled_pocket',severity='REVIEW',reason=r['reason'],
                 bounds_mm=r['bounds_mm'],area_mm2=r['area_mm2'],pocket_sha256=r['pocket_sha256'])for r in pending]


def dependency_findings(check):
    if check.get('passed')is True:return []
    groups=check.get('groups')
    if not groups:return None
    failed=[g for g in groups if g.get('passed')is not True]
    if not failed or any(g.get('source_floor_preserved')is not True or
                         g.get('new_pockets')!=0 or not g.get('new_corners_mm')for g in failed):return None
    return [dict(kind='corner',severity='REVIEW',reason='FINISHED_BOUNDARY_HAS_SHARP_POINT',
                 point_mm=point,source_ids=g['source_ids'])for g in failed for point in g['new_corners_mm']]


def endpoint_findings(check):
    if check.get('passed')is True:return []
    failures=check.get('failures')
    if not failures or any(not isinstance(r,dict)or r.get('reason')!=ENDPOINT_REASON for r in failures):return None
    return [dict(kind='endpoint',severity='REVIEW',reason=ENDPOINT_REASON,point_mm=r['endpoint_mm'],
                 source_ids=[r['source_id']],route_id=r['route_id'],
                 missing_section_length_mm=r['missing_section_length_mm'])for r in failures]


def outline_disposition(receipt):
    """Reclassify only known outline quality findings; keep raw verdicts."""
    findings=[];errors=[]
    if receipt.get('new_pockets')!=0:errors.append('new_pockets')
    net=receipt.get('bridge_net_growth_area_mm2')
    if not isinstance(net,(float,int))or net < -1e-12:errors.append('growth_budget')
    points=receipt.get('points_mm')
    if not isinstance(points,list)or receipt.get('additional_shoulders')!=len(points):errors.append('outline_evidence')
    else:findings.extend(dict(kind='corner',severity='REVIEW',reason='ASSEMBLED_BOUNDARY_HAS_SHARP_POINT',point_mm=p)for p in points)
    if 'shoulder_phase'in receipt:
        child=outline_disposition(receipt['shoulder_phase']);errors.extend('shoulder_phase:'+e for e in child['errors']);findings.extend(child['review_findings'])
    if receipt.get('passed')is not True and not findings and not errors:errors.append('unclassified_outline_failure')
    return dict(output_valid=not errors,errors=errors,review_findings=findings,completion=outcome(findings))
