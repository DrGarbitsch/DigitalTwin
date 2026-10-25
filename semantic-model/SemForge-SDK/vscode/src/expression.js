/**
* Copyright (c) 2026 IndustryFusion Foundation
*
* Licensed under the Apache License, Version 2.0 (the "License");
* you may not use this file except in compliance with the License.
* You may obtain a copy of the License at
*
*    http://www.apache.org/licenses/LICENSE-2.0
*
* Unless required by applicable law or agreed to in writing, software
* distributed under the License is distributed on an "AS IS" BASIS,
* WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
* See the License for the specific language governing permissions and
* limitations under the License.
*/

/**
 * The value editor: what an attribute's value may be.
 *
 * First its forms -- a Property's value, a Relationship's entity, a
 * JsonProperty, a ListProperty, … any choice of them, as NGSI-LD allows --
 * then, for each form on its own, what it must be: conditions, and
 * expressions of them (any of, all of, exactly one of, not, nested). "One
 * boolean, or a list of numbers" is two forms with their own conditions.
 *
 * A panel beside the type page draws each form as a card and its conditions
 * as nested boxes; everything is edited where it stands. Opened from the
 * attribute's ⋯ menu ("Value editor…"), from its value when that is more
 * than one plain value, or from "Combine with another condition…" in the
 * value picker. One plain value -- what nearly every attribute needs -- is
 * still edited with the picker.
 *
 * Every change is one request (semforge/editValueForms); the server rewrites
 * the value and reads it back before keeping it (cooked/valueforms.py), and
 * the panel is drawn again from what is now in the file.
 */
const crypto = require('crypto');
const vscode = require('vscode');

// What a condition may be, in the order a reader thinks of them.
const CONDITIONS = [
  { parameter: 'sh:datatype', label: 'datatype', hint: 'xsd:double, xsd:string, …', list: 'datatypes' },
  { parameter: 'sh:class', label: 'class', hint: 'a vocabulary term or an entity type', list: 'classes' },
  { parameter: 'sh:hasValue', label: 'exactly', hint: 'a number, "text", or a prefixed name' },
  { parameter: 'sh:in', label: 'one of', hint: 'values separated by commas' },
  { parameter: 'sh:minInclusive', label: '≥', hint: 'a number' },
  { parameter: 'sh:minExclusive', label: '>', hint: 'a number' },
  { parameter: 'sh:maxInclusive', label: '≤', hint: 'a number' },
  { parameter: 'sh:maxExclusive', label: '<', hint: 'a number' },
  { parameter: 'sh:minLength', label: 'at least … characters', hint: 'a whole number' },
  { parameter: 'sh:maxLength', label: 'at most … characters', hint: 'a whole number' },
  { parameter: 'sh:pattern', label: 'matching', hint: 'a regular expression' },
  { parameter: 'sh:nodeKind', label: 'node kind', hint: 'sh:Literal or sh:IRI' }
];
const CONNECTIVES = { or: 'any of', and: 'all of', xone: 'exactly one of', not: 'not' };

