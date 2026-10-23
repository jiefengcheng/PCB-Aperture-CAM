"""Source-bound, non-authorizing profile for the pinned three-member G22 family."""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import re
import warnings
from collections import Counter
from pathlib import Path
from typing import Any

from shapely import STRtree, from_wkb
from shapely.geometry import box
from shapely.affinity import scale
from gerbonara.rs274x import GerberFile
from gerbonara.utils import MM
from src.gerber_image import read_image as strict_read_gerber_image

from src.native_inventory import inventory


DATASET_REL = Path("dataset/szu-comm_3020301113B_intake_ready_20261021_v1")
ORG_BOARD_REL = DATASET_REL / "raw/ORG/top.kicad_pcb"
ORG_PROJECT_REL = DATASET_REL / "raw/ORG/top.kicad_pro"
EDIT_BOARD_REL = DATASET_REL / "raw/EDIT/top_layer.kicad_pcb"
PROJECTION_REL = Path(
    "out/ingestion/workbench/pair-selection-v6/run-22d82f479a3b49beb19fac6a91615daf"
    "/org_family_maps/06fae5f16739c44c/review.json"
)
EXPECTED = {
    "dataset_id": "client:szu-comm:3020301113b:intake-20261021:v1",
    "input_snapshot_id": "13dc1b667f39688c3f95c28f38ae9b256a6b9fb54d899b521ca7d2773412b67d",
    "org_source_sha256": "850c4c74d55717a721d4bbed7ec876ee086f475efd97f69bb5b5164ef77533a0",
    "org_revision": "a6456452a162db04b776fcd4e3b9da2813f5d2a491125d5b4e6ad9976054cfd8",
    "map_revision": "2e3a279a5f0db97937d3a2374806910d02eeb8d4aa1df522cde232ff8cb1300c",
    "projection_sha256": "0dc65fba0779e3fca83be2a15b4e9fac1942b2bc846c9aa8d62069eec83dc445",
    "projection_file_sha256": "34bda27b9195a87f31fe03f5fe92a9bba7a597e308e53bdc2a3c9f93ef2c9f91",
    "family_key": "cdca145fddd555c55a8cdd3b94d08fa4546738a9228e4d20cbaa295881ac7d53",
    "member_keys": [
        "0bcaad306c62b68e069df6bc1daf9472be9c6d294d718fee990ba868655e6ff9",
        "439135b39508c0c2152da7a76150bb5cb34f49a5a1e8cd94a134393fd9ee2569",
        "58155bbdb4e5841e838b31b495f8cb7afe0892da903639e471e044a26b6587dc",
    ],
}
NEIGHBOR_LIMIT_MM = 0.5
NEIGHBOR_ROWS = 8
CONTEXT_GERBER_REL = [
    DATASET_REL / "raw/ORG/top_layer.gdo.gbr",
    DATASET_REL / "raw/ORG/top_soldermask.gdo.gbr",
    DATASET_REL / "raw/ORG/top_solderpaste.gdo.gbr",
    DATASET_REL / "raw/ORG/cvl_top.gdo.gbr",
    DATASET_REL / "raw/ORG/cvl_bottom.gdo.gbr",
    DATASET_REL / "raw/ORG/sus_bottom.gdo.gbr",
    DATASET_REL / "raw/ORG/outboard.gdo.gbr",
]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_source_id(source_sha: str, span: list[int]) -> str:
    return f"{source_sha}:bytes:{span[0]}:{span[1]}"


def resolve_context_claim(
    evidence: list[dict[str, Any]], *, claim: str, subject_id: str, revision: str
) -> dict[str, Any]:
    """Resolve explicit, source-revision-bound yes/no claims; never infer from layer labels."""
    applicable = [
        item for item in evidence
        if item.get("claim") == claim and item.get("subject_id") == subject_id
        and item.get("source_revision") == revision and item.get("value") in (True, False)
    ]
    rejected = [
        item for item in evidence
        if item.get("claim") == claim and item.get("subject_id") == subject_id
        and item.get("source_revision") != revision
    ]
    values = sorted({item["value"] for item in applicable})
    if not applicable:
        status = "UNKNOWN"
    elif len(values) > 1:
        status = "CONFLICT"
    else:
        status = "DECLARED_TRUE" if values[0] else "DECLARED_FALSE"
    return {
        "status": status,
        "applicable_evidence": applicable,
        "rejected_wrong_revision_evidence": rejected,
    }


