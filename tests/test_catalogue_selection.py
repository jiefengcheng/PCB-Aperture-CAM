import json
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from src.catalogue_selection import diagnostic_selection
from src.ingestion_files import sha
from tests.test_common_catalogue import fixture


class DiagnosticSelectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir='out');self.root=Path(self.tmp.name).resolve()
        self.run='run-'+'a'*32;self.bundle=self.root/self.run/'common_context/selection';self.bundle.mkdir(parents=True)
        self.revision,_=fixture(self.bundle)
    def tearDown(self):self.tmp.cleanup()
    def test_subset_dedup_dependencies_and_recorded_relationships(self):
        before={str(p):sha(p) for p in self.bundle.rglob('*') if p.is_file()}
        full=diagnostic_selection(self.bundle,self.revision,['R140.1','R140.2','connected_trace','mask_opening'])
        self.assertEqual(full['object_count'],8);self.assertEqual(len(full['relationships']['physical_contacts']),1)
        mask=diagnostic_selection(self.bundle,self.revision,['mask_opening'])
        self.assertEqual(mask['object_count'],3);self.assertEqual(mask['dependencies'][0]['reference'],'R140')
        self.assertEqual(mask['relationships']['physical_contacts'],[])
        self.assertFalse(mask['relationships']['recorded_group_membership'][0]['complete_within_recorded_group'])
        self.assertEqual(diagnostic_selection(self.bundle,self.revision,['connected_trace'])['object_count'],2)
        self.assertEqual(diagnostic_selection(self.bundle,self.revision,['R140.1','mask_opening'])['object_count'],4)
        self.assertEqual(mask['writable_ids'],[]);self.assertTrue(all(q['complete'] and not q['writable_ids'] for q in mask['selection_receipts']))
        self.assertEqual(before,{str(p):sha(p) for p in self.bundle.rglob('*') if p.is_file()})
    def test_unknown_empty_and_stale_revision_reject(self):
        for roles in ([],['unknown'],['R140.1']*5):
            with self.assertRaises(ValueError):diagnostic_selection(self.bundle,self.revision,roles)
        with self.assertRaisesRegex(ValueError,'STALE_MIXED'):diagnostic_selection(self.bundle,'0'*64,['mask_opening'])
    def test_http_attachment_and_identity_origin_guards(self):
        from tools.ingestion_server import make_handler
        server=ThreadingHTTPServer(('127.0.0.1',0),SimpleHTTPRequestHandler);port=server.server_address[1]
        server.RequestHandlerClass=make_handler(self.root,self.root,None,port)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        base='http://127.0.0.1:'+str(port)
        path='/api/catalogue/selection?run='+self.run+'&revision='+self.revision+'&roles=mask_opening'
        try:
            with urlopen(base+path) as response:
                self.assertIn('attachment',response.headers['Content-Disposition']);body=json.loads(response.read())
                self.assertEqual(body['object_count'],3);self.assertEqual(body['mode'],'SERVER_SELECTION_FROM_VERIFIED_CATALOGUE')
            for url,headers,status in [(base+path,{'Origin':'https://invalid.example'},403),
                                        (base+path,{'Sec-Fetch-Site':'cross-site'},403),
                                        (base+path.replace(self.run,'../outside'),{},400),
                                        (base+path.replace('mask_opening','unknown'),{},400)]:
                with self.assertRaises(HTTPError) as error:urlopen(Request(url,headers=headers))
                self.assertEqual(error.exception.code,status)
                error.exception.close()
        finally:server.shutdown();server.server_close();thread.join()


if __name__=='__main__':unittest.main()
