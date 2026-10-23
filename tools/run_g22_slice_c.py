#!/usr/bin/env python3
"""Export frozen G22 candidates and independently reread the KiCad Gerbers.

This is a scoped experimental fidelity audit. It cannot establish electrical,
manufacturing, or complete-family reconstruction acceptance.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import gc
import importlib.metadata
import json
import shutil
import subprocess
import sys
from pathlib import Path

from shapely import from_wkb
from shapely import affinity
from shapely.geometry import box
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from gerbonara.rs274x import GerberFile
from gerbonara.utils import MM
from src.gerber_image import CompletionParser, object_geometry, ordered
from src.g22_reconstruction import generate_org_candidate
from src.native_inventory import inventory

CLI = Path("/Users/geoffcheng/Projects/client/misc_repo/KiCAD_PCB_CAM/build/release/kicad/KiCad.app/Contents/MacOS/kicad-cli")
PINNED_RECEIPT = ROOT / "out/native_exports/20261014T140617_287308Z/run_receipt.json"
DATA = ROOT / "dataset/szu-comm_3020301113B_intake_ready_20261021_v1/raw"
FIT = ROOT / "out/g22_family_reconstruction/slice_b/run-d135c1387f58e549/fit_report.json"
CONTRACT = ROOT / "out/g22_family_reconstruction/slice_a/experiment_contract_a0622519d0ef8c9b.json"
LAYERS = ("F.Cu", "F.Mask", "F.Paste", "Edge.Cuts")


def gerber_roi_for_native(roi, same_coordinates: str):
    return box(roi.bounds[0], -roi.bounds[3], roi.bounds[2], -roi.bounds[1]) if same_coordinates == "Original" else roi


def scalar_file_attribute(value):
    return value[0] if isinstance(value, (list, tuple)) else value


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def normalized_plot_sha(path: Path) -> str:
    import re
    raw = path.read_bytes()
    raw = re.sub(rb"(?m)^%TF\.CreationDate,[^*]*\*%\r?\n|^G04 Created by KiCad[^\r\n]*\r?\n", b"", raw)
    return sha_bytes(raw)


def append_gerber_rectangle_fault(raw: bytes, x: float = 1000.0, y: float = 1000.0,
                                  width: float = 0.1, height: float = 0.1) -> bytes:
    if raw.count(b"M02*") != 1:
        raise ValueError("GERBER_FAULT_CONTROL_REQUIRES_ONE_EOF")
    x0, x1 = round(x * 1_000_000), round((x + width) * 1_000_000)
    y0, y1 = round(y * 1_000_000), round((y + height) * 1_000_000)
    region = (b"%LPD*%\nG36*\n" + f"X{x0}Y{y0}D02*\nX{x1}Y{y0}D01*\n"
              f"X{x1}Y{y1}D01*\nX{x0}Y{y1}D01*\nX{x0}Y{y0}D01*\nG37*\n".encode())
    return raw.replace(b"M02*", region + b"M02*")


def command(argv: list[str], log: Path, accepted: tuple[int, ...] = (0,)) -> dict:
    p = subprocess.run([str(v) for v in argv], capture_output=True, text=True, timeout=600)
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text("$ " + " ".join(map(str, argv)) + "\n" + p.stdout + "\n" + p.stderr)
    row = {"argv": list(map(str, argv)), "exit_code": p.returncode,
           "stdout": p.stdout, "stderr": p.stderr, "log": str(log.relative_to(ROOT))}
    if p.returncode not in accepted:
        raise RuntimeError(f"COMMAND_FAILED:{p.returncode}:{log}")
    return row


def gerber_for(directory: Path, board_stem: str, layer: str) -> Path:
    suffix = layer.replace(".", "_")
    path = directory / f"{board_stem}-{suffix}.gbr"
    if not path.is_file():
        raise FileNotFoundError(f"EXPECTED_GERBER_ABSENT:{path.name}")
    return path


def parsed_layer_regions(path: Path, windows: list) -> dict:
    """Parse every command but union detailed geometry only in the fixed ROIs."""
    import collections
    text = path.read_text()
    gerber = GerberFile()
    parser = CompletionParser(gerber)
    parser.parse(text, filename=str(path))
    if parser.block_frame is not None or parser.current_region is not None:
        raise ValueError("GERBER_INCOMPLETE_BLOCK_OR_REGION")
    if parser.inventory["MO"] != 1 or parser.inventory["FS"] != 1:
        raise ValueError("GERBER_EXPLICIT_UNIT_AND_FORMAT_REQUIRED")
    if parser.file_settings.number_format not in ((2, 6), (4, 6)):
        raise ValueError("GERBER_FORMAT_OUTSIDE_PROFILE")
    if parser.file_settings.unit != MM or "%MOMM*%" not in text or parser.file_settings.notation != "absolute":
        raise ValueError("GERBER_UNIT_OR_NOTATION_UNSUPPORTED")
    if len(gerber.objects) > 200000:
        raise ValueError("GERBER_OBJECT_RESOURCE_BOUND")
    same_coordinates = scalar_file_attribute(gerber.file_attrs.get(".SameCoordinates", [None]))
    # KiCad's X2 SameCoordinates=Original plot coordinates use the opposite Y
    # sign from the serialized native-board coordinates in this checkout.
    # This axis-only mapping is fixed by the registered/native coordinate
    # contract; no copper-derived translation, rotation, or scale is fitted.
    y_sign = -1 if same_coordinates == "Original" else 1
    regions = []
    for roi in windows:
        gerber_roi = gerber_roi_for_native(roi, same_coordinates)
        items = []
        selected = []
        for obj in gerber.objects:
            bounds = obj.bounding_box()
            if bounds is None or not box(bounds[0][0], bounds[0][1], bounds[1][0], bounds[1][1]).intersects(gerber_roi):
                continue
            geom = object_geometry(obj).intersection(gerber_roi)
            items.append((geom, obj.polarity_dark))
            selected.append(obj)
        image = ordered(items)
        if not image.is_valid:
            raise ValueError("INVALID_COMPOSED_LOCAL_GERBER_IMAGE")
        if y_sign == -1:
            image = affinity.scale(image, xfact=1, yfact=-1, origin=(0, 0))
        regions.append({"geometry": image, "object_count": len(selected),
                        "object_types": dict(collections.Counter(type(obj).__name__ for obj in selected))})
    meta = {"path": str(path.relative_to(ROOT)), "sha256": sha(path),
            "size_bytes": path.stat().st_size, "object_count": len(gerber.objects),
            "file_attributes": gerber.file_attrs, "parser_inventory": dict(parser.inventory),
            "normalized_plot_sha256": normalized_plot_sha(path),
            "registered_axis_mapping": {"same_coordinates": same_coordinates, "native_y_per_gerber_y": y_sign,
                                         "basis": "X2 SameCoordinates plus source-frame contract; no fitted copper transform"}}
    return meta, regions


def native_layer_union(raw: bytes, inv: dict, layer: str, roi=None) -> tuple[object, dict]:
    supported = []
    unsupported = []
    for item in inv["objects"]:
        if layer not in item.get("layers", []):
            continue
        bounds = item.get("bounds_mm")
        if roi is not None and bounds:
            if not box(*bounds).intersects(roi):
                continue
        elif roi is not None and not bounds:
            unsupported.append({"identity": item["id"], "kind": item["kind"],
                                "reason": item.get("unsupported_reason"), "bounds_mm": None})
            continue
        geometry_hash = item.get("geometry_sha256")
        if geometry_hash:
            geom = from_wkb(inv["payloads"][geometry_hash])
            if roi is None or geom.intersects(roi):
                supported.append(geom.intersection(roi) if roi is not None else geom)
        else:
            unsupported.append({"identity": item["id"], "kind": item["kind"],
                                "reason": item.get("unsupported_reason"), "bounds_mm": bounds})
    geom = unary_union(supported) if supported else box(0, 0, 0, 0)
    return geom, {"supported_occurrences": len(supported), "unsupported_occurrences": unsupported,
                  "unsupported_count": len(unsupported), "coverage": "COMPLETE_FOR_WINDOW" if not unsupported else "INCOMPLETE"}


def geometric_measure(expected, observed) -> dict:
    if expected.is_empty or observed.is_empty:
        if expected.is_empty and observed.is_empty:
            return {"status": "EQUAL_EMPTY", "expected_area_mm2": 0.0, "observed_area_mm2": 0.0,
                    "symmetric_difference_area_mm2": 0.0}
        return {"status": "MEASURED", "expected_area_mm2": expected.area,
                "observed_area_mm2": observed.area,
                "symmetric_difference_area_mm2": expected.symmetric_difference(observed).area,
                "boundary_hausdorff_mm": None}
    inter = expected.intersection(observed)
    return {"status": "MEASURED", "expected_area_mm2": expected.area,
            "observed_area_mm2": observed.area, "intersection_area_mm2": inter.area,
            "expected_perimeter_mm": expected.length, "observed_perimeter_mm": observed.length,
            "symmetric_difference_area_mm2": expected.symmetric_difference(observed).area,
            "boundary_hausdorff_mm": expected.boundary.hausdorff_distance(observed.boundary),
            "expected_covered_fraction": inter.area / expected.area if expected.area else None,
            "observed_covered_fraction": inter.area / observed.area if observed.area else None}


def topology_change(org, candidate, roi) -> dict:
    """Compare local plotted-copper contact and fragmentation, never net identity."""
    parts = lambda geom: list(geom.geoms) if hasattr(geom, "geoms") else ([] if geom.is_empty else [geom])
    org_parts, candidate_parts = parts(org), parts(candidate)
    added = candidate.difference(org)
    new_contacts = []
    for added_part in parts(added):
        touched = [i for i, original in enumerate(org_parts) if added_part.distance(original) <= 1e-9]
        if len(touched) > 1:
            new_contacts.append({"added_area_mm2": added_part.area, "original_components_touched": touched})
    possible_splits = []
    for i, original in enumerate(org_parts):
        remaining = [j for j, current in enumerate(candidate_parts)
                     if current.intersection(original).area > 1e-10]
        if len(remaining) > 1:
            possible_splits.append({"original_component": i, "candidate_components": remaining})
    boundary_open = any(g.boundary.intersects(roi.boundary) for g in parts(added) + parts(org.difference(candidate)))
    status = ("FAIL_NEW_GEOMETRIC_CONTACT" if new_contacts else
              "FAIL_POSSIBLE_LOCAL_FRAGMENTATION" if possible_splits else
              "NOT_ESTABLISHED_LOCAL_COMPONENTS_TOUCH_ANALYSIS_BOUNDARY" if boundary_open else
              "PASS_NO_NEW_LOCAL_CONTACT_OR_FRAGMENTATION")
    return {"status": status, "scope": "local plotted copper only; not electrical connectivity",
            "window_bounds_mm": list(roi.bounds), "original_component_count": len(org_parts),
            "candidate_component_count": len(candidate_parts), "added_area_mm2": added.area,
            "removed_area_mm2": org.difference(candidate).area,
            "new_contact_events": new_contacts, "possible_fragmentation_events": possible_splits,
            "analysis_boundary_open": boundary_open}


def fidelity_gate(coverage: dict, measure: dict, geometry_error_mm: float) -> dict:
    if coverage["coverage"] != "COMPLETE_FOR_WINDOW":
        return {"status": "NOT_ESTABLISHED", "reason": "UNSUPPORTED_NATIVE_SOURCE_GEOMETRY_IN_WINDOW"}
    if measure["status"] == "EQUAL_EMPTY":
        return {"status": "PASS", "rule": "Both native and exported geometry empty in this window."}
    if measure.get("expected_perimeter_mm") is None or measure.get("observed_perimeter_mm") is None:
        return {"status": "FAIL", "reason": "ONE_SIDE_EMPTY_DESPITE_COMPLETE_NATIVE_SOURCE_COVERAGE"}
    tol_area = (measure["expected_perimeter_mm"] + measure["observed_perimeter_mm"]) * geometry_error_mm + 2 * 3.141592653589793 * geometry_error_mm ** 2
    passed = (measure["boundary_hausdorff_mm"] <= geometry_error_mm and
              measure["symmetric_difference_area_mm2"] <= tol_area)
    return {"status": "PASS" if passed else "FAIL", "geometry_error_mm": geometry_error_mm,
            "area_error_envelope_mm2": tol_area,
            "rule": "Bounded Hausdorff and perimeter-derived area error on complete source geometry."}


def serializable(report: dict) -> dict:
    # Keep GEOS objects out of the receipt while preserving all measured fields.
    return report


def main() -> int:
    if not CLI.is_file() or not PINNED_RECEIPT.is_file():
        raise RuntimeError("PINNED_KICAD_CLI_OR_RECEIPT_UNAVAILABLE")
    pinned = json.loads(PINNED_RECEIPT.read_text())
    cli_hash = sha(CLI)
    if cli_hash != pinned["cli_sha256"]:
        raise RuntimeError("PINNED_KICAD_BINARY_HASH_MISMATCH")
    fit = json.loads(FIT.read_text())
    contract = json.loads(CONTRACT.read_text())
    if sha(CONTRACT) != fit["inputs"]["contract_sha256"] or sha(FIT) != "e8a1d1dcaeb29e6ef0ba411cfcd668b227573b6d5b1414d3ddd88b996137fe48":
        raise RuntimeError("SLICE_B_EVIDENCE_HASH_MISMATCH")
    org = DATA / "ORG/top.kicad_pcb"
    edit = DATA / "EDIT/top_layer.kicad_pcb"
    if sha(org) != fit["inputs"]["ORG_sha256"] or sha(edit) != fit["inputs"]["EDIT_sha256"]:
        raise RuntimeError("PINNED_NATIVE_SOURCE_DRIFT")
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    run = ROOT / "out/g22_family_reconstruction/slice_c" / f"run_{stamp}"
    run.mkdir(parents=True, exist_ok=False)
    version = command([CLI, "version"], run / "version.log")
    if "10.99.0" not in version["stdout"]:
        raise RuntimeError("PINNED_KICAD_VERSION_MISMATCH")
    cases = {"ORG": org, "EDIT": edit}
    expected_candidate_hashes = {}
    for transfer in fit["transfer"]:
        cases[f"candidate_member_{transfer['member']}"] = ROOT / transfer["candidate_board_path"]
        expected_candidate_hashes[f"candidate_member_{transfer['member']}"] = transfer["candidate_board_sha256"]

    receipt = {"schema": "g22-slice-c-export-readback/1", "run_id": run.name,
               "slice_b_run": fit["run_id"], "slice_b_report_sha256": sha(FIT),
               "contract_sha256": sha(CONTRACT), "cli": str(CLI), "cli_sha256": cli_hash,
               "cli_version": version["stdout"].strip(), "pinned_export_receipt": str(PINNED_RECEIPT.relative_to(ROOT)),
               "package_aggregate_status": contract["sealed_package"]["status"],
               "layers": list(LAYERS), "geometry_kernel": "Gerbonara + Shapely/GEOS existing project parser",
               "tool_versions": {"gerbonara": importlib.metadata.version("gerbonara"),
                                 "shapely": importlib.metadata.version("shapely")},
               "native_export_comparison_geometry_error_mm": contract["geometry_kernel"]["geometry_error_mm"],
               "cases": {}, "source_isolation": {}, "windows": {},
               "drc": {"status": "NOT_RUN", "reason": "Gerber fidelity and bounded geometry checks are the Slice C gate; DRC is supplementary and cannot establish these claims."},
               "external_independent_review": {"Cursor": "NOT_RUN: CHANNEL_UNAVAILABLE"},
               "limitations": ["Experimental geometry fidelity only; no electrical or manufacturing acceptance.",
                               "Complete target reconstruction remains NOT_ESTABLISHED for A/B/C as qualified in Slice A/B.",
                               "Gerber export is an independent KiCad plotting path; reread and native reference both use project-local geometry tooling."]}
    windows = [box(*coords) for coords in contract["windows"]]
    halo_mm = float(contract["safety_halo"]["value_mm"])
    analysis_windows = windows + [roi.buffer(halo_mm, join_style="mitre") for roi in windows]
    case_regions = {}
    native_summaries = {}
    native_regions = {}
    source_operation_ids = {op["source_identity"] for t in fit["transfer"]
                            for op in t["candidate_receipt"]["editable_source_occurrences"]}
    source_operation_bounds = {}
    try:
        for name, source in cases.items():
            source_hash = sha(source)
            if name in expected_candidate_hashes and source_hash != expected_candidate_hashes[name]:
                raise RuntimeError(f"SLICE_B_CANDIDATE_HASH_MISMATCH:{name}")
            if name == "ORG" and source_hash != fit["inputs"]["ORG_sha256"]:
                raise RuntimeError("ORG_CASE_HASH_MISMATCH")
            if name == "EDIT" and source_hash != fit["inputs"]["EDIT_sha256"]:
                raise RuntimeError("EDIT_CASE_HASH_MISMATCH")
            work = run / "boards" / name
            work.mkdir(parents=True)
            board = work / source.name
            shutil.copyfile(source, board)
            if sha(board) != source_hash:
                raise RuntimeError(f"COPY_HASH_MISMATCH:{name}")
            output = run / "gerbers" / name
            output.mkdir(parents=True)
            args = [CLI, "pcb", "export", "gerbers", "--layers", ",".join(LAYERS),
                    "--precision", "6", "--no-protel-ext", "-o", str(output) + "/", board]
            cmd = command(args, run / "logs" / f"{name}_export.log")
            if sha(board) != source_hash:
                raise RuntimeError(f"BOARD_MUTATED_DURING_EXPORT:{name}")
            layer_receipts = {}
            case_regions[name] = {}
            for layer in LAYERS:
                p = gerber_for(output, board.stem, layer)
                meta, regions = parsed_layer_regions(p, analysis_windows)
                case_regions[name][layer] = regions
                layer_receipts[layer] = meta
            receipt["cases"][name] = {"source_path": str(source.relative_to(ROOT)),
                                      "source_sha256": source_hash, "working_copy": str(board.relative_to(ROOT)),
                                      "working_copy_sha256_after_export": sha(board), "export": cmd,
                                      "gerbers": layer_receipts}
            # Build source-native inventory once per board, then discard it before opening the next.
            raw = board.read_bytes()
            inv = inventory(raw)
            coverage_rows = {}
            native_regions[name] = {"F.Cu": []}
            for i, window in enumerate(analysis_windows, 1):
                geom, coverage = native_layer_union(raw, inv, "F.Cu", window)
                native_regions[name]["F.Cu"].append({"geometry": geom, "coverage": coverage})
                coverage_rows[str(i)] = coverage
            fcu_unsupported = [o for o in inv["objects"] if "F.Cu" in o.get("layers", []) and not o.get("geometry_sha256")]
            if name == "ORG":
                rows_by_id = {o["id"]: o for o in inv["objects"]}
                source_operation_bounds = {identity: rows_by_id[identity].get("bounds_mm")
                                           for identity in sorted(source_operation_ids)}
            native_summaries[name] = {"source_objects": inv["source_objects"],
                                      "f_cu_supported_source_geometries": sum("F.Cu" in o.get("layers", []) and bool(o.get("geometry_sha256")) for o in inv["objects"]),
                                      "f_cu_unsupported_occurrences": len(fcu_unsupported),
                                      "unsupported_sample": [{"identity": o["id"], "kind": o["kind"],
                                                               "reason": o.get("unsupported_reason"), "bounds_mm": o.get("bounds_mm")}
                                                              for o in fcu_unsupported[:40]],
                                      "local_window_coverage": coverage_rows,
                                      "coverage": "SOURCE_INVENTORY_SUPPORTED_GEOMETRY_ONLY" if fcu_unsupported else "SOURCE_INVENTORY_COMPLETE"}
            del inv, raw
            gc.collect()

        # Native source inventory versus independent Gerbonara reread, on each frozen ORG-frame window.
        for transfer, window in zip(fit["transfer"], windows):
            member = transfer["member"]
            org_name, cand_name, edit_name = "ORG", f"candidate_member_{member}", "EDIT"
            window_key = str(member)
            cases_in_window = {}
            for name in (org_name, cand_name, edit_name):
                native = native_regions[name]["F.Cu"][member - 1]["geometry"]
                coverage = native_regions[name]["F.Cu"][member - 1]["coverage"]
                plotted = case_regions[name]["F.Cu"][member - 1]["geometry"]
                cases_in_window[name] = {"native": native, "coverage": coverage,
                                         "plotted": plotted,
                                         "native_to_gerber": geometric_measure(native, plotted)}
            topology_roi = analysis_windows[member + 2]
            topology = topology_change(
                case_regions[org_name]["F.Cu"][member + 2]["geometry"],
                case_regions[cand_name]["F.Cu"][member + 2]["geometry"], topology_roi)
            receipt["windows"][window_key] = {"bounds_org_mm": list(window.bounds),
                                              "member_key": transfer["member_key"],
                                              "native_to_gerber": {n: {"coverage": v["coverage"], "measure": v["native_to_gerber"]}
                                                                   for n, v in cases_in_window.items()},
                                              "native_export_fidelity": {n: fidelity_gate(v["coverage"], v["native_to_gerber"],
                                                                                         contract["geometry_kernel"]["geometry_error_mm"])
                                                                          for n, v in cases_in_window.items()},
            "exported_copper_comparison": {
                                                  "candidate_vs_org": geometric_measure(cases_in_window[cand_name]["plotted"],
                                                                                       cases_in_window[org_name]["plotted"]),
                                                  "candidate_vs_edit": geometric_measure(cases_in_window[cand_name]["plotted"],
                                                                                       cases_in_window[edit_name]["plotted"]),
                                                  "unchanged_org_vs_edit": geometric_measure(cases_in_window[org_name]["plotted"],
                                                                                           cases_in_window[edit_name]["plotted"]),
                                                  "local_neighbor_interaction": topology,
                                                  "edit_target_qualification": transfer["target_composition_status"],
                                                  "whole_target_fit": transfer["whole_target_fit_status"],
                                                  "B_alternatives_retained": transfer["edit_candidate_alternatives_retained"] if member == 2 else None,
                                                  "C_unsupported_retained": transfer["target_composition_status"] == "NOT_ESTABLISHED" if member == 3 else None}}

        # Reference-layer exports are compared locally; candidate source construction is F.Cu-only.
        for name in ("candidate_member_1", "candidate_member_2", "candidate_member_3"):
            reference_comparisons = {}
            for layer in ("F.Mask", "F.Paste", "Edge.Cuts"):
                reference_comparisons[layer] = {str(i + 1): geometric_measure(
                    case_regions[name][layer][i]["geometry"], case_regions["ORG"][layer][i]["geometry"])
                    for i in range(len(windows))}
                candidate_file = receipt["cases"][name]["gerbers"][layer]
                org_file = receipt["cases"]["ORG"]["gerbers"][layer]
                reference_comparisons[layer]["whole_layer_normalized_byte_check"] = {
                    "status": "PASS" if candidate_file["normalized_plot_sha256"] == org_file["normalized_plot_sha256"] else "FAIL",
                    "candidate_normalized_sha256": candidate_file["normalized_plot_sha256"],
                    "org_normalized_sha256": org_file["normalized_plot_sha256"],
                    "normalization": "removed only KiCad CreationDate header/comment; all remaining plot bytes compared exactly"}
            receipt["cases"][name]["reference_layer_preservation_vs_org"] = reference_comparisons

        for name in cases:
            receipt["cases"][name]["native_inventory_summary"] = native_summaries[name]

        # Replay each exact source-located constructor from ORG bytes and the
        # frozen Slice B receipt. EDIT is absent from this function's inputs.
        org_raw = org.read_bytes()
        constructor_replay = {}
        for transfer in fit["transfer"]:
            construction = transfer["candidate_receipt"]
            operation_map = {op["source_identity"]: {
                "radius_delta_mm": op["radius_delta_mm"],
                "width_delta_mm": op["width_delta_mm"]}
                for op in construction["editable_source_occurrences"]}
            blends = [(row["center_mm"], row["radius_mm"])
                      for row in construction["inserted_blend_features"]]
            replayed, replay_receipt = generate_org_candidate(
                org_raw, fit["inputs"]["ORG_sha256"], operation_map,
                blend_points=blends, member_key=transfer["member_key"])
            candidate_path = ROOT / transfer["candidate_board_path"]
            exact_bytes = replayed == candidate_path.read_bytes()
            exact_receipt = replay_receipt == construction
            safe_region = analysis_windows[transfer["member"] + 2]
            bounds = {identity: source_operation_bounds.get(identity)
                      for identity in sorted(operation_map)}
            influence_by_identity = {op["source_identity"]: max(abs(op["radius_delta_mm"]),
                                                                  abs(op["width_delta_mm"]) / 2)
                                     for op in construction["editable_source_occurrences"]}
            influenced_bounds = {identity: (list(box(*item_bounds).buffer(influence_by_identity[identity]).bounds)
                                               if item_bounds is not None else None)
                                 for identity, item_bounds in bounds.items()}
            operations_within_halo = all(
                bounds[identity] is not None and
                safe_region.covers(box(*bounds[identity]).buffer(influence_by_identity[identity]))
                for identity in bounds)
            constructor_replay[str(transfer["member"])] = {
                "status": "PASS" if exact_bytes and exact_receipt else "FAIL",
                "replayed_candidate_sha256": sha_bytes(replayed),
                "stored_candidate_sha256": sha(candidate_path),
                "source_role": "ORG", "edit_target_input_to_constructor": False,
                "editable_occurrence_count": len(operation_map),
                "source_object_bounds_mm": bounds,
                "max_operation_influence_mm": influence_by_identity,
                "conservative_influenced_bounds_mm": influenced_bounds,
                "all_source_object_bounds_inside_window_plus_halo": operations_within_halo,
                "receipt_exactly_reproduced": exact_receipt}
            if not exact_bytes or not exact_receipt:
                raise RuntimeError(f"ORG_ONLY_CONSTRUCTOR_REPLAY_MISMATCH:member_{transfer['member']}")

        receipt["source_isolation"] = {
            "ORG_sha256_before_after": fit["inputs"]["ORG_sha256"],
            "EDIT_sha256_before_after": fit["inputs"]["EDIT_sha256"],
            "candidate_hashes_bound_to_slice_b": {str(t["member"]): t["candidate_board_sha256"] for t in fit["transfer"]},
            "candidate_construction_receipts": {str(t["member"]): {
                "source_role": t["candidate_receipt"]["source_role"],
                "source_sha256": t["candidate_receipt"]["source_sha256"],
                "candidate_sha256": t["candidate_receipt"]["candidate_sha256"],
                "edit_target_used_as_operator": t["candidate_receipt"]["edit_target_used_as_operator"],
                "source_occurrence_operations": t["candidate_receipt"]["editable_source_occurrences"],
                "inserted_features": t["candidate_receipt"]["inserted_blend_features"]}
                for t in fit["transfer"]},
            "org_only_constructor_replay": constructor_replay,
            "EDIT_used_as_geometry_operator": False,
            "EDIT_role": "target for A calibration and comparison only; shared parameters are target-informed",
            "noncandidate_board_copies_unchanged_after_export": all(receipt["cases"][k]["source_sha256"] == receipt["cases"][k]["working_copy_sha256_after_export"] for k in ("ORG", "EDIT"))}
        # Deliberate out-of-scope artwork insertion verifies that the independent
        # Gerber reread detects a known added region instead of silently omitting it.
        clean_path = ROOT / receipt["cases"]["candidate_member_1"]["gerbers"]["F.Cu"]["path"]
        fault_path = run / "faults/out_of_scope_extra_copper.gbr"
        fault_path.parent.mkdir(parents=True, exist_ok=True)
        fault_bytes = append_gerber_rectangle_fault(clean_path.read_bytes())
        fault_path.write_bytes(fault_bytes)
        fault_roi_native = box(999.9, -1000.2, 1000.2, -999.9)
        _, clean_fault_region = parsed_layer_regions(clean_path, [fault_roi_native])
        _, inserted_fault_region = parsed_layer_regions(fault_path, [fault_roi_native])
        detected = geometric_measure(clean_fault_region[0]["geometry"], inserted_fault_region[0]["geometry"])
        receipt["fault_controls"] = {"out_of_scope_added_copper": {
            "status": "PASS_DETECTED_AND_REJECTED" if detected.get("symmetric_difference_area_mm2", 0) > 0 else "FAIL_NOT_DETECTED",
            "basis": "deliberately altered copy of actual candidate F.Cu Gerber; original export remains immutable",
            "clean_gerber_sha256": sha(clean_path), "fault_gerber_sha256": sha(fault_path),
            "fault_roi_native_mm": list(fault_roi_native.bounds), "comparison": detected,
            "scope_disposition": "REJECT_OUT_OF_SCOPE_GEOMETRY"}}
        if receipt["fault_controls"]["out_of_scope_added_copper"]["status"] != "PASS_DETECTED_AND_REJECTED":
            raise RuntimeError("GERBER_OUT_OF_SCOPE_FAULT_NOT_DETECTED")
        receipt["aggregate_export_status"] = "EXPORTS_AND_GERBER_REREAD_COMPLETED"
        receipt["research_invariants"] = "MEASURED_WITH_EXPLICIT_COVERAGE; no electrical/manufacturing acceptance"
    except Exception as exc:
        receipt["aggregate_export_status"] = "FAILED_OR_INCOMPLETE"
        receipt["error"] = f"{type(exc).__name__}:{exc}"
        (run / "run_receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
        raise
    report_path = run / "run_receipt.json"
    report_path.write_text(json.dumps(serializable(receipt), indent=2, sort_keys=True) + "\n")
    print(json.dumps({"run": str(run.relative_to(ROOT)), "status": receipt["aggregate_export_status"],
                      "receipt_sha256": sha(report_path), "cases": len(receipt["cases"]),
                      "windows": len(receipt["windows"])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
