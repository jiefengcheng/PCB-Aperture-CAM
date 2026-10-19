"""Bounded source-located R140 native adapter; no whole-board geometry promotion."""
import math
import sexpdata
from shapely import affinity,to_wkb
from .native_inventory import geometry,ERROR_MM
from .native_reference import children,one
from .revision_catalog import CatalogError,digest
from .source_locators import locate

PROFILE='native-bottom-rect-context/1'


def net_annotation(node,nets):
    values=one(node,'net',[])
    if not values:return None,None,'ABSENT'
    first=values[0]
    if isinstance(first,str):return None,first,'SOURCE_NAMED_NET'
    if isinstance(first,int) and not isinstance(first,bool):
        return first,(str(values[1]) if len(values)>1 else nets.get(first)) if first else None,'SOURCE_NUMERIC_NET'
    raise CatalogError('UNSUPPORTED_NET_ANNOTATION')


def extract_native(source,reference,trace_uuid):
    top=locate(source,max_depth=2);source_hash=digest(source)
    nets={};footprints=[];trace=[];setup=None
    needle=reference.encode()
    for span in top:
        if span.head not in ('net','setup','footprint','module','segment'):continue
        raw=source[span.start:span.end]
        if span.head in ('footprint','module') and needle not in raw:continue
        if span.head=='segment' and trace_uuid.encode() not in raw:continue
        node=sexpdata.loads(raw.decode())
        if span.head=='net' and len(node)>2 and isinstance(node[1],int):nets[node[1]]=str(node[2])
        if span.head=='setup':setup=(span,node)
        if span.head in ('footprint','module'):
            refs=[str(p[2]) for p in children(node,'property') if str(p[1])=='Reference']
            refs += [str(p[2]) for p in children(node,'fp_text') if str(p[1])=='reference']
            if reference in refs:footprints.append((span,node))
        if span.head=='segment' and str(one(node,'uuid',one(node,'tstamp',['']))[0])==trace_uuid:trace.append((span,node))
    if len(footprints)!=1:raise CatalogError('AMBIGUOUS_OR_MISSING_COMPONENT')
    if len(trace)!=1:raise CatalogError('AMBIGUOUS_OR_MISSING_TRACE')
    fp_span,fp=footprints[0];at=list(map(float,one(fp,'at',[0,0,0])))
    if len(at)==2:at.append(0)
    pads=[p for p in children(fp,'pad') if str(p[1]) in ('1','2')]
    if sorted(str(p[1]) for p in pads)!=['1','2']:raise CatalogError('AMBIGUOUS_OR_MISSING_PAD')
    local_spans=locate(source[fp_span.start:fp_span.end]);pad_spans=[s for s in local_spans if s.head=='pad' and s.parent_start==0]
    if len(pad_spans)!=len(children(fp,'pad')):raise CatalogError('PAD_SOURCE_LOCATOR_MISMATCH')
    records=[];payloads={};role_ids={};mask=None
    def record(node,span,kind,parent=None,shape=None,position=None,reason=None):
        code,name,basis=net_annotation(node,nets)
        layers=list(map(str,one(node,'layers',one(node,'layer',[]))))
        native=str(one(node,'uuid',one(node,'tstamp',['']))[0]) or None
        row={'id':f'{source_hash}:bytes:{span[0]}:{span[1]}','source_span':list(span),'source_sha256':source_hash,
             'representation':'native','kind':kind,'parent_id':parent,'native_id':native,'reference':reference if kind in ('footprint','pad') else None,
             'pin':str(node[1]) if kind=='pad' else None,'net_code':code,'net_name':name,'net_basis':basis,
             'layers':layers,'layer_instances':[{'layer':l,'role':'copper' if l.endswith('.Cu') else 'opening' if l.endswith('.Mask') else 'annotation'} for l in layers],
             'geometry_layers':['B.Cu'] if shape is not None else [],'position_mm':position,'nominal_anchor_mm':position,
             'endpoints_mm':None,'bounds_mm':None,'geometry_sha256':None,'geometry_basis':PROFILE,
             'geometry_error_mm':2*ERROR_MM,'coverage':'UNSUPPORTED' if shape is None else 'GEOMETRY_AVAILABLE',
             'unsupported_reason':reason,'qualification_refs':[],'match_refs':[],'native_group_members':[]}
        if shape is not None:
            raw=to_wkb(shape);key=digest(raw);payloads[key]=raw
            row.update(geometry_sha256=key,bounds_mm=list(shape.bounds))
        records.append(row);return row
    parent=record(fp,[fp_span.start,fp_span.end],'footprint',reason='CONTAINER_ONLY: selected children separately materialized')
    for node,span in zip(children(fp,'pad'),pad_spans):
        if str(node[1]) not in ('1','2'):continue
        shape=None;position=None;reason=None
        try:
            if str(one(fp,'layer',[''])[0])!='B.Cu' or abs(at[2]-180)>1e-9:raise CatalogError('BACKSIDE_POSE_OUTSIDE_PROFILE')
            if str(node[2])!='smd' or str(node[3])!='rect' or children(node,'drill') or children(node,'primitives'):raise CatalogError('PAD_SHAPE_OUTSIDE_PROFILE')
            if list(map(str,one(node,'layers',[])))[:1]!=['B.Cu']:raise CatalogError('PAD_LAYER_OUTSIDE_PROFILE')
            local=list(map(float,one(node,'at',[0,0,0])))
            angle=math.radians(at[2]);position=[at[0]+math.cos(angle)*local[0]+math.sin(angle)*local[1],at[1]-math.sin(angle)*local[0]+math.cos(angle)*local[1]]
            shape=affinity.translate(geometry(node,'pad'),*position)
            if not shape.is_valid or shape.is_empty:raise CatalogError('INVALID_NATIVE_PAD')
        except (ValueError,TypeError,IndexError) as error:reason=str(error);shape=None;position=None
        row=record(node,[fp_span.start+span.start,fp_span.start+span.end],'pad',parent['id'],shape,position,reason)
        role_ids['R140.'+str(node[1])]=row['id']
        if str(node[1])=='1':
            # Zero explicit clearance only. Membership alone never supplies mask geometry.
            base=one(setup[1],'pad_to_mask_clearance',None) if setup else None
            margin=one(node,'solder_mask_margin',one(fp,'solder_mask_margin',base))
            if shape is not None and 'B.Mask' in row['layers'] and margin and float(margin[0])==0:
                mask={'geometry_sha256':row['geometry_sha256'],'basis':'Explicit resolved zero pad_to_mask_clearance; rectangular pad profile',
                      'resolved_margin_mm':0,'setup_source_span':[setup[0].start,setup[0].end] if setup else None}
    span,node=trace[0];shape=geometry(node,'segment')
    if str(one(node,'layer',[''])[0])!='B.Cu':raise CatalogError('TRACE_OUTSIDE_LAYER_PROFILE')
    row=record(node,[span.start,span.end],'segment',shape=shape)
    row['endpoints_mm']=[list(map(float,one(node,'start'))),list(map(float,one(node,'end')))]
    role_ids['connected_trace']=row['id'];role_ids['mask_opening']=role_ids['R140.1']
    return {'source_sha256':source_hash,'objects':records,'payloads':payloads,'roles':role_ids,'parent_id':parent['id'],
            'mask_expectation':mask,'profile':PROFILE,'coverage':'Only selected R140 footprint, two pads and one segment; no full-board topology'}
