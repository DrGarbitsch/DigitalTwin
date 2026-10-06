/*
 * The shape page: what one shape checks, and what it reaches.
 *
 * A shape is not tied to an entity type. It targets nodes -- by class, by
 * named node, by the subjects or objects of a predicate, by a SPARQL query --
 * or nothing, being reached from another shape through sh:node. The type
 * page reads constraints by type; this page is the shape's own: its target in
 * words, its attributes and rules (the same rows the type page shows), the
 * nodes it reaches in the model, the types those are, and the cases that make
 * it fire.
 *
 * Its attributes are edited as on the type page -- the same rows, the same
 * actions (presence, value, ⋯, New test…, + Attribute) -- written into this
 * shape. `renderShapePage` is a pure function from the payload
 * `semforge/shapePage` returns; everything shown is escaped, and script and
 * style run only with the per-render nonce.
 */

const crypto = require('crypto');
const vscode = require('vscode');

const { showLocation } = require('./reveal');
const { escape, attributeRows: typeRows, EDITS } = require('./typepage');
const { pickTarget } = require('./shapes');

function chip(text, tone, title) {
  return `<span class="chip ${tone || ''}"${title ? ` title="${escape(title)}"` : ''}>` +
    `${escape(text)}</span>`;
}

function shapeLink(name, iri) {
  return `<a href="#" data-shape="${escape(iri)}">${escape(name)}</a>`;
}

function targetSection(page) {
  const targets = page.targets || [];
  if (!targets.length) {
    const users = page.usedBy || [];
    return users.length
      ? `<p>No target of its own. It is checked wherever ${users.map((u) =>
        shapeLink(u.name, u.iri)).join(', ')} reaches it through <span class="mono">sh:node</span>.</p>`
      : '<p class="empty">No target, and no shape uses it: SHACL never evaluates it.</p>';
  }
  // Each target can be taken off here; a SPARQL target is a query, and an
  // implicit one is the shape being a class -- both are edited in the .ttl.
  return `<div class="rules">${targets.map((t, index) => `<div class="rule">` +
    `<span class="mono">${escape(
      { class: 'sh:targetClass', node: 'sh:targetNode', subjectsOf: 'sh:targetSubjectsOf',
        objectsOf: 'sh:targetObjectsOf', sparql: 'sh:target', implicit: 'implicit' }[t.kind] ||
      t.kind)}</span><span>${escape(t.text)}` +
    (t.kind === 'sparql' && t.value
      ? `<pre class="query">${escape(t.value.trim())}</pre>` : '') + '</span>' +
    (['class', 'node', 'subjectsOf', 'objectsOf'].includes(t.kind)
      ? `<button data-action="removeTarget" data-row="${index}" ` +
        'title="Take this target off the shape">Remove</button>' : '<span></span>') +
    '</div>').join('')}</div>`;
}

/** The type page's rows, actions and all: a shape's attributes are edited
 *  here the same way, written into this shape. */
function attributeRows(attributes) {
  return typeRows(attributes, -1, { shapeColumn: false });
}

const NEW_CASE_TIP = 'Writes a bad case asserting this shape fires, copied from a ' +
  'scene where it holds. It fails until you edit its data so the rule is broken: ' +
  'it cannot pass by accident.';

function caseChips(cases) {
  return cases.length ? `<div class="chips">${cases.map((c) =>
    `<a href="#" data-case="${escape(c.file)}" title="${escape(c.description || '')}">` +
    chip(`${c.case.split('/').slice(-3).join(' / ')} · ` +
      (c.fired ? `fires ${c.fired}×` : 'holds') + ` · ${c.passed ? 'passes' : 'FAILS'}`,
    c.passed ? (c.fired ? 'ok' : '') : 'bad') + '</a>').join('')}</div>` : '';
}

