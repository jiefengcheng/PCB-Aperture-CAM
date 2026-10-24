#!/usr/bin/env python3
"""Presentation-only raster rendering using the system Pillow installation."""
import hashlib
import json
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, __version__ as pillow_version

out = Path(sys.argv[1]).resolve()
original = json.loads((out / "original_crop_rings.json").read_text())
after = json.loads((out / "t01_multicircle_crop_rings.json").read_text())
additions = json.loads((out / "t01_additions_crop_rings.json").read_text())
assert original["bounds_mm"] == after["bounds_mm"] == additions["bounds_mm"]
x0, y0, x1, y1 = original["bounds_mm"]
width = 1800
scale = width / (x1 - x0)
height = round((y1 - y0) * scale)


def paint(data, fill, image):
    draw = ImageDraw.Draw(image)
    for polygon in data["polygons"]:
        draw.polygon([((x - x0) * scale, (y1 - y) * scale)
                      for x, y in polygon["exterior"]], fill=fill)
        for ring in polygon["interiors"]:
            draw.polygon([((x - x0) * scale, (y1 - y) * scale)
                          for x, y in ring], fill="#071522")


before_image = Image.new("RGB", (width, height), "#071522")
paint(original, "#e9485b", before_image)
before_image.save(out / "before_t01.png")
after_image = Image.new("RGB", (width, height), "#071522")
paint(after, "#e9485b", after_image)
paint(additions, "#35d4b7", after_image)
after_image.save(out / "after_t01.png")

panel_w = 1050
panel_h = round(height * panel_w / width)
font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 30)
review = Image.new("RGB", (2 * panel_w + 60, panel_h + 105), "#f2f6f9")
draw = ImageDraw.Draw(review)
for index, (image, label) in enumerate([
    (before_image, "ORG · before T01"),
    (after_image, "T01 candidate · teal shows additions")
]):
    thumb = image.resize((panel_w, panel_h), Image.Resampling.LANCZOS)
    x = 20 + index * (panel_w + 20)
    draw.text((x, 18), label, font=font, fill="#152d43")
    review.paste(thumb, (x, 70))
review.save(out / "t01_crop_review.png")

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

receipt = {"pillow_version": pillow_version, "presentation_only": True,
           "bounds_mm": original["bounds_mm"], "pixel_size": [width, height],
           "same_frame": True,
           "input_sha256": {name: sha(out / f"{name}_rings.json") for name in
                            ["original_crop", "t01_multicircle_crop", "t01_additions_crop"]},
           "after_render_order": ["all T01 copper", "teal T01 additions overlay"]}
(out / "render_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
print(json.dumps(receipt, indent=2))
