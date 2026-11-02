"""Explicit native-mm viewports and bounded raster fidelity checks."""

from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np
from PIL import Image
from shapely import contains_xy, distance, points, prepare

SVG = '{http://www.w3.org/2000/svg}'
FOREGROUND = '#DD2233'
BACKGROUND = '#061727'


def crop_svg(source, destination, bounds, size):
    """Change only the display window and colours of a native KiCad plot."""
    root = ET.fromstring(Path(source).read_bytes())
    if root.tag != SVG + 'svg':
        raise ValueError('NATIVE_SVG_ROOT_REQUIRED')
    for node in root.iter():
        if node.tag not in {SVG + t for t in ('svg', 'title', 'desc', 'g', 'path', 'circle', 'rect', 'line', 'polyline', 'polygon')}:
            raise ValueError('NATIVE_SVG_ELEMENT_UNSUPPORTED:' + node.tag)
        if any('href' in k or 'url(' in v for k, v in node.attrib.items()):
            raise ValueError('EXTERNAL_SVG_REFERENCE_UNSUPPORTED')
        for key, value in list(node.attrib.items()):
            node.set(key, value.replace('#C83434', FOREGROUND))
    x0, y0, x1, y1 = bounds
    root.set('viewBox', ' '.join(map(str, (x0, y0, x1 - x0, y1 - y0))))
    root.set('width', str(size[0]))
    root.set('height', str(size[1]))
    root.set('preserveAspectRatio', 'none')
    root.insert(0, ET.Element(SVG + 'rect', dict(x=str(x0), y=str(y0), width=str(x1-x0),
                                               height=str(y1-y0), fill=BACKGROUND)))
    Path(destination).write_bytes(ET.tostring(root, encoding='utf-8', xml_declaration=True))


def verify_svg_view(path, bounds, size):
    root = ET.fromstring(Path(path).read_bytes())
    x0, y0, x1, y1 = bounds
    if ([float(v) for v in root.attrib['viewBox'].split()] != [x0, y0, x1-x0, y1-y0]
            or [int(root.attrib[k]) for k in ('width', 'height')] != list(size)
            or root.attrib.get('preserveAspectRatio') != 'none'):
        raise ValueError('SVG_VIEWPORT_MISMATCH')


def raster_fidelity(path, geometry, bounds, size, error_mm):
    """Check every pixel centre against separately parsed finite-width copper.

    Anti-aliasing and native renderer curve approximation are allowed only inside
    the declared physical boundary band. This is display fidelity, not a DRC.
    """
    with Image.open(path) as image:
        if image.size != tuple(size) or image.format != 'PNG':
            raise ValueError('RASTER_DIMENSIONS_OR_FORMAT_MISMATCH')
        rgba = np.asarray(image.convert('RGBA'), dtype=np.int16)
    if np.any(rgba[:, :, 3] != 255):
        raise ValueError('OPAQUE_RASTER_REQUIRED')
    foreground = (rgba[:, :, 0] > 100) & (rgba[:, :, 0] - rgba[:, :, 2] > 50)
    if not foreground.any() or not (~foreground).any():
        raise ValueError('RASTER_EMPTY_OR_SOLID')
    x0, y0, x1, y1 = bounds
    xs = x0 + (np.arange(size[0]) + .5) * (x1-x0) / size[0]
    ys = y0 + (np.arange(size[1]) + .5) * (y1-y0) / size[1]
    prepare(geometry)
    expected = contains_xy(geometry, xs[None, :], ys[:, None])
    row, col = np.nonzero(foreground != expected)
    maximum = 0.0
    for start in range(0, len(row), 1024):
        distances = distance(points(xs[col[start:start+1024]], ys[row[start:start+1024]]), geometry.boundary)
        maximum = max(maximum, float(distances.max()))
        if np.any(distances > error_mm):
            raise ValueError(f'RASTER_FIDELITY_EXCEEDED:sample:{maximum:.9f}')
    return dict(passed=True, pixels_checked=int(expected.size),
                foreground_pixels=int(foreground.sum()), mismatch_pixels=len(row),
                maximum_mismatch_distance_mm=maximum, allowed_boundary_error_mm=error_mm,
                mismatches_outside_band=0,
                pixel_pitch_mm=[(x1-x0)/size[0], (y1-y0)/size[1]])
