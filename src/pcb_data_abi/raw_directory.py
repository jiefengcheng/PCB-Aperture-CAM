"""Native-only raw Gerber qualification. No filename-based roles or fitted frames.

Legacy positive IP and LN metadata are explicitly accounted for here; the shared
strict export parser is unchanged. Coordinate quantization bounds qualify input
correspondence only. They never modify T01 or copper-clearance rules.
"""
from dataclasses import replace
from pathlib import Path
import math,re,json,time
from gerbonara.rs274x import GerberFile
from gerbonara import graphic_objects as go
from gerbonara.apertures import CircleAperture,RectangleAperture
from gerbonara.utils import MM
from shapely.geometry import GeometryCollection
from shapely import union_all,difference,set_precision
from src.gerber_image import CompletionParser,object_geometry,ordered,SAG
from src.native_inventory import inventory
from src.pcb_data_abi.service import CLI,CLI_SHA,LAYERS,plot_name
from .input_directory import digest,validate,layer_role

VERSION='pcb-directory-identification/1'
BOOLEAN_GRID_MM=.000001

def parse_raw(blob,name):
    text=blob.decode('ascii');legacy=[]
    # Only obsolete positive image polarity and non-semantic layer-name metadata
    # are normalized in memory. Original bytes are always retained unchanged.
    for token in re.findall(r'%IP[^%]*%',text):
        if token!='%IPPOS*%':raise ValueError('RAW_GERBER_IMAGE_POLARITY_UNSUPPORTED')
        if text.index(token)>min([m.start()for m in re.finditer(r'(?:^|\*)\s*(?:X[+-]?\d|Y[+-]?\d|D0[123]\*)',text)]+[len(text)]):raise ValueError('RAW_GERBER_LATE_IMAGE_POLARITY')
        legacy.append(token)
    if len(legacy)>1:raise ValueError('RAW_GERBER_IMAGE_POLARITY_AMBIGUOUS')
    names=re.findall(r'%LN[^*%]+\*%',text);legacy.extend(names)
    text=re.sub(r'%LN[^*%]+\*%','',text.replace('%IPPOS*%',''))
    if any(a!='%TO.N,*%'for a in re.findall(r'%TO\.[^%]*%',text)):raise ValueError('RAW_GERBER_OBJECT_ATTRIBUTES_UNSUPPORTED')
    g=GerberFile();p=CompletionParser(g);p.parse(text,filename=name)
    fmt=p.file_settings.number_format
    if not p.eof_found or p.current_region is not None or p.block_frame is not None or p.inventory['MO']!=1 or p.inventory['FS']!=1 or p.file_settings.unit!=MM or p.file_settings.notation!='absolute' or fmt not in((3,3),(4,6)):
        raise ValueError('RAW_GERBER_PROFILE_OR_COMPLETENESS_FAILED')
    grid=10.**(-fmt[1]);arc_bound=2*math.sqrt(2)*grid;residual=0.
    shapes=[]
    for obj in g.objects:
        if getattr(obj,'completion_transform',(1,1,0,1))!=(1,1,0,1):raise ValueError('RAW_GERBER_APERTURE_TRANSFORM_UNSUPPORTED')
        if isinstance(obj,go.Arc):
            if not isinstance(obj.aperture,CircleAperture)or obj.aperture.hole_dia:raise ValueError('RAW_GERBER_ARC_APERTURE_UNSUPPORTED')
            cx,cy=obj.x1+obj.cx,obj.y1+obj.cy;r=math.hypot(obj.cx,obj.cy);end=math.hypot(obj.x2-cx,obj.y2-cy)
            err=abs(end-r);residual=max(residual,err)
            if r<=0 or end<=0 or err>arc_bound+1e-12:raise ValueError('RAW_GERBER_ARC_OUTSIDE_COORDINATE_BOUND')
            if err>0:obj=replace(obj,x2=cx+(obj.x2-cx)*r/end,y2=cy+(obj.y2-cy)*r/end)
        if isinstance(obj,go.Line)and(not isinstance(obj.aperture,(CircleAperture,RectangleAperture))or obj.aperture.hole_dia):raise ValueError('RAW_GERBER_LINE_APERTURE_UNSUPPORTED')
        shapes.append(obj)
    tolerance=(arc_bound if residual>2e-6 else 0.)+2*SAG+.00002+2*BOOLEAN_GRID_MM
    return g,shapes,dict(coordinate_format=list(fmt),coordinate_grid_mm=grid,boolean_grid_mm=BOOLEAN_GRID_MM,rectangular_strokes='Exact linear Minkowski sweep; no circular equivalent-width approximation',explicit_legacy_metadata=legacy,arc_radius_residual_mm=residual,correspondence_tolerance_mm=tolerance,registration_fit_used=False)

