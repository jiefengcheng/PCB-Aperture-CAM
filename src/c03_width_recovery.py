"""Exact C03 exposed-source width reconciliation, separate from generic U03.

Original native edges, original fixed-source junctions, and disjoint primary
cohorts follow the accepted C03 construction recipe. No primitive clipping,
source rerouting, fixed-source edit, numerical exemption, or historical candidate
geometry enters construction. Every full-scene width predicate remains required.
"""
from collections import Counter
import math
from shapely import STRtree,from_wkb,to_wkb
from shapely.geometry import LineString,box
from shapely.ops import unary_union
from src.stage_abi.store import canonical,digest
from src.source_junction_paths import junction_source_paths
from src.u03_board.source import native_rows,route_evidence,TRACE_KINDS
from src.u03_board.selection import window
from src.u04_board.roles import reviewed_roles
from src.parallel_trace_relations import parallel_relation,relation_groups
from src.primary_parallel_cohorts import choose_primary_cohorts,station_spacing_links
from src.parallel_curve_relations import parallel_curve_relation
from src.native_inventory import ERROR_MM
from tools.build_c02_trace_eligibility import edge_runs
from src.trace_growth_eligibility import overlapping_parallel_fill_witness

FAMILY='c03-complete-exposed-native-primary-cohorts/2'


def exposed_runs(parents,fixed,source_sha256):
    """Maximal complete native-edge runs between fixed source/junction endpoints."""
    all_ids={s for p in parents for s in p['source_ids']}
    eligible=all_ids-set(fixed);runs=[]
    for parent in parents:
        for edges in edge_runs(parent,eligible):
            members=sorted(s for e in edges for s in e['source_alias_ids'])
            key='ER-'+digest('\n'.join(members).encode())[:16]
            start,end=edges[0]['start_decimal_mm'],edges[-1]['end_decimal_mm']
            contacts=[]
            for endpoint in (start,end):
                for edge in parent['ordered_source_edges']:
                    if edge not in edges and endpoint in (edge['start_decimal_mm'],edge['end_decimal_mm']):
                        for sid in edge['source_alias_ids']:
                            if sid in fixed:contacts.append(dict(fixed_source_id=sid,point_decimal_mm=endpoint))
            runs.append(dict(path_id=key,parent_route_id=parent['path_id'],source_ids=members,
                source_sha256=source_sha256,uniform_original_width_mm=parent['uniform_original_width_mm'],
                ordered_source_edges=edges,terminal_points_decimal_mm=[start,end],original_fixed_source_ports=contacts,original_width_transition_ports=parent.get('original_width_transition_ports',[]),
                primitive_trimming='NONE',route_type='CLOSED_UNIFORM_SOURCE_ROUTE' if start==end else 'OPEN_UNIFORM_SOURCE_ROUTE'))
    represented=[s for r in runs for s in r['source_ids']]
    if len(represented)!=len(set(represented)) or set(represented)!=eligible:
        raise ValueError('C03_EXPOSED_NATIVE_PARTITION_INCOMPLETE')
    return runs


