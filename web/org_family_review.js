/* Read-only browser for one receipt-bound ORG family-map projection. */
function orgFamilyReviewBounds(rows,pad=.2){
 const boxes=rows.map(r=>r.geometry?.bounds_mm).filter(b=>Array.isArray(b)&&b.length===4);
 if(!boxes.length)return [0,0,1,1];
 const x0=Math.min(...boxes.map(b=>b[0])),y0=Math.min(...boxes.map(b=>b[1]));
 const x1=Math.max(...boxes.map(b=>b[2])),y1=Math.max(...boxes.map(b=>b[3]));
 const p=Math.max(pad,Math.max(x1-x0,y1-y0)*.12);
 return [x0-p,y0-p,Math.max(x1-x0+2*p,.05),Math.max(y1-y0+2*p,.05)];
}
const ORG_FAMILY_RESOURCE_LIMIT_BYTES=64*1024*1024;
const ORG_FAMILY_SHA256=/^[0-9a-f]{64}$/;
async function orgFamilySha256(bytes){return Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),b=>b.toString(16).padStart(2,'0')).join('');}
async function orgFamilyValidateGeometryPaths(paths,bindings,mode){
 if(!paths||typeof paths!=='object'||Array.isArray(paths)||!bindings||typeof bindings!=='object'||Array.isArray(bindings))throw new Error('Geometry path binding is missing.');
 const keys=Object.keys(paths);if(keys.length!==Object.keys(bindings).length||keys.some(key=>!Object.prototype.hasOwnProperty.call(bindings,key)))throw new Error('Geometry path set differs from its bindings.');
 const digestKey=mode==='stored'?'stored_path_sha256':'simplified_path_sha256';
 for(const key of keys){const path=paths[key],binding=bindings[key];if(typeof path!=='string'||!path.trim()||binding?.source_wkb_sha256!==key||binding?.derivation!=='pcb-org-svg-path/v1'||!ORG_FAMILY_SHA256.test(binding?.[digestKey]||''))throw new Error('Geometry path source binding is invalid.');
  const actual=await orgFamilySha256(new TextEncoder().encode(path));if(actual!==binding[digestKey])throw new Error((mode==='stored'?'Stored':'Simplified')+' geometry path hash mismatch.');
 }
 return true;
}
async function orgFamilyReadBoundedResponse(response,label){
 const declared=response.headers?.get?.('content-length');
 if(declared!==null&&declared!==undefined&&declared!==''&&Number.isFinite(Number(declared))&&Number(declared)>ORG_FAMILY_RESOURCE_LIMIT_BYTES)
  throw new Error(label+' exceeds the 64 MiB resource budget.');
 if(response.body?.getReader){
  const reader=response.body.getReader(),chunks=[];let total=0;
  try{while(true){const {done,value}=await reader.read();if(done)break;total+=value.byteLength;if(total>ORG_FAMILY_RESOURCE_LIMIT_BYTES){await reader.cancel();throw new Error(label+' exceeds the 64 MiB resource budget.');}chunks.push(value);}}
  finally{reader.releaseLock?.();}
  const bytes=new Uint8Array(total);let offset=0;for(const chunk of chunks){bytes.set(chunk,offset);offset+=chunk.byteLength;}return bytes;
 }
 const bytes=new Uint8Array(await response.arrayBuffer());
 if(bytes.byteLength>ORG_FAMILY_RESOURCE_LIMIT_BYTES)throw new Error(label+' exceeds the 64 MiB resource budget.');
 return bytes;
}
function orgFamilyResolvePhysicalGroup(group,data,geometryPaths){
 const fail=reason=>({ok:false,reason});
 if(group?.inspection_status!=='COMPLETE')return fail('Group is not marked complete.');
 if(typeof data.binding?.org_revision!=='string'||typeof data.binding?.org_source_sha256!=='string')return fail('Pinned ORG source identity is missing.');
 const ids=group.source_member_ids,count=group.source_member_count;
 if(!Array.isArray(ids)||!Number.isInteger(count)||count<1||count>100||ids.length!==count||ids.some(id=>typeof id!=='string')||new Set(ids).size!==count)
  return fail('Group member IDs are missing, duplicated, or inconsistent with the declared count.');
 const records=[];
 for(const id of ids){
  const object=data.source_objects?.[id];
  if(!object||object.object_id!==id)return fail('A group source ID does not resolve to the same object identity.');
  if(object.source_revision!==data.binding?.org_revision||object.source_sha256!==data.binding?.org_source_sha256)
   return fail('A group object is bound to a different ORG source revision.');
  if(!Number.isInteger(object.source_span?.[0])||!Number.isInteger(object.source_span?.[1])||object.source_span[0]<0||object.source_span[1]<=object.source_span[0])
   return fail('A group object has an invalid ORG source byte span.');
  if(!group.layer||!Array.isArray(object.layers)||!object.layers.includes(group.layer))
   return fail('A group object does not match the declared layer.');
  const bounds=object.bounds_mm,path=geometryPaths?.[object.geometry_sha256];
  const geometryBinding=data.geometry_bindings?.[object.geometry_sha256];
  if(!object.geometry_sha256||!geometryBinding||geometryBinding.source_wkb_sha256!==object.geometry_sha256||typeof path!=='string'||!path.trim()||!Array.isArray(bounds)||bounds.length!==4||!bounds.every(Number.isFinite))
   return fail('A group object is missing drawable geometry or finite bounds.');
  records.push(object);
 }
 return {ok:true,records};
}
function orgFamilyReviewRoleColor(role){
 if(role==='local_land_candidate_seed')return '#e3b34f';
 if(role==='incident_trace'||role==='uncertain_trace_contact')return role==='incident_trace'?'#56a4d8':'#e786a2';
 if(role==='F.Mask_feature_candidate'||role==='F.Mask_unsupported_feature_candidate')return '#39b8c8';
 if(role==='F.Paste_feature_candidate'||role==='F.Paste_unsupported_feature_candidate')return '#a987c8';
 return '#98a8b4';
}
async function renderOrgFamilyReview(scene,panel,initialDatasetId,onBack){
 const maps=scene.ingestion?.org_family_maps||{};
 const ids=Object.keys(maps).sort();
 const el=(tag,value,cls)=>{const n=document.createElement(tag);if(value!==undefined)n.textContent=String(value);if(cls)n.className=cls;return n;};
 const ns='http://www.w3.org/2000/svg',cache=new Map(),storedPathCache=new Map();
 let datasetId=ids.includes(initialDatasetId)?initialDatasetId:ids[0];
 let data=null,selectedFamily=null,selectedMember=null,selectedExcluded=null,search='',page=0,epoch=0,memberSearch='',memberFilter='all',memberPage=0,excludedSearch='',excludedPage=0,geometryMode='simplified',storedPaths=null;
 const short=value=>String(value||'').slice(0,18)+'…';
 const panelRoot=el('div',undefined,'org-family-review');
 const toolbar=el('div',undefined,'toolbar');
 const back=el('button','← Storage & indexes');back.type='button';back.onclick=onBack;toolbar.append(back);
 toolbar.append(el('strong','ORG family hypotheses · read-only'));
 const datasetSelect=el('select');datasetSelect.setAttribute('aria-label','ORG family map dataset');
 for(const id of ids){const option=el('option',scene.ingestion.datasets.find(d=>d.id===id)?.label||id);option.value=id;datasetSelect.append(option);}
 datasetSelect.value=datasetId;datasetSelect.onchange=()=>{datasetId=datasetSelect.value;selectedFamily=null;selectedMember=null;selectedExcluded=null;storedPaths=null;geometryMode='simplified';page=0;load();};toolbar.append(datasetSelect);
 const status=el('p','Loading hash-bound inspection projection…','org-family-status');
 panelRoot.append(toolbar,status);panel.replaceChildren(panelRoot);

 async function getData(id){
  if(cache.has(id))return cache.get(id);
  const binding=maps[id];
  if(!binding?.snapshot||!binding?.projection_sha256)throw new Error('No receipt-bound ORG family projection for this dataset.');
  const response=await fetch(binding.snapshot,{cache:'no-store',credentials:'same-origin'});
  if(!response.ok)throw new Error('Could not load saved ORG family review projection ('+response.status+').');
  const bytes=await orgFamilyReadBoundedResponse(response,'Review projection');
  const hash=await orgFamilySha256(bytes);
  if(hash!==binding.projection_sha256)throw new Error('Review projection checksum does not match this publication.');
  const parsed=JSON.parse(new TextDecoder().decode(bytes));
  if(parsed.schema!=='pcb-org-family-review-projection/3')throw new Error('Unsupported ORG review projection schema: '+String(parsed.schema));
  const identityFields=['dataset_id','map_revision','map_content_sha256','org_revision','org_source_sha256'];
  if(identityFields.some(key=>parsed.binding?.[key]!== (key==='dataset_id'?id:binding[key])))
   throw new Error('Review projection identity differs from the selected pinned map.');
  await orgFamilyValidateGeometryPaths(parsed.geometry_paths,parsed.geometry_bindings,'simplified');
  if(!parsed.stored_geometry_paths_ref?.snapshot||!parsed.stored_geometry_paths_ref?.sha256)
   throw new Error('Stored-geometry fallback is not bound in this projection.');
  cache.set(id,parsed);return parsed;
 }
 async function getStoredPaths(){
  if(storedPaths)return storedPaths;
  if(storedPathCache.has(datasetId)){storedPaths=storedPathCache.get(datasetId);return storedPaths;}
  const binding=data.stored_geometry_paths_ref;
  const response=await fetch(binding.snapshot,{cache:'no-store',credentials:'same-origin'});
  if(!response.ok)throw new Error('Could not load pinned stored-geometry paths ('+response.status+').');
  const bytes=await orgFamilyReadBoundedResponse(response,'Stored-geometry resource');
  const hash=await orgFamilySha256(bytes);
  if(hash!==binding.sha256)throw new Error('Stored-geometry path checksum does not match this publication.');
  const parsed=JSON.parse(new TextDecoder().decode(bytes));
  const keys=Object.keys(data.geometry_paths||{});
  if(!parsed||typeof parsed!=='object'||Array.isArray(parsed)||keys.length!==binding.geometry_count||Object.keys(parsed).length!==binding.geometry_count||keys.some(key=>typeof parsed[key]!=='string'||!parsed[key].trim()))
   throw new Error('Stored-geometry path set differs from the pinned projection.');
  await orgFamilyValidateGeometryPaths(parsed,data.geometry_bindings,'stored');
  storedPaths=parsed;storedPathCache.set(datasetId,parsed);return parsed;
 }
 function stat(title,value,note){const box=el('div',undefined,'org-family-stat');box.append(el('small',title),el('strong',value),el('span',note));return box;}
 function safePath(object){const key=object?.geometry_sha256;if(!key)return null;return geometryMode==='stored'?storedPaths?.[key]:data.geometry_paths?.[key];}
 function geometryModeDescription(){const spec=data.display_geometry||{},frame=`Coordinates are ${spec.coordinate_unit||'source'} with ${spec.coordinate_transform||'declared source transform'}; polygon rings use ${spec.path_fill_rule||'declared'} fill. `;return geometryMode==='stored'?frame+`Stored WKB geometry · no geometric simplification · SVG coordinates rounded to ${spec.stored_coordinate_decimals||9} decimal places (maximum per-axis rounding ${spec.stored_coordinate_rounding_bound_mm||0.0000000005} mm). This is the exact persisted geometry payload, not the original KiCad source bytes.`:frame+`Simplified inspection path · ${spec.simplification_parameter_mm||0.00005} mm simplification parameter · ${spec.simplified_coordinate_decimals||5}-decimal SVG coordinates. This parameter is not a maximum-error guarantee.`;}
 function seedFor(member){return member.source_refs.find(r=>r.role==='local_land_candidate_seed');}
 function memberFor(key){return data.members.find(m=>m.member_key===key);}
 function familyFor(key){return data.families.find(f=>f.family_key===key);}
 function sourceRef(member,role){return member.source_refs.filter(r=>r.role===role);}
 function displayRole(member,ref){return (member.trace_associations?.uncertain_associations||[]).some(a=>a.object_id===ref.object_id)?'uncertain_trace_contact':ref.role;}
 function familyStatusCounts(){
  return data.members.reduce((counts,member)=>{const key=member.family_membership_status||'UNKNOWN';counts[key]=(counts[key]||0)+1;return counts;},{});
 }
 function refocus(label){
  const visit=node=>{if(node.getAttribute?.('aria-label')===label)return node;for(const child of node.children||[]){const found=visit(child);if(found)return found;}return null;};
  const input=visit(panelRoot);input?.focus?.();const end=input?.value?.length;if(Number.isInteger(end))input.setSelectionRange?.(end,end);
 }
 function drawOverview(svg,family){
  const rows=family.member_keys.map(memberFor).filter(Boolean),view=orgFamilyReviewBounds(rows,.08);
  svg.setAttribute('viewBox',view.join(' '));svg.setAttribute('role','img');
  svg.setAttribute('aria-label','ORG F.Cu candidate sites in selected provisional family');
  const bg=document.createElementNS(ns,'rect');for(const [k,v] of Object.entries({x:view[0],y:view[1],width:view[2],height:view[3],fill:'#f5f8fa'}))bg.setAttribute(k,String(v));svg.append(bg);
  for(const member of rows){const ref=seedFor(member),obj=ref&&data.source_objects[ref.object_id],path=safePath(obj);if(!path)continue;
   const p=document.createElementNS(ns,'path');p.setAttribute('d',path);p.setAttribute('fill','#d8a943');p.setAttribute('fill-rule','evenodd');p.setAttribute('fill-opacity',member.member_key===selectedMember?.member_key?'.95':'.58');
   p.setAttribute('stroke',member.member_key===selectedMember?.member_key?'#163f5a':'#896516');p.setAttribute('stroke-width',member.member_key===selectedMember?.member_key?'.025':'.012');
   p.setAttribute('tabindex','0');p.setAttribute('role','button');p.setAttribute('aria-label','Select member at '+member.geometry.center_mm.map(v=>Number(v).toFixed(3)).join(', ')+' mm');
   p.onclick=()=>{selectedMember=member;renderBody();};p.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();selectedMember=member;renderBody();}};svg.append(p);
  }
 }
 function drawMember(svg,member){
  const refs=member.source_refs.map(r=>({ref:{...r,role:displayRole(member,r)},obj:data.source_objects[r.object_id]})).filter(x=>x.obj?.bounds_mm&&safePath(x.obj));
  const boxes=refs.map(x=>({geometry:{bounds_mm:x.obj.bounds_mm}})),view=orgFamilyReviewBounds(boxes,.08);
  svg.setAttribute('viewBox',view.join(' '));svg.setAttribute('role','img');svg.setAttribute('aria-label','Selected ORG candidate and its referenced source geometry');
  const bg=document.createElementNS(ns,'rect');for(const [k,v]of Object.entries({x:view[0],y:view[1],width:view[2],height:view[3],fill:'#f5f8fa'}))bg.setAttribute(k,String(v));svg.append(bg);
  const order={incident_trace:1,uncertain_trace_contact:2,'F.Mask_feature_candidate':3,'F.Mask_unsupported_feature_candidate':3,'F.Paste_feature_candidate':4,'F.Paste_unsupported_feature_candidate':4,local_land_candidate_seed:5};
  for(const {ref,obj} of refs.sort((a,b)=>(order[a.ref.role]||0)-(order[b.ref.role]||0))){const p=document.createElementNS(ns,'path');p.setAttribute('d',safePath(obj));
   const color=orgFamilyReviewRoleColor(ref.role),reference=ref.role.startsWith('F.Mask')||ref.role.startsWith('F.Paste');
   p.setAttribute('fill',reference?'none':color);p.setAttribute('fill-rule','evenodd');p.setAttribute('fill-opacity',ref.role==='local_land_candidate_seed'?'.95':'.72');p.setAttribute('stroke',color);p.setAttribute('stroke-width',ref.role==='local_land_candidate_seed'?'.025':'.012');
   if(ref.role==='uncertain_trace_contact'||reference)p.setAttribute('stroke-dasharray','.04 .025');svg.append(p);
  }
 }
 function drawPhysicalGroup(svg,member,rows){
  const refs=new Map(member.source_refs.map(ref=>[ref.object_id,displayRole(member,ref)]));
  const drawable=rows.map(obj=>({obj,path:safePath(obj)})).filter(row=>row.obj?.bounds_mm&&row.path);
  const boxes=drawable.map(row=>({geometry:{bounds_mm:row.obj.bounds_mm}})),view=orgFamilyReviewBounds(boxes,.08);
  svg.setAttribute('viewBox',view.join(' '));svg.setAttribute('role','img');
  svg.setAttribute('aria-label','Complete ORG physical contact group geometry');
  const bg=document.createElementNS(ns,'rect');for(const [k,v]of Object.entries({x:view[0],y:view[1],width:view[2],height:view[3],fill:'#f5f8fa'}))bg.setAttribute(k,String(v));svg.append(bg);
  for(const {obj,path} of drawable){const role=refs.get(obj.object_id),color=role?orgFamilyReviewRoleColor(role):'#899aa5';
   const p=document.createElementNS(ns,'path');p.setAttribute('d',path);p.setAttribute('fill',color);p.setAttribute('fill-rule','evenodd');p.setAttribute('fill-opacity',role==='local_land_candidate_seed'?'.96':'.72');p.setAttribute('stroke',color);p.setAttribute('stroke-width',role==='local_land_candidate_seed'?'.025':'.012');
   if(role==='uncertain_trace_contact')p.setAttribute('stroke-dasharray','.04 .025');svg.append(p);
  }
 }
 function renderBody(){
  if(!data)return;
  const family=selectedFamily&&familyFor(selectedFamily);if(family&&!family.member_keys.includes(selectedMember?.member_key))selectedMember=memberFor(family.member_keys[0]);
  const content=el('div');
  const caveat=el('p','These are ORG-derived geometric hypotheses. A candidate is one source primitive, a family is a provisional repetition pattern, and a physical group is connected copper under the stored predicate. None establishes pad/net identity, manufacturing purpose, or permission to edit.','org-family-boundary');content.append(caveat);
  const stats=el('div',undefined,'org-family-stats');stats.append(
   stat('Candidate members',data.members.length,'single-primitive hypotheses'),
   stat('Provisional families',data.families.length,'overlap is retained'),
   stat('Physical groups',data.physical_groups.length,'distinct from families'),
   stat('ORG source revision',short(data.binding.org_revision),'SHA-256 '+short(data.binding.org_source_sha256)));
  content.append(stats);
  const coverage=data.coverage||{},membership=familyStatusCounts(),references=coverage.reference_association_statuses||{};
  const inventory=Number(coverage.source_object_count||0),projected=Number(data.projection_counts?.map_referenced_source_object_count||Object.keys(data.source_objects||{}).length);
  const geometryCount=Number(data.projection_counts?.map_referenced_geometry_path_count||Object.keys(data.geometry_paths||{}).length),displayCoverage=el('section',undefined,'org-family-coverage');
  displayCoverage.append(el('h2','Coverage and display limits'));
  displayCoverage.append(el('p',`${projected.toLocaleString()} unique ORG source objects are referenced by this map, from ${inventory.toLocaleString()} inventoried source records (${inventory?((100*projected/inventory).toFixed(1)+'%'): 'denominator unavailable'}). This is map-reference coverage, not board geometry or land-recognition completeness.`));
  const simplification=Number(data.display_geometry?.simplification_parameter_mm||0.0005);
  displayCoverage.append(el('p',`${geometryCount.toLocaleString()} distinct geometry paths are shared by map-referenced objects. The review also provides direct access to ${data.excluded_features.length.toLocaleString()} excluded F.Cu source shapes; those are additional to map-reference counts. Simplified paths use a ${simplification.toFixed(4)} mm parameter, not a guaranteed maximum source-to-display deviation. The display does not qualify contact, clearance, or boundary semantics.`));
  const groupSourceCount=Number(data.projection_counts?.group_inspection_additional_source_object_count||0),smallGroupCount=Number(data.projection_counts?.group_inspection_group_count||0);
  displayCoverage.append(el('p',`Complete object drawings are available for ${smallGroupCount.toLocaleString()} physical-contact groups of at most 100 objects; these expose ${groupSourceCount.toLocaleString()} additional source objects beyond member evidence. Larger components remain summarized by count and type.`));
  const coverageList=el('ul');
  const coverageRows=[
   ['No family hypothesis',membership.NO_FAMILY_HYPOTHESIS||0],
   ['One provisional family hypothesis',membership.ONE_PROVISIONAL_FAMILY_HYPOTHESIS||0],
   ['Multiple provisional family hypotheses',membership.AMBIGUOUS_MULTIPLE_FAMILY_HYPOTHESES||0],
   ['Excluded filled F.Cu polygons',coverage.seed_exclusions?.NOT_FOUR_DISTINCT_RECTANGLE_VERTICES||0],
   ['Uncertain near-trace associations',coverage.trace_associations?.uncertain_trace_associations||0],
   ['Unsupported F.Mask features',Object.values(coverage.reference_feature_exclusions?.['F.Mask']||{}).reduce((a,b)=>a+b,0)],
   ['Unsupported F.Paste features',Object.values(coverage.reference_feature_exclusions?.['F.Paste']||{}).reduce((a,b)=>a+b,0)],
   ['F.Mask unique / unmatched',`${references['F.Mask:UNIQUE_GEOMETRIC_CANDIDATE']||0} / ${references['F.Mask:UNMATCHED']||0}`],
   ['F.Paste unique / unmatched',`${references['F.Paste:UNIQUE_GEOMETRIC_CANDIDATE']||0} / ${references['F.Paste:UNMATCHED']||0}`]
  ];
  for(const [label,value] of coverageRows){const row=el('li');row.append(el('strong',label+': '),el('span',value));coverageList.append(row);}
  displayCoverage.append(coverageList);content.append(displayCoverage);

  const geometryControls=el('section',undefined,'org-family-geometry-mode');geometryControls.append(el('h2','Display geometry'),el('p',geometryModeDescription()));
  const modeButtons=el('div',undefined,'org-family-geometry-controls');modeButtons.setAttribute('role','group');modeButtons.setAttribute('aria-label','Choose ORG display geometry');
  for(const [mode,label] of [['simplified','Simplified inspection'],['stored','Stored WKB · unsimplified']]){const button=el('button',label);button.type='button';button.setAttribute('aria-pressed',String(geometryMode===mode));button.onclick=async()=>{try{if(mode==='stored'){status.textContent='Verifying stored geometry paths…';await getStoredPaths();}geometryMode=mode;renderBody();}catch(error){geometryMode='simplified';status.textContent='NOT_AVAILABLE · '+error.message;}};modeButtons.append(button);}
  geometryControls.append(modeButtons);content.append(geometryControls);

  const excludedBrowser=el('section',undefined,'org-family-excluded');excludedBrowser.append(el('h2','Excluded F.Cu source features'),el('p',`${data.excluded_features.length.toLocaleString()} source features excluded from candidate-member recognition. These stay selectable here with their exact ORG source identity and reason; selection does not add them to the map.`));
  const excludedSearchBox=el('input');excludedSearchBox.type='search';excludedSearchBox.placeholder='Search source ID, byte span, or exclusion reason';excludedSearchBox.setAttribute('aria-label','Search excluded ORG source features');excludedSearchBox.value=excludedSearch;excludedSearchBox.oninput=()=>{excludedSearch=excludedSearchBox.value.toLowerCase();excludedPage=0;renderBody();refocus('Search excluded ORG source features');};excludedBrowser.append(excludedSearchBox);
  const matchingExcluded=data.excluded_features.filter(item=>(item.object_id+' '+item.source_span.join(' ')+' '+item.exclusion_reason).toLowerCase().includes(excludedSearch));
  const excludedPageSize=20,excludedPages=Math.max(1,Math.ceil(matchingExcluded.length/excludedPageSize));excludedPage=Math.min(excludedPage,excludedPages-1);
  excludedBrowser.append(el('p',`${matchingExcluded.length.toLocaleString()} matching excluded features · page ${excludedPage+1} of ${excludedPages}`));
  const excludedList=el('div',undefined,'org-family-excluded-list');excludedList.setAttribute('aria-label','Excluded ORG source feature results');
  for(const item of matchingExcluded.slice(excludedPage*excludedPageSize,(excludedPage+1)*excludedPageSize)){const button=el('button',undefined,'org-family-excluded-feature');button.type='button';button.setAttribute('aria-pressed',String(selectedExcluded===item.object_id));button.setAttribute('aria-label',`Inspect excluded F.Cu source bytes ${item.source_span.join(' to ')} · ${item.exclusion_reason}`);button.append(el('strong',`F.Cu · ${item.kind} · bytes ${item.source_span.join('–')}`),el('span',`${item.exclusion_reason} · area ${Number(item.area_mm2||0).toFixed(6)} mm²`));button.onclick=()=>{selectedExcluded=item.object_id;selectedMember=null;selectedFamily=null;renderBody();};excludedList.append(button);}
  excludedBrowser.append(excludedList);
  const excludedPagination=el('div',undefined,'org-family-pagination'),excludedPrev=el('button','Previous excluded features'),excludedNext=el('button','Next excluded features');excludedPrev.disabled=excludedPage===0;excludedPrev.onclick=()=>{excludedPage--;renderBody();};excludedNext.disabled=excludedPage+1>=excludedPages;excludedNext.onclick=()=>{excludedPage++;renderBody();};excludedPagination.append(excludedPrev,el('span',`Page ${excludedPage+1} / ${excludedPages}`),excludedNext);excludedBrowser.append(excludedPagination);content.append(excludedBrowser);

  const memberBrowser=el('section',undefined,'org-family-browser');
  memberBrowser.append(el('h2','Browse all candidate members'),el('p','This list includes members with no family hypothesis and members retained in multiple hypotheses. Select one to inspect its exact ORG references and associated evidence.'));
  const filters=el('div',undefined,'org-family-browser-controls'),membershipSelect=el('select');membershipSelect.setAttribute('aria-label','Filter members by family membership');
  for(const [value,label] of [['all','All candidates'],['none','No family hypothesis'],['one','One family hypothesis'],['multiple','Multiple family hypotheses']]){const option=el('option',label);option.value=value;membershipSelect.append(option);}
  membershipSelect.value=memberFilter;membershipSelect.onchange=()=>{memberFilter=membershipSelect.value;memberPage=0;renderBody();};
  const memberSearchBox=el('input');memberSearchBox.type='search';memberSearchBox.placeholder='Search member key, coordinates, or source span';memberSearchBox.setAttribute('aria-label','Search candidate members');memberSearchBox.value=memberSearch;memberSearchBox.oninput=()=>{memberSearch=memberSearchBox.value.toLowerCase();memberPage=0;renderBody();refocus('Search candidate members');};filters.append(membershipSelect,memberSearchBox);memberBrowser.append(filters);
  const byFilter=data.members.filter(m=>memberFilter==='none'?m.candidate_family_keys.length===0:memberFilter==='one'?m.candidate_family_keys.length===1:memberFilter==='multiple'?m.candidate_family_keys.length>1:true);
  const matchingMembers=byFilter.filter(m=>{const seed=seedFor(m),object=seed&&data.source_objects[seed.object_id];return (m.member_key+' '+m.geometry.center_mm.join(' ')+' '+(object?.source_span||[]).join(' ')+' '+m.geometry.shape_signature.primitive).toLowerCase().includes(memberSearch);});
  const memberPageSize=25,memberPages=Math.max(1,Math.ceil(matchingMembers.length/memberPageSize));memberPage=Math.min(memberPage,memberPages-1);
  memberBrowser.append(el('p',`${matchingMembers.length.toLocaleString()} matching members · page ${memberPage+1} of ${memberPages}`));
  const memberOptions=el('div',undefined,'org-family-members');memberOptions.setAttribute('aria-label','All ORG candidate members');
  for(const m of matchingMembers.slice(memberPage*memberPageSize,(memberPage+1)*memberPageSize)){const button=el('button',undefined,'org-family-member');button.type='button';button.setAttribute('aria-pressed',String(m.member_key===selectedMember?.member_key));button.append(el('strong',`${m.geometry.center_mm.map(v=>Number(v).toFixed(3)).join(', ')} mm`),el('span',`${m.geometry.shape_signature.primitive} · ${m.family_membership_status} · ${short(m.member_key)}`));button.onclick=()=>{selectedMember=m;selectedExcluded=null;selectedFamily=m.candidate_family_keys[0]||null;renderBody();};memberOptions.append(button);}
  memberBrowser.append(memberOptions);
  const memberPagination=el('div',undefined,'org-family-pagination'),memberPrev=el('button','Previous member results'),memberNext=el('button','Next member results');memberPrev.disabled=memberPage===0;memberPrev.onclick=()=>{memberPage--;renderBody();};memberNext.disabled=memberPage+1>=memberPages;memberNext.onclick=()=>{memberPage++;renderBody();};memberPagination.append(memberPrev,el('span',`Page ${memberPage+1} / ${memberPages}`),memberNext);memberBrowser.append(memberPagination);content.append(memberBrowser);
  const selectGrid=el('div',undefined,'org-family-columns');const familyPane=el('section',undefined,'org-family-pane'),detailPane=el('section',undefined,'org-family-pane');selectGrid.append(familyPane,detailPane);content.append(selectGrid);
  familyPane.append(el('h2','1 · Choose a pattern hypothesis'),el('p','Search by family key prefix, seed shape, or nominal trace-contact count.'));const searchBox=el('input');searchBox.type='search';searchBox.placeholder='Search family or shape';searchBox.setAttribute('aria-label','Search provisional families');searchBox.value=search;searchBox.oninput=()=>{search=searchBox.value.toLowerCase();page=0;renderBody();refocus('Search provisional families');};familyPane.append(searchBox);
  const filtered=data.families.filter(f=>(f.family_key+' '+f.shape_signature.primitive+' '+f.nominal_trace_contact_count).toLowerCase().includes(search));
  const pageSize=20,pages=Math.max(1,Math.ceil(filtered.length/pageSize));page=Math.min(page,pages-1);
  familyPane.append(el('p',filtered.length+' matching hypotheses · '+(filtered.length?`showing ${page*pageSize+1}–${Math.min((page+1)*pageSize,filtered.length)}`:'none')));
  for(const familyRow of filtered.slice(page*pageSize,(page+1)*pageSize)){const button=el('button',undefined,'org-family-choice');button.type='button';button.setAttribute('aria-pressed',String(selectedFamily===familyRow.family_key));button.append(el('strong',familyRow.shape_signature.primitive+' · '+familyRow.member_keys.length+' members'),el('span',familyRow.nominal_trace_contact_count+' nominal trace contacts · '+short(familyRow.family_key)));button.onclick=()=>{selectedExcluded=null;selectedFamily=familyRow.family_key;selectedMember=memberFor(familyRow.member_keys[0]);renderBody();};familyPane.append(button);}
  const pagination=el('div',undefined,'org-family-pagination');const prev=el('button','Previous');prev.disabled=page===0;prev.onclick=()=>{page--;renderBody();};const next=el('button','Next');next.disabled=page+1>=pages;next.onclick=()=>{page++;renderBody();};pagination.append(prev,el('span','Page '+(page+1)+' / '+pages),next);familyPane.append(pagination);

  if(!family){detailPane.append(el('h2','2 · Family hypothesis'),el('p','This member has no family hypothesis. Select a family hypothesis to inspect repeated displacement evidence and supporting pairs.'));}
  else {
   const heading=el('div',undefined,'org-family-detail-head'),headingText=el('div');headingText.append(el('h2','2 · Family hypothesis'),el('p',family.shape_signature.primitive+' · '+family.member_keys.length+' candidate members · '+family.nominal_trace_contact_count+' nominal trace contacts per member'));heading.append(headingText);
   detailPane.append(heading);
   const overview=document.createElementNS(ns,'svg');overview.classList.add('org-family-overview');drawOverview(overview,family);detailPane.append(overview,el('p','Selected family sites on F.Cu · X right, Y down · mm. The selected site is outlined; other sites are members of this same hypothesis.'));
   detailPane.append(el('p','Pattern rule: '+family.family_rule+'. Locality '+family.locality_radius_mm+' mm; displacement bucket '+family.vector_tolerance_mm+' mm. This rule is uncalibrated.'),el('p','Supporting displacement pairs: '+family.support_pairs.length+' · '+JSON.stringify(family.canonical_displacement_mm)+' mm.'));
   const memberList=el('div',undefined,'org-family-members');memberList.setAttribute('aria-label','Candidate members in family');
   for(const key of family.member_keys){const m=memberFor(key),seed=seedFor(m),obj=data.source_objects[seed?.object_id];const button=el('button',undefined,'org-family-member');button.type='button';button.setAttribute('aria-pressed',String(m.member_key===selectedMember?.member_key));button.append(el('strong',m.geometry.center_mm.map(v=>Number(v).toFixed(3)).join(', ')+' mm'),el('span',m.geometry.shape_signature.primitive+' · '+m.trace_associations.nominal_contacts.length+' contacts · '+m.family_membership_status));button.onclick=()=>{selectedMember=m;renderBody();};memberList.append(button);}
  detailPane.append(el('h3','Members · select one to inspect source identities and display geometry'),memberList);
  }
  const selectedPane=el('section',undefined,'org-family-selected');
  if(selectedMember){
   const m=selectedMember;selectedPane.append(el('h2','3 · Inspect the selected ORG member'),el('p','Candidate status: '+m.status+' · '+m.family_membership_status));
   const local=document.createElementNS(ns,'svg');local.classList.add('org-family-member-view');drawMember(local,m);selectedPane.append(local,el('p','Gold: seed primitive · blue: nominal trace contact · pink dashed: uncertain near-contact · cyan outline: F.Mask geometric candidate · purple outline: F.Paste geometric candidate. '+geometryModeDescription()+' The saved records retain measured predicates and statuses.'));
   const memberships=el('div',undefined,'org-family-membership-links');memberships.append(el('h3','Family hypotheses for this member'));
   if(m.candidate_family_keys.length){for(const key of m.candidate_family_keys){const linked=familyFor(key);const button=el('button',`${short(key)} · ${linked?.member_keys.length||0} members`);button.type='button';button.onclick=()=>{selectedFamily=key;page=Math.max(0,Math.floor(data.families.findIndex(x=>x.family_key===key)/20));renderBody();};memberships.append(button);}}
   else memberships.append(el('p','None. This member remains inspectable as a standalone candidate.'));
   selectedPane.append(memberships);
   const group=m.physical_group,groupDetails=el('details',undefined,'org-family-group-inspection');
   const groupCheck=group?.inspection_status==='COMPLETE'?orgFamilyResolvePhysicalGroup(group,data,geometryMode==='stored'?storedPaths:data.geometry_paths):null;
   const groupMembers=groupCheck?.ok?groupCheck.records:[],groupCount=group?.source_member_count??'unknown';
   groupDetails.append(el('summary','Physical-contact group · '+groupCount+' F.Cu source objects · '+(groupCheck?.ok?'complete group view':groupCheck?'integrity check failed':'summary only')));
   groupDetails.append(el('p','Group key '+short(group?.physical_group_key)+' · '+(group?.predicate||'predicate unavailable')+'. This connected component is separate from a candidate member, family, or electrical net.'));
   if(groupCheck?.ok){
    const groupSvg=document.createElementNS(ns,'svg');groupSvg.classList.add('org-family-group-view');drawPhysicalGroup(groupSvg,m,groupMembers);groupDetails.append(groupSvg,el('p',`${groupMembers.length}/${groupCount} source objects and geometries are shown. Gold marks this member seed; blue marks its recorded trace contacts; grey marks other objects in the same connected component.`));
    const inventory=el('details');inventory.append(el('summary','All source objects in this connected group ('+groupMembers.length+')'));
    for(const obj of groupMembers){const row=el('p',`${obj.kind} · ${(obj.layers||[]).join(', ')} · bytes ${(obj.source_span||[]).join('–')} · ${obj.object_id}`);inventory.append(row);}
    groupDetails.append(inventory);
   }else{
    const kinds=Object.entries(group?.source_member_kind_counts||{}).map(([kind,count])=>`${kind}: ${count}`).join(' · ');
    groupDetails.append(el('p',groupCheck?`Group integrity check failed: ${groupCheck.reason}`:`This component is too large for a local drawing or contains geometry outside this projection (${kinds||'kind counts unavailable'}). Its exact membership remains in the pinned family-map revision.`));
   }
   selectedPane.append(groupDetails);
   const refs=el('details');refs.open=true;refs.append(el('summary','Source identities and recorded evidence ('+m.source_refs.length+' references)'));
   for(const ref of m.source_refs){const object=data.source_objects[ref.object_id]||{};const role=el('details');role.append(el('summary',displayRole(m,ref)+' · '+object.kind+' · '+(object.layers||[]).join(', ')),el('p','ORG source revision: '+ref.source_revision),el('p','Exact source object ID: '+ref.object_id),el('p','Source byte span: '+(object.source_span||[]).join('–')),el('p','Geometry SHA-256: '+(object.geometry_sha256||'NOT_AVAILABLE')));refs.append(role);}
   selectedPane.append(refs);
   for(const layer of ['F.Mask','F.Paste']){const association=m.reference_features[layer];selectedPane.append(el('p',layer+' association: '+association.status+' · '+association.candidates.length+' supported candidates · '+association.unsupported_candidates.length+' unsupported features. Geometric match only; purpose is not inferred.'));}
  } else if(selectedExcluded){
   const item=data.excluded_features.find(row=>row.object_id===selectedExcluded),object=data.source_objects[selectedExcluded];
   selectedPane.append(el('h2','Inspect excluded ORG source geometry'),el('p','This source shape is excluded from candidate-member recognition under the recorded reason below. It is shown here for review, not added to a family map or member record.'));
   const view=document.createElementNS(ns,'svg');view.classList.add('org-family-member-view');const selectedObject={geometry_sha256:item.geometry_sha256,bounds_mm:object.bounds_mm};
   view.setAttribute('viewBox',orgFamilyReviewBounds([{geometry:{bounds_mm:object.bounds_mm}}],.08).join(' '));view.setAttribute('role','img');view.setAttribute('aria-label','Selected excluded ORG source geometry');
   const box=orgFamilyReviewBounds([{geometry:{bounds_mm:object.bounds_mm}}],.08),bg=document.createElementNS(ns,'rect');for(const [key,value]of Object.entries({x:box[0],y:box[1],width:box[2],height:box[3],fill:'#f5f8fa'}))bg.setAttribute(key,String(value));view.append(bg);
   const path=document.createElementNS(ns,'path');path.setAttribute('d',safePath(selectedObject));path.setAttribute('fill','#e786a2');path.setAttribute('fill-rule','evenodd');path.setAttribute('fill-opacity','.65');path.setAttribute('stroke','#9c3558');path.setAttribute('stroke-width','.012');view.append(path);selectedPane.append(view,el('p','Geometry mode: '+geometryModeDescription()));
   selectedPane.append(el('p','Exclusion reason: '+item.exclusion_reason),el('p','Exact ORG source object ID: '+item.object_id),el('p','ORG source revision: '+item.source_revision),el('p','Source SHA-256: '+item.source_sha256),el('p','Source byte span: '+item.source_span.join('–')),el('p','Stored geometry SHA-256: '+item.geometry_sha256),el('p','Stored filled area: '+Number(item.area_mm2||0).toFixed(9)+' mm²'));
  } else selectedPane.append(el('h2','3 · Inspect the selected ORG member'),el('p','Choose a family, member, or excluded source feature to inspect its source geometry and recorded evidence.'));
  content.append(selectedPane);
  const provenance=el('details');provenance.append(el('summary','Pinned ORG and map identities'),el('pre',JSON.stringify({dataset_id:data.binding.dataset_id,org_revision:data.binding.org_revision,org_source_sha256:data.binding.org_source_sha256,map_revision:data.binding.map_revision,map_content_sha256:data.binding.map_content_sha256,input_snapshot_id:data.binding.input_snapshot_id,projection_sha256:maps[datasetId].projection_sha256,coverage:data.coverage},null,2)));content.append(provenance);
  content.append(el('p',data.display_limitations.join(' '),'org-family-limitations'));
  panelRoot.replaceChildren(toolbar,status,content);
  status.textContent='Projection hash verified · map revision '+short(data.binding.map_revision)+' · read-only inspection';
 }
 async function load(){
  const my=++epoch;status.textContent='Loading hash-bound inspection projection…';
  try{const next=await getData(datasetId);if(my!==epoch)return;data=next;if(!selectedFamily)selectedFamily=data.families[0]?.family_key||null;selectedMember=selectedFamily?memberFor(familyFor(selectedFamily).member_keys[0]):null;renderBody();}
  catch(error){if(my!==epoch)return;status.textContent='NOT_AVAILABLE · '+error.message;}
 }
 await load();
}
