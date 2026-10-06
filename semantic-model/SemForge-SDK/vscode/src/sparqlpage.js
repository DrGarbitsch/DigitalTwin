/*
 * The SPARQL workbench: one SPARQL query of a shape, the data it runs over,
 * and what it returns -- to develop a SPARQL constraint (or rule) against the
 * very graph validation hands it.
 *
 * The query is edited in place. Apply (Ctrl+Enter) runs the edited text the
 * way validation does -- once per focus node, $this bound -- and shows, for a
 * constraint, which nodes would violate next to the saved query's verdict; for
 * a rule, the triples it would construct. Cancel goes back to the saved text,
 * Save (Ctrl+S) writes it over the literal in shacl.ttl. The data source is
 * Main or any test case, those the shape reaches first. Nothing is written
 * until Save, and Save refuses if the file changed underneath.
 *
 * `renderSparqlBench` is a pure function from the `semforge/sparqlBench`
 * payload; results arrive later by postMessage, so a run never resets the
 * editor.
 */

const crypto = require('crypto');
const vscode = require('vscode');

const { showLocation } = require('./reveal');
const { escape } = require('./typepage');

const REFRESH_VIEWS = ['semforge.refreshTree', 'semforge.refreshShapes',
  'semforge.refreshModel', 'semforge.refreshKnowledge'];

function chip(text, tone, title) {
  return `<span class="chip ${tone || ''}"${title ? ` title="${escape(title)}"` : ''}>` +
    `${escape(text)}</span>`;
}

