"""Admit catalog context, then run the unchanged frozen coupon executor/checker.
The catalog constrains source/context admission. The frozen executor deliberately
rediscovers geometry from those exact bytes; native shadow does not control edits.
"""
from pathlib import Path
import argparse,datetime,json,shutil,subprocess,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.revision_catalog import RevisionCatalog,canonical,digest,CatalogError
from src.v2_executor import execute,sha,ROOT
from src.validator import evaluate,layers,equivalent
from src.falsification import falsify
from tools.v2_run import CLI
from tools.qualify_public import command
from tools.preflight import verify_manifest

def admit(pipeline,contract):
    pipeline=Path(pipeline);receipt=json.loads((pipeline/'receipt.json').read_text())
    entry=next(x for x in receipt['datasets'] if x['label']=='synthetic_before')
    file=pipeline/entry['file']
    if sha(file)!=receipt['outputs'][entry['file']]:raise CatalogError('PIPELINE_RECORD_HASH_MISMATCH')
    record=json.loads(file.read_text());revision=record['catalog_revision'];prior_selection=record['selection']
    with RevisionCatalog(pipeline/'catalog') as catalog:
        if catalog.published('synthetic_before')!=revision:raise CatalogError('SOURCE_PUBLICATION_MISMATCH')
        manifest=catalog.snapshot(revision);source=catalog.read_payload(manifest['source_sha256'])
        if digest(source)!=contract['source_sha256']:raise CatalogError('EXECUTOR_SOURCE_REVISION_MISMATCH')
        expected=[contract['target'],*contract['dependents']];ids=[];queries=[]
        for native_id in expected:
            q=catalog.query(revision,native_id=native_id,limit=2);queries.append(q)
            if not q['complete'] or len(q['records'])!=1:raise CatalogError('AMBIGUOUS_OPERATION_REFERENCE')
            ids.append(q['records'][0]['id'])
        if set(ids)!=set(prior_selection['writable_ids']):raise CatalogError('CONTEXT_PERMISSION_MISMATCH')
        selection=catalog.select(revision,object_ids=ids,context_ids=prior_selection['component']['members'],writable_ids=ids)
        if len(selection['context_ids'])!=2:raise CatalogError('PROTECTED_CONTEXT_MISMATCH')
        # Prove physical membership from persisted relations, independently of the
        # selected membership array. Contact is symmetric; stored edges are oriented.
        relations=catalog.query(revision,relation_type='physical_contact',limit=100000)
        if not relations['complete']:raise CatalogError('INCOMPLETE_RELATION_CONTEXT')
        adjacency={}
        for r in relations['records']:
            adjacency.setdefault(r['source'],set()).add(r['target']);adjacency.setdefault(r['target'],set()).add(r['source'])
        visited=set();todo=[ids[0]]
        while todo:
            uid=todo.pop()
            if uid in visited:continue
            visited.add(uid);todo.extend(adjacency.get(uid,set())-visited)
        if visited!=set(prior_selection['component']['members']):raise CatalogError('PERSISTED_COMPONENT_MISMATCH')
    return source,{'catalog_revision':revision,'source_sha256':digest(source),'pipeline_record_sha256':sha(file),'identity_queries':queries,'relation_query':relations,'selection':selection,'admission':'PASS','role':'Catalog admission; frozen executor rediscovers geometry from identical source bytes.'}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('pipeline',type=Path);args=ap.parse_args();verify_manifest()
    contract=json.loads((ROOT/'contracts/v2_move_pad.json').read_text());source_bytes,admission=admit(args.pipeline,contract)
    pinned=json.loads((ROOT/'out/native_exports/20261014T140617_287308Z/run_receipt.json').read_text())
    if sha(CLI)!=pinned['cli_sha256']:raise ValueError('PINNED_KICAD_BINARY_MISMATCH')
    original=json.loads((ROOT/'out/v2/run_20261014T164520_384804Z/result.json').read_text())
    for path,expected in original['implementation_sha256'].items():
        if sha(ROOT/path)!=expected:raise ValueError('FROZEN_EXECUTION_IMPLEMENTATION_CHANGED')
    frozen_validation={}
    for name in ['src/validator.py','src/gerber_image.py','src/completion_checks.py','src/native_reference.py']:
        reference=subprocess.check_output(['git','show','5d91db9:'+name],cwd=ROOT)
        if sha(ROOT/name)!=digest(reference):raise ValueError('FROZEN_VALIDATOR_SOURCE_CHANGED: '+name)
        frozen_validation[name]=digest(reference)
    run=ROOT/'out/v2'/datetime.datetime.now(datetime.timezone.utc).strftime('catalog_%Y%m%dT%H%M%S_%fZ');run.mkdir()
    source=run/'catalog_source/coupon.kicad_pcb';source.parent.mkdir();source.write_bytes(source_bytes)
    project=ROOT/contract['source'];project=project.with_suffix('.kicad_pro')
    result={'status':'NOT_ESTABLISHED','operation_contract':contract['id'],'contract_sha256':sha(ROOT/'contracts/v2_move_pad.json'),'catalog_admission':admission,'source_sha256':digest(source_bytes),'cli_sha256':sha(CLI),'transactions':{},'Cursor':'NOT_RUN: CHANNEL_UNAVAILABLE','factory':'NOT_ESTABLISHED','implementation_sha256':original['implementation_sha256'],'frozen_validation_sha256':frozen_validation,'execution_source':{'frozen_executor_commit':subprocess.check_output(['git','rev-parse','500d070'],cwd=ROOT,text=True).strip(),'integration_base_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'integration_working_tree_dirty':bool(subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip())},'integration_sha256':{p:sha(ROOT/p) for p in ['tools/catalog_v2_run.py','src/revision_catalog.py']}}
    def export(board,bundle):
        verify_manifest()
        if sha(CLI)!=pinned['cli_sha256']:raise ValueError('PINNED_KICAD_BINARY_DRIFT')
        directory=bundle/'gerbers';directory.mkdir()
        if project.exists():shutil.copy2(project,board.with_suffix('.kicad_pro'))
        receipt={'input_board_sha256':sha(board),'commands':[]}
        try:
            for argv,log,allowed in [([CLI,'pcb','drc','--format','json','--severity-all','--exit-code-violations','-o',bundle/'drc.json',board],'drc.log',(0,5)),([CLI,'pcb','export','gerbers','--layers','F.Cu,F.Mask,Edge.Cuts','--precision','6','--no-protel-ext','-o',str(directory)+'/',board],'export.log',(0,))]:
                r=command(argv,bundle/log);r['log_relative_to_bundle']=log;receipt['commands'].append(r)
                if r['exit_code'] not in allowed:raise RuntimeError('NATIVE_TOOL_FAILURE')
            if sha(CLI)!=pinned['cli_sha256']:raise RuntimeError('KICAD_BINARY_CHANGED_DURING_EXPORT')
            if sha(board)!=receipt['input_board_sha256']:raise RuntimeError('EXPORTED_BOARD_CHANGED')
            receipt['outputs']={p.name:sha(p) for p in directory.iterdir() if p.is_file()}
        finally:(bundle/'export_receipt.json').write_bytes(canonical(receipt))
        return directory
    try:
        result['version']=command([CLI,'version'],run/'version.log')
        before=run/'before';before.mkdir();(before/'coupon.kicad_pcb').write_bytes(source_bytes)
        before_export=export(before/'coupon.kicad_pcb',before)
        validator=lambda directory:evaluate(before_export,directory)
        for name in ['positive','replay']:
            result['transactions'][name]=execute(source,contract,run/name,export,validator)
            if result['transactions'][name]['state']!='COMMITTED':raise RuntimeError('EXECUTION_NOT_COMMITTED')
        candidate=run/'positive/accepted/coupon.kicad_pcb';candidate_export=candidate.parent/'gerbers'
        replay=run/'replay/accepted/coupon.kicad_pcb'
        old_candidate=ROOT/'out/v2/run_20261014T164520_384804Z/positive/accepted/coupon.kicad_pcb'
        result['same_qualified_candidate']={'status':'PASS' if candidate.read_bytes()==replay.read_bytes()==old_candidate.read_bytes() else 'FAIL','candidate_sha256':sha(candidate),'prior_candidate_sha256':sha(old_candidate),'replay_sha256':sha(replay)}
        result['native_gerber_validation']=validator(candidate_export)
        negatives=falsify(before_export,candidate_export,run/'gerber_faults');(run/'negative_controls.json').write_bytes(canonical(negatives))
        result['frozen_gerber_fault_controls']=[{k:v for k,v in r.items() if k!='report'} for r in negatives]
        for name,anchor,replacement,expected in [('broken_connection','X20000000Y-21550000D02*\nX20000000Y-23000000D01*','','FAIL'),('unsupported_semantics','%LPD*%','%LPD*%\n%LMX*%','NOT_ESTABLISHED')]:
            def corrupted(board,bundle,anchor=anchor,replacement=replacement):
                directory=export(board,bundle);p=directory/'coupon-F_Cu.gbr';raw=p.read_text()
                if anchor not in raw:raise ValueError('FAULT_ANCHOR_UNAVAILABLE')
                p.write_text(raw.replace(anchor,replacement));return directory
            result['transactions'][name]=execute(source,contract,run/name,corrupted,validator)
            observed=json.loads((run/name/'staging/validation.json').read_text())['overall']
            if result['transactions'][name]['state']!='REJECTED' or observed!=expected:raise RuntimeError('FAULT_REJECTION_MISMATCH')
        for phase in ['STAGED','VALIDATED']:
            def fault(name,workspace,phase=phase):
                if name==phase:raise OSError('deliberate prepublication fault '+phase)
            name='failure_at_'+phase.lower();result['transactions'][name]=execute(source,contract,run/name,export,validator,fault)
            if result['transactions'][name]['state']!='REJECTED' or (run/name/'accepted').exists():raise RuntimeError('FAILED_TRANSACTION_PUBLISHED')
        result['rollback']={'status':'PASS' if sha(source)==contract['source_sha256'] and sha(candidate)==sha(old_candidate) else 'FAIL','source_unchanged':sha(source)==contract['source_sha256'],'previous_accepted_unchanged':sha(old_candidate)==original['output_sha256']['positive/accepted/coupon.kicad_pcb'],'mechanism':'Failed staging retained; only validated transaction published; no power-loss durability claim.'}
        result['status']='PASS' if all([result['same_qualified_candidate']['status']=='PASS',result['native_gerber_validation']['overall']=='PASS',all(r['status']=='PASS' for r in negatives),result['rollback']['status']=='PASS']) else 'FAIL'
    except Exception as exc:result['error']=repr(exc);result['status']='FAIL';raise
    finally:
        result['output_sha256']={str(p.relative_to(run)):sha(p) for p in sorted(run.rglob('*')) if p.is_file() and p.name!='result.json'}
        (run/'result.json').write_bytes(canonical(result));print(json.dumps({'run':str(run),'status':result['status'],'error':result.get('error')}),flush=True)
if __name__=='__main__':main()
