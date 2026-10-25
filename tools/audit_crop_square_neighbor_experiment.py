#!/usr/bin/env python3
"""Local full-inventory verification, without invoking the editing constructor."""
import hashlib
import argparse
import json
import math
import re
import sys
from pathlib import Path

from shapely import from_wkb, to_wkb

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.native_inventory import inventory

OUT = ROOT / "out/crop_dynamic_tasks/square_neighbor_mechanism_20261024"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def gh(shape):
    return hashlib.sha256(to_wkb(shape, byte_order=1)).hexdigest()


def bound_source_path(relative_path, expected_sha256):
    """Verify historical execution against its hash-bound code snapshot."""
    for candidate in (ROOT/relative_path, OUT/"review_source"/relative_path):
        if candidate.is_file() and sha(candidate) == expected_sha256:
            return candidate
    raise AssertionError("BOUND_IMPLEMENTATION_UNAVAILABLE:" + relative_path)


def main(audit_output=None, bundle=None):
    global OUT
    if bundle is not None:
        selected = Path(bundle).resolve()
        if not selected.is_relative_to(ROOT/"out"):
            raise ValueError("AUDIT_BUNDLE_MUST_BE_UNDER_PROJECT_OUT")
        OUT = selected
    report = json.loads((OUT/"report.json").read_bytes())
    policy = json.loads((OUT/"policy.json").read_bytes())
    bindings = json.loads((OUT/"obstacle_bindings.json").read_bytes())
    assert sha(OUT/"policy.json") == report["policy_sha256"]
    assert sha(OUT/"selection.json") == report["selection_sha256"]
    assert sha(OUT/"obstacle_bindings.json") == report["obstacle_bindings_sha256"]
    source_bindings = {
        "implementation": str(bound_source_path("src/crop_square_neighbor_experiment.py", report["implementation_sha256"]).relative_to(ROOT)),
        "runner": str(bound_source_path(
            "tools/run_crop_square_rotated_priority.py" if report["schema"] == "square-rot45-round-priority-result/1"
            else "tools/run_crop_square_neighbor_experiment.py", report["runner_sha256"]).relative_to(ROOT)),
    }
    source_path = ROOT/policy["source"]
    assert sha(source_path) == report["source_sha256"] == policy["source_sha256"]
    source = source_path.read_bytes()
    inv = inventory(source)
    rows = [row for row in inv["objects"] if "F.Cu" in row["layers"]]
    assert len(rows) == 17849 and all(row["geometry_sha256"] for row in rows)
    shapes = {row["id"]: from_wkb(inv["payloads"][row["geometry_sha256"]]) for row in rows}
    saved = {}
    for name, expected in report["geometry_sha256"].items():
        path = OUT/(name+".wkb")
        assert sha(path) == expected
        saved[name] = from_wkb(path.read_bytes())
    for key in ("a", "b"):
        assert shapes[report[key]["source_id"]].equals_exact(saved[key+"_core"], 0)
    experiments = [
        ("a_source_scene", "a", "a_accepted", None),
        ("b_live_scene", "b", "b_accepted", "a"),
        ("b_source_scene", "b", "b_without_a_addition", None),
        ("b_source_scene", "b", "b_without_a_addition_and_square", None),
        ("b_live_scene", "b", "b_without_square", "a"),
        ("a_assembled_scene", "a", "a_accepted", "b"),
    ]
    if report["schema"] == "square-rot45-round-priority-result/1":
        experiments.append(("b_live_scene", "b", "b_zero_degrees", "a"))
    cases = []
    ports = []
    for binding_key, target_key, candidate_key, replaced_key in experiments:
        site = report[target_key]
        core = saved[target_key+"_core"]
        envelope = saved[target_key+"_envelope"]
        candidate = saved[candidate_key]
        addition = candidate.difference(core)
        assert candidate.is_valid and core.difference(candidate).area <= 1e-10
        assert candidate.difference(envelope).area <= 1e-10
        parts = [addition] if addition.geom_type == "Polygon" else list(addition.geoms)
        assert all(part.distance(core) <= 1e-9 for part in parts)
        bound_by_id = {row["source_id"]: row for row in bindings[binding_key]}
        influence_count = 0
        minimum = float("inf")
        port_count = 0
        for row in rows:  # Deliberately full scan; no STRtree or runner lookup.
            source_id = row["id"]
            if source_id in site["aliases"]:
                continue
            geometry = shapes[source_id]
            if replaced_key and source_id in report[replaced_key]["aliases"]:
                geometry = saved[replaced_key+"_accepted"]
                source_id = report[replaced_key]["source_id"]
            elif target_key == "b" and source_id in report["a"]["aliases"]:
                source_id = report["a"]["source_id"]
            construction_exclusion = geometry.buffer(.025, quad_segs=128)
            if not construction_exclusion.intersects(envelope):
                continue
            influence_count += 1
            assert source_id in bound_by_id, "MISSED_APPLICABLE_OBSTACLE:"+source_id
            bound = bound_by_id[source_id]
            assert gh(geometry) == bound["geometry_sha256"]
            port = None
            if row["kind"] in ("segment", "arc") and geometry.intersects(core.buffer(1e-7, quad_segs=128)):
                raw = source[slice(*row["source_span"])].decode()
                width = float(re.search(r"\(\s*width\s+([0-9.]+)\s*\)", raw).group(1))
                port = geometry.buffer(max(.005, width/2+.005), quad_segs=128).intersection(
                    core.buffer(site["enlarged_radius"]-site["radius"], quad_segs=128))
                assert bound["port_zone_wkb"] is not None
                assert port.equals_exact(from_wkb(bytes.fromhex(bound["port_zone_wkb"])), 0)
                inherited_contact = core.intersection(geometry)
                assert inherited_contact.area > 1e-10
                assert inherited_contact.difference(candidate).area <= 1e-10
                new_contact_outside_port = addition.intersection(geometry).difference(port).area
                assert new_contact_outside_port <= 1e-10
                ports.append({"case": candidate_key, "scene": binding_key,
                              "target_source_id": site["source_id"],
                              "trace_source_id": row["id"], "source_width_mm": width,
                              "port_geometry_sha256": gh(port),
                              "inherited_core_trace_contact_area_mm2": inherited_contact.area,
                              "inherited_contact_lost_mm2": inherited_contact.difference(candidate).area,
                              "new_copper_trace_overlap_inside_port_mm2": addition.intersection(geometry).intersection(port).area,
                              "new_copper_trace_overlap_outside_port_mm2": new_contact_outside_port,
                              "exemption_scope": "Novel land copper may join only this source-existing attached trace inside the frozen bounded source-derived port; all other obstacles remain checked."})
                port_count += 1
            else:
                assert bound["port_zone_wkb"] is None
                minimum = min(minimum, addition.distance(geometry))
            hard_exclusion = geometry.buffer(.020, quad_segs=128)
            if port is not None:
                hard_exclusion = hard_exclusion.difference(port)
            assert addition.intersection(hard_exclusion).area <= 1e-10, "NOVEL_COPPER_HARD_GAP_VIOLATION:"+source_id
        cases.append({"case": candidate_key, "scene": binding_key,
                      "full_source_records_scanned": len(rows),
                      "actual_influence_records_checked": influence_count,
                      "source_attachment_ports_checked": port_count,
                      "minimum_unexempted_addition_gap_mm": minimum})
    ca = saved["b_accepted"].symmetric_difference(saved["b_without_a_addition"]).area
    cs = saved["b_accepted"].symmetric_difference(saved["b_without_square"]).area
    assert ca > 1e-8 and cs > 1e-8
    assert abs(ca-report["check_a_symmetric_difference_mm2"]) < 1e-12
    assert abs(cs-report["check_b_symmetric_difference_mm2"]) < 1e-12
    baseline_square_effect = saved["b_without_a_addition"].symmetric_difference(
        saved["b_without_a_addition_and_square"]).area
    assert baseline_square_effect <= 1e-10
    assert baseline_square_effect == report["four_condition_control"]["square_effect_without_a_addition_mm2"]
    center = report["b"]["center"]
    radius = report["b"]["enlarged_radius"]
    assert all(abs(math.dist(center, vertex)-radius) < 1e-12
               for vertex in list(saved["b_square"].exterior.coords)[:4])
    rotation_checks = {}
    if report["schema"] == "square-rot45-round-priority-result/1":
        round_radius = report["round_priority"]["radius_mm"]
        assert saved["a_accepted"].equals_exact(saved["a_envelope"], 0)
        round_error = max(abs(math.dist(report["a"]["center"], point)-round_radius)
                          for point in saved["a_accepted"].exterior.coords)
        assert round_error <= 0.00002
        assert report["a"]["radius"] <= round_radius <= report["a"]["enlarged_radius"]
        theta = math.radians(policy["orientation_degrees"])
        for key, square_radius in (("a",round_radius),("b",report["b"]["enlarged_radius"])):
            h = square_radius/math.sqrt(2)
            cx,cy = report[key]["center"]
            expected = [(cx+x*math.cos(theta)-y*math.sin(theta),
                         cy+x*math.sin(theta)+y*math.cos(theta))
                        for x,y in ((-h,-h),(h,-h),(h,h),(-h,h))]
            vertices = list(saved[key+"_square"].exterior.coords)[:4]
            assert all(math.dist(actual,wanted)<=1e-12 for actual,wanted in zip(vertices,expected))
        zero_delta = saved["b_accepted"].symmetric_difference(saved["b_zero_degrees"]).area
        assert abs(zero_delta-report["rotation_comparison"]["changed_area_mm2"]) <= 1e-12
        rotation_checks = {"priority_roundness_error_mm":round_error,
                           "both_square_angles_match_declared_policy":True,
                           "rotation_changed_area_mm2":zero_delta}
    result = {"status": "PASS_SCOPED_LOCAL_FULL_INVENTORY_AUDIT",
              "independence": "Same-author local verifier; no constructor call or spatial-index reuse. Not independent external review.",
              "report_sha256": sha(OUT/"report.json"), "auditor_sha256": sha(Path(__file__)),
              "source_sha256": sha(source_path), "cases": cases,
              "verified_execution_source_paths": source_bindings,
              "check_a_recomputed_mm2": ca, "check_b_recomputed_mm2": cs,
              "square_effect_without_earlier_addition_mm2": baseline_square_effect,
              "rotation_and_round_checks": rotation_checks,
              "ports": ports}
    destination = Path(audit_output) if audit_output is not None else OUT/"local_full_inventory_audit.json"
    if not destination.resolve().is_relative_to(ROOT/"out"):
        raise ValueError("AUDIT_OUTPUT_MUST_BE_UNDER_PROJECT_OUT")
    destination.write_text(json.dumps(result, indent=2, sort_keys=True)+"\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Write a new audit under out/, preserving the frozen review bundle.")
    parser.add_argument("--bundle", type=Path, help="Select a saved experiment directory under out/.")
    args = parser.parse_args()
    main(args.output, args.bundle)