def primary_groups(paths,relations,byid,tree,ids,cores,native_by_id):
    """Reuse the accepted source-station cohort recipe and all hard equalities."""
    links=[];unqualified=[];keys=sorted(paths);ct=STRtree([cores[k] for k in keys])
    for i,a in enumerate(keys):
        for j in sorted(int(v) for v in ct.query(cores[a],predicate='intersects') if int(v)>i):
            b=keys[j]
            if cores[a].intersection(cores[b]).area>0:
                witnesses=[]
                for sa in paths[a]['source_ids']:
                    for sb in paths[b]['source_ids']:
                        ra,rb=native_by_id[sa],native_by_id[sb]
                        if ra['kind']!= 'segment' or rb['kind']!='segment':continue
                        def stroke(s,r):return dict(id=s,start_mm=r['route_points_mm'][0],end_mm=r['route_points_mm'][-1],width_mm=r['width_mm'],geometry=byid[s])
                        witness=overlapping_parallel_fill_witness(stroke(sa,ra),stroke(sb,rb))
                        if witness:witnesses.append(witness)
                if witnesses:links.append(dict(member_a=a,member_b=b,reason='SOURCE_VERIFIED_LONGITUDINAL_OVERLAP_ONE_OPERATION',native_witnesses=witnesses))
                else:unqualified.append(dict(member_a=a,member_b=b,reason='BRANCH_CAP_CONTACT_NO_LONGITUDINAL_SCALE_WITNESS',finite_copper_interaction='REQUIRED_UNCHANGED'))
    parents={}
    for k,p in paths.items():parents.setdefault(p['parent_route_id'],[]).append(k)
    for parent,children in sorted(parents.items()):
        for child in sorted(children)[1:]:links.append(dict(member_a=min(children),member_b=child,reason='ORIGINAL_TRACE_COMMON_SCALE',parent_route_id=parent))
    hard=relation_groups(keys,[(r['member_a'],r['member_b']) for r in links])
    units={'HU-'+digest('\n'.join(row).encode())[:16]:row for row in hard}
    owner={k:u for u,row in units.items() for k in row}
    ucores={u:unary_union([cores[k] for k in row]) for u,row in units.items()}
    usources={u:{s for k in row for s in paths[k]['source_ids']} for u,row in units.items()}
    supports=[];family_rejections=[];fallback=[]
    for r in relations:
        a,b=owner[r['path_a']],owner[r['path_b']]
        if a==b:continue
        wa,wb=paths[r['path_a']]['uniform_original_width_mm'],paths[r['path_b']]['uniform_original_width_mm']
        if max(wa,wb)>2*min(wa,wb)+1e-12:
            family_rejections.append(r);continue
        if r['source_kind_a']!='segment' or r['source_kind_b']!='segment':
            score=r.get('shared_projected_length_mm',r.get('shared_run_mm',r.get('shared_sampled_run_mm',0)))
            if score>0:fallback.append(dict(candidate_id='CV-'+digest(canonical(r))[:16],members=sorted([a,b]),edges=[sorted([a,b])],score=score,priority=1))
            continue
        pts=r['native_points_a'];p,q=pts;length=math.dist(p,q)
        u=[(q[i]-p[i])/length for i in (0,1)]
        if u[0]<0 or (u[0]==0 and u[1]<0):u=[-v for v in u]
        supports.append(dict(unit_a=a,unit_b=b,points_a=pts,points_b=r['native_points_b'],direction=u,source_a=r['source_a'],source_b=r['source_b']))
    dot=lambda p,u:sum(x*y for x,y in zip(p,u))
    def at(points,u,t):
        a,b=points;den=dot([b[i]-a[i] for i in (0,1)],u)
        if abs(den)<1e-12:return None
        f=(t-dot(a,u))/den;return [a[i]+f*(b[i]-a[i]) for i in (0,1)]
    candidates={r['candidate_id']:r for r in fallback};stations={r['candidate_id']:dict(candidate_id=r['candidate_id'],basis='Retained complete native curved parallel pair; secondary candidate',units=r['members']) for r in fallback}
    for seed in supports:
        u=seed['direction'];v=[-u[1],u[0]]
        lo=max(min(dot(p,u) for p in seed[k]) for k in ('points_a','points_b'))
        hi=min(max(dot(p,u) for p in seed[k]) for k in ('points_a','points_b'))
        if hi<=lo:continue
        t=(lo+hi)/2;positions={};ports={};evidence=[]
        def port(unit,p):
            transverse=dot(p,v);existing=positions.setdefault(unit,[])
            for position,name in existing:
                if abs(position-transverse)<=1e-7:return name
            name=unit+':port:'+str(len(existing));existing.append((transverse,name));ports[name]=unit;return name
        for s in supports:
            if abs(dot(s['direction'],u))<math.cos(math.radians(1.)):continue
            low=max(min(dot(p,u) for p in s[k]) for k in ('points_a','points_b'))
            high=min(max(dot(p,u) for p in s[k]) for k in ('points_a','points_b'))
            if not low<=t<=high or high-low<=0:continue
            pa,pb=at(s['points_a'],u,t),at(s['points_b'],u,t)
            if pa is None or pb is None:continue
            a,b=s['unit_a'],s['unit_b'];cross=LineString([pa,pb]).difference(ucores[a].union(ucores[b]))
            if cross.is_empty:continue
            excluded=usources[a]|usources[b]
            if any(ids[int(i)] not in excluded for i in tree.query(cross,predicate='intersects')):continue
            evidence.append(dict(port_a=port(a,pa),port_b=port(b,pb),unit_a=a,unit_b=b,source_a=s['source_a'],source_b=s['source_b'],surface_gap_mm=cross.length,shared_projected_length_mm=high-low,cross_section_mm=[pa,pb]))
        evidence,rejected=station_spacing_links(evidence)
        for component in relation_groups(sorted(ports),sorted(set(tuple(sorted((r['port_a'],r['port_b']))) for r in evidence))):
            members=sorted({ports[p] for p in component})
            if len(members)<2 or len(members)!=len(component):continue
            support=[r for r in evidence if r['port_a'] in component and r['port_b'] in component]
            edges=sorted(set(tuple(sorted((r['unit_a'],r['unit_b']))) for r in support));score=sum(r['shared_projected_length_mm'] for r in support)
            key='CS-'+digest(canonical(route_evidence([u,t,members,edges])))[:16]
            candidates[key]=dict(candidate_id=key,members=members,edges=edges,score=score,priority=0)
            stations[key]=dict(candidate_id=key,direction=u,station_mm=t,support=support,spacing_rejections=rejected)
    chosen=choose_primary_cohorts(sorted(units),list(candidates.values()));groups=[]
    for c in chosen:
        members=sorted('route:'+k for u in c['units'] for k in units[u]);gid='PG-'+digest('\n'.join(members).encode())[:16]
        groups.append(dict(group_id=gid,members=members))
    return groups,dict(hard_links=links,unqualified_overlap_scale_links=unqualified,hard_units=units,primary_candidates=[stations[k] for k in sorted(stations)],primary_assignment=chosen,width_family_membership_rejections=family_rejections,
        scope='Membership selection only; every omitted relationship remains a full finite-copper interaction')


