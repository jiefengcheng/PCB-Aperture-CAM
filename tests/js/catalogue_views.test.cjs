const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const {Element,descend}=require('./ingestion_views.test.cjs');
function run(){
 const panel=new Element('div'),nodes={headline:new Element('h1'),story:new Element('p')};
 const document={getElementById:id=>nodes[id],createElement:t=>new Element(t),createElementNS:(_,t)=>new Element(t)};
 const roles=['R140.1','connected_trace','R140.2','mask_opening'].map((role,i)=>({role,native:{id:'n'+i,net_name:'NET'+i},plotted:{geometry_sha256:'g'+i,position_mm:[1+i,2],bounds_mm:[i,1,i+1,2]},match:{witness:{status:'VERIFIED_IN_SCOPE',tolerance_mm:.001,hausdorff_mm:0}}}));
 const scene={pipeline:{datasets:[{label:'Retained'}]},common_context:{result:{roles,relationships:{contact:{matches:[{distance_mm:0}]},proximity:{matches:[{id:'n2',distance_mm:.36}]}},query:{bounds_mm:[0,0,4,4],scope:'Bounded selected objects'},dataset_revision:'a'.repeat(64),result_sha256:'b'.repeat(64),qualifications:[{code:'L2GND_ROI_MISMATCH'}],selections:{},engineering_acceptance:'NOT_ESTABLISHED'},geometry_svg:{g0:'M0 0Z',g1:'M1 1Z',g2:'M2 2Z',g3:'M3 3Z'},evidence:{acceptance:'a.json',selection:'s.json',receipt:'r.json',result:'query.json'},execution:{writer_pid:1,reader_pid:2,export_reader_pid:3}}};
 let selectedLegacy;const context=vm.createContext({document,scene,panel,onLegacy:v=>selectedLegacy=v});vm.runInContext(fs.readFileSync(path.join(__dirname,'../../web/catalogue_views.js'),'utf8'),context);vm.runInContext('renderCommonCatalogue(scene,panel,onLegacy)',context);
 assert.deepEqual(descend(panel,n=>n.tag==='h2').map(n=>n._text),['1 · Find the stored records','2 · Understand the relationships','3 · Reopen the same stored revision','4 · Export this selected context']);
 assert.equal(descend(panel,n=>n.dataset.contextRole).length,4);assert.equal(descend(panel,n=>n.dataset.contextGeometry).length,4);
 assert.match(panel.textContent,/0.360 mm/);assert.match(panel.textContent,/REPLAY/);assert.match(panel.textContent,/browser shows that saved execution/);
 descend(panel,n=>n.dataset.contextRole==='mask_opening')[0].onclick();
 assert.equal(descend(panel,n=>n.dataset.contextGeometry==='mask_opening')[0].attrs.fill,'none');
 assert.equal(descend(panel,n=>n.dataset.contextGeometry==='mask_opening')[0].attrs.stroke,'#ffffff');
 assert.equal(descend(panel,n=>n.tag==='a'&&n._text==='Reopened result ↗')[0].href,'query.json');
 const selector=descend(panel,n=>n.tag==='select')[0];selector.value='Retained';selector.onchange();assert.equal(selectedLegacy,'Retained');
 return {status:'PASS',checks:['Four-step narrative; four source-bound selectable roles','Mask remains outline; selected geometry highlighted','Measured relationship values and replay boundary','Receipt links and retained native inspectors']};
}
module.exports={run};if(require.main===module)console.log(JSON.stringify(run()));
