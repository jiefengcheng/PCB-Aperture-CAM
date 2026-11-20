"""Durable child of the retained native parallel catalogue; no parent edits."""
from pathlib import Path
from src.stage_abi.store import canonical,digest
from . import arc_membership as arcs
from .durable_groups import retain


def prepare(directory,straight,curves,parent_binding):
    signature=b''.join(p.read_bytes()for p in(Path(__file__),Path(arcs.__file__),Path(__file__).with_name('_curve_catalogue.py')))
    key=dict(schema='t04-durable-maximal-arc-catalogue/1',parent_binding=parent_binding,
             algorithm_sha256=digest(signature),straight_sha256=digest(canonical(straight)),
             curves_sha256=digest(canonical(curves)),noise_fraction=.01,minimum_shared_mm=.05)
    return retain(directory,key,'ARC_CATALOGUE.json.gz',lambda:arcs.catalogue(straight,curves))