/** What a SPARQL shape checks, the evidence it can fire, and its query. */
function checkSections(page, checks, cases) {
  const fires = cases.filter((c) => c.fired);
  const holds = cases.filter((c) => !c.fired);
  const said = checks.map((c) => `<div class="rule"><span class="kind">${escape(c.kind)}</span>` +
    `<span>${escape(c.message || (c.kind === 'rule'
      ? 'Derives data; a rule adds facts rather than reporting'
      : 'No sh:message: the query below is all it says'))}</span>` +
    `${c.severity ? chip(`severity: ${c.severity}`,
      c.severity === 'warning' ? 'warn' : c.severity === 'info' ? '' : 'bad') : ''}</div>`).join('');
  const constraint = checks.some((c) => c.kind === 'constraint');
  const evidence = !constraint ? '' : [
    fires.length
      ? `<div class="rule">${chip(`fires in ${fires.length}`, 'ok')}<span>` +
        fires.map((c) => `<a href="#" data-case="${escape(c.file)}">` +
          `${escape(c.case.split('/').slice(-3).join(' / '))}</a>` +
          (c.firedOn.length ? ` <span class="dim">on ${escape(c.firedOn.join(', '))}</span>` : ''))
          .join('<br>') + '</span><span></span></div>'
      : `<div class="rule">${chip('fires in 0', 'warn')}<span>No test case makes it fire. ` +
        'A rule that cannot fire looks exactly like one that holds.</span>' +
        (page.canNewCase ? `<button class="primary" data-newcase="1" title="${escape(NEW_CASE_TIP)}">` +
          'New case…</button>' : '<span></span>') + '</div>',
    holds.length
      ? `<div class="rule">${chip(`holds in ${holds.length}`)}<span>Evaluated in ` +
        `${holds.length} case(s), conforming: ` + holds.map((c) =>
          `<a href="#" data-case="${escape(c.file)}">${escape(c.case.split('/').slice(-3).join(' / '))}</a>`)
          .join(', ') + '</span><span></span></div>'
      : '',
    !cases.length
      ? `<div class="rule">${chip('0 cases')}<span>No test case reaches it at all.</span>` +
        '<span></span></div>'
      : ''
  ].join('');
  // A query is where a SPARQL constraint is developed: a click opens it in
  // the workbench, run over the same data validation gives it.
  const queries = checks.map((c, i) => (c.query
    ? `<div class="bar"><button class="primary" data-action="bench" data-row="${i}" ` +
      'title="Edit it, run it over a test case\'s data, save it">Open in SPARQL workbench</button>' +
      `<button data-action="removeSparql" data-row="${i}" title="Remove this ${escape(c.kind)} ` +
      'from the shape">Remove…</button>' +
      `<span class="dim">${escape(c.kind)}${c.message ? ` · ${escape(c.message)}` : ''}</span></div>` +
      `<pre class="query bench" data-action="bench" data-row="${i}" ` +
      `title="Open in the SPARQL workbench">${escape(c.query)}</pre>` : '')).join('');
  // Apart, so the page can put what it checks under Constraints and the
  // evidence after what it reaches.
  return { said: `<div class="rules">${said}</div>` +
      (queries ? `<p class="dim">The query · click it to develop it in the SPARQL workbench</p>${queries}` : ''),
    evidence: evidence ? `<div class="rules">${evidence}</div>` : '' };
}

