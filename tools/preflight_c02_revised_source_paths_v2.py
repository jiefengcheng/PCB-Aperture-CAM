#!/usr/bin/env python3
"""Exact-source no-growth identity check, preserving the original raw verifier."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.prepared_width_scene import PreparedWidthScene
from tools.preflight_c02_revised_source_paths import main


def check(traces,fixed):return PreparedWidthScene(traces,fixed).check(traces,materialize_scene=True)


if __name__=='__main__':main(check)
