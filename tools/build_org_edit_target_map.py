#!/usr/bin/env python3
"""Build the frozen three-member ORG→EDIT target-map review bundle."""
from __future__ import annotations

import argparse
import hashlib
import html
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.org_edit_target_map import build_target_map


def _fmt(value, digits=6):
    if value is None:
        return "Not established"
    return f"{value:.{digits}f}"


def _summary_row(member):
    seed = member["seed"]
    local = member["local_copper_region"]
    traces = member["trace_correspondence"]
    trace_links = sum(len(v) for v in traces["by_org_trace"].values())
    refs = ", ".join(f"{r['layer']}: {r['status']}" for r in member["reference_correspondence"])
    circle = seed["edit_candidates"]
    after_radius = (" · ".join(f"r={c['radius_mm']:.5f} mm" for c in circle)
                    if circle else "no registered circle candidate")
    return f"""<tr><th>Member {member['ordinal']}<small>center {member['center_org_mm'][0]:.3f}, {member['center_org_mm'][1]:.3f} mm</small></th>
<td><b>{seed['edit_status']}</b><small>{html.escape(after_radius)}</small></td>
<td><b>{trace_links} trace candidate edge(s)</b><small>Widths and coverage stay per source trace below.</small></td>
<td>{html.escape(refs)}</td>
<td><b>{local['status']}</b><small>+{local['added_area_mm2']:.6f} / −{local['removed_area_mm2']:.6f} mm² within this fixed local window.</small></td></tr>"""


