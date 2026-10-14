"""Exact JSON-pointer navigation with access to the complete bound snapshot."""
import hashlib,html,json
from pathlib import Path

def resolve_pointer(value,pointer):
    if pointer=='':return value
    if not pointer.startswith('/'):raise ValueError('INVALID_JSON_POINTER')
    for raw in pointer[1:].split('/'):
        key=raw.replace('~1','/').replace('~0','~')
        if isinstance(value,list):
            if not key.isdigit() or (len(key)>1 and key.startswith('0')):raise ValueError('INVALID_ARRAY_POINTER')
            value=value[int(key)]
        else:value=value[key]
    return value

def add_record_pages(scene,out):
    out=Path(out);folder=out/'records';folder.mkdir(exist_ok=True)
    for case in scene['cases']:
        for state in case['states']:
            for finding in state['checks']:
                evidence=finding['evidence'];source=out/evidence['snapshot'];raw=source.read_bytes()
                if hashlib.sha256(raw).hexdigest()!=evidence['sha256']:raise ValueError('RECORD_SOURCE_HASH_MISMATCH')
                report=json.loads(raw);pointers=[];cid=finding['id'];sid=state['id']
                if case['id']=='synthetic':
                    if sid=='computed':base='/native_gerber_validation'
                    elif sid=='disconnected_n1':base=''
                    else:
                        indexes=[i for i,r in enumerate(report) if r['name']==sid]
                        if len(indexes)!=1:raise ValueError('AMBIGUOUS_CONTROL_RECORD')
                        base=f'/{indexes[0]}/report'
                    checks=resolve_pointer(report,base)['checks'];matches=[i for i,r in enumerate(checks) if r['id']==cid]
                    if len(matches)!=1:raise ValueError('AMBIGUOUS_FINDING_RECORD')
                    pointers=[base+f'/checks/{matches[0]}']
                elif case['id']=='halpi2':
                    if cid=='anchors':pointers=['/terminal_export_mapping']+(['/named_open_control/pad_shape_fully_retained'] if sid=='open' else [])
                    elif sid=='open':pointers=['/named_open_control/observed_connections','/named_open_control/failed_expected_pairs','/named_open_control/pad_shape_fully_retained'] if cid=='connections' else ['/positives/F.Cu/positive/no_short']
                    elif sid=='bridge':pointers=['/bridge_control/observed/'+('source_justified_same_layer_pairs' if cid=='connections' else 'shorts')]
                    else:pointers=['/positives/'+layer+'/positive/'+('source_justified_same_layer_pairs' if cid=='connections' else 'no_short') for layer in ('F.Cu','B.Cu')]
                elif case['id']=='glowstitch':pointers=['/boards/GlowStitch/geometry_profile','/boards/GlowStitch/nominal_exposure'] if cid=='geometry' else ['/electrical_acceptance/GlowStitch','/original_overall']
                records=[{'json_pointer':p,'record':resolve_pointer(report,p)} for p in pointers]
                key=f"{case['id']}_{sid}_{cid}.html";path=folder/key
                body='<!doctype html><meta charset="utf-8"><title>Bound finding record</title><style>body{font:15px sans-serif;max-width:1000px;margin:30px auto;padding:15px}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f0f4f6;padding:15px}a{overflow-wrap:anywhere}</style>'
                body+='<h1>'+html.escape(finding['label'])+'</h1><p>Requirement: '+html.escape(finding['expected'])+'</p><p>Stored observed verdict: '+html.escape(finding['status'])+'</p>'
                body+='<p>Scope: '+html.escape(case['basis'])+'</p><p>Source snapshot SHA256: '+evidence['sha256']+'</p>'
                body+='<p><a href="../'+html.escape(evidence['snapshot'],quote=True)+'">Complete original snapshot</a></p>'
                for record in records:body+='<h2>'+html.escape(record['json_pointer'])+'</h2><pre>'+html.escape(json.dumps(record['record'],indent=2))+'</pre>'
                body+='<p>Snapshot excerpt only; no live-source verification, new validation, or authorship claim.</p>'
                path.write_text(body);finding['evidence']={**evidence,'record_page':'records/'+key,'json_pointers':pointers}
