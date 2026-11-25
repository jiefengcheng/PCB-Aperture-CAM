import AppKit
import WebKit

extension ViewerHost {
    func runT04Smoke(folder: URL) {
        Task {
            do {
                try FileManager.default.createDirectory(at:folder,withIntermediateDirectories:true)
                var ready=false
                for _ in 0..<180 {
                    if (try? await web.callAsyncJavaScript("return !!window.t04Data && !!t04Data()",arguments:[:],in:nil,contentWorld:.page)) as? Bool == true { ready=true;break }
                    try await Task.sleep(for:.milliseconds(500))
                }
                guard ready else { throw NSError(domain:"T04Smoke",code:1,userInfo:[NSLocalizedDescriptionKey:"Saved T04 display was not loaded"]) }
                let result = try await web.callAsyncJavaScript("""
                const checks=[];window.t04SmokeChecks=checks;const check=(name,ok)=>{checks.push({name,pass:!!ok});if(!ok)throw Error(name)};
                const events=[],savedPost=post;post=value=>events.push(value);
                const original=JSON.stringify(t04Data()),revision=scene().revision;
                try {
                  $('workspace-mode').value='t04';workspaceChanged();
                  check('dedicated workspace',isT04()&&!$('t04-controls').hidden&&!$('t04-panel').hidden);
                  check('cleanup controls isolated',$('cleanup-controls').hidden&&$('cleanup-panel').hidden&&$('cleanup-run').hidden);
                  check('source controls isolated',$('trace-controls').hidden);
                  for(const mode of ['original','corrected','comparison']){
                    $('t04-view').value=mode;$('t04-view').onchange();
                    const paths=[...document.querySelectorAll('[data-board-growth]')];
                    check(mode+' grey copper',paths.filter(p=>p.dataset.boardGrowth!=='removed'||mode!=='comparison').every(p=>p.getAttribute('fill')==='#bac8ce'));
                    check(mode+' partition',mode==='original'?!paths.some(p=>p.dataset.boardGrowth==='added'):mode==='corrected'?!paths.some(p=>p.dataset.boardGrowth==='removed'):true);
                  }
                  if(t04BaseData().shoulderReview){
                    const savedBaseline=$('t04-baseline').value;
                    check('saved shoulder baseline selector visible',!$('t04-baseline-control').hidden);
                    $('t04-baseline').value='input';$('t04-baseline').onchange();
                    check('cleaned input comparison selected',t04Data().beforeWkbSHA256===t04BaseData().beforeWkbSHA256);
                    $('t04-baseline').value='shoulder';$('t04-baseline').onchange();
                    check('previous widening comparison selected',t04Data().beforeWkbSHA256===t04BaseData().shoulderReview.beforeWkbSHA256);
                    check('baseline switch retains final copper',t04Data().afterWkbSHA256===t04BaseData().afterWkbSHA256);
                    $('t04-baseline').value=savedBaseline;$('t04-baseline').onchange();
                  }
                  $('t04-filter').value='corner';$('t04-filter').onchange();check('all corners navigable',t04Findings().length===t04Data().findings.filter(f=>f.kind==='corner').length);
                  $('t04-filter').value='endpoint';$('t04-filter').onchange();check('all endpoints navigable',t04Findings().length===t04Data().findings.filter(f=>f.kind==='endpoint').length);
                  for(const kind of ['eligibility','continuity','transition','terminal','marked']){$('t04-filter').value=kind;$('t04-filter').onchange();check(kind+' places navigable',t04Findings().length===t04Data().findings.filter(f=>f.kind===kind).length)}
                  if(t04Data().maximumTransitionAngleDegrees!=null)check('saved transition angle visible',$('t04-limits').textContent.includes(t04Data().maximumTransitionAngleDegrees+'°'));
                  if(t04Data().fullBoard===false){check('bounded scope visible',$('t04-heading').textContent.includes('bounded'));check('coverage policy visible',$('t04-limits').textContent.includes((t04Data().largeFillCoverageFraction*100).toFixed(0)+'%'))}
                  $('t04-filter').value='all';$('t04-filter').onchange();
                  const first=t04Selection;$('t04-next').click();check('next finding',t04Selection!==first);$('t04-prev').click();check('previous finding',t04Selection===first);
                  const playStart=t04Selection;$('t04-play').click();check('play starts',t04Timer!==null);await new Promise(resolve=>setTimeout(resolve,4200));check('play advances finding',t04Selection!==playStart);$('t04-play').click();check('play pauses',t04Timer===null);
                  $('t04-view').value='original';$('t04-view').onchange();const cameraBefore=JSON.stringify(camera);
                  $('workspace-mode').value='cleanup';workspaceChanged();
                  if(t04Only){
                    check('T04-only mode blocks workspace switching',isT04()&&$('cleanup-controls').hidden&&$('cleanup-run').hidden);
                    check('T04-only stage selector removed',$('workspace-mode').options.length===1&&$('workspace-mode').closest('label').hidden&&!$('t04-only-title').hidden);
                    check('T04-only source opening hidden',$('open').hidden);
                  }else check('cleanup keeps own controls',!$('cleanup-controls').hidden&&$('t04-controls').hidden&&!$('cleanup-run').hidden);
                  $('workspace-mode').value='t04';workspaceChanged();check('T04 view and camera retained',$('t04-view').value==='original'&&JSON.stringify(camera)===cameraBefore);
                  check('saved data unchanged',JSON.stringify(t04Data())===original&&scene().revision===revision);
                  check('no treatment execution requests',events.every(e=>!['runLargeCopper','runT04','open'].includes(e.action)));
                  check('cutoff belongs to T04 panel',$('t04-limits').textContent.includes(t04Data().nominalCutoffMM.toFixed(3)));
                  $('t04-overview').click();
                  check('findings button restores problem list',$('t04-filter').value==='findings');
                  check('findings exclude normal grown traces',t04Findings().every(f=>f.kind!=='continuity'));
                  check('findings retain all exclusions',t04Findings().length===t04Data().findings.filter(f=>f.kind!=='continuity'&&f.kind!=='terminal'&&(!['transition','marked'].includes(f.kind)||f.reasons.includes('UNRESOLVED'))).length);
                  check('deferred terminals stay out of interior findings',t04Findings().every(f=>f.kind!=='terminal'));
                  check('resolved transitions stay in their own list',t04Findings().every(f=>f.kind!=='transition'||f.reasons.includes('UNRESOLVED')));
                  $('t04-view').value='comparison';$('t04-view').onchange();$('t04-fit').click();
                  return {checks,revision,inputSceneSHA256:t04Data().inputSceneSHA256,findings:t04Data().findings.length,parts:t04Data().parts.length,treatmentRequests:0};
                } finally {post=savedPost;post({action:'displayed',revision:scene().revision,presentation:'T04_WORKSPACE',growthParts:String(document.querySelectorAll('[data-board-growth]').length)})}
                """, arguments:[:],in:nil,contentWorld:.page)
                try JSONSerialization.data(withJSONObject:result as Any,options:[.prettyPrinted,.sortedKeys]).write(to:folder.appendingPathComponent("t04-ui-smoke.json"))
                let marked = (try await web.callAsyncJavaScript("return t04BaseData()?.shoulderReview ? t04BaseData().findings.filter(f=>f.kind==='marked').map(f=>f.id) : []",arguments:[:],in:nil,contentWorld:.page)) as? [String] ?? []
                var pairs:[[String:Any]]=[]
                for (index,id) in marked.enumerated() {
                    for mode in ["original","corrected"] {
                        let saved = try await web.callAsyncJavaScript("""
                        $('t04-baseline').value='shoulder';$('t04-baseline').onchange();
                        $('t04-filter').value='marked';$('t04-filter').onchange();
                        t04Selection=id;$('t04-findings').value=id;
                        $('t04-view').value=mode;$('t04-view').onchange();focusT04();
                        return {id,mode,revision:scene().revision,bounds:t04Selected().bounds,
                          beforeWkbSHA256:t04Data().beforeWkbSHA256,afterWkbSHA256:t04Data().afterWkbSHA256};
                        """,arguments:["id":id,"mode":mode],in:nil,contentWorld:.page)
                        try await Task.sleep(for:.milliseconds(200))
                        let capture=try await web.takeSnapshot(configuration:nil)
                        let name="marked-\(index+1)-\(mode).png"
                        if let tiff=capture.tiffRepresentation,let bitmap=NSBitmapImageRep(data:tiff),let png=bitmap.representation(using:.png,properties:[:]) {
                            try png.write(to:folder.appendingPathComponent(name))
                            pairs.append(["image":name,"saved":saved as Any])
                        }
                    }
                }
                if let first=marked.first {
                    _ = try await web.callAsyncJavaScript("t04Selection=id;$('t04-findings').value=id;$('t04-view').value='comparison';$('t04-view').onchange();focusT04()",arguments:["id":first],in:nil,contentWorld:.page)
                    try JSONSerialization.data(withJSONObject:pairs,options:[.prettyPrinted,.sortedKeys]).write(to:folder.appendingPathComponent("marked-ui-comparisons.json"))
                }
                let image=try await web.takeSnapshot(configuration:nil)
                if let tiff=image.tiffRepresentation,let bitmap=NSBitmapImageRep(data:tiff),let png=bitmap.representation(using:.png,properties:[:]) { try png.write(to:folder.appendingPathComponent("t04-view.png")) }
            } catch {
                try? String(describing:error).data(using:.utf8)?.write(to:folder.appendingPathComponent("T04_UI_FAILED.txt"))
                if let checks=try? await web.callAsyncJavaScript("return window.t04SmokeChecks || []",arguments:[:],in:nil,contentWorld:.page),let data=try? JSONSerialization.data(withJSONObject:checks,options:[.prettyPrinted]) {try? data.write(to:folder.appendingPathComponent("t04-ui-partial.json"))}
            }
        }
    }
}
