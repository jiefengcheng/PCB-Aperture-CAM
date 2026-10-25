#!/usr/bin/env python3
"""Render provisional ORG rectangle targets on the fixed source crop."""
from __future__ import annotations

import csv
import base64
import json
from pathlib import Path
import sys

from shapely import wkb

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.native_inventory import inventory


def main():
    out = ROOT / "out/crop_dynamic_tasks/t02_rectangle_candidates_review_20261025"
    out.mkdir(parents=True, exist_ok=True)
    source = ROOT / "dataset/szu-comm_3020301113B_intake_ready_20261021_v2/raw/ORG/top.kicad_pcb"
    bounds = [16.44342222222222, -16.556731666666664, 27.198977777777777, -8.645620555555553]
    dispositions_path = ROOT / "out/crop_dynamic_tasks/t02_org_inventory_20261025/feature_dispositions.json"
    table = json.loads(dispositions_path.read_text())
    rows = [x for x in table["dispositions"] if x["disposition"] == "TREAT"]
    rows.sort(key=lambda x: (x["bounds_mm"][1], x["bounds_mm"][0], x["source_id"]))
    raw = source.read_bytes()
    inv = inventory(raw)
    image_path = ROOT / "out/crop_dynamic_tasks/t02_crop_registration_20261024/org_before.png"
    import struct
    png_data = image_path.read_bytes()
    w, h = struct.unpack(">II", png_data[16:24])
    minx, miny, maxx, maxy = bounds

    def xy(x, y):
        return ((x - minx) / (maxx - minx) * w, (maxy - y) / (maxy - miny) * h)

    overlay = []
    mapping = []
    for i, row in enumerate(rows, start=1):
        blob = inv["payloads"].get(row["source_geometry_sha256"])
        if not blob:
            raise SystemExit(f"MISSING_TARGET_GEOMETRY:{row['source_id']}")
        geom = wkb.loads(blob)
        poly = [xy(x, y) for x, y in list(geom.exterior.coords)[:-1]]
        point_string = " ".join(f"{x:.2f},{y:.2f}" for x, y in poly)
        overlay.append(f'<polygon points="{point_string}" fill="#ffc626" fill-opacity="0.30" stroke="#ffe15a" stroke-width="3"/>')
        cx, cy = geom.centroid.x, geom.centroid.y
        px, py = xy(cx, cy)
        label = f"{i:02d}"
        overlay.append(f'<g><circle cx="{px:.2f}" cy="{py:.2f}" r="10" fill="#08182a" fill-opacity="0.94" stroke="white" stroke-width="1.5"/><text x="{px:.2f}" y="{py+3.5:.2f}" text-anchor="middle" font-family="Arial,sans-serif" font-size="9" font-weight="bold" fill="white">{label}</text></g>')
        mapping.append({"review_id": label, "source_id": row["source_id"], "source_span": row["source_span"], "bounds_mm": row["bounds_mm"], "size_mm": row["source_size_mm"]})
    b64 = base64.b64encode(png_data).decode("ascii")
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">',
           f'<image width="{w}" height="{h}" href="data:image/png;base64,{b64}"/>',
           *overlay,
           '<rect x="12" y="12" width="514" height="46" rx="10" fill="#08182a" fill-opacity="0.94" stroke="white" stroke-opacity="0.8"/>',
           '<text x="26" y="42" font-family="Arial,sans-serif" font-size="21" font-weight="bold" fill="white">ORG crop · 81 provisional rectangle targets</text>',
           '</svg>']
    svg_path = out / "org_crop_81_rectangle_targets.svg"
    svg_path.write_text("\n".join(svg) + "\n")
    with (out / "target_id_map.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["review_id", "source_id", "source_span", "bounds_mm", "size_mm"])
        writer.writeheader()
        writer.writerows(mapping)
    (out / "review_note.md").write_text(
        "# ORG crop rectangle candidates\n\n"
        "Yellow outlines and numbered badges show the 81 ORG-derived, filled four-vertex rectangle candidates. "
        "All other source copper is unchanged in the background. The IDs map to exact source spans in `target_id_map.csv`. "
        "These are provisional geometric targets only: the pending full-crop T01 baseline has not been accepted, "
        "so this image does not authorize or depict enlargement.\n"
    )
    print(svg_path)


if __name__ == "__main__":
    main()