function renderSparqlBench(page, options) {
  const nonce = (options && options.nonce) || '';
  const draft = options && typeof options.draft === 'string' ? options.draft : undefined;
  const csp = `default-src 'none'; style-src 'nonce-${nonce}'; script-src 'nonce-${nonce}';`;
  const holder = page.holder;
  const rule = holder.kind === 'rule';
  const tabs = page.holders.length > 1
    ? `<div class="tabs">${page.holders.map((h) =>
      `<button class="tab${h.index === holder.index ? ' on' : ''}" data-holder="${h.index}" ` +
      `title="line ${h.line}">${escape(h.kind)} ${h.index + 1}${h.message
        ? ` · ${escape(h.message.slice(0, 40))}` : ''}</button>`).join('')}</div>` : '';
  const sources = page.sources.map((s) => `<option value="${escape(s.id)}"` +
    `${s.id === page.source ? ' selected' : ''}>${escape(s.label)}` +
    `${s.expect ? ` (${escape(s.expect)})` : ''} — ${s.focus} focus node(s)</option>`).join('');
  const state = { baseline: holder.query, draft: draft === undefined ? holder.query : draft,
    kind: holder.kind, message: holder.message,
    snapshots: (options && options.snapshots) || [] };
  const selects = page.selector;

  return `<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="${csp}">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${escape(page.label)} · SPARQL</title>
<style nonce="${nonce}">
  body { font-family: var(--vscode-font-family); font-size: var(--vscode-font-size);
         color: var(--vscode-foreground); background: var(--vscode-editor-background);
         padding: 14px 20px 40px; line-height: 1.45; }
  a { color: var(--vscode-textLink-foreground); text-decoration: none; }
  a:hover { text-decoration: underline; }
  .dim { color: var(--vscode-descriptionForeground); }
  h1 { font-size: 1.4em; font-weight: 600; margin: 2px 0 4px; }
  h2 { font-size: 0.78em; font-weight: 600; letter-spacing: .08em; text-transform: uppercase;
       color: var(--vscode-descriptionForeground); margin: 18px 0 6px; }
  .chips, .bar, .tabs { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
  .bar { margin: 8px 0; gap: 8px; }
  .chip { font-size: 0.86em; padding: 1px 8px; border-radius: 999px; white-space: nowrap;
          border: 1px solid var(--vscode-panel-border, rgba(128,128,128,.35)); }
  .chip.ok { color: var(--vscode-testing-iconPassed, #388a34); border-color: currentColor; }
  .chip.bad { color: var(--vscode-errorForeground, #f14c4c); border-color: currentColor; }
  .chip.warn { color: var(--vscode-editorWarning-foreground, #cca700); border-color: currentColor; }
  button { font: inherit; color: var(--vscode-button-secondaryForeground, inherit);
           background: var(--vscode-button-secondaryBackground, transparent);
           border: 1px solid var(--vscode-panel-border, rgba(128,128,128,.35));
           padding: 3px 12px; border-radius: 2px; cursor: pointer; }
  button.primary { color: var(--vscode-button-foreground); background: var(--vscode-button-background);
                   border-color: var(--vscode-button-background); }
  button:disabled { opacity: .45; cursor: default; }
  .tab.on { border-color: var(--vscode-focusBorder, #0078d4); }
  select { font: inherit; color: var(--vscode-dropdown-foreground); padding: 2px 4px;
           background: var(--vscode-dropdown-background); border: 1px solid var(--vscode-dropdown-border); }
  textarea { width: 100%; box-sizing: border-box; min-height: 18em; resize: vertical;
             font-family: var(--vscode-editor-font-family); font-size: var(--vscode-editor-font-size, 13px);
             color: var(--vscode-input-foreground); background: var(--vscode-input-background);
             border: 1px solid var(--vscode-input-border, rgba(128,128,128,.35)); padding: 8px;
             tab-size: 4; line-height: 1.4; }
  textarea.dirty { border-color: var(--vscode-editorWarning-foreground, #cca700); }
  pre { font-family: var(--vscode-editor-font-family); font-size: 0.9em; margin: 0;
        padding: 8px; overflow: auto; max-height: 28em;
        background: var(--vscode-textCodeBlock-background, rgba(128,128,128,.1)); }
  table { border-collapse: collapse; width: 100%; font-size: 0.92em; }
  th, td { text-align: left; padding: 3px 8px; vertical-align: top;
           border-bottom: 1px solid var(--vscode-panel-border, rgba(128,128,128,.25)); }
  td { font-family: var(--vscode-editor-font-family); overflow-wrap: anywhere; }
  .problem { color: var(--vscode-errorForeground, #f14c4c); white-space: pre-wrap;
             border-left: 2px solid currentColor; padding-left: 8px; }
  .warning { color: var(--vscode-editorWarning-foreground, #cca700);
             border-left: 2px solid currentColor; padding-left: 8px; margin: 2px 0; }
  details summary { cursor: pointer; }
  .selects { margin: 6px 0 2px; }
  .selects b { font-weight: 600; margin-right: 6px; }
  tr.dropped td { opacity: .55; }
  td.yes { color: var(--vscode-testing-iconPassed, #388a34); }
  td.no { color: var(--vscode-errorForeground, #f14c4c); }
  td.err { color: var(--vscode-editorWarning-foreground, #cca700); }
  .snap { display: flex; gap: 8px; align-items: baseline; padding: 2px 0; }
  .snap .name { font-weight: 600; }
  h3 { font-size: 1em; margin: 12px 0 4px; }
  .status { margin-left: auto; }
</style></head><body>
<div class="dim">SPARQL workbench · <a href="#" data-shape="1">${escape(page.shapeName)}</a></div>
<h1>${escape(page.label)} <span class="dim">· ${escape(holder.kind)}</span></h1>
<div class="chips">
  ${holder.message ? chip(holder.message, '', 'sh:message — {?var} is filled from each row') : ''}
  ${holder.severity ? chip(`severity: ${holder.severity}`) : ''}
  <a href="#" data-open="${escape(holder.file)}:${holder.line}">shacl.ttl:${holder.line}</a>
</div>
${tabs}

<h2>Data</h2>
<div class="bar">
  <label for="source">Run over</label>
  <select id="source">${sources}</select>
  <span class="dim">${page.focus.length} focus node(s): ${escape(page.focus.slice(0, 6).join(', '))}${
  page.focus.length > 6 ? ' …' : ''}</span>
</div>
${selects ? `<div class="selects"><b>Selects</b><span>${selects.binds
    ? `$this = each of ${escape(selects.text)} → ${selects.count} node(s), bound before the query runs`
    : `the query never mentions $this: it runs once, unbound (${escape(selects.text)})`}</span></div>
<details><summary class="dim">Show as SPARQL — what the engine adds</summary><pre>${
  escape(selects.sparql)}</pre></details>` : ''}

<h2>Query</h2>
<textarea id="query" spellcheck="false" aria-label="SPARQL query"></textarea>
<div class="bar">
  <button class="primary" id="apply" title="Run the edited query (Ctrl+Enter)">Apply</button>
  <button id="inspect" title="Every variable of every row, and which FILTER part dropped a row — the query is not changed">Inspect</button>
  <button id="snapshot" title="Keep this text to come back to — for this session; closing VS Code forgets it">Snapshot</button>
  <button id="cancel" title="Back to the saved query">Cancel</button>
  <button id="save" title="Write it into shacl.ttl (Ctrl+S)">Save</button>
  <span class="status dim" id="status"></span>
  <button id="remove" title="Remove this ${escape(holder.kind)} from the shape">Remove…</button>
</div>
<div id="warnings"></div>
<div id="snapshots"></div>

<h2>Result</h2>
<div id="result" class="dim">${rule ? 'Apply shows the triples the rule constructs.'
    : 'Apply shows which focus nodes violate, and what the saved query says.'}</div>
<div id="inspected"></div>

<h2>What the query runs over</h2>
<p class="dim">${escape(page.stats.graph)} · ${page.data.triples} instance triple(s), ${
  page.data.derivedTriples} of them derived by rules, and ${page.stats.knowledge} knowledge
  triple(s) not shown.</p>
<details open><summary>Instance data (Turtle)</summary><pre id="data">${escape(page.data.turtle)}</pre></details>
${page.data.derivedTriples ? `<details><summary>Derived by rules (${page.data.derivedTriples})</summary>` +
  `<pre>${escape(page.data.derived)}</pre></details>` : ''}

<script nonce="${nonce}">
  const vscode = acquireVsCodeApi();
  const state = ${JSON.stringify(state).replace(/</g, '\\u003c')};
  const editor = document.getElementById('query');
  const apply = document.getElementById('apply');
  const cancel = document.getElementById('cancel');
  const save = document.getElementById('save');
  const status = document.getElementById('status');
  const esc = (text) => String(text == null ? '' : text).replace(/[&<>"']/g, (c) =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);

  // Set here, not in the markup: HTML drops a newline right after <textarea>,
  // and a query starts with one (""" then a line break) -- every query opened
  // as edited, and a Save would have stripped it. A text box also turns CRLF
  // into LF, so "edited" is judged with line ends normalised. (This script is
  // a template string: a backslash escape here must be written doubled.)
  const lines = (text) => String(text).replace(/\\r\\n?/g, '\\n');
  editor.value = state.draft;
  if (editor.value !== lines(state.draft)) {
    let at = 0;
    while (at < state.draft.length && editor.value[at] === state.draft[at]) { at += 1; }
    const codes = (text) => Array.from(text.slice(Math.max(at - 3, 0), at + 3))
      .map((c) => c.charCodeAt(0));
    vscode.postMessage({ command: 'mismatch', shown: editor.value.length,
      expected: state.draft.length, at, shownCodes: codes(editor.value),
      expectedCodes: codes(state.draft) });
  }
  function dirty() { return editor.value !== lines(state.baseline); }
  function update() {
    const changed = dirty();
    editor.classList.toggle('dirty', changed);
    cancel.disabled = !changed;
    save.disabled = !changed;
    vscode.postMessage({ command: 'draft', query: editor.value, dirty: changed });
  }
  function run() {
    status.textContent = 'running…';
    vscode.postMessage({ command: 'run', query: editor.value });
  }
  editor.addEventListener('input', update);
  editor.addEventListener('keydown', (event) => {
    if (event.key === 'Tab' && !event.shiftKey) {
      event.preventDefault();
      editor.setRangeText('    ', editor.selectionStart, editor.selectionEnd, 'end');
      update();
    } else if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
      event.preventDefault();
      run();
    } else if (event.key === 's' && (event.ctrlKey || event.metaKey)) {
      event.preventDefault();
      if (dirty()) { vscode.postMessage({ command: 'save', query: editor.value }); }
    }
  });
  apply.addEventListener('click', run);
  document.getElementById('inspect').addEventListener('click', () => {
    status.textContent = 'inspecting…';
    vscode.postMessage({ command: 'inspect', query: editor.value });
  });
  document.getElementById('snapshot').addEventListener('click', () =>
    vscode.postMessage({ command: 'snapshot', query: editor.value }));
  cancel.addEventListener('click', () => { editor.value = state.baseline; update(); run(); });
  save.addEventListener('click', () => vscode.postMessage({ command: 'save', query: editor.value }));
  document.getElementById('remove').addEventListener('click', () =>
    vscode.postMessage({ command: 'remove', dirty: dirty() }));
  document.getElementById('source').addEventListener('change', (event) =>
    vscode.postMessage({ command: 'source', source: event.target.value, query: editor.value }));
  document.addEventListener('click', (event) => {
    const snap = event.target.closest('[data-load],[data-drop]');
    if (snap) {
      event.preventDefault();
      if (snap.dataset.drop) {
        vscode.postMessage({ command: 'deleteSnapshot', id: Number(snap.dataset.drop) });
        return;
      }
      const chosen = snap.dataset.load === 'saved' ? { query: state.baseline }
        : state.snapshots.find((s) => String(s.id) === snap.dataset.load);
      if (chosen) {
        editor.value = chosen.query;
        update();
        run();
      }
      return;
    }
    const target = event.target.closest('[data-open],[data-shape],[data-holder]');
    if (!target) { return; }
    event.preventDefault();
    if (target.dataset.open) { vscode.postMessage({ command: 'open', at: target.dataset.open }); }
    else if (target.dataset.shape) { vscode.postMessage({ command: 'shape' }); }
    else { vscode.postMessage({ command: 'holder', index: Number(target.dataset.holder),
      dirty: dirty() }); }
  });

  function table(columns, rows) {
    return '<table><thead><tr>' + columns.map((c) => '<th>?' + esc(c) + '</th>').join('') +
      '</tr></thead><tbody>' + rows.map((row) => '<tr>' + columns.map((c) =>
        '<td>' + esc(row[c]) + '</td>').join('') + '</tr>').join('') + '</tbody></table>';
  }
  function show(result) {
    const out = document.getElementById('result');
    document.getElementById('warnings').innerHTML = (result.warnings || []).map((w) =>
      '<div class="warning">' + esc(w) + '</div>').join('');
    out.classList.remove('dim');
    if (!result.ok) {
      status.textContent = 'not run';
      out.innerHTML = '<div class="problem">' + esc(result.error) + '</div>';
      return;
    }
    status.textContent = 'ran in ' + result.ms + ' ms over ' + result.focusCount + ' focus node(s)';
    if (result.kind === 'rule') {
      const made = (result.focus || []).map((f) => esc(f.node) + ': ' + f.triples).join(' · ');
      out.innerHTML = '<p>' + (result.triples ? result.triples + ' triple(s) constructed'
        : 'Constructs nothing: the WHERE matched for no focus node.') + '</p>' +
        '<p class="dim">' + made + '</p>' +
        (result.triples ? '<pre>' + esc(result.constructed) + '</pre>' : '');
      return;
    }
    const violating = result.violating || [];
    let summary = '<p>' + (violating.length
      ? '<span class="chip bad">' + violating.length + ' violating</span> ' + esc(violating.join(', '))
      : '<span class="chip ok">no violation</span> every focus node conforms') + '</p>';
    if (result.saved) {
      const before = result.saved.violating || [];
      const added = violating.filter((n) => !before.includes(n));
      const gone = before.filter((n) => !violating.includes(n));
      summary += '<p class="dim">The saved query: ' + (before.length
        ? before.length + ' violating (' + esc(before.join(', ')) + ')' : 'no violation') +
        (added.length ? ' · now also ' + esc(added.join(', ')) : '') +
        (gone.length ? ' · no longer ' + esc(gone.join(', ')) : '') + '</p>';
    }
    const rows = (result.focus || []).filter((f) => f.rows.length).map((f) =>
      '<h3>' + esc(f.node) + '</h3>' + (f.messages || []).filter(Boolean).map((m) =>
        '<div class="warning">' + esc(m) + '</div>').join('') +
      table(result.columns || [], f.rows)).join('');
    out.innerHTML = summary + rows;
  }
  function snapshots() {
    const list = state.snapshots;
    const box = document.getElementById('snapshots');
    if (!list.length) { box.innerHTML = ''; return; }
    box.innerHTML = '<h2>Snapshots · this session only</h2>' +
      '<div class="snap"><span class="name">Saved in shacl.ttl</span>' +
      '<a href="#" data-load="saved">Load</a></div>' +
      list.map((s) => '<div class="snap"><span class="name">' + esc(s.name) + '</span>' +
        '<span class="dim">' + esc(s.verdict) + ' · ' + esc(s.at) + '</span>' +
        '<a href="#" data-load="' + s.id + '">Load</a>' +
        '<a href="#" data-drop="' + s.id + '">Delete</a></div>').join('');
  }
  function mark(held) {
    return held === true ? '<td class="yes">✓</td>' : held === false ? '<td class="no">✗</td>'
      : '<td class="err" title="an error: FILTER counts it as false">⚠</td>';
  }
  function inspected(result) {
    const out = document.getElementById('inspected');
    if (!result.ok) {
      out.innerHTML = '<h2>Inspect</h2><div class="problem">' + esc(result.error) + '</div>';
      return;
    }
    status.textContent = 'inspected in ' + result.ms + ' ms';
    const filters = result.filters || [];
    const legend = filters.map((f, i) => '<div><b>F' + (i + 1) + '</b> <code>' + esc(f) +
      '</code></div>').join('');
    const head = '<tr>' + result.columns.map((c) => '<th>?' + esc(c) + '</th>').join('') +
      filters.map((f, i) => '<th title="' + esc(f) + '">F' + (i + 1) + '</th>').join('') +
      '<th></th></tr>';
    const blocks = (result.focus || []).map((f) => {
      const rows = f.rows.map((r) => '<tr class="' + (r.kept ? 'kept' : 'dropped') + '">' +
        result.columns.map((c) => '<td>' + esc(r.values[c] || '') + '</td>').join('') +
        r.checks.map(mark).join('') + '<td>' + (r.kept ? (result.kind === 'rule'
          ? 'constructs' : 'violation') : 'dropped') + '</td></tr>').join('');
      return '<h3>' + esc(f.node) + ' <span class="dim">· ' + f.total + ' row(s) from the WHERE, ' +
        f.kept + ' kept' + (f.total > f.rows.length ? ', first ' + f.rows.length + ' shown' : '') +
        '</span></h3>' + (f.total ? '<table><thead>' + head + '</thead><tbody>' + rows +
        '</tbody></table>' : '<p class="dim">The pattern matches nothing for this node: ' +
        'no FILTER is reached.</p>');
    }).join('');
    out.innerHTML = '<h2>Inspect</h2>' + (result.notes || []).map((n) =>
      '<div class="warning">' + esc(n) + '</div>').join('') +
      (legend ? '<div class="dim">' + legend + '</div>' : '<p class="dim">No outer FILTER: every ' +
        'row of the WHERE is kept.</p>') + blocks;
  }
  window.addEventListener('message', (event) => {
    const message = event.data || {};
    if (message.type === 'result') { show(message.result); }
    else if (message.type === 'inspect') { inspected(message.result); }
    else if (message.type === 'snapshots') { state.snapshots = message.list; snapshots(); }
    else if (message.type === 'saved') {
      state.baseline = message.query;
      update();
      status.textContent = 'saved to ' + message.where;
    } else if (message.type === 'error') { status.textContent = message.text; }
  });
  update();
  snapshots();
  run();
</script>
</body></html>`;
}

