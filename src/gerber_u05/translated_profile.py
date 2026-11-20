"""Opt-in bounded whole-route translation and profiled widths in actual T04.

One rigid pose and one aggregate copper body per native route. Source aliases
retain immutable identities/refs; both vacated and added trace copper are bound
in a motion ledger. No growth-only core predicate is waived: native checks use
an explicitly certified translated source reference, retaining predecessor voids.
"""
from collections import OrderedDict
from contextlib import contextmanager
from pathlib import Path
from time import perf_counter
import copy,math
import numpy as np
from shapely import STRtree,to_wkb,from_wkb,is_valid_reason
from shapely.errors import GEOSException
from shapely.geometry import LineString,Point,Polygon,box
from shapely.affinity import translate
from shapely.ops import unary_union,nearest_points
from src import component_clearance as cc,source_channel_scope as sc,pin_separation as pin
from src.t04_topology import SourceVoids
from src.component_hole_lineage import hole_polygons
from src.original_copper_owners import OriginalOwners
from . import pipeline as p,limiting_growth_v2 as legacy
from .limiting_growth import owner_material,working_scope
from .limiting_math import MARGIN,GUARD
from .profile_candidates import CandidateCache,CandidateRecipe,DEFAULT_CACHE_BYTES

SCHEMA='t04-translated-route-profile/2'
ENTRY='t04-translated-profile-entry'
ALIAS='t04-translated-source-alias/1'


class ProfileGeometryRejected(ValueError):
    """An optional profile could not be constructed as valid exact copper."""


def parameters(rule,route_ids):
    if rule.get('schema')!=SCHEMA:raise ValueError('T04_TRANSLATION_SCHEMA_CHANGED')
    if rule.get('scope')=='BOUNDED':
        if not route_ids or len(set(route_ids))!=len(route_ids) or len(route_ids)>128:
            raise ValueError('T04_TRANSLATION_EXPLICIT_BOUNDED_SCOPE_REQUIRED')
    elif rule.get('scope')=='FULL_BOARD':
        if route_ids is not None:raise ValueError('T04_FULL_BOARD_MUST_USE_COMPLETE_SOURCE_SCOPE')
        from .profile_readiness import require
        require(rule['qualification_manifest'],rule)
    else:raise ValueError('T04_TRANSLATION_EXPLICIT_SCOPE_REQUIRED')
    if rule.get('standalone_profile') and any(k in rule for k in ('baseline_seed','baseline_seed_sha256','baseline_reference')):raise ValueError('T04_STANDALONE_REFERENCE_INPUT_FORBIDDEN')
    tol=rule.get('width_variation_limit')
    if type(tol) not in (int,float) or not math.isfinite(tol) or not 0<=tol<=.25:raise ValueError('T04_WIDTH_VARIATION_PARAMETER_INVALID')
    if rule.get('maximum_translation_mm',.025)!=.025 or rule.get('transition_length_mm',.05)!=.05:raise ValueError('T04_TRANSLATION_BOUNDED_PARAMETERS_CHANGED')
    return float(tol)


def band_mask(first,last,low,high):
    span=.05;xs=np.unique(np.r_[np.linspace(first-span,first,12),first,last,np.linspace(last,last+span,12)]);radii=[]
    for x in xs:
        u=min(1.,max(0.,(first-x)/span,(x-last)/span));u=u*u*(3-2*u);radii.append(low/2+(high-low)*u/2)
    allowed=Polygon([(float(x),v) for x,v in zip(xs,radii)]+[(float(x),-v) for x,v in reversed(list(zip(xs,radii)))])
    return box(first-span,-.25,last+span,.25).difference(allowed)


def oriented_mask(line,pose,low,high):
    from shapely.affinity import affine_transform
    a,b=np.array(line.coords[0]),np.array(line.coords[-1]);length=np.linalg.norm(b-a)
    if length<.05:return Polygon()
    u=(b-a)/length;n=np.array([-u[1],u[0]]);origin=a+pose
    return affine_transform(band_mask(0.,length,low,high),[u[0],n[0],u[1],n[1],origin[0],origin[1]])


def profile_body(core,width,low,high,pose,line,forbidden,*,envelope=False):
    moved=translate(core,xoff=pose[0],yoff=pose[1]);d0=max(0.,(low-width)/2);d1=max(0.,(high-width)/2)
    if d1<=0:return moved.buffer(MARGIN,quad_segs=128) if envelope and math.hypot(*pose)>0 else moved
    lower=moved.buffer(max(d0,min(d1,1e-10)),quad_segs=128)
    # At equal widths the upper buffer is exactly the lower buffer. Clipping
    # and re-unioning a subset is redundant and can introduce overlay slivers
    # on coincident boundaries (the saved full-board failure did exactly this).
    if low==high:body=lower
    else:
        upper=moved.buffer(d1,quad_segs=128)
        mask=oriented_mask(line,np.array(pose),low,high)
        try:
            optional=upper.difference(forbidden).difference(mask)
            if not optional.is_valid:
                raise ProfileGeometryRejected('T04_PROFILE_OPTIONAL_OVERLAY_INVALID:'+is_valid_reason(optional))
            body=unary_union([lower,optional])
        except GEOSException as error:
            raise ProfileGeometryRejected('T04_PROFILE_OPTIONAL_OVERLAY_FAILED:'+str(error)) from error
    if not body.is_valid or not body.covers(moved):raise ValueError('T04_TRANSLATED_CORE_NOT_COVERED')
    if low!=high and (lower.difference(body).area>1e-12 or body.difference(upper).area>1e-12):raise ValueError('T04_TRANSLATED_WIDTH_BAND_CHANGED')
    return body.buffer(MARGIN,quad_segs=128) if envelope else body


