"""Source-bound circular-site inventory and read-only geometry rendering helpers."""
import hashlib,json,math,re
from collections import defaultdict
from pathlib import Path
import sexpdata
from shapely import STRtree,from_wkb,to_wkb
from shapely.geometry import Point,box
from src.native_inventory import inventory
from src.native_reference import one
from src.crop_square_neighbor_experiment import geometry_hash
ROOT=Path(__file__).resolve().parents[1]

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def source_scene(source, policy):
    inv = inventory(source)
    rows = [row for row in inv["objects"] if "F.Cu" in row["layers"]]
    unsupported = [row["id"] for row in rows if not row["geometry_sha256"]]
    if unsupported:
        raise ValueError("UNSUPPORTED_FCU_GEOMETRY:" + str(unsupported))
    shapes = [from_wkb(inv["payloads"][row["geometry_sha256"]]) for row in rows]
    tree = STRtree(shapes)
    occurrences = defaultdict(list)
    viewport = box(*policy["viewport_mm"])
    for index, (row, geometry) in enumerate(zip(rows, shapes)):
        if row["kind"] != "gr_circle" or not geometry.intersects(viewport):
            continue
        node = sexpdata.loads(source[slice(*row["source_span"])].decode())
        if str(one(node, "fill", ["none"])[0]) not in ("yes", "solid"):
            continue
        occurrences[row["geometry_sha256"]].append(index)
    sites = []
    for geometry_sha, indexes in occurrences.items():
        core = shapes[indexes[0]]
        center = [core.centroid.x, core.centroid.y]
        radius = (core.bounds[2]-core.bounds[0]+core.bounds[3]-core.bounds[1])/4
        sites.append({"source_id": min(rows[i]["id"] for i in indexes),
                      "aliases": sorted(rows[i]["id"] for i in indexes),
                      "core": core, "center": center, "radius": radius,
                      "geometry_sha256": geometry_sha, "indexes": indexes})
    sites.sort(key=lambda site: (site["center"][1], site["center"][0], site["source_id"]))
    assert len(sites) == 51
    # Fresh whole-source same-layer physical contact groups, not electrical nets.
    group_by_index = {}
    for site in sites:
        seed = site["indexes"][0]
        if seed not in group_by_index:
            seen = {seed}
            todo = [seed]
            while todo:
                current = todo.pop()
                for item in tree.query(shapes[current], predicate="intersects"):
                    index = int(item)
                    if index not in seen:
                        seen.add(index)
                        todo.append(index)
            members = sorted(rows[i]["id"] for i in seen)
            group_id = hashlib.sha256("\n".join(members).encode()).hexdigest()
            for index in seen:
                group_by_index[index] = group_id
        site["physical_contact_group"] = group_by_index[seed]
        site["enlarged_radius"] = policy["radius_multiplier"] * site["radius"]
    return inv, rows, shapes, tree, sites


def obstacles_for(site, rows, shapes, tree, source, settings, accepted=None):
    envelope = Point(*site["center"]).buffer(site["enlarged_radius"],
                                             quad_segs=settings.quad_segs)
    influence = envelope.buffer(settings.construction_gap_mm + 0.00002,
                                quad_segs=settings.quad_segs)
    result = []
    # Current accepted geometry is within its envelope, so extend search with
    # the live shape explicitly even when its source bounds miss the query.
    indexes = {int(i) for i in tree.query(influence)}
    if accepted:
        indexes.update(accepted["indexes"])
    for index in sorted(indexes):
        row, geometry = rows[index], shapes[index]
        if row["id"] in site["aliases"]:
            continue
        source_id = row["id"]
        if accepted and index in accepted["indexes"]:
            geometry = accepted["candidate"]
            source_id = accepted["source_id"]
        port = None
        if row["kind"] in ("segment", "arc") and geometry.intersects(
                site["core"].buffer(1e-7, quad_segs=settings.quad_segs)):
            raw = source[slice(*row["source_span"])].decode()
            width = re.search(r"\(\s*width\s+([0-9.]+)\s*\)", raw)
            if not width:
                raise ValueError("SOURCE_ATTACHMENT_WIDTH_UNAVAILABLE:" + row["id"])
            lateral = max(0.005, float(width.group(1))/2 + 0.005)
            port = geometry.buffer(lateral, quad_segs=settings.quad_segs).intersection(
                site["core"].buffer(site["enlarged_radius"]-site["radius"],
                                     quad_segs=settings.quad_segs))
        result.append({"source_id": source_id, "geometry": geometry,
                       "kind": row["kind"], "port_zone": port})
    return result


def site_record(site):
    return {key: site[key] for key in ("source_id", "aliases", "center", "radius",
                                       "enlarged_radius", "geometry_sha256",
                                       "physical_contact_group")}


def obstacle_records(obstacles):
    return [{"source_id": row["source_id"], "kind": row["kind"],
             "geometry_sha256": geometry_hash(row["geometry"]),
             "port_zone_wkb": to_wkb(row["port_zone"], byte_order=1).hex()
             if row["port_zone"] is not None else None}
            for row in obstacles]


def path_for(geometry):
    if geometry.is_empty:
        return ""
    if geometry.geom_type in ("MultiPolygon", "GeometryCollection"):
        return " ".join(path_for(part) for part in geometry.geoms)
    if geometry.geom_type != "Polygon":
        return ""
    def ring(coords):
        return "M " + " L ".join(f"{x:.9f} {y:.9f}" for x, y, *_ in coords) + " Z"
    return " ".join([ring(geometry.exterior.coords),
                     *(ring(part.coords) for part in geometry.interiors)])


def shape(geometry, fill, stroke="none", width=.002, opacity=1, dash=""):
    return (f'<path d="{path_for(geometry)}" fill="{fill}" stroke="{stroke}" '
            f'stroke-width="{width}" opacity="{opacity}" fill-rule="evenodd" '
            f'stroke-dasharray="{dash}"/>')



def verify_assets():
    lines=(ROOT/'contracts/asset_manifest.sha256').read_text().splitlines()
    for line in lines:
        expected,relative=line.split(maxsplit=1)
        if sha(ROOT/relative.lstrip('*'))!=expected:raise ValueError('ASSET_HASH_MISMATCH:'+relative)
    return {'status':'PASS','files':len(lines),'manifest_sha256':sha(ROOT/'contracts/asset_manifest.sha256')}
