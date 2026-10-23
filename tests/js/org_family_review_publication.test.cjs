const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),{webcrypto}=require('node:crypto');
const {Element,descend}=require('./ingestion_views.test.cjs');

async function run(root,runId){
 const workbench=path.join(root,'out/ingestion/workbench'),entry=fs.readFileSync(path.join(workbench,'index.html'),'utf8');
 const selected=runId||entry.match(/url=(run-[0-9a-f]{32})\/index\.html/)?.[1];assert.ok(selected,'current workbench entry resolves to an immutable run');
 const runPath=path.isAbsolute(selected)?selected:path.join(workbench,selected),scene=JSON.parse(fs.readFileSync(path.join(runPath,'scene.json'),'utf8'));
 const [datasetId,registryBinding]=Object.entries(scene.ingestion.org_family_maps)[0];assert.ok(registryBinding,'published run has a bound ORG family map');
 const reviewPath=path.join(runPath,registryBinding.snapshot),projection=JSON.parse(fs.readFileSync(reviewPath,'utf8'));
 const group=[...projection.physical_groups].filter(row=>row.inspection_status==='COMPLETE').sort((a,b)=>b.source_member_count-a.source_member_count)[0];
 assert.ok(group,'published projection has a COMPLETE physical group');assert.equal(group.source_member_ids.length,group.source_member_count);
 const candidate=projection.members.find(row=>row.physical_group_key===group.physical_group_key);assert.ok(candidate,'a member navigates to the selected largest complete group');
 const storedPath=path.join(runPath,projection.stored_geometry_paths_ref.snapshot),storedBytes=fs.readFileSync(storedPath),reviewBytes=fs.readFileSync(reviewPath);
 const document={createElement:t=>new Element(t),createElementNS:(_,t)=>new Element(t)},panel=new Element('section');
 const fetch=async url=>{const target=String(url).includes('stored-geometry')?storedBytes:reviewBytes;return {ok:true,headers:{get:()=>String(target.byteLength)},arrayBuffer:async()=>target.buffer.slice(target.byteOffset,target.byteOffset+target.byteLength)};};
 const context=vm.createContext({document,window:{},scene,panel,TextDecoder,TextEncoder,crypto:webcrypto,fetch});
 vm.runInContext(fs.readFileSync(path.join(root,'web/org_family_review.js'),'utf8'),context);
 await vm.runInContext(`renderOrgFamilyReview(scene,panel,${JSON.stringify(datasetId)},()=>{})`,context);
 assert.match(panel.textContent,/Projection hash verified/);
 const memberSearch=descend(panel,node=>node.attrs['aria-label']==='Search candidate members')[0];assert.ok(memberSearch);memberSearch.value=candidate.member_key;memberSearch.oninput();
 const list=descend(panel,node=>node.attrs['aria-label']==='All ORG candidate members')[0],button=list.children.find(node=>node.className==='org-family-member');assert.ok(button);button.onclick();
 assert.match(panel.textContent,new RegExp(`${group.source_member_count}/${group.source_member_count} source objects and geometries are shown`));
 const svg=descend(panel,node=>node.attrs['aria-label']==='Complete ORG physical contact group geometry')[0];assert.ok(svg);
 const paths=svg.children.filter(node=>node.tag==='path');const drawn=paths.length;assert.equal(drawn,group.source_member_count,'every source member in the largest COMPLETE group is drawn');assert.ok(paths.every(node=>node.attrs['fill-rule']==='evenodd'),'all closed ORG path rings use explicit SVG even-odd fill semantics');
 const viewBox=svg.attrs.viewBox.split(/\s+/).map(Number),[vx,vy,vw,vh]=viewBox;for(const node of paths){const numbers=node.attrs.d.match(/-?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?/g).map(Number);for(let i=0;i<numbers.length;i+=2){assert.ok(numbers[i]>=vx-1e-9&&numbers[i]<=vx+vw+1e-9,'path x coordinate is inside the padded viewBox');assert.ok(numbers[i+1]>=vy-1e-9&&numbers[i+1]<=vy+vh+1e-9,'path y coordinate is inside the padded viewBox');}}
 const seedRef=candidate.source_refs.find(ref=>ref.role==='local_land_candidate_seed'),seedPath=projection.geometry_paths[projection.source_objects[seedRef.object_id].geometry_sha256];assert.ok(paths.some(node=>node.attrs.d===seedPath&&node.attrs.fill==='#e3b34f'),'selected member highlight resolves to the exact pinned seed path');
 assert.match(panel.textContent,/Coordinates are mm with identity_from_org_wkb_xy; polygon rings use evenodd fill\./);
 return {status:'PASS',run:path.basename(runPath),runPath,datasetId,physicalGroupKey:group.physical_group_key,sourceMemberCount:group.source_member_count,svgObjectPaths:drawn,inspectionStatus:group.inspection_status};
}
module.exports={run};