def _detail(member):
    seed = member["seed"]
    local = member["local_copper_region"]
    lines = []
    for identity, edges in member["trace_correspondence"]["by_org_trace"].items():
        if not edges:
            lines.append(f"<li><code>{html.escape(identity)}</code>: no candidate under the centerline rule. No deletion inference.</li>")
        else:
            for edge in edges:
                org_at = edge["before_width_sample_centerline_midpoint_mm"]
                edit_at = edge["after_width_sample_centerline_midpoint_mm"]
                lines.append(f"<li><code>{html.escape(identity)}</code> → <code>{html.escape(edge['after_identity'])}</code>; width {edge['before_width_mm']:.5f} → {edge['after_width_mm']:.5f} mm (Δ {edge['width_delta_mm']:+.5f}); midpoint samples ORG ({org_at[0]:.6f}, {org_at[1]:.6f}) and EDIT ({edit_at[0]:.6f}, {edit_at[1]:.6f}) mm; width is uniform per primitive. Coverage ORG {edge['before_covered_fraction']:.1%}, EDIT {edge['after_covered_fraction']:.1%}. This is a partial/overlap candidate, not a semantic identity.</li>")
    circles = []
    for c in seed["edit_candidates"]:
        circles.append(f"<li><code>{html.escape(c['identity'])}</code> center ({c['center_mm'][0]:.5f}, {c['center_mm'][1]:.5f}) mm; r {c['radius_mm']:.5f} mm; Δr {c.get('radius_delta_mm', 0):+.5f} mm.</li>")
    refs = []
    for ref in member["reference_correspondence"]:
        rows = "".join(f"<li><code>{html.escape(c['identity'])}</code>; center residual {c['center_displacement_mm']:.6f} mm; boundary Hausdorff {c['boundary_hausdorff_distance_mm']:.6g} mm; symmetric difference {c['symmetric_difference_area_mm2']:.8f} mm².</li>" for c in ref["candidates"])
        if not rows:
            rows = f"<li>No same-kind/layer registered center candidate found. ORG identity <code>{html.escape(ref['org_identity'])}</code>.</li>"
        refs.append(f"<li>{html.escape(ref['layer'] or 'reference')}: <b>{ref['status']}</b><ul>{rows}</ul></li>")
    unsupported = "".join(f"<li><code>{html.escape(x['identity'])}</code> ({html.escape(x['kind'])}): {html.escape(x.get('reason') or 'unsupported')}; source points fall in this crop. Affected complete-region area is not established.</li>" for x in local["unsupported_edit"] + local["unsupported_org"])
    if not unsupported:
        unsupported = "<li>None located in this crop by the source inventory.</li>"
    return f"""<section class="member-detail" id="member-{member['ordinal']}">
<h2>Member {member['ordinal']} · source-grounded detail</h2>
<object class="review-svg" type="image/svg+xml" data="member-{member['ordinal']}.svg" aria-label="Member {member['ordinal']} ORG EDIT and delta comparison"></object>
<div class="columns"><article><h3>Copper seed</h3><p>ORG <code>{html.escape(seed['org_identity'])}</code>, radius {seed['org']['radius_mm']:.5f} mm. EDIT status: <b>{seed['edit_status']}</b>.</p><ul>{''.join(circles) if circles else '<li>No supported circle candidate under the registered-center rule.</li>'}</ul><p>Circle matching uses center only (0.001 mm); radius is measured after matching. A candidate is not a confirmed pad/terminal identity.</p></article>
<article><h3>Reference geometry</h3><ul>{''.join(refs)}</ul><p>These are layer-specific geometric candidates; matching layer names do not establish process role or fixed/editable status.</p></article>
<article><h3>Geometric contact groups</h3><p>ORG seed belongs to the profiled {member['physical_contact_group']['org']['count']}-object transitive F.Cu intersection component. EDIT has {', '.join(str(c.get('object_count',0)) + ' supported local object(s)' for c in member['physical_contact_group']['edit_supported_local_components']) or 'no located supported component'} around the listed circle candidate(s). The group-to-group relation remains <b>{member['physical_contact_group']['group_correspondence_status']}</b>. These are geometric intersections, not electrical nets.</p><details><summary>Show ORG component source identities</summary><ul>{''.join(f"<li><code>{html.escape(identity)}</code></li>" for identity in member['physical_contact_group']['org']['source_member_ids'])}</ul></details><p>Full EDIT component source identities are in <a href="target_map.json">target_map.json</a>.</p></article>
<article><h3>Attached traces</h3><ul>{''.join(lines)}</ul><p>{html.escape(member['trace_correspondence']['rule'])}</p></article>
<article><h3>Same-window copper union</h3><p>Status: <b>{local['status']}</b>. Supported ORG union {local['org_union_area_mm2']:.6f} mm²; EDIT union {local['edit_union_area_mm2']:.6f} mm²; added {local['added_area_mm2']:.6f} mm²; removed {local['removed_area_mm2']:.6f} mm². This is the union clipped to identical window bounds, so overlaps are counted once.</p><p>Complete-window support: {html.escape(local['status'])}. Violet markers identify unsupported EDIT source control points.</p><ul>{unsupported}</ul></article>
<article><h3>Observed contact and neighborhood gaps</h3><p>For ORG, the profile's nearest external seed gaps are retained as a candidate set. For EDIT, the bundle measures the nearest nonintersecting supported feature from each candidate circle; it does not assert that the nearest EDIT feature is the same source object as the ORG neighbor. Delta below compares nearest-distance statistics only, not matched neighbor identities.</p><ul>{''.join(f"<li>ORG {html.escape(n['kind'] or 'object')} <code>{html.escape(n['identity'] or '')}</code>: {n['gap_mm']:.6f} mm</li>" for n in member['neighbor_gaps']['org_profile_nearest_external_from_seed'])}{''.join(f"<li>EDIT circle <code>{html.escape(n['seed_identity'])}</code>: {html.escape(n['status'])}; {n.get('nearest_gap_mm',0):.6f} mm; nearest-statistic Δ {n.get('delta_from_org_nearest_distance_statistic_mm',0):+.6f} mm; completeness {html.escape(n['completeness'])}; candidate(s): {', '.join(html.escape(x['identity']) for x in n.get('neighbors_within_tie_tolerance',[]))}</li>" for n in member['neighbor_gaps']['edit_nearest_nonintersecting_from_each_circle_candidate'])}</ul><p>ORG/EDIT seed-to-trace contact is represented by measured intersection area and boundary gap below; geometric contact does not prove electrical continuity.</p><ul>{''.join(f"<li>ORG trace <code>{html.escape(c['org_trace_identity'])}</code>: intersection {c['org_intersection_area_mm2']:.8f} mm², centroid {c['org_contact_centroid_mm']}, gap {c['org_boundary_gap_mm']:.6f} mm. EDIT candidate relation: {html.escape(c['edit_status'])}; {len(c['edit_candidates'])} mapped pair(s); EDIT contact observations {', '.join(str(e['contact_centroid_mm']) for e in c['edit_candidates']) or 'not established'}.</li>" for c in member['seed_trace_contact'])}</ul></article></div></section>"""