def reference_authority_status(_layer_label: str, _geometric_match: bool) -> str:
    """Layer labels and geometric coincidence are deliberately insufficient authority."""
    return "UNKNOWN"


def _member_radius(member: dict[str, Any]) -> float:
    return float(member["geometry"]["shape_signature"]["radius_mm"])


def _object_row(records: dict[str, dict[str, Any]], raw: bytes, object_id: str, source_sha: str):
    row = records.get(object_id)
    if row is None:
        raise ValueError(f"projection source reference is missing from pinned inventory: {object_id}")
    if row.get("source_sha256") != source_sha:
        raise ValueError(f"projection source reference has a different source hash: {object_id}")
    if object_id != canonical_source_id(source_sha, row["source_span"]):
        raise ValueError(f"projection reference is not canonical for source span: {object_id}")
    source_text = raw[slice(*row["source_span"])].decode("utf-8")
    width = re.search(r"\(\s*width\s+([0-9]+(?:\.[0-9]+)?)\s*\)", source_text)
    net = re.search(r"\(\s*net\s+([0-9]+)(?:\s+\"([^\"]*)\")?\s*\)", source_text)
    return row, source_text, (float(width.group(1)) if width else None), (int(net.group(1)) if net else None)


def _geometry(payloads: dict[str, bytes], row: dict[str, Any]):
    digest = row.get("geometry_sha256")
    if not digest or digest not in payloads:
        raise ValueError(f"source object lacks stored WKB geometry: {row.get('id')}")
    return from_wkb(payloads[digest])


def _svg_path(geom: Any) -> str:
    """Serialize stored polygonal WKB into an SVG path without changing coordinates."""
    polygons = list(geom.geoms) if hasattr(geom, "geoms") else [geom]
    fragments = []
    for polygon in polygons:
        if not hasattr(polygon, "exterior"):
            continue
        for ring in [polygon.exterior, *polygon.interiors]:
            points = list(ring.coords)
            if points:
                fragments.append("M " + " L ".join(f"{x:.9f} {y:.9f}" for x, y, *_ in points) + " Z")
    return " ".join(fragments)


def _component(seed_id: str, rows: list[dict[str, Any]], shapes: list[Any], tree: STRtree, row_indexes: dict[str, int]):
    start = row_indexes.get(seed_id)
    if start is None:
        raise ValueError(f"seed is not represented in the F.Cu geometry inventory: {seed_id}")
    seen, front = {start}, [start]
    while front:
        current = front.pop()
        for candidate in tree.query(shapes[current], predicate="intersects"):
            index = int(candidate)
            if index not in seen:
                seen.add(index)
                front.append(index)
    return sorted((rows[index] for index in seen), key=lambda row: row["id"])


