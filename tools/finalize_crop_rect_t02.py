"""Finalize deterministic T02 receipts, review HTML, and bundle checksums."""
import argparse
import hashlib
import html
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = ("feature_dispositions.json", "t02_decisions.json", "t02_result.json",
         "t02_additions.wkb", "t01_accepted_plus_t02.wkb", "accepted_t01_crop.svg",
         "t01_plus_t02.svg", "t02_delta.svg", "t02_policy.json",
         "org_inventory_binding.json", "future_trace_work_items.json")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def target_details_html(decisions_doc, max_factor=1.5):
    rows = []
    for decision in decisions_doc.get("decisions", []):
        span = decision.get("source_span", [])
        source = f"{span[0]}–{span[1]}" if len(span) == 2 else decision["source_id"]
        source_id = html.escape(decision["source_id"])
        short_hash = html.escape(decision.get("source_geometry_sha256", "")[:12])
        size = " × ".join(f"{float(value):.6f}" for value in decision["source_size_mm"])
        proposed = " × ".join(f"{float(value):.6f}" for value in decision["accepted_size_mm_in_source_axes"])
        cap = " × ".join(f"{float(value):.6f}" for value in decision["maximum_size_mm"])
        angle = f"{float(decision['orientation_radians']) * 180.0 / 3.141592653589793:.3f}°"
        constraints = decision.get("limiting_constraints", {})
        cap_witness = constraints.get("policy_cap", {})
        crop_witness = constraints.get("crop_boundary", {})
        cap_axes = ", ".join("XY"[int(axis)] for axis in cap_witness.get("active_axes", [])) or "not binding"
        crop_margin = (f"{float(crop_witness['cap_to_crop_boundary_mm']):.6f} mm" if crop_witness
                       else "not recorded")
        tightest = constraints.get("tightest_recorded_constraint")
        if tightest:
            limit_span = tightest.get("source_span", [])
            limit_id = html.escape(tightest.get("source_id", ""))
            limit_label = (f"{html.escape(str(tightest.get('constraint_type', '')))} · "
                           f"{html.escape(str(tightest.get('source_kind') or 'prior addition'))} "
                           f"{limit_span[0]}–{limit_span[1]}" if len(limit_span) == 2 else
                           f"{html.escape(str(tightest.get('constraint_type', '')))} · {limit_id}")
            limit_gap = (f"{float(tightest['measured_gap_mm']):.8f} / "
                         f"{float(tightest['required_gap_mm']):.8f} mm required")
            limit_state = "PASS tolerance" if tightest.get("passes_tolerance") else "FAIL"
            limit_hash = html.escape(str(tightest.get("source_geometry_sha256") or "")[:12])
            limit = (f"<span title=\"{limit_id}\">{limit_label}</span><br><small>{limit_id} "
                     f"{limit_hash}</small><br>{limit_gap}<br>{limit_state}")
        else:
            limit = "No nearby limiting geometry recorded"
        prior = constraints.get("nearest_prior_t02_addition")
        prior_cell = "None in prior scene" if not prior else (
            f"<span title=\"{html.escape(prior['source_id'])}\">"
            f"{html.escape(str(prior.get('source_kind') or 'T02'))} "
            f"{prior.get('source_span', ['?', '?'])[0]}–{prior.get('source_span', ['?', '?'])[1]}</span>"
            f"<br>{float(prior['measured_gap_mm']):.8f} mm")
        checks = decision.get("verification", {})
        checks_pass = bool(checks) and all(checks.values())
        check_cell = "PASS" if checks_pass else "CHECK FAILED"
        rows.append(
            f"<tr><td title=\"{source_id}\">{source}<br><small>{short_hash}</small></td>"
            f"<td>{size} mm</td><td>{proposed} mm</td><td>{cap} mm<br><small>{cap_axes} axis</small></td>"
            f"<td>{angle}</td><td>{crop_margin}</td>"
            f"<td>{limit}</td><td>{prior_cell}</td>"
            f"<td>{int(decision.get('input_scene_revision', 0))} → {int(decision.get('output_scene_revision', 0))}</td>"
            f"<td>{html.escape(str(decision.get('decision', 'UNKNOWN')))} · {check_cell}</td></tr>"
        )
    return ("<details><summary>Per-target dimensions, limits, scene revision and checks</summary>"
            "<div class=\"tablewrap\"><table><thead><tr><th>ORG feature (source span / geometry hash)</th>"
            f"<th>ORG size</th><th>Accepted proposal</th><th>{max_factor:.2f}× cap / binding axis</th><th>Orientation</th>"
            "<th>Cap-to-crop boundary</th>"
            "<th>Tightest recorded limit (measured / required)</th><th>Nearest earlier T02 addition</th>"
            "<th>Scene revision</th><th>Decision / checks</th></tr></thead><tbody>"
            + "".join(rows) + "</tbody></table></div></details>")


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
               "side_by_side_centerline_gap_mm":result["side_by_side_centerline_gap_mm"],
               "side_trace_reservation_count":result["side_trace_reservation_count"],
               "future_trace_overlap_count":result["future_trace_overlap_count"],
               "future_trace_overlap_pairwise_area_total_mm2":result["future_trace_overlap_pairwise_area_total_mm2"],
               "future_trace_overlap_unique_area_mm2":result["future_trace_overlap_unique_area_mm2"],
               "future_trace_work_items_sha256":digest(run/"future_trace_work_items.json"),
               "trace_changed_in_t02":False,
               "composition_audit_sha256":digest(audit/"t02_composition_audit.json") if audit else None,
               "edit_geometry_used_for_construction":False, "native_export":result["native_export"],
               "electrical_status":result["electrical_status"],
               "manufacturing_status":result["manufacturing_status"]}
    (run / "t02_execution_receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True)+"\n")
    disposition_doc=json.loads((run/"feature_dispositions.json").read_bytes())
    decisions_doc=json.loads((run/"t02_decisions.json").read_bytes())
    dispositions=disposition_doc["dispositions"]
    class_counts=Counter(d.get("geometric_class") for d in dispositions)
    withheld=class_counts.get("crop_edge_rectangle_withheld",0)
    crossing_polygons=class_counts.get("crop_crossing_nonrectangle_polygon",0)
    protected_other=class_counts.get(None,0)
    unsupported=sum(d.get("disposition")=="UNSUPPORTED_GEOMETRY" for d in dispositions)
    audit_link=(f'<p><a href="../{audit.name}/t02_composition_audit.json">Fresh T01→T02 composition audit</a></p>'
                if audit else '<p>Composition audit pending.</p>')
    tolerance_mm = float(policy["geometry_tolerance_mm"])
    measured_gap = (float(audit_doc["T02_to_protected_minimum_gap_mm"])
                    if audit_doc and audit_doc.get("T02_to_protected_minimum_gap_mm") is not None else None)
    trace_policy = policy["trace_interactions"]
    overlap_note = (f"{result['future_trace_overlap_count']} trace-copper overlap records "
                    f"({result['future_trace_overlap_pairwise_area_total_mm2']:.6f} mm² cumulative pairwise; "
                    f"{result['future_trace_overlap_unique_area_mm2']:.6f} mm² unique T02-added copper; "
                    f"{max((float(x['overlap_area_mm2']) for x in json.loads((run/'future_trace_work_items.json').read_bytes())['items']), default=0.0):.6f} mm² largest) "
                    "are deferred to a future trace session. The owner has not numerically bounded ‘slight’, "
                    "so this is a review diagnostic and not an accepted overlap magnitude.")
    corridor_note = (f"Side-by-side straight segments keep at least "
                     f"{result['side_by_side_centerline_gap_mm']:.5f} mm centerline standoff. This is not guaranteed physical copper clearance. "
                     f"Trace copper may still be intersected by a proposed rectangle; "
                     f"traces remain unchanged in T02. {overlap_note}")
    kind_counts=inventory_report['intersecting_supported_fcu_counts_by_kind']
    census = (f"ORG source census: {inventory_report['source_record_count']} board records enumerated; "
              f"{inventory_report['intersecting_supported_fcu_count']} supported F.Cu contributions intersect the crop "
              f"({kind_counts.get('gr_poly',0)} polygons, {kind_counts.get('gr_circle',0)} circles, "
              f"{kind_counts.get('segment',0)} segments, {kind_counts.get('arc',0)} arcs). "
              f"Disposition table covers {len(dispositions)} crop-intersecting contributions. "
              "The source inventory uses one parser lineage; independent parser completeness is NOT ESTABLISHED.")
    disposition_note = (f"The {crossing_polygons} nonrectangular polygon(s) crossing the crop edge remain protected "
                        f"because local ownership and a bounded write envelope are not established. "
                        f"{withheld} crop-edge rectangle(s) are also withheld unchanged; {protected_other} other "
                        f"non-target contributions remain protected and {unsupported} intersecting source records "
                        "have unsupported geometry.")
    growth=result['decision_counts'].get('GROW',0)
    kept=result['decision_counts'].get('KEEP',0)
    details_html=target_details_html(decisions_doc, float(policy["factor_per_axis"]))
    html=f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>T02 rectangle-preserving crop review</title><style>body{{font:16px/1.5 system-ui,sans-serif;margin:0;background:#eef3f7;color:#17283a}}main{{max-width:1500px;margin:auto;padding:28px}}header,article{{background:white;border:1px solid #cad6e0;border-radius:16px;padding:22px;margin:0 0 22px}}h1,h2{{margin:0 0 8px}}img{{display:block;width:100%;height:auto;border:1px solid #b8c7d4;border-radius:8px;background:#071522}}.stats{{display:flex;gap:20px;flex-wrap:wrap}}.stats div{{padding:10px 14px;background:#f3f7fa;border-radius:10px}}.small{{font-size:.9rem;color:#405366}}.notice{{background:#fff4d7;border-left:5px solid #dc8c00;padding:12px 16px}}a{{color:#075ea8}}.tablewrap{{overflow:auto;max-height:65vh;margin-top:12px}}table{{border-collapse:collapse;width:100%;font-size:.85rem}}th,td{{border:1px solid #cad6e0;padding:7px;text-align:left;vertical-align:top}}th{{position:sticky;top:0;background:#f3f7fa}}details{{margin:18px 0;padding:12px;border:1px solid #cad6e0;border-radius:10px}}summary{{cursor:pointer;font-weight:650}}</style><main><header><h1>T02 · Rectangle-preserving growth on the frozen T01 crop</h1><p>Four same-scale views of the registered ORG crop. Proposals stay complete rectangles: nearby circles and other non-trace copper can limit X/Y growth but cannot carve, notch, or round a rectangular contour. The {float(policy['factor_per_axis']):.2f}× per-axis ceiling is hard; rectangles whose complete capped envelope crosses the review boundary stay unchanged. Traces remain unchanged in T02.</p><p>{corridor_note}</p><p class="notice"><b>Deferred trace issues:</b> {overlap_note} <a href="future_trace_work_items.json">Open the source-bound overlap ledger</a>.</p><p class="small">{census}</p><p class="small">{disposition_note}</p><div class="stats"><div><b>Eligible rectangles</b><br>{result['target_set_count']}</div><div><b>Grown</b><br>{growth}</div><div><b>Eligible targets kept unchanged</b><br>{kept}</div><div><b>Edge rectangles withheld</b><br>{withheld}</div><div><b>Nonrect edge polygons protected</b><br>{crossing_polygons}</div><div><b>Other protected contributions</b><br>{protected_other}</div><div><b>Added copper</b><br>{result['added_area_mm2']:.6f} mm²</div><div><b>Side centerline checks</b><br>{result['side_trace_reservation_count']}</div><div><b>Trace copper overlap pairs</b><br>{result['future_trace_overlap_count']}</div><div><b>Cumulative pairwise overlap area</b><br>{result['future_trace_overlap_pairwise_area_total_mm2']:.6f} mm²</div><div><b>Unique added-copper overlap</b><br>{result['future_trace_overlap_unique_area_mm2']:.6f} mm²</div><div><b>Neighbor responses</b><br>{len(result['current_neighbor_causal_pairs'])} counterfactual pairs</div><div><b>Replay</b><br>byte-identical</div></div>{details_html}<p class="small">Geometric experiment only. Future trace reroute, bend, narrowing or no-change decisions are not applied or presumed. Trace proximity is geometric and does not infer electrical attachment. Electrical identity, EDIT equivalence, native export and manufacturing approval remain NOT ESTABLISHED.</p><p><a href="t02_result.json">Run summary</a> · <a href="t02_decisions.json">Decisions</a> · <a href="feature_dispositions.json">Full source dispositions</a> · <a href="future_trace_work_items.json">Future trace work items</a> · <a href="determinism_receipt.json">Replay receipt</a></p>{audit_link}</header><article><h2>ORG · original crop</h2><img src="org_crop.svg" alt="ORG crop"></article><article><h2>T01 · accepted frozen scene</h2><img src="accepted_t01_crop.svg" alt="accepted T01 crop"></article><article><h2>T01 + T02 · resulting crop</h2><img src="t01_plus_t02.svg" alt="combined crop"></article><article><h2>T02 · additions only</h2><img src="t02_delta.svg" alt="T02 additions"></article></main></html>'''
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