def candidate_neighbors(paths,data,cores):
    """Conservative, stable neighbors for every eligible pose and candidate.

    Bounds include both bodies and deltas, plus the initial unchanged core.
    A pair outside these bounds would be skipped by both original envelope
    tests for every possible chosen candidate. Exact checks remain unchanged.
    """
    keys=sorted(paths);bounds=[]
    for r in keys:
        boxes=[cores[r].bounds]
        for c in data[r]['candidates']:
            if isinstance(c,CandidateRecipe):boxes.append(c.geometry.bounds)
            else:boxes.extend(g.bounds for g in (c['body'],c['delta']) if not g.is_empty)
        bounds.append(box(min(b[0] for b in boxes),min(b[1] for b in boxes),
                          max(b[2] for b in boxes),max(b[3] for b in boxes)))
    tree=STRtree(bounds)
    return {r:[keys[i] for i in sorted(map(int,tree.query(bounds[k],predicate='dwithin',distance=GUARD+2*MARGIN+1e-12))) if keys[i]!=r]
            for k,r in enumerate(keys)}


def plan(rows,current,original,paths,roles,context,settings,seed,variation,progress=None,*,corridor_only=False,candidate_cache_bytes=DEFAULT_CACHE_BYTES):
    cache=CandidateCache(candidate_cache_bytes)
    start=perf_counter();used={s for ss in paths.values() for s in ss};cores={r:unary_union([original[s] for s in ss]) for r,ss in paths.items()}
    fixedids=sorted(set(rows)-used-set(roles));fixed=[current[s] for s in fixedids if not current[s].is_empty];fixedids=[s for s in fixedids if not current[s].is_empty];tree=STRtree(fixed)
    owners={r:context.ids[ss[0]] for r,ss in paths.items()};data={};rejections=[]
    if any(not core.is_valid for core in cores.values()):raise ValueError('T04_TRANSLATED_SOURCE_CORE_INVALID')
    for index,(r,ss) in enumerate(sorted(paths.items()),1):
        width=rows[ss[0]]['metadata']['minimum_caliper_mm'];cap=min(width*settings.maximum_factor,width+settings.maximum_total_width_increase_mm)
        if any(rows[s]['metadata']['minimum_caliper_mm']!=width or context.ids[s]!=owners[r] for s in ss):raise ValueError('T04_TRANSLATION_ROUTE_IDENTITY_CHANGED')
        window=(cap-width)/2+.025+GUARD+2*MARGIN
        hits=sorted(map(int,tree.query(cores[r],predicate='dwithin',distance=window)))
        foreign=[fixed[i] for i in hits if context.ids.get(fixedids[i],())!=owners[r] or fixedids[i] in getattr(context,'frame_ids',())]
        own=[fixed[i] for i in hits if context.ids.get(fixedids[i],())==owners[r]]
        fg=unary_union(foreign);forbidden=unary_union([g.buffer(GUARD+2*MARGIN,quad_segs=128) for g in foreign])
        lines=[LineString(rows[s]['metadata']['route_points_mm']) for s in ss]
        straight=[g for s,g in zip(ss,lines) if rows[s]['metadata']['route_kind']=='segment'];line=max(straight or lines,key=lambda g:g.length)
        a,b=np.array(line.coords[0]),np.array(line.coords[-1]);u=b-a
        u=np.array([1.,0.]) if np.linalg.norm(u)<1e-12 else u/np.linalg.norm(u);normal=np.array([-u[1],u[0]])
        if fg.is_empty:away=normal.copy()
        else:
            a,b=nearest_points(cores[r],fg);away=np.array(a.coords[0])-np.array(b.coords[0]);norm=np.linalg.norm(away);away=normal.copy() if norm<1e-12 else away/norm
        directions=[normal,-normal,away]
        for n in (normal,-normal):
            v=n+away
            if np.linalg.norm(v)>1e-12:directions.append(v/np.linalg.norm(v))
        poses=[(0.,0.)]
        for direction in directions:
            for size in (.005,.015):poses.append(tuple(float(v) for v in direction*size))
        poses=list(dict.fromkeys(poses))
        fixedown=unary_union(own);ports=list(OriginalOwners(unary_union(cc.surfaces(cores[r].intersection(fixedown)))).owners) if cores[r].intersection(fixedown).area>0 else []
        candidates=[]
        for pose in poses:
            moved=translate(cores[r],xoff=pose[0],yoff=pose[1])
            if any(moved.intersection(fixedown).intersection(port.buffer(.025,quad_segs=32)).area<=0 for port in ports):continue
            delta=moved.difference(context.cores[owners[r][0]])
            if not fg.is_empty and not delta.is_empty and delta.distance(fg)<GUARD+MARGIN-1e-12:continue
            # Use both the source-normalized seed and cap-limited profile bands.
            widths=sorted(set([width,min(cap,width+2*seed[r]),max(width,cap/(1+variation)),cap]+([width+(cap-width)*k/10 for k in range(11)] if corridor_only else [])),reverse=True)
            for low in widths:
                high=low if corridor_only else min(cap,low*(1+variation));base=moved if low==width else moved.buffer((low-width)/2,quad_segs=128)
                exposed=base.difference(context.cores[owners[r][0]])
                if not fg.is_empty and not exposed.is_empty and exposed.distance(fg)<GUARD+(2*MARGIN if corridor_only else MARGIN)-1e-12:continue
                try:body=base if corridor_only else profile_body(cores[r],width,low,high,pose,line,forbidden)
                except ProfileGeometryRejected as error:
                    rejections.append(dict(route=r,translation_mm=list(pose),low_mm=low,high_mm=high,reason=str(error)))
                    continue
                except ValueError:continue
                if any(body.intersection(fixedown).intersection(port.buffer(.025,quad_segs=32)).area<=0 for port in ports):continue
                geometry=cache.record(body,body.difference(context.cores[owners[r][0]]))
                candidates.append(CandidateRecipe(pose,low,high,(round(low/width,10),round(body.area,9),-math.hypot(*pose)),geometry))
        identity=cache.record(cores[r],Polygon())
        candidates.append(CandidateRecipe((0.,0.),width,width,(1.,round(cores[r].area,9),0.),identity,identity=True))
        # All admissible recipes survive. Cache capacity never limits search
        # breadth, even for an oversized route or a zero-byte cache.
        data[r]=dict(width=width,cap=cap,line=line,foreign=fg,forbidden=forbidden,candidates=sorted(candidates,key=lambda c:c.score,reverse=True),ports=ports,fixedown=fixedown)
        if progress and (index==1 or index%32==0 or index==len(paths)):
            progress(dict(event='motion_candidates',index=index,routes=len(paths),geometry_rejections=len(rejections)))
    neighbors=candidate_neighbors(paths,data,cores)
    chosen={r:dict(pose=(0.,0.),low=data[r]['width'],high=data[r]['width'],body=cores[r],delta=Polygon()) for r in paths};pair_checks=0
    def rebuild(r,c):
        if c.identity:return cores[r],Polygon()
        d=data[r]
        if corridor_only:
            moved=translate(cores[r],xoff=c.pose[0],yoff=c.pose[1])
            body=moved if c.low==d['width'] else moved.buffer((c.low-d['width'])/2,quad_segs=128)
        else:body=profile_body(cores[r],d['width'],c.low,c.high,c.pose,d['line'],d['forbidden'])
        return body,body.difference(context.cores[owners[r][0]])
    for sweep in range(2):
        for idx,r in enumerate(sorted(paths)):
            for recipe in data[r]['candidates']:
                c=recipe.selected(cache.get(recipe.geometry,lambda:rebuild(r,recipe)))
                okay=True
                for other in neighbors[r]:
                    if other==r or owners[other]==owners[r]:continue
                    a=c['delta'];b=chosen[other]['delta']
                    if a.envelope.distance(chosen[other]['body'].envelope)>GUARD+2*MARGIN and b.envelope.distance(c['body'].envelope)>GUARD+2*MARGIN:continue
                    pair_checks+=1
                    if (not a.is_empty and a.distance(chosen[other]['body'])<GUARD+2*MARGIN-1e-12) or (not b.is_empty and b.distance(c['body'])<GUARD+2*MARGIN-1e-12):okay=False;break
                if okay:chosen[r]=c;break
            if progress:progress(dict(event='motion_plan',route=r,sweep=sweep,index=idx+1,routes=len(paths)))
    receipt=dict(schema=SCHEMA,width_variation_limit=variation,maximum_translation_mm=.025,transition_length_mm=.05,route_plans={r:dict(translation_mm=[float(v) for v in c['pose']],corridor_width_mm=c['low'],outer_width_ceiling_mm=c['high'],source_width_mm=data[r]['width'],source_width_cap_mm=data[r]['cap'],candidate_count=len(data[r]['candidates']),fixed_contact_components=len(data[r]['ports'])) for r,c in chosen.items()},planning_seconds=perf_counter()-start,exact_pair_checks=pair_checks,candidate_geometry_rejections=rejections)
    # Budget-dependent counters are operational diagnostics, not geometry or
    # native proof authority. They cannot alter the construction receipt.
    if progress:progress(dict(event='motion_candidate_cache',**cache.diagnostics()))
    cache.clear()
    for value in data.values():value.pop('candidates')
    return chosen,data,cores,receipt


