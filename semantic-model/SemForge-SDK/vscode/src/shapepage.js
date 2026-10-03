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
 * Read-only. `renderShapePage` is a pure function from the payload
 * `semforge/shapePage` returns; everything shown is escaped, and script and
 * style run only with the per-render nonce.
 */

const crypto = require('crypto');
const vscode = require('vscode');

const { showLocation } = require('./reveal');
const { escape } = require('./typepage');

const TESTED_CLASS = {
  'both ways': 'ok', 'fires only': 'warn', 'never fired': 'warn', untested: ''
};

function chip(text, tone, title) {
  return `<span class="chip ${tone || ''}"${title ? ` title="${escape(title)}"` : ''}>` +
    `${escape(text)}</span>`;
}

function openable(text, at) {
  return at ? `<a href="#" data-open="${escape(at)}">${escape(text)}</a>` : escape(text);
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
  return `<ul class="targets">${targets.map((t) => `<li><span class="mono">${escape(
    { class: 'sh:targetClass', node: 'sh:targetNode', subjectsOf: 'sh:targetSubjectsOf',
      objectsOf: 'sh:targetObjectsOf', sparql: 'sh:target', implicit: 'implicit' }[t.kind] ||
    t.kind)}</span> ${escape(t.text)}` +
    (t.kind === 'sparql' && t.value
      ? `<pre class="query">${escape(t.value.trim())}</pre>` : '') + '</li>').join('')}</ul>`;
}

function attributeRows(attributes) {
  return attributes.map((row) => {
    const tested = row.tested && row.tested !== 'untested'
      ? chip(row.tested, TESTED_CLASS[row.tested]) : '';
    const model = row.violations.length
      ? chip(`${row.violations.length} in the model`, 'bad', row.violations.join('\n')) : '';
    return `<tr${row.violations.length ? ' class="flag"' : ''}>` +
      `<td${row.depth ? ` class="depth${Math.min(row.depth, 4)}"` : ''}>` +
      `${openable(row.label, row.definedAt)}</td>` +
      `<td><span class="kind">${escape(row.kind)}</span></td>` +
      `<td>${escape(row.presence)}</td><td>${escape(row.value)}` +
      `${row.verbatim.length ? `<div class="verbatim">${row.verbatim.map(escape).join('<br>')}</div>` : ''}</td>` +
      `<td>${tested}</td><td>${model}</td></tr>`;
  }).join('');
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
  const queries = checks.filter((c) => c.query).map((c) =>
    `<pre class="query">${escape(c.query)}</pre>`).join('');
  return `<h2>What it checks</h2><div class="rules">${said}</div>` +
    (evidence ? `<h2>Evidence</h2><div class="rules">${evidence}</div>` : '') +
    (queries ? `<h2>The query · read-only, edit it in the .ttl</h2>${queries}` : '');
}

function renderShapePage(page, options) {
  const nonce = (options && options.nonce) || '';
  const csp = `default-src 'none'; style-src 'nonce-${nonce}'; script-src 'nonce-${nonce}';`;
  const summary = page.summary || {};
  const attributes = page.attributes || [];
  const checks = page.checks || [];
  const cases = page.exercisedBy || [];
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
<button data-refresh="1">Refresh</button></div>

<h2>Target</h2>
${targetSection(page)}

<h2>Reaches</h2>
${types.length ? `<div class="chips">${types.map((t) => t.page
    ? `<a href="#" data-type="${escape(t.iri)}">${chip(t.label)}</a>`
    : chip(t.label, '', t.iri)).join('')}</div>` : ''}
${reach.nodes.length ? `<ul>${reach.nodes.map((n) => `<li><span class="mono">${escape(n.id)}</span> ` +
    (n.violations.length ? n.violations.map((v) => chip(v, 'bad')).join(' ') : chip('valid', 'ok')) +
    '</li>').join('')}${reach.more ? `<li class="dim">… and ${reach.more} more</li>` : ''}</ul>`
    : '<p class="empty">Nothing in the model is a focus node of this shape.</p>'}

${attributes.length ? `<h2>Attributes</h2><div class="table"><table>
<thead><tr><th>Attribute</th><th>Kind</th><th>Presence</th><th>Value</th><th>Tested</th><th>Model</th></tr></thead>
<tbody>${attributeRows(attributes)}</tbody></table></div>`
    : checks.length ? '' : '<h2>Attributes</h2><p class="empty">No property constraints.</p>'}

${checks.length ? checkSections(page, checks, cases) : `<h2>Test cases that reach it</h2>
${caseChips(cases) || '<p class="empty">No test case reaches it. Nothing proves it can fire.</p>'}`}

<script nonce="${nonce}">
  const vscode = acquireVsCodeApi();
  document.addEventListener('click', (event) => {
    const target = event.target.closest('[data-open],[data-type],[data-shape],[data-case],[data-newcase],[data-refresh]');
    if (!target) { return; }
    event.preventDefault();
    if (target.dataset.open) { vscode.postMessage({ command: 'open', at: target.dataset.open }); }
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
    if (message.command === 'open' && message.at) {
      await showLocation(message.at, true);
    } else if (message.command === 'type' && message.name) {
      await vscode.commands.executeCommand('semforge.openTypePage',
        { raw: { targetClass: message.name }, packageUri });
    } else if (message.command === 'shape' && message.name) {
      await this.show(packageUri, message.name);
    } else if (message.command === 'case' && message.file) {
      await vscode.commands.executeCommand('semforge.openCasePage',
        { raw: { kind: 'example', file: message.file }, packageUri });
    } else if (message.command === 'newCase') {
      await this.newCase();
    } else if (message.command === 'refresh') {
      await this.render();
    }
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
