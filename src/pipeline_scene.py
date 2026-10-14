"""Portable read-only display projection of actual consolidation stage receipts."""
from pathlib import Path
import json,shutil
from shapely import from_wkb
from .visual_scene import ROOT,UnverifiedEvidence,bound,sha,svg_path

def add_pipeline(scene,pipeline,out):
    pipeline=Path(pipeline).resolve();out=Path(out)
    if not pipeline.is_relative_to(ROOT/'out'):raise UnverifiedEvidence('Pipeline input outside project output scope')
    def scoped(relative,expected):
        path=(pipeline/relative).resolve()
        if not path.is_relative_to(pipeline) or len(expected)!=64 or any(c not in '0123456789abcdef' for c in expected):raise UnverifiedEvidence('Unsafe pipeline binding')
        return bound(path,expected)
    receipt=json.loads((pipeline/'receipt.json').read_text())
    for relative,expected in receipt['outputs'].items():scoped(relative,expected)
    datasets=[]
    for entry in receipt['datasets']:
        dataset_path=scoped(entry['file'],receipt['outputs'][entry['file']]);data=json.loads(dataset_path.read_text());inventory=data['inventory']
        source=scoped('catalog/payloads/'+data['source_sha256'],data['source_sha256'])
        target=out/'evidence'/f"{data['source_sha256']}.kicad_pcb";shutil.copy2(source,target)
        records=inventory['objects'];display={}
        for record in records:
            key=record.get('geometry_sha256')
            if key and key not in display:
                payload=scoped('catalog/payloads/'+key,key)
                display[key]=svg_path(from_wkb(payload.read_bytes()))
        topology=data['topology']
        # Keep all source records and components. Query display is explicitly a
        # bounded sample; the complete original receipt remains a separate file.
        selected_ids=set(data.get('selection',{}).get('component',{}).get('members',[])) if data.get('selection') else set()
        samples=[q for q in topology['queries'] if q['query']['object'] in selected_ids]
        if not samples:samples=topology['queries'][:32]
        focus_ids={r['id'] for r in records if r.get('reference')=='J22' and r.get('pin')=='1'}
        samples+= [q for q in topology['queries'] if q['query']['object'] in focus_ids and q not in samples]
        evidence_name='pipeline_'+sha(dataset_path)[:20]+'.json';shutil.copy2(dataset_path,out/'evidence'/evidence_name)
        evidence={'path':str(pipeline/entry['file']),'snapshot':'evidence/'+evidence_name,'sha256':sha(pipeline/entry['file'])}
        scene['provenance'].append(evidence)
        datasets.append({'label':entry['label'],'source_sha256':data['source_sha256'],'catalog_revision':data['catalog_revision'],'objects':records,'geometry_paths':display,'components':topology['components'],'catalog_query_examples':data.get('catalog_query_examples',[]),'query_samples':samples,'query_sample_scope':'selected synthetic component, or first 32 recorded queries; not complete query coverage','stages':data['stages'],'selection':data.get('selection'),'source_utf8':source.read_bytes().decode('utf-8'),'source_evidence':{'snapshot':str(target.relative_to(out)),'sha256':data['source_sha256']},'evidence':evidence,'inventory_counts':{k:inventory[k] for k in ('source_objects','layer_instances','geometry_available','counts','unsupported_reasons')},'limitations':['Nominal native geometry only; acceptance remains with exported-Gerber validators.','Only recorded query samples are selectable in Storage; missing queries are NOT_RECORDED.','Display paths simplify at 0.001 mm and never enter acceptance.']})
    scene['pipeline']={'datasets':datasets,'receipt_sha256':sha(pipeline/'receipt.json'),'source_pipeline':str(pipeline),'native_export':'UNSUPPORTED: diagnostic preserved-source context only'}

def add_native_comparisons(scene,manifest_path,out):
    """Bind actual native process receipts; never synthesize native query results."""
    from .revision_catalog import canonical,digest
    manifest_path=Path(manifest_path).resolve();out=Path(out)
    if not manifest_path.is_relative_to(ROOT/'out'):raise UnverifiedEvidence('Comparison manifest outside output scope')
    manifest=json.loads(manifest_path.read_text());datasets={d['label']:d for d in scene.get('pipeline',{}).get('datasets',[])};seen=set()
    for entry in manifest['comparisons']:
        path=Path(entry['path']);path=path if path.is_absolute() else ROOT/path;path=path.resolve()
        if not path.is_relative_to(ROOT/'out'):raise UnverifiedEvidence('Native report outside output scope')
        bound(path,entry['sha256']);report=json.loads(path.read_text());dataset=datasets[entry['dataset']];layer=entry['layer']
        if (entry['dataset'],layer) in seen:raise UnverifiedEvidence('Ambiguous native layer comparison')
        seen.add((entry['dataset'],layer))
        if report['status']!='PARITY_PASS' or report['source_snapshot']!=dataset['catalog_revision'] or report['source_pipeline_sha256']!=dataset['evidence']['sha256'] or report['layer_scope']!=layer:raise UnverifiedEvidence('Unqualified or stale native comparison')
        build=report['native_build'];materialization=path.parent/'materialization'
        if build['source_snapshot']!=dataset['catalog_revision'] or build['layer_scope']!=layer or build['binary_sha256']!=report['binary_sha256']:raise UnverifiedEvidence('Native materialization scope mismatch')
        for relative,expected in build['files'].items():
            candidate=(materialization/relative).resolve()
            if not candidate.is_relative_to(materialization.resolve()):raise UnverifiedEvidence('Unsafe native binding')
            bound(candidate,expected)
        mapping=json.loads((materialization/'identities.json').read_text())
        if not set(mapping)<={r['id'] for r in dataset['objects']}:raise UnverifiedEvidence('Native identity outside source catalog')
        samples=report['actual_query_samples']
        for direction,sample in samples.items():
            if sample['source_snapshot']!=dataset['catalog_revision'] or sample.get('layer_scope')!=layer or sample['direction']!=direction or sample['result_sha256']!=digest(canonical(sample['records'])):raise UnverifiedEvidence('Native query sample binding mismatch')
        target=out/'evidence'/('native_'+entry['sha256'][:20]+'.json');shutil.copy2(path,target)
        evidence={'snapshot':str(target.relative_to(out)),'sha256':entry['sha256'],'path':str(path)};scene['provenance'].append(evidence)
        dataset.setdefault('native_comparisons',[]).append({'layer':layer,'backend_decision':'SHADOW_ONLY','materialized_ids':sorted(mapping),'identity_count':report['identity_count'],'query_samples':samples,'parity_status':report['status'],'evidence':evidence,'source_snapshot':report['source_snapshot'],'samples':report['samples'],'limitations':report['limitations']})