def _context_sources(root: Path, raw_board: bytes, project: dict[str, Any]) -> dict[str, Any]:
    docs = [
        DATASET_REL / "dataset.md", DATASET_REL / "index.md",
        DATASET_REL / "evidence/index.md", DATASET_REL / "qualification/index.md",
        DATASET_REL / "sources/index.md", DATASET_REL / "runbooks/profiling.md",
    ]
    declared_profile = json.loads((root / DATASET_REL / "metadata/profile.json").read_text(encoding="utf-8"))
    raw_inputs = [DATASET_REL / "raw" / row["path"] for row in declared_profile["files"]]
    search_files = list(dict.fromkeys([
        *raw_inputs,
        DATASET_REL / "metadata/manifest.json", DATASET_REL / "metadata/profile.json",
        DATASET_REL / "metadata/registration_recipe.json", *docs,
    ]))
    terms = {
        "supported_termination": r"stiffener|backer|support(?:ed)?|termination(?:_region)?",
        "active_bending": r"bend(?:ing)?|flex(?:ure)?|fold(?:_line)?",
        "electrical_restriction": r"no[-_ ]?copper|do[-_ ]?not[-_ ]?modify|no[-_ ]?change|restricted(?:_region)?|forbidden",
    }
    counts: dict[str, dict[str, int]] = {key: {} for key in terms}
    declared_hashes = {row["path"]: row["sha256"] for row in declared_profile["files"]}
    raw_source_status: dict[str, dict[str, str | None]] = {}
    skipped_raw_sources = []
    for relative in search_files:
        data = (root / relative).read_bytes()
        relative_to_dataset = relative.relative_to(DATASET_REL)
        if relative_to_dataset.parts[0] == "raw":
            raw_relative = Path(*relative_to_dataset.parts[1:]).as_posix()
            expected_hash = declared_hashes.get(raw_relative)
            actual_hash = sha256(data)
            status = "MATCH" if expected_hash == actual_hash else "MISMATCH"
            raw_source_status[relative.as_posix()] = {"intake_profile_sha256": expected_hash, "status": status}
            if status != "MATCH":
                skipped_raw_sources.append({"path": relative.as_posix(), "status": status,
                                            "intake_profile_sha256": expected_hash, "actual_sha256": actual_hash,
                                            "reason": "Excluded from lexical search because its bytes differ from the intake-profile identity."})
                continue
        text = data.decode("utf-8", errors="replace")
        for key, pattern in terms.items():
            counts[key][relative.as_posix()] = len(re.findall(pattern, text, flags=re.IGNORECASE))

    board_text = raw_board.decode("utf-8", errors="replace")
    layer_table = re.search(r"\(layers\s+(.*?)\n\s*\)", board_text, flags=re.DOTALL)
    declared_layers = re.findall(r"\(\s*\d+\s+([^\s)]+)\s+(signal|user)\s*\)", layer_table.group(1)) if layer_table else []
    return {
        "context_claims": {
            claim: {
                "status": "UNKNOWN",
                "reason": "No member-specific, revision-matched authoritative declaration surfaced in the bounded lexical scan; zero keyword hits do not prove semantic absence.",
                "evidence": [],
            }
            for claim in ("supported_termination", "active_bending", "electrical_restriction")
        },
        "search": {
            "files": [
                {"path": relative.as_posix(), "sha256": sha256((root / relative).read_bytes()),
                 **raw_source_status.get(relative.as_posix(), {})}
                for relative in search_files
            ],
            "term_hit_counts": counts,
            "skipped_raw_sources": skipped_raw_sources,
            "method_and_limit": "Case-insensitive lexical scan across every raw source file listed in the admitted intake profile plus the listed package documents. Zero hits do not prove semantic absence; filenames, Gerber load names, or geometry do not qualify process roles or region claims.",
            "board_generator": "gerbview" if '(generator "gerbview")' in board_text else "NOT_IDENTIFIED",
            "declared_board_layers": [{"name": layer, "type": layer_type} for layer, layer_type in declared_layers],
            "project_defaults": {
                "min_clearance_mm": project.get("board", {}).get("design_settings", {}).get("rules", {}).get("min_clearance"),
                "min_track_width_mm": project.get("board", {}).get("design_settings", {}).get("rules", {}).get("min_track_width"),
                "default_netclass_clearance_mm": next((row.get("clearance") for row in project.get("net_settings", {}).get("classes", []) if row.get("name") == "Default"), None),
                "netclass_assignments": project.get("net_settings", {}).get("netclass_assignments", {}),
                "interpretation": "Generic KiCad project settings only; no member-specific rule or engineering authority is established.",
            },
        },
    }


def _gerber_bbox_in_board_coordinates(obj: Any):
    bounds = obj.bounding_box(unit=MM)
    if not bounds or any(value is None for point in bounds for value in point):
        return None
    (min_x, min_y), (max_x, max_y) = bounds
    # ORG Gerber is emitted with positive plot Y opposite KiCad's board-Y-down frame.
    return box(min_x, -max_y, max_x, -min_y)


