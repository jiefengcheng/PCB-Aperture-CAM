/* Read-only comparison of explicit recorded query inputs and actual outputs. */
(function(root){
 function recordedNeighbors(dataset,id,layer,backend){
  const reference=dataset.query_samples.find(q=>q.query.object===id&&q.query.layer===layer);
  const refIds=reference?.matches.map(r=>r.id).sort();
  if(backend==='reference')return reference?{status:reference.status,complete:reference.complete,neighbors:refIds,receipt:reference,role:'Recorded Rtree candidates + GEOS exact nominal contact'}:{status:'NOT_RECORDED',complete:false,neighbors:[],role:'No reference sample retained for this object/layer'};
  const comparison=dataset.native_comparisons?.find(c=>c.layer===layer);
  if(!comparison)return {status:'NOT_RUN',complete:false,neighbors:[],role:'No qualified native materialization for this revision/layer'};
  if(!comparison.materialized_ids.includes(id))return {status:'OUTSIDE_MATERIALIZED_SCOPE',complete:false,neighbors:[],role:'Isolated/non-materialized object; inspect through reference catalog'};
  const out=comparison.query_samples.out, incoming=comparison.query_samples.in;
  if(!out?.query?.seeds.includes(id)||!incoming?.query?.seeds.includes(id))return {status:'NOT_RECORDED',complete:false,neighbors:[],role:'No explicit native query inputs retained for this object'};
  if(!out.complete||!incoming.complete)return {status:'INCOMPLETE',complete:false,neighbors:[],receipt:{out,in:incoming},role:'Partial native result; no match or engineering acceptance claim'};
  const neighbors=[...new Set([...out.records.filter(r=>r.seed===id).map(r=>r.target),...incoming.records.filter(r=>r.seed===id).map(r=>r.source)])].sort();
  const match=reference?.complete?JSON.stringify(refIds)===JSON.stringify(neighbors):null;
  return {status:match===null?'REFERENCE_NOT_RECORDED':match?'MATCH':'MISMATCH',complete:true,neighbors,match,receipt:{source_snapshot:comparison.source_snapshot,layer,out,in:incoming},evidence:comparison.evidence,role:'Recorded gfs reads + retained proof catalog · SHADOW_ONLY; no edit or acceptance authority'};
 }
 root.recordedNeighbors=recordedNeighbors;if(typeof module!=='undefined')module.exports={recordedNeighbors};
})(typeof globalThis!=='undefined'?globalThis:this);
