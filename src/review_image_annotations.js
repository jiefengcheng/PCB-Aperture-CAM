/* Local review feedback only. Never writes copper, receipts or verdicts. */
(() => {
  'use strict';
  const script = document.currentScript;
  const report = script.dataset.report;
  const storageKey = `pcb-review-annotations:${report}`;
  const main = document.querySelector('main');
  let notes = [], active = false, target = null;
  try { notes = JSON.parse(localStorage.getItem(storageKey) || '[]'); } catch (_) {}
  if (!Array.isArray(notes)) notes = [];
  const el = (tag, text, attrs = {}) => {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value);
    return node;
  };
  const style = el('style');
  style.textContent = `
    .feedback-bar{position:sticky;top:0;z-index:20;background:#fff9df;border:1px solid #d4af37;border-radius:8px;padding:10px;margin:10px 0}
    .feedback-bar p{margin:5px 0}.feedback-bar button{margin:3px}.feedback-on img{cursor:crosshair}
    .feedback-image{position:relative;display:block;line-height:0}.feedback-image img{display:block}
    .feedback-pin{position:absolute;transform:translate(-50%,-50%);background:#1674e8;color:white;border:2px solid white;border-radius:50%;min-width:28px;height:28px;padding:0;line-height:24px;font-weight:bold;z-index:2}
    #feedback-dialog{max-width:420px;width:85%;border:1px solid #aac;border-radius:12px;padding:18px;color:#152b40}
    #feedback-dialog textarea{box-sizing:border-box;width:100%;min-height:100px;padding:8px;font:inherit}
    #feedback-dialog button{margin:6px 6px 0 0}#feedback-list{line-height:1.4}#feedback-list li{margin:8px 0;overflow-wrap:anywhere}
    #feedback-list button{font-size:13px;padding:3px 8px;margin-left:8px}
  `;
  document.head.append(style);
  const bar = el('section', undefined, {class: 'feedback-bar', 'aria-label': 'Image annotations'});
  const toggle = el('button', 'Annotate image', {type: 'button', 'aria-pressed': 'false'});
  const copy = el('button', 'Copy feedback', {type: 'button'});
  const exportButton = el('button', 'Export feedback JSON', {type: 'button'});
  const hint = el('p', 'Click Annotate image, then a point on any board image. Save your comment. Copy feedback and paste it into this chat.');
  const status = el('p', 'Notes stay in this browser for this saved result.', {id: 'feedback-status', role: 'status'});
  const details = el('details');
  const summary = el('summary', 'Saved feedback (0)');
  const list = el('ol', undefined, {id: 'feedback-list'});
  details.append(summary, list); bar.append(toggle, copy, exportButton, hint, status, details);
  main.insertBefore(bar, main.children[1]);
  const dialog = el('dialog', undefined, {id: 'feedback-dialog'});
  const label = el('label', 'Your comment', {for: 'feedback-comment'});
  const context = el('p');
  const input = el('textarea', undefined, {id: 'feedback-comment', placeholder: 'For example: still too small; keep this circle round.'});
  const save = el('button', 'Save annotation', {type: 'button'});
  const cancel = el('button', 'Cancel', {type: 'button'});
  dialog.append(context, label, input, save, cancel); document.body.append(dialog);
  const images = [...document.querySelectorAll('main img')];
  images.forEach(image => {
    const wrapper = el('span', undefined, {class: 'feedback-image'});
    image.before(wrapper); wrapper.append(image);
    image.addEventListener('click', event => {
      if (!active) return;
      event.preventDefault();
      const box = image.getBoundingClientRect();
      target = {image: image.getAttribute('src'), image_label: image.alt,
        x: Math.max(0, Math.min(1, (event.clientX-box.left)/box.width)),
        y: Math.max(0, Math.min(1, (event.clientY-box.top)/box.height))};
      context.textContent = `Pin on ${target.image_label} (${target.image})`;
      input.value = ''; dialog.showModal(); input.focus();
    });
    new MutationObserver(() => renderPins()).observe(image, {attributes: true, attributeFilter: ['src']});
  });
  function renderPins() {
    document.querySelectorAll('.feedback-pin').forEach(pin => pin.remove());
    images.forEach(image => notes.forEach((note, index) => {
      if (note.image !== image.getAttribute('src')) return;
      const pin = el('button', String(index+1), {class: 'feedback-pin', type: 'button', title: note.comment, 'aria-label': `Annotation ${index+1}: ${note.comment}`});
      pin.style.left = `${note.x*100}%`; pin.style.top = `${note.y*100}%`;
      pin.addEventListener('click', () => {details.open = true; document.getElementById(`feedback-note-${index}`).scrollIntoView({block: 'center'});});
      image.parentElement.append(pin);
    }));
  }
  function render() {
    list.replaceChildren(); summary.textContent = `Saved feedback (${notes.length})`;
    notes.forEach((note, index) => {
      const row = el('li', `${note.image_label}: ${note.comment}`, {id: `feedback-note-${index}`});
      const remove = el('button', 'Remove', {type: 'button', 'aria-label': `Remove annotation ${index+1}`});
      remove.addEventListener('click', () => {notes.splice(index, 1); persist();});
      row.append(remove); list.append(row);
    });
    renderPins();
  }
  function persist() {
    try {localStorage.setItem(storageKey, JSON.stringify(notes)); status.textContent = `${notes.length} annotation(s) saved in this browser. Copy feedback and paste it into this chat.`;}
    catch (_) {status.textContent = 'Browser storage unavailable. Copy or export your feedback before leaving.';}
    render();
  }
  const payload = () => ({schema: 'pcb-image-review-feedback/1', report_sha256: report, annotations: notes});
  toggle.addEventListener('click', () => {
    active = !active; toggle.textContent = active ? 'Finish annotating' : 'Annotate image';
    toggle.setAttribute('aria-pressed', String(active)); document.body.classList.toggle('feedback-on', active);
    status.textContent = active ? 'Annotation mode on: click a point on a board image.' : 'Annotation mode off. Your saved notes remain.';
  });
  save.addEventListener('click', () => {
    const comment = input.value.trim(); if (!comment) {input.focus(); return;}
    notes.push({...target, comment}); persist(); dialog.close();
  });
  cancel.addEventListener('click', () => dialog.close());
  copy.addEventListener('click', async () => {
    try {await navigator.clipboard.writeText(JSON.stringify(payload(), null, 2)); status.textContent = 'Feedback copied. Paste it into this chat.';}
    catch (_) {details.open = true; status.textContent = 'Clipboard unavailable. Use Export feedback JSON or copy your notes below.';}
  });
  exportButton.addEventListener('click', () => {
    const url = URL.createObjectURL(new Blob([JSON.stringify(payload(), null, 2)], {type: 'application/json'}));
    const link = el('a', undefined, {href: url, download: 'pcb-review-feedback.json'}); link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  });
  render();
})();
