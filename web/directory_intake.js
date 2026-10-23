/* Local sealed-package selection. Only file identities go to the loopback API. */
function directoryIntakeControl(dataset) {
 const group=document.createElement('span');
 const button=document.createElement('button');
 button.type='button';button.textContent='+';
 button.setAttribute('aria-label','Add dataset directory');
 button.title='Add a sealed intake profile or restore a qualified package from checkout/dataset';
 const input=document.createElement('input');
 input.type='file';input.multiple=true;input.setAttribute('webkitdirectory','');input.hidden=true;
 input.setAttribute('aria-label','Choose dataset directory');
 const status=document.createElement('span');
 status.setAttribute('role','status');status.setAttribute('aria-live','polite');
 const remove=document.createElement('button');
 remove.type='button';remove.textContent='−';remove.disabled=!dataset;
 remove.setAttribute('aria-label','Remove selected dataset');
 remove.title=dataset?'Remove '+dataset.label+' from the saved registry. Input files and historical runs are kept.':'No dataset selected';
 async function publishRequest(endpoint,payload){
  const response=await fetch(endpoint,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
  let result;try{result=await response.json();}catch{throw Error('Dataset changes require the local ingestion server on port 8769.');}
  if(!response.ok||result.status!=='PASS')throw Error(result.error||'Dataset publication failed.');
  const target=new URL(result.url,location.href);
  if(target.origin!==location.origin)throw Error('Unexpected publication destination.');
  location.assign(target.href);
 }
 remove.onclick=async()=>{
  if(!dataset)return;
  button.disabled=true;remove.disabled=true;
  status.textContent=' Removing '+dataset.label+' from the saved registry… Input files are retained.';
  try{await publishRequest('/api/ingestion/remove',{dataset_id:dataset.id});}
  catch(error){status.textContent=' Not removed: '+error.message+' Previous publication retained.';}
  finally{button.disabled=false;remove.disabled=false;}
 };
 button.onclick=()=>input.click();
 input.onchange=async()=>{
  if(!input.files?.length)return;
  button.disabled=true;remove.disabled=true;
  try{
   const files=Array.from(input.files),roots=new Set(files.map(f=>f.webkitRelativePath.split('/')[0]));
   if(roots.size!==1||files.some(f=>!f.webkitRelativePath.includes('/')))throw Error('Choose one dataset package directory.');
   const inventory=[];
   for(const [index,file] of files.entries()){
    status.textContent=' Verifying selected files '+(index+1)+' / '+files.length+'…';
    const hash=await crypto.subtle.digest('SHA-256',await file.arrayBuffer());
    inventory.push({path:file.webkitRelativePath.split('/').slice(1).join('/'),bytes:file.size,
     sha256:Array.from(new Uint8Array(hash),b=>b.toString(16).padStart(2,'0')).join('')});
   }
   status.textContent=' Verifying the sealed package and adding its recorded intake status… No content qualification is run here.';
   await publishRequest('/api/ingestion/directories',{package_name:[...roots][0],files:inventory});
  }catch(error){status.textContent=' Not added/restored: '+error.message+' Previous publication retained.';}
  finally{button.disabled=false;remove.disabled=!dataset;input.value='';}
 };
 group.append(button,input,status,remove);
 return group;
}
