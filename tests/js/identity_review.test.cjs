const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');

class Element {
 constructor(tag){this.tag=tag;this.children=[];this.dataset={};this.attrs={};this.classList={add(){},toggle(){}};this.value='';this.disabled=false;this._text='';}
 set textContent(value){this._text=String(value);this.children=[];}
 get textContent(){return this._text+' '+this.children.map(x=>x.textContent||'').join(' ');}
 append(...items){this.children.push(...items);}
 replaceChildren(...items){this.children=items;}
 setAttribute(key,value){this.attrs[key]=value;}
}
function descend(node,predicate){return [node,...node.children.flatMap(x=>descend(x,predicate))].filter(predicate);}

async function run(){
 const entries=Array.from({length:13},(_,i)=>({review_class:i===12?'candidate':'exact',review_id:String(i),
  kind:'segment',layer:'F.Cu',before_identity:'a'.repeat(64)+':bytes:'+i+':'+(i+1),after_identity:'b'.repeat(64)+':bytes:'+i+':'+(i+1),image_file:'pair-'+i+'.svg',
  before_width_mm:.2,after_width_mm:i===0?.35:.2,stroke_width_changed:i===0,keypoint_displacement_mm:i===12?.003:undefined}));
 const document={createElement:tag=>new Element(tag)};
 const roundPairs=[{before_identity:'a'.repeat(64)+':bytes:100:120',after_identity:'b'.repeat(64)+':bytes:200:220',before_radius_mm:.15,after_radius_mm:.18,center_displacement_mm:.0002,added_area_mm2:.015},{before_identity:'a'.repeat(64)+':bytes:300:320',after_identity:'b'.repeat(64)+':bytes:400:420',before_radius_mm:.15,after_radius_mm:.2,center_displacement_mm:.0005,added_area_mm2:.03}];
 const groupManifest={scope:'representative copper-neighborhoods',round_feature_pairs:roundPairs,registration:{inlier_count:219,fitted_after_to_before:{translation_mm:[0,0],rotation_radians:0},max_inlier_residual_mm:0,tolerance_mm:.001},trace_polygon_correspondence:{trace_graph_accounting:{unmatched_before_identities:['a'.repeat(64)+':bytes:150:160'],unmatched_after_identities:['b'.repeat(64)+':bytes:160:170']},polygon_graph_accounting:{unmatched_before_identities:['a'.repeat(64)+':bytes:180:190'],unmatched_after_identities:['b'.repeat(64)+':bytes:190:200']},trace_summary:{relation_component_count:2,one_to_one_full_coverage_count:1,one_to_one_partial_coverage_count:0,one_to_many_count:1,many_to_one_count:0,many_to_many_ambiguous_count:0,unmatched_before_count:4,unmatched_after_count:5,excluded_invalid_after_count:2},trace_relations:[{relation_id:'trace-000001',status:'one_to_one_geometric_candidate',before_identities:['a'.repeat(64)+':bytes:10:20'],after_identities:['b'.repeat(64)+':bytes:30:40'],candidate_edges:[{before_identity:'a'.repeat(64)+':bytes:10:20',after_identity:'b'.repeat(64)+':bytes:30:40',before_length_mm:1,after_length_mm:1.01,before_covered_fraction:1,after_covered_fraction:.99,before_width_mm:.2,after_width_mm:.3,width_delta_mm:.1}]},{relation_id:'trace-000002',status:'partial_geometric_correspondence_candidate',before_identities:['a'.repeat(64)+':bytes:50:60'],after_identities:['b'.repeat(64)+':bytes:70:80','b'.repeat(64)+':bytes:90:100'],candidate_edges:[]}],polygon_summary:{relation_component_count:1,one_to_one_full_coverage_count:0,one_to_one_partial_coverage_count:1,one_to_many_count:0,many_to_one_count:0,many_to_many_ambiguous_count:0,unmatched_before_count:1,unmatched_after_count:2},polygon_relations:[{relation_id:'polygon-000001',status:'partial_geometric_correspondence_candidate',before_identities:['a'.repeat(64)+':bytes:110:120'],after_identities:['b'.repeat(64)+':bytes:130:140'],candidate_edges:[{before_identity:'a'.repeat(64)+':bytes:110:120',after_identity:'b'.repeat(64)+':bytes:130:140',before_area_mm2:.2,after_area_mm2:.3,area_delta_mm2:.1,before_covered_fraction:1,after_covered_fraction:.67}]}]},groups:[{group_id:'copper-01',title:'Round-feature and trace neighborhood',center_mm:[12.1,-15.5],pair_count:3,kind_counts:{arc:2,segment:1},image_file:'copper-group-01.svg',members:[]}]};
 groupManifest.groups.push({group_id:'copper-03',title:'Round-feature and trace neighborhood',center_mm:[13.1,-16.5],pair_count:4,kind_counts:{arc:1,segment:3},image_file:'copper-group-03.svg',members:[]});
 groupManifest.groups.push({group_id:'copper-05',title:'Round-feature and trace neighborhood',center_mm:[15.1,-18.5],pair_count:2,kind_counts:{arc:1,segment:1},image_file:'copper-group-05.svg',members:[]});
 const footprint={status:'MEASURED',before_copper_area_mm2:.2,after_copper_area_mm2:.3,signed_area_delta_mm2:.1,symmetric_difference_area_mm2:.12,before_covered_fraction:.8,after_covered_fraction:.533333};
 groupManifest.trace_polygon_correspondence.trace_summary.copper_footprint_metrics_available=2;
 groupManifest.trace_polygon_correspondence.polygon_summary.copper_footprint_metrics_available=1;
 groupManifest.trace_polygon_correspondence.trace_copper_footprint_method={model:'round buffer',arc_centerline_max_chord_error_mm:.00001,buffer_rounding_max_sagitta_mm:.00001};
 groupManifest.trace_polygon_correspondence.trace_relations[0].copper_footprint_comparison=footprint;
 groupManifest.trace_polygon_correspondence.trace_relations[0].candidate_edges[0].copper_footprint_comparison=footprint;
 groupManifest.trace_polygon_correspondence.polygon_relations[0].copper_footprint_comparison=footprint;
 groupManifest.trace_polygon_correspondence.polygon_relations[0].candidate_edges[0].copper_footprint_comparison=footprint;
 const context=vm.createContext({document,fetch:async(url)=>({ok:true,json:async()=>String(url)==='groups.json'?groupManifest:{entries}})});
 const src=fs.readFileSync(path.join(__dirname,'../../web/ingestion_views.js'),'utf8').replace('return { init };','return { init, appendIdentityReview };');
 vm.runInContext(src,context);
 const ui=vm.runInContext('ingestionUI',context);const root=new Element('div');
 ui.appendIdentityReview(root,{id:'dataset'}, {ingestion:{identity_reviews:{dataset:{manifest:{snapshot:'identity_reviews/x/manifest.json'},images_root:'identity_reviews/x/images',groups_manifest:{snapshot:'groups.json'},group_images_root:'groups',screenshot_evidence:[
  {id:'org-screenshot',label:'User-provided ORG before crop',snapshot:'evidence/before.png'},
  {id:'org-overlay',label:'ORG full-copper crop fit',snapshot:'evidence/org.png'},
  {id:'edit-screenshot',label:'User-provided EDIT after crop',snapshot:'evidence/after.png'},
  {id:'edit-overlay',label:'EDIT full-copper crop fit',snapshot:'evidence/edit.png'},
  {id:'org-centers',label:'ORG detected crop landmarks',snapshot:'evidence/org-centers.png'},
  {id:'edit-centers',label:'EDIT detected crop landmarks',snapshot:'evidence/edit-centers.png'},
  {id:'org-runner-up',label:'ORG runner-up crop fit',snapshot:'evidence/org-runner-up.png'},
  {id:'edit-runner-up',label:'EDIT runner-up crop fit',snapshot:'evidence/edit-runner-up.png'},
  {id:'joint-pairs',label:'Geometric pairs',snapshot:'evidence/pairs.csv'},
  {id:'pair-closure',label:'Pair closure',snapshot:'evidence/pair-closure.json'},
  {id:'sensitivity',label:'Sensitivity report',snapshot:'evidence/sensitivity.json'}
 ],group_summary:{screenshot_candidate_review:{status:'LOCAL_CROP_MATCH_SUPPORTED',exact_screenshot_match:'LOCAL_CROP_MATCH_SUPPORTED; SEMANTIC_OBJECT_IDENTITY_NOT_ESTABLISHED',method:'Full-shape F.Cu geometry mask search.',priority_group_ids:['copper-01'],rationales:{'copper-01':'Top full-shape crop candidate.'},joint_pair_closure:{status:'PASS',pair_count:16},limits:{ORG_iou:.852,ORG_runner_up_iou:.472,EDIT_iou:.915,EDIT_runner_up_iou:.674,ORG_landmarks_associated:42,ORG_landmarks_detected:42,EDIT_landmarks_associated:16,EDIT_landmarks_detected:46,EDIT_landmarks_not_associated_by_this_check:30,registered_circle_pairs_seen_in_both:16,exact_joint_identity:'UNPROVEN',global_uniqueness:'UNPROVEN',ORG_runner_up_bounds_mm:[3.2858,-15.6871,6.5081,-12.976],EDIT_runner_up_bounds_mm:[3.5768,-5.5345,6.4656,-3.1345]},joint_pairs:[
  {ORG_source_identity:'a'.repeat(64)+':bytes:1540101:1540225',EDIT_source_identity:'b'.repeat(64)+':bytes:242561:242685',ORG_source_center_mm:'[1.613, -13.729]',EDIT_source_center_mm:'[1.613, -13.729]',ORG_residual_mm:'0.019414',EDIT_residual_mm:'0.016196'},
  {ORG_source_identity:'a'.repeat(64)+':bytes:1540228:1540352',EDIT_source_identity:'b'.repeat(64)+':bytes:242688:242812',ORG_source_center_mm:'[1.641, -14.077]',EDIT_source_center_mm:'[1.641, -14.077]',ORG_residual_mm:'0.012434',EDIT_residual_mm:'0.017194'}
 ],limitations:['Global uniqueness remains UNPROVEN.']}}}}}});
 await new Promise(resolve=>setTimeout(resolve,0));
 assert.equal(descend(root,x=>x.className==='copper-group-card').length,3);
 assert.match(root.textContent,/Both crops match local F\.Cu geometry; they point to the same board neighborhood as a candidate/);
 assert.match(root.textContent,/Crop overlap scores · ORG 0\.852 \(next 0\.472\) · EDIT 0\.915 \(next 0\.674\)/);
 assert.match(root.textContent,/42\/42 detected ORG maxima; 16\/46 detected EDIT maxima associated/);
 assert.match(root.textContent,/30 EDIT maxima are unmatched by this check; that does not show missing or changed copper/);
 assert.match(root.textContent,/Source-reference check · 16 shared pairs validated against unique registered circles and both crop bounds \(PASS\)/);
 assert.match(root.textContent,/How the crop fit was produced/);
 assert.match(root.textContent,/What these results do not establish/);
 assert.match(root.textContent,/global uniqueness remains UNPROVEN/i);
 assert.match(root.textContent,/Candidate 1 · copper-01/);
 assert.match(root.textContent,/First center-supported review candidate/);
 assert.ok(root.textContent.indexOf('Candidate 1 · copper-01')<root.textContent.indexOf('Candidate 2 · copper-03'));
 assert.ok(root.textContent.indexOf('Screenshot correspondence · visual candidates')<root.textContent.indexOf('Candidate 1 · copper-01'));
 assert.match(root.textContent,/Other 2 source-derived neighborhoods available for review/);
 assert.equal(descend(root,x=>x.tag==='img'&&x.src==='evidence/org.png').length,1);
 assert.equal(descend(root,x=>x.tag==='img'&&x.src==='evidence/edit.png').length,1);
 assert.equal(descend(root,x=>x.tag==='img'&&x.src==='evidence/before.png').length,1);
 assert.equal(descend(root,x=>x.tag==='img'&&x.src==='evidence/after.png').length,1);
 assert.equal(descend(root,x=>x.tag==='img'&&x.src==='evidence/org-runner-up.png').length,1);
 assert.equal(descend(root,x=>x.tag==='img'&&x.src==='evidence/edit-runner-up.png').length,1);
 assert.match(root.textContent,/runner-up fits and repeated-pattern alternatives/);
 assert.match(root.textContent,/bounds \[3\.286, -15\.687, 6\.508, -12\.976\] mm/);
 assert.equal(descend(root,x=>x.tag==='tr').length,3);
 assert.equal(descend(root,x=>x.tag==='td'&&/bytes 1540101–1540225/.test(x.textContent)).length,1);
 assert.equal(descend(root,x=>x.tag==='a'&&x._text==='Download pair evidence CSV ↗')[0].href,'evidence/pairs.csv');
 assert.equal(descend(root,x=>x.tag==='a'&&x._text==='Open complete fit, scramble and sensitivity report ↗')[0].href,'evidence/sensitivity.json');
 assert.equal(descend(root,x=>x.tag==='a'&&x._text==='Open source-bound pair closure report ↗')[0].href,'evidence/pair-closure.json');
 assert.match(root.textContent,/F.Mask shape landmarks only/);
 assert.match(root.textContent,/Registration result: 219 mutual-unique F.Mask landmarks/);
 assert.match(root.textContent,/EDIT→ORG shift \(0\.000000, 0\.000000\) mm/);
 assert.equal(descend(root,x=>x.tag==='a'&&x._text==='Open registration and complete correspondence records ↗')[0].href,'groups.json');
 assert.equal(descend(root,x=>x.tag==='img'&&x.src==='groups/copper-group-01.svg').length,1);
 assert.equal(descend(root,x=>x.className==='identity-review-all-pairs').length,1);
 assert.equal(descend(root,x=>x.className==='copper-round-pairs').length,1);
 assert.equal(descend(root,x=>x.tag==='li'&&/disk-area delta/.test(x.textContent)).length,2);
 const roundFilter=descend(root,x=>x.tag==='input'&&x.attrs['aria-label']==='Filter registered round-feature pairs')[0];
 roundFilter.value='bytes:300';roundFilter.oninput();
 assert.equal(descend(root,x=>x.tag==='li'&&/disk-area delta/.test(x.textContent)).length,1);
 assert.match(root.textContent,/1 of 2 registered round-feature pairs/);
 assert.equal(descend(root,x=>x.className==='identity-review-card').length,12);
 assert.match(root.textContent,/13 pairs · 12 unique anchor links · 1 near-geometry candidates/);
 assert.match(root.textContent,/2 overlap components/);
 assert.match(root.textContent,/Trace gate: 1 one-to-one with ≥90% coverage on both sides; 0 partial one-to-one; 1 one-to-many/);
 assert.match(root.textContent,/Component-union copper footprint: 0\.200000 → 0\.300000 mm²/);
 assert.match(root.textContent,/footprint symmetric difference 0\.120000 mm²/);
 assert.match(root.textContent,/Separate footprint metrics: 2\/2 trace components and 1\/1 polygon components/);
 assert.match(root.textContent,/Polygon gate: 0 one-to-one with ≥90% coverage on both sides; 1 partial one-to-one/);
 assert.match(root.textContent,/area 0\.200000 → 0\.300000 mm² · delta 0\.100000 mm²/);
 const traceFilter=descend(root,x=>x.tag==='input'&&x.attrs['aria-label']==='Filter F.Cu trace centerlines correspondence')[0];
 traceFilter.value='bytes:50';traceFilter.oninput();
 assert.equal(descend(root,x=>x.tag==='li'&&/trace-000002/.test(x.textContent)).length,1);
 assert.match(root.textContent,/1 of 2 overlap components/);
 assert.match(root.textContent,/ORG a{12}… · bytes 0–1/);
 const unmatchedFilter=descend(root,x=>x.tag==='input'&&x.attrs['aria-label']==='Filter no-candidate F.Cu trace source identity')[0];
 unmatchedFilter.value='bytes:150:160';unmatchedFilter.oninput();
 assert.equal(descend(root,x=>x.tag==='li'&&/bytes:150:160/.test(x.textContent)).length,1);
 assert.match(root.textContent,/1 matching source identities/);
 const img=descend(root,x=>x.tag==='img'&&x.src==='identity_reviews/x/images/pair-0.svg')[0];assert.ok(img);assert.equal(img.loading,'lazy');
 const next=descend(root,x=>x.tag==='button'&&x._text==='Next pairs')[0];next.onclick();
 assert.equal(descend(root,x=>x.className==='identity-review-card').length,1);
 const filter=descend(root,x=>x.tag==='select')[0];filter.value='candidate';filter.onchange();
 assert.equal(descend(root,x=>x.className==='identity-review-card').length,1);
 assert.match(root.textContent,/Maximum keypoint displacement: 0.003 mm/);
 const search=descend(root,x=>x.tag==='input'&&x.attrs['aria-label']==='Search source identity')[0];search.value='does-not-exist';search.oninput();
 assert.equal(descend(root,x=>x.className==='identity-review-card').length,0);
 assert.match(root.textContent,/0 pairs/);
 return {status:'PASS',checks:['paged all-pair gallery','lazy image source binding','candidate and exact filters','identity search']};
}
if(require.main===module)run().then(x=>console.log(JSON.stringify(x))).catch(e=>{console.error(e);process.exitCode=1;});
module.exports={run};
