"""Loopback-only workbench server with serialized qualified-directory restoration."""
import json
import re
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote,urlsplit,parse_qs
from src.directory_intake import remove_dataset, restore_directory
from src.ingestion_registry import publish
from src.ingestion_verification import verify_publication


def published_config(destination, fallback):
    entry = Path(destination) / 'index.html'
    if not entry.exists():
        return fallback
    match = re.search(r'url=(run-[0-9a-f]{32})/index.html', entry.read_text())
    if not match:
        raise ValueError('Invalid current publication entry')
    run = Path(destination) / match[1]
    verify_publication(run)
    return json.loads((run / 'registry.json').read_text())


def make_handler(root, destination, fallback, port):
    root, destination = Path(root).resolve(), Path(destination).resolve()
    lock = threading.Lock()
    origin = 'http://127.0.0.1:' + str(port)

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(destination), **kwargs)

        def response(self, status, payload):
            data = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_POST(self):
            if self.path not in ('/api/ingestion/directories', '/api/ingestion/remove'):
                return self.response(404, {'status': 'FAIL', 'error': 'Unknown local endpoint'})
            if self.headers.get('Host') != '127.0.0.1:' + str(port) or self.headers.get('Origin') != origin:
                return self.response(403, {'status': 'FAIL', 'error': 'Same-origin loopback request required'})
            if not lock.acquire(blocking=False):
                return self.response(409, {'status': 'FAIL', 'error': 'Another intake is still publishing; retry after completion'})
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if self.headers.get_content_type() != 'application/json' or not 0 < length <= 2_000_000:
                    raise ValueError('Expected a bounded JSON request')
                request = json.loads(self.rfile.read(length))
                config = published_config(destination, fallback)
                if self.path == '/api/ingestion/remove':
                    updated = remove_dataset(config, request.get('dataset_id'))
                    run = publish(root, updated, destination)
                    selected = next((row['id'] for row in updated['datasets']), None)
                    suffix = '#dataset=' + quote(selected, safe='') if selected else ''
                    return self.response(200, {'status': 'PASS', 'url': '/' + run.name + '/index.html' + suffix,
                                               'change': updated['registration_change']})
                name = request.get('package_name')
                if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', name):
                    raise ValueError('Invalid selected package directory name')
                if not isinstance(request.get('files'), list) or not request['files']:
                    raise ValueError('The selected directory file inventory is required')
                updated = restore_directory(root, config, 'dataset/' + name, request['files'])
                run = publish(root, updated, destination)
                self.response(200, {'status': 'PASS', 'dataset_id': updated['directory_intake']['dataset_id'],
                                    'url': '/' + run.name + '/index.html#dataset=' +
                                    quote(updated['directory_intake']['dataset_id'], safe=''),
                                    'intake': updated['directory_intake']})
            except Exception as error:
                self.response(400, {'status': 'FAIL', 'error': str(error)})
            finally:
                lock.release()

        def do_GET(self):
            if self.headers.get('Host') != '127.0.0.1:' + str(port):
                return self.response(403, {'status': 'FAIL', 'error': 'Loopback host required'})
            request=urlsplit(self.path)
            if request.path=='/api/catalogue/selection':
                if self.headers.get('Origin') not in (None,origin) or self.headers.get('Sec-Fetch-Site')=='cross-site':
                    return self.response(403,{'status':'FAIL','error':'Same-origin loopback download required'})
                try:
                    params=parse_qs(request.query,strict_parsing=True)
                    if set(params)!={'run','revision','roles'} or any(len(v)!=1 for v in params.values()):raise ValueError('Invalid selection request')
                    run,revision,roles=(params[key][0] for key in ('run','revision','roles'))
                    if not re.fullmatch(r'run-[0-9a-f]{32}',run) or not re.fullmatch(r'[0-9a-f]{64}',revision) or len(roles)>100:raise ValueError('Invalid selection identity')
                    from src.catalogue_selection import diagnostic_selection
                    from src.ingestion_files import local
                    bundle=local(destination,run+'/common_context/selection')
                    manifest=diagnostic_selection(bundle,revision,roles.split(','))
                    manifest['saved_full_context_store']='/'+run+'/common_context/selection/dataset.json'
                    data=json.dumps(manifest,indent=2,allow_nan=False).encode()
                    self.send_response(200);self.send_header('Content-Type','application/json')
                    self.send_header('Content-Disposition','attachment; filename="r140-context-selection.json"')
                    self.send_header('Content-Length',str(len(data)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(data)
                except Exception as error:self.response(400,{'status':'FAIL','error':str(error)})
                return
            super().do_GET()

    return Handler


def serve(root, destination, fallback, port=8769):
    server = ThreadingHTTPServer(('127.0.0.1', port), make_handler(root, destination, fallback, port))
    print(json.dumps({'status': 'SERVING', 'url': 'http://127.0.0.1:' + str(port) + '/index.html',
                      'scope': 'Project-local qualified-package restoration; no uploads or CAM execution'}), flush=True)
    server.serve_forever()
