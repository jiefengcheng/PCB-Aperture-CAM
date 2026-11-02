"""Curve-preserving display derivative of the actual qualified Gerber file.

KiCad 10.99.0's PNG converter facets curves beyond the retained 5 um audit
band on this board. Gerbonara emits SVG arcs/circles; native SIPS rasterizes
that vector file. This changes display only, never the exported Gerber.
"""
from pathlib import Path
from src.pcb_data_abi import gerber
from .view import FOREGROUND,BACKGROUND


def gerber_svg(source,destination):
    parsed=gerber.parse(source)
    if (parsed.file_attrs.get('.FileFunction')!=('Copper','L1','Top')
            or parsed.file_attrs.get('.FilePolarity')!=('Positive',)):
        raise ValueError('RENDER_FCU_ROLE_REQUIRED')
    if any(not obj.polarity_dark for obj in parsed.objects):
        raise ValueError('RENDER_CLEAR_POLARITY_UNSUPPORTED')
    # Preserve true vector curves rather than polygonizing their raster outlines.
    # Explicit native coordinate mapping, with no fitted translation or scale.
    tags=''.join(str(tag)for tag in parsed.svg_objects(fg=FOREGROUND,bg=BACKGROUND))
    svg='<svg xmlns="http://www.w3.org/2000/svg"><g transform="scale(1 -1)">'+tags+'</g></svg>'
    with Path(destination).open('x')as stream:stream.write(svg)
    return dict(renderer='Gerbonara 1.6.3 SVG curves + native SIPS',source_objects=len(parsed.objects),coordinate_mapping='Gerber X=native X; Gerber Y=-native Y; scale(1 -1)',source_edited=False)
