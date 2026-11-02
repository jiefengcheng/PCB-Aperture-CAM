"""Fresh stored-file geometry used only to audit image placement and fidelity."""

import sexpdata
from shapely.geometry import box
from shapely.ops import unary_union

from src.native_inventory import geometry
from src.native_reference import one
from src.pcb_data_abi import gerber


def native_copper(path, bounds):
    board = sexpdata.loads(path.read_text())
    if str(board[0]) != 'kicad_pcb':
        raise ValueError('KICAD_BOARD_REQUIRED')
    crop = box(*bounds)
    surfaces = []
    allowed = {'segment', 'gr_line', 'gr_arc', 'arc', 'gr_circle', 'gr_poly', 'gr_rect'}
    for node in board[1:]:
        if not isinstance(node, list) or str(one(node, 'layer', [''])[0]) != 'F.Cu':
            continue
        kind = str(node[0])
        if kind not in allowed:
            raise ValueError('RENDER_NATIVE_OBJECT_UNSUPPORTED:' + kind)
        surface = geometry(node, kind)
        if surface.intersects(crop):
            surfaces.append(surface.intersection(crop))
    return nonempty(unary_union(surfaces))


def gerber_copper(path, bounds):
    parsed = gerber.parse(path)
    if (parsed.file_attrs.get('.FileFunction') != ('Copper', 'L1', 'Top')
            or parsed.file_attrs.get('.FilePolarity') != ('Positive',)):
        raise ValueError('RENDER_FCU_ROLE_REQUIRED')
    crop = box(*bounds)
    surfaces = []
    for obj in parsed.objects:
        if not obj.polarity_dark:
            raise ValueError('RENDER_CLEAR_POLARITY_UNSUPPORTED')
        surface = gerber.native_geometry(obj)
        if surface.intersects(crop):
            surfaces.append(surface.intersection(crop))
    return nonempty(unary_union(surfaces))


def nonempty(surface):
    if surface.is_empty or not surface.is_valid:
        raise ValueError('RENDER_VALID_NONEMPTY_COPPER_REQUIRED')
    return surface
