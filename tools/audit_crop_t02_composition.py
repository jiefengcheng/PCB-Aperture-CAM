"""Fresh-process audit of T02 composition against its exact accepted T01 scene."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from shapely import STRtree, from_wkb, wkb
from shapely.affinity import scale
from shapely.geometry import LineString, Point, box
from shapely.ops import unary_union
from sexpdata import loads

from src import crop_circle_sources as circle_sources
from src.crop_rect_t02 import (RectGrowthPolicy, rectangular_feature,
                               envelope_constraint_records, _projected_size,
                               is_side_by_side_trace)
from src.native_inventory import arc_points
from src.native_reference import one
from src.org_edit_target_map import _inventory_side, _row_geometry

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUN = ROOT / "out/crop_dynamic_tasks/t02_rectangles_crop_20261025_v31"
DEFAULT_AUDIT = ROOT / "out/crop_dynamic_tasks/t02_composition_audit_20261025_v13"
AREA_TOL = 1e-8


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def is_simple_rectangle(geometry, tolerance: float = 1e-9) -> bool:
    """Check four straight orthogonal sides without relying on oriented-envelope heuristics."""
    if geometry.geom_type != "Polygon" or geometry.interiors:
        return False
    coords = list(geometry.exterior.coords)
    if len(coords) != 5:
        return False
    points = coords[:-1]
    if len({(round(x, 10), round(y, 10)) for x, y in points}) != 4:
        return False
    edges = [(points[(i + 1) % 4][0] - points[i][0],
              points[(i + 1) % 4][1] - points[i][1]) for i in range(4)]
    lengths = [(x*x + y*y) ** 0.5 for x, y in edges]
    if min(lengths) <= tolerance:
        return False
    if abs(lengths[0] - lengths[2]) > tolerance or abs(lengths[1] - lengths[3]) > tolerance:
        return False
    return abs(edges[0][0] * edges[1][0] + edges[0][1] * edges[1][1]) <= tolerance * lengths[0] * lengths[1]


def assert_t01_round_classes(sites: list[dict], decisions: list[dict], geometries: dict[str, object],
                             *, area_epsilon: float = 1e-10) -> dict:
    """Require every unchanged site to remain its exact core and round growth to be circular."""
    by_id = {d["source_id"]: d for d in decisions}
    if set(by_id) != {s["source_id"] for s in sites}:
        raise ValueError("T01_DECISION_SITE_COVERAGE_MISMATCH")
    round_growth = []
    unchanged = 0
    for site in sites:
        sid = site["source_id"]
        decision = by_id[sid]
        candidate = geometries[sid]
        core = site["core"]
        if core.difference(candidate).area > area_epsilon:
            raise ValueError(f"T01_CORE_LOSS:{sid}")
        if decision["decision"] == "ROUND_GROW_PRIORITY":
            expected = Point(*site["center"]).buffer(float(decision["proposed_radius_mm"]),
                                                        quad_segs=128)
            if not candidate.equals(expected):
                raise ValueError(f"T01_PRIORITY_NOT_ROUND:{sid}")
            round_growth.append(sid)
        elif not candidate.equals_exact(core, 0):
            raise ValueError(f"T01_UNAUTHORIZED_SHAPE_CHANGE:{sid}")
        else:
            unchanged += 1
    return {"status": "PASS_T01_ROUND_SHAPE_CLASSES", "site_count": len(sites),
            "unchanged_round_source_sites": unchanged, "round_priority_growth_sites": round_growth,
            "nonround_growth_sites": 0}


def audit(run_dir: Path, audit_dir: Path) -> dict:
    result = json.loads((run_dir / "t02_result.json").read_bytes())
    decisions_doc = json.loads((run_dir / "t02_decisions.json").read_bytes())
    dispositions = json.loads((run_dir / "feature_dispositions.json").read_bytes())
    policy_doc = json.loads((run_dir / "t02_policy.json").read_bytes())
    inventory_binding = json.loads((run_dir / "org_inventory_binding.json").read_bytes())
    receipt = json.loads((run_dir / "t02_execution_receipt.json").read_bytes())
    if result.get("status") != "EXPERIMENTAL_REAL_CROP_EXECUTED" or not result.get("all_per_target_checks_pass"):
        raise ValueError("T02_RUN_NOT_EXECUTED_WITH_ALL_LOCAL_CHECKS_PASS")
    policy_hash = sha_bytes((run_dir / "t02_policy.json").read_bytes())
    if policy_hash != result.get("policy_sha256") or policy_hash != decisions_doc.get("policy_sha256"):
        raise ValueError("T02_POLICY_HASH_BINDING_MISMATCH")
    inventory_dir = ROOT / inventory_binding.get("inventory_directory", "")
    if ROOT / "out" not in inventory_dir.resolve().parents:
        raise ValueError("T02_FROZEN_INVENTORY_PATH_OUTSIDE_OUT")
    inventory_manifest_path = inventory_dir / "SHA256SUMS.txt"
    inventory_manifest = inventory_manifest_path.read_bytes()
    if sha_bytes(inventory_manifest) != inventory_binding.get("inventory_manifest_sha256"):
        raise ValueError("T02_FROZEN_INVENTORY_MANIFEST_HASH_MISMATCH")
    for line in inventory_manifest.decode("utf-8").splitlines():
        expected_hash, relative_path = line.split("  ", 1)
        if sha_bytes((inventory_dir / relative_path).read_bytes()) != expected_hash:
            raise ValueError(f"T02_FROZEN_INVENTORY_FILE_HASH_MISMATCH:{relative_path}")
    inventory_report = json.loads((inventory_dir / "inventory_report.json").read_bytes())
    inventory_dispositions = json.loads((inventory_dir / "feature_dispositions.json").read_bytes())
    if (inventory_report.get("status") != "ORG_RECTANGLE_TARGET_SET_FROZEN"
            or inventory_report.get("source_sha256") != result.get("source_sha256")
            or inventory_report.get("policy_sha256") != policy_hash
            or inventory_binding.get("policy_sha256") != policy_hash
            or inventory_binding.get("source_sha256") != result.get("source_sha256")
            or result.get("org_inventory_manifest_sha256") != inventory_binding.get("inventory_manifest_sha256")
            or decisions_doc.get("inventory_manifest_sha256") != inventory_binding.get("inventory_manifest_sha256")
            or inventory_binding.get("inventory_report_sha256") != sha_bytes((inventory_dir / "inventory_report.json").read_bytes())
            or inventory_dispositions.get("target_set_sha256") != inventory_report.get("candidate_target_ids_sha256")
            or inventory_binding.get("target_set_sha256") != inventory_report.get("candidate_target_ids_sha256")):
        raise ValueError("T02_FROZEN_INVENTORY_CONTENT_BINDING_MISMATCH")
    trace_policy_v8 = "trace_interactions" in policy_doc
    side_gap_fraction = (0.0 if trace_policy_v8 else
                         float(policy_doc["side_trace_gap_reservation"]["fraction_of_original_surface_gap"]))
    policy = RectGrowthPolicy(
        max_axis_factor=float(policy_doc["factor_per_axis"]),
        construction_gap_mm=float(policy_doc["construction_gap_mm"]),
        hard_gap_mm=float(policy_doc["hard_experimental_gap_mm"]),
        geometry_tolerance_mm=float(policy_doc["geometry_tolerance_mm"]),
        quad_segs=int(policy_doc["quad_segs"]),
        side_trace_gap_fraction_of_org=side_gap_fraction,
    )
    policy.validate()

    owner_doc = json.loads((ROOT / "contracts/agent_abi/v0_1/owner_decisions.json").read_bytes())
    profiles_doc = json.loads((ROOT / "contracts/agent_abi/v0_1/registry.json").read_bytes())
    owner = owner_doc["decisions"][result["accepted_T01_decision_id"]]
    profile = profiles_doc["profiles"][owner["profile_id"]]
    scene_path = ROOT / profile["scene"]["path"]
    scene_bytes = scene_path.read_bytes()
    scene_hash = sha_bytes(scene_bytes)
    if (owner.get("status") != "ACCEPTED_VISUAL_CROP"
            or owner.get("scene_sha256") != scene_hash
            or result.get("accepted_T01_scene_sha256") != scene_hash
            or receipt.get("t01_scene_sha256") != scene_hash):
        raise ValueError("T02_ACCEPTED_T01_SCENE_BINDING_MISMATCH")
    t01_scene = from_wkb(scene_bytes)
    combined = from_wkb((run_dir / "t01_accepted_plus_t02.wkb").read_bytes())
    additions = from_wkb((run_dir / "t02_additions.wkb").read_bytes())
    crop = box(*result["crop_bounds_mm"])
    if t01_scene.difference(crop).area > AREA_TOL:
        raise ValueError("T01_SCENE_OUTSIDE_T02_CROP")

    # The exact imported scene must also be the geometry represented by the saved
    # pre-T02 ring payload, preventing a metadata-only hash binding.
    rings_doc = json.loads((run_dir / "accepted_t01_render_rings.json").read_bytes())
    rendered = []
    for item in rings_doc["polygons"]:
        rendered.append(__import__("shapely.geometry", fromlist=["Polygon"]).Polygon(
            item["exterior"], item["interiors"]))
    rendered_scene = unary_union(rendered) if rendered else crop.difference(crop)
    if rendered_scene.symmetric_difference(t01_scene).area > AREA_TOL:
        raise ValueError("T02_RENDERED_PRESTATE_DIFFERS_FROM_ACCEPTED_T01")

    lost_t01 = t01_scene.difference(combined).area
    unexpected_composition = combined.symmetric_difference(t01_scene.union(additions)).area
    if lost_t01 > AREA_TOL:
        raise ValueError("T02_COMPOSITION_LOST_ACCEPTED_T01_COPPER")
    if unexpected_composition > AREA_TOL:
        raise ValueError("T02_COMPOSITION_NOT_T01_PLUS_ADDITIONS")
    if additions.difference(crop).area > AREA_TOL or combined.difference(crop).area > AREA_TOL:
        raise ValueError("T02_COMPOSITION_OUTSIDE_CROP")

    org_path = ROOT / "dataset/szu-comm_3020301113B_intake_ready_20261021_v2/raw/ORG/top.kicad_pcb"
    org_bytes = org_path.read_bytes()
    source_hash = sha_bytes(org_bytes)
    if source_hash != result["source_sha256"] or source_hash != receipt["source_sha256"]:
        raise ValueError("T02_ORG_SOURCE_BINDING_MISMATCH")
    side = _inventory_side(org_bytes, source_hash)
    source_geometries = {}
    source_rows = {}
    feature_by_id = {}
    for row in side["rows"]:
        if "F.Cu" not in row.get("layers", []):
            continue
        geometry = (_row_geometry(row, side["payloads"])
                    if row.get("coverage") == "GEOMETRY_AVAILABLE" else None)
        if geometry is not None and not geometry.is_empty:
            source_geometries[row["id"]] = geometry
            source_rows[row["id"]] = row
            feature = rectangular_feature(row, side["payloads"], crop,
                                          max_axis_factor=float(policy_doc["factor_per_axis"]))
            if feature is not None:
                feature_by_id[row["id"]] = feature
    org_region = unary_union([geometry.intersection(crop) for geometry in source_geometries.values()])
    t01_additions = t01_scene.difference(org_region)
    accepted_t01_constraint_id = f"T01_SCENE:{owner['decision_id']}"
    limiting_source_geometries = dict(source_geometries)
    limiting_source_metadata = {sid: row for sid, row in source_rows.items()}
    if not t01_additions.is_empty:
        limiting_source_geometries[accepted_t01_constraint_id] = t01_additions
        limiting_source_metadata[accepted_t01_constraint_id] = {
            "kind": "accepted_T01_scene_addition", "source_span": [],
            "geometry_sha256": scene_hash,
        }
    run_source_rows = dispositions.get("dispositions", [])
    inv_source_rows = inventory_dispositions.get("dispositions", [])
    run_by_id = {row.get("source_id"): row for row in run_source_rows}
    inv_by_id = {row.get("source_id"): row for row in inv_source_rows}
    if (None in run_by_id or None in inv_by_id
            or len(run_by_id) != len(run_source_rows)
            or len(inv_by_id) != len(inv_source_rows)
            or set(run_by_id) != set(inv_by_id)):
        raise ValueError("T02_SOURCE_DISPOSITION_COVERAGE_MISMATCH")
    decision_by_id = {d["source_id"]: d for d in decisions_doc["decisions"]}
    if len(decision_by_id) != len(decisions_doc["decisions"]):
        raise ValueError("T02_DUPLICATE_TARGET_DECISION")
    for sid in sorted(inv_by_id):
        source = inv_by_id[sid]
        runtime_source = run_by_id[sid]
        for field in ("source_sha256", "source_span", "source_kind",
                      "source_geometry_sha256", "source_record_sha256",
                      "geometric_class", "disposition", "reason"):
            if runtime_source.get(field) != source.get(field):
                raise ValueError(f"T02_SOURCE_DISPOSITION_BINDING_MISMATCH:{field}:{sid}")
        if source.get("disposition") == "TREAT":
            result_row = runtime_source.get("t02_result")
            decision = decision_by_id.get(sid)
            if not isinstance(result_row, dict) or decision is None:
                raise ValueError(f"T02_TARGET_OUTCOME_MISSING:{sid}")
            if (result_row.get("decision") != decision.get("decision")
                    or result_row.get("candidate_geometry_sha256") != decision.get("candidate_geometry_sha256")
                    or result_row.get("accepted_size_mm_in_source_axes") != decision.get("accepted_size_mm_in_source_axes")):
                raise ValueError(f"T02_TARGET_OUTCOME_BINDING_MISMATCH:{sid}")
        elif "t02_result" in runtime_source:
            raise ValueError(f"T02_PROTECTED_SOURCE_HAS_EDIT_OUTCOME:{sid}")
    run_disposition_counts = Counter(row.get("disposition") for row in run_source_rows)
    run_class_counts = Counter(row.get("geometric_class") or "unclassified_protected_source"
                               for row in run_source_rows)
    if (dispositions.get("source_disposition_count") != len(run_source_rows)
            or dispositions.get("source_disposition_counts") != dict(sorted(run_disposition_counts.items()))
            or dispositions.get("source_class_counts") != dict(sorted(run_class_counts.items()))
            or dispositions.get("inventory_manifest_sha256") != inventory_binding.get("inventory_manifest_sha256")):
        raise ValueError("T02_SOURCE_DISPOSITION_SUMMARY_MISMATCH")

    target_rows = [row for row in run_source_rows if row.get("disposition") == "TREAT"]
    target_ids = {row["source_id"] for row in target_rows}
    if (len(target_ids) != int(result.get("target_set_count", -1)) or target_ids != set(decision_by_id)
            or target_ids != set(feature_by_id)):
        raise ValueError("T02_TARGET_INVENTORY_COVERAGE_MISMATCH")
    inventory_target_ids = {row["source_id"] for row in inventory_dispositions["dispositions"]
                            if row.get("disposition") == "TREAT"}
    if (target_ids != inventory_target_ids
            or len(target_ids) != int(inventory_report.get("candidate_target_count", -1))
            or sha_bytes("\n".join(sorted(target_ids)).encode()) != inventory_report.get("candidate_target_ids_sha256")
            or inventory_binding.get("target_count") != len(target_ids)):
        raise ValueError("T02_RUNTIME_TARGETS_DIFFER_FROM_FROZEN_INVENTORY")

    expected_additions = []
    target_growth = {}
    trace_kinds = (set(policy_doc["trace_interactions"]["trace_source_kinds"])
                   if trace_policy_v8 else
                   set(policy_doc["side_trace_gap_reservation"]["native_source_kinds"]))
    trace_copper_by_id = {sid: geometry for sid, geometry in source_geometries.items()
                          if source_rows[sid].get("kind") in trace_kinds
                          and "F.Cu" in source_rows[sid].get("layers", [])}

    def native_trace_centerline(row):
        start, end = map(int, row["source_span"])
        node = loads(org_bytes[start:end].decode("utf-8"))
        xy = lambda key: tuple(map(float, one(node, key)))
        points = ([xy("start"), xy("end")] if row["kind"] == "segment" else
                  arc_points(xy("start"), xy("mid"), xy("end")))
        return LineString(points)

    trace_centerline_by_id = ({sid: native_trace_centerline(source_rows[sid])
                               for sid in trace_copper_by_id}
                              if trace_policy_v8 else trace_copper_by_id)
    # The limiter receipt measures side interactions to centerlines and all other
    # deferred trace records to their source centerline geometry.
    trace_by_id = trace_centerline_by_id
    if inventory_binding.get("target_count") != len(target_ids):
        raise ValueError("T02_FROZEN_INVENTORY_TARGET_COUNT_MISMATCH")
    for sid in sorted(target_ids):
        feature = feature_by_id[sid]
        decision = decision_by_id[sid]
        candidate_path = run_dir / "t02_candidates" / (hashlib.sha256(sid.encode()).hexdigest() + ".wkb")
        candidate = from_wkb(candidate_path.read_bytes())
        if sha_bytes(candidate.wkb) != decision["candidate_geometry_sha256"]:
            raise ValueError(f"T02_CANDIDATE_HASH_MISMATCH:{sid}")
        core = feature["geometry"]
        if core.difference(candidate).area > policy.area_epsilon_mm2:
            raise ValueError(f"T02_TARGET_CORE_LOSS:{sid}")
        cap = scale(core, xfact=policy.max_axis_factor, yfact=policy.max_axis_factor,
                    origin=tuple(feature["center_mm"]))
        if candidate.difference(cap).area > policy.area_epsilon_mm2:
            raise ValueError(f"T02_TARGET_CAP_EXCEEDED:{sid}")
        if not is_simple_rectangle(candidate):
            raise ValueError(f"T02_RECTANGULAR_CONTOUR_RECESSED_OR_NOTCHED:{sid}")
        expected_envelopes = envelope_constraint_records(
            candidate, cap, crop,
            accepted_size_mm=_projected_size(candidate, feature["center_mm"], feature["orientation_radians"]),
            maximum_size_mm=[value * policy.max_axis_factor for value in feature["source_size_mm"]],
            policy_sha256=policy_hash,
            tolerance_mm=policy.geometry_tolerance_mm,
            area_epsilon_mm2=policy.area_epsilon_mm2,
        )
        recorded_limits = decision.get("limiting_constraints", {})
        if recorded_limits.get("policy_cap") != expected_envelopes["policy_cap"]:
            raise ValueError(f"T02_POLICY_CAP_WITNESS_MISMATCH:{sid}")
        if recorded_limits.get("crop_boundary") != expected_envelopes["crop_boundary"]:
            raise ValueError(f"T02_CROP_BOUNDARY_WITNESS_MISMATCH:{sid}")
        growth = candidate.difference(core)
        if decision.get("decision") == "GROW":
            if growth.area <= policy.area_epsilon_mm2:
                raise ValueError(f"T02_GROW_DECISION_HAS_NO_ADDITION:{sid}")
        elif decision.get("decision") == "KEEP":
            if growth.area > policy.area_epsilon_mm2 or candidate.symmetric_difference(core).area > policy.area_epsilon_mm2:
                raise ValueError(f"T02_KEEP_DECISION_CHANGED_SOURCE:{sid}")
        else:
            raise ValueError(f"T02_UNSUPPORTED_TARGET_DECISION:{sid}:{decision.get('decision')}")
        reservations = decision.get("trace_gap_reservations", [])
        expected_trace_ids = set()
        expected_trace_policy = {}
        for trace_id, trace_copper in trace_copper_by_id.items():
            trace_centerline = trace_centerline_by_id[trace_id]
            org_gap = core.distance(trace_copper)
            trace_kind = source_rows[trace_id].get("kind")
            side_by_side = is_side_by_side_trace(
                core, feature["center_mm"], feature["orientation_radians"],
                trace_centerline, trace_kind)
            if trace_policy_v8:
                required = policy.construction_gap_mm if side_by_side else 0.0
                relevant = ((side_by_side and trace_copper.distance(cap) + policy.geometry_tolerance_mm < required)
                            or (not side_by_side and trace_copper.distance(cap) <= policy.geometry_tolerance_mm))
            else:
                fraction = 1.0 if side_by_side else policy.side_trace_gap_fraction_of_org
                required = max(policy.construction_gap_mm, fraction * org_gap)
                relevant = trace_copper.distance(cap) + policy.geometry_tolerance_mm < required
            expected_trace_policy[trace_id] = (side_by_side, required, org_gap)
            if relevant:
                expected_trace_ids.add(trace_id)
        reserved_trace_ids = {r["source_id"] for r in reservations}
        if expected_trace_ids != reserved_trace_ids:
            raise ValueError(f"T02_TRACE_RESERVATION_COVERAGE_MISMATCH:{sid}")
        for reservation in reservations:
            trace = trace_by_id.get(reservation["source_id"])
            trace_copper = trace_copper_by_id.get(reservation["source_id"])
            if trace is None or trace_copper is None:
                raise ValueError(f"T02_TRACE_RESERVATION_SOURCE_MISSING:{sid}:{reservation['source_id']}")
            org_gap = core.distance(trace_copper)
            expected_side_by_side, required, _ = expected_trace_policy[reservation["source_id"]]
            if reservation.get("side_by_side_classification") != expected_side_by_side:
                raise ValueError(f"T02_TRACE_SIDE_BY_SIDE_CLASSIFICATION_MISMATCH:{sid}:{reservation['source_id']}")
            if abs(org_gap - float(reservation["org_surface_gap_mm"])) > policy.geometry_tolerance_mm:
                raise ValueError(f"T02_TRACE_ORG_GAP_MISMATCH:{sid}:{reservation['source_id']}")
            if abs(required - float(reservation["required_retained_gap_mm"])) > policy.geometry_tolerance_mm:
                raise ValueError(f"T02_TRACE_POLICY_GAP_MISMATCH:{sid}:{reservation['source_id']}")
            final_gap_geometry = trace if (trace_policy_v8 and expected_side_by_side) else trace_copper
            if (decision.get("decision") == "GROW" and required > 0.0
                    and growth.distance(final_gap_geometry) + policy.geometry_tolerance_mm < required):
                raise ValueError(f"T02_TRACE_GAP_NOT_PRESERVED:{sid}:{reservation['source_id']}")
        target_growth[sid] = growth
        expected_additions.append(growth)

    # Reconstruct each recorded limiter from source geometry and the deterministic
    # accepted-scene order. This verifies audit-row identity and distances; it does
    # not create an independent geometry-kernel qualification.
    target_decision_order = decisions_doc["decisions"]
    if [row["source_id"] for row in target_decision_order] != [
            row["source_id"] for row in sorted(
                target_decision_order,
                key=lambda row: (feature_by_id[row["source_id"]]["center_mm"][1],
                                 feature_by_id[row["source_id"]]["center_mm"][0],
                                 row["source_id"]))]:
        raise ValueError("T02_DECISION_ORDER_NOT_DETERMINISTIC")
    earlier_grown_ids = []
    limit_record_count = 0
    for decision in target_decision_order:
        sid = decision["source_id"]
        growth = target_growth[sid]
        recorded = decision.get("limiting_constraints")
        if not isinstance(recorded, dict):
            raise ValueError(f"T02_LIMITING_CONSTRAINTS_MISSING:{sid}")

        def verify_nearest(record, candidates, threshold, label):
            if growth.is_empty:
                if record is not None:
                    raise ValueError(f"T02_UNEXPECTED_LIMIT_RECORD_FOR_EMPTY_GROWTH:{label}:{sid}")
                return None
            expected_rows = []
            for candidate_id, geometry in candidates.items():
                gap = float(growth.distance(geometry))
                source_row = limiting_source_metadata.get(candidate_id, {})
                expected_rows.append({
                    "source_id": candidate_id,
                    "source_kind": source_row.get("kind"),
                    "source_span": list(source_row.get("source_span", [])),
                    "source_geometry_sha256": source_row.get("geometry_sha256"),
                    "measured_gap_mm": gap,
                    "required_gap_mm": threshold,
                    "margin_mm": gap - threshold,
                    "passes_tolerance": gap + policy.geometry_tolerance_mm >= threshold,
                })
            expected = min(expected_rows, key=lambda row: (row["margin_mm"], row["source_id"])) if expected_rows else None
            if expected is None:
                if record is not None:
                    raise ValueError(f"T02_UNEXPECTED_LIMIT_RECORD:{label}:{sid}")
                return None
            if not isinstance(record, dict):
                raise ValueError(f"T02_LIMIT_RECORD_MISSING:{label}:{sid}")
            for field in ("source_id", "source_kind", "source_span", "source_geometry_sha256",
                          "required_gap_mm", "passes_tolerance"):
                if record.get(field) != expected[field]:
                    raise ValueError(f"T02_LIMIT_RECORD_BINDING_MISMATCH:{label}:{field}:{sid}")
            for field in ("measured_gap_mm", "margin_mm"):
                if abs(float(record.get(field, float("inf"))) - expected[field]) > 1e-12:
                    raise ValueError(f"T02_LIMIT_RECORD_MEASUREMENT_MISMATCH:{label}:{field}:{sid}")
            return expected

        expected_source = verify_nearest(
            recorded.get("nearest_original_protected_source"),
            {source_id: geometry for source_id, geometry in limiting_source_geometries.items() if source_id != sid},
            policy.construction_gap_mm, "original_source")
        expected_prior = verify_nearest(
            recorded.get("nearest_prior_t02_addition"),
            {prior_id: target_growth[prior_id] for prior_id in earlier_grown_ids},
            policy.construction_gap_mm, "prior_t02")

        trace_records = recorded.get("trace_reservations", [])
        decision_reservations = {row["source_id"]: row for row in decision.get("trace_gap_reservations", [])}
        if growth.is_empty and trace_records:
            raise ValueError(f"T02_UNEXPECTED_TRACE_LIMIT_RECORD_FOR_EMPTY_GROWTH:{sid}")
        expected_limit_trace_ids = (set() if growth.is_empty else set(decision_reservations))
        if {row.get("source_id") for row in trace_records} != expected_limit_trace_ids:
            raise ValueError(f"T02_LIMIT_TRACE_SET_MISMATCH:{sid}")
        trace_limit_rows = []
        for actual in trace_records:
            source_id = actual["source_id"]
            trace = trace_by_id.get(source_id)
            if trace is None:
                raise ValueError(f"T02_LIMIT_TRACE_SOURCE_MISSING:{sid}:{source_id}")
            reservation = decision_reservations[source_id]
            gap = float(growth.distance(trace))
            required = float(reservation["required_retained_gap_mm"])
            gap_field = ("measured_final_centerline_gap_mm"
                         if trace_policy_v8 and reservation.get("side_by_side_classification")
                         else "measured_final_gap_mm")
            if (actual.get("source_kind") != source_rows[source_id].get("kind")
                    or actual.get("source_span") != list(source_rows[source_id].get("source_span", []))
                    or actual.get("source_geometry_sha256") != source_rows[source_id].get("geometry_sha256")
                    or actual.get("required_retained_gap_mm") != required
                    or actual.get("org_surface_gap_mm") != reservation["org_surface_gap_mm"]
                    or actual.get("required_centerline_gap_mm") != reservation.get("required_centerline_gap_mm")
                    or actual.get("passes_tolerance") != (gap + policy.geometry_tolerance_mm >= required)
                    or abs(float(actual.get(gap_field, float("inf"))) - gap) > 1e-12
                    or abs(float(actual.get("clearance_margin_mm", float("inf"))) - (gap - required)) > 1e-12):
                raise ValueError(f"T02_LIMIT_TRACE_MEASUREMENT_MISMATCH:{sid}:{source_id}")
            trace_limit_rows.append({
                "source_id": source_id,
                "source_kind": source_rows[source_id].get("kind"),
                "source_span": list(source_rows[source_id].get("source_span", [])),
                "source_geometry_sha256": source_rows[source_id].get("geometry_sha256"),
                "measured_gap_mm": gap,
                "required_gap_mm": required,
                "margin_mm": gap - required,
                "passes_tolerance": gap + policy.geometry_tolerance_mm >= required,
            })
        expected_tightest = min(
            [row for row in [expected_source, expected_prior] if row is not None] + trace_limit_rows,
            key=lambda row: (row["margin_mm"], row["source_id"]),
        ) if (expected_source or expected_prior or trace_limit_rows) else None
        actual_tightest = recorded.get("tightest_recorded_constraint")
        if (expected_tightest is None) != (actual_tightest is None):
            raise ValueError(f"T02_TIGHTEST_LIMIT_PRESENCE_MISMATCH:{sid}")
        if expected_tightest is not None:
            if (actual_tightest.get("source_id") != expected_tightest["source_id"]
                    or actual_tightest.get("measured_gap_mm") != expected_tightest["measured_gap_mm"]
                    or actual_tightest.get("required_gap_mm") != expected_tightest["required_gap_mm"]
                    or actual_tightest.get("source_geometry_sha256") != expected_tightest.get("source_geometry_sha256")
                    or actual_tightest.get("margin_mm") != expected_tightest["margin_mm"]
                    or actual_tightest.get("passes_tolerance") != expected_tightest["passes_tolerance"]):
                raise ValueError(f"T02_TIGHTEST_LIMIT_MISMATCH:{sid}")
        limit_record_count += 1
        if decision.get("decision") == "GROW":
            if decision.get("input_scene_revision") != len(earlier_grown_ids):
                raise ValueError(f"T02_SCENE_REVISION_ORDER_MISMATCH:{sid}")
            earlier_grown_ids.append(sid)

    reconstructed_additions = unary_union(expected_additions)
    addition_diff = additions.symmetric_difference(reconstructed_additions).area
    if addition_diff > AREA_TOL:
        raise ValueError("T02_ADDITIONS_DO_NOT_MATCH_TARGET_CANDIDATES")
    if abs(additions.area - float(result["added_area_mm2"])) > AREA_TOL:
        raise ValueError("T02_ADDED_AREA_REPORT_MISMATCH")
    unique_scene_delta = additions.difference(t01_scene).area
    if abs((combined.area - t01_scene.area) - unique_scene_delta) > AREA_TOL:
        raise ValueError("T02_UNION_AREA_DELTA_MISMATCH")
    if abs(combined.area - float(result["accepted_union_area_mm2"])) > AREA_TOL:
        raise ValueError("T02_COMBINED_AREA_REPORT_MISMATCH")

    # Recheck hard construction clearance from protected non-trace ORG
    # contributions, other target cores/additions, and frozen T01 additions.
    # Trace interactions follow the explicit v8 centerline/deferred-overlap
    # contract and are verified above plus by the source-bound overlap audit.
    t01_additions = t01_scene.difference(unary_union([g.intersection(crop) for sid, g in source_geometries.items()]))
    source_ids = [sid for sid in source_geometries if sid not in trace_copper_by_id]
    source_tree = STRtree([source_geometries[sid] for sid in source_ids])
    growth_ids = list(target_growth)
    growth_tree = STRtree([target_growth[sid] for sid in growth_ids])
    min_protected_gap = None
    for sid, growth in target_growth.items():
        query = growth.buffer(policy.hard_gap_mm + policy.geometry_tolerance_mm)
        blockers = [source_geometries[source_ids[int(i)]]
                    for i in source_tree.query(query) if source_ids[int(i)] != sid]
        blockers.extend(target_growth[growth_ids[int(i)]]
                        for i in growth_tree.query(query) if growth_ids[int(i)] != sid)
        if not t01_additions.is_empty and growth.distance(t01_additions) <= policy.hard_gap_mm + policy.geometry_tolerance_mm:
            blockers.append(t01_additions)
        gap = min((growth.distance(blocker) for blocker in blockers), default=float("inf"))
        min_protected_gap = gap if min_protected_gap is None else min(min_protected_gap, gap)
        if gap + policy.geometry_tolerance_mm < policy.hard_gap_mm:
            raise ValueError(f"T02_COMPOSED_TARGET_GAP_BELOW_HARD_LIMIT:{sid}:{gap}")

    # Re-read and independently classify every frozen T01 circle's saved contour.
    t01_policy_bytes = (ROOT / profile["artifacts"]["policy"]["path"]).read_bytes()
    t01_policy = json.loads(t01_policy_bytes)
    t01_report = json.loads((ROOT / profile["artifacts"]["report"]["path"]).read_bytes())
    inv, rows, _, _, sites = circle_sources.source_scene(
        org_bytes,
        {**t01_policy, "radius_multiplier": t01_policy["max_growth_factor"]},
        expected_unique_sites=t01_policy["expected_unique_circle_sites"],
        expected_occurrences=t01_policy["expected_circle_occurrences"])
    t01_geometries = {}
    for decision in t01_report["decisions"]:
        relative = decision["geometry"]["dynamic"]
        t01_geometries[decision["source_id"]] = from_wkb((scene_path.parent / relative).read_bytes())
    round_audit = assert_t01_round_classes(sites, t01_report["decisions"], t01_geometries)

    audit = {
        "schema": "t02-composition-audit/1",
        "status": "PASS_T01_T02_COMPOSITION_AND_ROUND_SHAPE_AUDIT",
        "audit_scope": "saved geometry and hash-bound local crop only; not an independent geometry kernel",
        "source_sha256": source_hash,
        "accepted_T01_decision_id": owner["decision_id"],
        "accepted_T01_scene_sha256": scene_hash,
        "accepted_T01_prestate_render_matches_scene": True,
        "T01_round_shape_audit": round_audit,
        "T02_target_count": len(target_ids),
        "T02_per_target_limiting_constraint_records_pass": limit_record_count == len(target_ids),
        "T02_per_target_limiting_constraint_record_count": limit_record_count,
        "T02_constraint_witness_categories_reconstructed": [
            "all_ORG_FCu_geometry", "accepted_T01_scene_addition", "all_earlier_accepted_T02_additions",
            "all_reserved_ORG_side_traces", "configured_per_axis_policy_cap", "full_cap_envelope_crop_boundary",
        ],
        "T02_constraint_witness_completeness_pass": limit_record_count == len(target_ids),
        "T02_source_disposition_count": len(run_source_rows),
        "T02_source_disposition_counts": dict(sorted(run_disposition_counts.items())),
        "T02_source_class_counts": dict(sorted(run_class_counts.items())),
        "T02_crop_crossing_nonrectangle_polygon_count": run_class_counts.get("crop_crossing_nonrectangle_polygon", 0),
        "T02_full_source_dispositions_bind_to_inventory": True,
        "T02_growth_decision_count": sum(d.get("decision") == "GROW" for d in decisions_doc["decisions"]),
        "T02_keep_decision_count": sum(d.get("decision") == "KEEP" for d in decisions_doc["decisions"]),
        "T02_keep_decisions_preserve_exact_source": True,
        "T02_target_growth_reconstructs_saved_additions": True,
        "T02_trace_interaction_reservations_pass": True,
        "T02_trace_reservation_count": sum(len(d.get("trace_gap_reservations", [])) for d in decisions_doc["decisions"]),
        "T02_trace_policy_mode": ("centerline_standoff_and_deferred_overlap_recording"
                                   if trace_policy_v8 else "fraction_of_org_surface_gap"),
        "T02_policy_sha256": policy_hash,
        "T02_org_inventory_manifest_sha256": inventory_binding.get("inventory_manifest_sha256"),
        "T01_square_recess_policy": t01_policy.get("square_guided_recess"),
        "T02_final_composition_preserves_T01_area_mm2": lost_t01 <= AREA_TOL,
        "T02_final_composition_equals_T01_union_additions": unexpected_composition <= AREA_TOL,
        "T02_crop_coverage_and_change_scope": True,
        "T02_added_area_report_matches_mm2": float(result["added_area_mm2"]),
        "T02_accepted_union_area_report_matches_mm2": float(result["accepted_union_area_mm2"]),
        "T02_union_area_delta_mm2": combined.area - t01_scene.area,
        "T02_addition_area_overlapping_existing_T01_scene_mm2": additions.area - unique_scene_delta,
        "T02_to_protected_minimum_gap_mm": min_protected_gap,
        "t01_area_loss_mm2": lost_t01,
        "composition_difference_area_mm2": unexpected_composition,
        "addition_reconstruction_difference_area_mm2": addition_diff,
        "area_tolerance_mm2": AREA_TOL,
        "limitations": [
            "Uses the same pinned Shapely geometry library as construction; it is a fresh-process audit, not an independent kernel.",
            "Does not establish EDIT equivalence, electrical/net intent, native export, manufacturing acceptance, or T03 readiness.",
        ],
    }
    audit_dir.mkdir(parents=True, exist_ok=False)
    payload = json.dumps(audit, indent=2, sort_keys=True) + "\n"
    (audit_dir / "t02_composition_audit.json").write_text(payload)
    (audit_dir / "SHA256SUMS.txt").write_text(
        f"{sha_bytes(payload.encode())}  t02_composition_audit.json\n")
    return audit


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, default=DEFAULT_RUN)
    parser.add_argument("--output", type=Path, default=DEFAULT_AUDIT)
    args = parser.parse_args()
    print(json.dumps(audit(args.run.resolve(), args.output.resolve()), indent=2))


if __name__ == "__main__":
    main()