function renderMessage(text) {
  return `<!DOCTYPE html><html><head><meta charset="utf-8">` +
    `<meta http-equiv="Content-Security-Policy" content="default-src 'none';"></head>` +
    `<body><p>${escape(text)}</p></body></html>`;
}

class SparqlBench {
  constructor(clientHolder) {
    this.clientHolder = clientHolder;
    this.panel = undefined;
    this.current = undefined;
    this.page = undefined;
    this.draft = undefined;          // the editor's text, kept across re-renders
    this.dirty = false;
    // Snapshots: texts kept to come back to, per query, for this session only.
    // Nothing is written anywhere: closing VS Code keeps the saved query alone.
    this.snapshots = new Map();
    this.nextSnapshot = 1;
  }

  snapshotKey() {
    return this.current && this.page
      ? `${this.current.packageUri}|${this.current.shape}|${this.page.holder.index}` : '';
  }

  snapshotList() {
    return this.snapshots.get(this.snapshotKey()) || [];
  }

  async snapshot(query) {
    const list = this.snapshotList();
    const name = await vscode.window.showInputBox({
      title: 'Snapshot', value: `Snapshot ${list.length + 1}`,
      prompt: 'Kept for this session, to come back to — closing VS Code forgets it. ' +
        'Only Save writes shacl.ttl.'
    });
    if (name === undefined) {
      return undefined;
    }
    const ran = await this.request('semforge/sparqlRun', { index: this.page.holder.index,
      source: this.current.source, query });
    const where = (this.page.sources.find((s) => s.id === this.current.source) || {}).label ||
      this.current.source;
    const verdict = !ran.ok ? 'does not run'
      : ran.kind === 'rule' ? `${ran.triples} triple(s) on ${where}`
        : `${ran.violating.length} violating on ${where}`;
    const entry = { id: this.nextSnapshot++, name: name || `Snapshot ${list.length + 1}`,
      query, verdict, at: new Date().toLocaleTimeString() };
    this.snapshots.set(this.snapshotKey(), list.concat([entry]));
    this.post({ type: 'snapshots', list: this.snapshotList() });
    return entry;
  }

