#!/usr/bin/env python3
"""Check the nested verification family at exact original source width only."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.uniform_trace_width_v2 import construct_uniform_width
from tools.preflight_c02_uniform_width import main

if __name__=='__main__':main(construct_uniform_width)