def qualify(raw,manifest,original_blobs,current_blobs,*,selection):
    if selection is None:raise ValueError('C03_EXPLICIT_NATIVE_IMAGE_WINDOW_REQUIRED')
    source=digest(raw);meta={r['id']:r for r in manifest}
    if source!=selection['source_sha256'] or set(meta)!=set(original_blobs) or set(meta)!=set(current_blobs) or any(digest(original_blobs[s])!=meta[s]['geometry_sha256'] for s in meta):
        raise ValueError('C03_WIDTH_COMPLETE_SOURCE_BINDING_CHANGED')
    native=native_rows(raw,manifest)
    if any(current_blobs[r['source_id']]!=original_blobs[r['source_id']] for r in native):
        raise ValueError('C03_WIDTH_CHANGED_SOURCE_PATH_UNSUPPORTED')
    if any(r['kind'] not in ('segment','arc') for r in native):raise ValueError('C03_WIDTH_GRAPHIC_STROKE_UNSUPPORTED')
    parents=route_evidence(junction_source_paths(native,[r['source_id'] for r in native]))
    roles=reviewed_roles(raw,manifest,original_blobs);fixed=set(roles['protected'])
    # Degenerate sources remain fixed context; they cannot acquire a route.
    fixed.update(s for p in parents if p['route_type']=='DEGENERATE_SOURCE_STROKE_CONTEXT' for s in p['source_ids'])
    runs=exposed_runs(parents,fixed,source)
    byid={s:from_wkb(current_blobs[s]) for s in sorted(meta)};ids=sorted(byid);tree=STRtree([byid[s] for s in ids])
    cores={p['path_id']:unary_union([byid[s] for s in p['source_ids']]) for p in runs}
    region=window(selection);crop=box(*selection['bounds_mm'])
    # The crop seeds complete original parents; remote eligible runs remain in
    # the same hard unit. A remote blocker never disappears from the group.
    selected_parents={p['parent_route_id'] for p in runs if cores[p['path_id']].intersects(crop)}
    selected={p['path_id']:p for p in runs if p['parent_route_id'] in selected_parents}
    for p in runs:
        for contact in p['original_fixed_source_ports']:
            if not cores[p['path_id']].intersects(byid[contact['fixed_source_id']]):raise ValueError('C03_NATIVE_FIXED_PORT_CONTACT_MISSING')
    entries=[r for r in native if any(r['source_id'] in p['source_ids'] for p in selected.values()) and r['route_points_mm'][0]!=r['route_points_mm'][-1]]
    owner={s:p for p,r in selected.items() for s in r['source_ids']}
    lines=[LineString(r['route_points_mm']) for r in entries];lt=STRtree(lines);relations=[];blocked=[]
    max_width=max((r['width_mm'] for r in entries),default=0)
    for i,a in enumerate(entries):
        for j in sorted(int(v) for v in lt.query(lines[i].buffer(.5+(a['width_mm']+max_width)/2)) if int(v)>i):
            b=entries[j];pa,pb=owner[a['source_id']],owner[b['source_id']]
            if pa==pb:continue
            minimum_shared=max(.02,min(a['width_mm'],b['width_mm']));maximum_distance=.5+(a['width_mm']+b['width_mm'])/2
            rel=(parallel_relation(a['route_points_mm'],b['route_points_mm'],min_shared_length_mm=minimum_shared,max_transverse_distance_mm=maximum_distance) if a['kind']==b['kind']=='segment' else parallel_curve_relation(a['route_points_mm'],b['route_points_mm'],min_shared_run_mm=minimum_shared,max_center_distance_mm=maximum_distance,allow_remote_intersections=True,samples=min(2049,max(49,int(min(lines[i].length,lines[j].length)/minimum_shared*4)+1))))
            if rel is None:continue
            cross=LineString(rel['midpoint_cross_section_mm']).difference(cores[pa].union(cores[pb]))
            if cross.is_empty:continue
            excluded=set(selected[pa]['source_ids'])|set(selected[pb]['source_ids'])
            blockers=sorted(ids[int(k)] for k in tree.query(cross,predicate='intersects') if ids[int(k)] not in excluded)
            row=dict(path_a=pa,path_b=pb,source_kind_a=a['kind'],source_kind_b=b['kind'],source_a=a['source_id'],source_b=b['source_id'],native_points_a=a['route_points_mm'],native_points_b=b['route_points_mm'],blocker_source_ids=blockers,**rel)
            (blocked if blockers else relations).append(row)
    groups,cohorts=primary_groups(selected,relations,byid,tree,ids,cores,{r['source_id']:r for r in native})
    records=[];lookup={}
    for p in runs:
        pid=p['path_id'];core=cores[pid];members=set(p['source_ids'])
        neighbors=sorted(ids[int(i)] for i in tree.query(core,predicate='intersects') if ids[int(i)] not in members)
        covering=unary_union([byid[s] for s in neighbors]);covered=covering.covers(core)
        caps=[]
        for sid in p['source_ids']:
            x0,y0,x1,y1=byid[sid].bounds;pad=.25*meta[sid]['trace_width_mm']+ERROR_MM
            if not region.covers(box(x0-pad,y0-pad,x1+pad,y1+pad)):caps.append(sid)
        status='KEEP_OUTSIDE_CROP' if pid not in selected else 'KEEP_CROP_BOUNDARY' if caps else 'KEEP_FULLY_COVERED' if covered else 'ADMIT_COMPLETE_NATIVE_ROUTE'
        record=dict(path=p,disposition=status,reason=None,original_core_sha256=digest(to_wkb(core)),original_core_area_mm2=core.area,exposed_area_mm2=core.difference(covering).area,coverage_source_ids=neighbors,coverage_union_sha256=digest(to_wkb(covering)),maximum_crop_blocker_source_ids=caps)
        records.append(record);lookup['route:'+pid]=record
    # Fully covered members stay represented in their complete hard/cohort unit
    # and are checked if a peer grows. Only a real crop blocker holds the unit.
    kept_groups=[];admitted=set()
    for group in groups:
        rows=[lookup[s] for s in group['members']]
        if any(r['disposition'] in ('KEEP_CROP_BOUNDARY','KEEP_OUTSIDE_CROP') for r in rows):
            for r in rows:
                if r['disposition']!='KEEP_CROP_BOUNDARY':r['disposition']='KEEP_CROP_GROUP_BOUNDARY'
        elif any(r['disposition']=='ADMIT_COMPLETE_NATIVE_ROUTE' for r in rows):
            if any(r['disposition']=='KEEP_FULLY_COVERED' for r in rows):raise ValueError('C03_COVERED_GROUP_NOT_QUALIFIED')
            kept_groups.append(group);admitted.update(group['members'])
            for r in rows:r['disposition']='ADMIT_COMPLETE_NATIVE_ROUTE'
    # Account for protected fixed native occurrences explicitly, never omit them.
    records.extend(dict(source_ids=[s],disposition='KEEP_REVIEWED_FIXED_SOURCE',reason='Fixed original contributor; never selected or split') for s in sorted(fixed))
    assigned=[s for r in records for s in (r['path']['source_ids'] if r.get('path') else r['source_ids'])]
    nativeids={r['source_id'] for r in native}
    if set(assigned)!=nativeids or len(assigned)!=len(nativeids):raise ValueError('C03_WIDTH_TRACE_PARTITION_INCOMPLETE')
    admitted_paths=[p for p in runs if 'route:'+p['path_id'] in admitted];represented={s for p in admitted_paths for s in p['source_ids']}
    if represented&fixed:raise ValueError('C03_FIXED_SOURCE_SELECTED_FOR_WIDTH')
    from src.c03_recovery import load_intent
    from tools.t01_operator_host import ROOT,read
    definitions=load_intent(ROOT,read(ROOT/'contracts/operator/c03_coverage_recovery.json'))['T04_CONSTRUCTION']
    runmap={p['path_id']:p for p in runs};obligations=[]
    for definition in definitions:
        pid=definition['component_id'];p=runmap.get(pid)
        if definition['factor']>1 and (p is None or p['source_ids']!=sorted(definition['complete_source_ids'])):
            raise ValueError('C03_ORIGINAL_WIDTH_NATIVE_MEMBERSHIP_NOT_RECONSTRUCTED:'+pid)
        obligations.append(dict(reference_id=pid,required_factor=definition['factor'],required_positive=definition['factor']>1,source_ids=definition['complete_source_ids'],disposition=lookup['route:'+pid]['disposition'] if p else 'REFERENCE_KEEP',fresh_native_run_reconstructed=p is not None))
    return dict(schema='u03-native-width-admission/1',c03_width_family=FAMILY,source_sha256=source,native_rows=native,source_objects=len(meta),trace_occurrences=len(native),paths=records,admitted_paths=admitted_paths,groups=kept_groups,relations=relations,blocked_relations=blocked,unsupported=[],classifications=dict(Counter(r['disposition'] for r in records)),complete_trace_coverage=True,protected_source_ids=sorted(set(meta)-represented),reviewed_source_roles=roles,cohort_proof=cohorts,reference_width_obligations=obligations,source_parent_count=len(parents),source_run_count=len(runs),scope='Complete native exposed runs; original parent hard equalities; primary parallel cohorts; unchanged max-envelope crop and finite-copper rules')