  deleteSnapshot(id) {
    this.snapshots.set(this.snapshotKey(), this.snapshotList().filter((s) => s.id !== id));
    this.post({ type: 'snapshots', list: this.snapshotList() });
  }

  /** `options`: {index, query, kind, source} -- which query, over which data. */
  async show(packageUri, shape, options) {
    if (!this.clientHolder.client || !packageUri || !shape) {
      vscode.window.showWarningMessage(
        'SemForge: no package is open, or the language server is not running.');
      return;
    }
    const wanted = Object.assign({}, options || {});
    const same = this.current && this.current.packageUri === packageUri &&
      this.current.shape === shape && (wanted.query === undefined ||
        (this.page && this.page.holder.query.trim() === String(wanted.query).trim()));
    if (this.panel && this.dirty && !same && !(await this.discard())) {
      this.panel.reveal();
      return;
    }
    this.current = { packageUri, shape, index: wanted.index, query: wanted.query,
      kind: wanted.kind, source: wanted.source || '@main' };
    if (!same) {
      this.draft = undefined;
      this.dirty = false;
    }
    if (!this.panel) {
      this.panel = vscode.window.createWebviewPanel('semforgeSparqlBench', 'SPARQL',
        { viewColumn: vscode.ViewColumn.Active, preserveFocus: !!wanted.preserveFocus },
        { enableScripts: true, retainContextWhenHidden: true, localResourceRoots: [] });
      this.panel.onDidDispose(() => this.closed());
      this.panel.webview.onDidReceiveMessage((message) => this.receive(message));
    } else {
      this.panel.reveal(undefined, !!wanted.preserveFocus);
      if (same && this.page) {
        return;
      }
    }
    await this.render();
  }