function renderShapePage(page, options) {
  const nonce = (options && options.nonce) || '';
  const csp = `default-src 'none'; style-src 'nonce-${nonce}'; script-src 'nonce-${nonce}';`;
  const summary = page.summary || {};
  const attributes = page.attributes || [];
  const checks = page.checks || [];
  const cases = page.exercisedBy || [];
  const parts = checks.length ? checkSections(page, checks, cases) : null;
  const reach = page.reach || { nodes: [], more: 0 };
  const types = page.types || [];
  const chips = [
    chip(page.target || ''),
    summary.violations
      ? chip(`${summary.violations} violation(s) in the model`, 'bad')
      : summary.reached ? chip(`${summary.reached} in the model · all valid`, 'ok')
        : chip('reaches nothing in the model'),
    summary.cases
      ? chip(`${summary.cases} case(s) reach it · ` +
        (summary.casesFailing ? `${summary.casesFailing} failing` : 'all pass'),
      summary.casesFailing ? 'bad' : 'ok')
      : chip('no test case reaches it', 'warn'),
    summary.neverFired ? chip('never fired', 'warn',
      'No test case makes this shape report anything. A shape that cannot fire ' +
      'looks exactly like one that holds.') : ''
  ].join('');

  return `<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="${csp}">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${escape(page.label)}</title>
<style nonce="${nonce}">
  body { font-family: var(--vscode-font-family); font-size: var(--vscode-font-size);
         color: var(--vscode-foreground); background: var(--vscode-editor-background);
         padding: 16px 22px 40px; line-height: 1.45; }
  a { color: var(--vscode-textLink-foreground); text-decoration: none; }
  a:hover, a:focus-visible { text-decoration: underline; }
  .crumbs, .dim, .empty { color: var(--vscode-descriptionForeground); }
  .crumbs { font-size: 0.92em; }
  .empty { font-style: italic; }
  h1 { font-size: 1.6em; font-weight: 600; margin: 4px 0 8px; }
  h2 { font-size: 0.78em; font-weight: 600; letter-spacing: .08em; text-transform: uppercase;
       color: var(--vscode-descriptionForeground); margin: 26px 0 8px; }
  h3 { font-size: 1em; font-weight: 600; margin: 14px 0 6px; }
  .chips { display: flex; flex-wrap: wrap; gap: 6px; }
  .chips.top { margin-top: 8px; }
  .chip { font-size: 0.86em; padding: 1px 8px; border-radius: 999px; white-space: nowrap;
          border: 1px solid var(--vscode-panel-border, rgba(128,128,128,.35)); }
  .chip.ok { color: var(--vscode-testing-iconPassed, #388a34); border-color: currentColor; }
  .chip.bad { color: var(--vscode-errorForeground, #f14c4c); border-color: currentColor; }
  .chip.warn { color: var(--vscode-editorWarning-foreground, #cca700); border-color: currentColor; }
  .bar { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }
  button { font: inherit; color: var(--vscode-button-secondaryForeground, inherit);
           background: var(--vscode-button-secondaryBackground, transparent);
           border: 1px solid var(--vscode-panel-border, rgba(128,128,128,.35));
           padding: 3px 10px; border-radius: 2px; cursor: pointer; }
  button.primary { background: var(--vscode-button-background); color: var(--vscode-button-foreground);
                   border-color: var(--vscode-button-background); }
  .table { overflow-x: auto; border: 1px solid var(--vscode-panel-border, rgba(128,128,128,.35)); }
  table { border-collapse: collapse; width: 100%; }
  th { text-align: left; font-size: 0.78em; letter-spacing: .06em; text-transform: uppercase;
       color: var(--vscode-descriptionForeground); font-weight: 600; padding: 7px 12px;
       background: var(--vscode-sideBar-background, transparent); }
  td { padding: 6px 12px; border-top: 1px solid var(--vscode-panel-border, rgba(128,128,128,.25));
       white-space: nowrap; vertical-align: top; }
  tr.flag td:first-child { box-shadow: inset 3px 0 0 var(--vscode-errorForeground, #f14c4c); }
  tr:hover td { background: var(--vscode-list-hoverBackground); }
  a.act { color: inherit; border-bottom: 1px dashed var(--vscode-descriptionForeground); }
  a.act:hover, a.act:focus-visible { color: var(--vscode-textLink-foreground); text-decoration: none; }
  td.acts { text-align: right; }
  td.acts button { padding: 0 8px; }
  td.depth1 { padding-left: 30px; } td.depth2 { padding-left: 48px; }
  td.depth3 { padding-left: 66px; } td.depth4 { padding-left: 84px; }
  .kind { font-size: 0.84em; padding: 0 6px; border-radius: 3px;
          background: var(--vscode-badge-background); color: var(--vscode-badge-foreground); }
  .mono, .verbatim, .query { font-family: var(--vscode-editor-font-family); font-size: 0.92em; }
  .verbatim { color: var(--vscode-descriptionForeground); white-space: normal; margin-top: 2px; }
  .query { white-space: pre-wrap; overflow-wrap: anywhere; margin: 6px 0 0; padding: 8px 10px;
           background: var(--vscode-textCodeBlock-background, rgba(128,128,128,.1)); }
  ul { margin: 0; padding-left: 1.2em; display: grid; gap: 4px; }
  .rule { display: grid; grid-template-columns: auto 1fr auto; gap: 10px; align-items: baseline;
          padding: 6px 10px; border: 1px solid var(--vscode-panel-border, rgba(128,128,128,.35));
          margin-bottom: 6px; }
</style></head><body>
<div class="crumbs">Shapes ›</div>
<h1>${escape(page.label)}</h1>
<div class="dim mono">${escape(page.name)}</div>
<div class="chips top">${chips}</div>
<div class="bar">${page.definedAt ? `<button data-open="${escape(page.definedAt)}">Open in .ttl</button>` : ''}
${types.filter((t) => t.page).slice(0, 1).map((t) =>
    `<button data-type="${escape(t.iri)}">Open ${escape(t.label)} type page</button>`).join('')}
<button data-action="merge" title="Fold this shape into another that selects the same nodes">Merge into…</button>
<button data-refresh="1">Refresh</button></div>

<h2>Selects</h2>
<p class="dim">The node selector: which nodes the constraints below are checked on.
Several targets add up.</p>
${targetSection(page)}
<div class="bar"><button data-action="addTarget">+ Target</button></div>

<h2>Constraints</h2>
<h3>On its attributes</h3>
${attributes.length ? `<div class="table"><table>
<thead><tr><th>Attribute</th><th>Kind</th><th>Presence</th><th>Value</th><th>Tested</th><th>Model</th><th></th></tr></thead>
<tbody>${attributeRows(attributes)}</tbody></table></div>`
    : '<p class="empty">None yet.</p>'}
${page.ownShape ? '<div class="bar"><button class="primary" data-action="addAttribute">+ Attribute</button></div>' : ''}
<h3>On the whole node</h3>
${parts ? parts.said
    : '<p class="empty">No SPARQL constraint or rule yet.</p>'}
<div class="bar"><button data-action="addSparql" title="A SPARQL constraint reads the node as a whole; it is written in the workbench">+ SPARQL constraint</button></div>

<h2>Reaches</h2>
${types.length ? `<div class="chips">${types.map((t) => t.page
    ? `<a href="#" data-type="${escape(t.iri)}">${chip(t.label)}</a>`
    : chip(t.label, '', t.iri)).join('')}</div>` : ''}
${reach.nodes.length ? `<ul>${reach.nodes.map((n) => `<li><span class="mono">${escape(n.id)}</span> ` +
    (n.violations.length ? n.violations.map((v) => chip(v, 'bad')).join(' ') : chip('valid', 'ok')) +
    '</li>').join('')}${reach.more ? `<li class="dim">… and ${reach.more} more</li>` : ''}</ul>`
    : '<p class="empty">Nothing in the model is a focus node of this shape.</p>'}

<h2>Evidence</h2>
${parts && parts.evidence ? parts.evidence
    : caseChips(cases) || '<p class="empty">No test case reaches it. Nothing proves it can fire.</p>'}

<script nonce="${nonce}">
  const vscode = acquireVsCodeApi();
  document.addEventListener('click', (event) => {
    const target = event.target.closest('[data-open],[data-type],[data-shape],[data-case],[data-newcase],[data-action],[data-refresh]');
    if (!target) { return; }
    event.preventDefault();
    if (target.dataset.action) {
      vscode.postMessage({ command: target.dataset.action,
                           row: target.dataset.row === undefined ? -1 : Number(target.dataset.row) });
    }
    else if (target.dataset.open) { vscode.postMessage({ command: 'open', at: target.dataset.open }); }
    else if (target.dataset.type) { vscode.postMessage({ command: 'type', name: target.dataset.type }); }
    else if (target.dataset.shape) { vscode.postMessage({ command: 'shape', name: target.dataset.shape }); }
    else if (target.dataset.case) { vscode.postMessage({ command: 'case', file: target.dataset.case }); }
    else if (target.dataset.newcase) { vscode.postMessage({ command: 'newCase' }); }
    else { vscode.postMessage({ command: 'refresh' }); }
  });
</script>
</body></html>`;
}

