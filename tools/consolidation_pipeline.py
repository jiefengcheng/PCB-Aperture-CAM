"""Generate source-bound inventory, topology, catalog and context receipts."""
from pathlib import Path
import argparse,datetime,importlib.metadata,json,sys,time,zipfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.native_inventory import inventory,VERSION,ERROR_MM
from src.revision_catalog import RevisionCatalog,canonical,digest
from src.spatial_context import SpatialContext
from tools.preflight import verify_manifest
ROOT=Path(__file__).resolve().parents[1]

def component_filter(revision,objects,components):
    """Recorded diagnostic bbox/aspect query; never a copper-area or permission test."""
    started=time.perf_counter();by_id={r['id']:r for r in objects};rows=[]
    for c in components:
        bounds=[by_id[uid]['bounds_mm'] for uid in c['members']]
        a=min(b[0] for b in bounds);b=min(b[1] for b in bounds);x=max(bd[2] for bd in bounds);y=max(bd[3] for bd in bounds)
        width=x-a;height=y-b;area=width*height;aspect=width/height if height else None
        if area>=1 and aspect is not None and .1<=aspect<=10:rows.append({'id':c['id'],'layer':c['layer'],'bbox_area_mm2':area,'aspect_width_over_height':aspect,'bounds_mm':[a,b,x,y],'members':c['members']})
    rows.sort(key=lambda r:r['id']);complete=len(rows)<=10;rows=rows[:10]
    return {'revision':revision,'backend':'recorded nominal component bounds','status':'COMPLETE' if complete else 'TRUNCATED','complete':complete,'scope':'Available nominal geometry components only; bbox area is not filled copper area; no electrical or permission inference','query':{'minimum_bbox_area_mm2':1,'aspect_width_over_height':[.1,10],'limit':10},'components_examined':len(components),'records':rows,'selected_ids':rows[0]['members'] if rows else [],'result_sha256':digest(canonical(rows)),'elapsed_seconds':time.perf_counter()-started}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--legacy',action='store_true');ap.add_argument('--public',action='store_true');ap.add_argument('--v2-result',type=Path);args=ap.parse_args()
    implementation_paths=['src/native_inventory.py','src/source_locators.py','src/spatial_context.py','src/revision_catalog.py','src/catalog_selection.py','tools/consolidation_pipeline.py']
    implementation_at_start={p:digest((ROOT/p).read_bytes()) for p in implementation_paths}
    assets_verified=verify_manifest()
    run=ROOT/'out/consolidation'/datetime.datetime.now(datetime.timezone.utc).strftime('pipeline_%Y%m%dT%H%M%S_%fZ');run.mkdir()
    contract=json.loads((ROOT/'contracts/v2_move_pad.json').read_text())
    sources=[('synthetic_before',ROOT/contract['source'],contract['source_sha256'])]
    if args.legacy:sources.append(('legacy_scale',Path(contract['pcb_Z_path'])/'test.kicad_pcb',None))
    execution=None
    if args.v2_result:
        execution=json.loads(args.v2_result.read_text())
        candidate=args.v2_result.parent/'positive/accepted/coupon.kicad_pcb'
        if execution['status']!='PASS' or digest(candidate.read_bytes())!=execution['output_sha256']['positive/accepted/coupon.kicad_pcb']:raise ValueError('UNQUALIFIED_CANDIDATE_RESULT')
        sources.append(('synthetic_candidate',candidate,execution['output_sha256']['positive/accepted/coupon.kicad_pcb']))
    archived_sources={}
    if args.public:
        public=json.loads((ROOT/'contracts/public_sources.json').read_text())
        for name in ('GlowStitch','HALPI2-HDMI-FPC'):
            declaration=public['sources'][name];selection=declaration['selection'];folder=ROOT/'external/sources'/name
            if selection['archive']:
                archive=folder/selection['archive'];entry=next(r for r in declaration['source_inventory'] if r['path']==selection['archive'])
                if digest(archive.read_bytes())!=entry['sha256']:raise ValueError('PUBLIC_ARCHIVE_HASH_MISMATCH')
                with zipfile.ZipFile(archive) as z:raw=z.read(selection['board'])
                archived_sources[archive]=(raw,selection['board']);path=archive
            else:path=folder/selection['board']
            sources.append((name,path,selection['source_board_sha256']))
    bundles=[]
    with RevisionCatalog(run/'catalog') as catalog:
        for label,path,expected in sources:
            start=time.perf_counter();source=archived_sources[path][0] if path in archived_sources else path.read_bytes();source_hash=digest(source)
            if expected is not None and source_hash!=expected:raise ValueError('SOURCE_HASH_MISMATCH')
            acquisition=time.perf_counter()-start
            data=inventory(source)
            for payload in data['payloads'].values():catalog.put_payload(payload)
            context=SpatialContext(source_hash,data['objects'],data['payloads'])
            start=time.perf_counter();topology=context.topology();group_seconds=time.perf_counter()-start
            start=time.perf_counter();revision=catalog.import_revision(source,data['objects'],topology['relations'],{'extractor':VERSION,'geometry_error_mm':data['geometry_error_mm'],'units':'mm','spatial_snapshot':context.snapshot,'kernel_versions':context.kernel_versions,'implementation_sha256':{p:implementation_at_start[p] for p in ['src/native_inventory.py','src/source_locators.py','src/spatial_context.py']}},publish_as=label);persist_seconds=time.perf_counter()-start
            stages=[]
            def stage(name,parents,seconds,counts,**details):
                stages.append({'id':label+'/'+name,'stage':name,'parent_stages':[label+'/'+p for p in parents],'source_sha256':source_hash,'catalog_revision':revision,'state':'COMPLETE','elapsed_seconds':seconds,'counts':counts,'memory':'NOT_RECORDED','details':details})
            stage('source_custody',[],acquisition,{'source_bytes':len(source)},source_path=str(path),archive_member=archived_sources[path][1] if path in archived_sources else None,source_archive_sha256=digest(path.read_bytes()) if path in archived_sources else None,payload_sha256=source_hash)
            stage('inventory',['source_custody'],data['elapsed_seconds'],{'source_objects':data['source_objects'],'layer_instances':data['layer_instances'],'geometry_available':data['geometry_available']},extractor=VERSION,timing_breakdown=data['timings'],unsupported_reasons=data['unsupported_reasons'],metadata_exclusions=data['metadata_exclusions'],kind_counts=data['counts'])
            stage('spatial_index',['inventory'],context.build_seconds,{'indexed_objects':len(context.shapes),'indexed_layer_instances':sum(map(len,context.layers.values()))},backend='rtree/libspatialindex',kernel_versions=context.kernel_versions,timing_breakdown={'geometry_decode_and_layer_bind_seconds':context.geometry_decode_layer_bind_seconds,'index_bulk_build_seconds':context.index_bulk_build_seconds},snapshot=context.snapshot)
            stage('exact_relationships',['spatial_index'],group_seconds,{'candidate_rows':sum(len(q['candidate_ids']) for q in topology['queries']),'physical_relation_occurrences':len(topology['relations']),'computed_components':len(topology['components']),'singletons':sum(c['singleton'] for c in topology['components'])},predicate='GEOS intersects on nominal native geometry',pcb_groups=data['counts'].get('group',0),omissions=topology['omissions'])
            stage('persistence',['exact_relationships'],persist_seconds,{'stored_objects':data['source_objects'],'stored_relation_occurrences':len(topology['relations'])},backend='SQLite reference + SHA256 payload catalog',durability='transactional consistency; no power-loss durability claim')
            query_examples=[]
            for title,kwargs in [('Ordered first five',{'limit':5}),('Front copper pads',{'properties':{'kind':'pad'},'layer':'F.Cu','limit':100}),('All retained native terminals',{'properties':{'kind':'pad'},'limit':10000})]:
                q=catalog.query(revision,**kwargs);query_examples.append({'title':title,'kind':'catalog_query','receipt':q})
            first=next((r for r in data['objects'] if r.get('geometry_sha256') and 'F.Cu' in r['layers']),None)
            if first:
                q=catalog.region_query(revision,first['bounds_mm'],'F.Cu',limit=1000)
                query_examples.append({'title':'Exact front-copper region','kind':'region_query','receipt':q})
            if first:
                seed=next((r for r in data['objects'] if r.get('native_id')==contract['target'] and r.get('geometry_sha256')),first)
                q=context.query(seed['id'],'F.Cu',distance_mm=2.0)
                query_examples.append({'title':'Nearby copper within 2 mm · read-only','kind':'proximity_query','receipt':q})
            query_examples.append({'title':'Component bbox area / width-height aspect','kind':'component_filter','receipt':component_filter(revision,data['objects'],topology['components'])})
            if label=='HALPI2-HDMI-FPC':
                q=catalog.query(revision,properties={'kind':'pad','reference':'J22','pin':'1'},limit=100)
                query_examples.append({'title':'J22.1 native-source terminals · intent is separate','kind':'catalog_query','receipt':q})
            named=next((r for r in data['objects'] if r['kind']=='group' and r.get('group_name') is not None),None)
            if named:
                try:q=catalog.select(revision,named_groups=[named['group_name']])
                except ValueError as exc:q={'status':'ERROR','complete':False,'error':str(exc),'records':[]}
                query_examples.append({'title':'Native group '+named['group_name'],'kind':'native_group_selection','receipt':q})
            stage('catalog_queries',['persistence'],sum(e['receipt'].get('elapsed_seconds',0) for e in query_examples),{'recorded_queries':len(query_examples)},backend='SQLite reference / exact GEOS region',scope='Bounded recorded diagnostic queries; incomplete/unknown coverage is explicit.')
            selection=None
            if label=='synthetic_before':
                by_native={r['native_id']:r['id'] for r in data['objects'] if r['native_id']}
                target=by_native[contract['target']];writable=[target,*[by_native[x] for x in contract['dependents']]]
                component=next(c for c in topology['components'] if c['layer']=='F.Cu' and target in c['members'])
                selection=catalog.select(revision,object_ids=writable,context_ids=component['members'],writable_ids=writable)
                selection['target_id']=target;selection['component']=component
                stage('operation_context',['persistence'],selection['elapsed_seconds'],{'direct_target':1,'writable_objects':len(writable),'physical_component_objects':len(component['members']),'protected_context_objects':len(selection['context_ids']),'container_dependencies':len(selection['dependency_ids'])},contract_sha256=digest((ROOT/'contracts/v2_move_pad.json').read_bytes()),native_export=selection['native_export'],recorded_v2_result=str(args.v2_result) if execution else 'out/v2/run_20261014T164520_384804Z/result.json',execution='RECORDED: catalog-admitted execution' if execution and execution['catalog_admission']['catalog_revision']==revision else 'NOT_RUN: no matching catalog-admitted execution',execution_result_sha256=digest(args.v2_result.read_bytes()) if execution else None)
            bundle={'label':label,'source_sha256':source_hash,'catalog_revision':revision,'inventory':{k:v for k,v in data.items() if k!='payloads'},'topology':topology,'selection':selection,'catalog_query_examples':query_examples,'stages':stages}
            (run/(label+'.json')).write_bytes(canonical(bundle));bundles.append({'label':label,'file':label+'.json','catalog_revision':revision})
    with RevisionCatalog(run/'catalog') as reopened:
        for item in bundles:
            rev=reopened.published(item['label']);assert rev==item['catalog_revision']
            item['reopen_query']=reopened.query(rev,limit=10)
    receipt={'status':'GENERATED_NOT_ACCEPTANCE','assets_verified':assets_verified,'datasets':bundles,'tool_versions':{n:importlib.metadata.version(n) for n in ['sexpdata','shapely','rtree']},'implementation_sha256':implementation_at_start,'implementation_unchanged_during_run':implementation_at_start=={p:digest((ROOT/p).read_bytes()) for p in implementation_paths},'outputs':{str(p.relative_to(run)):digest(p.read_bytes()) for p in run.rglob('*') if p.is_file()},'limitations':['Native source geometry is context, not exported-Gerber acceptance.','No new V2 execution claimed by this pipeline alone.','Missing/unqualified native geometry stays explicitly unsupported.']}
    if not receipt['implementation_unchanged_during_run']:receipt['status']='UNQUALIFIED_SOURCE_DRIFT'
    (run/'receipt.json').write_bytes(canonical(receipt));print(json.dumps({'run':str(run),'datasets':[{k:v for k,v in x.items() if k!='reopen_query'} for x in bundles]}),flush=True)
if __name__=='__main__':main()
