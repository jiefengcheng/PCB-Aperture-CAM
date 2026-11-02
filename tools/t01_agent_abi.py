#!/usr/bin/env python3
"""Dedicated T01 English-contract interaction ABI; no later-stage execution."""
from pathlib import Path
import sys
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.t01_abi.cli import main
if __name__=='__main__':raise SystemExit(main())
