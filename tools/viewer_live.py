#!/usr/bin/env python3
"""Wire completed T04 slices to the viewer file ABI, without changing engineering files."""
from pathlib import Path
import argparse
import fcntl
import json
import os
import sys
import time
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.pcb_workspace import prepare, require_storage, WORK
from src.viewer_abi import live
from src.viewer_abi.publisher import encode, atomic_write


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--connection', required=True, help='Absolute viewer-only connection directory under LaCie work')
    sub = parser.add_subparsers(dest='command', required=True)
    init = sub.add_parser('init')
    for name in ['template', 'legacy', 'construction', 'thread']:
        init.add_argument('--'+name, required=True)
    event = sub.add_parser('complete', help='Seal explicit completion after both artifacts are finalized')
    event.add_argument('--label', required=True); event.add_argument('--report', required=True)
    group = event.add_mutually_exclusive_group(required=True)
    group.add_argument('--shapes'); group.add_argument('--construction')
    event.add_argument('--display-status', choices=['Preview', 'Failed'], default='Preview')
    sub.add_parser('status'); sub.add_parser('once'); sub.add_parser('start')
    feed = sub.add_parser('attach-benchmark')
    for name in ['log', 'qualification', 'script']:
        feed.add_argument('--'+name, required=True)
    watch = sub.add_parser('watch'); watch.add_argument('--interval', type=float, default=1.)
    args = parser.parse_args()
    prepare()
    root = Path(args.connection).resolve()
    if root == WORK.resolve() or not root.is_relative_to(WORK.resolve()):
        raise ValueError('LIVE_CONNECTION_MUST_USE_LACIE_WORK')
    if args.command == 'init':
        print(json.dumps(live.initialize(root, template=args.template, legacy=args.legacy,
                                        construction=args.construction, thread=args.thread), indent=2))
    elif args.command == 'attach-benchmark':
        print(json.dumps(live.attach_benchmark(root, log=args.log, qualification=args.qualification, script=args.script), indent=2))
    elif args.command == 'complete':
        event = live.enqueue(root, label=args.label, report=args.report, shapes=args.shapes,
                             construction=args.construction, display_status=args.display_status)
        print(json.dumps(dict(status='QUEUED_COMPLETED_SLICE', event=event, selection=live.feedback(root)), indent=2))
    elif args.command == 'status':
        config = live.load_connection(root)
        manifest = json.loads((root / 'session/current.json').read_bytes())
        state = json.loads((root / 'receipts' / (manifest['sha256']+'.state.json')).read_bytes())
        receipts = [json.loads(p.read_bytes()) for p in (root / 'receipts').glob('*.json') if not p.name.endswith('.state.json')]
        heartbeat = root / 'watcher.json'
        display_path = root / 'session/outbox/display.json'
        display = json.loads(display_path.read_bytes()) if display_path.exists() else None
        print(json.dumps(dict(connection=config, revision=state['revision'], last_event=state['event'],
                              display=display, display_current=bool(display and display.get('payloadSHA256') == manifest['sha256']),
                              watcher=json.loads(heartbeat.read_bytes()) if heartbeat.exists() else None,
                              events=receipts[-5:], selection=live.feedback(root)), indent=2))
    elif args.command == 'start':
        import subprocess
        with (root / 'watcher.lock').open('a') as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                print(json.dumps(dict(status='ALREADY_RUNNING', watcher=str(root / 'watcher.json'))))
                return
        log_path = root / ('watcher-' + str(time.time_ns()) + '.log')
        with log_path.open('xb') as log:
            child = subprocess.Popen([sys.executable, '-B', str(Path(__file__).resolve()), '--connection', str(root), 'watch'],
                                     stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
        for _ in range(30):
            if child.poll() is not None:
                raise RuntimeError('LIVE_WATCHER_START_FAILED:' + str(log_path))
            heartbeat = root / 'watcher.json'
            if heartbeat.exists() and json.loads(heartbeat.read_bytes()).get('pid') == child.pid:
                print(json.dumps(dict(status=json.loads(heartbeat.read_bytes()).get('status', 'WATCHING'), pid=child.pid, log=str(log_path))))
                return
            time.sleep(.1)
        raise RuntimeError('LIVE_WATCHER_START_NOT_CONFIRMED:' + str(log_path))
    else:
        # The OS lock releases on exit; a second watcher cannot publish concurrently.
        with (root / 'watcher.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            require_storage()
            atomic_write(root / 'watcher.json', encode(dict(pid=os.getpid(), status='STARTING', last_tick_ns=time.time_ns(), results=[])))
            while True:
                require_storage()
                results = live.tick(root)
                atomic_write(root / 'watcher.json', encode(dict(pid=os.getpid(), status='WATCHING', last_tick_ns=time.time_ns(), results=results)))
                if results:
                    print(json.dumps(results), flush=True)
                if args.command == 'once':
                    break
                if not .2 <= args.interval <= 60:
                    raise ValueError('LIVE_INTERVAL_OUT_OF_RANGE')
                time.sleep(args.interval)


if __name__ == '__main__':
    main()
