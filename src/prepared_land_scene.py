"""Finite-surface growth checks for source-bound zero-stroke filled lands.

Reuses the qualified growth-only surface predicate without inventing a positive
trace width for a filled graphic. Original source copper alone hides internal
boundaries; newly grown copper never hides another candidate's boundary.
"""
import math
from shapely import STRtree
from shapely.ops import unary_union
from .prepared_width_scene import PreparedWidthScene
from .trace_width_clearance import TraceWidthContract,sha
from src.stage_abi.preparation import prepared_tree as STRtree


class PreparedLandScene(PreparedWidthScene):
    def __init__(self,lands,fixed_copper,contract=TraceWidthContract()):
        if contract!=TraceWidthContract():raise ValueError('LAND_SURFACE_POLICY_CHANGED')
        if not lands:raise ValueError('NO_SOURCE_LANDS')
        self.contract=contract;self.original={};self.widths={};self.trace_ids={};self.kinds={};self.fixed_count=len(fixed_copper)
        for row in lands:
            sid=row['id']
            if sid in self.original:raise ValueError('DUPLICATE_SCENE_SOURCE')
            if row['native_source_kind'] not in ('gr_poly','gr_circle') or row['native_stroke_width_mm']!=0:
                raise ValueError('VERIFIED_ZERO_STROKE_FILLED_LAND_REQUIRED')
            self.original[sid]=row['original'];self.widths[sid]=0.;self.trace_ids[sid]=sha(row['original']);self.kinds[sid]=row['native_source_kind']
        for row in fixed_copper:
            sid=row['id']
            if sid in self.original:raise ValueError('DUPLICATE_SCENE_SOURCE')
            self.original[sid]=row['geometry'];self.widths[sid]=row.get('trace_width_mm',0.)
            if not math.isfinite(self.widths[sid]) or self.widths[sid]<0:raise ValueError('INVALID_FIXED_SOURCE_WIDTH')
        for g in self.original.values():self.valid_geometry(g)
        self.ids=sorted(self.original);self.tree=STRtree([self.original[s] for s in self.ids]);self.predecessor=unary_union([self.original[s] for s in self.ids]);self.predecessor_sha=sha(self.predecessor)
        self.fixed_visibility={};self.trace_visibility={};self.ports={};self.addition_visibility={}

    def check(self,lands,*,materialize_scene=False,fail_fast=False):
        rows=[]
        for row in lands:
            if row['native_stroke_width_mm']!=0 or row['native_source_kind']!=self.kinds.get(row['id']):raise ValueError('NATIVE_LAND_BINDING_CHANGED')
            rows.append(dict(id=row['id'],original=row['original'],candidate=row['candidate'],verified_original_width_mm=0.))
        result=super().check(rows,materialize_scene=materialize_scene,fail_fast=fail_fast)
        result['schema']='source-filled-land-visible-growth/1';result['land_count']=result.pop('trace_count');result['checked_land_count']=result.pop('checked_trace_count');result['lands']=result.pop('traces')
        for row in result['lands']:row['source_id']=row.pop('trace_id')
        for row in result['failures']:
            if 'trace_id' in row:row['source_id']=row.pop('trace_id')
        result['native_land_attachment_width_mm']=0.;result['scope']='Filled source lands, not trace-width construction; full source copper visibility and original local contact ports only'
        return result
