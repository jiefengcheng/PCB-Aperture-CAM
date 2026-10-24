"""Finalize deterministic T02 receipts, review HTML, and bundle checksums."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = ("feature_dispositions.json", "t02_decisions.json", "t02_result.json",
         "t02_additions.wkb", "t01_accepted_plus_t02.wkb", "accepted_t01_crop.svg",
         "t01_plus_t02.svg", "t02_delta.svg", "t02_policy.json",
         "org_inventory_binding.json")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def finalize(run, repeat, audit):
    result = json.loads((run / "t02_result.json").read_bytes())
    policy = json.loads((run / "t02_policy.json").read_bytes())
    inventory_binding = json.loads((run / "org_inventory_binding.json").read_bytes())
    inventory_report = json.loads((ROOT / inventory_binding["inventory_directory"] / "inventory_report.json").read_bytes())
    audit_doc = json.loads((audit / "t02_composition_audit.json").read_bytes()) if audit else None
    comparisons = {}
    for name in FILES:
        a, b = run / name, repeat / name
        ah, bh = digest(a), digest(b)
        comparisons[name] = {"equal": ah == bh, "run_sha256": ah, "repeat_sha256": bh}
    if not all(x["equal"] for x in comparisons.values()):
        raise ValueError("T02_REPEAT_NOT_BYTE_IDENTICAL")
    det = {"schema":"t02-determinism-receipt/1", "status":"PASS_BYTE_IDENTICAL_REPLAY",
           "first_run":run.name, "repeat_run":repeat.name, "compared_artifacts":comparisons}
    (run / "determinism_receipt.json").write_text(json.dumps(det, indent=2, sort_keys=True)+"\n")
    receipt = {"schema":"t02-execution-receipt/1", "status":result["status"],
               "source_sha256":result["source_sha256"], "crop_bounds_mm":result["crop_bounds_mm"],
               "t01_owner_decision_id":result["accepted_T01_decision_id"],
               "t01_scene_sha256":result["accepted_T01_scene_sha256"],
               "t01_policy_sha256":result["accepted_T01_policy_sha256"],
               "t01_selection_sha256":result["accepted_T01_selection_sha256"],
               "t02_policy_sha256":result["policy_sha256"],
               "t02_org_inventory_manifest_sha256":result["org_inventory_manifest_sha256"],
               "t02_target_count":result["target_set_count"],
               "t02_target_set_sha256":result["target_set_sha256"],
               "t02_decision_counts":result["decision_counts"],
               "t02_added_area_mm2":result["added_area_mm2"],
               "all_per_target_checks_pass":result["all_per_target_checks_pass"],
               "repeat_determinism_receipt_sha256":digest(run/"determinism_receipt.json"),
               "current_neighbor_causal_pairs":len(result["current_neighbor_causal_pairs"]),
               "side_trace_reservation_fraction_of_org_gap":result["side_trace_reservation_fraction_of_org_gap"],
               "side_trace_reservation_count":result["side_trace_reservation_count"],
               "composition_audit_sha256":digest(audit/"t02_composition_audit.json") if audit else None,
               "edit_geometry_used_for_construction":False, "native_export":result["native_export"],
               "electrical_status":result["electrical_status"],
               "manufacturing_status":result["manufacturing_status"]}
    (run / "t02_execution_receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True)+"\n")
    dispositions=json.loads((run/"feature_dispositions.json").read_bytes())["dispositions"]
    withheld=sum("complete 1.5x growth envelope crosses" in d.get("reason","") for d in dispositions)
    audit_link=(f'<p><a href="../{audit.name}/t02_composition_audit.json">Fresh T01→T02 composition audit</a></p>'
                if audit else '<p>Composition audit pending.</p>')
    tolerance_mm = float(policy["geometry_tolerance_mm"])
    nominal_floor_mm = float(policy["side_trace_gap_reservation"]["minimum_retained_gap_mm"])
    measured_gap = (float(audit_doc["T02_to_protected_minimum_gap_mm"])
                    if audit_doc and audit_doc.get("T02_to_protected_minimum_gap_mm") is not None else None)
    if measured_gap is None:
        corridor_note = (f"The nominal trace reservation is max({nominal_floor_mm:.5f} mm, "
                         f"0.5 × the ORG surface gap). Gap comparisons use a {tolerance_mm:.5f} mm "
                         "numerical/curve-approximation tolerance; this is not a strict exact-distance guarantee.")
    else:
        below_nm = max(0.0, (nominal_floor_mm - measured_gap) * 1_000_000)
        corridor_note = (f"Nominal trace reservation: max({nominal_floor_mm:.5f} mm, 0.5 × ORG surface gap). "
                         f"The reported minimum protected gap is {measured_gap:.8f} mm; comparisons use "
                         f"a {tolerance_mm:.5f} mm numerical/curve-approximation tolerance. "
                         f"It is {below_nm:.2f} nm below the nominal floor and passes the implemented "
                         "tolerance-bounded predicate; do not read this as a strict floor guarantee.")
    census = (f"Source census: {inventory_report['source_record_count']} source records enumerated; "
              f"{inventory_report['intersecting_supported_fcu_count']} intersect the crop, including "
              f"{inventory_report['intersecting_supported_fcu_counts_by_kind'].get('segment', 0)} segments and "
              f"{inventory_report['intersecting_supported_fcu_counts_by_kind'].get('arc', 0)} arcs. "
              f"All {inventory_report['source_record_count']} inventory records had geometry available "
              "to this parser; this is not independent parser-completeness verification.")
    growth=result['decision_counts'].get('GROW',0)
    kept=result['decision_counts'].get('KEEP',0)
    html=f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>T02 rectangle and trace-corridor crop review</title><style>body{{font:16px/1.5 system-ui,sans-serif;margin:0;background:#eef3f7;color:#17283a}}main{{max-width:1500px;margin:auto;padding:28px}}header,article{{background:white;border:1px solid #cad6e0;border-radius:16px;padding:22px;margin:0 0 22px}}h1,h2{{margin:0 0 8px}}img{{display:block;width:100%;height:auto;border:1px solid #b8c7d4;border-radius:8px;background:#071522}}.stats{{display:flex;gap:20px;flex-wrap:wrap}}.stats div{{padding:10px 14px;background:#f3f7fa;border-radius:10px}}.small{{font-size:.9rem;color:#405366}}a{{color:#075ea8}}</style><main><header><h1>T02 · Rectangles on the frozen T01 crop</h1><p>Four views of the registered ORG crop. A target is eligible only when its complete 1.5× growth envelope stays inside the reviewed crop; edge-crossing rectangles remain unchanged. The corridor reserves at least half the original ORG surface gap for future trace growth, subject to the declared numeric tolerance.</p><p>{corridor_note}</p><p class="small">{census}</p><div class="stats"><div><b>Eligible rectangles</b><br>{result['target_set_count']}</div><div><b>Grown</b><br>{growth}</div><div><b>Kept unchanged</b><br>{kept}</div><div><b>Crop-edge shapes withheld</b><br>{withheld}</div><div><b>Added copper</b><br>{result['added_area_mm2']:.6f} mm²</div><div><b>Trace reservations</b><br>{result['side_trace_reservation_count']}</div><div><b>Neighbor responses</b><br>{len(result['current_neighbor_causal_pairs'])} counterfactual pairs</div><div><b>Replay</b><br>byte-identical</div></div><p class="small">Geometric experiment only. Trace proximity is geometric and does not infer electrical attachment. Electrical identity, EDIT equivalence, native export and manufacturing approval remain NOT ESTABLISHED.</p><p><a href="t02_result.json">Run summary</a> · <a href="t02_decisions.json">Decisions</a> · <a href="feature_dispositions.json">Source dispositions</a> · <a href="determinism_receipt.json">Replay receipt</a></p>{audit_link}</header><article><h2>ORG · original crop</h2><img src="org_crop.svg" alt="ORG crop"></article><article><h2>T01 · accepted frozen scene</h2><img src="accepted_t01_crop.svg" alt="accepted T01 crop"></article><article><h2>T01 + T02 · resulting crop</h2><img src="t01_plus_t02.svg" alt="combined crop"></article><article><h2>T02 · additions only</h2><img src="t02_delta.svg" alt="T02 additions"></article></main></html>'''
    (run/"index.html").write_text(html)
    entries=[f"{digest(p)}  {p.relative_to(run).as_posix()}" for p in sorted(run.rglob("*")) if p.is_file() and p.name!="SHA256SUMS.txt"]
    (run/"SHA256SUMS.txt").write_text("\n".join(entries)+"\n")


if __name__ == "__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--run",type=Path,default=ROOT/"out/crop_dynamic_tasks/t02_rectangles_crop_20261025_v5")
    ap.add_argument("--repeat",type=Path,default=ROOT/"out/crop_dynamic_tasks/t02_rectangles_crop_20261025_v6")
    ap.add_argument("--audit",type=Path,default=None)
    a=ap.parse_args()
    finalize(a.run.resolve(),a.repeat.resolve(),a.audit.resolve() if a.audit else None)
    print("PASS_FINALIZED_T02_BUNDLE")