  async discard() {
    const answer = await vscode.window.showWarningMessage(
      `The SPARQL query of ${this.page ? this.page.label : 'this shape'} has unsaved edits.`,
      { modal: true }, 'Discard them');
    return answer === 'Discard them';
  }

  closed() {
    this.panel = undefined;
    if (this.dirty && this.current) {
      // A webview cannot refuse to close; what it can do is not lose the text.
      const kept = Object.assign({}, this.current, { draft: this.draft,
        query: this.page && this.page.holder.query });
      vscode.window.showWarningMessage(
        `SemForge: the SPARQL workbench closed with unsaved edits to ${this.page
          ? this.page.label : 'a query'}.`,
        'Reopen with them').then((answer) => {
        if (answer === 'Reopen with them') {
          this.reopen(kept);
        }
      });
    }
  }

  async reopen(kept) {
    await this.show(kept.packageUri, kept.shape, { query: kept.query, source: kept.source });
    this.draft = kept.draft;
    this.dirty = true;
    await this.render();
  }

  async request(method, params) {
    try {
      return await this.clientHolder.client.sendRequest(method,
        Object.assign({ uri: this.current.packageUri, shape: this.current.shape }, params));
    } catch (error) {
      return { ok: false, error: error.message || String(error) };
    }
  }

