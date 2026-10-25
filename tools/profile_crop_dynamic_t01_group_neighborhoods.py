#!/usr/bin/env python3
"""Profile existing ORG physical components and circle proposals, read-only."""
from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

from shapely import from_wkb
from shapely.geometry import box
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.crop_dynamic_t01_r1 import run  # noqa: E402
from src.native_inventory import inventory  # noqa: E402
from tools import run_crop_dynamic_t01_r1_spacing as base  # noqa: E402


OUTPUT = ROOT / "out/crop_dynamic_tasks/t01_proportional_cap_diagnostic_20261024"
MAIN = ROOT / "out/crop_dynamic_tasks/t01_r1_spacing_driven_20261024"
EPS_AREA_MM2 = 1e-10


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    source = (ROOT / base.ORG_REL).read_bytes()
    source_sha = sha(source)
    if source_sha != base.EXPECTED_ORG_SHA:
        raise SystemExit("ORG_SOURCE_HASH_MISMATCH")
    policy = json.loads((MAIN / "frozen_policy.json").read_text())
    if policy["source_sha256"] != source_sha:
        raise SystemExit("T01_POLICY_SOURCE_BINDING_MISMATCH")
    calibration = {float(key): float(value)
                   for key, value in policy["calibrated_radius_limits_mm"].items()}
    result = run(source, calibrated_radius_limits=calibration,
                 order_policy="source_yx")
    inv = inventory(source)
    rows = {row["id"]: row for row in inv["objects"]}

    components = {}
    for component_id, priority_source_id in result["priority_sites_by_component"].items():
        decision = next(row for row in result["decisions"]
                        if row["source_id"] == priority_source_id)
        member_ids = decision["component_source_member_ids"]
        members = [rows[source_id] for source_id in member_ids]
        geometry_members = [from_wkb(inv["payloads"][row["geometry_sha256"]])
                            for row in members if row.get("geometry_sha256")]
        components[component_id] = {
            "member_ids": member_ids,
            "member_count": len(member_ids),
            "kinds": dict(sorted(Counter(row["kind"] for row in members).items())),
            "geometry": unary_union(geometry_members),
            "target_circle_sites": sum(
                row["physical_component_id"] == component_id
                for row in result["decisions"]),
        }

    component_pairs = []
    component_ids = sorted(components)
    for index, left_id in enumerate(component_ids):
        left = components[left_id]["geometry"]
        for right_id in component_ids[index + 1:]:
            right = components[right_id]["geometry"]
            component_pairs.append({
                "component_a": left_id,
                "component_b": right_id,
                "copper_gap_mm": left.distance(right),
            })
    component_pairs.sort(key=lambda row: (row["copper_gap_mm"],
                                          row["component_a"], row["component_b"]))

    core_by_id = {}
    for decision in result["decisions"]:
        row = rows[decision["source_id"]]
        core_by_id[decision["source_id"]] = from_wkb(
            inv["payloads"][row["geometry_sha256"]])
    static = {row["source_id"]: from_wkb(bytes.fromhex(row["candidate_wkb"]))
              for row in result["static_baseline"]["decisions"]}
    additions = {source_id: candidate.difference(core_by_id[source_id])
                 for source_id, candidate in static.items()}
    nonempty = {source_id: geometry for source_id, geometry in additions.items()
                if not geometry.is_empty and geometry.area > EPS_AREA_MM2}
    proposal_pairs = []
    proposal_ids = sorted(nonempty)
    for index, left_id in enumerate(proposal_ids):
        left = nonempty[left_id]
        for right_id in proposal_ids[index + 1:]:
            right = nonempty[right_id]
            proposal_pairs.append({
                "site_a": left_id,
                "site_b": right_id,
                "added_patch_gap_mm": left.distance(right),
                "overlap_area_mm2": left.intersection(right).area,
            })
    proposal_pairs.sort(key=lambda row: (row["added_patch_gap_mm"],
                                         row["site_a"], row["site_b"]))

    kind_counts = Counter(row["kind"] for row in inv["objects"])
    fcu_kind_counts = Counter(row["kind"] for row in inv["objects"]
                              if "F.Cu" in row["layers"])
    source_text = source.decode("utf-8")
    native_pad_syntax_count = len(re.findall(r"\(\s*pad(?:\s|\))", source_text))
    native_footprint_syntax_count = len(re.findall(
        r"\(\s*footprint(?:\s|\))", source_text))

    report = {
        "schema": "crop-dynamic-t01-org-group-neighborhood-profile/1",
        "status": "PASS_WITH_SCOPE_LIMITS",
        "source_path": str(base.ORG_REL),
        "source_sha256": source_sha,
        "inventory_version": inv["version"],
        "target_components": {
            "component_count": len(components),
            "target_circle_site_count": len(result["decisions"]),
            "target_circle_site_distribution_per_component": dict(sorted(
                Counter(row["target_circle_sites"] for row in components.values()).items())),
            "component_member_kind_counts": dict(sorted(
                Counter(kind for component in components.values()
                        for kind, count in component["kinds"].items()
                        for _ in range(count)).items())),
            "physical_component_pair_count": len(component_pairs),
            "nearest_component_pairs": component_pairs[:10],
        },
        "source_semantics": {
            "inventory_kind_counts_all_layers": dict(sorted(kind_counts.items())),
            "inventory_kind_counts_fcu": dict(sorted(fcu_kind_counts.items())),
            "native_pad_syntax_count": native_pad_syntax_count,
            "native_footprint_syntax_count": native_footprint_syntax_count,
            "interpretation": "The source provides geometric graphics/tracks for these groups; the parsed ORG does not provide native pad or footprint records to anchor semantic terminal/pad identities.",
        },
        "independent_circle_proposal_pairs": {
            "all_target_site_pairs": len(result["decisions"]) * (len(result["decisions"]) - 1) // 2,
            "nonempty_proposal_sites": len(nonempty),
            "nonempty_proposal_pair_count": len(proposal_pairs),
            "overlapping_added_patch_pair_count": sum(
                row["overlap_area_mm2"] > EPS_AREA_MM2 for row in proposal_pairs),
            "closest_added_patch_pairs": proposal_pairs[:10],
        },
        "limitations": [
            "Physical components are transitive same-layer geometry connectivity, not KiCad net identities, terminal groups or CAM intent.",
            "A connected component may span far beyond one terminal-to-pad local group; its full geometry is shown only as source context.",
            "No candidate geometry or source file was modified by this profile.",
            "Component and proposal distances use the same inventory parser and Shapely kernel as the construction experiment.",
        ],
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    path = OUTPUT / "org_group_neighborhood_profile.json"
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    files = sorted(p for p in OUTPUT.rglob("*") if p.is_file()
                   and p.name != "SHA256SUMS")
    (OUTPUT / "SHA256SUMS").write_text("".join(
        f"{sha(file.read_bytes())}  {file.relative_to(OUTPUT).as_posix()}\n"
        for file in files))
    print(json.dumps({
        "status": report["status"],
        "target_components": report["target_components"]["component_count"],
        "nearest_component_gap_mm": component_pairs[0]["copper_gap_mm"],
        "native_pad_syntax_count": native_pad_syntax_count,
        "native_footprint_syntax_count": native_footprint_syntax_count,
        "circle_proposal_pairs": len(proposal_pairs),
        "proposal_overlaps": report["independent_circle_proposal_pairs"]["overlapping_added_patch_pair_count"],
        "closest_proposal_gap_mm": proposal_pairs[0]["added_patch_gap_mm"],
        "evidence": str(path.relative_to(ROOT)),
    }, indent=2))


if __name__ == "__main__":
    main()