class Construction(legacy.Construction):
    relocation=True
    def __init__(self,paths,original,rows,chosen,data,oldcores,receipt,admission,settings,progress):
        targets={r:(c['high']-data[r]['width'])/2 for r,c in chosen.items()}
        super().__init__(paths,original,rows,targets,settings=settings,receipt=receipt,admission=admission,progress=progress)
        self.settings=settings
        self.chosen=chosen;self.data=data;self.oldcores=oldcores;self.cores={r:translate(oldcores[r],xoff=c['pose'][0],yoff=c['pose'][1]) for r,c in chosen.items()};self.shape_cache=OrderedDict();self.shape_bytes=0;self.profiles=None
    def validate_input(self,current):
        for r,ss in self.paths.items():
            reference=self.data[r]['baseline_body'] if self.receipt.get('side_specific_growth') else self.cores[r]
            if r not in current or not current[r].equals_exact(reference,0):raise ValueError('T04_TRANSLATED_ENTRY_BODY_CHANGED')
            if any(not current[s].is_empty for s in ss):raise ValueError('T04_TRANSLATED_ENTRY_ALIAS_NOT_ZERO')
    def route(self,r,f,envelope):
        if f==1 and self.receipt.get('side_specific_growth'):
            from .side_profile import body_at
            return body_at(self.oldcores[r],self.data[r]['width'],self.receipt['route_plans'][r],self.data[r],f,envelope=envelope)
        if f==1:return self.cores[r].buffer(MARGIN,quad_segs=128) if envelope and math.hypot(*self.chosen[r]['pose'])>0 else self.cores[r]
        key=(r,f,envelope)
        if key not in self.shape_cache:
            c=self.chosen[r];d=self.data[r]
            if self.receipt.get('side_specific_growth'):
                from .side_profile import body_at
                body=body_at(self.oldcores[r],d['width'],self.receipt['route_plans'][r],d,f,envelope=envelope)
            elif 'baseline_profile' in self.receipt['route_plans'][r] or 'construction_floor_profile' in self.receipt['route_plans'][r]:
                from .profile_refinement import body_at
                body=body_at(self.oldcores[r],d['width'],self.receipt['route_plans'][r],d,f,envelope=envelope)
            else:
                t=(f-1)/(.5);low=d['width']+(c['low']-d['width'])*t;high=d['width']+(c['high']-d['width'])*t
                body=profile_body(self.oldcores[r],d['width'],low,high,c['pose'],d['line'],d['forbidden'],envelope=envelope)
            size=3*len(to_wkb(body))+256
            while self.shape_cache and self.shape_bytes+size>64*1024**2:
                _,(_,weight)=self.shape_cache.popitem(last=False);self.shape_bytes-=weight
            if size>64*1024**2:return body
            self.shape_cache[key]=(body,size);self.shape_bytes+=size
        self.shape_cache.move_to_end(key)
        return self.shape_cache[key][0]
    def effective(self,s,f):
        from .profile_refinement import band_at
        r=self.owner[s];return band_at(self.receipt['route_plans'][r],f)[1]/self.data[r]['width']
    def describe_rung(self,r,rung):
        from .profile_refinement import band_at
        width=self.data[r]['width'];candidate=self.settings.rung(width,rung)
        low,high=band_at(self.receipt['route_plans'][r],candidate['factor'])
        increase=high-width
        allowed=(width<=low<=high and high<=width*self.settings.maximum_factor+1e-12
                 and increase<=self.settings.maximum_total_width_increase_mm+1e-12)
        # The factor is progress to a pre-capped shape, not a second physical
        # widening of the source. Reporting source_width*progress rejected
        # valid later rungs of wider traces before geometry was even checked.
        candidate.update(resulting_width_mm=high,total_width_increase_mm=increase,
                         per_side_offset_mm=increase/2,percentage_growth=increase/width*100,
                         within_growth_limits=allowed,
                         blocking_reason=None if allowed else 'PROFILE_WIDTH_BAND_LIMIT',
                         factor_semantics='PROFILE_PROGRESS; widths are physical ceilings')
        return candidate
    def solve(self,*args,**kwargs):
        value=super().solve(*args,**dict(kwargs,describe_rung=self.describe_rung));value['schema']=SCHEMA;value['geometry_family']='single-body-translated-route-profile';return value
    def publication(self,store,current,selected):
        after=dict(current);metadata={};additions=[];aliases={};routes={}
        for r in sorted(self.paths):
            body=self.route(r,selected[r],False);ref=p.geomref(store,body);movedref=p.geomref(store,self.cores[r]);empty=p.geomref(store,Polygon());source_refs={s:self.rows[s]['original_ref'] for s in self.paths[r]}
            route=dict(body_ref=ref,translated_reference_ref=movedref,input_route_ref=p.geomref(store,self.oldcores[r]),source_refs=source_refs,translation_mm=[float(v) for v in self.chosen[r]['pose']],selected_progress=selected[r],removed_trace_ref=p.geomref(store,self.oldcores[r].difference(body)),added_trace_ref=p.geomref(store,body.difference(self.oldcores[r])))
            if 'baseline_body' in self.data[r]:
                key='construction_floor_body_ref' if 'construction_floor_profile' in self.receipt['route_plans'][r] else 'baseline_body_ref'
                route[key]=p.geomref(store,self.data[r]['baseline_body'])
            if self.receipt.get('side_specific_growth'):
                route['side_profile_ref']=store.put_json('t04-side-profile',self.data[r]['side_recipe'])
                self.receipt['route_plans'][r]['side_profile_recipe_sha256']=route['side_profile_ref']['sha256']
            routes[r]=route
            for s in self.paths[r]:
                after[s]=Polygon();alias=dict(schema=ALIAS,source_id=s,route_id=r,original_ref=source_refs[s],body_ref=ref);aliases[s]=alias;metadata[s]=dict(self.rows[s]['metadata'],translated_route_alias=alias)
            body_md=dict(reference_source_ids=self.paths[r],original_channel_id=self.receipt['route_owners'][r],original_source_sha256=self.receipt['source_sha256'],original_width_mm=self.data[r]['width'],nominal_width_mm=self.data[r]['width'],translated_profile=dict(schema=SCHEMA,input_route_ref=route['input_route_ref'],translation_mm=route['translation_mm'],source_refs=source_refs))
            if r in after:after[r]=body;metadata[r]=body_md
            else:additions.append(dict(source_id=r,kind='trace',original_ref=movedref,geometry_ref=ref,metadata=body_md))
        self.receipt['published_routes']=routes;self.receipt['source_aliases']=aliases
        self.receipt['source_identity_policy']='IMMUTABLE_SOURCE_REFS_PLUS_EXPLICIT_RELOCATED_ALIAS_TO_ONE_ROUTE_BODY'
        ledger_ref=store.put_json('t04-route-motion',self.receipt)
        self.receipt_ref=ledger_ref
        return after,metadata,additions,ledger_ref


