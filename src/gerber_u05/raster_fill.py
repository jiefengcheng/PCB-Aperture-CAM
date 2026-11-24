"""Original plotted-fill evidence for curved boundary strokes; no geometry edits.

A complete interior centerline must be covered by repeated short, same-aperture
source strokes. Original cap neighborhoods require other original copper too.
This is a fill-role witness, never a claim of full finite-stroke containment.
"""
import math
from shapely import STRtree, to_wkb
from shapely.geometry import LineString
from shapely.ops import substring, unary_union
from src.stage_abi.store import digest


class RasterFill:
    def __init__(self, rows, original):
        self.rows, self.original = rows, original
        self.ids = sorted(s for s, g in original.items() if not g.is_empty)
        self.tree = STRtree([original[s] for s in self.ids])

    def witness(self, source):
        row = self.rows[source]; md = row['metadata']; pts = md.get('route_points_mm')
        if md.get('route_kind') != 'arc' or not pts or len(pts) < 3:
            return None
        width = md['minimum_caliper_mm']; line = LineString(pts)
        if not math.isfinite(width) or width <= 0 or line.length <= 3 * width:
            return None
        body = self.original[source]; blob = to_wkb(body)
        near = sorted(self.ids[int(i)] for i in self.tree.query(body, predicate='intersects')
                      if self.ids[int(i)] != source and to_wkb(self.original[self.ids[int(i)]]) != blob)
        hatches = []
        for sid in near:
            other = self.rows[sid]['metadata']; op = other.get('route_points_mm')
            if (other.get('route_kind') == 'segment' and op and len(op) == 2 and
                    other['minimum_caliper_mm'] == width and 0 < math.dist(*op) <= width):
                hatches.append(sid)
        # Distinct original positions are required; repeated aliases are not raster fill.
        if len({to_wkb(self.original[s]) for s in hatches}) < 3:
            return None
        hatch_copper = unary_union([self.original[s] for s in hatches])
        interior = substring(line, width / 2, line.length - width / 2)
        if not hatch_copper.covers(interior):
            return None
        other_copper = unary_union([self.original[s] for s in near])
        if not other_copper.covers(line):
            return None
        return dict(schema='t04-original-raster-fill-curve/1', source_id=source,
                    original_geometry_sha256=digest(blob), native_centerline_sha256=digest(to_wkb(line)),
                    verified_source_width_mm=width, cap_neighborhood_mm=width / 2,
                    interior_length_mm=interior.length, original_hatch_source_ids=hatches,
                    hatch_geometry_sha256={s:digest(to_wkb(self.original[s])) for s in hatches},
                    cap_cover_source_ids=near, original_interior_fully_in_hatch_copper=True,
                    entire_native_centerline_in_other_original_copper=True,
                    finite_source_body_action='KEEP_EXACT_STAGE_ENTRY_GEOMETRY',
                    qualification='SOURCE_FILL_ROLE; NOT_FINITE_STROKE_CONTAINMENT_OR_CLEARANCE')
