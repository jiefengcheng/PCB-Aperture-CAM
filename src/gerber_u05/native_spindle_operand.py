"""Use the actual positive append operand for native additive-contract checks.

An additive operand may duplicate existing owner copper for encoding support.
Subtracting the global scene and re-adding that Boolean result can create a
remote floating-point wedge. It is not the exported operand. Scope/clearance
are checked on the complete parsed positive operand, which is conservative
relative to checking only its newly exposed subset. No tolerance is changed.
"""
from shapely.ops import unary_union

def operand(regions):
 material=unary_union(regions)
 if material.is_empty or not material.is_valid:raise ValueError('NATIVE_POSITIVE_SPINDLE_OPERAND_INVALID')
 return material
