/* One immutable event projection for every viewer consumer. No inferred snapshots. */
(function(root){
 function executionAvailable(record){const e=record.execution?.evidence;return !!(e&&typeof e.snapshot==='string'&&e.snapshot&&/^[a-f0-9]{64}$/.test(e.sha256));}
 function projectReplay(c,record,index){
  const events=record.replay||[];
  if(!events.length)return {state:record,note:'Stored validation snapshot; no execution replay',event:null};
  const event=events[index];
  if(!executionAvailable(record))return unavailable('Execution evidence unavailable');
  if(index===events.length-1)return {state:record,note:'Final retained snapshot · '+event,event};
  if(event==='PLANNED'){
   const original=c.states[0];
   return {state:{...original,candidate_verdict:'NOT_RUN',checks:[],pairs:[],control_test:null,
    metrics:{...original.metrics,candidate_exposed_mm2:record.metrics?.before_exposed_mm2}},
    note:'REPLAY · source before candidate creation · original retained snapshot',event};
  }
  return unavailable('Intermediate geometry and event-time measurements were not retained');
  function unavailable(reason){return {state:{...record,layers:{},delta:{},objects:[],pairs:[],checks:[],metrics:{},candidate_verdict:'NOT_AVAILABLE',control_test:null},note:'REPLAY · '+reason,event:event||null};}
 }
 root.projectReplay=projectReplay;root.executionAvailable=executionAvailable;
 if(typeof module!=='undefined')module.exports={projectReplay,executionAvailable};
})(typeof globalThis!=='undefined'?globalThis:this);