def build(output: Path):
    data = build_target_map(ROOT)
    output.mkdir(parents=True, exist_ok=True)
    for member in data["members"]:
        svg = member.pop("_svg")
        (output / f"member-{member['ordinal']}.svg").write_text(svg)
    (output / "target_map.json").write_text(json.dumps(data, indent=2) + "\n")
    rows = "".join(_summary_row(m) for m in data["members"])
    details = "".join(_detail(m) for m in data["members"])
    integrity = data["package_integrity"]
    failed_inventory_paths = ", ".join(integrity["failed_paths"]) or "none"
    page = f"""<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>One-family ORG → EDIT target map</title>
<style>
:root{{font:16px/1.55 system-ui,-apple-system,sans-serif;color:#24323b;background:#f3f6f7}}body{{margin:0}}main{{max-width:1440px;margin:auto;padding:28px}}h1{{font-size:2rem;margin:0 0 8px}}.lead{{font-size:1.1rem;max-width:1000px}}.badge{{display:inline-block;background:#fff0cf;color:#76530c;border-radius:6px;padding:5px 10px;font-weight:700}}.card{{background:#fff;border:1px solid #d3dde1;border-radius:12px;padding:20px;margin:18px 0}}table{{border-collapse:collapse;width:100%;overflow:auto}}th,td{{border-bottom:1px solid #e1e7e9;padding:12px;text-align:left;vertical-align:top}}th small,td small{{display:block;color:#66767e;margin-top:4px}}.scroll{{overflow:auto}}code{{font-size:.85em;overflow-wrap:anywhere}}.member-nav{{position:sticky;top:0;background:#f3f6f7;padding:10px 0;z-index:1}}.member-nav button{{margin-right:8px;padding:8px 14px;border:1px solid #bdcbd0;border-radius:8px;background:white;cursor:pointer}}.member-detail{{scroll-margin-top:60px}}.review-svg{{width:100%;height:620px;border:1px solid #d3dde1;border-radius:9px;background:white}}.columns{{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:14px}}.columns article{{background:#f9fbfb;border:1px solid #e1e7e9;border-radius:9px;padding:14px}}.foot{{color:#64757d;font-size:.9rem}}summary{{cursor:pointer;font-weight:700}}@media(max-width:700px){{main{{padding:14px}}.review-svg{{height:440px}}}}
</style><main><header class="card"><h1>One-family ORG → EDIT target map</h1><p class="lead">ORG defines the three reviewed members. EDIT is the measured observed destination, registered using F.Mask geometry alone. This sheet records correspondences, local differences, and unresolved alternatives; it does not infer an editing recipe or engineering purpose.</p><p><span class="badge">Package integrity {integrity['status']} · {html.escape(failed_inventory_paths)}</span></p><p>Current package check compared with profile record: {integrity['checked_count']} listed files; previous profile listed {integrity.get('profile_recorded_checked_count', integrity['checked_count'])}. Profile-record discrepancy: {integrity['differs_from_profile_record']}.</p><p>Family <code>{data['family_key']}</code> · ORG <code>{data['sources']['ORG']['sha256']}</code> · EDIT <code>{data['sources']['EDIT']['sha256']}</code></p><p>Registration: identity transform, F.Mask-only descriptor fit; 219 mutual-unique inliers / 386 ORG and 331 EDIT anchors; 0.001 mm tolerance. No F.Cu geometry fitted the transform. The shared crop is X ±0.300 mm and Y ±0.420 mm around each frozen ORG member coordinate.</p></header>
<section class="card"><h2>What repeats across the three sites</h2><p>{html.escape(data['observed_pattern']['seed_circles'])}</p><p>{html.escape(data['observed_pattern']['reference_geometry'])}</p><p>{html.escape(data['observed_pattern']['traces'])}</p><p>{html.escape(data['observed_pattern']['local_regions'])}</p><p><b>{html.escape(data['observed_pattern']['interpretation'])}</b></p></section>
<section class="card"><h2>Three-member result</h2><div class="scroll"><table><thead><tr><th>Member</th><th>Seed circle</th><th>Attached traces</th><th>Reference candidates</th><th>Local copper union</th></tr></thead><tbody>{rows}</tbody></table></div></section>
<nav class="member-nav">Jump to: <button onclick="document.getElementById('member-1').scrollIntoView()">Member A</button><button onclick="document.getElementById('member-2').scrollIntoView()">Member B</button><button onclick="document.getElementById('member-3').scrollIntoView()">Member C</button></nav>
{details}
<section class="card"><h2>Scope and review limits</h2><ul>{''.join(f'<li>{html.escape(x)}</li>' for x in data['limits'])}<li>Current package inventory status is {integrity['status']}; failing paths: {html.escape(failed_inventory_paths)}. The prior profile record differs: {integrity['differs_from_profile_record']}. Inputs were not changed.</li><li>The local window totals describe supported native geometry only. Any unsupported source geometry listed above makes full-window totals NOT_ESTABLISHED.</li><li>Observed contact/intersection is geometric only; no electrical connectivity or net intent is established.</li></ul><p><a href="target_map.json">Machine-readable evidence</a> · <a href="README.md">Audit notes and reproduction</a></p></section></main></html>"""
    (output / "index.html").write_text(page)
    return data


