"""One immutable stage-entry containment rule for circle and rectangle lands."""
from shapely import STRtree,to_wkb
from shapely.ops import unary_union
from src.stage_abi.store import digest


def policy():
    return dict(schema='contained-shape-keep/1',action='KEEP_EXACT_PREDECESSOR',
                context='COMPLETE_STAGE_ENTRY_COPPER',coverage='UNION_OF_OTHER_COPPER',
                exclude='SELF_AND_EXACT_GEOMETRIC_ALIASES',area_epsilon_mm2=1e-12,
                partial_coverage='NOT_CONTAINED',allocation='NO_INDEPENDENT_GROWTH_OR_INCLUSIVE_MEMBERSHIP')


class ContainmentIndex:
    def __init__(self,geometries):
        self.geometries=dict(geometries);self.ids=sorted(geometries)
        for g in self.geometries.values():
            if g.is_empty or not g.is_valid or g.geom_type not in ('Polygon','MultiPolygon'):
                raise ValueError('CONTAINMENT_FINITE_COPPER_REQUIRED')
        self.tree=STRtree([self.geometries[s]for s in self.ids])

    def assess(self,sid,aliases=()):
        core=self.geometries[sid]
        nearby=sorted(self.ids[int(i)]for i in self.tree.query(core,predicate='intersects'))
        excluded={sid,*aliases}|{s for s in nearby if self.geometries[s].equals(core)}
        others=[s for s in nearby if s not in excluded]
        missing=core.difference(unary_union([self.geometries[s]for s in others])).area
        contained=missing<=policy()['area_epsilon_mm2']
        return dict(source_id=sid,source_geometry_sha256=digest(to_wkb(core,byte_order=1)),
                    excluded_aliases=sorted(excluded),covering_context_source_ids=others,
                    uncovered_area_mm2=missing,contained=contained,
                    disposition='KEEP_CONTAINED'if contained else'NOT_CONTAINED')


def records(geometries,targets):
    index=ContainmentIndex(geometries)
    return {sid:index.assess(sid)for sid in sorted(targets)}