  async render() {
    if (!this.panel || !this.current) {
      return;
    }
    const page = await this.request('semforge/sparqlBench', {
      index: this.current.index, query: this.current.query, kind: this.current.kind,
      source: this.current.source });
    if (!this.panel) {
      return;
    }
    if (!page.ok) {
      this.panel.title = 'SPARQL';
      this.panel.webview.html = renderMessage(`SemForge: ${page.error}`);
      return;
    }
    this.page = page;
    this.current.index = page.holder.index;
    this.current.query = page.holder.query;
    this.panel.title = `${page.label} · SPARQL`;
    this.panel.webview.html = renderSparqlBench(page, {
      nonce: crypto.randomBytes(16).toString('base64'), draft: this.draft,
      snapshots: this.snapshotList() });
  }

  async receive(message) {
    if (!message || !this.current || !this.page) {
      return;
    }
    if (message.command === 'mismatch') {
      this.mismatch = message;          // the editor does not hold what it was given
    } else if (message.command === 'draft') {
      this.draft = message.query;
      this.dirty = !!message.dirty;
    } else if (message.command === 'run') {
      const result = await this.request('semforge/sparqlRun', { index: this.page.holder.index,
        source: this.current.source, query: message.query });
      this.post({ type: 'result', result });
      return result;
    } else if (message.command === 'inspect') {
      const result = await this.request('semforge/sparqlInspect', {
        index: this.page.holder.index, source: this.current.source, query: message.query });
      this.post({ type: 'inspect', result });
      return result;
    } else if (message.command === 'snapshot') {
      return this.snapshot(message.query);
    } else if (message.command === 'deleteSnapshot') {
      this.deleteSnapshot(message.id);
    } else if (message.command === 'save') {
      return this.save(message.query);
    } else if (message.command === 'remove') {
      return this.remove(!!message.dirty);
    } else if (message.command === 'source') {
      this.draft = message.query;
      this.current.source = message.source;
      await this.render();
    } else if (message.command === 'holder') {
      if (message.dirty && !(await this.discard())) {
        return;
      }
      this.draft = undefined;
      this.dirty = false;
      this.current.query = undefined;
      this.current.index = message.index;
      await this.render();
    } else if (message.command === 'open' && message.at) {
      await showLocation(message.at, true);
    } else if (message.command === 'shape') {
      await vscode.commands.executeCommand('semforge.openShapePage',
        { raw: { shape: this.current.shape }, packageUri: this.current.packageUri });
    }
    return undefined;
  }

