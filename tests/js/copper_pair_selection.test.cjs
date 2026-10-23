const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const context = vm.createContext({ document: { createElement: () => ({}) } });
const source = fs.readFileSync(path.join(__dirname, '../../web/ingestion_views.js'), 'utf8') +
  '\nglobalThis.pairReview = ingestionUI;';
vm.runInContext(source, context);

function attrNode(initial = {}) {
  const attrs = { ...initial };
  return {
    children: [],
    firstElementChild: null,
    hasAttribute: key => Object.hasOwn(attrs, key),
    getAttribute: key => attrs[key] ?? null,
    setAttribute: (key, value) => { attrs[key] = String(value); },
    removeAttribute: key => { delete attrs[key]; },
    attrs,
  };
}

const orgShape = attrNode({ stroke: 'none', 'stroke-width': '1.5' });
const editShape = attrNode({ stroke: '#14828a', 'stroke-width': '2' });
const otherShape = attrNode({ stroke: '#c4ced2', 'stroke-width': '0.65' });
const org = attrNode({ 'data-source-identity': 'org-hash:bytes:10:20', 'data-source-side': 'before' }); org.firstElementChild = orgShape;
const edit = attrNode({ 'data-source-identity': 'edit-hash:bytes:30:40', 'data-source-side': 'after' }); edit.firstElementChild = editShape;
const other = attrNode({ 'data-source-identity': 'other-hash:bytes:50:60', 'data-source-side': 'before' }); other.firstElementChild = otherShape;
const svgNodes = [org, edit, other];
const svgDocument = { querySelectorAll: selector => selector === '[data-source-identity][data-source-side]' ? svgNodes : [] };
const pair = {
  ORG_source_identity: 'org-hash:bytes:10:20', EDIT_source_identity: 'edit-hash:bytes:30:40',
  ORG_source_center_mm: '[1, -2]', EDIT_source_center_mm: '[1, -2]',
  CAD_registered_center_displacement_mm: 0.0002, ORG_residual_mm: 0.0194, EDIT_residual_mm: 0.0162,
};

assert.deepEqual({ ...context.pairReview.highlightSourcePair(svgDocument, pair) }, { matched: true, selected: 2 });
assert.equal(org.getAttribute('data-pair-selected'), 'true');
assert.equal(edit.getAttribute('data-pair-selected'), 'true');
assert.equal(org.getAttribute('data-pair-selected-side'), 'before');
assert.equal(edit.getAttribute('data-pair-selected-side'), 'after');
assert.equal(org.getAttribute('data-source-identity'), pair.ORG_source_identity);
assert.equal(edit.getAttribute('data-source-identity'), pair.EDIT_source_identity);
assert.equal(orgShape.getAttribute('stroke'), '#ffb000');
assert.equal(editShape.getAttribute('stroke'), '#ffb000');
assert.equal(orgShape.getAttribute('stroke-width'), '7');
assert.match(orgShape.getAttribute('filter'), /drop-shadow/);
assert.equal(other.getAttribute('data-pair-selected'), null);
const summary = context.pairReview.pairSelectionSummary(pair, 2);
assert.match(summary, /registered CAD center displacement 0\.000200 mm/);
assert.match(summary, /screenshot-fit center residuals ORG 0\.0194 mm \/ EDIT 0\.0162 mm/);

const nextPair = { ...pair, ORG_source_identity: 'other-hash:bytes:50:60', EDIT_source_identity: 'missing' };
assert.deepEqual({ ...context.pairReview.highlightSourcePair(svgDocument, nextPair) }, { matched: false, selected: 0 });
assert.equal(orgShape.getAttribute('stroke'), 'none');
assert.equal(editShape.getAttribute('stroke'), '#14828a');
assert.equal(otherShape.getAttribute('stroke'), '#c4ced2');
assert.equal(other.getAttribute('data-pair-selected'), null);

const duplicate = attrNode({ 'data-source-identity': pair.ORG_source_identity, 'data-source-side': 'before' });
duplicate.firstElementChild = attrNode({ stroke: '#222', 'stroke-width': '1' });
svgNodes.push(duplicate);
assert.deepEqual({ ...context.pairReview.highlightSourcePair(svgDocument, pair) }, { matched: false, selected: 0 });
assert.equal(org.getAttribute('data-pair-selected'), null);
assert.equal(edit.getAttribute('data-pair-selected'), null);
assert.equal(duplicate.getAttribute('data-pair-selected'), null);
console.log(JSON.stringify({ status: 'PASS', checks: ['exact ORG-before and EDIT-after identities are selected once', 'selection highlight is visible and side-tagged', 'previous selection restores original SVG styles', 'missing or duplicated source members produce no highlight', 'CAD displacement and screenshot-fit residuals remain separately labeled'] }));
