#!/usr/bin/env python3
"""Fresh-process verifier and diagnostic audit for spacing-driven T01-R1."""
from __future__ import annotations
import hashlib, json, sys
from pathlib import Path
from shapely import from_wkb
from shapely.geometry import Point
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.crop_dynamic_t01_r1 import (CONSTRUCTION_BUFFER_MM, ERROR_MM, GAP_TOLERANCE_MM, HARD_GAP_MM, _nearest_spacing_bound, run)
from src.native_inventory import inventory
EVIDENCE = ROOT / "out/crop_dynamic_tasks/t01_r1_spacing_driven_20261024"
ORG = ROOT / "dataset/szu-comm_3020301113B_intake_ready_20261021_v2/raw/ORG/top.kicad_pcb"
def sha(data): return hashlib.sha256(data).hexdigest()
def components(geometry):
    if geometry.is_empty: return []
    if geometry.geom_type == "Polygon": return [geometry]
    return [g for g in getattr(geometry, "geoms", ()) if g.geom_type == "Polygon"]
def main():
    errors=[]; checks=[]
    def check(name, ok, detail=""):
        checks.append({"name":name,"status":"PASS" if ok else "FAIL","detail":detail})
        if not ok: errors.append(name)
    receipt=json.loads((EVIDENCE/"t01_r1_run.json").read_text()); result=receipt["run"]
    policy_bytes=(EVIDENCE/"frozen_policy.json").read_bytes(); policy=json.loads(policy_bytes)
    source=ORG.read_bytes(); source_sha=sha(source)
    check("source_and_receipt_binding", source_sha==receipt["source_sha256"]==policy["source_sha256"])
    check("policy_hash_binding", sha(policy_bytes)==receipt["policy_sha256"]==result["contract_sha256"])
    check("implementation_hash_binding", policy["implementation_sha256"]==sha((ROOT/"src/crop_dynamic_t01_r1.py").read_bytes()))
    check("nearest_spacing_policy_declared", "nearest other target" in policy["parameters"]["growth_reach_rule"] and
          policy["parameters"]["hard_experimental_separation_mm"]==HARD_GAP_MM)
    check("EDIT_not_a_constructor_bound", policy["parameters"].get("EDIT_used_for_site_selection_or_growth_bound") is False)
    check("supported_target_census", result["target_occurrence_count"]==53 and result["target_site_count"]==51 and
          len(result["unsupported_FCu_influence_ids"])==0)
    check("decision_population", len(result["decisions"])==51 and
          sum(d["decision"]=="KEEP_PRIORITY_ROUND" for d in result["decisions"])==26 and
          sum(d["decision"]=="GROW" for d in result["decisions"])==23 and
          sum(d["decision"]=="KEEP_CONSTRAINED" for d in result["decisions"])==2)
    check("priority_outlines", len(result["priority_outline_checks"])==26 and
          all(x["status"]=="ROUND_OUTLINE_PRESERVED" for x in result["priority_outline_checks"]))
    check("hard_gap", not result["dynamic_hard_gap_violations"] and
          result["minimum_dynamic_optional_gap_mm"]>=HARD_GAP_MM-GAP_TOLERANCE_MM-1e-10,
          str(result["minimum_dynamic_optional_gap_mm"]))
    check("bounded_trace_ports", not result["attached_trace_port_violations"])
    check("runaway_domain_is_bounded", len(result["write_domain_bounds_mm"])==4 and
          len(result["influence_domain_bounds_mm"])==4)
    # Fresh replay independently binds every candidate and its evolving spacing reach.
    calibration={float(k):float(v) for k,v in policy["calibrated_radius_limits_mm"].items()}
    replay=run(source, calibrated_radius_limits=calibration)
    decisions={d["source_id"]:d for d in result["decisions"]}
    inv=inventory(source); rows={r["id"]:r for r in inv["objects"]}
    source_cores={d["source_id"]:from_wkb(inv["payloads"][rows[d["source_id"]]["geometry_sha256"]])
        for d in result["decisions"]}
    geometry_ok=[]; invariant_ok=[]; bound_ok=[]; oversize=[]
    for d in result["decisions"]:
        path=ROOT/d["geometry_artifact"]; data=path.read_bytes(); candidate=from_wkb(data)
        core=from_wkb(inv["payloads"][rows[d["source_id"]]["geometry_sha256"]])
        added=candidate.difference(core)
        geometry_ok.append(sha(data)==d["geometry_artifact_sha256"] and candidate.is_valid)
        attached=all(part.distance(core)<=ERROR_MM/2+1e-12 for part in components(added))
        invariant_ok.append(core.difference(candidate).area<=1e-10 and attached and
            (d["decision"]!="KEEP_PRIORITY_ROUND" or candidate.equals(core)))
        radius=float(d["maximum_growth_reach_mm"])
        bound_ok.append(added.difference(core.buffer(radius+ERROR_MM, quad_segs=32)).area<=1e-10 and
            d["candidate_radius_max_mm"]<=d["original_radius_mm"]+radius+ERROR_MM)
        if d["decision"]!="KEEP_PRIORITY_ROUND":
            base_area=max(core.area,1e-15); final_radius=float(d["candidate_radius_max_mm"])
            ratio=final_radius/max(float(d["original_radius_mm"]),1e-15)
            oversize.append({"source_id":d["source_id"],"source_radius_mm":d["original_radius_mm"],
                "nearest_target_source_id":d["spacing_bound_source_id"],
                "nearest_target_spacing_mm":d["nearest_target_spacing_mm"],
                "proposed_reach_mm":radius,"final_max_radial_extent_mm":final_radius,
                "added_area_mm2":d["added_area_mm2"],"final_area_ratio":d["final_effective_area_mm2"]/base_area,
                "max_radius_ratio":ratio,"limiting_obstacles":d["limiting_obstacles"],
                "ranked_high_reach":False,"ranked_high_radius_ratio":False,"ranked_high_added_area":False})
    for key in ("ranked_high_reach","ranked_high_radius_ratio","ranked_high_added_area"):
        metric={"ranked_high_reach":"proposed_reach_mm","ranked_high_radius_ratio":"max_radius_ratio",
                "ranked_high_added_area":"added_area_mm2"}[key]
        for row in sorted(oversize,key=lambda x:(x[metric],x["source_id"]),reverse=True)[:3]: row[key]=True
    check("candidate_artifact_hashes", all(geometry_ok), f"{sum(geometry_ok)}/{len(geometry_ok)}")
    check("core_attachment_priority_invariants", all(invariant_ok), f"{sum(invariant_ok)}/{len(invariant_ok)}")
    check("dynamic_spacing_envelope_containment", all(bound_ok), f"{sum(bound_ok)}/{len(bound_ok)}")
    replay_map={d["source_id"]:d for d in replay["decisions"]}
    deterministic=all(bytes.fromhex(replay_map[k]["candidate_wkb"])==(ROOT/v["geometry_artifact"]).read_bytes()
        and abs(replay_map[k]["maximum_growth_reach_mm"]-v["maximum_growth_reach_mm"])<=1e-12
        and replay_map[k]["spacing_bound_source_id"]==v["spacing_bound_source_id"]
        for k,v in decisions.items())
    check("fresh_process_determinism",deterministic)
    # Compare the evolving run with the same policy and schedule on immutable ORG only.
    static={d["source_id"]:d for d in result["static_baseline"]["decisions"]}
    interaction_rows=[]
    for d in result["decisions"]:
        s=static[d["source_id"]]
        delta=from_wkb((ROOT/d["geometry_artifact"]).read_bytes()).symmetric_difference(
            from_wkb((ROOT/s["geometry_artifact"]).read_bytes())).area
        interaction_rows.append({"source_id":d["source_id"],"order":d["order"],
            "dynamic_vs_static_symmetric_difference_mm2":delta,
            "accepted_neighbor_ids":d["prior_accepted_neighbor_ids"],
            "adapted_by_prior_acceptance":d["adapted_by_prior_acceptance"]})
    check("dynamic_event_accounting", sum(x["adapted_by_prior_acceptance"] for x in interaction_rows)==
          result["dynamic_adaptation_event_count"]==0)
    # Conservative screen: the static-source nearest-spacing bound contains
    # every possible evolving reach because accepted candidates retain their
    # source cores and only add copper, so later spacing reach cannot increase.
    static_reaches={}
    for site_id, core in source_cores.items():
        neighbors=[(other_id,other) for other_id,other in source_cores.items() if other_id!=site_id]
        static_reaches[site_id]=_nearest_spacing_bound(core,neighbors)[0]
    pair_screen=[]
    for earlier in result["decisions"]:
        if earlier["decision"]!="GROW": continue
        earlier_shape=from_wkb((ROOT/earlier["geometry_artifact"]).read_bytes())
        earlier_addition=earlier_shape.difference(source_cores[earlier["source_id"]])
        for later in result["decisions"]:
            if later["decision"]=="KEEP_PRIORITY_ROUND" or later["order"]<=earlier["order"]: continue
            max_envelope=source_cores[later["source_id"]].buffer(static_reaches[later["source_id"]],quad_segs=32)
            separation=earlier_addition.distance(max_envelope)
            pair_screen.append({"earlier_source_id":earlier["source_id"],"later_source_id":later["source_id"],
                "earlier_added_to_later_static_envelope_mm":separation,
                "within_construction_buffer":separation<=CONSTRUCTION_BUFFER_MM+ERROR_MM})
    nonpriority=[d for d in result["decisions"] if d["decision"]!="KEEP_PRIORITY_ROUND"]
    possible_pairs=[(earlier,later) for earlier in nonpriority for later in nonpriority
                    if later["order"]>earlier["order"]]
    screened_keys={(row["earlier_source_id"],row["later_source_id"]) for row in pair_screen}
    excluded_pairs=[{"earlier_source_id":earlier["source_id"],"earlier_order":earlier["order"],
                     "earlier_decision":earlier["decision"],"later_source_id":later["source_id"],
                     "later_order":later["order"],"reason":"EARLIER_SITE_ADDED_NO_COPPER"}
                    for earlier,later in possible_pairs
                    if (earlier["source_id"],later["source_id"]) not in screened_keys]
    pair_reconciles=(len(possible_pairs)==len(pair_screen)+len(excluded_pairs)
                     and all(row["earlier_decision"]!="GROW" for row in excluded_pairs))
    check("interaction_pair_reconciliation",pair_reconciles,
          f"{len(pair_screen)} screened + {len(excluded_pairs)} no-growth exclusions = {len(possible_pairs)} possible")
    pair_hits=[x for x in pair_screen if x["within_construction_buffer"]]
    closest_pair=min(pair_screen,key=lambda x:x["earlier_added_to_later_static_envelope_mm"],default=None)
    check("zero_events_explained_by_spacing_envelopes",not pair_hits,
          f"{len(pair_screen)} ordered pairs; closest separation {None if closest_pair is None else closest_pair['earlier_added_to_later_static_envelope_mm']}")
    report={"schema":"crop-dynamic-t01-r1-spacing-verification/1",
        "status":"PASS_WITH_SCOPE_LIMITS" if not errors else "FAIL",
        "source_sha256":source_sha,"policy_sha256":sha(policy_bytes),"checks":checks,
        "failed_checks":errors,"behavioral_acceptance":"PARTIAL_0_OF_3_ACCEPTED_NEIGHBOR_EVENTS",
        "construction_buffer_note":"0.025 mm is an obstacle-construction buffer; final gap is checked separately against 0.020 mm. The observed minimum is tolerance-qualified and is not a manufacturing clearance claim.",
        "independent_semantic_or_manufacturing_validation":"NOT_ESTABLISHED"}
    (EVIDENCE/"fresh_verification.json").write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
    (EVIDENCE/"spacing_oversize_and_interaction_audit.json").write_text(json.dumps({
        "schema":"crop-dynamic-t01-r1-spacing-diagnostics/1","source_sha256":source_sha,
        "summary":{"nonpriority_sites":len(oversize),"dynamic_event_count":result["dynamic_adaptation_event_count"],
                   "possible_ordered_nonpriority_pairs":len(possible_pairs),
                   "checked_earlier_added_to_later_envelopes":len(pair_screen),
                   "excluded_pairs_where_earlier_site_added_no_copper":len(excluded_pairs),
                   "within_construction_buffer_count":len(pair_hits),
                   "closest_pair":closest_pair,
                   "rank_flags":"top 3 by each observed metric for navigation only; not rejection thresholds"},
        "site_rows":oversize,"dynamic_vs_frozen_org_rows":interaction_rows,
        "ordered_pair_spacing_screen":pair_screen,"excluded_ordered_pairs":excluded_pairs},indent=2,sort_keys=True)+"\n")
    receipt["status"]["technical_checks"]="PASS_WITH_SCOPE_LIMITS" if not errors else "FAIL"
    receipt["status"]["fresh_verification_path"]="out/crop_dynamic_tasks/t01_r1_spacing_driven_20261024/fresh_verification.json"
    receipt["status"]["behavioral_acceptance"]="PARTIAL_0_OF_3_ACCEPTED_NEIGHBOR_EVENTS"
    (EVIDENCE/"t01_r1_run.json").write_text(json.dumps(receipt,indent=2,sort_keys=True)+"\n")
    report_path=EVIDENCE/"t01_r1_report.md"; report_text=report_path.read_text()
    report_text += f"\nFresh-process spacing-policy verification: `{report['status']}`. Diagnostics: `spacing_oversize_and_interaction_audit.json`; owner acceptance remains `NOT_ACCEPTED`.\n"
    report_path.write_text(report_text)
    files=sorted(p for p in EVIDENCE.rglob("*") if p.is_file() and p.name!="SHA256SUMS")
    (EVIDENCE/"SHA256SUMS").write_text("".join(f"{sha(p.read_bytes())}  {p.relative_to(EVIDENCE).as_posix()}\n" for p in files))
    print(json.dumps({"status":report["status"],"checks":len(checks),"failed":errors,
        "oversize_report":str(EVIDENCE/"spacing_oversize_and_interaction_audit.json")},indent=2))
    if errors: raise SystemExit(1)
if __name__=="__main__": main()