  async save(query) {
    const result = await this.request('semforge/sparqlSave', {
      index: this.page.holder.index, query, expected: this.page.holder.query });
    if (!result.ok) {
      vscode.window.showErrorMessage(`SemForge: ${result.error}`);
      this.post({ type: 'error', text: 'not saved' });
      return result;
    }
    this.page.holder.query = query;
    this.current.query = query;
    this.draft = query;
    this.dirty = false;
    this.post({ type: 'saved', query, where: `shacl.ttl:${result.line}` });
    for (const command of REFRESH_VIEWS) {
      vscode.commands.executeCommand(command);
    }
    vscode.window.setStatusBarMessage(
      `SemForge: the query of ${this.page.label} saved — validation re-runs`, 5000);
    return result;
  }

  /** Remove the open query; the page then shows the shape's next one, or closes. */
  async remove(dirty) {
    const done = await removeQuery(this.clientHolder, this.current.packageUri,
      this.current.shape, this.page.holder, this.page.label, dirty);
    if (!done) {
      return undefined;
    }
    this.draft = undefined;
    this.dirty = false;
    this.current.query = undefined;
    this.current.index = 0;
    const next = await this.request('semforge/sparqlBench', { index: 0,
      source: this.current.source });
    if (!next.ok && this.panel) {
      this.panel.dispose();            // that was the shape's last query
    } else {
      await this.render();
    }
    return done;
  }

  post(message) {
    if (this.panel) {
      this.panel.webview.postMessage(message);
    }
  }

  /** A save elsewhere: re-read the data, but never over unsaved edits. */
  refresh() {
    if (this.panel && this.panel.visible && !this.dirty) {
      this.draft = undefined;
      this.render();
    }
  }
}

/**
 * Remove one SPARQL constraint or rule, after saying what goes with it: the
 * test cases that assert it (asserts name the shape's SPARQL constraints
 * together, so they only lose their meaning with its LAST one), and unsaved
 * edits in the workbench. Returns the server's answer, or undefined.
 */