function renderMessage(message) {
  return `<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'none';"></head>
<body><p>${escape(message)}</p></body></html>`;
}

/** One reused panel, like the type page. */
class ShapePages {
  constructor(clientHolder) {
    this.clientHolder = clientHolder;
    this.panel = undefined;
    this.current = undefined;
  }

  async show(packageUri, shape, preserveFocus) {
    if (!this.clientHolder.client || !packageUri || !shape) {
      vscode.window.showWarningMessage(
        'SemForge: no package is open, or the language server is not running.');
      return;
    }
    const same = this.panel && this.current && this.current.packageUri === packageUri &&
      this.current.shape === shape;
    this.current = { packageUri, shape };
    if (!this.panel) {
      this.panel = vscode.window.createWebviewPanel(
        'semforgeShapePage', 'Shape',
        { viewColumn: vscode.ViewColumn.Active, preserveFocus: !!preserveFocus },
        { enableScripts: true, localResourceRoots: [] });
      this.panel.onDidDispose(() => { this.panel = undefined; });
      this.panel.webview.onDidReceiveMessage((message) => this.receive(message));
    } else {
      this.panel.reveal(undefined, !!preserveFocus);
      if (same) {
        return;
      }
    }
    await this.render();
  }

  async render() {
    if (!this.panel || !this.current) {
      return;
    }
    let page;
    try {
      page = await this.clientHolder.client.sendRequest('semforge/shapePage',
        { uri: this.current.packageUri, shape: this.current.shape });
    } catch (error) {
      page = { ok: false, error: error.message || String(error) };
    }
    if (!this.panel) {
      return;
    }
    if (!page.ok) {
      this.panel.title = 'Shape';
      this.panel.webview.html = renderMessage(`SemForge: ${page.error}`);
      return;
    }
    this.page = page;
    this.panel.title = `${page.label} · shape`;
    this.panel.webview.html = renderShapePage(page,
      { nonce: crypto.randomBytes(16).toString('base64') });
  }

