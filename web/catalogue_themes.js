/* Preliminary visual navigation over verified replay records. No live SQL. */
function catalogueThemeSelection(result,roles){
 const chosen=new Set(roles);if([...chosen].some(role=>!result.roles.some(r=>r.role===role)))throw Error('Unknown context role');
 const rows=result.roles.filter(r=>chosen.has(r.role)),native=new Map(),plotted=new Map();
 for(const row of rows){native.set(row.native.id,row.native);plotted.set(row.plotted.id,row.plotted);}
 const parent=result.parent_dependency,dependencies=parent&&[...native.values()].some(r=>r.parent_id===parent.id)&&!native.has(parent.id)?[parent]:[];
 return {schema:'pcb-diagnostic-selection-preview/1',mode:'BROWSER_SELECTION_FROM_VERIFIED_REPLAY',dataset_revision:result.dataset_revision,
  from_result_sha256:result.result_sha256,roles:rows,native_records:[...native.values()],gerber_records:[...plotted.values()],dependencies,
  object_count:native.size+plotted.size+dependencies.length,qualifications:result.qualifications,writable_ids:[],
  purpose:'Diagnostic manifest referencing saved source/geometry payloads. Full original artifacts remain in the linked recorded store.'};
}

function renderCatalogueThemes(scene,panel,onLegacy){
 const context=scene.common_context,result=context.result,facts=context.themes;
 const el=(tag,text)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=String(text);return e;};
 const ns='http://www.w3.org/2000/svg',short=s=>s.slice(0,12)+'…',num=v=>Number(v).toFixed(3);
 let theme='discovery',selected='R140.1',exportRoles=new Set(result.roles.map(r=>r.role));
 const titles={discovery:'Discovery',grouping:'Grouping',storage:'Storage & indexes',export:'Selective export'};
 const label=role=>role==='connected_trace'?'Connected trace':role==='mask_opening'?'Mask opening':role;
 function link(path,title){const a=el('a',title);a.href=path;a.target='_blank';a.rel='noopener';return a;}
 function details(title,value){const d=el('details');d.append(el('summary',title),el('pre',JSON.stringify(value,null,2)));return d;}
 function svgElement(tag,attrs,text){const e=document.createElementNS(ns,tag);for(const [k,v] of Object.entries(attrs||{}))e.setAttribute(k,String(v));if(text!==undefined)e.textContent=text;return e;}
 function roleButton(role,text){const b=el('button',text||label(role));b.dataset.themeRole=role;b.setAttribute('aria-pressed',String(selected===role));b.onclick=()=>{selected=role;render();};return b;}
 function tile(title,value,caption){const e=el('div');e.className='catalogue-tile';e.append(el('small',title),el('strong',value),el('p',caption));return e;}
 function grouping(){
  const svg=svgElement('svg',{viewBox:'0 0 720 410',role:'group','aria-label':'Stored ownership, contact, proximity and opening relationships'});svg.classList.add('catalogue-graph');
  const p1=result.roles.find(r=>r.role==='R140.1').native.id,p2=result.roles.find(r=>r.role==='R140.2').native.id;
  const gap=result.relationships.proximity.matches.find(r=>r.id===p2)?.distance_mm;
  const group=svgElement('rect',{x:420,y:105,width:215,height:275,rx:24,fill:'#fff3d6',stroke:'#c79535','stroke-dasharray':'7 5'});svg.append(group);
  svg.append(svgElement('text',{x:527,y:398,'text-anchor':'middle',fill:'#775420'},'Measured copper contact group'));
  function edge(x1,y1,x2,y2,color,dash,text,x,y){svg.append(svgElement('line',{x1,y1,x2,y2,stroke:color,'stroke-width':2,...(dash?{'stroke-dasharray':'6 5'}:{})}));if(text)svg.append(svgElement('text',{x,y,'text-anchor':'middle',fill:color},text));}
  edge(355,66,190,119,'#6d7790',true,'owns pad',215,91);edge(355,66,525,119,'#6d7790',true,'owns pad',495,91);
  edge(285,150,430,150,'#78839a',true,num(gap)+' mm nearby',355,135);
  edge(525,181,525,284,'#a77519',false,num(result.relationships.contact.matches.find(r=>r.id!==p1)?.distance_mm)+' mm contact',596,240);
  edge(478,181,230,284,'#168795',false,'opening_for',317,252);
  function node(role,x,y,title,caption){const g=svgElement('g',{'data-group-role':role||'parent'});const color=role===selected?'#174e73':'#f7fafc';g.append(svgElement('rect',{x:x-95,y:y-30,width:190,height:62,rx:10,fill:color,stroke:'#abbac7'}),svgElement('text',{x,y:y-4,'text-anchor':'middle',fill:role===selected?'white':'#173446','font-weight':650},title),svgElement('text',{x,y:y+17,'text-anchor':'middle',fill:role===selected?'#d6edf7':'#566a7b'},caption));if(role){g.setAttribute('role','button');g.setAttribute('tabindex','0');g.setAttribute('aria-label','Inspect '+label(role));g.onclick=()=>{selected=role;render();};g.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();selected=role;render();}};}svg.append(g);}
  node(null,355,36,result.parent_dependency.reference+' footprint','Native parent dependency');
  node('R140.2',190,150,'R140.2','Separate copper group');node('R140.1',525,150,'R140.1','Native pad ↔ Gerber flash');
  node('mask_opening',190,315,'B.Mask opening','Own Gerber source occurrence');node('connected_trace',525,315,'Connected trace','Native segment ↔ Gerber line');
  return svg;
 }
 function render(){
  panel.replaceChildren();panel.dataset.commonCatalogue='true';panel.dataset.catalogueTheme=theme;
  document.getElementById('headline').textContent='Storage & indexes · Client VME-WREN';
  document.getElementById('story').textContent='Follow one real stored context through discovery, grouping, persistence and selective export.';
  const toolbar=el('div');toolbar.className='toolbar';toolbar.append(el('b','Preliminary infrastructure view · REPLAY'));
  const selector=el('select');selector.setAttribute('aria-label','Source revision');const option=el('option','Client VME-WREN · R140 context');option.value='common';selector.append(option);
  for(const d of scene.pipeline?.datasets||[]){const o=el('option',d.label+' · retained native inspector');o.value=d.label;selector.append(o);}selector.onchange=()=>{if(selector.value!=='common')onLegacy(selector.value);};toolbar.append(selector);
  const mapIds=Object.keys(scene.ingestion?.org_family_maps||{}).sort();
  if(mapIds.length){const review=el('button','Inspect ORG family hypotheses');review.type='button';review.onclick=()=>window.openOrgFamilyReview?.(mapIds[0]);toolbar.append(review);}
  panel.append(toolbar);
  const nav=el('nav');nav.className='catalogue-theme-nav';nav.setAttribute('aria-label','Storage themes');
  const stats={discovery:facts.sqlite.counts.objects+' stored occurrences',grouping:result.relationships.topology.components.length+' copper groups',storage:facts.sqlite.counts.revisions+' artifact revisions',export:catalogueThemeSelection(result,[...exportRoles]).object_count+' objects with dependencies'};
  for(const [i,key] of Object.keys(titles).entries()){const b=el('button');b.dataset.storageTheme=key;b.setAttribute('aria-pressed',String(theme===key));b.append(el('small',String(i+1)),el('strong',titles[key]),el('span',stats[key]));b.onclick=()=>{theme=key;render();};nav.append(b);}panel.append(nav);
  const copy={discovery:['Find the same object in two sources','The preserved KiCad and Gerber files have separate identities. Each row below joins their selected occurrences through a measured match.'],grouping:['See why these records belong together','Footprint ownership, physical copper contact, nearby context and a mask association are four different relationships. Select a node to inspect its stored geometry.'],storage:['See what is durable and what is rebuilt','The dataset revision pins records, original source bytes, geometry and reports. SQLite indexes are on disk; the spatial R-tree is rebuilt from stored geometry when the catalogue reopens.'],export:['Choose the context to carry forward','Select roles to preview a diagnostic manifest. Native parent dependencies are retained automatically. No selection grants write permission.']};
  panel.append(el('h2',copy[theme][0]),el('p',copy[theme][1]));const grid=el('div');grid.className='catalogue-theme-grid';const main=el('div'),side=el('div');grid.append(main,side);panel.append(grid);
  if(theme==='discovery'){
   const table=el('table');table.setAttribute('aria-label','Native and Gerber source correspondence');const tr=el('tr');for(const t of ['Role','KiCad occurrence','Gerber occurrence'])tr.append(el('th',t));table.append(tr);
   for(const row of result.roles){const tr=el('tr'),td=el('td');td.append(roleButton(row.role));tr.append(td,el('td',row.native.kind+' · '+(row.native.reference||row.native.net_name||'board routing')),el('td',row.plotted.kind+' · '+row.plotted.layers.join(', ')));table.append(tr);}main.append(table,tile('Parent retained',result.parent_dependency.reference+' footprint','The two native pads retain their original footprint dependency.'),el('p',result.query.scope));
   main.append(details('Input artifacts, original byte identities and extracted counts',facts.artifacts));
  }else if(theme==='grouping'){
   main.append(grouping(),el('p','Schematic of relationships, not board coordinates. Dashed grey: ownership/proximity. Gold: copper contact. Cyan: mask association.'),details('Stored relation predicates and witnesses',result.relationships));
  }else if(theme==='storage'){
   const flow=el('div');flow.className='catalogue-store-flow';flow.append(tile('Pinned dataset revision',short(result.dataset_revision),'One immutable envelope binds the artifact revisions and sidecars.'));
   const stores=el('div');stores.className='catalogue-store-columns';stores.append(tile('SQLite · durable records',facts.sqlite.counts.objects+' object rows',facts.sqlite.counts.revisions+' artifact revisions · '+facts.sqlite.counts.relations+' same-artifact SQL relation rows'),tile('Files · durable payloads',facts.payloads.count+' content-addressed files',(facts.payloads.bytes/1048576).toFixed(1)+' MiB · original sources, geometry and JSON reports'));flow.append(el('div','↓'),stores,tile('Relationship sidecars',result.roles.length+' matched roles · '+result.qualifications.length+' qualifications',result.relationships.topology.relations.length+' copper-contact relation; cross-source matches and qualifications are pinned JSON payloads.'));main.append(flow);
   const indexes=facts.sqlite.indexes.filter(i=>i.sql).map(i=>i.name).join(', ');
   main.append(el('h3','Indexes have different lifetimes'),el('p','On disk: '+indexes+'. Composite primary-key indexes retain revision/object identity.'),el('p','Rebuilt on reopen: R-tree over '+facts.spatial.indexed_native_shapes+' qualified native copper shapes, followed by exact GEOS predicates.'),details('Actual database inventory, index definitions and file hashes',facts),link(facts.sqlite.path,'Inspect the copied SQLite store ↗'));
  }else{
   const checkboxes=el('div');checkboxes.className='catalogue-export-roles';for(const row of result.roles){const wrap=el('label'),input=el('input');input.type='checkbox';input.checked=exportRoles.has(row.role);input.setAttribute('aria-label','Include '+label(row.role));input.onchange=()=>{if(input.checked)exportRoles.add(row.role);else exportRoles.delete(row.role);render();};wrap.append(input,el('span',label(row.role)));checkboxes.append(wrap);}main.append(checkboxes);
   const selection=catalogueThemeSelection(result,[...exportRoles]);const stats=el('div');stats.className='catalogue-selection-counts';stats.append(tile('Native',selection.native_records.length,'Unique selected source objects'),tile('Gerber',selection.gerber_records.length,'Own plotting occurrences'),tile('Dependencies',selection.dependencies.length,'Retained parent containers'));main.append(stats,el('h3',selection.object_count+' source objects in this selection'));
   const chips=el('div');chips.className='catalogue-selection-chips';for(const row of selection.native_records.concat(selection.gerber_records,selection.dependencies)){const chip=el('span',row.representation+' · '+(row.reference&&row.pin?row.reference+'.'+row.pin:row.kind));chips.append(chip);}main.append(chips);
   const manifest={...selection,artifacts:facts.artifacts,saved_full_context_store:context.evidence.selection};
   if(selection.roles.length){const download=el('a','Download selection manifest');download.className='catalogue-download';const run=typeof window!=='undefined'&&window.location?.hostname==='127.0.0.1'?window.location.pathname.match(/\/(run-[0-9a-f]{32})\/index\.html$/)?.[1]:null;download.href=run?'/api/catalogue/selection?run='+run+'&revision='+result.dataset_revision+'&roles='+encodeURIComponent(selection.roles.map(r=>r.role).join(',')):'data:application/json;charset=utf-8,'+encodeURIComponent(JSON.stringify(manifest,null,2));download.download='r140-context-selection.json';main.append(download);}else main.append(el('p','Choose at least one role to create a manifest.'));
   main.append(el('p','The preview is composed from the verified replay. On the local server, Download resolves the selected records read-only from the pinned catalogue. Both manifests reference saved payloads. The byte-complete recorded export below contains the full four-role store.'),link(context.evidence.selection,'Recorded full-context export ↗'),details('Preview selection from recorded result',manifest));
  }
  const active=result.roles.find(r=>r.role===selected);const svg=svgElement('svg',{viewBox:[result.query.bounds_mm[0]-.1,result.query.bounds_mm[1]-.1,result.query.bounds_mm[2]-result.query.bounds_mm[0]+.2,result.query.bounds_mm[3]-result.query.bounds_mm[1]+.2].join(' '),role:'img','aria-label':'Actual saved Gerber geometry'});svg.classList.add('pipeline-svg');
  for(const row of result.roles){const p=svgElement('path',{d:context.geometry_svg[row.plotted.geometry_sha256],'fill-rule':'evenodd',fill:row.role==='mask_opening'?'none':row.role==='R140.2'?'#8b97a9':'#deb96e',stroke:row.role===selected?'white':row.role==='mask_opening'?'#67daea':'none','stroke-width':row.role===selected ? 0.035 : 0.02,opacity:theme==='export'&&!exportRoles.has(row.role) ? 0.2 : 1});p.dataset.themeGeometry=row.role;p.onclick=()=>{selected=row.role;render();};svg.append(p);}
  side.append(svg,el('p','Actual Gerber geometry · mm, Y down. White: inspected role. Cyan outline: mask. Export view dims unselected roles.'),el('h3',label(selected)),el('p',active.native.net_name?(selected==='mask_opening'?'Linked native pad net: ':'Native net annotation: ')+active.native.net_name:'No native net annotation'),el('p',active.match.witness.status+' · tolerance '+active.match.witness.tolerance_mm+' mm'),details('Source identities, exact bytes and match witness',active));
  const footer=el('div');footer.className='catalogue-theme-footer';footer.append(el('b','Reopened result · '+short(result.dataset_revision)),el('p','Recorded writer → fresh reader → exported-store reader returned the same digest. The browser shows saved execution; it does not run live SQL.'),link(context.evidence.acceptance,'Execution receipt ↗'),el('span',' · '),link(context.evidence.result,'Retrieved records ↗'),details('Qualifications remain attached to the dataset',result.qualifications),el('p',result.engineering_acceptance));panel.append(footer);
 }
 render();return true;
}
