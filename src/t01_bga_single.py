"""Source-qualified isolated circular islands in an explicit-clear pad array.

No image/ROI, component-wide clearance permission or requested target shape is
an input. Clear provenance classifies the case; ordinary constraints construct
its optional growth. Later dark material remains material.
"""
import json
from collections import defaultdict
from pathlib import Path
from shapely import to_wkb
from src.stage_abi.store import canonical, digest

PATH = 'contracts/t01_bga_single/settings.json'
ROOT = Path(__file__).resolve().parents[1]
SCHEMA = 't01-original-clear-array-circle/1'


def capture():
    raw = (ROOT / PATH).read_bytes()
    spec = json.loads(raw)
    if (spec['schema'] != 't01-bga-single-circle-policy/1'
            or type(spec['minimum_axis_sites']) is not int
            or spec['minimum_axis_sites'] < 3):
        raise ValueError('T01_BGA_SINGLE_POLICY_INVALID')
    return dict(path=PATH, sha256=digest(raw), specification=spec)


def qualify(source_sha256, circles, clears, *, coordinate_grid_mm):
    """Return provenance for full native-tick grids, not guessed BGA labels.

    circles: original resolved dark flash identities, centers, cores, ordinals.
    clears: actual earlier removed material and original clear identities.
    Native aperture sizes and coordinate ticks define exact array membership.
    Incomplete, rotated or irregular arrangements retain ordinary T01 behavior.
    """
    policy = capture(); minimum = policy['specification']['minimum_axis_sites']
    if coordinate_grid_mm <= 0:
        raise ValueError('T01_BGA_SOURCE_GRID_REQUIRED')
    groups = defaultdict(list)
    for clear in clears:
        for circle in circles:
            if (clear['ordinal'] >= circle['ordinal']
                    or not clear['removed'].covers(circle['core'])):
                continue
            groups[(clear['source_id'], float(circle['radius']).hex())].append(circle)
    result = {}
    for (clear_id, _), members in sorted(groups.items()):
        # Exact duplicate occurrences form one grid position, not extra sites.
        positions = defaultdict(list)
        for circle in members:
            ticks = tuple(round(v / coordinate_grid_mm) for v in circle['center'])
            if any(abs(v-t*coordinate_grid_mm) > 1e-12
                   for v,t in zip(circle['center'], ticks)):
                raise ValueError('T01_BGA_NATIVE_CENTER_OFF_GRID')
            positions[ticks].append(circle)
        axes = [sorted({p[i] for p in positions}) for i in (0, 1)]
        if any(len(a) < minimum or len({b-a for a,b in zip(a,a[1:])}) != 1
               for a in axes):
            continue
        if len(positions) != len(axes[0])*len(axes[1]):
            continue
        clear = next(c for c in clears if c['source_id'] == clear_id)
        witness = dict(source_sha256=source_sha256, clear_source_id=clear_id,
                       clear_ordinal=clear['ordinal'],
                       removed_material_sha256=digest(to_wkb(clear['removed'])),
                       array_source_ids=sorted(c['source_id'] for c in members),
                       axes_native_ticks=axes, coordinate_grid_mm=coordinate_grid_mm,
                       policy=policy)
        array_sha = digest(canonical(witness))
        for circle in members:
            value = dict(schema=SCHEMA, source_id=circle['source_id'],
                         source_geometry_sha256=digest(to_wkb(circle['core'])),
                         dark_ordinal=circle['ordinal'], array_sha256=array_sha,
                         witness=witness)
            # Earliest valid source witness wins deterministically.
            result.setdefault(circle['source_id'], value)
    return result


def validate(site, value):
    witness = value.get('witness', {})
    if (value.get('schema') != SCHEMA
            or value.get('source_id') not in site['aliases']
            or value.get('source_id') not in witness.get('array_source_ids', [])
            or not value.get('source_id', '').startswith(witness.get('source_sha256', '!')+':bytes:')
            or value.get('source_geometry_sha256') != digest(to_wkb(site['core']))
            or value.get('array_sha256') != digest(canonical(witness))
            or witness.get('policy') != capture()
            or value.get('dark_ordinal', -1) <= witness.get('clear_ordinal', -1)):
        raise ValueError('T01_BGA_SINGLE_SOURCE_BINDING_CHANGED')
    return value


def eligible_sites(sites, rows, shapes):
    """Recheck physical isolation against complete original source geometry.

    A circle with a trace/Region attachment, another pad or a remote common bar
    is not this case, even if metadata says it belongs to the array.
    """
    from shapely import STRtree
    tree = STRtree(shapes); result = {}
    byid = {row['id']: row for row in rows}
    for site in sites:
        markers = [byid[a].get('t01_bga_single') for a in site['aliases']
                   if byid[a].get('t01_bga_single') is not None]
        if not markers:
            continue
        for value in markers:
            validate(site, value)
        core = site['core']
        contacts = [int(i) for i in tree.query(core, predicate='intersects')]
        # Identical aliases may contact; any other original material keeps the
        # ordinary attachment/pair policy. No fuzzy near-contact exemption.
        if any(not shapes[i].equals(core) for i in contacts):
            continue
        result[site['source_id']] = sorted(markers, key=lambda m:m['source_id'])[0]
    return result
