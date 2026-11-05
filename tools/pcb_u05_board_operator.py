#!/usr/bin/env python3
"""Local Code U05: explicit retained U04, same native machine audits as Terminal."""
import argparse,json,sys
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools import u05_app

def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=('start','status'));p.add_argument('--u04-job',type=Path);p.add_argument('--reference',type=Path);p.add_argument('--request-id');a=p.parse_args()
    try:
        if a.action=='start':
            if a.u04_job is None or a.request_id:raise ValueError('U05_EXPLICIT_U04_JOB_REQUIRED')
            result=u05_app.start(a.u04_job,a.reference)
        else:
            if not a.request_id or a.u04_job is not None or a.reference is not None:raise ValueError('U05_STATUS_REQUEST_ID_ONLY')
            result=u05_app.status(a.request_id)
        print(json.dumps(result,sort_keys=True));return 2 if result['status']=='HALTED' else 0
    except Exception as error:
        print(json.dumps(dict(status='HALTED',error=str(error),owner='PENDING_USER',rendering='NOT_REQUESTED',next_action='REPORT_AND_STOP; no automatic retry'),sort_keys=True));return 2
if __name__=='__main__':raise SystemExit(main())
