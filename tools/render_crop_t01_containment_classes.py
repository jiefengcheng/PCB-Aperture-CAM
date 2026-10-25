#!/usr/bin/env python3
"""Render ORG and T01 with per-circle containment classes highlighted."""
import csv
import hashlib
import json
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, __version__ as pillow_version


out = Path(sys.argv[1]).resolve()
report = json.loads((out / "report.json").read_text())
original = json.loads((out / "original_crop_rings.json").read_text())
after = json.loads((out / "t01_multicircle_crop_rings.json").read_text())
additions = json.loads((out / "t01_additions_crop_rings.json").read_text())
assert original["bounds_mm"] == after["bounds_mm"] == additions["bounds_mm"]
x0, y0, x1, y1 = original["bounds_mm"]
width = 1800
scale = width / (x1 - x0)
height = round((y1 - y0) * scale)
classes = {
    "KEEP_CIRCLE_CONTAINED_IN_OTHER_SOURCE_SHAPE": ("contained", "#ffd166"),
    "KEEP_CIRCLE_CONTAINMENT_UNCERTAIN": ("uncertain", "#ff9f43"),
}


def paint(data, fill, image):
    draw = ImageDraw.Draw(image)
    for polygon in data["polygons"]:
        draw.polygon([((x - x0) * scale, (y1 - y) * scale)
                      for x, y, *_ in polygon["exterior"]], fill=fill)
        for ring in polygon["interiors"]:
            draw.polygon([((x - x0) * scale, (y1 - y) * scale) for x, y in ring], fill="#071522")


before = Image.new("RGB", (width, height), "#071522")
paint(original, "#e9485b", before)
after_image = Image.new("RGB", (width, height), "#071522")
paint(after, "#e9485b", after_image)
paint(additions, "#35d4b7", after_image)

font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 19)
label_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 12)
classification = []
for decision in report["decisions"]:
    key = decision["key"]
    class_name, color = classes.get(decision["decision"], ("eligible", "#65c8ff"))
    px = lambda x, y: ((x - x0) * scale, (y1 - y) * scale)
    cx, cy = decision["center"]
    radius = decision["source_radius_mm"]
    # Presentation outline sampled at the same 128 segments per quadrant as
    # the saved source circle buffer; saved WKB remains the geometry authority.
    coords = [px(cx + radius * math.cos(2 * math.pi * n / 512),
                 cy + radius * math.sin(2 * math.pi * n / 512)) for n in range(513)]
    for image in (before, after_image):
        draw = ImageDraw.Draw(image)
        draw.line(coords, fill=color, width=3, joint="curve")
        if class_name != "eligible":
            cx, cy = px(*decision["center"])
            label = key
            draw.rounded_rectangle((cx - 15, cy - 9, cx + 15, cy + 9), radius=4, fill="#071522")
            draw.text((cx - 13, cy - 7), label, font=label_font, fill=color)
    classification.append({
        "key": key,
        "source_id": decision["source_id"],
        "class": class_name,
        "decision": decision["decision"],
        "center_x_mm": decision["center"][0],
        "center_y_mm": decision["center"][1],
        "container_or_near_boundary_source_ids": ";".join(
            item["source_id"] for item in
            decision.get("containing_source_objects", decision.get("near_boundary_source_objects", [])))
    })

panel_w = 1050
panel_h = round(height * panel_w / width)
canvas = Image.new("RGB", (2 * panel_w + 60, panel_h + 190), "#f2f6f9")
draw = ImageDraw.Draw(canvas)
for index, (image, title) in enumerate([
    (before, "ORG · circles classified before grouping"),
    (after_image, "T01 candidate · teal additions, same circle classes"),
]):
    x = 20 + index * (panel_w + 20)
    draw.text((x, 14), title, font=font, fill="#152d43")
    canvas.paste(image.resize((panel_w, panel_h), Image.Resampling.LANCZOS), (x, 46))

counts = {name: sum(item["class"] == name for item in classification)
          for name in ["contained", "uncertain", "eligible"]}
legend_y = panel_h + 58
legend = [("#ffd166", f"Fully covered by another ORG primitive: {counts['contained']} (held unchanged)"),
          ("#ff9f43", f"Near-boundary uncertainty: {counts['uncertain']} (held unchanged)"),
          ("#65c8ff", f"Eligible after exclusion: {counts['eligible']} (22 singleton, 18 in 6 groups)")]
for i, (color, label) in enumerate(legend):
    y = legend_y + i * 28
    draw.ellipse((28, y + 5, 44, y + 21), outline=color, width=4)
    draw.text((54, y), label, font=font, fill="#152d43")
canvas.save(out / "containment_classification_review.png")

with (out / "containment_classification.csv").open("w", newline="") as stream:
    writer = csv.DictWriter(stream, fieldnames=classification[0].keys())
    writer.writeheader()
    writer.writerows(classification)

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

receipt = {"status": "PRESENTATION_ONLY", "pillow_version": pillow_version,
           "source_sha256": report["source_sha256"], "policy_sha256": report["policy_sha256"],
           "bounds_mm": original["bounds_mm"], "counts": counts,
           "image_sha256": sha(out / "containment_classification_review.png"),
           "classification_csv_sha256": sha(out / "containment_classification.csv"),
           "note": "Outlines classify source circles; they do not assert electrical identities or manufacturing validity."}
(out / "containment_classification_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
print(json.dumps(receipt, indent=2))
