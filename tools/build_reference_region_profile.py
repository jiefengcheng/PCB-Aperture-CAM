#!/usr/bin/env python3
"""Build the pinned G22 three-member reference and region evidence sheet."""
from __future__ import annotations

import hashlib
import html
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.reference_region_profile import build_profile  # noqa: E402

OUT = ROOT / "out/ingestion/audits/20261024_g22_reference_region_profile_v1"


def esc(value) -> str:
    return html.escape(str(value), quote=True)


def fmt(value, places=6) -> str:
    return f"{value:.{places}f}"


def _svg(bounds, paths, *, class_name="member-map", height=280) -> str:
    x0, y0, x1, y1 = bounds
    width, height_mm = max(x1 - x0, 0.01), max(y1 - y0, 0.01)
    pad = max(width, height_mm) * 0.1
    view = f"{x0-pad:.9f} {y0-pad:.9f} {width+pad*2:.9f} {height_mm+pad*2:.9f}"
    body = []
    for item in paths:
        if item.get("d"):
            attrs = [f'd="{esc(item["d"])}"', f'class="{esc(item["class"])}"', 'fill-rule="evenodd"']
            if item.get("title"):
                body.append(f"<path {' '.join(attrs)}><title>{esc(item['title'])}</title></path>")
            else:
                body.append(f"<path {' '.join(attrs)}/>")
        if item.get("cx") is not None:
            body.append(f'<circle cx="{item["cx"]:.9f}" cy="{item["cy"]:.9f}" r="0.012" class="center-mark"/>')
    return f'<svg class="{class_name}" viewBox="{view}" role="img" aria-label="Measured ORG family geometry">{"".join(body)}</svg>'


