// Reusable smoke-check helper for a verified Codex browser tab (tab.playwright).
// No browser launch, server, uploads or page-script mutations. The recorded
// delivery checks were executed through the same documented CUA locator API.
export async function checkCombinations(tab) {
  const results=[];
  for(const spec of [
    {id:'synthetic',states:['before','computed','disconnected_n1','bridge','shifted_aperture','protected_p3']},
    {id:'halpi2',states:['positive','open','bridge']},
    {id:'glowstitch',states:['preserved']}
  ]) {
    await tab.playwright.locator(`[data-case="${spec.id}"]`).click();
    for(const state of spec.states) {
      await tab.playwright.getByLabel('Case state',{exact:true}).selectOption(state);
      for(const mode of ['compare','overlay','delta']) {
        await tab.playwright.locator(`[data-mode="${mode}"]`).click();
        const value=await tab.playwright.evaluate(()=>({
          left:document.querySelector('#left').getAttribute('viewBox'),
          right:document.querySelector('#right').getAttribute('viewBox'),
          candidate:document.querySelector('#candidate-status').textContent,
          control:document.querySelector('#control-status').textContent
        }));
        if(value.left!==value.right)throw Error('Views desynchronized');
        if(!['before','computed','positive','preserved'].includes(state)&&
          (!value.candidate.includes('FAIL')||!value.control.includes('test: PASS')))
          throw Error('Control test confused with candidate verdict');
        results.push({case:spec.id,state,mode,...value});
      }
    }
  }
  return results;
}