def _readme(data):
    return f"""# One-family ORG → EDIT target map

This bundle compares only the frozen three-member family `{data['family_key']}`. Recognition was not rerun; the selected member keys and source bytes are hash-bound in `target_map.json`.

Open `index.html` to review all members, matched/ambiguous candidates, exact source-byte-span identities, fixed-window overlays, and source-supported measurements. `member-N.svg` uses the same ORG coordinate window for ORG, registered EDIT, and local EDIT-minus-ORG panes. Green is added copper, red is removed copper, and violet marks unsupported local source primitives.

## Evidence and limits

- F.Mask-only registration: `out/ingestion/audits/20261023_registered_copper_correspondence_v1/evidence/registration.json`; rigid fit, scale fixed, 219 mutual-unique anchors, 0.001 mm tolerance. The current fit is identity, but it is applied as a recorded transform.
- Native inventories are recomputed from the two sealed board files by `native-inventory/2`; every row identity must bind to the exact source digest and byte span.
- Circle correspondence uses the existing mutual-unique registered-center rule. Radius is excluded from the match key and measured separately; multiple center candidates remain ambiguous.
- Trace candidates use the existing 0.001 mm centerline tolerance, 90% shorter-line coverage, and 0.02 mm minimum overlap. Partial overlap is not semantic identity.
- Copper area is an effective-geometry union clipped to a same-frame fixed window. Source-object areas are not summed. Unsupported local primitives keep full-window area `NOT_ESTABLISHED`.
- F.Mask/F.Paste records are geometric reference candidates only. Identical layer labels do not prove a process role, fixed state, or manufacturing rule.
- The observed family pattern and its qualifications appear in `target_map.json` under `observed_pattern` and at the top of the review page.
- Nine UNKNOWN assessments remain UNKNOWN; the separate G22 crop review remains PENDING_USER. No manufacturing, electrical, or edit-authorization claim is made.
- The package-wide inventory status is rechecked at build time and remains `{data['package_integrity']['status']}`. Current failing paths: `{', '.join(data['package_integrity']['failed_paths'])}`. The frozen profile recorded `{data['package_integrity']['profile_recorded_status']}` with `{', '.join(data['package_integrity']['profile_recorded_failed_paths'])}`; any difference is explicitly reported. Inputs are not changed.

## Reproduction

```sh
.venv/bin/python tools/build_org_edit_target_map.py
.venv/bin/python -m unittest tests.test_org_edit_target_map -v
```

Bundle source: `{data['sources']['ORG']['path']}` (`{data['sources']['ORG']['sha256']}`) and `{data['sources']['EDIT']['path']}` (`{data['sources']['EDIT']['sha256']}`). The profile and registration evidence hashes are listed in `target_map.json`.
"""


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "out/ingestion/audits/20261024_g22_org_edit_target_map_v1")
    args = parser.parse_args(argv)
    data = build(args.output)
    (args.output / "README.md").write_text(_readme(data))
    entries = []
    for path in sorted(args.output.iterdir()):
        if path.is_file() and path.name != "SHA256SUMS":
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            entries.append(f"{digest}  {path.name}")
    (args.output / "SHA256SUMS").write_text("\n".join(entries) + "\n")
    print(f"Wrote target-map review bundle: {args.output}")
    print("Members:", ", ".join(m["member_key"][:12] for m in data["members"]))
    print("Status:", data["status"], "package integrity:", data["package_integrity"]["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
