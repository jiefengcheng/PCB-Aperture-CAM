#!/usr/bin/env python3
"""Run the local CAM Agent ABI JSON adapter."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.agent_abi.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