  async receive(message) {
    if (!message || !this.current) {
      return;
    }
    const packageUri = this.current.packageUri;
    const edit = EDITS[message.command];
    if (edit) {
      // The type page's own edits: they write into `page.ownShape`, which
      // here is this shape.
      const row = this.page && this.page.attributes
        ? this.page.attributes[message.row] : undefined;
      if (await edit(this, row)) {
        await this.render();
        for (const command of ['semforge.refreshTree', 'semforge.refreshShapes',
          'semforge.refreshKnowledge', 'semforge.refreshModel']) {
          vscode.commands.executeCommand(command);
        }
      }
    } else if (message.command === 'bench') {
      const check = (this.page.checks || [])[message.row];
      if (check) {
        await vscode.commands.executeCommand('semforge.openSparqlBench',
          { raw: { shape: this.page.iri }, packageUri },
          { query: check.query, kind: check.kind });
      }
    } else if (message.command === 'removeSparql') {
      const check = (this.page.checks || [])[message.row];
      if (check && await vscode.commands.executeCommand('semforge.removeSparqlQuery',
        { raw: { shape: this.page.iri, label: this.page.label }, packageUri },
        { query: check.query, kind: check.kind, message: check.message })) {
        await this.render();
      }
    } else if (message.command === 'addSparql') {
      if (await vscode.commands.executeCommand('semforge.addSparqlConstraint',
        { raw: { shape: this.page.iri, label: this.page.label }, packageUri })) {
        this.render();
      }
    } else if (message.command === 'open' && message.at) {
      await showLocation(message.at, true);
    } else if (message.command === 'type' && message.name) {
      await vscode.commands.executeCommand('semforge.openTypePage',
        { raw: { targetClass: message.name }, packageUri });
    } else if (message.command === 'shape' && message.name) {
      await this.show(packageUri, message.name);
    } else if (message.command === 'case' && message.file) {
      await vscode.commands.executeCommand('semforge.openCasePage',
        { raw: { kind: 'example', file: message.file }, packageUri });
    } else if (message.command === 'merge') {
      // On success the merged-into shape's page replaces this one.
      await vscode.commands.executeCommand('semforge.mergeShape',
        { raw: { shape: this.page.iri }, packageUri: this.current.packageUri });
    } else if (message.command === 'addTarget' || message.command === 'removeTarget') {
      if (await this.editTarget(message)) {
        await this.render();
        for (const command of ['semforge.refreshShapes', 'semforge.refreshTree']) {
          vscode.commands.executeCommand(command);
        }
      }
    } else if (message.command === 'newCase') {
      await this.newCase();
    } else if (message.command === 'refresh') {
      await this.render();
    }
  }