def _report(profile: dict) -> str:
    b = profile["binding"]
    lines = [
        "# G22 three-member Reference and Region Profile",
        "",
        "**Status: `REVIEW_EVIDENCE_READY` for human inspection.** This is a source-bound measurement profile, not semantic or manufacturing qualification.",
        "",
        f"The profile reuses confirmed family `{profile['family']['family_key']}` and pinned source revision `{b['org_revision']}`. It does not rerun family recognition. The standalone [visual evidence sheet](index.html) shows one family view and three member cards.",
        "",
        "## Family at a glance",
        "",
        "| Member | Center (mm) | Seed diameter (mm) | F.Cu contact group | F.Mask / F.Paste geometric overlap | Support / bend / electrical status |",
        "|---|---:|---:|---:|---|---|",
    ]
    for m in profile["family"]["members"]:
        states = "UNKNOWN for seed + both traces"
        refs = ", ".join(f"{r['layers'][0]} {('matches' if r['geos_equals_seed'] else 'differs')}" for r in m["references"])
        lines.append(f"| {m['ordinal']} | ({fmt(m['center_mm'][0],3)}, {fmt(m['center_mm'][1],3)}) | {fmt(m['seed']['diameter_mm'],5)} | {m['physical_contact_group']['count']} objects | {refs} | {states} |")
    lines.extend(["", "The members are a **provisional geometric family hypothesis** and have three distinct transitive F.Cu contact groups. The group counts (22, 18, 10) are not one shared connected copper object.", "", "## What is measured", ""])
    for m in profile["family"]["members"]:
        group_kinds = ", ".join(f"{kind}: {count}" for kind, count in sorted(m["physical_contact_group"]["kind_counts"].items()))
        lines.extend([
            f"### Member {m['ordinal']} — `{m['member_key']}`",
            "",
            f"Seed center `{m['center_mm'][0]:.6f}, {m['center_mm'][1]:.6f}` mm; diameter `{m['seed']['diameter_mm']:.5f}` mm; stored-WKB area `{m['seed']['area_mm2']:.12f}` mm²; source ID `{m['seed_source_id']}`.",
            "",
            "| Candidate reference | Layer | Diameter from measured bounds (mm) | Offset from seed (mm) | GEOS distance (mm) | Overlap area (mm²) | Authority / fixed status |",
            "|---|---|---:|---:|---:|---:|---|",
        ])
        for r in m["references"]:
            diameter = r["bounds_mm"][2] - r["bounds_mm"][0]
            lines.append(f"| Geometric feature candidate | {r['layers'][0]} | {diameter:.5f} | ({r['seed_center_offset_mm'][0]:.6f}, {r['seed_center_offset_mm'][1]:.6f}) | {r['seed_distance_mm']:.9f} | {r['intersection_area_mm2']:.12f} | `{r['authority_status']}` / `UNKNOWN` |")
        lines.extend([
            "",
            "| Attached trace candidate | Width (mm) | net id | Seed intersection area (mm²) | Geometric contact | Source ID |",
            "|---|---:|---:|---:|---|---|",
        ])
        for t in m["traces"]:
            lines.append(f"| {t['kind']} | {t['width_mm']:.5f} | {t['net_id']} | {t['seed_intersection_area_mm2']:.12f} | `{str(t['seed_intersects']).upper()}` | `{t['object_id']}` |")
        lines.extend([
            "",
            f"**Contact group:** `{m['physical_contact_group']['key']}`; {m['physical_contact_group']['count']} source objects ({group_kinds}); reconstructed using transitive F.Cu GEOS intersection over stored WKB.",
            "",
            "| Context subject | CVL_TOP box-gap lower bound (mm) | CVL_BOTTOM box-gap lower bound (mm) | SUS_BOTTOM box-gap lower bound (mm) | OUTBOARD box-gap lower bound (mm) | Supported | Bending | Electrical restriction |",
            "|---|---:|---:|---:|---:|---|---|---|",
        ])
        region_layer_names = ["cvl_top.gdo.gbr", "cvl_bottom.gdo.gbr", "sus_bottom.gdo.gbr", "outboard.gdo.gbr"]
        def region_gap_values(rows):
            by_name = {row["path"].split("/")[-1]: row for row in rows}
            return [by_name[name]["seed_to_feature_bbox_distance_lower_bound_mm"] for name in region_layer_names]
        seed_gaps = " | ".join(f"{value:.6f}" for value in region_gap_values(m["additional_org_layer_geometry"]["seed"]))
        lines.append(f"| Seed `{m['context']['seed']['subject_id']}` | {seed_gaps} | `UNKNOWN` | `UNKNOWN` | `UNKNOWN` |")
        for c, region in zip(m["context"]["traces"], m["additional_org_layer_geometry"]["traces"]):
            trace_gaps = " | ".join(f"{value:.6f}" for value in region_gap_values(region["layers"]))
            lines.append(f"| Attached {region['kind']} `{c['subject_id']}` | {trace_gaps} | `UNKNOWN` | `UNKNOWN` | `UNKNOWN` |")
        lines.extend([
            "",
            "Nearest external same-layer geometry candidates measured from the seed (not the full group):",
            "",
            "| Gap from seed (mm) | Kind | Candidate source ID |",
            "|---:|---|---|",
        ])
        for n in m["nearby_external_copper_geometry"][:5]:
            lines.append(f"| {n['gap_from_seed_mm']:.9f} | {n['kind']} | `{n['object_id']}` |")
        lines.extend([
            "", "Each gap is geometric proximity only; it does not identify an electrical obstacle or apply a clearance rule.", "",
            "Additional ORG job-layer coverage measured by per-object Gerber bounding boxes:", "",
            "| Source layer filename | Nearest primitive | Seed-to-box gap lower bound (mm) | Box matches seed | Strict image parser |",
            "|---|---|---:|---|---|",
        ])
        for layer in m["additional_org_layer_geometry"]["seed"]:
            lines.append(f"| `{layer['path'].split('/')[-1]}` | {layer.get('nearest_feature_type','—')} | {layer.get('seed_to_feature_bbox_distance_lower_bound_mm',float('nan')):.6f} | `{str(layer.get('seed_bbox_matches_feature_bbox_within_5um',False)).upper()}` | `{layer['strict_project_geometry_parser_probe']['status']}` |")
        lines.extend(["", "Bounding-box separation is only a conservative lower bound to the plotted feature; the project's strict image parser rejects these Gerbers at `%IPPOS%`. The top-copper/mask/paste boxes match the seed placement. `CVL_TOP`, `CVL_BOTTOM`, `SUS_BOTTOM`, and `OUTBOARD` are filename-labelled geometry candidates only, not authoritative process-region declarations.", ""])
        lines.extend([
        "## Reference authority and region context",
        "",
        "| Question for each seed and attached trace | Current status | Evidence boundary |",
        "|---|---|---|",
        "| Is the termination mechanically supported? | `UNKNOWN` | No member-specific support/stiffener/backer or termination declaration surfaced in the bounded lexical scan; zero hits do not prove absence. |",
        "| Does the location encounter active bending? | `UNKNOWN` | No member-specific bend/flex region declaration surfaced in the bounded lexical scan; zero hits do not prove absence. |",
        "| Are electrical changes restricted here? | `UNKNOWN` | The measured attached-trace records carry KiCad net id `0`; this is not net intent. The project has no netclass assignments. |",
        "| Are F.Mask/F.Paste candidates authoritative and fixed? | `UNKNOWN` | Their stored geometry equals each seed, but the ORG board is GerbView-generated; layer labels and shape coincidence do not prove process purpose, authority, or editability. |",
        "",
        f"The inspected project defaults include min clearance `{profile['project_defaults']['min_clearance_mm']}` mm, default netclass clearance `{profile['project_defaults']['default_netclass_clearance_mm']}` mm, and min track width `{profile['project_defaults']['min_track_width_mm']}` mm. These are generic project settings, not a member-bound rule or approval.",
        "",
        "`UNKNOWN` does not mean “not supported,” “not bending,” or “safe to reshape.” The next exact inputs needed are an authoritative support/flex region source and an electrical/net-constraint source revision that can be associated with these objects.",
        "",
        "## Provenance and limits",
        "",
        f"- Dataset `{b['dataset_id']}`; snapshot `{b['input_snapshot_id']}`.",
        f"- ORG source SHA-256 `{b['org_source_sha256']}`; ORG revision `{b['org_revision']}`.",
        f"- Family map revision `{b['map_revision']}`; projection file SHA-256 `{b['projection_file_sha256']}`.",
        f"- Measurement: `native-inventory/2` stored WKB; GEOS/Shapely; geometry error `{b['geometry_error_mm']}` mm; curve approximation `{b['per_curve_approximation_error_mm']}` mm.",
        f"- Dataset seal: `{profile['source_material_integrity']['dataset_sha256_manifest']['status']}`; failed paths `{profile['source_material_integrity']['dataset_sha256_manifest']['failed_paths']}`. Inputs were not modified or resealed.",
        "- Context sources inspected (bounded lexical scan; zero hits do not prove semantic absence):",
        "",
        "  | Source path | Current SHA-256 | Intake profile match |",
        "  |---|---|---|",
        *[f"  | `{item['path']}` | `{item['sha256']}` | `{item.get('status', '—')}` |" for item in profile["source_search"]["files"]],
        "",
        "- Full machine-readable values: [profile.json](profile.json). Reproduction: `./.venv/bin/python tools/build_reference_region_profile.py`.",
        "",
        "This profile does not select or rank a copper treatment, run a simulation, blend or cut back geometry, alter any board, or establish engineering/manufacturing acceptance.",
        "",
    ])
    return "\n".join(lines)


