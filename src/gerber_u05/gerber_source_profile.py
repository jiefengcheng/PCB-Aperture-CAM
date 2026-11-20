"""Isolated Gerber-only source qualification; no growth/export acceptance.

Legacy empty coordinate fields have explicit zero semantics in this separate
trailing-zero profile. Both spellings are checked by an independent integer
decoder before the maintained parser sees normalized in-memory commands.
"""
import collections,hashlib,json,math,re
from dataclasses import replace
from gerbonara.rs274x import GerberFile
from gerbonara import graphic_objects as go,graphic_primitives as gp
from gerbonara.apertures import CircleAperture,RectangleAperture
from gerbonara.utils import MM
from shapely import to_wkb
from shapely.geometry import LineString,GeometryCollection
from src.gerber_image import CompletionParser,primitive,ordered,contour,SAG,MAX_POINTS
from src.pcb_data_abi.raw_directory import raw_object_geometry

TOKEN=re.compile(r'G04.*?\*\s*|%.*?%\s*|[^*%]*\*\s*',re.S)
EMPTY=re.compile(r'([XYIJ])([+-]?)(?=[XYIJD*])')
FIELD=re.compile(r'([XYIJ])([+-]?\d*)(?=[XYIJD*])')

def digest(raw):return hashlib.sha256(raw).hexdigest()
def decode_coordinate(spelling,integer=3,fraction=5):
    sign=-1 if spelling.startswith('-')else 1
    digits=spelling.lstrip('+-')
    if digits and not digits.isdigit():raise ValueError('NONINTEGER_COORDINATE')
    if len(digits)>integer+fraction:raise ValueError('COORDINATE_WORD_TOO_LONG')
    # Declared trailing-zero suppression: absent least significant places
    # contribute zero. The legacy all-zero spelling is the empty word.
    return sign*int((digits+'0'*(integer+fraction-len(digits)))or'0')

def normalize(raw):
    text=raw.decode('ascii')
    if text.count('%FSTAX35Y35*%')!=1 or text.count('%MOMM*%')!=1:raise ValueError('GERBER_ONLY_PROFILE_REQUIRES_MM_T35_ABSOLUTE')
    if '%IPNEG' in text or text.count('%IPPOS*%')!=1:raise ValueError('POSITIVE_IMAGE_POLARITY_REQUIRED')
    tokens=[];output=[];coordinates=0;empty=0;end=0
    for m in TOKEN.finditer(text):
        if text[end:m.start()].strip():raise ValueError('UNCONSUMED_SOURCE_BYTES')
        end=m.end();original=m[0];trim=original.strip()
        if not trim.strip('%').rstrip('*'):continue
        if trim=='%IPPOS*%'or re.fullmatch(r'%LN[^*%]+\*%',trim):continue
        normalized=original
        if not trim.startswith(('%','G04')):
            normalized,n=EMPTY.subn(r'\g<1>\g<2>0',original);empty+=n
            before=[(a,decode_coordinate(b))for a,b in FIELD.findall(original)]
            after=[(a,decode_coordinate(b))for a,b in FIELD.findall(normalized)]
            if before!=after:raise ValueError('COORDINATE_ORACLE_MISMATCH')
            coordinates+=len(before)
        start=m.start()+len(original)-len(original.lstrip());stop=start+len(trim)
        output.append(normalized);tokens.append(dict(command=normalized.strip().strip('%').rstrip('*'),span=[start,stop]))
    if text[end:].strip():raise ValueError('TRAILING_UNCONSUMED_SOURCE')
    return ''.join(output),tokens,dict(coordinate_fields=coordinates,legacy_empty_zero_fields=empty,
        zero_semantics='EXPLICIT_SEPARATE_LEGACY_T35_PROFILE; not strict-standard syntax admission',
        coordinate_grid_mm=.00001,source_bytes_changed=False)

class SourceParser(CompletionParser):
    def __init__(self,target,tokens,raw):
        super().__init__(target);self.tokens=iter(tokens);self.spans={};self.region_start=None;self.raw=raw
    def _split_commands(self,data):
        for command in super()._split_commands(data):
            token=next(self.tokens)
            if token['command']!=command:raise ValueError('SOURCE_COMMAND_ALIGNMENT')
            if command=='G36':self.region_start=token['span'][0]
            before=len(self.target.objects)
            yield command
            for index in range(before,len(self.target.objects)):
                self.spans[index]=[self.region_start if command=='G37'else token['span'][0],token['span'][1]]
            if command=='G37':self.region_start=None
        if next(self.tokens,None)is not None:raise ValueError('UNPARSED_SOURCE_COMMAND')