async function removeQuery(clientHolder, packageUri, shape, holder, label, dirty) {
  const client = clientHolder.client;
  const which = { uri: packageUri, shape, query: holder.query, kind: holder.kind };
  const plan = await client.sendRequest('semforge/sparqlRemovalPlan', which);
  if (!plan.ok) {
    vscode.window.showErrorMessage(`SemForge: ${plan.error}`);
    return undefined;
  }
  const what = holder.kind === 'rule' ? 'SPARQL rule'
    : `SPARQL constraint${holder.message ? ` "${holder.message}"` : ''}`;
  const lines = [];
  const cases = plan.asserts.map((a) => `  ${a.case}${a.resource ? ` (on ${a.resource})` : ''}`);
  let buttons = ['Remove'];
  if (plan.asserts.length && plan.last) {
    lines.push(`${plan.asserts.length} test case assert(s) name it, and no other SPARQL ` +
      'constraint of this shape is left to satisfy them:', ...cases,
    'Removing them too keeps those cases meaningful; keeping them makes them fail.');
    buttons = ['Remove it and its asserts', 'Remove it only'];
  } else if (plan.asserts.length) {
    lines.push(`${plan.asserts.length} test case assert(s) name this shape's SPARQL ` +
      `constraints; ${plan.others} other(s) remain, so the asserts are kept:`, ...cases);
  }
  if (dirty) {
    lines.push('Its unsaved edits in the workbench go with it.');
  }
  lines.push(`Written at shacl.ttl:${plan.holder.line}.`);
  const answer = await vscode.window.showWarningMessage(
    `Remove the ${what} from ${label}?`, { modal: true, detail: lines.join('\n') }, ...buttons);
  if (!answer) {
    return undefined;
  }
  const done = await client.sendRequest('semforge/sparqlRemove', Object.assign(which,
    { expected: holder.query, dropAsserts: answer === 'Remove it and its asserts' }));
  if (!done.ok) {
    vscode.window.showErrorMessage(`SemForge: ${done.error}`);
    return undefined;
  }
  for (const command of REFRESH_VIEWS) {
    vscode.commands.executeCommand(command);
  }
  vscode.window.setStatusBarMessage(`SemForge: the ${what} removed from ${label}` +
    (done.asserts ? `, with ${done.asserts} assert(s)` : ''), 6000);
  return done;
}

/** + SPARQL constraint: ask what a violation means, write a skeleton, open it. */
async function addConstraint(bench, clientHolder, packageUri, shape, label) {
  const message = await vscode.window.showInputBox({
    title: `New SPARQL constraint on ${label}`,
    prompt: 'Its sh:message: what a violation means, e.g. "Cutter running without a filter". ' +
      '{?var} is filled from the query\'s row.',
    validateInput: (text) => (text && text.trim() ? undefined : 'a message is required')
  });
  if (!message) {
    return undefined;
  }
  const made = await clientHolder.client.sendRequest('semforge/addSparqlConstraint',
    { uri: packageUri, shape, message });
  if (!made.ok) {
    vscode.window.showErrorMessage(`SemForge: ${made.error}`);
    return undefined;
  }
  for (const command of REFRESH_VIEWS) {
    vscode.commands.executeCommand(command);
  }
  await bench.show(packageUri, shape, { index: made.index });
  vscode.window.showInformationMessage(
    'SemForge: a SPARQL constraint that fires on nothing yet — write its condition, Apply ' +
      'to see what it finds, Save when it says what you mean.');
  return made;
}

function register(context, clientHolder, session) {
  const bench = new SparqlBench(clientHolder);
  const target = (node) => ({
    packageUri: (node && node.packageUri) || session.uri,
    shape: node && node.raw && (node.raw.shape || node.raw.iri)
  });
  context.subscriptions.push(
    vscode.commands.registerCommand('semforge.openSparqlBench', async (node, options) => {
      const { packageUri, shape } = target(node);
      if (!shape) {
        vscode.window.showInformationMessage('SemForge: open the workbench from a shape.');
        return;
      }
      await bench.show(packageUri, shape, options);
    }),
    vscode.commands.registerCommand('semforge.addSparqlConstraint', async (node) => {
      const { packageUri, shape } = target(node);
      if (!shape || !clientHolder.client) {
        return undefined;
      }
      return addConstraint(bench, clientHolder, packageUri, shape,
        (node.raw.label || shape.split(/[/#]/).pop()));
    }),
    // From the shape page: which query is said by its text.
    vscode.commands.registerCommand('semforge.removeSparqlQuery', async (node, holder) => {
      const { packageUri, shape } = target(node);
      if (!shape || !holder || !clientHolder.client) {
        return undefined;
      }
      const label = node.raw.label || shape.split(/[/#]/).pop();
      const open = bench.panel && bench.current && bench.current.shape === shape &&
        bench.page && bench.page.holder.query.trim() === String(holder.query).trim();
      if (open) {
        bench.panel.reveal();
        return bench.remove(bench.dirty);
      }
      return removeQuery(clientHolder, packageUri, shape, holder, label, false);
    }),
    vscode.workspace.onDidSaveTextDocument(() => bench.refresh())
  );
  return bench;
}

module.exports = { register, renderSparqlBench, SparqlBench };
