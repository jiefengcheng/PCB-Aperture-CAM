"""Verify retained bundle bytes; does not verify live sources or authorship."""
import argparse,base64,gzip,hashlib,json,re
from pathlib import Path

def verify(bundle):
    errors=[]
    try:
        receipt=json.loads((bundle/'build_receipt.json').read_text())
    except (OSError,ValueError) as exc:
        return {'status':'FAIL','errors':[{'path':'build_receipt.json','error':'UNREADABLE_RECEIPT','detail':str(exc)}]}
    if receipt.get('status')!='PASS':errors.append({'path':'build_receipt.json','error':'GENERATION_UNVERIFIED'})
    def check(relative,expected):
        path=(bundle/relative).resolve()
        if not path.is_relative_to(bundle.resolve()):
            errors.append({'path':relative,'error':'OUTSIDE_BUNDLE'});return
        if not path.is_file():
            errors.append({'path':relative,'error':'MISSING'});return
        if hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
            errors.append({'path':relative,'error':'HASH_MISMATCH'})
    for relative,digest in receipt['outputs'].items():check(relative,digest)
    check('scene.json',receipt['scene_sha256'])
    check('index.html',receipt['html_sha256'])
    if not (bundle/'index.html').is_file() or not (bundle/'scene.json').is_file():
        return {'status':'FAIL','errors':errors}
    page=(bundle/'index.html').read_text()
    embedded=re.search(r'<script[^>]*id="scene-data"[^>]*>(.*?)</script>',page,re.S)
    decoded=embedded[1].encode() if embedded else None
    if embedded and receipt.get('embedded_transport')=='gzip-base64':
        try:decoded=gzip.decompress(base64.b64decode(embedded[1],validate=True))
        except (ValueError,OSError):decoded=None
    if decoded!=(bundle/'scene.json').read_bytes():
        errors.append({'path':'index.html','error':'EMBEDDED_SCENE_MISMATCH'})
    scene=json.loads((bundle/'scene.json').read_text())
    # All copied provenance snapshots must remain bound, including links nested in findings.
    def visit(value):
        if isinstance(value,dict):
            if 'snapshot' in value and 'sha256' in value:check(value['snapshot'],value['sha256'])
            for child in value.values():visit(child)
        elif isinstance(value,list):
            for child in value:visit(child)
    visit(scene)
    for dataset in scene.get('pipeline',{}).get('datasets',[]):
        if hashlib.sha256(dataset['source_utf8'].encode()).hexdigest()!=dataset['source_sha256']:
            errors.append({'path':dataset['label'],'error':'EMBEDDED_SOURCE_BYTES_MISMATCH'})
    return {'status':'PASS' if not errors else 'FAIL','scope':'retained snapshot bytes and embedded scene only; no live source or authorship claim','manifest_outputs':len(receipt['outputs']),'errors':errors}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('bundle',type=Path);args=ap.parse_args()
    result=verify(args.bundle);print(json.dumps(result,indent=2));return result['status']!='PASS'
if __name__=='__main__':raise SystemExit(main())