def parse_source(raw):
    normalized,tokens,proof=normalize(raw);g=GerberFile();p=SourceParser(g,tokens,raw);p.parse(normalized,filename='source:'+digest(raw))
    if not p.eof_found or p.current_region is not None or p.block_frame is not None:raise ValueError('INCOMPLETE_GERBER_SOURCE')
    expected={
        'MM_L46_ABSOLUTE':((4,6),'leading'),
        'MM_L33_ABSOLUTE':((3,3),'leading'),
    }.get(proof.get('source_format'),((3,5),'trailing'))
    if p.file_settings.unit!=MM or p.file_settings.number_format!=expected[0]or p.file_settings.zeros!=expected[1]or p.file_settings.notation!='absolute':raise ValueError('SOURCE_FORMAT_DRIFT')
    if p.inventory['MO']!=1 or p.inventory['FS']!=1:raise ValueError('AMBIGUOUS_FORMAT_OR_UNITS')
    if set(p.spans)!=set(range(len(g.objects))):raise ValueError('SOURCE_OBJECT_SPAN_COVERAGE')
    if proof.get('source_format')=='MM_L33_ABSOLUTE':
        # L33 arc endpoints were rounded on a 1 µm source grid. This
        # allowance applies only to source arc recognition.
        for obj in g.objects:
            obj.u05_source_arc_grid_mm=.001
    return g,p,proof

def source_arc_grid(obj):
    return getattr(obj,'u05_source_arc_grid_mm',.00001)

def arc_points(a,b,c,cw,*,grid=.00001):
    radius=math.dist(a,c);other=math.dist(b,c);residual=abs(radius-other);bound=2*math.sqrt(2)*grid
    if radius<=0 or other<=0 or residual>bound+1e-12:raise ValueError('ARC_RADIUS_EXCEEDS_SOURCE_COORDINATE_BOUND')
    first=math.atan2(a[1]-c[1],a[0]-c[0]);last=math.atan2(b[1]-c[1],b[0]-c[0]);sweep=(first-last)%(2*math.pi)if cw else(last-first)%(2*math.pi)
    if a==b:sweep=2*math.pi
    count=max(1,math.ceil(sweep/(2*math.acos(max(-1.,1.-SAG/radius)))))
    if count>MAX_POINTS:raise ValueError('ARC_RESOURCE_BOUND')
    sign=-1 if cw else 1;points=[(c[0]+radius*math.cos(first+sign*sweep*i/count),c[1]+radius*math.sin(first+sign*sweep*i/count))for i in range(count+1)]
    points[0]=a;points[-1]=b
    return points,residual

def primitive_geometry(p,*,grid=.00001):
    if isinstance(p,gp.Arc):
        points,residual=arc_points((p.x1,p.y1),(p.x2,p.y2),(p.cx,p.cy),p.clockwise,grid=grid)
        if p.width<=0:raise ValueError('NONPOSITIVE_ARC_STROKE')
        radius=p.width/2;q=max(16,math.ceil(math.pi/(4*math.acos(max(-1.,1.-SAG/radius)))))
        return LineString(points).buffer(radius,quad_segs=q),residual
    if isinstance(p,gp.ArcPoly):
        points=[];residual=0.
        for a,b,(cw,c)in p.segments:
            part,r=([a,b],0.)if cw is None else arc_points(a,b,c,cw,grid=grid)
            residual=max(residual,r);points.extend(part if not points else part[1:])
        return contour(points),residual
    return primitive(p),0.

def object_geometry(obj):
    if obj.unit!=MM or getattr(obj,'completion_transform',(1,1,0,1))!=(1,1,0,1):raise ValueError('SOURCE_UNITS_OR_TRANSFORM_UNSUPPORTED')
    if isinstance(obj,go.Line)and isinstance(obj.aperture,RectangleAperture):return raw_object_geometry(obj),0.
    if isinstance(obj,(go.Line,go.Arc,go.Flash)):
        if not isinstance(obj.aperture,(CircleAperture,RectangleAperture))or obj.aperture.hole_dia:raise ValueError('SOURCE_APERTURE_UNSUPPORTED')
        positive=replace(obj,polarity_dark=True)
    elif isinstance(obj,go.Region):positive=obj
    else:raise ValueError('SOURCE_OBJECT_UNSUPPORTED')
    result=[];residual=0.
    for p in positive.to_primitives(unit=MM):
        shape,r=primitive_geometry(p,grid=source_arc_grid(obj));residual=max(residual,r);result.append((shape,p.polarity_dark if isinstance(obj,go.Flash)else True))
    return ordered(result),residual

