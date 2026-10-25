#!/usr/bin/env python3
"""Build a browser review page for T01 groups after covered-circle exclusion."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.crop_circle_sources import source_scene, verify_assets
from shapely.geometry import box
from shapely.ops import unary_union


bundle = Path(sys.argv[1]).resolve()
selection_path = bundle / "selection.json"
report_path = bundle / "report.json"
selection = json.loads(selection_path.read_text())
report = json.loads(report_path.read_text())
bounds = json.loads((bundle / "original_crop_rings.json").read_text())["bounds_mm"]
x0, y0, x1, y1 = bounds
width = 1800
height = round(width * (y1 - y0) / (x1 - x0))

decisions = {}
for decision in report["decisions"]:
    for source_id in [decision["source_id"], *decision.get("aliases", [])]:
        decisions[source_id] = decision

policy_path = ROOT / "contracts/crop_t01_multicircle_crop_policy.json"
policy = json.loads(policy_path.read_text())
if (policy["source_sha256"] != selection["source_sha256"]
        or selection["policy_sha256"] != hashlib.sha256(policy_path.read_bytes()).hexdigest()
        or report["policy_sha256"] != selection["policy_sha256"]):
    raise SystemExit("SOURCE_POLICY_SELECTION_HASH_MISMATCH")
asset_integrity = verify_assets()
if asset_integrity["status"] != "PASS":
    raise SystemExit("ASSET_MANIFEST_NOT_PASS")
source = (ROOT / policy["source"]).read_bytes()
if hashlib.sha256(source).hexdigest() != selection["source_sha256"]:
    raise SystemExit("ORG_SOURCE_HASH_MISMATCH")
policy_for_scene = {**policy, "radius_multiplier": policy["max_growth_factor"]}
source_inventory, source_rows, source_shapes, source_tree, source_sites = source_scene(
    source, policy_for_scene, expected_unique_sites=87, expected_occurrences=96)
recognition_audit = source_inventory["circle_recognition_audit"]
covered_by_other_shape = {}
uncertain_by_other_shape = {}
eligible_sites = []
for site in source_sites:
    own_indexes = set(site["indexes"])
    queried = source_tree.query(site["core"], predicate="intersects")
    other_shapes = [source_shapes[int(index)] for index in queried
                    if int(index) not in own_indexes and not source_shapes[int(index)].is_empty]
    individually_covered = any(shape.covers(site["core"]) for shape in other_shapes)
    near_boundary = any(not shape.covers(site["core"])
                        and site["core"].difference(shape).area <= 1e-12
                        for shape in other_shapes)
    if individually_covered:
        covered_by_other_shape[site["source_id"]] = True
    elif near_boundary:
        uncertain_by_other_shape[site["source_id"]] = True
    else:
        eligible_sites.append(site)

# This page is an independent geometric-membership audit, not the T01 growth
# grouping rule. It asks which uncovered circles share actual connected F.Cu.
physical_components = {}
for site in eligible_sites:
    component_id = site.get("physical_component_source_id")
    if not isinstance(component_id, str) or len(component_id) != 64:
        raise SystemExit("MISSING_ORG_PHYSICAL_COMPONENT_ID")
    physical_components.setdefault(component_id, []).append(site)
eligible_components = []
for component_id, members in physical_components.items():
    ids = sorted(site["source_id"] for site in members)
    eligible_components.append({"component_id": "PC-" + component_id[:12],
                            "component_sha256": component_id,
                            "site_ids": ids, "members": members,
                            "size": len(members)})
eligible_components.sort(key=lambda component: component["component_id"])
replayed_physical_diagnostic = {
    "basis": "whole_board_connected_F.Cu_source_geometry_after_direct_cover_exclusion",
    "used_for_T01_growth_grouping": False,
    "accepted_physical_component_ids": ["PC-6acc2586a685", "PC-a7f115866d96",
                                        "PC-b211bc963d11", "PC-b44608d50690"],
    "multi_circle_components": [
        {"component_id": component["component_id"], "site_ids": component["site_ids"],
         "size": component["size"],
         "owner_review_status": ("OWNER_ACCEPTED_PHYSICAL_COMPONENT"
                                 if component["component_id"] in {"PC-a7f115866d96", "PC-6acc2586a685",
                                                                  "PC-b211bc963d11", "PC-b44608d50690"}
                                 else "ACCEPTANCE_NOT_RECORDED")}
        for component in eligible_components
        if component["size"] > 1]}
if replayed_physical_diagnostic != selection["physical_component_diagnostic"]:
    raise SystemExit("PHYSICAL_COMPONENT_DIAGNOSTIC_DIFFERS_FROM_SELECTION")
eligible_ids = {site["source_id"] for site in eligible_sites}
excluded_ids = set(covered_by_other_shape)
uncertain_ids = set(uncertain_by_other_shape)
if eligible_ids & (excluded_ids | uncertain_ids):
    raise SystemExit("EXCLUDED_CIRCLE_LEAKED_INTO_ELIGIBLE_GROUPS")
if eligible_ids | excluded_ids | uncertain_ids != {site["source_id"] for site in source_sites}:
    raise SystemExit("CIRCLE_ELIGIBILITY_PARTITION_MISMATCH")
eligible_component_rows = [component for component in eligible_components if component["size"] > 1]
viewport = box(x0, y0, x1, y1)
for component in eligible_component_rows:
    seed = component["members"][0]["indexes"][0]
    seen = {seed}
    todo = [seed]
    while todo:
        current = todo.pop()
        for item in source_tree.query(source_shapes[current], predicate="intersects"):
            index = int(item)
            if index not in seen:
                seen.add(index)
                todo.append(index)
    component_source_ids = sorted(source_rows[index]["id"] for index in seen)
    if hashlib.sha256("\n".join(component_source_ids).encode()).hexdigest() != component["component_sha256"]:
        raise SystemExit("PHYSICAL_COMPONENT_MEMBERSHIP_REPLAY_MISMATCH")
    clipped = [source_shapes[index].intersection(viewport) for index in seen
               if source_shapes[index].intersects(viewport)]
    component_geometry = unary_union(clipped)
    path_commands = []
    polygons = [component_geometry] if component_geometry.geom_type == "Polygon" else list(component_geometry.geoms)
    for polygon in polygons:
        if polygon.geom_type != "Polygon":
            continue
        for ring in [polygon.exterior, *polygon.interiors]:
            points = [((x - x0) * width / (x1 - x0), (y1 - y) * width / (x1 - x0))
                      for x, y, *_ in ring.coords]
            path_commands.append("M " + " L ".join(f"{x:.3f} {y:.3f}" for x, y in points) + " Z")
    component["component_path"] = " ".join(path_commands)
component_cards = []
for index, component in enumerate(eligible_component_rows):
    members = []
    for source_id in component["site_ids"]:
        decision = decisions.get(source_id)
        if decision is None:
            raise SystemExit(f"physical-component member has no report decision: {source_id}")
        members.append({
            "key": decision["key"],
            "source_id": source_id,
            "center_x_mm": decision["center"][0],
            "center_y_mm": decision["center"][1],
            "radius_mm": decision["source_radius_mm"],
            "decision": decision["decision"],
        })
    px_centers = [((m["center_x_mm"]-x0)*width/(x1-x0),
                   (y1-m["center_y_mm"])*width/(x1-x0)) for m in members]
    px_radii = [m["radius_mm"]*policy["max_growth_factor"]*width/(x1-x0) for m in members]
    component_bounds = [min(x-r for (x,y),r in zip(px_centers,px_radii)),
                        min(y-r for (x,y),r in zip(px_centers,px_radii)),
                        max(x+r for (x,y),r in zip(px_centers,px_radii)),
                        max(y+r for (x,y),r in zip(px_centers,px_radii))]
    owner_accepted = component["component_id"] in {"PC-a7f115866d96", "PC-6acc2586a685",
                                                    "PC-b211bc963d11", "PC-b44608d50690"}
    component_cards.append({"component_id": component["component_id"], "members": members,
                   "owner_review_status": "OWNER_ACCEPTED_PHYSICAL_COMPONENT" if owner_accepted else "ACCEPTANCE_NOT_RECORDED",
                   "component_bounds_px": component_bounds, "component_path": component["component_path"],
                   "color": "#37d9c3" if owner_accepted else "#9aa9b5"})
component_cards.sort(key=lambda component: component["owner_review_status"] != "OWNER_ACCEPTED_PHYSICAL_COMPONENT")

singletons = []
for component in eligible_components:
    if len(component["site_ids"]) != 1:
        continue
    decision = decisions.get(component["site_ids"][0])
    if decision is not None:
        singletons.append({"key": decision["key"], "center_x_mm": decision["center"][0],
                           "center_y_mm": decision["center"][1], "radius_mm": decision["source_radius_mm"]})

def circle_markers(source_ids):
    result = []
    for source_id in sorted(source_ids):
        decision = decisions.get(source_id)
        if decision is None:
            raise SystemExit(f"circle has no report decision: {source_id}")
        result.append({"key": decision["key"], "center_x_mm": decision["center"][0],
                       "center_y_mm": decision["center"][1],
                       "radius_mm": decision["source_radius_mm"]})
    return result

covered_markers = circle_markers(excluded_ids)
uncertain_markers = circle_markers(uncertain_ids)

# Emit an explicit crosswalk for T01's operational relation. It is deliberately
# separate from the physical-contact groups shown in the main selector.
decision_by_id = {row["source_id"]: row for row in report["decisions"]}
local_groups = [group for group in selection["t01_envelope_groups"] if group["size"] > 1]
local_group_by_id = {source_id: group["group_id"] for group in local_groups
                     for source_id in group["site_ids"]}
crosswalk_sites = []
for source_id in sorted([*local_group_by_id, *selection["singleton_round_site_ids"]]):
    decision = decision_by_id[source_id]
    physical_component = decision.get("physical_component")
    crosswalk_sites.append({
        "source_id": source_id,
        "key": decision["key"],
        "t01_envelope_group_id": local_group_by_id.get(source_id),
        "t01_singleton": source_id not in local_group_by_id,
        "physical_component_id": ("PC-" + physical_component[:12]
                                   if physical_component else None),
        "decision": decision["decision"],
        "growth_status": "GROWN" if decision.get("added_area_mm2", 0) > 0 else "UNCHANGED",
        "added_area_mm2": decision.get("added_area_mm2", 0),
    })
key_by_id = {row["source_id"]: row["key"] for row in crosswalk_sites}
group_by_id = {row["source_id"]: row["t01_envelope_group_id"] for row in crosswalk_sites}
crosswalk_edges = []
for edge in selection["envelope_competition_edges_diagnostic_only"]:
    if edge["a"] not in group_by_id or edge["b"] not in group_by_id:
        raise SystemExit("ENVELOPE_EDGE_ENDPOINT_NOT_ELIGIBLE")
    if group_by_id[edge["a"]] != group_by_id[edge["b"]]:
        raise SystemExit("ENVELOPE_EDGE_CROSSES_LOCAL_GROUPS")
    if edge["cap_envelope_gap_mm"] > policy["construction_gap_mm"]:
        raise SystemExit("ENVELOPE_EDGE_EXCEEDS_CONFIGURED_GAP")
    crosswalk_edges.append({**edge, "a_key": key_by_id[edge["a"]],
                            "b_key": key_by_id[edge["b"]],
                            "group_id": group_by_id[edge["a"]]})
if len(crosswalk_sites) != 40 or len(local_groups) != 6 or len(crosswalk_edges) != 13:
    raise SystemExit("T01_ENVELOPE_CROSSWALK_COUNT_MISMATCH")
envelope_crosswalk = {
    "schema": "t01-crop-envelope-crosswalk/1",
    "source_sha256": selection["source_sha256"],
    "policy_sha256": selection["policy_sha256"],
    "selection_sha256": hashlib.sha256(selection_path.read_bytes()).hexdigest(),
    "report_sha256": hashlib.sha256(report_path.read_bytes()).hexdigest(),
    "rule": "T01 local groups are transitive components of eligible circle pairs whose 1.5x maximum-growth circular envelopes have gap <= construction_gap_mm. Physical F.Cu connectivity is recorded as a separate crosswalk field and does not determine these groups.",
    "construction_gap_mm": policy["construction_gap_mm"],
    "site_count": len(crosswalk_sites),
    "multi_group_count": len(local_groups),
    "multi_group_member_count": sum(group["size"] for group in local_groups),
    "singleton_count": len(selection["singleton_round_site_ids"]),
    "competition_edge_count": len(crosswalk_edges),
    "sites": crosswalk_sites,
    "groups": [{"group_id": group["group_id"], "size": group["size"],
                "members": [decision_by_id[sid]["key"] for sid in group["site_ids"]],
                "source_ids": group["site_ids"]}
               for group in sorted(local_groups, key=lambda row: row["group_id"])],
    "edges": crosswalk_edges,
}

data = {"bounds_mm": bounds, "pixel_size": [width, height], "components": component_cards, "singletons": singletons,
        "covered_circles": covered_markers, "uncertain_circles": uncertain_markers,
        "counts": {"covered_excluded": len(covered_by_other_shape),
                   "uncertain_held": len(uncertain_by_other_shape),
                   "eligible": len(eligible_sites),
                   "singletons": len(singletons), "multi_components": len(component_cards),
                   "multi_members": sum(len(component["members"]) for component in component_cards),
                   "circle_bearing_components": len(eligible_components),
                   "t01_growth_groups": sum(1 for g in selection["t01_envelope_groups"] if g["size"] > 1),
                   "t01_growth_group_members": sum(g["size"] for g in selection["t01_envelope_groups"] if g["size"] > 1)},
        "asset_integrity": asset_integrity, "recognition": recognition_audit,
        "t01_envelope_crosswalk": envelope_crosswalk}

page = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>T01 physical components and envelope groups</title>
<style>
:root{font:16px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color:#172b3d;background:#edf3f7}
body{margin:0;padding:24px}.wrap{max-width:1500px;margin:auto}.card{background:white;border:1px solid #d3e0e9;border-radius:16px;padding:22px;margin:0 0 20px;box-shadow:0 3px 14px #17324a0a}
h1{margin:0 0 6px;font-size:28px}p{margin:8px 0}.stats{display:flex;gap:12px;flex-wrap:wrap;margin:16px 0}.stat{background:#f2f7fb;border-radius:12px;padding:10px 14px;min-width:135px}.stat b{display:block;font-size:24px}.layout{display:grid;grid-template-columns:minmax(0,1fr) 360px;gap:18px}.views{display:grid;grid-template-columns:1fr 1fr;gap:12px}.view h2{font-size:18px;margin:0 0 8px}.board{position:relative;background:#071522;border-radius:10px;overflow:hidden;border:1px solid #b7c7d3}.board img{display:block;width:100%;height:auto}.board svg{position:absolute;inset:0;width:100%;height:100%;pointer-events:none}.groups{display:grid;gap:8px}.groups button{font:inherit;text-align:left;background:#fff;border:1px solid #c8d7e1;border-radius:10px;padding:10px 12px;cursor:pointer}.groups button.active{outline:3px solid #248bff;border-color:#248bff}.groups button:hover{background:#f3f8fb}.gid{font-size:12px;color:#617587}.members{font-weight:650}.hint{color:#526779;font-size:14px}.pill{display:inline-block;border-radius:999px;background:#edf4f8;padding:3px 8px;font-size:13px;margin-right:5px}.legend{font-size:14px;color:#526779}.notice{background:#fff6df;border-left:4px solid #e6b848;padding:10px 14px;border-radius:6px}.member-dot{font-size:16px;font-weight:800;paint-order:stroke;stroke:#071522;stroke-width:3px;stroke-linejoin:round;fill:white}
#focus .board{aspect-ratio:1800/1324}
@media(max-width:950px){.layout{grid-template-columns:1fr}.views{grid-template-columns:1fr}}
</style></head><body><main class="wrap">
<section class="card"><h1>Which uncovered circles share a connected F.Cu component?</h1><p>This is a source-geometry audit: identify filled ORG F.Cu circles, remove those covered by other copper, hold uncertain cases aside, then count the remaining circles in each connected whole-board F.Cu component. Choose a multi-circle component to inspect its members in the full crop and close-up.</p><div class="stats" id="stats"></div><p class="notice" id="pairNotice"></p><p class="hint">This component audit is separate from T01's operational grouping, which remains based on local 1.5× growth-envelope competition. This review does not qualify candidate growth or manufacturing behavior.</p></section>
<section class="card layout"><div><div class="views"><div class="view"><h2>ORG · all source-circle locations</h2><div class="board"><img src="before_t01.png"><svg id="beforeMarks" viewBox="0 0 1800 1324" preserveAspectRatio="none"></svg></div></div><div class="view"><h2>T01 candidate · same crop context</h2><div class="board"><img src="after_t01.png"><svg id="afterMarks" viewBox="0 0 1800 1324" preserveAspectRatio="none"></svg></div></div></div><p class="legend">Tinted regions are the actual connected F.Cu physical component. Bright rings mark uncovered circle members. Gray rings are uncovered singleton circles; dashed gray rings are directly covered and excluded; orange rings are uncertain and held out.</p><div id="focus" hidden><h2 id="focusTitle">Selected physical component close-up</h2><div class="views"><div class="view"><h2>ORG · selected component in crop context</h2><div class="board"><svg id="zoomBefore" viewBox="0 0 1800 1324" preserveAspectRatio="xMidYMid meet"></svg></div></div><div class="view"><h2>T01 · selected component in crop context</h2><div class="board"><svg id="zoomAfter" viewBox="0 0 1800 1324" preserveAspectRatio="xMidYMid meet"></svg></div></div></div></div></div><aside><h2 style="margin-top:0">Physical F.Cu components with multiple uncovered circles</h2><div class="groups" id="components"></div><p class="hint" id="selectionHint">Choose a component to highlight its uncovered circles.</p></aside></section>
<section class="card"><h2>Separate relationship: T01 envelope groups</h2><p>These are the operational T01 groups. They are built from transitive competition between eligible circles’ 1.5× maximum-growth envelopes at the configured gap. Physical copper connectivity above is an independent finding and does not choose these groups.</p><div id="t01Groups"></div><h3>Envelope-competition edges</h3><div id="t01Edges"></div><p class="hint">The source-bound site crosswalk also records each circle’s physical-component ID and growth disposition. It is saved beside this page as <a href="t01_envelope_crosswalk.json">t01_envelope_crosswalk.json</a>.</p></section>
<section class="card"><h2>Reading the counts</h2><p id="explain"></p><p class="hint" id="relationNote"></p></section>
<script>
const D=__DATA__;
const stats=document.getElementById('stats');
for(const [n,label] of [[D.counts.covered_excluded,'circles directly covered by another source shape'],[D.counts.uncertain_held,'uncertain circles held out'],[D.counts.eligible,'uncovered eligible circles'],[D.counts.circle_bearing_components,'physical F.Cu components with eligible circles'],[D.counts.multi_components,'physical components with multiple uncovered circles'],[D.counts.multi_members,'uncovered circles in those physical components'],[D.counts.t01_growth_groups,'T01 envelope-based groups'],[D.counts.t01_growth_group_members,'circles in T01 envelope groups']]){const e=document.createElement('div');e.className='stat';e.innerHTML=`<b>${n}</b>${label}`;stats.appendChild(e)}
document.getElementById('explain').textContent=`After exclusions, ${D.counts.eligible} uncovered circles remain across ${D.counts.circle_bearing_components} physical components. ${D.counts.multi_members} uncovered circles share ${D.counts.multi_components} physical component${D.counts.multi_components===1?'':'s'}; the other ${D.counts.singletons} eligible circles are alone in their physical component.`;
document.getElementById('relationNote').textContent=`Circle recognition cross-check: ${D.recognition.raw_occurrences} raw source occurrences at ${D.recognition.raw_unique_sites} unique center/radius sites match the inventory exactly by source span and geometry. Each physical component identity was replayed from the connected source-shape graph and checked against its source-ID hash. The separate T01 counts above come from its 1.5× envelope competition rule; they do not define physical components.`;
document.getElementById('pairNotice').textContent=D.components.length?`Physical F.Cu components accepted by the owner after direct-cover exclusions: ${D.components.map(c=>`${c.component_id} (${c.owner_review_status}) has ${c.members.map(m=>m.key).join(' and ')}`).join('; ')}. These are physical connectivity findings, not T01 envelope groups.`:'No physical F.Cu component contains more than one uncovered circle under this audit.';
const local=D.t01_envelope_crosswalk;
document.getElementById('t01Groups').innerHTML=local.groups.map(g=>`<p><b>${g.group_id}</b> · ${g.size} circles · ${g.members.join(' · ')}</p>`).join('')+`<p class="hint">${local.singleton_count} eligible circles remain T01 singletons. These six envelope groups contain ${local.multi_group_member_count} circles.</p>`;
document.getElementById('t01Edges').innerHTML=local.edges.map(e=>`<span class="pill">${e.a_key} ↔ ${e.b_key}: ${e.cap_envelope_gap_mm.toFixed(6)} mm</span>`).join('');
let selected=(D.components.find(c=>c.owner_review_status==='OWNER_ACCEPTED_PHYSICAL_COMPONENT')||D.components[0])?.component_id||null;
function xy(m){return [(m.center_x_mm-D.bounds_mm[0])*D.pixel_size[0]/(D.bounds_mm[2]-D.bounds_mm[0]),(D.bounds_mm[3]-m.center_y_mm)*D.pixel_size[0]/(D.bounds_mm[2]-D.bounds_mm[0])]}
function drawMarkup(svg){svg.innerHTML='';for(const c of D.components){if(selected&&c.component_id!==selected)continue;const cp=document.createElementNS('http://www.w3.org/2000/svg','path');cp.setAttribute('d',c.component_path);cp.setAttribute('fill',c.color);cp.setAttribute('fill-opacity','.32');cp.setAttribute('fill-rule','evenodd');cp.setAttribute('stroke',c.color);cp.setAttribute('stroke-width','2');svg.appendChild(cp)}function ring(m,color,width,dash){const [x,y]=xy(m),r=Math.max(10,m.radius_mm*D.pixel_size[0]/(D.bounds_mm[2]-D.bounds_mm[0]));const c=document.createElementNS('http://www.w3.org/2000/svg','circle');c.setAttribute('cx',x);c.setAttribute('cy',y);c.setAttribute('r',r);c.setAttribute('fill','none');c.setAttribute('stroke',color);c.setAttribute('stroke-width',width);if(dash)c.setAttribute('stroke-dasharray',dash);svg.appendChild(c)}for(const m of D.singletons)ring(m,'#c3d0d9',2);for(const m of D.covered_circles)ring(m,'#667684',2,'4 4');for(const m of D.uncertain_circles)ring(m,'#ff9f43',3);for(const c of D.components){if(selected&&c.component_id!==selected)continue;for(const m of c.members){ring(m,c.color,selected?6:4);const [x,y]=xy(m),r=Math.max(10,m.radius_mm*D.pixel_size[0]/(D.bounds_mm[2]-D.bounds_mm[0]));const t=document.createElementNS('http://www.w3.org/2000/svg','text');t.setAttribute('x',x+r+3);t.setAttribute('y',y-2);t.setAttribute('class','member-dot');t.textContent=m.key;svg.appendChild(t)}}}
function draw(){for(const id of ['beforeMarks','afterMarks'])drawMarkup(document.getElementById(id));
const focus=document.getElementById('focus');focus.hidden=!selected;if(selected){const c=D.components.find(c=>c.component_id===selected);document.getElementById('focusTitle').textContent=`${c.component_id} · ${c.members.length} uncovered circles in one connected physical F.Cu component: ${c.members.map(m=>m.key).join(' · ')}`;const [minX0,minY0,maxX0,maxY0]=c.component_bounds_px,pad=55,minX=minX0-pad,maxX=maxX0+pad,minY=minY0-pad,maxY=maxY0+pad;for(const [id,img] of [['zoomBefore','before_t01.png'],['zoomAfter','after_t01.png']]){const svg=document.getElementById(id);svg.setAttribute('viewBox',`${minX} ${minY} ${maxX-minX} ${maxY-minY}`);svg.innerHTML=`<image href="${img}" x="0" y="0" width="${D.pixel_size[0]}" height="${D.pixel_size[1]}"/>`;drawMarkup(svg)}}
document.querySelectorAll('#components button').forEach(b=>b.classList.toggle('active',b.dataset.id===selected));document.getElementById('selectionHint').textContent=selected?`The connected physical source-copper component is tinted; only uncovered circles count as members.`:'Choose a physical component to highlight its uncovered circles.'}
const root=document.getElementById('components');for(const c of D.components){const b=document.createElement('button');b.dataset.id=c.component_id;b.innerHTML=`<div class="gid"><span style="color:${c.color}">●</span> ${c.component_id} · ${c.members.length} uncovered circles · ${c.owner_review_status.replaceAll('_',' ')}</div><div class="members">${c.members.map(m=>m.key).join(' · ')}</div>`;b.onclick=()=>{selected=selected===c.component_id?null:c.component_id;draw();if(selected)document.getElementById('focus').scrollIntoView({behavior:'smooth',block:'start'})};root.appendChild(b)}draw();
</script></main></body></html>'''.replace("__DATA__", json.dumps(data, separators=(",", ":")))

out = bundle / "post_exclusion_group_review"
out.mkdir(exist_ok=True)
(out / "index.html").write_text(page)
crosswalk_path = out / "t01_envelope_crosswalk.json"
crosswalk_path.write_text(json.dumps(envelope_crosswalk, indent=2) + "\n")
for name in ("before_t01.png", "after_t01.png"):
    target = out / name
    source = bundle / name
    if not target.exists() or hashlib.sha256(target.read_bytes()).digest() != hashlib.sha256(source.read_bytes()).digest():
        target.write_bytes(source.read_bytes())
receipt = {"status": "PRESENTATION_ONLY", "source_bundle": str(bundle),
           "selection_sha256": hashlib.sha256(selection_path.read_bytes()).hexdigest(),
           "report_sha256": hashlib.sha256(report_path.read_bytes()).hexdigest(),
           "source_sha256": selection["source_sha256"],
           "asset_manifest_status": asset_integrity["status"],
           "eligibility_method": "Exclude a circle only when one other source primitive directly covers it. Do not combine multiple primitives to infer coverage. Hold out cases where one intersecting primitive leaves at most 1e-12 mm^2 uncovered.",
           "grouping_method": "For this independent evidence page, count eligible circles by their whole-board connected F.Cu source-geometry component; replay and verify the component source-ID hash. This audit does not redefine T01 operational growth groups, which remain based on 1.5x envelope competition.",
           "raw_recognition_crosscheck": recognition_audit,
           "counts": data["counts"],
           "t01_envelope_crosswalk_sha256": hashlib.sha256(crosswalk_path.read_bytes()).hexdigest(),
           "t01_envelope_groups": envelope_crosswalk["groups"],
           "t01_envelope_competition_edges": envelope_crosswalk["edges"],
           "physical_component_members": [{"component_id": c["component_id"], "members": [m["key"] for m in c["members"]],
                                           "owner_review_status": c["owner_review_status"]} for c in component_cards]}
(out / "review_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
print(json.dumps(receipt, indent=2))