def _load_context_gerbers(root: Path) -> dict[str, dict[str, Any]]:
    profile_rows = {row["path"]: row for row in json.loads((root / DATASET_REL / "metadata/profile.json").read_text())["files"]}
    result = {}
    for relative in CONTEXT_GERBER_REL:
        path = root / relative
        raw = path.read_bytes()
        relative_to_raw = relative.relative_to(DATASET_REL / "raw").as_posix()
        declared = profile_rows.get(relative_to_raw)
        source_sha = sha256(raw)
        if declared is None or declared.get("sha256") != source_sha:
            raise ValueError(f"Gerber context source differs from the admitted dataset profile: {relative_to_raw}")
        caught = []
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            parsed = GerberFile.open(path)
        try:
            strict_read_gerber_image(path)
            strict_probe = {"status": "SUPPORTED", "reason": None}
        except Exception as error:
            strict_probe = {"status": "UNSUPPORTED", "reason": f"{type(error).__name__}: {error}"}
        features = []
        unsupported_bounds = 0
        for ordinal, obj in enumerate(parsed.objects):
            try:
                geom = _gerber_bbox_in_board_coordinates(obj)
            except Exception:
                geom = None
            if geom is None or geom.is_empty:
                unsupported_bounds += 1
                continue
            features.append({"ordinal": ordinal, "type": type(obj).__name__, "geometry": geom, "bounds_mm": list(geom.bounds)})
        result[relative_to_raw] = {
            "path": relative.as_posix(), "sha256": source_sha, "features": features,
            "feature_count": len(parsed.objects), "bounded_feature_count": len(features),
            "unbounded_feature_count": unsupported_bounds,
            "file_attributes": parsed.file_attrs,
            "warnings": [{"category": item.category.__name__, "message": str(item.message)} for item in caught],
            "strict_project_geometry_parser_probe": strict_probe,
            "parser": f"Gerbonara {importlib.metadata.version('gerbonara')} bounding_box(unit=MM)",
            "coordinate_transform": "x unchanged; Gerber Y reflected into KiCad board-Y-down coordinates",
            "interpretation": "Source filename/load-name and plot geometry only; no authoritative process-role or region declaration is inferred.",
        }
    return result