def qualify(raw,out):
    g,p,proof=parse_source(raw);records=[];items=[];max_residual=0.
    for i,o in enumerate(g.objects):
        shape,residual=object_geometry(o)
        if not shape.is_valid or shape.is_empty:raise ValueError('SOURCE_PRIMITIVE_INVALID_OR_EMPTY:'+str(i))
        start,end=p.spans[i];sid=f'{digest(raw)}:bytes:{start}:{end}';body=to_wkb(shape);key=digest(body);(out/(key+'.wkb')).write_bytes(body)
        max_residual=max(max_residual,residual);items.append((shape,o.polarity_dark))
        records.append(dict(source_id=sid,ordinal=i,source_span=[start,end],prefix_sha256=digest(raw[:end]),kind=type(o).__name__,polarity_dark=o.polarity_dark,geometry_sha256=key,area_mm2=shape.area,bounds_mm=list(shape.bounds),arc_radius_residual_mm=residual))
    image=ordered(items)
    if not image.is_valid or image.is_empty:raise ValueError('COMPOSED_IMAGE_INVALID_OR_EMPTY')
    body=to_wkb(image);(out/'original_image.wkb').write_bytes(body)
    return dict(schema='gerber-only-source-qualification/1',status='SOURCE_GEOMETRY_ONLY_NO_U05_EXECUTION',source_sha256=digest(raw),source_objects=len(records),records=records,composition_sha256=digest(body),composition_area_mm2=image.area,coordinate_oracle=proof,max_arc_radius_residual_mm=max_residual,arc_coordinate_bound_mm=2*math.sqrt(2)*(.001 if proof.get('source_format')=='MM_L33_ABSOLUTE'else .00001),polygon_sag_mm=SAG,source_file_untouched=True,owner='PENDING_USER',electrical_manufacturing='NOT_ESTABLISHED')

# Millimetre leading-zero formats preserve the source bytes and spans.
# Empty coordinate words are only admitted by the separate legacy T35 profile.
def decode_l46(spelling):
 sign=-1 if spelling.startswith('-')else 1;digits=spelling.lstrip('+-')
 if not digits or not digits.isdigit()or len(digits)>10:raise ValueError('L46_INTEGER_COORDINATE_REQUIRED')
 return sign*int(digits)

def normalize_leading(raw, *, coarse=False):
 text=raw.decode('ascii')
 header='%FSLAX33Y33*%' if coarse else '%FSLAX46Y46*%'
 max_digits=6 if coarse else 10
 if text.count(header)!=1 or text.count('%MOMM*%')!=1:
  raise ValueError('GERBER_ONLY_L33_PROFILE_REQUIRES_MM_ABSOLUTE' if coarse else 'GERBER_ONLY_L46_PROFILE_REQUIRES_MM_ABSOLUTE')
 if '%IPNEG' in text or text.count('%IPPOS*%')>1:raise ValueError('POSITIVE_IMAGE_POLARITY_REQUIRED')
 tokens=[];output=[];coordinates=0;end=0
 for m in TOKEN.finditer(text):
  if text[end:m.start()].strip():raise ValueError('UNCONSUMED_SOURCE_BYTES')
  end=m.end();original=m[0];trim=original.strip()
  if not trim.strip('%').rstrip('*'):continue
  if trim=='%IPPOS*%'or re.fullmatch(r'%LN[^*%]+\*%',trim):continue
  if not trim.startswith(('%','G04')):
   fields=FIELD.findall(original)
   for _,spelling in fields:
    if coarse and len(spelling.lstrip('+-'))>max_digits:raise ValueError('L33_COORDINATE_WORD_TOO_LONG')
    decode_l46(spelling)
   coordinates+=len(fields)
  start=m.start()+len(original)-len(original.lstrip());stop=start+len(trim)
  output.append(original);tokens.append(dict(command=trim.strip('%').rstrip('*'),span=[start,stop]))
 if text[end:].strip():raise ValueError('TRAILING_UNCONSUMED_SOURCE')
 return ''.join(output),tokens,dict(coordinate_fields=coordinates,legacy_empty_zero_fields=0,
  zero_semantics='STANDARD_LEADING_ZERO_SUPPRESSION',coordinate_grid_mm=.001 if coarse else .000001,
  source_bytes_changed=False,source_format='MM_L33_ABSOLUTE' if coarse else 'MM_L46_ABSOLUTE',
  arc_semantics='Original declared source grid bounds retained source arcs only' if coarse else 'Existing explicit legacy-source arc recognition bound retained; independent of clearance and file quantization')

_normalize_t35=normalize
def normalize(raw):
 if b'%FSLAX33Y33*%' in raw:return normalize_leading(raw,coarse=True)
 if b'%FSLAX46Y46*%' in raw:return normalize_leading(raw)
 return _normalize_t35(raw)
