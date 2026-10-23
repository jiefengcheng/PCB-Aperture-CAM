/* DOM contract regressions for the production ingestion renderer. Run with Node. */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
class Element {
 constructor(tag){this.tag=tag;this.children=[];this.dataset={};this.style={};this.attrs={};this.classList={add:()=>{},toggle:()=>{}};this._text='';}
 set textContent(value){this._text=String(value);this.children=[];}
 get textContent(){return this._text+this.children.map(c=>c.textContent||'').join(' ');}
 append(...items){this.children.push(...items);}
 prepend(...items){this.children.unshift(...items);}
 replaceChildren(...items){this.children=items;}
 setAttribute(k,v){this.attrs[k]=v;}
 getAttribute(k){return this.attrs[k]??null;}
 focus(){this.focused=true;}
 setSelectionRange(start,end){this.selection=[start,end];}
 after(item){this.following=item;}
 addEventListener(){}
 scrollIntoView(options){this.scrolled=options.block;}
}
function descend(node,predicate){return [node,...node.children.flatMap(n=>descend(n,predicate))].filter(predicate);}
function chapter(panel,title){return descend(panel,n=>n.tag==='button'&&n.children.some(c=>c.tag==='strong'&&c._text===title))[0];}
function run(){
 const nav=new Element('nav');const nodes={'workbench-views':nav,'case-view':new Element('div'),'pipeline-view':new Element('div'),'headline':new Element('h1'),'story':new Element('p')};
 const document={getElementById:id=>nodes[id],createElement:t=>new Element(t),createElementNS:(_,t)=>new Element(t)};
 const context=vm.createContext({document});vm.runInContext(fs.readFileSync(path.join(__dirname,'../../web/ingestion_views.js'),'utf8'),context);
 const evidence=[{path:'local',sha256:'a',snapshot:'local.json'},{path:'discrepancy',sha256:'b',snapshot:'diff.json'},{path:'drills',sha256:'c',snapshot:'drill.json'}];
 const data={id:'client:first',label:'First',qualification:'Partial',intent:'Unknown',sources:[],evidence,qualification_data:{records:[
  {role:'local',evidence:evidence[0],metrics:{roi_mm:[1,2,3,4],layers:{'B.Cu':{symmetric_difference_area_mm2:1.234}}}},
  {role:'discrepancy',evidence:evidence[1],metrics:{source_only_flash_count:7,native_only_flash_count:2,symmetric_difference_area_mm2:8.765,roi_mm:[1,2,3,4]}},
  {role:'drills',evidence:evidence[2],metrics:{PTH:{drills:{matched:123,total_source:125,total_native:124,position_tolerance_mm:.009,tool_tolerance_mm:.008},slot_match:{matched:3,endpoint_tolerance_mm:.007}}}}
 ],comparisons:[{label:'Known difference',receipt_role:'discrepancy',view_box:[0,0,4,4],source_path:'M0 0 L1 0 Z',native_path:'M2 2 L3 2 Z',source_only_path:'M0 0 L.5 0 Z',native_only_path:'',inputs:{},basis:'REPLAY'}]}};
 context.scene={cases:[],ingestion:{intake:{dataset_id:data.id,package_root:'dataset/sample',artifacts:{entry:{snapshot:'intake/index.md'},manifest:{snapshot:'intake/metadata/manifest.json'},checksums:{snapshot:'intake/SHA256SUMS'}},raw_files:[{path:'raw/kicad/sample.kicad_pcb',bytes:20},{path:'raw/gerber/sample.gbr',bytes:30}]},cursor_review:{status:'NOT_RUN',reason:'NO_REVIEW_ATTACHED_TO_THIS_PUBLICATION',scope:'AT_GENERATION'},datasets:[data,{id:'client:second',label:'Second',sources:[],evidence:[],qualification:'Unknown',intent:'Unknown',qualification_data:{records:[],comparisons:[]}}]}};
 for(const title of ['Storage & indexes','Cases']){const b=new Element('button');b.textContent=title;nav.append(b);}
 vm.runInContext('initIngestion(scene)',context);const panel=nav.following;
 assert.deepEqual(nav.children.map(e=>e.textContent),['Datasets / Ingestion','Storage & indexes','Cases']);
 assert.equal(panel.hidden,false,'Datasets / Ingestion is the default landing view');
 const missingStages=descend(panel,n=>n.className==='ingestion-related')[0];missingStages.open=true;missingStages.ontoggle();
 assert.match(panel.textContent,/No custody\/extraction stage receipts are linked/);
 assert.match(panel.textContent,/Cursor review at generation: NOT_RUN/);assert.doesNotMatch(panel.textContent,/CHANNEL_UNAVAILABLE/);
 assert.equal(descend(panel,n=>n.tag==='tr'&&n.dataset.persistenceLayer).length,5);
 assert.match(panel.textContent,/Not implemented for this client/);
 assert.equal(descend(panel,n=>n.tag==='svg').length,0,'Persistence is the initial client view');
 descend(panel,n=>n.tag==='button'&&n.textContent==='Inspect saved inputs')[0].onclick();
 assert.match(panel.textContent,/Preserved inputs · 2 raw files/);
 assert.equal(descend(panel,n=>n.tag==='a'&&n._text==='Sealed manifest ↗')[0].href,'intake/metadata/manifest.json');
 descend(panel,n=>n.tag==='button'&&n.textContent==='Inspect registration')[0].onclick();
 assert.equal(descend(panel,n=>n.tag==='a'&&n._text==='Open the published file registry ↗')[0].href,'registry.json');
 descend(panel,n=>n.tag==='button'&&n.textContent==='Inspect saved review')[0].onclick();
 assert.equal(descend(panel,n=>n.tag==='a'&&n._text==='Download original scene.json')[0].href,'scene.json');
 assert.equal(descend(panel,n=>n.className==='ingestion-saved-record').length,2);
 const next=descend(panel,n=>n.dataset.reviewDirection==='next')[0];
 const previous=descend(panel,n=>n.dataset.reviewDirection==='previous')[0];
 assert.equal(previous.disabled,true);
 assert.deepEqual(descend(panel,n=>n.className==='ingestion-story-nav')[0].children.map(n=>n.children[0]._text),['Stored on disk','Input findings']);
 next.onclick();assert.match(panel.textContent,/View 2 of 2 · Input findings/);assert.equal(next.disabled,true);
 assert.equal(descend(panel,n=>n.className==='eyebrow'&&n._text.startsWith('View '))[0].scrolled,'start');
 assert.equal(descend(panel,n=>n.className==='ingestion-related').length,1);
 assert.doesNotMatch(panel.textContent,/What the input comparisons establish/,'Qualification detail should load only when opened');
 previous.onclick();assert.match(panel.textContent,/View 1 of 2 · Stored on disk/);
 chapter(panel,'Input findings').onclick();
 const panes=descend(panel,n=>n.tag==='svg');const native=panes.find(p=>p.dataset.pane==='native'),source=panes.find(p=>p.dataset.pane==='source'),delta=panes.find(p=>p.dataset.pane==='delta');
 assert.equal(native.children.length,1);assert.equal(native.children[0].attrs.d,data.qualification_data.comparisons[0].native_path);assert.equal(source.children.length,1);assert.equal(source.children[0].attrs.d,data.qualification_data.comparisons[0].source_path);assert.equal(delta.children.length,2);assert.equal(delta.children[0].attrs.d,data.qualification_data.comparisons[0].source_only_path);
 assert.match(panel.textContent,/Source-only flashes: 7/);assert.match(panel.textContent,/1\.234 mm²/);assert.match(panel.textContent,/matched hits 123/);assert.match(panel.textContent,/position tolerance 0\.009 mm/);
 const technical=descend(panel,n=>n.tag==='details'&&n.className==='ingestion-evidence')[0];
 assert.ok(technical);assert.notEqual(technical.open,true);
 assert.equal(panes.length,3,'Only the selected comparison should be drawn');
 assert.match(panel.textContent,/7 plotted flashes occur only/);
 const results=descend(panel,n=>n.className==='ingestion-related')[0];results.open=true;results.ontoggle();
 assert.match(panel.textContent,/What the input comparisons establish/);
 assert.match(panel.textContent,/Gerber-to-KiCad conversion has no verified tool/);
 assert.doesNotMatch(panel.textContent,/Generated result|Test a cut trace|Test a copper bridge|Recorded pad-move/);
 assert.equal(descend(panel,n=>n.tag==='svg').length,3,'Input findings must not add a correction visualization');
 results.ontoggle();assert.equal(descend(panel,n=>n.tag==='h3'&&n._text==='What the input comparisons establish').length,1,'Repeated toggles should not duplicate qualification');
 data.qualification_data.records[1].metrics.source_only_flash_count=9;data.qualification_data.records[2].metrics.PTH.drills.matched=321;
 let select=descend(panel,n=>n.tag==='select')[0];select.value=data.id;select.onchange();chapter(panel,'Input findings').onclick();assert.match(panel.textContent,/Source-only flashes: 9/);assert.match(panel.textContent,/9 plotted flashes occur only/);assert.match(panel.textContent,/matched hits 321/);
 select=descend(panel,n=>n.tag==='select')[0];select.value='client:second';select.onchange();assert.match(panel.textContent,/NOT_AVAILABLE/);assert.doesNotMatch(panel.textContent,/Source-only flashes:|matched hits|R140\.1|4,894/);
 assert.deepEqual(descend(panel,n=>n.className==='ingestion-story-nav')[0].children.map(n=>n.children[0]._text),['Stored on disk','Input findings']);
 assert.equal(descend(panel,n=>n.tag==='tr'&&n.dataset.persistenceLayer).length,5);
 chapter(panel,'Input findings').onclick();
 assert.match(panel.textContent,/comparison views: Not available in this registration/);
 assert.match(panel.textContent,/Drill correspondence: Not recorded/);
 assert.equal(descend(panel,n=>n.tag==='svg').length,0,'Sparse datasets must not inherit client comparison geometry');
 assert.doesNotMatch(panel.textContent,/L2GND|R140|Gerber-to-KiCad conversion has no verified tool|matched hits/);
 const second=context.scene.ingestion.datasets[1];
 const nativePipeline={label:'Second',source_sha256:'native-hash',catalog_revision:'revision',evidence:{snapshot:'pipeline.json'},source_evidence:{snapshot:'native.kicad_pcb'},stages:[{stage:'source_custody',state:'COMPLETE',counts:{source_bytes:20}},{stage:'inventory',state:'PARTIAL',counts:{source_objects:7}},{stage:'persistence',state:'COMPLETE',counts:{stored_objects:7,stored_relation_occurrences:8}}],inventory_counts:{source_objects:7,geometry_available:5},query_samples:[{}],catalog_query_examples:[{}]};
 context.scene.pipeline={datasets:[nativePipeline,{...nativePipeline,source_sha256:'unrelated-hash',stages:[{stage:'persistence',state:'COMPLETE',counts:{stored_objects:777}}]}]};
 chapter(panel,'Stored on disk').onclick();
 assert.match(descend(panel,n=>n.dataset.persistenceLayer==='Board-record materialization')[0].textContent,/Not linked/,'Matching a label is not enough to bind a native revision');
 second.sources=[{path:'source.kicad_pcb',sha256:'native-hash'}];
 chapter(panel,'Stored on disk').onclick();
 assert.match(descend(panel,n=>n.dataset.persistenceLayer==='Board-record materialization')[0].textContent,/Recorded · 1 revision/);
 const inputStages=descend(panel,n=>n.className==='ingestion-related')[0];inputStages.open=true;inputStages.ontoggle();
 assert.deepEqual(descend(panel,n=>n.dataset.inputStage).map(n=>n.dataset.inputStage),['source_custody','inventory']);
 assert.match(panel.textContent,/Extract the native inventory · PARTIAL/);
 assert.doesNotMatch(panel.textContent,/unrelated-hash/);
 descend(panel,n=>n.tag==='button'&&n._text==='Inspect recorded objects')[0].onclick();
 assert.match(panel.textContent,/Stored objects: 7/);assert.doesNotMatch(panel.textContent,/Stored objects: 777/);
 assert.equal(descend(panel,n=>n.tag==='a'&&n._text==='Open bound pipeline record ↗')[0].href,'pipeline.json');
 descend(panel,n=>n.tag==='button'&&n._text==='Inspect recorded samples')[0].onclick();
 assert.match(panel.textContent,/A reopen receipt is not linked/);
 context.location={hash:'#dataset=client%3Asecond'};vm.runInContext('initIngestion(scene)',context);
 assert.equal(nav.following.hidden,false);assert.equal(descend(nav.following,n=>n.tag==='select')[0].value,'client:second');
 assert.doesNotMatch(nav.following.textContent,/Client persistence · what is stored/);
 context.scene.ingestion.datasets=[];vm.runInContext('initIngestion(scene)',context);
 assert.match(nav.following.textContent,/No datasets registered/);
 assert.equal(descend(nav.following,n=>n.tag==='select')[0].disabled,true);
 return {status:'PASS',checks:['Pure source/native panes; differences confined to delta','Receipt-driven changed comparison/drill values; no cross-dataset leakage','Generation review metadata without a fabricated channel status','Technical records collapsed and only one comparison drawn','Input qualification retains unknowns without a duplicated correction visualization','Direct dataset links open the requested review','Persistence first: five statuses and three artifact inspectors; no cross-dataset leakage','Two primary tabs; qualification loads once; forward/back reveals the new context','Sparse datasets share the layout without inherited client findings or zero measurements','Native revisions bind by exact source hash, never label alone','Recorded query samples do not imply linked reopen proof','Top navigation order and default dataset landing','Input stage receipts retain actual states and exact source binding; unavailable receipts stay explicit']};
}
module.exports={run,Element,descend};
if(require.main===module)console.log(JSON.stringify(run()));