function escape(text) {
  return String(text === undefined || text === null ? '' : text)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function conditionLabel(parameter) {
  const known = CONDITIONS.find((c) => c.parameter === parameter);
  return known ? known.label : parameter;
}

function button(act, label, title, extra) {
  return `<button class="tool" data-act="${act}" title="${escape(title)}"${extra || ''}>${escape(label)}</button>`;
}

/** One part of the expression, as a box; `address` is its path from the root. */
function box(node, address, own, editable) {
  const at = ` data-addr="${escape(JSON.stringify(address))}"`;
  if (node.kind === 'raw') {
    return `<div class="box raw"${at}><div class="head"><span class="what">kept as written</span>` +
      (editable ? `<span class="tools">${button('remove', 'Remove', 'Remove this part')}` +
        `${button('open', 'Open in .ttl', 'Show it in the shapes file')}</span>` : '') +
      `</div><code>${escape(node.words)}</code></div>`;
  }
  if (node.kind === 'leaf') {
    const chips = node.conditions.map((c) =>
      `<span class="chip" data-param="${escape(c.parameter)}" data-value="${escape(c.value)}">` +
      `<span class="p">${escape(conditionLabel(c.parameter))}</span> ${escape(c.value)}` +
      (editable ? `<a href="#" class="x" data-act="change" title="Change it">✎</a>` +
        `<a href="#" class="x" data-act="unset" title="Remove this condition">×</a>` : '') +
      '</span>').join('');
    const tools = editable ? '<span class="tools">' +
      button('set', '+ Condition', 'Add a condition: all of them must hold') +
      (own ? '' : button('wrapor', 'Or else…', 'Any of: this, or another') +
        button('wrapxone', 'Exactly one of…', 'This or another, not both') +
        button('wrapnot', 'Not', 'Anything but this') +
        button('remove', 'Remove', 'Remove this branch')) + '</span>' : '';
    return `<div class="box leaf${own ? ' own' : ''}"${at}><div class="head">` +
      `<span class="what">${own ? 'always' : escape(node.words)}</span>${tools}</div>` +
      `<div class="chips">${chips || '<span class="dim">no condition: any value</span>'}</div></div>`;
  }
  const kids = node.children.map((child, index) =>
    box(child, address.concat([index]), false, editable)).join('');
  const kind = node.op === 'not' ? '<span class="what">not</span>'
    : editable ? `<select data-act="retype" title="What its branches say together">${['or', 'and', 'xone'].map((op) =>
      `<option value="${op}"${op === node.op ? ' selected' : ''}>${CONNECTIVES[op]}</option>`).join('')}</select>`
      : `<span class="what">${CONNECTIVES[node.op]}</span>`;
  const tools = editable ? '<span class="tools">' +
    (node.op !== 'not' ? button('add', '+ Condition', 'Another branch: one condition') +
      button('addgroup', '+ Group', 'Another branch: any of / all of / exactly one of / not') : '') +
    button('wrapnot', 'Not', 'Anything but this group') +
    button('unwrap', node.op === 'not' ? 'Drop "not"' : 'Unwrap', 'Its branches take its place') +
    button('remove', 'Remove', 'Remove this group') + '</span>' : '';
  return `<div class="box op op-${node.op}"${at}><div class="head">${kind}${tools}</div>` +
    `<div class="kids">${kids}</div></div>`;
}

/**
 * One form of the value -- a Property's value, a list, a JsonProperty, … --
 * as a card: its kind (a choice), whether a list may be empty, what it says,
 * and its own conditions as boxes. `index` is the form's place in the value.
 */
function formCard(form, index, state) {
  const editable = !!state.editable;
  const expression = form.expression || { kind: 'op', op: 'and', children: [] };
  const [own, ...rest] = expression.children;
  const kind = editable
    ? `<select data-act="formkind" title="What kind of attribute this form is">${(state.kinds || [])
      .map((k) => `<option value="${k}"${k === form.kind ? ' selected' : ''}>${k}</option>`).join('')}</select>`
    : `<span class="kindchip">${escape(form.kind)}</span>`;
  const empty = form.list ? `<label class="empty"><input type="checkbox" data-act="empty"` +
    `${form.mayBeEmpty ? ' checked' : ''}${editable ? '' : ' disabled'}> may be empty</label>` : '';
  const tools = editable ? '<span class="tools">' +
    button('combine-or', 'Or else…', 'Any of: what it is now, or another condition') +
    button('combine-xone', 'Exactly one of…', 'What it is now, or another condition — not both') +
    button('combine-not', 'But not…', 'What it is now, except') +
    button('rootgroup', '+ Group', 'A part it must also satisfy: any of / all of / exactly one of / not') +
    button('removeform', 'Remove form', 'The value may no longer take this form') + '</span>' : '';
  return `<div class="box form" data-form="${index}"><div class="head">${kind}` +
    ` <code>${escape(form.payload)}</code>${empty}${tools}</div>` +
    `<div class="formsaid">${escape(form.said)}</div>` +
    `<div class="sub">${form.list ? 'Each item must be' : 'It must be'}</div>` +
    `${own ? box(own, [0], true, editable) : ''}${rest.map((node, i) =>
      box(node, [i + 1], false, editable)).join('')}</div>`;
}

/** The panel. `state`: what semforge/expression said, the row, the choices. */
function renderExpressionPanel(state, options) {
  const nonce = options.nonce;
  const csp = `default-src 'none'; style-src 'nonce-${nonce}'; script-src 'nonce-${nonce}';`;
  const editable = !!state.editable;
  const forms = state.forms || [];
  const add = editable ? `<div class="roottools"><select id="newkind" title="The kind of the new form">` +
    `${(state.kinds || []).map((k) => `<option value="${k}">${k}</option>`).join('')}</select>` +
    button('addform', '+ Form', 'The value may also take this form') + '</div>' : '';
  const lists = ['datatypes', 'classes'].map((name) => `<datalist id="${name}">` +
    (state[name] || []).map((c) => `<option value="${escape(c.value)}">${escape(c.label || '')}</option>`).join('') +
    '</datalist>').join('');
  return `<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="${csp}">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${escape(state.label)}</title>
<style nonce="${nonce}">
  body { font-family: var(--vscode-font-family); color: var(--vscode-foreground); padding: 12px 18px; }
  h1 { font-size: 1.2em; margin: 0 0 4px; }
  .said { margin: 4px 0 12px; }
  .note { color: var(--vscode-descriptionForeground); font-size: 0.9em; }
  .error { color: var(--vscode-errorForeground); margin: 6px 0; }
  .box { border: 1px solid var(--vscode-panel-border, rgba(128,128,128,.35)); border-radius: 4px;
         padding: 6px 8px; margin: 6px 0; }
  .box.op { border-left: 3px solid var(--vscode-textLink-foreground); }
  .box.op-not { border-left-color: var(--vscode-errorForeground); }
  .box.own { border-style: dashed; }
  .kids { margin-left: 14px; }
  .head { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
  .what { font-weight: 600; }
  .tools { display: inline-flex; flex-wrap: wrap; gap: 4px; margin-left: auto; }
  .tool { font-size: 0.85em; padding: 1px 6px; color: var(--vscode-button-secondaryForeground);
          background: var(--vscode-button-secondaryBackground); border: none; border-radius: 3px; cursor: pointer; }
  .tool:hover { background: var(--vscode-button-secondaryHoverBackground); }
  .chips { margin-top: 4px; display: flex; flex-wrap: wrap; gap: 4px; }
  .chip { background: var(--vscode-badge-background); color: var(--vscode-badge-foreground);
          border-radius: 10px; padding: 1px 8px; font-size: 0.9em; }
  .chip .p { opacity: .8; }
  .chip .x { margin-left: 4px; color: inherit; text-decoration: none; }
  .dim { color: var(--vscode-descriptionForeground); }
  .roottools { display: flex; flex-wrap: wrap; gap: 6px; margin: 8px 0; }
  h2 { font-size: 1em; margin: 14px 0 4px; }
  .box.form { border-width: 2px; padding: 8px 10px; margin: 10px 0; }
  .formsaid { margin: 4px 0; }
  .sub { color: var(--vscode-descriptionForeground); font-size: 0.9em; margin-top: 6px; }
  .empty { font-size: 0.9em; }
  select { background: var(--vscode-input-background); color: var(--vscode-input-foreground);
           border: 1px solid var(--vscode-input-border, transparent); }
  .kindchip { font-size: 0.8em; padding: 0 6px; border-radius: 3px;
              background: var(--vscode-badge-background); color: var(--vscode-badge-foreground); }
  code { font-family: var(--vscode-editor-font-family); font-size: 0.9em; overflow-wrap: anywhere; }
  form { margin: 6px 0; padding: 6px 8px; background: var(--vscode-editorWidget-background, rgba(128,128,128,.1));
         border-radius: 4px; }
  form .row { display: flex; gap: 6px; margin: 4px 0; align-items: center; flex-wrap: wrap; }
  form input, form select { background: var(--vscode-input-background); color: var(--vscode-input-foreground);
         border: 1px solid var(--vscode-input-border, transparent); padding: 2px 4px; }
  form input { min-width: 16em; }
  .primary { background: var(--vscode-button-background); color: var(--vscode-button-foreground);
             border: none; padding: 3px 10px; border-radius: 3px; cursor: pointer; }
</style></head><body>
<h1>${escape(state.label)}: what its value may be</h1>
<div class="said">${escape(state.said || 'any value')}</div>
${state.error ? `<div class="error">${escape(state.error)}</div>` : ''}
${editable ? '' : `<div class="error">Edited in the .ttl: ${escape(state.reason || '')}</div>`}
<h2>Its forms — each with what it must be</h2>
${add}
<div id="forms">${forms.length ? forms.map((form, index) => formCard(form, index, state)).join('')
    : '<div class="dim">Any value: no form is constrained yet. Add one.</div>'}</div>
${lists}
<script nonce="${nonce}">
  const vscode = acquireVsCodeApi();
  const CONDITIONS = ${JSON.stringify(CONDITIONS)};
  const CONNECTIVES = ${JSON.stringify(CONNECTIVES)};
  // Every request names the form it is about: the card it comes from.
  function send(action, from) {
    const card = from && from.closest('[data-form]');
    if (card) { action.form = Number(card.dataset.form); }
    vscode.postMessage({ command: 'edit', action: action });
  }
  function el(tag, attrs, text) {
    const node = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) { node.setAttribute(k, attrs[k]); });
    if (text !== undefined) { node.textContent = text; }
    return node;
  }
  // One row of a form: which condition, and its value.
  function conditionRow(fixed, value) {
    const row = el('div', { class: 'row' });
    const pick = el('select', { 'data-field': 'parameter' });
    CONDITIONS.forEach(function (c) {
      const option = el('option', { value: c.parameter }, c.label);
      if (fixed === c.parameter) { option.selected = true; }
      pick.append(option);
    });
    if (fixed) { pick.disabled = true; }
    const input = el('input', { 'data-field': 'value' });
    if (value !== undefined) { input.value = value; }
    function hint() {
      const c = CONDITIONS.find(function (x) { return x.parameter === pick.value; });
      input.placeholder = c.hint;
      if (c.list) { input.setAttribute('list', c.list); } else { input.removeAttribute('list'); }
    }
    pick.addEventListener('change', hint);
    hint();
    row.append(pick, input);
    return row;
  }
  function closeForms() { document.querySelectorAll('form').forEach(function (f) { f.remove(); }); }
  // An inline form under a box: spec.rows condition rows (more may be added
  // when spec.more), a connective choice when spec.connective, then
  // spec.done(values, connective).
  function openForm(holder, spec) {
    closeForms();
    const form = el('form');
    if (spec.title) { form.append(el('div', { class: 'what' }, spec.title)); }
    let connective;
    if (spec.connective) {
      const row = el('div', { class: 'row' });
      connective = el('select', { 'data-field': 'connective' });
      ['or', 'and', 'xone', 'not'].forEach(function (op) {
        connective.append(el('option', { value: op }, CONNECTIVES[op]));
      });
      row.append(el('span', {}, 'a group:'), connective);
      form.append(row);
    }
    const rows = el('div');
    for (let i = 0; i < (spec.rows || 1); i += 1) { rows.append(conditionRow(spec.fixed, spec.value)); }
    form.append(rows);
    const actions = el('div', { class: 'row' });
    if (spec.more) {
      const more = el('button', { type: 'button', class: 'tool' }, '+ Another condition');
      more.addEventListener('click', function () { rows.append(conditionRow()); });
      actions.append(more);
    }
    const ok = el('button', { type: 'submit', class: 'primary' }, 'Apply');
    const cancel = el('button', { type: 'button', class: 'tool' }, 'Cancel');
    cancel.addEventListener('click', closeForms);
    actions.append(ok, cancel);
    form.append(actions);
    form.addEventListener('submit', function (event) {
      event.preventDefault();
      const values = Array.from(rows.querySelectorAll('.row')).map(function (row) {
        return { parameter: row.querySelector('[data-field=parameter]').value,
          value: row.querySelector('[data-field=value]').value.trim() };
      }).filter(function (c) { return c.value; });
      if (!values.length) { return; }
      spec.done(values, connective ? connective.value : undefined);
    });
    holder.after(form);
    const first = form.querySelector('input');
    if (first) { first.focus(); }
  }
  document.addEventListener('click', function (event) {
    const target = event.target.closest('[data-act]');
    if (!target || target.tagName === 'SELECT') { return; }
    event.preventDefault();
    const act = target.dataset.act;
    const boxNode = target.closest('[data-addr]');
    const addr = boxNode ? JSON.parse(boxNode.dataset.addr) : [];
    const head = boxNode ? boxNode.querySelector(':scope > .head') : target;
    const chip = target.closest('.chip');
    function send_(action) { send(action, target); }
    if (act === 'addform') {
      send({ op: 'addform', kind: document.getElementById('newkind').value });
      return;
    }
    if (act === 'removeform') { send_({ op: 'removeform' }); return; }
    if (act === 'open') { vscode.postMessage({ command: 'open' }); return; }
    if (act === 'remove' || act === 'unwrap') { send_({ op: act, node: addr }); return; }
    if (act === 'wrapnot') { send_({ op: 'wrap', node: addr, connective: 'not' }); return; }
    if (act === 'unset') { send_({ op: 'unset', node: addr, parameter: chip.dataset.param }); return; }
    if (act === 'change') {
      openForm(chip, { title: 'Change it', fixed: chip.dataset.param, value: chip.dataset.value,
        done: function (v) { send_({ op: 'set', node: addr, parameter: v[0].parameter, value: v[0].value }); } });
      return;
    }
    if (act === 'set' || act === 'add') {
      openForm(head, { title: act === 'set' ? 'Another condition — all of them must hold'
        : 'Another branch',
        done: function (v) { send_({ op: act, node: addr, parameter: v[0].parameter, value: v[0].value }); } });
      return;
    }
    if (act === 'wrapor' || act === 'wrapxone') {
      openForm(head, { title: act === 'wrapor' ? 'Or else' : 'Exactly one of this and',
        done: function (v) {
          send_({ op: 'wrap', node: addr, connective: act === 'wrapor' ? 'or' : 'xone',
            parameter: v[0].parameter, value: v[0].value });
        } });
      return;
    }
    if (act === 'addgroup' || act === 'rootgroup') {
      openForm(head, { title: 'A group of conditions', connective: true, rows: 2, more: true,
        done: function (v, connective) {
          send_({ op: 'addgroup', node: act === 'rootgroup' ? [] : addr, connective: connective,
            conditions: v });
        } });
      return;
    }
    if (act.indexOf('combine-') === 0) {
      const connective = act.slice('combine-'.length);
      openForm(target.parentElement, { title: { or: 'Or else', xone: 'Exactly one of: what it is now, or',
        not: 'But not' }[connective],
        done: function (v) {
          send_({ op: 'combine', connective: connective, parameter: v[0].parameter, value: v[0].value });
        } });
    }
  });
  document.addEventListener('change', function (event) {
    const target = event.target;
    if (target.matches('select[data-act=retype]')) {
      const addr = JSON.parse(target.closest('[data-addr]').dataset.addr);
      send({ op: 'retype', node: addr, connective: target.value }, target);
    } else if (target.matches('select[data-act=formkind]')) {
      send({ op: 'formkind', kind: target.value }, target);
    } else if (target.matches('input[data-act=empty]')) {
      send({ op: 'empty', value: target.checked }, target);
    }
  });
</script>
</body></html>`;
}

/** One panel, beside the type page; it follows the attribute it was opened on. */
class ExpressionPanel {
  constructor(pages) {
    this.pages = pages;
    this.panel = undefined;
    this.row = undefined;
    this.packageUri = undefined;
    this.error = '';
  }

  async open(row) {
    this.row = row;
    this.packageUri = this.pages.current.packageUri;
    this.error = '';
    if (!this.panel) {
      this.panel = vscode.window.createWebviewPanel('semforgeExpression', 'Expression',
        { viewColumn: vscode.ViewColumn.Beside, preserveFocus: false },
        { enableScripts: true, localResourceRoots: [] });
      this.panel.onDidDispose(() => { this.panel = undefined; });
      this.panel.webview.onDidReceiveMessage((message) => this.receive(message));
    } else {
      this.panel.reveal(vscode.ViewColumn.Beside);
    }
    this.choices = await this.loadChoices();
    await this.render();
  }

  async request(method, params) {
    const client = this.pages.clientHolder.client;
    if (!client) {
      return { ok: false, error: 'the language server is not running' };
    }
    try {
      return await client.sendRequest(method, Object.assign({ uri: this.packageUri }, params));
    } catch (error) {
      return { ok: false, error: error.message || String(error) };
    }
  }

  async loadChoices() {
    const slot = this.row.kind === 'Relationship' ? 'ngsild:hasObject' : 'ngsild:hasValue';
    const [datatypes, classes] = await Promise.all(['sh:datatype', 'sh:class'].map((parameter) =>
      this.request('semforge/choices', { path: [this.row.term, slot], parameter, search: null })));
    return { datatypes: (datatypes && datatypes.choices) || [], classes: (classes && classes.choices) || [] };
  }

  async render() {
    if (!this.panel) {
      return;
    }
    const read = await this.request('semforge/valueForms', { shape: this.row.shape, path: this.row.path });
    this.panel.title = `${this.row.label} · value`;
    const state = Object.assign({ label: this.row.label }, this.choices,
      read.ok ? read : { editable: false, reason: read.error }, { error: this.error });
    this.panel.webview.html = renderExpressionPanel(state,
      { nonce: crypto.randomBytes(16).toString('base64') });
  }

  async receive(message) {
    if (!message || !this.row) {
      return;
    }
    if (message.command === 'open') {
      await require('./reveal').showLocation(this.row.definedAt, true);
      return;
    }
    if (message.command === 'edit') {
      const done = await this.request('semforge/editValueForms',
        { shape: this.row.shape, path: this.row.path, action: message.action });
      this.error = done.ok ? '' : done.error;
      await this.render();
      if (done.ok) {
        this.pages.refresh();
      }
    }
  }
}

let panel;

/** Open the expression editor on `row` of the type (or shape) page. */
async function openExpression(pages, row) {
  if (!panel || panel.pages !== pages) {
    panel = new ExpressionPanel(pages);
  }
  await panel.open(row);
  return false;          // the page refreshes when an edit is applied
}

/** "Combine with another condition…": the editor, ready to combine. */
async function combine(pages, row) {
  return openExpression(pages, row);
}

module.exports = { openExpression, combine, renderExpressionPanel, CONDITIONS };