  /** + Target and Remove: the node selector, edited in place. */
  async editTarget(message) {
    const page = this.page;
    const client = this.clientHolder.client;
    const { packageUri } = this.current;
    let result;
    if (message.command === 'addTarget') {
      const chosen = await pickTarget(client, packageUri,
        `${page.label}: select what else?`);
      if (!chosen) {
        return false;
      }
      result = await client.sendRequest('semforge/addTarget', { uri: packageUri,
        shape: page.iri, targetKind: chosen.kind, target: chosen.target });
    } else {
      const target = (page.targets || [])[message.row];
      if (!target) {
        return false;
      }
      const last = page.targets.length === 1;
      const answer = await vscode.window.showWarningMessage(
        `Take "${target.text}" off ${page.label}?`,
        { modal: true, detail: last
          ? 'It is the only target: the shape will then run only where another shape ' +
            'reaches it through sh:node.'
          : 'The shape keeps its other targets and its constraints.' },
        'Remove');
      if (answer !== 'Remove') {
        return false;
      }
      result = await client.sendRequest('semforge/removeTarget', { uri: packageUri,
        shape: page.iri, targetKind: target.kind, value: target.value });
    }
    if (!result.ok) {
      vscode.window.showErrorMessage(`SemForge: ${result.error}`);
      return false;
    }
    if (result.note) {
      vscode.window.showWarningMessage(`SemForge: ${result.note}`);
    }
    return true;
  }

  /** Write a bad case asserting this shape fires, then open it to edit. */
  async newCase() {
    const page = this.page;
    const name = await vscode.window.showInputBox({
      title: `New case: make ${page.label} fire`,
      prompt: 'A name for the case file (letters, digits, dashes)',
      value: 'fires',
      validateInput: (text) => (/[A-Za-z0-9]/.test(text) ? undefined : 'a name is required')
    });
    if (!name) {
      return;
    }
    const { packageUri } = this.current;
    const made = await this.clientHolder.client.sendRequest('semforge/newCase',
      { uri: packageUri, shape: page.iri, name });
    if (!made.ok) {
      vscode.window.showErrorMessage(`SemForge: ${made.error}`);
      return;
    }
    await this.render();
    vscode.commands.executeCommand('semforge.refreshModel');
    await vscode.commands.executeCommand('semforge.openCasePage',
      { raw: { kind: 'example', file: made.file }, packageUri });
    const open = await vscode.window.showInformationMessage(
      `SemForge: ${made.case} started from ${made.source}. It fails until its ` +
        `data makes ${page.label} fire on ${made.resource}.`, 'Open .jsonld');
    if (open) {
      await showLocation(`${made.file}:1`, true);
    }
  }

  refresh() {
    if (this.panel && this.panel.visible) {
      this.render();
    }
  }
}

async function pickShape(client, packageUri) {
  const answer = await client.sendRequest('semforge/shapes', { uri: packageUri });
  const picked = await vscode.window.showQuickPick(
    (answer.roots || []).map((r) => ({ label: r.label, description: r.detail, shape: r.shape })),
    { title: 'Open the page of a shape', matchOnDescription: true });
  return picked ? picked.shape : undefined;
}

function register(context, clientHolder, session) {
  const pages = new ShapePages(clientHolder);
  context.subscriptions.push(
    vscode.commands.registerCommand('semforge.openShapePage', async (node, options) => {
      const client = clientHolder.client;
      const packageUri = (node && node.packageUri) || session.uri;
      if (!client || !packageUri) {
        vscode.window.showWarningMessage(
          'SemForge: no package is open, or the language server is not running.');
        return;
      }
      const shape = node && node.raw ? node.raw.shape : await pickShape(client, packageUri);
      if (shape) {
        await pages.show(packageUri, shape, !!(options && options.preserveFocus));
      }
    }),
    vscode.workspace.onDidSaveTextDocument(() => pages.refresh())
  );
  return pages;
}

module.exports = { register, renderShapePage, ShapePages };