def raw_object_geometry(obj):
    if isinstance(obj,go.Line)and isinstance(obj.aperture,RectangleAperture):
        # Translating a convex rectangular aperture along a segment is exactly
        # the convex hull of its endpoint flashes, for every segment direction.
        if obj.aperture.hole_dia:raise ValueError('RAW_GERBER_LINE_APERTURE_UNSUPPORTED')
        ends=[object_geometry(go.Flash(x=x,y=y,aperture=obj.aperture,unit=obj.unit,polarity_dark=True))for x,y in[(obj.x1,obj.y1),(obj.x2,obj.y2)]]
        return union_all(ends).convex_hull
    return object_geometry(obj)

def image(objects):
    # Fixed one-nanometre Boolean precision avoids floating overlay singularities.
    # Its two-sided rounding allowance is included in the recorded input bound.
    result=GeometryCollection();pending=[]
    for obj in objects:
        shape=raw_object_geometry(obj)
        if not shape.is_valid:raise ValueError('RAW_GERBER_INVALID_PRIMITIVE_GEOMETRY')
        shape=set_precision(shape,BOOLEAN_GRID_MM)
        if obj.polarity_dark:pending.append(shape)
        else:
            result=union_all([result,*pending],grid_size=BOOLEAN_GRID_MM);pending=[]
            result=difference(result,shape,grid_size=BOOLEAN_GRID_MM)
    return union_all([result,*pending],grid_size=BOOLEAN_GRID_MM)

def buffer_image(shape,tolerance):
    # GEOS can return a MultiPolygon containing nested shells when buffering
    # this imported board as one image. Buffer each valid input component,
    # verify every resulting polygon, and explicitly union *all* pieces.
    # This is the set union defining dilation, not make_valid or dropped holes.
    if not shape.is_valid:raise ValueError('RAW_CORRESPONDENCE_INVALID_IMAGE')
    parts=[]
    for polygon in shape.geoms if hasattr(shape,'geoms')else[shape]:
        grown=polygon.buffer(tolerance)
        for part in grown.geoms if hasattr(grown,'geoms')else[grown]:
            if not part.is_valid:raise ValueError('RAW_CORRESPONDENCE_INVALID_BUFFER_PART')
            parts.append(part)
    result=union_all(parts,grid_size=BOOLEAN_GRID_MM)
    if not result.is_valid:raise ValueError('RAW_CORRESPONDENCE_INVALID_BUFFER_UNION')
    return result

def compare_images(a,b,tolerance):
    if a.is_empty or b.is_empty:return dict(passed=False,reason='EMPTY_IMAGE',outside_source_mm2=None,outside_plot_mm2=None)
    if max(abs(x-y)for x,y in zip(a.bounds,b.bounds))>tolerance:
        return dict(passed=False,reason='BOUNDS_OUTSIDE_CORRESPONDENCE_LIMIT',source_bounds_mm=list(a.bounds),plot_bounds_mm=list(b.bounds),tolerance_mm=tolerance,outside_source_mm2=None,outside_plot_mm2=None)
    # Both directed containments include islands and holes. No raster, registration
    # fit, bounding-box-only acceptance or whole-board percentage allowance.
    source_covered=bool(buffer_image(b,tolerance).covers(a))
    plot_covered=bool(buffer_image(a,tolerance).covers(b))
    return dict(passed=source_covered and plot_covered,source_covered=source_covered,plot_covered=plot_covered,outside_source_mm2=0. if source_covered else None,outside_plot_mm2=0. if plot_covered else None,tolerance_mm=tolerance,source_area_mm2=a.area,plot_area_mm2=b.area)

def match_candidates(candidates):
    """Uniqueness is checked on both sides, including byte-identical duplicates."""
    assigned={};used={}
    for name,layers in candidates.items():
        if len(layers)>1:raise ValueError('RAW_GERBER_LAYER_AMBIGUOUS:'+name)
        if layers:
            layer=layers[0]
            if layer in used:raise ValueError('RAW_GERBER_DUPLICATE_LAYER:'+layer)
            assigned[name]=layer;used[layer]=name
    if 'F.Cu'not in used:raise ValueError('RAW_GERBER_FCU_CORRESPONDENCE_NOT_ESTABLISHED')
    return assigned

