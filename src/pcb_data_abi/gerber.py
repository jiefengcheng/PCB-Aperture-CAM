"""Reparse pinned KiCad plots with the existing maintained Gerber adapter."""
from collections import Counter
from dataclasses import Field
import math
import re
from pathlib import Path
from gerbonara.rs274x import GerberFile
from gerbonara import graphic_objects as go
from gerbonara.utils import MM
from shapely import affinity
from shapely.ops import unary_union
from src.gerber_image import CompletionParser,object_geometry


def parse(path):
    text=Path(path).read_text()
    attributes=re.findall(r'%TO\.[^%]*%',text)
    if any(a!='%TO.N,*%' for a in attributes):raise ValueError('GERBER_OBJECT_ATTRIBUTES_OUTSIDE_GRAPHIC_PROFILE')
    g=GerberFile();p=CompletionParser(g);p.parse(text,filename=str(path))
    if p.current_region is not None or p.block_frame is not None or p.inventory['MO']!=1 or p.inventory['FS']!=1 or p.file_settings.unit!=MM or p.file_settings.number_format!=(4,6) or p.file_settings.notation!='absolute':
        raise ValueError('GERBER_PROFILE_OR_COMPLETENESS_FAILED')
    if g.file_attrs.get('.SameCoordinates')!=('Original',):raise ValueError('GERBER_COORDINATE_FRAME_UNQUALIFIED')
    return g


def number(v):return round(float(v),9)


def atom(obj):
    """Order-independent plotting semantics; aperture numbers/metadata excluded."""
    ap=getattr(obj,'aperture',None)
    aperture=(type(ap).__name__,number(ap.diameter),ap.hole_dia,ap.attrs) if hasattr(ap,'diameter') else None
    polarity=bool(obj.polarity_dark)
    attrs=obj.attrs
    # Gerbonara 1.6.3 Region.__init__ leaves the inherited empty dict factory
    # as a Field. Only that known empty default is normalized here. Explicit
    # named object attributes are outside this graphic-only export profile.
    # KiCad's empty TO.N declaration denotes unassigned graphic/track data.
    if isinstance(attrs,Field) and attrs.default_factory is dict:attrs={}
    if type(attrs)is not dict:raise ValueError('GERBER_ATTRIBUTE_CONTAINER_UNSUPPORTED')
    attrs=tuple(sorted(attrs.items()))
    if isinstance(obj,go.Arc):
        return ('arc',polarity,number(obj.x1),number(obj.y1),number(obj.x2),number(obj.y2),number(obj.cx),number(obj.cy),obj.clockwise,aperture,attrs)
    if isinstance(obj,go.Line):
        return ('line',polarity,number(obj.x1),number(obj.y1),number(obj.x2),number(obj.y2),aperture,attrs)
    if isinstance(obj,go.Flash):
        return ('flash',polarity,number(obj.x),number(obj.y),aperture,attrs)
    if isinstance(obj,go.Region):
        g=object_geometry(obj).normalize()
        return ('region',polarity,g.wkb_hex,attrs)
    raise ValueError('UNSUPPORTED_PLOT_ATOM:'+type(obj).__name__)


def circle_indices(objects,center,radius):
    cx,cy=center[0],-center[1];rows=[]
    for i,o in enumerate(objects):
        if not isinstance(o,go.Arc) or not o.polarity_dark or not hasattr(o.aperture,'diameter'):continue
        if abs(o.x1+o.cx-cx)>1e-6 or abs(o.y1+o.cy-cy)>1e-6:continue
        if abs(o.aperture.diameter-radius)>1e-6 or abs(math.hypot(o.cx,o.cy)*2-radius)>2e-6:continue
        if abs(o.x1-o.x2)<1e-12 and abs(o.y1-o.y2)<1e-12:continue
        rows.append(i)
    if not rows or len(rows)%2:raise ValueError('CIRCLE_PLOT_MEMBERSHIP_NOT_ESTABLISHED')
    return rows


def native_geometry(obj):
    return affinity.scale(object_geometry(obj),xfact=1,yfact=-1,origin=(0,0))


def native_circle(objects,indices):
    return affinity.scale(unary_union([object_geometry(objects[i]) for i in indices]),xfact=1,yfact=-1,origin=(0,0))


def protected_counter(objects,excluded):
    return Counter(atom(o) for i,o in enumerate(objects) if i not in excluded)
