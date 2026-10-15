"""Bounded, source-preserving Gerber coordinate edits; no object reconstruction."""
from pathlib import Path
from shapely.geometry import box
import hashlib, re
from gerbonara.rs274x import GerberFile
from gerbonara import graphic_objects as go
from gerbonara.utils import MM

class AdmissionError(ValueError): pass

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def coord(x,y,code):return f'X{round(x*1e6)}Y{round(y*1e6)}D{code:02d}*'.encode()
def parse(path):
    # Same maintained grammar, fail on all warnings; full composition is separate.
    from .gerber_image import CompletionParser
    text=Path(path).read_text();g=GerberFile();p=CompletionParser(g);p.parse(text,filename=str(path))
    if p.file_settings.unit!=MM or p.file_settings.number_format!=(4,6) or p.file_settings.notation!='absolute':raise AdmissionError('requires explicit absolute millimetre 4.6 format')
    if p.inventory['MO']!=1 or p.inventory['FS']!=1 or p.block_frame is not None or p.current_region is not None:raise AdmissionError('incomplete or ambiguous input')
    return g

def read_region(path, bounds_mm):
    """Compose only plotting features whose conservative bounds meet the ROI.

    Parse every source command, but construct detailed geometry only locally.
    This keeps the client's large board from requiring a whole-board GEOS union
    for a contract that authorizes one small region.
    """
    from .gerber_image import CompletionParser, object_geometry, ordered
    text=Path(path).read_text();g=GerberFile();p=CompletionParser(g);p.parse(text,filename=str(path))
    if p.file_settings.unit!=MM or p.file_settings.number_format!=(4,6) or p.file_settings.notation!='absolute':raise AdmissionError('requires explicit absolute millimetre 4.6 format')
    if p.inventory['MO']!=1 or p.inventory['FS']!=1 or p.block_frame is not None or p.current_region is not None:raise AdmissionError('incomplete or ambiguous input')
    roi=box(*bounds_mm);items=[];selected=[]
    for obj in g.objects:
        bb=obj.bounding_box()
        if bb is None: continue
        candidate=box(bb[0][0],bb[0][1],bb[1][0],bb[1][1])
        if not candidate.intersects(roi): continue
        shape=object_geometry(obj).intersection(roi)
        items.append((shape,obj.polarity_dark));selected.append(obj)
    image=ordered(items)
    if not image.is_valid:raise AdmissionError('invalid composed region geometry')
    return {'geometry':image,'objects':g.objects,'selected_objects':selected,'file_attrs':g.file_attrs,'inventory':dict(p.inventory),'roi_mm':list(bounds_mm)}

def locate(g,terminal,anchor):
    pads=[(i,o) for i,o in enumerate(g.objects) if isinstance(o,go.Flash) and tuple(o.attrs.get('.P',())[:2])==tuple(terminal)]
    if len(pads)!=1:raise AdmissionError('missing/ambiguous target flash')
    pi,pad=pads[0]
    if not pad.polarity_dark or ('.AperFunction',('SMDPad','CuDef')) not in (pad.aperture.attrs or ()):raise AdmissionError('target must be declared positive SMD copper pad')
    same=lambda a,b:abs(a[0]-b[0])<1e-6 and abs(a[1]-b[1])<1e-6
    lines=[]
    for i,o in enumerate(g.objects):
        if isinstance(o,go.Line):
            a=(o.x1,o.y1);b=(o.x2,o.y2)
            if (same(a,(pad.x,pad.y)) and same(b,anchor)) or (same(b,(pad.x,pad.y)) and same(a,anchor)):lines.append((i,o))
    if len(lines)!=1:raise AdmissionError('missing/ambiguous permitted straight connection')
    li,line=lines[0]
    if not line.polarity_dark or line.attrs.get('.N')!=pad.attrs.get('.N') or not pad.attrs.get('.N'):raise AdmissionError('connection label/polarity disagreement')
    return pi,pad,li,line

def replace_once(data,old,new):
    if data.count(old)!=1:raise AdmissionError('source command not unique')
    return data.replace(old,new,1)

def move_bytes(data,pad,line,center,move_trace=True):
    # Source commands are absolute, fully explicit and independently positioned.
    original=coord(pad.x,pad.y,3); replacement=coord(*center,3)
    data=replace_once(data,original,replacement)
    if move_trace:
        points=[(line.x1,line.y1),(line.x2,line.y2)];newpoints=[center if abs(x-pad.x)<1e-6 and abs(y-pad.y)<1e-6 else (x,y) for x,y in points]
        newline=b'\r\n' if b'\r\n' in data else b'\n'
        old=coord(*points[0],2)+newline+coord(*points[1],1)
        new=coord(*newpoints[0],2)+newline+coord(*newpoints[1],1)
        data=replace_once(data,old,new)
    return data

def break_connection(data,line,start):
    newline=b'\r\n' if b'\r\n' in data else b'\n'
    old=coord(line.x1,line.y1,2)+newline+coord(line.x2,line.y2,1)
    new=coord(*start,2)+newline+coord(line.x2,line.y2,1)
    return replace_once(data,old,new)

def append_bridge(data,a,b,aperture):
    if data.count(b'M02*')!=1:raise AdmissionError('ambiguous EOF')
    # Existing qualified circular conductor aperture; explicit state and no attributes.
    cmd=b'%TD*%\r\n%LPD*%\r\nG01*\r\n'+f'D{aperture}*\r\n'.encode()+coord(*a,2)+b'\r\n'+coord(*b,1)+b'\r\nM02*'
    return data.replace(b'M02*',cmd)