def resolve_operands(store,scene):
    entries=[v for v in scene['lineage'] if v.get('stage')=='t04-translated-profile-published']
    if not entries:raise ValueError('T04_TRANSLATED_ALIAS_AUTHORITY_MISSING')
    receipt=store.get_json(entries[-1]['receipt_ref'],kind='t04-route-motion')
    if receipt['schema'] not in (SCHEMA,'t04-translated-route-profile/1') or receipt['source_sha256']!=scene['source_sha256']:raise ValueError('T04_TRANSLATED_ALIAS_SOURCE_CHANGED')
    from src.stage_abi.scene import geometry
    rows={r['source_id']:r for r in scene['objects']};current={};original={}
    for sid,row in rows.items():
        original[sid]=geometry(store,row['original_ref']);alias=row['metadata'].get('translated_route_alias')
        if alias is None:
            if sid in receipt['source_aliases']:raise ValueError('T04_TRANSLATED_ALIAS_MISSING')
            if row['metadata'].get('removed_bulk_source'):
                marker=row['metadata']['removed_bulk_source']
                if marker!=receipt['removed_bulk_sources'].get(sid) or sid not in receipt['bulk_roles'] or marker['original_ref']!=row['original_ref'] or marker['after_ref']!=row['geometry_ref'] or marker['role_witness_sha256']!=p.digest(p.canonical(receipt['bulk_roles'][sid])):
                    raise ValueError('T04_TRANSLATED_BULK_AUTHORITY_CHANGED')
                g=from_wkb(store.get(row['geometry_ref'],kind='geometry'));assert g.is_empty;current[sid]=g
            else:current[sid]=geometry(store,row['geometry_ref'])
            continue
        if alias!=receipt['source_aliases'].get(sid) or alias['original_ref']!=row['original_ref']:raise ValueError('T04_TRANSLATED_ALIAS_BINDING_CHANGED')
        r=alias['route_id'];target=rows.get(r)
        if target is None or target['geometry_ref']!=alias['body_ref'] or target['original_ref']!=receipt['published_routes'][r]['translated_reference_ref'] or sid not in target['metadata']['reference_source_ids']:raise ValueError('T04_TRANSLATED_ROUTE_BODY_MISSING')
        g=from_wkb(store.get(row['geometry_ref'],kind='geometry'))
        if not g.is_empty or not g.is_valid:raise ValueError('T04_TRANSLATED_ALIAS_NOT_ZERO')
        current[sid]=g
    if not set(receipt['source_aliases'])<=set(rows):raise ValueError('T04_TRANSLATED_SOURCE_ID_LOST')
    validate_motion_recipe(store,rows,current,receipt)
    return rows,current,original


