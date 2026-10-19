"""Provenance for the existing maintained strict Gerber parser, not a new grammar."""
import re
from gerbonara.rs274x import GerberFile
from gerbonara import graphic_objects as go
from gerbonara.utils import MM
from shapely import affinity,to_wkb
from .gerber_image import CompletionParser,object_geometry,SAG
from .revision_catalog import CatalogError,digest

PROFILE='strict-mm46-flash-line-provenance/1'


class ProvenanceParser(CompletionParser):
    def __init__(self,target):
        super().__init__(target);self.feature_spans={};self.current_span=None

    def _split_commands(self,text):
        matches=(m for m in re.finditer(r'G04.*?\*\s*|%.*?%\s*|[^*%]*\*\s*',text,re.S)
                 if m[0].strip().strip('%').rstrip('*'))
        for command in super()._split_commands(text):
            match=next(matches);raw=match[0];trimmed=raw.strip()
            if trimmed.strip('%').rstrip('*')!=command:raise CatalogError('GERBER_PROVENANCE_ALIGNMENT')
            start=match.start()+len(raw)-len(raw.lstrip())
            self.current_span=[start,start+len(trimmed)]
            yield command

    def _parse_coord(self,match):
        old=len(self.target.objects);super()._parse_coord(match)
        for index in range(old,len(self.target.objects)):
            self.feature_spans[index]=list(self.current_span)


def parse_source(raw):
    text=raw.decode('ascii');g=GerberFile();parser=ProvenanceParser(g)
    parser.parse(text,filename='artifact:'+digest(raw))
    if parser.file_settings.unit!=MM or parser.file_settings.number_format!=(4,6) or parser.file_settings.notation!='absolute':raise CatalogError('GERBER_PROFILE_REQUIRES_MM46_ABSOLUTE')
    if parser.inventory['MO']!=1 or parser.inventory['FS']!=1 or not parser.eof_found or parser.block_frame is not None or parser.current_region is not None:raise CatalogError('GERBER_PROFILE_INCOMPLETE')
    return g,parser


def feature_record(raw,g,parser,index,layer):
    obj=g.objects[index];span=parser.feature_spans.get(index)
    if not span or not isinstance(obj,(go.Flash,go.Line)) or not obj.polarity_dark:raise CatalogError('FEATURE_OUTSIDE_PROVENANCE_PROFILE')
    attrs=g.file_attrs;function=attrs.get('.FileFunction',())
    if layer=='B.Cu' and (not function or function[0]!='Copper' or 'Bot' not in function):raise CatalogError('GERBER_LAYER_FUNCTION_MISMATCH')
    if layer=='B.Mask' and (not function or function[0]!='Soldermask' or 'Bot' not in function):raise CatalogError('GERBER_LAYER_FUNCTION_MISMATCH')
    expected='Negative' if layer=='B.Mask' else 'Positive'
    if attrs.get('.FilePolarity')!=(expected,):raise CatalogError('GERBER_FILE_POLARITY_OUTSIDE_PROFILE')
    shape=affinity.scale(object_geometry(obj),1,-1,origin=(0,0));payload=to_wkb(shape);key=digest(payload);source_hash=digest(raw)
    terminal=list(obj.attrs.get('.P',()));component=list(obj.attrs.get('.C',()))
    row={'id':f'{source_hash}:bytes:{span[0]}:{span[1]}','source_sha256':source_hash,'source_span':span,
         'parent_id':None,'native_id':None,'representation':'gerber','kind':'gerber_flash' if isinstance(obj,go.Flash) else 'gerber_line',
         'reference':terminal[0] if terminal else component[0] if component else None,'pin':terminal[1] if len(terminal)>1 else None,
         'net_name':obj.attrs.get('.N',(None,))[0],'net_code':None,'net_basis':'GERBER_X2_SOURCE_ANNOTATION',
         'layers':[layer],'geometry_layers':[layer],'layer_role':'opening' if layer=='B.Mask' else 'copper',
         'position_mm':[obj.x,-obj.y] if isinstance(obj,go.Flash) else None,
         'endpoints_mm':[[obj.x1,-obj.y1],[obj.x2,-obj.y2]] if isinstance(obj,go.Line) else None,
         'bounds_mm':list(shape.bounds),'geometry_sha256':key,'geometry_basis':PROFILE,'geometry_error_mm':2*SAG,
         'coverage':'GEOMETRY_AVAILABLE','unsupported_reason':None,'parser_ordinal':index,'source_attributes':obj.attrs,
         'state_dependencies':{'source_sha256':source_hash,'interpretation_prefix_span':[0,span[1]],'prefix_sha256':digest(raw[:span[1]]),
                               'scope':'Complete original command prefix binds prior point, aperture/macros, attributes, polarity, units/format and transforms',
                               'parser_profile':PROFILE,'file_attributes':attrs},'qualification_refs':[],'match_refs':[]}
    return row,{key:payload}


def extract_copper(raw):
    g,p=parse_source(raw);selected={}
    for pin in ('1','2'):
        matches=[i for i,o in enumerate(g.objects) if isinstance(o,go.Flash) and tuple(o.attrs.get('.P',())[:2])==('R140',pin)]
        if len(matches)!=1:raise CatalogError('AMBIGUOUS_OR_MISSING_GERBER_PAD')
        selected['R140.'+pin]=matches[0]
    pad=g.objects[selected['R140.1']]
    matches=[i for i,o in enumerate(g.objects) if isinstance(o,go.Line) and any(abs(x-pad.x)<1e-6 and abs(y-pad.y)<1e-6 for x,y in [(o.x1,o.y1),(o.x2,o.y2)])]
    if len(matches)!=1:raise CatalogError('AMBIGUOUS_OR_MISSING_CONNECTED_TRACE')
    selected['connected_trace']=matches[0]
    records=[];payloads={};roles={}
    for role,index in selected.items():
        record,parts=feature_record(raw,g,p,index,'B.Cu');records.append(record);payloads.update(parts);roles[role]=record['id']
    return {'objects':records,'payloads':payloads,'roles':roles,'parsed':g,'parser':p}


def extract_opening(raw,anchor):
    g,p=parse_source(raw)
    matches=[i for i,o in enumerate(g.objects) if isinstance(o,go.Flash) and tuple(o.attrs.get('.C',()))==('R140',)
             and abs(o.x-anchor[0])<=.001 and abs(-o.y-anchor[1])<=.001]
    if len(matches)!=1:raise CatalogError('AMBIGUOUS_OR_MISSING_MASK_OPENING')
    record,payloads=feature_record(raw,g,p,matches[0],'B.Mask')
    return {'objects':[record],'payloads':payloads,'roles':{'mask_opening':record['id']},'parsed':g,'parser':p}
