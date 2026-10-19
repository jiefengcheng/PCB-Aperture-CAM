/* Recorded common-catalogue retrieval. No browser writes or simulated SQL. */
function renderCommonCatalogue(scene,panel,onLegacy){
 const context=scene.common_context;if(!context)return false;
 if(context.themes&&typeof renderCatalogueThemes==='function')return renderCatalogueThemes(scene,panel,onLegacy);
 const result=context.result,el=(tag,value)=>{const e=document.createElement(tag);if(value!==undefined)e.textContent=String(value);return e;};
 let selected='R140.1';
 const short=value=>value.slice(0,16)+'…',number=value=>Number(value).toFixed(3);
 function link(path,title){const a=el('a',title);a.href=path;a.target='_blank';a.rel='noopener';return a;}
 function technical(title,value){const d=el('details');d.append(el('summary',title),el('pre',JSON.stringify(value,null,2)));return d;}
 function render(){
  document.getElementById('headline').textContent='Storage & indexes · Client VME-WREN';
  document.getElementById('story').textContent='Find records → understand their relationships → reopen the stored revision → export the selected context';
  panel.replaceChildren();panel.dataset.commonCatalogue='true';
  const toolbar=el('div');toolbar.className='toolbar';toolbar.append(el('b','Stored context · REPLAY'));
  const select=el('select');select.setAttribute('aria-label','Source revision');
  const common=el('option','Client VME-WREN · R140 context');common.value='common';select.append(common);
  for(const d of scene.pipeline?.datasets||[]){const o=el('option',d.label+' · retained native inspector');o.value=d.label;select.append(o);}
  select.onchange=()=>{if(select.value!=='common')onLegacy(select.value);};toolbar.append(select);panel.append(toolbar);
  panel.append(el('h2','1 · Find the stored records'),el('p','One persisted context: R140.1, its touching trace, nearby R140.2 and the corresponding mask opening. The original source files remain intact. This slice contains eight source occurrences, including the native footprint dependency.'));
  const grid=el('div');grid.className='pipeline-grid';const left=el('div'),right=el('div');grid.append(left,right);panel.append(grid);
  const table=el('table');table.className='ingestion-table';table.setAttribute('aria-label','Reopened R140 context');const head=el('tr');for(const title of ['Record','Source annotation','Match'])head.append(el('th',title));table.append(head);
  for(const row of result.roles){const tr=el('tr');const td=el('td'),b=el('button',row.role==='mask_opening'?'R140.1 mask opening':row.role==='connected_trace'?'Connected trace':row.role);b.dataset.contextRole=row.role;b.setAttribute('aria-pressed',String(selected===row.role));b.onclick=()=>{selected=row.role;render();};td.append(b);
   tr.append(td,el('td',row.role==='mask_opening'?'B.Mask · source .C=R140':row.native.net_name||'No net annotation'),el('td',row.match.witness.status==='VERIFIED_IN_SCOPE'?'Verified in this slice':row.match.witness.status));table.append(tr);}
  left.append(table,el('p','Select a row to inspect its geometry and source identities. Net names are source annotations; contact is measured separately.'));
  const row=result.roles.find(r=>r.role===selected),record=row.plotted;
  const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.classList.add('pipeline-svg');svg.setAttribute('role','img');svg.setAttribute('aria-label','Persisted R140 Gerber features in board millimetres');
  const bounds=result.query.bounds_mm;svg.setAttribute('viewBox',[bounds[0]-.1,bounds[1]-.1,bounds[2]-bounds[0]+.2,bounds[3]-bounds[1]+.2].join(' '));
  for(const item of result.roles){const p=document.createElementNS('http://www.w3.org/2000/svg','path');p.setAttribute('d',context.geometry_svg[item.plotted.geometry_sha256]);p.setAttribute('fill-rule','evenodd');p.setAttribute('fill',item.role==='mask_opening'?'none':item.role==='R140.2'?'#8b97a9':'#deb96e');p.setAttribute('stroke',item.role===selected?'#ffffff':item.role==='mask_opening'?'#67daea':'none');p.setAttribute('stroke-width',item.role===selected?'.035':'.02');p.dataset.contextGeometry=item.role;p.onclick=()=>{selected=item.role;render();};svg.append(p);}
  right.append(svg,el('p','Saved Gerber geometry · X right, Y down · mm. Gold: pad 1 + trace. Grey: pad 2. Cyan outline: mask opening. White outline: selected record.'));
  const position=record.position_mm?'Anchor '+record.position_mm.map(number).join(', ')+' mm':'Endpoints '+record.endpoints_mm.map(p=>p.map(number).join(', ')).join(' → ')+' mm';
  left.append(el('h3',selected==='mask_opening'?'R140.1 mask opening':selected),el('p',position),
    el('p','Bounds '+record.bounds_mm.map(number).join(', ')+' mm. Match tolerance '+row.match.witness.tolerance_mm+' mm; measured Hausdorff distance '+row.match.witness.hausdorff_mm.toExponential(2)+' mm.'),
    technical('Source identities, exact excerpts and match witness',row));
  const contact=result.relationships.contact,proximity=result.relationships.proximity,neighborId=result.roles.find(r=>r.role==='R140.2').native.id;
  const gap=proximity.matches.find(r=>r.id===neighborId)?.distance_mm;
  panel.append(el('h2','2 · Understand the relationships'),el('p','R140.1 and the trace form one physical contact group: measured distance '+number(contact.matches[0].distance_mm)+' mm. R140.2 is nearby at '+number(gap)+' mm, in a separate group. Both pads belong to the R140 footprint. The mask opening is associated by unique anchor and qualified zero-margin geometry. These are distinct relationships; none grants editing permission.'));
  panel.append(technical('Stored relationship witnesses and selection dependencies',{relationships:result.relationships,selections:result.selections}));
  const findings=el('div');findings.append(el('h3','Qualification travels with the data'),el('p','Known differences remain stored: the L2GND region is mismatched, and strict parsing of the top layer stopped at a zero-width interpolation. Their geometry is not promoted into this context.'));
  findings.append(technical('Retained qualifications, messages and report bindings',result.qualifications));panel.append(findings);
  panel.append(el('h2','3 · Reopen the same stored revision'),el('p','The writer exited. A fresh process opened SQLite and the content-addressed payloads read-only, resolved the four roles, and checked their geometry, source dependencies and relationships. This browser shows that saved execution.'));
  panel.append(el('p','Dataset revision '+short(result.dataset_revision)+' · result '+short(result.result_sha256)),link(context.evidence.acceptance,'Fresh-process acceptance receipt ↗'),el('span',' · '),link(context.evidence.result,'Reopened result ↗'),technical('Revision, processes, query scope and completeness',{execution:context.execution,query:result.query,status:result.status,backend:result.backend,engineering_acceptance:result.engineering_acceptance}));
  panel.append(el('h2','4 · Export this selected context'),el('p','The saved diagnostic bundle retains these selected records, their parent, exact source references, geometry, matches and qualifications. Another fresh process reopened it and returned the same result digest. Complete original source artifacts are retained for provenance; this is a diagnostic selection, not a standalone KiCad board.'));
  panel.append(link(context.evidence.selection,'Exported dataset manifest ↗'),el('span',' · '),link(context.evidence.receipt,'Export inventory and hashes ↗'),el('p',result.query.scope),el('p',result.engineering_acceptance));
 }
 render();return true;
}
