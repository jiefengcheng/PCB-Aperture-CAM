#!/usr/bin/env python3
"""Probe the acquired official compatibility ZIP without changing source bytes."""
from pathlib import Path, PurePosixPath
import hashlib,json,sys,zipfile
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.qualify_public import parser_probe
from src.validator import guard,Unsupported,sha

def main():
    source=ROOT/'external/sources/Ucamco/gerber-layer-format-test-files_en.zip'
    before=sha(source);out=ROOT/'out/v1_5/Ucamco';out.mkdir(parents=True,exist_ok=True)
    inventory=[];results=[];readmes=[]
    with zipfile.ZipFile(source) as z:
        for i in z.infolist():
            if i.is_dir():continue
            rel=PurePosixPath(i.filename)
            if rel.is_absolute() or '..' in rel.parts:raise ValueError('unsafe path')
            data=z.read(i);p=out/'extracted'/Path(*rel.parts);p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
            inventory.append({'path':i.filename,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
            if p.suffix.lower()=='.txt':readmes.append({'path':i.filename,'text':data.decode(errors='replace')})
            if p.suffix.lower()!='.gbr':continue
            probe=parser_probe(p)
            try:guard(p.read_text());frozen={'status':'PASS','limitation':'Lexical subset only; layer-role and geometry qualification still required'}
            except (Unsupported,UnicodeError) as exc:frozen={'status':'NOT_ESTABLISHED','reason':str(exc)}
            results.append({'path':i.filename,'gerbonara_parse_and_primitive_expansion':probe,'frozen_v1_lexical_coverage':frozen,
                            'render_oracle_comparison':'NOT_RUN','repair_correctness':'NOT_ESTABLISHED'})
    report={'source_url':'https://www.ucamco.com/files/downloads/file_en/423/gerber-layer-format-test-files_en.zip',
            'catalog_url':'https://www.ucamco.com/en/gerber/downloads','retrieved_date':'2026-10-14',
            'archive_sha256':before,'source_immutable':before==sha(source),'inventory':inventory,'readmes':readmes,
            'license_declaration':{'status':'NOT_ESTABLISHED','reason':'No separate license file in downloaded archive; preserve copyright/readme statements without inferring redistribution rights.'},
            'scope':'Official Gerber compatibility examples only; not repair training or engineering-rule authority.',
            'results':results,'overall':'NOT_ESTABLISHED','cursor_review':{'status':'NOT_RUN','reason':'CHANNEL_UNAVAILABLE'},
            'limitations':['Parser loading/primitive expansion does not establish spec conformance or correct rendered geometry.','Bundled PNG oracle images are retained; visual/geometry comparisons NOT_RUN.','Frozen V1 subset remains unchanged.']}
    (out/'compatibility.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'files':len(results),'gerbonara_statuses':[(x['path'],x['gerbonara_parse_and_primitive_expansion']['status']) for x in results],'readmes':readmes},indent=2))
if __name__=='__main__':main()
