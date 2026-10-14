const assert=require('node:assert/strict');
const fs=require('node:fs');
const {projectReplay,executionAvailable}=require('../../web/replay_model.js');
const scene=JSON.parse(fs.readFileSync('out/visual/run_20261014T171718_143371Z/scene.json','utf8'));
const c=scene.cases.find(c=>c.id==='synthetic');
const untouched=JSON.stringify(scene);
for(const id of ['computed','disconnected_n1']){
 const record=c.states.find(s=>s.id===id);
 for(let i=0;i<record.replay.length;i++){
  const p=projectReplay(c,record,i);
  // Controls repeatedly consume the same projection, without switching to final.
  for(const control of ['pan','zoom','layer','mode','selection','resize']){
   assert.deepEqual(projectReplay(c,record,i),p,control);
  }
  if(i===0){assert.equal(p.state.metrics.P1_center_mm[0],20.35);assert.equal(p.state.candidate_verdict,'NOT_RUN');assert.deepEqual(p.state.layers,c.states[0].layers);}
  else if(i===record.replay.length-1){assert.equal(p.state,record);}
  else{assert.deepEqual(p.state.layers,{});assert.deepEqual(p.state.objects,[]);assert.deepEqual(p.state.metrics,{});assert.equal(p.state.candidate_verdict,'NOT_AVAILABLE');}
 }
 const missing=projectReplay(c,{...record,execution:null},0);
 assert.equal(executionAvailable({...record,execution:null}),false);
 assert.equal(executionAvailable({...record,execution:{evidence:{}}}),false);
 assert.equal(missing.state.candidate_verdict,'NOT_AVAILABLE');
 assert.deepEqual(missing.state.layers,{});
}
assert.equal(JSON.stringify(scene),untouched);
console.log('PASS accepted/rejected event projections, repeated consumers, unavailable evidence, scene immutability');
