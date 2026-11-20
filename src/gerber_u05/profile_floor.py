"""Source-bound, lossless copper floor; contains geometry, never native verdicts.

The same ABI accepts saved qualification floors and a freshly checked baseline
in this process. Production floors use content-addressed store refs, so no
second WKB directory or checkpoint-specific path is needed.
"""
from dataclasses import dataclass
from pathlib import Path
import hashlib
import json
from shapely import from_wkb
from . import pipeline as p

SCHEMA = 't04-side-growth-floor/1'


@dataclass(frozen=True)
class CopperFloor:
    seed_bytes: bytes
    read_blob: object

    @property
    def sha256(self):
        return hashlib.sha256(self.seed_bytes).hexdigest()

    def load(self, binding, paths):
        seed = json.loads(self.seed_bytes)
        if (seed.get('schema') != SCHEMA or seed['source_sha256'] != binding['source_sha256']
                or seed['input_scene_sha256'] != binding['scene_ref']['sha256']
                or seed.get('reference_only') is not True or seed.get('proof_reuse') is not False
                or set(seed['routes']) != set(paths)):
            raise ValueError('SIDE_PROFILE_FLOOR_BINDING_CHANGED')
        def read(record):
            raw = self.read_blob(record)
            if hashlib.sha256(raw).hexdigest() != record['sha256']:
                raise ValueError('SIDE_PROFILE_FLOOR_GEOMETRY_CHANGED')
            body = from_wkb(raw)
            if not body.is_valid or body.geom_type not in ('Polygon', 'MultiPolygon'):
                raise ValueError('SIDE_PROFILE_FLOOR_GEOMETRY_INVALID')
            return body
        return seed, {r: read(q) for r, q in seed['routes'].items()}, {s: read(q) for s, q in seed['bulk'].items()}

    @classmethod
    def saved(cls, path, expected_sha256):
        path = Path(path)
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected_sha256:
            raise ValueError('SIDE_PROFILE_FLOOR_SEED_CHANGED')
        def read(record):
            name = record['file']
            if Path(name).name != name:
                raise ValueError('SIDE_PROFILE_FLOOR_PATH_INVALID')
            return (path.parent / 'floor' / name).read_bytes()
        return cls(raw, read)

    @classmethod
    def accepted(cls, store, source_scene, stage):
        """Bind freshly checked geometry without importing its proof as authority."""
        from .profile_refinement import band_at
        checks = stage['checks']
        if (set(checks) != {'nominal', 'envelope'} or not stage['motion_validation']['passed']
                or not all(q['passed'] and q['evaluation_complete'] and q['scene_union_materialized']
                           and q['functional_channels']['passed'] and not q['failures']
                           and all(v['passed'] for v in q['original_source_voids']) for q in checks.values())):
            raise ValueError('T04_PROFILE_FLOOR_NATIVE_CHECKS_REQUIRED')
        ledger = stage['limiting_construction']
        scene = store.get_json(stage['output_scene_ref'], kind='scene')
        oldrows = {q['source_id']: q for q in source_scene['objects']}
        rows = {q['source_id']: q for q in scene['objects']}
        if (ledger['source_sha256'] != source_scene['source_sha256']
                or ledger['input_scene_ref']['sha256'] != p.digest(p.canonical(source_scene))
                or not set(oldrows) <= set(rows)):
            raise ValueError('T04_PROFILE_FLOOR_SOURCE_CHANGED')
        routes = {}
        for r, pub in ledger['published_routes'].items():
            plan = ledger['route_plans'][r]
            low,high=band_at(plan,pub['selected_progress'])
            routes[r] = dict(source_ids=ledger['growth_source_ids_by_route'][r],
                source_width_mm=plan['source_width_mm'], floor_high_mm=high,
                translation_mm=pub['translation_mm'], corridor_width_mm=low,
                outer_width_ceiling_mm=plan['outer_width_ceiling_mm'], selected_progress=pub['selected_progress'],
                ref=pub['body_ref'], sha256=pub['body_ref']['sha256'])
        bulk = {}
        for sid, old in oldrows.items():
            row = rows[sid]
            if row['kind'] != old['kind'] or row['original_ref'] != old['original_ref']:
                raise ValueError('T04_PROFILE_FLOOR_SOURCE_IDENTITY_CHANGED')
            if sid in ledger['bulk_roles'] and row['geometry_ref'] != old['geometry_ref']:
                bulk[sid] = dict(ref=row['geometry_ref'], sha256=row['geometry_ref']['sha256'])
        seed = dict(schema=SCHEMA, source_sha256=source_scene['source_sha256'],
                    input_scene_sha256=p.digest(p.canonical(source_scene)), source_stage_sha256=p.digest(p.canonical(stage)),
                    baseline_output_scene_ref=stage['output_scene_ref'], reference_only=True, proof_reuse=False,
                    routes=routes, bulk=bulk)
        return cls(p.canonical(seed), lambda q: store.get(q['ref'], kind='geometry'))
