/* Exercise navigation and retained stage selection in the production renderer. */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const {Element,descend}=require('./ingestion_views.test.cjs');

function run(){
 const nodes=Object.fromEntries(['workbench-views','pipeline-view','case-view','headline','story'].map(id=>[id,new Element('div')]));
 const document={getElementById:id=>nodes[id],createElement:t=>new Element(t),createElementNS:(_,t)=>new Element(t)};
 const stages=['source_custody','inventory','spatial_index','exact_relationships','persistence','catalog_queries','operation_context','future_stage'].map((stage,i)=>({id:'stage-'+i,stage,state:i===3?'PARTIAL':'COMPLETE',counts:{witness:i},details:{retained:true}}));
 const dataset={label:'Recorded source',source_sha256:'source-hash',catalog_revision:'revision-hash',source_utf8:'source',objects:[],stages,inventory_counts:{source_objects:0,layer_instances:0,geometry_available:0},query_samples:[{query:{object:'missing',layer:'F.Cu'},status:'NOT_RECORDED',counts:{sample:1}}],components:[],geometry_paths:{},limitations:[],query_sample_scope:'Recorded samples only',catalog_query_examples:[{title:'Saved catalog example',kind:'example',receipt:{status:'PARTIAL',records:[]}}]};
 const context=vm.createContext({document,window:{},TextEncoder,TextDecoder,performance,scene:{pipeline:{datasets:[dataset]},cases:[{states:[]}]}});
 vm.runInContext(fs.readFileSync(path.join(__dirname,'../../web/pipeline_views.js'),'utf8'),context);
 vm.runInContext('initPipeline(scene)',context);
 const nav=nodes['workbench-views'],panel=nodes['pipeline-view'];
 assert.deepEqual(nav.children.map(n=>n.textContent),['Storage & indexes','Cases']);
 assert.equal(nodes['case-view'].hidden,false);
 nav.children[0].onclick();
 assert.equal(panel.hidden,false);assert.equal(nodes['case-view'].hidden,true);
 assert.equal(descend(panel,n=>n.tag==='h2'&&n._text==='persistence').length,1,'Storage opens on its persistence receipt');
 const retained=stages.filter(s=>!['source_custody','inventory'].includes(s.stage));
 assert.deepEqual(descend(panel,n=>n.dataset.stage).map(n=>n.dataset.stage),retained.map(s=>s.id));
 assert.deepEqual(descend(panel,n=>n.dataset.inputStage).map(n=>n.dataset.inputStage),['source_custody','inventory'],'Unlinked historical revisions retain input-stage receipts');
 for(const stage of retained){
  descend(panel,n=>n.dataset.stage===stage.id)[0].onclick();
  const receipt=descend(panel,n=>n.tag==='details'&&n.children[0]?._text==='Stage receipt · inputs, scope and implementation')[0].children[1];
  assert.deepEqual(JSON.parse(receipt._text),stage,'Each stage inspector uses the retained receipt');
 }
 descend(panel,n=>n.tag==='button'&&n._text==='missing · NOT_RECORDED')[0].onclick();
 assert.equal(descend(panel,n=>n.tag==='h2'&&n._text==='Recorded query').length,1);
 descend(panel,n=>n.dataset.catalogExample==='example')[0].onclick();
 assert.match(panel.textContent,/Saved catalog example/);
 nav.children[1].onclick();
 assert.equal(panel.hidden,true);assert.equal(nodes['case-view'].hidden,false);
 return {status:'PASS',checks:['Processing removed; Storage precedes Cases','Storage opens on persistence, preserving all non-input stages including unknown future stages','Unlinked historical native revisions retain input-stage receipts','Receipt selection retains original states, counts and details','Saved query examples and Cases navigation remain accessible']};
}
module.exports={run};
if(require.main===module)console.log(JSON.stringify(run()));