def _measure_layer_bbox_gaps(seed_geom: Any, gerber_rows: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    measurements = []
    for layer_name, data in gerber_rows.items():
        candidates = []
        for item in data["features"]:
            bbox_geom = item["geometry"]
            candidates.append((seed_geom.distance(bbox_geom), item))
        if not candidates:
            measurements.append({"path": data["path"], "sha256": data["sha256"], "status": "NOT_MEASURED_NO_BOUNDED_FEATURES",
                                 "feature_count": data["feature_count"], "unbounded_feature_count": data["unbounded_feature_count"],
                                 "file_attributes": data["file_attributes"], "warnings": data["warnings"], "parser": data["parser"],
                                 "interpretation": data["interpretation"]})
            continue
        distance, closest = min(candidates, key=lambda row: (row[0], row[1]["ordinal"]))
        # Axis-aligned object boxes contain the plotted feature. Distance to the closest box is a conservative lower bound.
        measurements.append({
            "path": data["path"], "source_layer_label": layer_name, "sha256": data["sha256"],
            "feature_count": data["feature_count"], "unbounded_feature_count": data["unbounded_feature_count"],
            "nearest_feature_ordinal": closest["ordinal"], "nearest_feature_type": closest["type"],
            "nearest_feature_bounds_mm": closest["bounds_mm"], "seed_to_feature_bbox_distance_lower_bound_mm": distance,
            "seed_bbox_matches_feature_bbox_within_5um": all(abs(a-b) <= 0.000005 for a,b in zip(seed_geom.bounds,closest["bounds_mm"])),
            "file_attributes": data["file_attributes"], "warnings": data["warnings"], "parser": data["parser"],
            "strict_project_geometry_parser_probe": data["strict_project_geometry_parser_probe"],
            "coordinate_transform": data["coordinate_transform"], "interpretation": data["interpretation"],
        })
    return measurements


def _dataset_manifest_result(root: Path) -> dict[str, Any]:
    manifest_path = root / DATASET_REL / "SHA256SUMS"
    checked, failed, missing = [], [], []
    for line in manifest_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        digest, relative = line.split(None, 1)
        relative = relative.lstrip("* ")
        path = root / DATASET_REL / relative
        if not path.is_file():
            missing.append(relative)
        elif sha256(path.read_bytes()) != digest:
            failed.append(relative)
        else:
            checked.append(relative)
    status = "PASS" if not failed and not missing else "MISMATCH"
    return {"status": status, "checked_count": len(checked), "failed_paths": failed, "missing_paths": missing,
            "manifest_path": DATASET_REL.joinpath("SHA256SUMS").as_posix(),
            "note": "The mismatching paths are reported as-is; profiling does not repair or reseal the intake package."}


def build_profile(root: Path) -> dict[str, Any]:
    projection_bytes = (root / PROJECTION_REL).read_bytes()
    projection = json.loads(projection_bytes)
    source_bytes = (root / ORG_BOARD_REL).read_bytes()
    source_sha = sha256(source_bytes)
    projection_byte_sha = sha256(projection_bytes)
    binding = projection.get("binding", {})
    checks = {
        "org_source_sha256": source_sha,
        "projection_file_sha256": projection_byte_sha,
        "dataset_id": binding.get("dataset_id"),
        "input_snapshot_id": binding.get("input_snapshot_id"),
        "org_revision": binding.get("org_revision"),
        "map_revision": binding.get("map_revision"),
        "projection_sha256": projection.get("projection_sha256"),
    }
    for name, expected in checks.items():
        if expected != EXPECTED[name]:
            raise ValueError(f"pinned G22 input mismatch for {name}: {expected!r}")

    family = next((item for item in projection.get("families", []) if item.get("family_key") == EXPECTED["family_key"]), None)
    if family is None or family.get("member_keys") != EXPECTED["member_keys"]:
        raise ValueError("the pinned G22 family membership differs from the confirmed three-member example")
    members = {item["member_key"]: item for item in projection.get("members", []) if item.get("member_key") in EXPECTED["member_keys"]}
    if set(members) != set(EXPECTED["member_keys"]):
        raise ValueError("one or more confirmed G22 members are absent from the projection")

    inv = inventory(source_bytes)
    records = {row["id"]: row for row in inv["objects"]}
    payloads = inv["payloads"]
    fcu_rows = [row for row in inv["objects"] if "F.Cu" in row.get("layers", []) and row.get("geometry_sha256") in payloads]
    fcu_shapes = [_geometry(payloads, row) for row in fcu_rows]
    tree = STRtree(fcu_shapes)
    row_indexes = {row["id"]: index for index, row in enumerate(fcu_rows)}
    project_bytes = (root / ORG_PROJECT_REL).read_bytes()
    project = json.loads(project_bytes)
    context = _context_sources(root, source_bytes, project)
    context_gerbers = _load_context_gerbers(root)
    cards = []

    for ordinal, key in enumerate(EXPECTED["member_keys"], start=1):
        member = members[key]
        references = []
        roles: dict[str, list[dict[str, Any]]] = {}
        for ref in member.get("source_refs", []):
            row, source_text, width_mm, net_id = _object_row(records, source_bytes, ref["object_id"], source_sha)
            geom = _geometry(payloads, row)
            item = {
                "role": ref["role"], "object_id": ref["object_id"], "source_revision": ref.get("source_revision"),
                "kind": row["kind"], "layers": row.get("layers", []), "geometry_sha256": row.get("geometry_sha256"),
                "bounds_mm": list(geom.bounds), "area_mm2": geom.area,
                "width_mm": width_mm, "net_id": net_id,
                "source_span": list(row["source_span"]), "svg_path": _svg_path(geom),
            }
            references.append(item)
            roles.setdefault(ref["role"], []).append((item, geom))
        seeds = roles.get("local_land_candidate_seed", [])
        if len(seeds) != 1:
            raise ValueError(f"expected one seed for member {key}")
        seed_item, seed_geom = seeds[0]
        if seed_item["geometry_sha256"] != member["geometry"]["geometry_sha256"]:
            raise ValueError(f"seed geometry hash differs from family projection for {key}")
        seed_id = seed_item["object_id"]
        component = _component(seed_id, fcu_rows, fcu_shapes, tree, row_indexes)
        group = member.get("physical_group", {})
        kind_counts = dict(Counter(row["kind"] for row in component))
        if len(component) != group.get("source_member_count") or kind_counts != group.get("source_member_kind_counts"):
            raise ValueError(f"recomputed physical-contact group differs from projection for {key}")
        component_ids = {row["id"] for row in component}

        references_measured = []
        for role in ("F.Mask_geometric_feature_candidate", "F.Paste_geometric_feature_candidate"):
            rows_for_role = roles.get(role, [])
            if len(rows_for_role) != 1:
                raise ValueError(f"expected one {role} for member {key}")
            ref_item, ref_geom = rows_for_role[0]
            geometric_match = bool(seed_geom.equals(ref_geom))
            references_measured.append({
                **ref_item,
                "seed_center_offset_mm": [ref_geom.centroid.x - seed_geom.centroid.x, ref_geom.centroid.y - seed_geom.centroid.y],
                "seed_distance_mm": seed_geom.distance(ref_geom),
                "intersection_area_mm2": seed_geom.intersection(ref_geom).area,
                "symmetric_difference_area_mm2": seed_geom.symmetric_difference(ref_geom).area,
                "boundary_hausdorff_distance_mm": seed_geom.boundary.hausdorff_distance(ref_geom.boundary),
                "geos_equals_seed": geometric_match,
                "authority_status": reference_authority_status("/".join(ref_item["layers"]), geometric_match),
                "fixed_status": "UNKNOWN",
                "authority_note": "Layer label and geometric coincidence identify a candidate only; process role, registration authority, and fixed/editable status are not established.",
            })

        traces = []
        for trace_item, trace_geom in roles.get("incident_trace", []):
            traces.append({
                **trace_item,
                "seed_intersects": bool(seed_geom.intersects(trace_geom)),
                "seed_distance_mm": seed_geom.distance(trace_geom),
                "seed_intersection_area_mm2": seed_geom.intersection(trace_geom).area,
                "interpretation": "Geometric contact only; net 0 is not named net intent or electrical connectivity.",
            })
        if len(traces) != 2 or not all(item["seed_intersects"] for item in traces):
            raise ValueError(f"expected two incident geometric trace contacts for member {key}")

        def context_for(subject_id: str) -> dict[str, Any]:
            empty_evidence: list[dict[str, Any]] = []
            return {
                claim: {
                    **resolve_context_claim(empty_evidence, claim=claim, subject_id=subject_id, revision=EXPECTED["org_revision"]),
                    "scope_note": "No permission or negative classification follows from UNKNOWN.",
                }
                for claim in ("supported_termination", "active_bending", "electrical_restriction")
            }

        x0, y0, x1, y1 = seed_geom.bounds
        search = box(x0 - NEIGHBOR_LIMIT_MM, y0 - NEIGHBOR_LIMIT_MM, x1 + NEIGHBOR_LIMIT_MM, y1 + NEIGHBOR_LIMIT_MM)
        candidate_indexes = [int(index) for index in tree.query(search)]
        neighbors = []
        for index in candidate_indexes:
            row = fcu_rows[index]
            if row["id"] in component_ids:
                continue
            geom = fcu_shapes[index]
            distance = seed_geom.distance(geom)
            if distance <= NEIGHBOR_LIMIT_MM:
                neighbors.append({
                    "object_id": row["id"], "kind": row["kind"], "bounds_mm": list(geom.bounds),
                    "geometry_sha256": row["geometry_sha256"], "gap_from_seed_mm": distance,
                    "svg_path": _svg_path(geom),
                    "outside_member_contact_group": True,
                    "family_member_key": next((candidate_key for candidate_key in EXPECTED["member_keys"] if candidate_key != key and any(ref["object_id"] == row["id"] for ref in members[candidate_key].get("source_refs", []) if ref["role"] == "local_land_candidate_seed")), None),
                    "interpretation": "Nearby same-layer geometry only; not a clearance rule, net, electrical obstacle, or treatment conclusion.",
                })
        neighbors.sort(key=lambda item: (item["gap_from_seed_mm"], item["object_id"]))

        diameter = _member_radius(member) * 2
        seed_context = {"subject_id": seed_id, "claims": context_for(seed_id)}
        trace_context = [{"subject_id": trace["object_id"], "claims": context_for(trace["object_id"])} for trace in traces]
        mechanical_layer_geometry = {
            "seed": _measure_layer_bbox_gaps(seed_geom, context_gerbers),
            "traces": [
                {"subject_id": trace["object_id"], "kind": trace["kind"],
                 "layers": _measure_layer_bbox_gaps(from_wkb(payloads[trace["geometry_sha256"]]), context_gerbers)}
                for trace in traces
            ],
        }
        cards.append({
            "ordinal": ordinal, "member_key": key, "catalogue_record_id": member["catalogue_record_id"],
            "center_mm": list(seed_geom.centroid.coords[0]), "seed_source_id": seed_id,
            "seed": {**seed_item, "diameter_mm": diameter, "radius_mm": _member_radius(member), "coordinate_frame": member["geometry"]["coordinate_frame"]},
            "physical_contact_group": {
                "key": member["physical_group_key"], "count": len(component), "kind_counts": kind_counts,
                "predicate": "transitive same-layer F.Cu GEOS-intersects over pinned stored WKB; geometric only",
                "source_member_ids": [row["id"] for row in component],
            },
            "references": references_measured,
            "traces": traces,
            "nearby_external_copper_geometry": neighbors[:NEIGHBOR_ROWS],
            "additional_org_layer_geometry": mechanical_layer_geometry,
            "context": {"seed": seed_context, "traces": trace_context},
        })

    geometries = {row["id"]: _geometry(payloads, row) for row in fcu_rows}
    arrangement = []
    for i, left in enumerate(cards):
        for right in cards[i + 1:]:
            left_geom, right_geom = geometries[left["seed_source_id"]], geometries[right["seed_source_id"]]
            arrangement.append({
                "from_member_key": left["member_key"], "to_member_key": right["member_key"],
                "center_distance_mm": left_geom.centroid.distance(right_geom.centroid),
                "edge_gap_mm": left_geom.distance(right_geom), "intersects": left_geom.intersects(right_geom),
            })

    assessed_object_count = sum(1 + len(card["traces"]) for card in cards)
    context_status = {
            claim: {"status_by_object": "UNKNOWN", "assessed_object_count": assessed_object_count,
                "reason": "Each of the three seeds and six attached trace candidates is assessed separately; source-layer geometry and filenames were checked, but the bounded lexical scan did not surface a member-specific authoritative declaration."}
        for claim in ("supported_termination", "active_bending", "electrical_restriction")
    }
    if project.get("net_settings", {}).get("netclass_assignments", {}) != {}:
        raise ValueError("the recorded empty netclass-assignment observation changed; re-audit before publishing")
    package_manifest = _dataset_manifest_result(root)
    return {
        "schema": "org-family-reference-region-profile/1",
        "status": "REVIEW_EVIDENCE_READY",
        "scope": "Three confirmed G22 ORG family members only; reuse the pinned family projection; no recognition rerun, treatment selection, simulation, blending, cutback, or copper modification.",
        "binding": {**EXPECTED, "projection_file_sha256": projection_byte_sha, "inventory_version": inv["version"],
                    "geometry_error_mm": inv.get("geometry_error_mm"), "per_curve_approximation_error_mm": inv.get("per_curve_approximation_error_mm")},
        "family": {"family_key": EXPECTED["family_key"], "status": family.get("status"), "members": cards, "pairwise_arrangement": arrangement,
                   "interpretation": "Provisional repeated-geometry hypothesis. The three members have separate identities and separate geometric contact groups."},
        "region_context_summary": context_status,
        "project_defaults": context["search"]["project_defaults"],
        "source_search": context["search"],
        "inventory_coverage": {
            "object_count": len(inv["objects"]), "kind_counts": dict(Counter(row["kind"] for row in inv["objects"])),
            "layer_counts": dict(Counter(layer for row in inv["objects"] for layer in row.get("layers", []))),
            "F.Cu_geometry_count": len(fcu_rows), "F.Cu_without_geometry": sum(1 for row in inv["objects"] if "F.Cu" in row.get("layers", []) and not row.get("geometry_sha256")),
            "parser_scope_note": "The ORG board is a GerbView-generated geometry source; these inventory counts do not establish a complete native design database, footprints, electrical connectivity, or manufacturing intent.",
        },
        "source_material_integrity": {
            "ORG_board_sha256_matches_pin": source_sha == EXPECTED["org_source_sha256"],
            "dataset_sha256_manifest": package_manifest,
        },
        "interpretation_limits": [
            "Layer names and matching geometric features do not prove mask/paste process purpose, registration authority, or fixed/editable status.",
            "The project file contains generic defaults, not a member-bound clearance or electrical authorization; the selected trace objects are net 0.",
            "Supported termination, active bending, and electrical-change restriction remain UNKNOWN for all three seeds and their attached traces.",
            "Nearby F.Cu geometry distances are seed-to-object gaps, not clearance-rule results or electrical obstacles.",
            f"The source package manifest status is {package_manifest['status']} (failed={package_manifest['failed_paths']}, missing={package_manifest['missing_paths']}); source board and projection identities independently match their pinned hashes.",
            "No treatment is selected; no copper is modified; no engineering or manufacturing qualification is asserted.",
        ],
    }
