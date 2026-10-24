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
    parser.add_argument('--round-priority-promotion',action='store_true')
    parser.add_argument('--apply-owner-review',action='store_true')
    args=parser.parse_args()
    if args.apply_owner_review and args.round_priority_promotion:parser.error('Select only one trial policy')
    name='crop_round_priority_promotion_t01_policy.json' if args.round_priority_promotion else 'crop_diameter_classes_t01_policy.json'
    expected='b74681cec401ba54ca2e92fc0dc6d265a1373d21892be0e200993f7ca44d47be' if args.round_priority_promotion else POLICY_SHA
    if args.apply_owner_review:
        name='crop_owner_review_t01_policy.json';expected='1b084cb2366a08e356841ebe5b8890248ba0f75656280e174dee23af1f1fcf5f'
    main(args.output,policy_path=ROOT/'contracts'/name,policy_sha=expected)
