"""Reject spindle scales that split accepted copper on the Gerber grid."""
from pathlib import Path

from shapely import STRtree, to_wkb

from src.component_voids import joined, parts
from src.stage_abi.store import canonical, digest
from src.u05_board.coverage import filled_patch

from .prior_copper import CoverageAdapter


class NativeGridCoverageAdapter(CoverageAdapter):
    def __init__(self, write, store, predecessor, binding):
        super().__init__(write)
        from .channel_finish import native_before_owned

        self._grid_store = store
        self._grid_predecessor = native_before_owned(store, predecessor, binding)

    def describe(self):
        result = super().describe()
        result['implementation'] = digest(canonical(result) + Path(__file__).read_bytes())
        return result

    def _check(self, owner, candidate, addition, window, foreign):
        result = super()._check(owner, candidate, addition, window, foreign)
        if not result['passed']:
            return result

        from .channel_finish import canonical_parent, export_reference, native_grid, GRID_MM
        from .component_finish import prepare_region
        from .export_absorption import compact_supported_region
        from .exporter import bounded_owner_surface, owner_encoding_overlap

        own = self._surface_owners[digest(to_wkb(owner))]
        prior = self._grid_predecessor[own]
        patch = filled_patch(addition, self._before)
        region, _, support_mode = compact_supported_region(patch, owner, window)
        region, _ = prepare_region(
            self._grid_store, region, owner, own, foreign=self._foreign_for(owner, foreign)
        )
        if support_mode == 'EXACT_ADDITION_WITHOUT_REDUNDANT_SUPPORT':
            region, _ = owner_encoding_overlap(region, owner, window)
        region, _ = bounded_owner_surface(region, owner, window)
        native = joined([
            prior,
            *(canonical_parent(export_reference(part)[0], grid_mm=GRID_MM)
              for part in parts(native_grid(region))),
        ])
        native_parts = parts(native)
        predecessor_parts = parts(prior)
        predecessor_count = len(predecessor_parts)
        index = STRtree(predecessor_parts)
        matches = [
            [int(i) for i in index.query(part) if part.intersection(predecessor_parts[int(i)]).area > 0]
            for part in native_parts
        ]
        passed = len(matches) == predecessor_count and all(len(match) == 1 for match in matches)
        passed = passed and len({match[0] for match in matches}) == predecessor_count
        return dict(
            result,
            passed=passed,
            failures=[] if passed else ['T05_NATIVE_GRID_OWNER_PARTITION_CHANGED'],
            native_grid_partition=dict(
                passed=passed, predecessor_components=predecessor_count,
                candidate_components=len(native_parts),
            ),
        )