def validate_motion_recipe(store,rows,current,receipt):
    source=store.get_json(receipt['input_scene_ref'],kind='scene')
    if source['source_sha256']!=receipt['source_sha256']:raise ValueError('T04_TRANSLATED_INPUT_SOURCE_CHANGED')
    oldrows={r['source_id']:r for r in source['objects']}
    for r,record in receipt['published_routes'].items():
        members=receipt['growth_source_ids_by_route'][r];plan=receipt['route_plans'][r];pose=record['translation_mm']
        if pose!=plan['translation_mm'] or len(pose)!=2 or any(type(v)not in(int,float) or not math.isfinite(v) for v in pose) or math.hypot(*pose)>receipt['maximum_translation_mm']+1e-12:
            raise ValueError('T04_TRANSLATED_POSE_CHANGED')
        if rows[r]['metadata']['reference_source_ids']!=members or rows[r]['metadata']['original_channel_id']!=receipt['route_owners'][r]:raise ValueError('T04_TRANSLATED_OWNER_OR_MEMBERS_CHANGED')
        for sid in members:
            if sid not in oldrows or oldrows[sid]['original_ref']!=record['source_refs'][sid] or rows[sid]['original_ref']!=record['source_refs'][sid]:raise ValueError('T04_TRANSLATED_INPUT_REFERENCE_CHANGED')
        original=unary_union([from_wkb(store.get(record['source_refs'][sid],kind='geometry')) for sid in members])
        if p.digest(to_wkb(original))!=record['input_route_ref']['sha256']:raise ValueError('T04_TRANSLATED_SOURCE_UNION_CHANGED')
        moved=translate(original,xoff=pose[0],yoff=pose[1])
        if p.digest(to_wkb(moved))!=record['translated_reference_ref']['sha256'] or not current[r].covers(moved):raise ValueError('T04_TRANSLATED_REFERENCE_RECIPE_CHANGED')
        w=plan['source_width_mm'];f=record['selected_progress']
        if not 1<=f<=1.5 or any(oldrows[sid]['metadata']['minimum_caliper_mm']!=w for sid in members):raise ValueError('T04_TRANSLATED_WIDTH_SOURCE_CHANGED')
        from .profile_refinement import band_at
        low,high=band_at(plan,f)
        if not w<=low<=high or high>w*1.5+1e-12 or high-w>.03+1e-12 or high>low*(1+receipt['width_variation_limit'])+1e-12:raise ValueError('T04_TRANSLATED_WIDTH_CAP_CHANGED')
        lower=moved if low==w else moved.buffer((low-w)/2,quad_segs=128)
        if receipt.get('side_specific_growth'):
            from .side_profile import verify_recipe,actual_widths
            recipe=store.get_json(record['side_profile_ref'],kind='t04-side-profile')
            if record['side_profile_ref']['sha256']!=plan['side_profile_recipe_sha256']:raise ValueError('SIDE_PROFILE_RECIPE_AUTHORITY_CHANGED')
            expected_points={sid:(np.asarray(oldrows[sid]['metadata']['route_points_mm'],float)+np.asarray(pose)).tolist()for sid in members}
            if recipe.get('source_centerlines')!=expected_points or recipe['translation_mm']!=pose:raise ValueError('SIDE_PROFILE_SOURCE_CENTERLINES_CHANGED')
            source_lines={sid:LineString(points)for sid,points in expected_points.items()}
            for cell in recipe['cells']:
                if cell['source_id']not in source_lines or any(source_lines[cell['source_id']].distance(Point(pt))>1e-9 for pt in (cell['a'],cell['b'])):raise ValueError('SIDE_PROFILE_SOURCE_STATION_CHANGED')
            baseline=from_wkb(store.get(record['baseline_body_ref'],kind='geometry'))
            fraction=max(0.,min(1.,(f-1)/(plan['progress_cap']-1)))
            verify_recipe(recipe,moved,w,low,high,baseline,current[r],fraction)
            cap_check=actual_widths(baseline,current[r],recipe,high)
            if not cap_check['passed']:raise ValueError('SIDE_PROFILE_ACTUAL_WIDTH_CAP_CHANGED:'+str(cap_check['failures'][:2]))
            if lower.difference(current[r]).area>1e-12:raise ValueError('T04_TRANSLATED_GEOMETRIC_MINIMUM_WIDTH_CHANGED')
        else:
            upper=moved if high==w else moved.buffer((high-w)/2,quad_segs=128)
            if current[r].difference(upper).area>1e-12 or lower.difference(current[r]).area>1e-12:raise ValueError('T04_TRANSLATED_GEOMETRIC_WIDTH_CAP_CHANGED')
        if 'baseline_profile' in plan or 'construction_floor_profile' in plan:
            key='construction_floor_body_ref' if 'construction_floor_profile' in plan else 'baseline_body_ref'
            floor=plan.get('construction_floor_profile',plan.get('baseline_profile'))
            baseline=from_wkb(store.get(record[key],kind='geometry'))
            if record[key]['sha256']!=floor['body_sha256']:raise ValueError('T04_PROFILE_BASELINE_BODY_CHANGED')
            from .profile_refinement import contains_floor
            if f>=floor['factor']-1e-12 and not contains_floor(current[r],baseline):raise ValueError('T04_PROFILE_BASELINE_COPPER_REMOVED')


