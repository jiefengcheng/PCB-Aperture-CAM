"""Physical sampling policy for crop-only display; fidelity bands stay fixed."""
import math


def choose_pixels(bounds,policy):
    if (type(bounds)is not list or len(bounds)!=4 or any(type(v) not in (int,float) or not math.isfinite(v) for v in bounds)
        or bounds[2]<=bounds[0] or bounds[3]<=bounds[1]):raise ValueError('CROP_RENDER_BOUNDS_INVALID')
    if set(policy)!={'minimum_width','maximum_pixel_pitch_mm','maximum_axis_pixels','maximum_pixels_per_panel'}:
        raise ValueError('CROP_RENDER_PIXEL_POLICY_INVALID')
    pitch=policy['maximum_pixel_pitch_mm']
    if type(pitch) not in (int,float) or not math.isfinite(pitch) or pitch<=0:raise ValueError('CROP_RENDER_PIXEL_POLICY_INVALID')
    if any(type(policy[k])is not int or policy[k]<=0 for k in ('minimum_width','maximum_axis_pixels','maximum_pixels_per_panel')):
        raise ValueError('CROP_RENDER_PIXEL_POLICY_INVALID')
    width=max(policy['minimum_width'],math.ceil((bounds[2]-bounds[0])/pitch))
    height=max(32,math.ceil(width*(bounds[3]-bounds[1])/(bounds[2]-bounds[0])))
    if max(width,height)>policy['maximum_axis_pixels'] or width*height>policy['maximum_pixels_per_panel']:
        raise ValueError('CROP_RENDER_PIXEL_BUDGET_EXCEEDED')
    return [width,height]
