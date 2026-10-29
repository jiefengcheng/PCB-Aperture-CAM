"""Deterministic cumulative T02+T03 SVG rendering for a trusted C2 PASS."""
from __future__ import annotations

import hashlib
import html
import json
from pathlib import Path
from typing import Any
from zipfile import ZipFile

from shapely import wkb
from shapely.geometry import box


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _rings_path(poly, ox: float, oy: float) -> str:
    parts = []
    for ring in [poly.exterior, *poly.interiors]:
        coords = list(ring.coords)
        if not coords:
            continue
        parts.append("M " + " L ".join(f"{x-ox:.6f} {y-oy:.6f}" for x, y, *_ in coords) + " Z")
    return " ".join(parts)


def _geometry_paths(geometry, ox: float, oy: float):
    if geometry.geom_type == "Polygon":
        yield _rings_path(geometry, ox, oy)
    elif geometry.geom_type in {"MultiPolygon", "GeometryCollection"}:
        for part in geometry.geoms:
            yield from _geometry_paths(part, ox, oy)


def _svg(geometries: dict[str, Any], *, bounds, title: str) -> str:
    minx, miny, maxx, maxy = bounds
    width, height = maxx - minx, maxy - miny
    elements = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="{max(1, round(1600*height/width))}" viewBox="{minx:.6f} {-maxy:.6f} {width:.6f} {height:.6f}">',
        f"<title>{html.escape(title)}</title>",
        f'<rect x="{minx:.6f}" y="{-maxy:.6f}" width="{width:.6f}" height="{height:.6f}" fill="#071522"/>',
        '<g transform="scale(1,-1)" fill="#e9465b" fill-rule="evenodd" stroke="none">',
    ]
    clip = box(minx, miny, maxx, maxy)
    for identity in sorted(geometries):
        geometry = geometries[identity]
        if geometry.is_empty or not geometry.intersects(clip):
            continue
        visible = geometry.intersection(clip)
        for path in _geometry_paths(visible, 0.0, 0.0):
            elements.append(f'<path data-source-id="{html.escape(identity, quote=True)}" d="{path}"/>')
    elements.extend(["</g>", "</svg>"])
    return "".join(elements)


def render_verified_cumulative_scene(
    *,
    archive_path: Path,
    expected_archive_sha256: str,
    expected_source_ids: set[str],
    expected_land_ids: set[str],
    output_directory: Path,
    receipt_bindings: dict[str, Any],
) -> dict[str, Any]:
    """Render archive-provided cumulative geometry after upstream trusted PASS.

    This function still validates archive bytes/member hashes and complete
    source/land partitions. It does not establish engineering acceptance.
    """
    archive_path = Path(archive_path).resolve()
    raw = archive_path.read_bytes()
    if _sha(raw) != expected_archive_sha256:
        raise ValueError("C2_RENDER_ARCHIVE_SHA256_MISMATCH")
    with ZipFile(archive_path) as archive:
        if archive.testzip() is not None:
            raise ValueError("C2_RENDER_ARCHIVE_CRC")
        manifest = json.loads(archive.read("manifest.json"))
        if manifest.get("schema") != "T03_C2_SAVED_GEOMETRY_ARCHIVE_V1":
            raise ValueError("C2_RENDER_ARCHIVE_SCHEMA")
        members = manifest.get("members", {})
        identity_members = manifest.get("identity_members", {})
        source_ids = set(identity_members.get("result/source", {}).values())
        land_ids = set(identity_members.get("result/lands", {}).values())
        if source_ids != expected_source_ids or land_ids != expected_land_ids:
            raise ValueError("C2_RENDER_RESULT_PARTITION_MISMATCH")
        geometries: dict[str, Any] = {}
        for prefix in ("result/source", "result/lands"):
            for key, identity in sorted(identity_members[prefix].items()):
                member = f"{prefix}/{key}.wkb"
                data = archive.read(member)
                if _sha(data) != members.get(member):
                    raise ValueError(f"C2_RENDER_MEMBER_HASH:{member}")
                geometry = wkb.loads(data)
                if geometry.is_empty or not geometry.is_valid:
                    raise ValueError(f"C2_RENDER_GEOMETRY_INVALID:{identity}")
                geometries[identity] = geometry
        copper = wkb.loads(archive.read("candidate/copper.wkb"))

    if copper.is_empty or not copper.is_valid:
        raise ValueError("C2_RENDER_CANDIDATE_COPPER_INVALID")
    total_bounds = None
    local_bounds = copper.bounds
    for geometry in geometries.values():
        if geometry.is_empty:
            continue
        b = geometry.bounds
        if total_bounds is None:
            total_bounds = list(b)
        else:
            total_bounds = [min(total_bounds[0], b[0]), min(total_bounds[1], b[1]), max(total_bounds[2], b[2]), max(total_bounds[3], b[3])]
    if total_bounds is None:
        raise ValueError("C2_RENDER_EMPTY_RESULT")
    margin = 2.0
    detail_bounds = (local_bounds[0]-margin, local_bounds[1]-margin, local_bounds[2]+margin, local_bounds[3]+margin)

    output_directory = Path(output_directory).resolve()
    output_directory.mkdir(parents=True, exist_ok=False)
    full_svg = _svg(geometries, bounds=tuple(total_bounds), title="Cumulative accepted T02 v69 + verified T03 C2 candidate")
    detail_svg = _svg(geometries, bounds=detail_bounds, title="C2 local detail · cumulative T02 v69 + verified T03 candidate")
    (output_directory / "cumulative.svg").write_text(full_svg, encoding="utf-8")
    (output_directory / "c2_detail.svg").write_text(detail_svg, encoding="utf-8")
    page = """<!doctype html><meta charset="utf-8"><title>Cumulative T02 + T03 C2 review</title>
<style>body{font:16px system-ui;margin:24px;background:#eef3f5;color:#162c40}article{background:white;padding:20px;border-radius:16px;margin:16px 0}img{width:100%;height:auto;border:1px solid #afbdca;background:#071522}</style>
<h1>Cumulative T02 v69 + T03 C2 candidate</h1><p>Verified candidate geometry · review visualization only · not engineering or manufacturing acceptance.</p>
<article><h2>C2 local detail</h2><img src="c2_detail.svg"></article><article><h2>Complete source scene</h2><img src="cumulative.svg"></article>"""
    (output_directory / "index.html").write_text(page, encoding="utf-8")
    outputs = {p.name: _sha(p.read_bytes()) for p in sorted(output_directory.iterdir()) if p.is_file()}
    receipt = {
        "schema": "T03_C2_CUMULATIVE_RENDER_RECEIPT_V1",
        "status": "PASS_RENDERED_CUMULATIVE_REVIEW_ARTIFACT",
        "archive_sha256": expected_archive_sha256,
        "render_inputs": receipt_bindings,
        "source_object_count": len(source_ids),
        "accepted_v69_land_count": len(land_ids),
        "bounds_mm": total_bounds,
        "detail_bounds_mm": detail_bounds,
        "outputs_sha256": outputs,
        "qualification": "display derivative of trusted saved candidate; not engineering/manufacturing acceptance",
    }
    receipt_path = output_directory / "render_receipt.json"
    receipt_path.write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    receipt["receipt_sha256"] = _sha(receipt_path.read_bytes())
    return receipt