@contextmanager
def prepared(store,scene,route_ids,settings,rule):
    from .side_profile import _WIDTH_PROOFS,_RECIPE_PROOFS
    _WIDTH_PROOFS.clear();_RECIPE_PROOFS.clear()
    variation=parameters(rule,route_ids);started=perf_counter();oldrule=dict(rule,schema=legacy.SCHEMA,coupled_allocation=True,local_profile=False)
    with legacy.prepared(store,scene,route_ids,settings,oldrule) as (entry,previous):
        rows,current,original=p.operands(store,entry);scope=sc.ACTIVE if sc.ACTIVE is not None else cc.ACTIVE;paths=previous.paths;roles=previous.receipt['bulk_roles']
        if getattr(scope,'frame_ids',()):raise ValueError('T04_TRANSLATION_INTEGRAL_SOURCE_REQUIRED')
        paths_flat={s for ss in paths.values() for s in ss}
        if any(not current[s].equals_exact(original[s],0) for s in paths_flat):raise ValueError('T04_TRANSLATION_ORIGINAL_SOURCE_REQUIRED')
        before_owners=owner_material(scope,current);oldcc,oldsc=cc.ACTIVE,sc.ACTIVE
        if 'side_specific_seed' in rule or 'copper_floor' in rule:
            from .side_profile import plan as sided
            chosen,data,oldcores,receipt=sided(rows,current,original,paths,roles,scope,settings,rule,rule.get('progress'))
        elif 'baseline_seed' in rule or 'baseline_seed_data' in rule or rule.get('source_built_25'):
            from .profile_refinement import plan as refine
            if rule.get('source_built_25'):
                # Source-only conservative proposal parameters, not a T04 run
                # or imported accepted state. Native checks occur once at 25%.
                base,base_data,_,_=plan(rows,current,original,paths,roles,scope,settings,previous.targets,.10,rule.get('progress'))
                seed=dict(schema='t04-profile-refinement-reference/1',source_sha256=scene['source_sha256'],
                    input_scene_sha256=rule['input_binding']['scene_ref']['sha256'],source_stage_sha256='SOURCE_PROPOSAL_NOT_ACCEPTED_T04',
                    reference_only=True,proof_reuse=False,routes={r:dict(source_ids=paths[r],source_width_mm=base_data[r]['width'],
                    translation_mm=list(c['pose']),corridor_width_mm=c['low'],outer_width_ceiling_mm=c['high'],
                    body_sha256=p.digest(to_wkb(c['body']))) for r,c in base.items()})
                rule=dict(rule,baseline_seed_data=seed,baseline_seed_sha256=p.digest(p.canonical(seed)),incremental_corridor_fill=True)
            chosen,data,oldcores,receipt=refine(rows,current,original,paths,roles,scope,settings,rule,rule.get('progress'))
        else:chosen,data,oldcores,receipt=plan(rows,current,original,paths,roles,scope,settings,previous.targets,variation,rule.get('progress'))
        receipt.update(scope=rule['scope'],source_sha256=scene['source_sha256'],input_scene_ref=rule['input_binding']['scene_ref'],growth_source_ids_by_route=paths,native_path_source_ids=previous.receipt['native_path_source_ids'],requested_native_route_ids=previous.receipt['requested_native_route_ids'],bulk_roles=roles,protected_source_ids=previous.receipt['protected_source_ids'],route_owners={r:scope.ids[ss[0]][0] for r,ss in paths.items()},width_tolerance=variation,within_route_width_variation_bound=variation,shared_parallel_length_mm=.05,removed_bulk_sources=previous.receipt['removed_bulk_sources'],source_role_dispositions=previous.receipt['source_role_dispositions'])
        if rule.get('source_built_25'):
            receipt['standalone_profile']=True
            for proposal in receipt['route_plans'].values():
                # This corridor has not been accepted by native T04 yet.
                # Only the later checked result becomes an unconditional floor.
                proposal['construction_floor_profile']=proposal.pop('baseline_profile')
        changed=dict(current)
        for r,ss in paths.items():
            for s in ss:changed[s]=translate(original[s],xoff=chosen[r]['pose'][0],yoff=chosen[r]['pose'][1])
        # The native scene reference is one route body, never a re-union of
        # independently translated source pieces. Source rows become aliases.
        reference_material=dict(changed);shadow=copy.copy(scope);shadow.ids=dict(scope.ids)
        for r,ss in paths.items():
            for sid in ss:reference_material[sid]=Polygon()
            reference_material[r]=translate(oldcores[r],xoff=chosen[r]['pose'][0],yoff=chosen[r]['pose'][1]);shadow.ids[r]=scope.ids[ss[0]]
        # Trim only source-classified foreign bulk, never pads/frame/trace cores.
        used={s for ss in paths.values() for s in ss};hard=set(rows)-set(roles);protected=unary_union([changed[s] for s in sorted(hard-used)])
        bulk_changes={};bulk_metadata={}
        for s in sorted(roles):
            if receipt.get('side_specific_growth'):
                # Freeze the exact saved-25 bulk. Restore from the accepted
                # floor even where the preliminary source-role entry differs.
                new=next(iter(data.values()))['bulk_floor'].get(s,current[s])
            else:
                own=scope.ids[s];corridors=[c['body'].buffer(GUARD+2*MARGIN,quad_segs=128) for r,c in chosen.items() if scope.ids[paths[r][0]]!=own and c['body'].envelope.buffer(GUARD).intersects(current[s].envelope)]
                if not corridors:continue
                removal=unary_union(corridors).difference(protected);new=current[s].difference(removal)
            if not new.equals_exact(current[s],0):
                if receipt.get('side_specific_growth') and not new.is_empty:
                    md=dict(rows[s]['metadata']);md.pop('removed_bulk_source',None);bulk_metadata[s]=md;receipt['removed_bulk_sources'].pop(s,None)
                if new.is_empty:
                    marker=dict(schema=legacy.SCHEMA,source_id=s,original_ref=rows[s]['original_ref'],before_ref=rows[s]['geometry_ref'],after_ref=p.geomref(store,new),role_witness_sha256=p.digest(p.canonical(roles[s])))
                    receipt['removed_bulk_sources'][s]=marker;bulk_metadata[s]=dict(rows[s]['metadata'],removed_bulk_source=marker)
                changed[s]=new;bulk_changes[s]=dict(before_ref=rows[s]['geometry_ref'],after_ref=p.geomref(store,new),removed_ref=p.geomref(store,current[s].difference(new)))
        receipt['bulk_changes']=bulk_changes
        receipt['predecessor_owner_material_refs']={o:p.geomref(store,before_owners[o]) for o in sorted({scope.ids[ss[0]][0] for ss in paths.values()})}
        counts={o:len(OriginalOwners(g).owners) for o,g in before_owners.items()}
        # Whole-owner connectivity is required at translated reference entry.
        for sid in roles:reference_material[sid]=changed[sid]
        new_owners=owner_material(shadow,reference_material)
        bad=[o for o,g in new_owners.items() if len(OriginalOwners(g).owners)>counts[o]]
        if bad:raise ValueError('T04_TRANSLATED_ENTRY_DISCONNECTED:'+str(bad))
        workingcc=working_scope(shadow if oldcc is scope else oldcc,Polygon(),receipt,reference_material,counts);workingsc=working_scope(shadow if oldsc is scope else oldsc,Polygon(),receipt,reference_material,counts)
        for ctx in (workingcc,workingsc):
            if ctx is None:continue
            ctx.source_void_reference=before_owners
            ctx.originals=dict(ctx.originals)
            for r,ss in paths.items():
                moved=translate(oldcores[r],xoff=chosen[r]['pose'][0],yoff=chosen[r]['pose'][1]);ctx.ids[r]=ctx.ids[ss[0]];ctx.originals[r]=moved
                for s in ss:ctx.originals[s]=changed[s]
            ctx.binding=p.digest(p.canonical([ctx.binding,receipt]))
        if workingcc is not None:workingcc.functional=workingsc
        if workingsc is not None:workingsc.physical_context=workingcc
        obj=Construction(paths,original,rows,chosen,data,oldcores,receipt,previous.admission,settings,rule.get('progress'))
        initial,metadata,additions,motion_ref=obj.publication(store,changed,dict.fromkeys(paths,1.))
        metadata.update(bulk_metadata)
        objects=[dict(row,geometry_ref=p.geomref(store,initial[row['source_id']]),metadata=metadata.get(row['source_id'],row['metadata'])) if row['source_id'] in metadata or not initial[row['source_id']].equals_exact(current[row['source_id']],0) else row for row in entry['objects']]
        newentry=dict(entry,objects=objects+additions,lineage=entry['lineage']+[dict(stage='t04-translated-profile-published',receipt_ref=motion_ref)])
        obj.before_owners=before_owners;obj.input_current=dict(current);obj.source_owner_ids=dict(scope.ids)
        obj.preparation_seconds=perf_counter()-started
        cc.ACTIVE,sc.ACTIVE=workingcc,workingsc
        try:yield newentry,obj
        finally:
            cc.ACTIVE,sc.ACTIVE=oldcc,oldsc;obj.shape_cache.clear()
            _WIDTH_PROOFS.clear();_RECIPE_PROOFS.clear()