def identify(root,blobs,ignored,out,command):
    """Native intake gate: retain all files; prove participating source layers."""
    out=Path(out);boards=[n for n in blobs if Path(n).suffix.lower()=='.kicad_pcb']
    if len(boards)!=1:raise ValueError('INPUT_DIRECTORY_EXACTLY_ONE_KICAD_REQUIRED')
    board=boards[0]
    if not blobs[board].lstrip().startswith(b'(kicad_pcb'):raise ValueError('INPUT_DIRECTORY_KICAD_FORMAT_REQUIRED')
    inv=inventory(blobs[board]);counts={}
    for r in inv['objects']:
        for layer in r['layers']:
            if layer in LAYERS:counts[layer]=counts.get(layer,0)+1
    if 'F.Cu'not in counts:raise ValueError('RAW_KICAD_NO_FCU_SOURCE')
    work=out/'native_source_work';work.mkdir();source=work/'board.kicad_pcb';source.write_bytes(blobs[board]);plot=out/'source_plots';plot.mkdir()
    if digest(CLI.read_bytes())!=CLI_SHA:raise ValueError('PINNED_KICAD_CLI_CHANGED')
    if command([CLI,'version'],'version')!='10.99.0':raise ValueError('KICAD_VERSION_CHANGED')
    command([CLI,'pcb','export','gerbers','--layers',','.join(sorted(counts)),'--precision','6','--no-protel-ext','-o',str(plot)+'/',source],'source_export')
    if source.read_bytes()!=blobs[board]:raise ValueError('RAW_NATIVE_EXPORT_CHANGED_BOARD')
    expected={plot_name(l)for l in counts}
    if {p.name for p in plot.glob('*.gbr')}!=expected:raise ValueError('RAW_NATIVE_PLOT_LAYER_SET_CHANGED')
    native={};matches=[];candidates={};dispositions=[];native_objects={}
    for layer in counts:
        _,native_objects[layer],_=parse_raw((plot/plot_name(layer)).read_bytes(),plot_name(layer))
    for name,blob in blobs.items():
        if name==board:continue
        (out/'progress.json').write_text(json.dumps(dict(status='QUALIFYING_RAW_GERBER',file=name,updated_at=time.time(),rendering='NOT_REQUESTED')))
        if b'%FS'not in blob or b'%MO'not in blob:raise ValueError('RAW_DIRECTORY_NON_GERBER_FILE:'+name)
        try:g,objects,profile=parse_raw(blob,name)
        except Exception as e:
            dispositions.append(dict(relative_path=name,status='EXCLUDED_COMPANION',reason='UNQUALIFIED_GERBER_PROFILE',details=str(e)));candidates[name]=[];continue
        possible=[l for l,n in counts.items()if len(objects)in(n,len(native_objects[l]))]
        # Explicit X2 roles are claims, never permission to skip correspondence.
        claimed=None
        if b'%TF.FileFunction,'in blob:
            claimed=layer_role(blob);possible=[l for l in possible if l==claimed]
        layers=[];measurements=[]
        if possible:
            a=image(objects)
            (out/(digest(blob)+'-image.wkb')).write_bytes(a.wkb)
            for layer in possible:
                if layer not in native:
                    native[layer]=image(native_objects[layer])
                    (out/(layer.replace('.','_')+'-native-image.wkb')).write_bytes(native[layer].wkb)
                proof=compare_images(a,native[layer],profile['correspondence_tolerance_mm'])
                measurements.append(dict(layer=layer,**proof))
                if proof['passed']:layers.append(layer)
        if claimed and not layers:raise ValueError('RAW_X2_SOURCE_CORRESPONDENCE_FAILED:'+name)
        candidates[name]=layers
        dispositions.append(dict(relative_path=name,status='MATCHED'if layers else'EXCLUDED_COMPANION',source_objects=len(g.objects),candidate_layers=possible,profile=profile,measurements=measurements))
    (out/'CANDIDATE_MATRIX.json').write_text(json.dumps(dict(candidates=candidates,dispositions=dispositions),indent=2))
    assigned=match_candidates(candidates)
    for row in dispositions:
        if row['relative_path']in assigned:
            layer=assigned[row['relative_path']];matches.append(dict(relative_path=row['relative_path'],layer=layer,profile=row['profile'],measurement=next(m for m in row['measurements']if m['layer']==layer),generated_sha256=digest((plot/plot_name(layer)).read_bytes())))
    proof=dict(schema=VERSION,companion_policy='PRESERVE_EXCLUDED',registration_fit_used=False,native_source_sha256=digest(blobs[board]),native_cli_sha256=CLI_SHA,native_layer_object_counts=counts,matches=matches,excluded_companions=sorted(n for n in blobs if n!=board and n not in assigned),dispositions=dispositions,method='Flat imported graphics: object-count candidate filter then complete ordered image correspondence in original absolute coordinates; no filenames or fitting',rendering='NOT_REQUESTED')
    rows=[dict(relative_path=n,kind='kicad'if n==board else'gerber'if n in assigned else'companion',layer=assigned.get(n),sha256=digest(b),bytes=len(b))for n,b in sorted(blobs.items())]
    return validate(dict(schema='pcb-raw-input-directory/2',provided_directory=str(root),files=rows,ignored_metadata=ignored,identification=proof))
