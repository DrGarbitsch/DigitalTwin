/*
 * The entity type page: one webview in the editor area showing everything
 * about one type -- its place in the hierarchy, every attribute it must or may
 * carry (inherited ones and sub-attributes included), the rules that judge it,
 * the cases that exercise it and what is wrong with it in the model.
 *
 * Read-only, and computed by the SDK: `semforge/typePage` returns one JSON
 * payload and this file only renders it. The page decides nothing a tree
 * could disagree with.
 *
 * `renderTypePage` is a pure function from payload to HTML so it can be
 * tested without a window. Everything shown is escaped; script and style run
 * only with the per-render nonce under a strict Content-Security-Policy.
 */

const crypto = require('crypto');
const vscode = require('vscode');

const { showLocation } = require('./reveal');

function escape(value) {
  return String(value === undefined || value === null ? '' : value)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

const TESTED_CLASS = {
  'both ways': 'ok', 'fires only': 'warn', 'never fired': 'warn', untested: ''
};

function chip(text, tone, title) {
  return `<span class="chip ${tone || ''}"${title ? ` title="${escape(title)}"` : ''}>` +
    `${escape(text)}</span>`;
}

function openable(text, at, extra) {
  return at
    ? `<a href="#" data-open="${escape(at)}"${extra || ''}>${escape(text)}</a>`
    : escape(text);
}

function attributeRows(attributes) {
  return attributes.map((row) => {
    const classes = [row.inherited ? 'inh' : '', row.violations.length ? 'flag' : '']
      .filter(Boolean).join(' ');
    const indent = row.depth ? ` style="padding-left:${12 + row.depth * 18}px"` : '';
    const verbatim = row.verbatim.length
      ? `<div class="verbatim">${row.verbatim.map(escape).join('<br>')}</div>` : '';
    const tested = row.tested && row.tested !== 'untested'
      ? chip(row.tested, TESTED_CLASS[row.tested],
        row.tested === 'never fired'
          ? 'No example makes this attribute\'s constraints fire. A constraint ' +
            'that cannot fire looks exactly like one that is satisfied.'
          : '')
      : '';
    const model = row.violations.length
      ? chip(`${row.violations.length} in the model`, 'bad', row.violations.join('\n'))
      : '';
    return `<tr class="${classes}">` +
      `<td${indent}>${row.depth ? '<span class="dim">└ </span>' : ''}` +
      `${openable(row.label, row.definedAt, ` title="${escape(row.term)}"`)}</td>` +
      `<td><span class="kind">${escape(row.kind)}</span></td>` +
      `<td>${escape(row.presence)}</td>` +
      `<td>${escape(row.value)}${verbatim}</td>` +
      `<td><span class="mono">${escape(row.shapeName.split(':').pop())}</span>` +
      `${row.inherited ? ` <span class="dim">· from ${escape(row.inheritedFrom)}</span>` : ''}</td>` +
      `<td>${tested}</td><td>${model}</td></tr>`;
  }).join('');
}

function ruleRows(rules) {
  return rules.map((rule) => `<div class="rule">` +
    `<span class="kind">${escape(rule.kind)}</span>` +
    `<span class="what">${openable(rule.shapeName.split(':').pop(), rule.definedAt)}` +
    `${rule.text ? ` <span class="dim">· ${escape(rule.text)}</span>` : ''}` +
    `${rule.inherited ? ` <span class="dim">· from ${escape(rule.inheritedFrom)}</span>` : ''}</span>` +
    `${rule.tested ? chip(rule.tested, TESTED_CLASS[rule.tested]) : ''}</div>`).join('');
}

function renderTypePage(page, options) {
  const nonce = (options && options.nonce) || '';
  const csp = `default-src 'none'; style-src 'nonce-${nonce}'; script-src 'nonce-${nonce}';`;
  const summary = page.summary || {};
  const crumbs = (page.crumbs || []).map((name) =>
    `<a href="#" data-type="${escape(name)}">${escape(name)}</a> › `).join('');
  const chips = [
    summary.cases
      ? chip(`${summary.cases} case(s) use it · ` +
        (summary.casesFailing ? `${summary.casesFailing} failing` : 'all pass'),
      summary.casesFailing ? 'bad' : 'ok')
      : chip('no test case uses it', 'warn'),
    summary.instances
      ? chip(summary.instancesViolating
        ? `${summary.instancesViolating} of ${summary.instances} in the model violate`
        : `${summary.instances} in the model · all valid`,
      summary.instancesViolating ? 'bad' : 'ok')
      : chip('no instance in the model'),
    summary.neverFired ? chip(`${summary.neverFired} never fired`, 'warn',
      'Constraints or rules that no example makes fire') : ''
  ].join('');
  const attributes = page.attributes || [];
  const rules = page.rules || [];
  const cases = page.exercisedBy || [];
  const instances = page.instances || [];
  const subtypes = page.subtypes || [];

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
  .crumbs, .dim { color: var(--vscode-descriptionForeground); }
  .crumbs { font-size: 0.92em; }
  h1 { font-size: 1.6em; font-weight: 600; margin: 4px 0 8px; }
  h2 { font-size: 0.78em; font-weight: 600; letter-spacing: .08em; text-transform: uppercase;
       color: var(--vscode-descriptionForeground); margin: 26px 0 8px; }
  .chips { display: flex; flex-wrap: wrap; gap: 6px; }
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
  button:hover { background: var(--vscode-button-secondaryHoverBackground, transparent); }
  .table { overflow-x: auto; border: 1px solid var(--vscode-panel-border, rgba(128,128,128,.35)); }
  table { border-collapse: collapse; width: 100%; }
  th { text-align: left; font-size: 0.78em; letter-spacing: .06em; text-transform: uppercase;
       color: var(--vscode-descriptionForeground); font-weight: 600; padding: 7px 12px;
       background: var(--vscode-sideBar-background, transparent); }
  td { padding: 6px 12px; border-top: 1px solid var(--vscode-panel-border, rgba(128,128,128,.25));
       white-space: nowrap; vertical-align: top; }
  tr:hover td { background: var(--vscode-list-hoverBackground); }
  tr.inh td { color: var(--vscode-descriptionForeground); }
  tr.flag td:first-child { box-shadow: inset 3px 0 0 var(--vscode-errorForeground, #f14c4c); }
  .kind { font-size: 0.84em; padding: 0 6px; border-radius: 3px;
          background: var(--vscode-badge-background); color: var(--vscode-badge-foreground); }
  .mono, .verbatim { font-family: var(--vscode-editor-font-family); font-size: 0.92em; }
  .verbatim { color: var(--vscode-descriptionForeground); white-space: normal; margin-top: 2px; }
  .rules { display: grid; gap: 6px; }
  .rule { display: grid; grid-template-columns: auto 1fr auto; gap: 10px; align-items: baseline;
          padding: 6px 10px; border: 1px solid var(--vscode-panel-border, rgba(128,128,128,.35)); }
  .empty { color: var(--vscode-descriptionForeground); font-style: italic; }
  ul { margin: 0; padding-left: 1.1em; }
  li { margin: 2px 0; }
</style></head><body>
<div class="crumbs">${crumbs}<b>${escape(page.label)}</b> · <span class="mono">${escape(page.term)}</span></div>
<h1>${escape(page.label)}</h1>
<div class="chips">${chips}</div>
<div class="bar">
  ${page.shapeAt ? `<button data-open="${escape(page.shapeAt)}">Open the shape in .ttl</button>` : ''}
  <button data-refresh="1">Refresh</button>
</div>

<h2>Attributes · own and inherited</h2>
${attributes.length ? `<div class="table"><table>
<thead><tr><th>Attribute</th><th>Kind</th><th>Presence</th><th>Value</th><th>Declared in</th><th>Tested</th><th>Model</th></tr></thead>
<tbody>${attributeRows(attributes)}</tbody></table></div>`
    : '<p class="empty">No shape constrains an attribute of this type.</p>'}

<h2>Rules</h2>
${rules.length ? `<div class="rules">${ruleRows(rules)}</div>`
    : '<p class="empty">No SPARQL constraint or rule targets this type.</p>'}

<h2>Exercised by</h2>
${cases.length ? `<div class="chips">${cases.map((c) =>
    `<a href="#" data-open="${escape(c.file)}:1" title="${escape(c.description || '')}">` +
    chip(`${c.case.split('/').slice(-3).join(' / ')} · ${c.expect} · ` +
      (c.passed ? 'passes' : 'FAILS'), c.passed ? 'ok' : 'bad') + '</a>').join('')}</div>`
    : '<p class="empty">No test case has an entity of this type. Nothing proves its constraints can fire.</p>'}

<h2>In the model</h2>
${instances.length ? `<ul>${instances.map((i) => `<li><span class="mono">${escape(i.id)}</span>` +
    (i.type !== page.label ? ` <span class="dim">· ${escape(i.type)}</span>` : '') +
    (i.violations.length ? ' ' + i.violations.map((v) =>
      chip(v.split('/').slice(1).join(' · ').replace('ConstraintComponent', ''), 'bad', v)).join(' ')
      : ' ' + chip('valid', 'ok')) + '</li>').join('')}</ul>`
    : '<p class="empty">No entity of this type in the model.</p>'}

${subtypes.length ? `<h2>Subtypes</h2><div class="chips">${subtypes.map((name) =>
    `<a href="#" data-type="${escape(name)}">${chip(name)}</a>`).join('')}</div>` : ''}

<script nonce="${nonce}">
  const vscode = acquireVsCodeApi();
  document.addEventListener('click', (event) => {
    const target = event.target.closest('[data-open],[data-type],[data-refresh]');
    if (!target) { return; }
    event.preventDefault();
    if (target.dataset.open) { vscode.postMessage({ command: 'open', at: target.dataset.open }); }
    else if (target.dataset.type) { vscode.postMessage({ command: 'type', name: target.dataset.type }); }
    else { vscode.postMessage({ command: 'refresh' }); }
  });
</script>
</body></html>`;
}

function renderMessage(title, message) {
  return `<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'none';">
<title>${escape(title)}</title></head>
<body style="font-family:var(--vscode-font-family);color:var(--vscode-foreground);padding:20px">
<p>${escape(message)}</p></body></html>`;
}

/** One reusable panel, like the Settings editor: clicking another type
 *  replaces the page rather than opening another tab. */
class TypePages {
  constructor(clientHolder, session) {
    this.clientHolder = clientHolder;
    this.session = session;
    this.panel = undefined;
    this.current = undefined;          // { packageUri, entityType }
  }

  async show(packageUri, entityType) {
    const client = this.clientHolder.client;
    if (!client || !packageUri || !entityType) {
      vscode.window.showWarningMessage(
        'SemForge: no package is open, or the language server is not running.');
      return;
    }
    this.current = { packageUri, entityType };
    if (!this.panel) {
      this.panel = vscode.window.createWebviewPanel(
        'semforgeTypePage', 'Entity type', vscode.ViewColumn.Active,
        { enableScripts: true, localResourceRoots: [] });
      this.panel.onDidDispose(() => { this.panel = undefined; });
      this.panel.webview.onDidReceiveMessage((message) => this.receive(message));
    } else {
      this.panel.reveal(undefined, false);
    }
    await this.render();
  }

  async render() {
    if (!this.panel || !this.current) {
      return;
    }
    const { packageUri, entityType } = this.current;
    let page;
    try {
      page = await this.clientHolder.client.sendRequest('semforge/typePage',
        { uri: packageUri, entityType });
    } catch (error) {
      page = { ok: false, error: error.message || String(error) };
    }
    if (!this.panel) {
      return;                          // closed while the server answered
    }
    if (!page.ok) {
      this.panel.title = 'Entity type';
      this.panel.webview.html = renderMessage('Entity type', `SemForge: ${page.error}`);
      return;
    }
    this.panel.title = `⬡ ${page.label}`;
    this.panel.webview.html = renderTypePage(page,
      { nonce: crypto.randomBytes(16).toString('base64') });
  }

  async receive(message) {
    if (!message || !this.current) {
      return;
    }
    if (message.command === 'open' && message.at) {
      await showLocation(message.at, true);
    } else if (message.command === 'type' && message.name) {
      await this.show(this.current.packageUri, message.name);
    } else if (message.command === 'refresh') {
      await this.render();
    }
  }

  /** After a save the page may be stale; the cache makes this cheap. */
  refresh() {
    if (this.panel && this.panel.visible) {
      this.render();
    }
  }
}

/** The entity type a tree row stands for, whichever tree it is in. */
function typeOf(node) {
  const raw = node && node.raw;
  if (!raw) {
    return undefined;
  }
  return raw.targetClass || (raw.kind === 'class' && raw.iri) || raw.entityType ||
    raw.iri || undefined;
}

async function pickType(client, packageUri) {
  const answer = await client.sendRequest('semforge/entityTypes', { uri: packageUri });
  const picked = await vscode.window.showQuickPick(
    (answer.types || []).map((t) => ({ label: t.label, description: t.term, iri: t.iri })),
    { title: 'Open the page of an entity type', matchOnDescription: true });
  return picked ? picked.iri : undefined;
}

function register(context, clientHolder, session) {
  const pages = new TypePages(clientHolder, session);
  context.subscriptions.push(
    vscode.commands.registerCommand('semforge.openTypePage', async (node) => {
      const client = clientHolder.client;
      const packageUri = (node && node.packageUri) || session.uri;
      if (!client || !packageUri) {
        vscode.window.showWarningMessage(
          'SemForge: no package is open, or the language server is not running.');
        return;
      }
      const entityType = node && node.raw ? typeOf(node) : await pickType(client, packageUri);
      if (entityType) {
        await pages.show(packageUri, entityType);
      }
    }),
    vscode.workspace.onDidSaveTextDocument(() => pages.refresh())
  );
  return pages;
}

module.exports = { register, renderTypePage, TypePages, typeOf, escape };
