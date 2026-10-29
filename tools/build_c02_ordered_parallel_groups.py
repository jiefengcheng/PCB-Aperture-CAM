#!/usr/bin/env python3
"""Parallel cohort selection independent of native primitive fragmentation."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools.build_c02_parallel_membership_v2 import main

if __name__=='__main__':main(pathwise=True)
