#!/usr/bin/env python3
"""Offline source applicability and OKF emitted-profile check; executes no recipes."""
import ast
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlsplit

BUNDLE = Path(__file__).resolve().parents[1]
PROJECT = BUNDLE.parents[1]


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1048576), b''):
            h.update(block)
    return h.hexdigest()


def require(ok, message):
    if not ok:
        raise ValueError(message)


def fm(text):
    match = re.match(r'\A---\n(.*?)\n---(?:\n|$)', text, re.S)
    require(match is not None, 'missing frontmatter')
    fields = {}
    for line in match.group(1).splitlines():
        key, sep, value = line.partition(': ')
        require(sep and key not in fields, 'invalid emitted-profile frontmatter')
        fields[key] = json.loads(value)
    return fields, text[match.end():]


def follow(reference, source):
    url = urlsplit(reference)
    if url.scheme or url.netloc or not url.path:
        return
    path = BUNDLE / unquote(url.path.lstrip('/')) if url.path.startswith('/') else source.parent / unquote(url.path)
    require(path.resolve().is_relative_to(BUNDLE), 'bundle link escapes root: ' + reference)
    require(path.exists(), 'missing bundle link: ' + reference)


def main():
    sources = json.loads((BUNDLE/'references/sources.json').read_text())
    stale = []
    for row in sources['sources']:
        path = (PROJECT/row['project_path']).resolve()
        require(path.is_relative_to(PROJECT), 'source escapes project')
        if not path.is_file() or sha(path) != row['sha256']:
            stale.append(row['project_path'])
        if row.get('snapshot'):
            require(sha(BUNDLE/row['snapshot']) == row['sha256'], 'source snapshot changed')
    dataset = sources['dataset']
    require(sha(PROJECT/dataset['project_path']/'SHA256SUMS') == dataset['sha256sums_sha256'], 'registered dataset seal changed')
    experiments = json.loads((BUNDLE/'references/experiments.json').read_text())
    for row in experiments['records']:
        p = (PROJECT/row['project_path']).resolve()
        require(p.is_relative_to(PROJECT) and p.is_file(), 'historical evidence missing')
        require(sha(p) == row['sha256'], 'historical evidence changed: ' + row['project_path'])
    count = shell_blocks = python_blocks = 0
    for p in sorted(BUNDLE.rglob('*.md')):
        text = p.read_text(encoding='utf-8')
        if p.name == 'index.md':
            if p == BUNDLE/'index.md':
                fields, body = fm(text)
                require(fields == {'okf_version':'0.2'}, 'root OKF version invalid')
            else:
                require(not text.startswith('---'), 'nested index frontmatter')
                body = text
        elif p.name == 'log.md':
            require(not text.startswith('---') and re.search(r'^## \d{4}-\d{2}-\d{2}$', text, re.M), 'invalid update log')
            body = text
        else:
            fields, body = fm(text)
            require(isinstance(fields.get('type'), str) and fields['type'].strip(), 'missing concept type')
            stamp = datetime.fromisoformat(fields['generated']['at'].replace('Z','+00:00'))
            require(stamp.tzinfo is not None and fields['generated']['by'], 'generation provenance invalid')
            require(fields.get('status') in ('draft','stable','deprecated'), 'lifecycle status invalid')
            for source in fields.get('sources', []):
                require(source.get('resource'), 'source resource missing')
                follow(source['resource'], p)
            count += 1
        for link in re.findall(r'\]\(([^\s)]+)\)', body):
            follow(link, p)
        for block in re.findall(r'```sh\n(.*?)\n```', body, re.S):
            result = subprocess.run(['/bin/sh','-n'], input=block, text=True, capture_output=True)
            require(result.returncode == 0, 'invalid shell recipe in ' + str(p) + ': ' + result.stderr)
            shell_blocks += 1
            for code in re.findall(r"<<'PYCODE'\n(.*?)\nPYCODE", block, re.S):
                ast.parse(code)
                python_blocks += 1
    return {'schema':'pcb-cam-runbook-verification-v1','status':'STALE' if stale else 'PASS','scope':'OKF emitted-profile structure, links, source/evidence hashes and recipe syntax; no experiment or engineering validation rerun','stale_sources':stale,'concepts':count,'source_bindings':len(sources['sources']),'historical_evidence_bindings':len(experiments['records']),'shell_blocks_syntax_checked':shell_blocks,'python_blocks_syntax_checked':python_blocks,'verified_at':datetime.now(timezone.utc).isoformat()}


if __name__ == '__main__':
    try:
        result = main()
    except Exception as exc:
        result = {'schema':'pcb-cam-runbook-verification-v1','status':'FAIL','error':str(exc)}
    print(json.dumps(result, indent=2))
    sys.exit(0 if result['status'] == 'PASS' else 1)
