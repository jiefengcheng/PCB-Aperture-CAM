#!/usr/bin/env python3
"""Run/reuse G22 contract and fit, export/evaluate candidates, and publish Slice D."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.ingestion_files import sha
from src.ingestion_registry import publish
from src.ingestion_verification import verify_publication
from tools.build_g22_experiment_contract import build as build_contract
from tools.run_g22_fit import run as run_fit
from tools.run_g22_slice_c import main as export_and_evaluate
from tools.build_g22_slice_d import AUDIT, BUILD_RECEIPT, CONTRACT, FIT, RECEIPT, OUTPUT, main as build_visual

WORKBENCH = ROOT / "out/ingestion/workbench"
FIT_SHA256 = "e8a1d1dcaeb29e6ef0ba411cfcd668b227573b6d5b1414d3ddd88b996137fe48"
CONTRACT_SHA256 = "a0622519d0ef8c9b2d01fe55d6659916ebfcf034292a3fa3913952e2c39dcfbd"
DATASET_ID = "client:szu-comm:3020301113b:intake-20261021:v1"


def main() -> int:
    # A and B builders are deterministic and immutable: they reuse an existing
    # byte-identical contract/candidate run, or create it if absent.
    _contract, contract_path = build_contract()
    if contract_path != CONTRACT or sha(contract_path) != CONTRACT_SHA256:
        raise ValueError("G22_SLICE_A_CONTRACT_DRIFT")
    fit = run_fit()
    if not FIT.is_file() or sha(FIT) != FIT_SHA256 or fit.get("status") != "BEST_WITHIN_DECLARED_SEARCH_SPACE":
        raise ValueError("G22_SLICE_B_FIT_NOT_REPRODUCED")
    if not AUDIT.is_file():
        raise FileNotFoundError("SLICE_C_SUMMARY_AUDIT_RECEIPT_ABSENT")

    # C always writes a new, timestamped, immutable export/evaluation run.
    c_root = ROOT / "out/g22_family_reconstruction/slice_c"
    prior_runs = {p.resolve() for p in c_root.glob("run_*") if p.is_dir()}
    if export_and_evaluate() != 0:
        raise ValueError("G22_SLICE_C_EXPORT_OR_EVALUATION_FAILED")
    new_runs = [p for p in c_root.glob("run_*") if p.is_dir() and p.resolve() not in prior_runs]
    if len(new_runs) != 1:
        raise ValueError(f"G22_SLICE_C_FRESH_RUN_CARDINALITY:{len(new_runs)}")
    receipt_path = new_runs[0] / "run_receipt.json"
    receipt_sha = sha(receipt_path)
    receipt = json.loads(receipt_path.read_text())
    if receipt.get("aggregate_export_status") != "EXPORTS_AND_GERBER_REREAD_COMPLETED":
        raise ValueError("G22_SLICE_C_RECEIPT_NOT_COMPLETE")

    build_visual(receipt_path=receipt_path, expected_receipt_sha256=receipt_sha)
    payload_sha = sha(OUTPUT)
    audit_sha = sha(AUDIT)
    # Reuse the explicit local registration recipe captured with Slice D.
    # An older publication may correctly fail the newer verifier after this
    # code adds receipt requirements, so do not load it through a verifier as
    # the source recipe. Publication still rechecks every registry binding.
    registry_path = OUTPUT.parent / "registry.json"
    if not registry_path.is_file():
        raise FileNotFoundError("G22_SLICE_D_REGISTRATION_RECIPE_ABSENT")
    config = json.loads(registry_path.read_text())
    if DATASET_ID not in config.get("org_family_maps", {}):
        raise ValueError("REGISTERED_G22_ORG_FAMILY_MAP_ABSENT")
    config["g22_reconstruction"] = {
        "dataset_id": DATASET_ID,
        "slice_c_receipt_sha256": receipt_sha,
        "payload": {"path": str(OUTPUT.relative_to(ROOT)), "sha256": payload_sha},
        "slice_c_receipt": {"path": str(receipt_path.relative_to(ROOT)), "sha256": receipt_sha},
        "slice_b_report": {"path": str(FIT.relative_to(ROOT)), "sha256": sha(FIT)},
        "experiment_contract": {"path": str(CONTRACT.relative_to(ROOT)), "sha256": sha(CONTRACT)},
        "chatgpt_audit_receipt": {"path": str(AUDIT.relative_to(ROOT)), "sha256": audit_sha},
        "slice_d_build_receipt": {"path": str(BUILD_RECEIPT.relative_to(ROOT)), "sha256": sha(BUILD_RECEIPT)},
    }
    registry_path.write_text(json.dumps(config, indent=2, sort_keys=True) + "\n")
    revision = publish(ROOT, config, WORKBENCH)
    verification = verify_publication(revision)
    if verification.get("status") != "PASS":
        raise ValueError("PUBLISHED_G22_WORKBENCH_VERIFICATION_FAILED")
    print(json.dumps({"status": "PASS", "scope": "reused Slice A/B when byte-identical; generated ORG candidates, exported and evaluated fresh in Slice C; rebuilt Slice D and verified read-only publication",
                      "slice_c_run": receipt.get("run_id"), "slice_c_receipt_sha256": receipt_sha,
                      "slice_b_report_sha256": sha(FIT),
                      "contract_sha256": sha(CONTRACT), "visual_payload_sha256": payload_sha,
                      "summary_audit_receipt_sha256": audit_sha,
                      "workbench_revision": str(revision.relative_to(ROOT)),
                      "outputs_verified": verification.get("outputs_verified")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
