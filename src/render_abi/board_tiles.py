"""Deterministic physical-resolution pages; overview is navigation only."""
import math
from .crop_pixels import choose_pixels

def tile_plan(bounds,policy):
    if set(policy)!={'tile_span_mm','pixel_policy','maximum_total_pixels_per_panel'} or type(policy['tile_span_mm'])not in(int,float)or not math.isfinite(policy['tile_span_mm'])or policy['tile_span_mm']<=0:raise ValueError('BOARD_TILE_POLICY_INVALID')
    # Validate bounds without trying to allocate a monolithic board raster.
    if type(bounds)is not list or len(bounds)!=4 or any(type(x)not in(int,float)or not math.isfinite(x)for x in bounds)or bounds[2]<=bounds[0]or bounds[3]<=bounds[1]:raise ValueError('BOARD_TILE_BOUNDS_INVALID')
    nx=math.ceil((bounds[2]-bounds[0])/policy['tile_span_mm']);ny=math.ceil((bounds[3]-bounds[1])/policy['tile_span_mm'])
    budget=policy['maximum_total_pixels_per_panel']
    if type(budget)is not int or budget<=0:raise ValueError('BOARD_TILE_POLICY_INVALID')
    # Lower bound first, before iterating a potentially excessive source window.
    pitch=policy['pixel_policy']['maximum_pixel_pitch_mm']
    if (bounds[2]-bounds[0])*(bounds[3]-bounds[1])/pitch**2>budget:raise ValueError('BOARD_RENDER_TOTAL_PIXEL_BUDGET_EXCEEDED')
    tiles=[];pixels=0
    for y in range(ny):
        for x in range(nx):
            b=[bounds[0]+x*(bounds[2]-bounds[0])/nx,bounds[1]+y*(bounds[3]-bounds[1])/ny,bounds[0]+(x+1)*(bounds[2]-bounds[0])/nx,bounds[1]+(y+1)*(bounds[3]-bounds[1])/ny]
            size=choose_pixels(b,policy['pixel_policy']);pixels+=size[0]*size[1]
            if pixels>budget:raise ValueError('BOARD_RENDER_TOTAL_PIXEL_BUDGET_EXCEEDED')
            tiles.append(dict(id=f'tile-{y:03d}-{x:03d}',column=x,row=y,bounds_mm=b,pixels=size))
    return dict(schema='pcb-board-tile-plan/1',bounds_mm=bounds,columns=nx,rows=ny,tiles=tiles,total_pixels_per_panel=pixels,coverage='Exact non-overlapping rectangular partition of the complete source/growth window; shared edges; no gaps',overview='Navigation only; per-tile native panels carry fidelity audits')
