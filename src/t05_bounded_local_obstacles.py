"""Experimental local subtraction under the explicit bounded-resemblance ABI.

The base helper already constructs a complete local obstacle mask with a halo
greater than twice the buffer radius. Its artificial clipping edges cannot
reach an in-domain proposal. Previously the mask was used only for a disjoint
proof, because Boolean reassociation could alter last-bit coordinates.

Here that same mask may trim contacting proposals. This is opt-in: the caller
must retain bounded reference comparison and every original physical check on
the unrounded result, against the complete original foreign geometry. No safety
verdict, retained acceptance or caller-provided patch selects this shortcut.
"""
from shapely import get_precision

from src.t05_local_obstacles import LocalObstacles


class BoundedLocalObstacles(LocalObstacles):
    """One immutable junction context; inherited fallbacks keep complete copper."""

    def trim(self, proposal):
        if self.reference is None and self.local is not None:
            bounds = proposal.bounds
            contained = (not proposal.is_empty and len(bounds) == 4 and
                         self.bounds[0] <= bounds[0] <= bounds[2] <= self.bounds[2] and
                         self.bounds[1] <= bounds[1] <= bounds[3] <= self.bounds[3])
            if (contained and proposal.is_valid and get_precision(proposal) == 0 and
                    proposal.geom_type in ('Polygon', 'MultiPolygon')):
                # Keep actual subtraction even for disjoint shapes. Do not
                # round, simplify, or return a reference patch. Geometry and
                # safety checks remain downstream obligations of the caller.
                self.statistics['bounded_local_trims'] = self.statistics.get('bounded_local_trims', 0) + 1
                return proposal.difference(self.local)
        # Invalid/unsupported geometry, nonzero precision, out-of-domain
        # proposals, or an already-established full mask retain the base path.
        return super().trim(proposal)