def _html(profile: dict) -> str:
    members = profile["family"]["members"]
    all_bounds = [member["seed"]["bounds_mm"] for member in members]
    all_bounds += [trace["bounds_mm"] for member in members for trace in member["traces"]]
    x0 = min(bounds[0] for bounds in all_bounds)
    y0 = min(bounds[1] for bounds in all_bounds)
    x1 = max(bounds[2] for bounds in all_bounds)
    y1 = max(bounds[3] for bounds in all_bounds)
    overview_paths = []
    colors = ["seed-one", "seed-two", "seed-three"]
    for member, color in zip(members, colors):
        for trace in member["traces"]:
            overview_paths.append({"d": trace["svg_path"], "class": "trace"})
        overview_paths.append({"d": member["seed"]["svg_path"], "class": color})
        overview_paths.append({"cx": member["center_mm"][0], "cy": member["center_mm"][1]})
    sections = []
    for member in members:
        render_paths = []
        for neighbor in member["nearby_external_copper_geometry"][:5]:
            render_paths.append({"d": neighbor["svg_path"], "class": "neighbor", "title": f"{neighbor['kind']} gap {neighbor['gap_from_seed_mm']:.6f} mm"})
        for trace in member["traces"]:
            render_paths.append({"d": trace["svg_path"], "class": "trace", "title": f"Attached {trace['kind']} trace, width {trace['width_mm']:.5f} mm; net {trace['net_id']}"})
        for reference in member["references"]:
            render_paths.append({"d": reference["svg_path"], "class": "mask-ref" if reference["layers"][0] == "F.Mask" else "paste-ref", "title": f"{reference['layers'][0]} geometric candidate, coincident with seed"})
        render_paths.append({"d": member["seed"]["svg_path"], "class": "seed"})
        render_paths.append({"cx": member["center_mm"][0], "cy": member["center_mm"][1]})
        bounds = [member["seed"]["bounds_mm"], *[t["bounds_mm"] for t in member["traces"]], *[n["bounds_mm"] for n in member["nearby_external_copper_geometry"][:5]]]
        view_bounds = [min(b[0] for b in bounds), min(b[1] for b in bounds), max(b[2] for b in bounds), max(b[3] for b in bounds)]
        diagram = _svg(view_bounds, render_paths)
        ref_rows = "".join(f"<tr><td>{esc(r['layers'][0])}</td><td>{fmt(r['bounds_mm'][2]-r['bounds_mm'][0],5)} × {fmt(r['bounds_mm'][3]-r['bounds_mm'][1],5)}</td><td>{fmt(r['seed_center_offset_mm'][0],6)}, {fmt(r['seed_center_offset_mm'][1],6)}</td><td>{fmt(r['intersection_area_mm2'],12)}</td><td><strong>UNKNOWN / UNKNOWN</strong></td></tr>" for r in member["references"])
        trace_rows = "".join(f"<tr><td>{esc(t['kind'])}</td><td>{fmt(t['width_mm'],5)}</td><td>{t['net_id']}</td><td>{fmt(t['seed_intersection_area_mm2'],12)}</td><td class='mono'>{esc(t['object_id'])}</td></tr>" for t in member["traces"])
        neighbor_rows = "".join(f"<tr><td>{fmt(n['gap_from_seed_mm'],9)}</td><td>{esc(n['kind'])}</td><td class='mono'>{esc(n['object_id'])}</td></tr>" for n in member["nearby_external_copper_geometry"][:5])
        layer_rows = "".join(f"<tr><td>{esc(layer['path'].split('/')[-1])}</td><td>{esc(layer.get('nearest_feature_type','—'))}</td><td>{fmt(layer.get('seed_to_feature_bbox_distance_lower_bound_mm',float('nan')),6)}</td><td>{'yes' if layer.get('seed_bbox_matches_feature_bbox_within_5um') else 'no'}</td><td>{esc(layer['strict_project_geometry_parser_probe']['status'])}</td></tr>" for layer in member["additional_org_layer_geometry"]["seed"])
        region_gap_rows = []
        region_layer_names = ["cvl_top.gdo.gbr", "cvl_bottom.gdo.gbr", "sus_bottom.gdo.gbr", "outboard.gdo.gbr"]
        for subject_kind, context_subject, layer_rows_for_subject in [("seed", member["context"]["seed"], member["additional_org_layer_geometry"]["seed"]), *[(trace["kind"], context, region["layers"]) for trace,context,region in zip(member["traces"],member["context"]["traces"],member["additional_org_layer_geometry"]["traces"])]]:
            region_gaps = {row["path"].split("/")[-1]: row["seed_to_feature_bbox_distance_lower_bound_mm"] for row in layer_rows_for_subject}
            gap_cells = "".join(f"<td>{fmt(region_gaps[name],6)}</td>" for name in region_layer_names)
            region_gap_rows.append(f"<tr><td>{esc(subject_kind)}</td><td class='mono'>{esc(context_subject['subject_id'])}</td>{gap_cells}<td>UNKNOWN</td><td>UNKNOWN</td><td>UNKNOWN</td></tr>")
        region_gap_rows = "".join(region_gap_rows)
        context_rows = f"<li><strong>Seed:</strong> <span class='unknown'>UNKNOWN</span> for support, active bending, and electrical restriction. <span class='mono'>{esc(member['context']['seed']['subject_id'])}</span></li>"
        context_rows += "".join(f"<li><strong>Attached {esc(trace['kind'])}:</strong> <span class='unknown'>UNKNOWN</span> for support, active bending, and electrical restriction. <span class='mono'>{esc(context['subject_id'])}</span></li>" for trace,context in zip(member["traces"], member["context"]["traces"]))
        sections.append(f'''<section class="card">
          <div><p class="eyebrow">MEMBER {member['ordinal']} · {member['physical_contact_group']['count']} OBJECT CONTACT GROUP</p><h2>({member['center_mm'][0]:.3f}, {member['center_mm'][1]:.3f}) mm</h2><p class="mono">Member {esc(member['member_key'])}<br>Seed {esc(member['seed_source_id'])}</p></div>
          {diagram}
          <div class="numbers"><div><b>{member['seed']['diameter_mm']:.5f} mm</b><span>seed diameter</span></div><div><b>{member['seed']['area_mm2']:.9f} mm²</b><span>stored-WKB area</span></div><div><b>{member['physical_contact_group']['count']}</b><span>separate group objects</span></div></div>
          <h3>Reference candidates — measured geometry</h3><p>F.Mask and F.Paste candidates exactly match the seed geometry in this pinned representation. Their manufacturing role, authority and fixed status remain <strong>UNKNOWN</strong>.</p>
          <table><thead><tr><th>Layer label</th><th>Bounds (mm)</th><th>Center offset (mm)</th><th>Overlap with seed (mm²)</th><th>Authority / fixed</th></tr></thead><tbody>{ref_rows}</tbody></table>
          <h3>Attached trace candidates</h3><table><thead><tr><th>Geometry</th><th>Width</th><th>KiCad net id</th><th>Seed contact area</th><th>Source identity</th></tr></thead><tbody>{trace_rows}</tbody></table><p class="callout">Net id 0 and geometric touching do not establish named electrical connectivity.</p>
          <h3>Nearby F.Cu geometry gaps from seed</h3><table><thead><tr><th>Gap (mm)</th><th>Kind</th><th>Source identity</th></tr></thead><tbody>{neighbor_rows}</tbody></table><p class="callout">These are seed-to-object geometric gaps, not clearance-rule results or electrical obstacles. The drawing highlights the five rows shown here.</p>
          <h3>Other ORG job-layer geometry</h3><div class="grid-scroll"><table><thead><tr><th>Source filename</th><th>Nearest primitive</th><th>Seed-to-box gap lower bound (mm)</th><th>Box matches seed</th><th>Strict image parser</th></tr></thead><tbody>{layer_rows}</tbody></table></div><p class="callout">Gerbonara per-object boxes show the filename-labelled CVL_TOP, CVL_BOTTOM, SUS_BOTTOM and OUTBOARD candidates; filenames do not prove process role or region authority. The boxes provide lower bounds; the strict project image parser rejects these files at IPPOS.</p>
          <h3>Region geometry by subject</h3><div class="grid-scroll"><table><thead><tr><th>Object</th><th>Source identity</th><th>CVL_TOP box-gap lower bound</th><th>CVL_BOTTOM box-gap lower bound</th><th>SUS_BOTTOM box-gap lower bound</th><th>OUTBOARD box-gap lower bound</th><th>Supported</th><th>Bending</th><th>Electrical restriction</th></tr></thead><tbody>{region_gap_rows}</tbody></table></div><p class="callout">Each seed and each attached trace is evaluated separately. Distances are conservative Gerber-object bounding-box lower bounds; all region claims remain UNKNOWN.</p>
          <h3>Region evidence — seed and traces assessed separately</h3><ul>{context_rows}</ul><p class="callout">Unknown is not a negative classification and does not authorize reshaping.</p>
        </section>''')
    family_center_distance = [pair["center_distance_mm"] for pair in profile["family"]["pairwise_arrangement"]]
    summary = "".join(f"<tr><td>{i}</td><td>{m['center_mm'][0]:.3f}, {m['center_mm'][1]:.3f}</td><td>{m['seed']['diameter_mm']:.5f}</td><td>{m['physical_contact_group']['count']}</td><td>UNKNOWN</td></tr>" for i,m in enumerate(members,1))
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>G22 Reference and Region Profile</title>
<style>
:root{{--ink:#172b3a;--muted:#617482;--line:#d7e0e7;--paper:#fff;--soft:#f4f7f9;--blue:#147d92;--orange:#ed6a36;--amber:#dc9d17;--purple:#9255c4;--unknown:#885c0b}}
*{{box-sizing:border-box}}body{{margin:0;background:#edf2f5;color:var(--ink);font:16px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}}main{{max-width:1500px;margin:0 auto;padding:30px}}header,.card,.summary{{background:var(--paper);border:1px solid var(--line);border-radius:15px;box-shadow:0 5px 16px #1830440a}}header{{padding:30px;margin-bottom:18px}}h1{{margin:.1em 0 .3em;font-size:clamp(28px,4vw,42px)}}h2{{margin:.1em 0 .5em;font-size:26px}}h3{{margin:24px 0 8px;font-size:19px}}p{{margin:.5em 0;color:#324858}}.eyebrow{{color:var(--muted);letter-spacing:.08em;font-size:12px;font-weight:800}}.status{{display:inline-block;background:#d9f2eb;color:#126c5e;border-radius:99px;padding:6px 11px;font-weight:750}}.lead{{font-size:18px;max-width:1000px}}.summary{{padding:22px;margin-bottom:18px}}.overview{{max-height:370px;width:100%;background:#10202b;border-radius:12px;margin:12px 0}}.card{{padding:22px;margin:18px 0;display:grid;grid-template-columns:minmax(190px,.7fr) minmax(280px,1fr);gap:12px 24px}}.card>h3,.card>table,.card>p,.card>ul{{grid-column:1/-1}}.member-map{{width:100%;height:300px;background:#10202b;border-radius:12px;align-self:center}}.seed,.seed-one,.seed-two,.seed-three{{fill:#28a7b8;fill-opacity:.82;stroke:#57e2e8;stroke-width:2;vector-effect:non-scaling-stroke}}.seed-two{{fill:#4489d7;stroke:#8dc0ff}}.seed-three{{fill:#ad77d7;stroke:#e0bcff}}.trace{{fill:var(--orange);fill-opacity:.9;stroke:#ffc08e;stroke-width:1;vector-effect:non-scaling-stroke}}.mask-ref{{fill:none;stroke:#ffcc57;stroke-width:2;stroke-dasharray:5 3;vector-effect:non-scaling-stroke}}.paste-ref{{fill:none;stroke:#dc9fff;stroke-width:2;stroke-dasharray:1 3;vector-effect:non-scaling-stroke}}.neighbor{{fill:#dce8ee;fill-opacity:.5;stroke:#b9cbd5;stroke-width:1;vector-effect:non-scaling-stroke}}.center-mark{{fill:white;stroke:#10202b;stroke-width:1;vector-effect:non-scaling-stroke}}.legend{{display:flex;gap:18px;flex-wrap:wrap;color:var(--muted);font-size:14px;margin-top:9px}}.legend i{{display:inline-block;width:13px;height:13px;border-radius:3px;margin-right:5px;vertical-align:-2px}}.numbers{{display:flex;gap:10px;flex-wrap:wrap}}.numbers div{{background:var(--soft);border-radius:10px;padding:11px 14px;min-width:125px}}.numbers b,.numbers span{{display:block}}.numbers span{{font-size:12px;color:var(--muted)}}table{{width:100%;border-collapse:collapse;font-size:14px}}th,td{{text-align:left;padding:9px 10px;border-bottom:1px solid var(--line);vertical-align:top}}th{{color:#536775;background:#f7f9fa}}.mono{{font:12px/1.45 ui-monospace,SFMono-Regular,monospace;overflow-wrap:anywhere;color:#455969}}.unknown{{color:var(--unknown);font-weight:800}}.callout{{background:#fff7e4;border-left:4px solid #e3aa2e;padding:11px 14px;border-radius:5px}}.grid-scroll{{overflow-x:auto}}footer{{color:var(--muted);font-size:13px;padding:12px 3px 26px}}@media(max-width:760px){{main{{padding:12px}}.card{{grid-template-columns:1fr;padding:16px}}.overview{{height:300px}}}}
</style></head><body><main>
<header><span class="status">REVIEW EVIDENCE READY</span><p class="eyebrow">PINNED G22 EXAMPLE · SOURCE-BOUND GEOMETRY · UNKNOWN PRESERVED</p><h1>Reference and Region Profile</h1><p class="lead">One family view, then one measured card per confirmed member. This answers what geometry is present and what context is actually evidenced; it does not choose a copper treatment.</p><p>Family spacing: three members, pairwise center distances {', '.join(fmt(x,3) for x in family_center_distance)} mm. Separate physical-contact groups: 22, 18 and 10 source objects.</p><div class="legend"><span><i style="background:#28a7b8"></i>seed circle</span><span><i style="background:#ed6a36"></i>attached trace</span><span><i style="background:#ffcc57"></i>F.Mask geometric candidate</span><span><i style="background:#dc9fff"></i>F.Paste geometric candidate</span><span><i style="background:#dce8ee"></i>nearby geometry</span></div></header>
<section class="summary"><h2>One family view</h2><p>All geometry is drawn in the pinned ORG board coordinate frame. Reference outlines coincide with each seed in the stored representation; the two outlines are intentionally not displaced for readability.</p>{_svg([x0,y0,x1,y1],overview_paths,class_name='overview',height=340)}<div class="grid-scroll"><table><thead><tr><th>Member</th><th>Center X,Y (mm)</th><th>Diameter (mm)</th><th>Separate F.Cu group</th><th>Support / bend / electrical</th></tr></thead><tbody>{summary}</tbody></table></div><p><a href="README.md">Detailed report</a> · <a href="profile.json">Machine-readable measurements</a></p></section>
{''.join(sections)}
<footer>Source revision {esc(profile['binding']['org_revision'])} · ORG SHA-256 {esc(profile['binding']['org_source_sha256'])} · dataset seal {esc(profile['source_material_integrity']['dataset_sha256_manifest']['status'])} ({esc(', '.join(profile['source_material_integrity']['dataset_sha256_manifest']['failed_paths']))}). Measurements are on stored polygonal WKB with stated parser error. This sheet is read-only and makes no engineering or manufacturing claim.</footer>
</main></body></html>'''


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    profile = build_profile(ROOT)
    json_path = OUT / "profile.json"
    md_path = OUT / "README.md"
    html_path = OUT / "index.html"
    json_path.write_text(json.dumps(profile, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(_report(profile), encoding="utf-8")
    html_path.write_text(_html(profile), encoding="utf-8")
    manifest = []
    for path in (json_path, md_path, html_path):
        manifest.append(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}")
    (OUT / "SHA256SUMS").write_text("\n".join(manifest) + "\n", encoding="utf-8")
    print(json.dumps({"status": profile["status"], "output": str(OUT), "members": len(profile["family"]["members"]),
                      "groups": [member["physical_contact_group"]["count"] for member in profile["family"]["members"]],
                      "context": profile["region_context_summary"],
                      "dataset_manifest": profile["source_material_integrity"]["dataset_sha256_manifest"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