async function savedRecordChecks(){
 const context=vm.createContext({document:{createElement:t=>new Element(t)},fetch:async()=>({ok:true,json:async()=>({status:'PASS',outputs:[{path:'index.html'}]})})});
 const source=fs.readFileSync(path.join(__dirname,'../../web/ingestion_views.js'),'utf8').replace('return { init };','return { init, savedRecord };');
 vm.runInContext(source,context);
 const make=vm.runInContext('ingestionUI.savedRecord',context);
 const scene=make('scene.json','Open saved scene.json',{geometry:'x'.repeat(3000),rows:Array.from({length:30},(_,i)=>i)});
 scene.open=true;await scene.ontoggle();
 const sections=descend(scene,n=>n.tag==='details').slice(1);
 for(const section of sections){section.open=true;section.ontoggle();}
 assert.match(scene.textContent,/preview truncated/);assert.doesNotMatch(scene.textContent,/x{2001}/);
 assert.equal(descend(scene,n=>n.tag==='a')[0].download,'scene.json');
 const receipt=make('receipt.json','Open publication receipt.json',{});receipt.open=true;await receipt.ontoggle();
 const status=descend(receipt,n=>n.tag==='details'&&n.children[0]?._text==='status')[0];status.open=true;status.ontoggle();
 assert.match(receipt.textContent,/PASS/);
 context.fetch=async()=>({ok:false,status:404});
 const missing=make('receipt.json','Open publication receipt.json',{});missing.open=true;await missing.ontoggle();assert.match(missing.textContent,/HTTP 404/);
 context.fetch=async()=>({ok:true,json:async()=>({status:'PASS'})});await missing.ontoggle();assert.doesNotMatch(missing.textContent,/Unable to load/);
 return {status:'PASS',checks:['bounded scene preview','receipt fetch and display','HTTP failure and retry','original file download retained']};
}
module.exports.savedRecordChecks=savedRecordChecks;

if(require.main===module)savedRecordChecks().then(result=>console.log(JSON.stringify(result))).catch(error=>{console.error(error);process.exitCode=1;});
