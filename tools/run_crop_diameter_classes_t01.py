#!/usr/bin/env python3
"""Run the separate shared-diameter follow-up; preserve previous trial bundles."""
import argparse,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.run_crop_balanced_t01 import main
POLICY_SHA='c5605b67986dfb64a7cf1cf8400aa624547231e73145af0ea39e7fa1b9731397'
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    main(parser.parse_args().output,policy_path=ROOT/'contracts/crop_diameter_classes_t01_policy.json',policy_sha=POLICY_SHA)
