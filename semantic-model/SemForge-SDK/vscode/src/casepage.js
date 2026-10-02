/*
 * The test case page: what one case claims, whether the claims hold, and the
 * data it uses -- entity cards instead of a nine-level tree, every violation
 * on the attribute it is about.
 *
 * Computed by the SDK (`semforge/casePage`, which runs the case exactly as
 * `semforge test` does) and only rendered here. `renderCasePage` is pure, so
 * it is tested without a window; everything shown is escaped, and script and
 * style run only with the per-render nonce.
 */

const crypto = require('crypto');
const vscode = require('vscode');

const { showLocation } = require('./reveal');
const { escape } = require('./typepage');

function chip(text, tone, title) {
  return `<span class="chip ${tone || ''}"${title ? ` title="${escape(title)}"` : ''}>` +
    `${escape(text)}</span>`;
}

function open(text, file, line, title) {
  return file
    ? `<a href="#" data-open="${escape(`${file}:${line || 1}`)}"` +
      `${title ? ` title="${escape(title)}"` : ''}>${escape(text)}</a>`
    : escape(text);
}

function problem(violation) {
  return `<div class="problem" title="${escape(violation.detail || '')}">` +
    `${escape(violation.text)} <span class="dim">· ${escape(violation.shape)}</span></div>`;
}

function attributeRows(rows, file, depth) {
  return rows.map((row) => `<div class="attr" style="padding-left:${depth * 16}px">` +
    `<span class="name">${depth ? '<span class="dim">└ </span>' : ''}` +
    `${open(row.name, file, row.line, row.term)}</span>` +
    `<span class="value">${escape(row.value)}` +
    `${row.dataset && row.dataset !== '@none' ? ` <span class="dim">· ${escape(row.dataset)}</span>` : ''}` +
    `</span>` +
    `${row.violations.map(problem).join('')}</div>` +
    attributeRows(row.children || [], file, depth + 1)).join('');
}

function anyViolation(rows) {
  return (rows || []).some((row) => row.violations.length || anyViolation(row.children));
}

function card(entity) {
  const bad = entity.violations.length || anyViolation(entity.attributes);
  return `<div class="card${bad ? ' bad' : ''}">` +
    `<div class="title">${open(entity.id || '(no id)', entity.file, entity.line)}` +
    `${entity.type ? ` <a href="#" class="dim" data-type="${escape(entity.type)}"` +
      ` title="Open the ${escape(entity.type)} page">· ${escape(entity.type)}</a>` : ''}</div>` +
    `${entity.error ? `<div class="problem">${escape(entity.error)}</div>` : ''}` +
    `${entity.violations.map(problem).join('')}` +
    `${attributeRows(entity.attributes, entity.file, 0) ||
      '<div class="dim">no attributes</div>'}</div>`;
}

const ASSERT_TIP = 'Assert it if the case MEANS this: it then fails the day this stops ' +
  'firing. If it fired only because the data is incomplete, fix the data instead, ' +
  'so the case fails for exactly one reason.';

function claimRow(claim, unasserted, index, at) {
  const explained = claim.explained || {};
  const where = claim.resource ? ` on <span class="mono">${escape(claim.resource)}</span>` : '';
  const status = unasserted ? chip('also fired', 'warn',
    'Not asserted. Either a second problem this case found, or a sign the data ' +
    'is not what the case means it to be.')
    : claim.holds ? chip('holds', 'ok') : chip('does not hold', 'bad');
  const parts = claim.constraint.split('/');
  const actions = unasserted
    ? `<span class="acts"><button data-assert="${index}" title="${escape(ASSERT_TIP)}">` +
      'Assert it</button>' +
      (at ? `<button data-open="${escape(at)}">Open in .jsonld</button>` : '') + '</span>'
    : '';
  return `<div class="claim${unasserted ? ' extra' : ''}">${status}<span class="what">` +
    `${escape(explained.text || parts.slice(1).join(' · ').replace('ConstraintComponent', ''))}` +
    `${where} <span class="dim">· ${escape(parts[0].split(':').pop())}</span></span>` +
    `${actions}</div>`;
}

function renderCasePage(page, options) {
  const nonce = (options && options.nonce) || '';
  const csp = `default-src 'none'; style-src 'nonce-${nonce}'; script-src 'nonce-${nonce}';`;
  const claims = page.claims || [];
  const unasserted = page.unasserted || [];
  const files = page.files || [];
  const crumbs = (page.case || '').split('/').slice(0, -1).map(escape).join(' › ');
  // Where each entity is written, so "Open in .jsonld" lands on it.
  const located = {};
  files.forEach((file) => file.cards.forEach((c) => {
    if (c.id && !located[c.id]) { located[c.id] = `${c.file}:${c.line}`; }
  }));

  return `<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="${csp}">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${escape(page.name)}</title>
<style nonce="${nonce}">
  body { font-family: var(--vscode-font-family); font-size: var(--vscode-font-size);
         color: var(--vscode-foreground); background: var(--vscode-editor-background);
         padding: 16px 22px 40px; line-height: 1.45; }
  a { color: var(--vscode-textLink-foreground); text-decoration: none; }
  a:hover, a:focus-visible { text-decoration: underline; }
  .dim, .crumbs { color: var(--vscode-descriptionForeground); }
  .crumbs { font-size: 0.92em; }
  .mono { font-family: var(--vscode-editor-font-family); font-size: 0.92em; }
  h1 { font-size: 1.5em; font-weight: 600; margin: 4px 0 4px; }
  .lede { margin: 0 0 10px; max-width: 80ch; }
  h2 { font-size: 0.78em; font-weight: 600; letter-spacing: .08em; text-transform: uppercase;
       color: var(--vscode-descriptionForeground); margin: 24px 0 8px; }
  .chips, .bar { display: flex; flex-wrap: wrap; gap: 6px; }
  .bar { margin-top: 10px; gap: 8px; }
  .chip { font-size: 0.86em; padding: 1px 8px; border-radius: 999px; white-space: nowrap;
          border: 1px solid var(--vscode-panel-border, rgba(128,128,128,.35)); }
  .chip.ok { color: var(--vscode-testing-iconPassed, #388a34); border-color: currentColor; }
  .chip.bad { color: var(--vscode-errorForeground, #f14c4c); border-color: currentColor; }
  .chip.warn { color: var(--vscode-editorWarning-foreground, #cca700); border-color: currentColor; }
  button { font: inherit; color: var(--vscode-button-secondaryForeground, inherit);
           background: var(--vscode-button-secondaryBackground, transparent);
           border: 1px solid var(--vscode-panel-border, rgba(128,128,128,.35));
           padding: 3px 10px; border-radius: 2px; cursor: pointer; }
  .claims { display: grid; gap: 6px; }
  .claim.extra { grid-template-columns: auto 1fr auto; }
  .acts { display: flex; gap: 6px; }
  .claim { display: grid; grid-template-columns: auto 1fr; gap: 10px; align-items: baseline;
           padding: 6px 10px; border: 1px solid var(--vscode-panel-border, rgba(128,128,128,.35)); }
  .failures { margin: 8px 0 0; padding-left: 1.2em; color: var(--vscode-errorForeground, #f14c4c); }
  .file { margin-top: 18px; }
  .file .head { display: flex; flex-wrap: wrap; gap: 8px; align-items: baseline; margin-bottom: 8px; }
  .cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 10px; }
  .card { border: 1px solid var(--vscode-panel-border, rgba(128,128,128,.35)); border-radius: 4px;
          padding: 10px 12px; display: grid; gap: 4px; align-content: start; }
  .card.bad { border-color: var(--vscode-errorForeground, #f14c4c); }
  .card .title { font-weight: 600; margin-bottom: 4px; }
  .attr { display: grid; grid-template-columns: minmax(7em, auto) 1fr; gap: 2px 12px; }
  .attr .value { font-family: var(--vscode-editor-font-family); font-size: 0.92em;
                 overflow-wrap: anywhere; }
  .problem { grid-column: 1 / -1; color: var(--vscode-errorForeground, #f14c4c);
             border-left: 2px solid currentColor; padding-left: 8px; font-size: 0.92em; }
</style></head><body>
<div class="crumbs">${crumbs}</div>
<h1>${escape(page.name)}</h1>
${page.description ? `<p class="lede">${escape(page.description)}</p>` : ''}
<div class="chips">
  ${chip(`expects ${page.expect}`)}
  ${page.passed ? chip('passes', 'ok') : chip('fails', 'bad')}
  ${page.residuePinned ? chip('residue pinned', '', 'Everything else that fires is pinned by digest') : ''}
  ${chip(`${(page.summary || {}).entities || 0} entities`)}
</div>
${(page.failures || []).length
    ? `<ul class="failures">${page.failures.map((f) => `<li>${escape(f)}</li>`).join('')}</ul>` : ''}
<div class="bar">
  <button data-open="${escape(page.file)}:1">Open the case file</button>
  ${page.expectations ? `<button data-open="${escape(page.expectations)}:1">Open its expectations</button>` : ''}
  <button data-refresh="1">Refresh</button>
</div>

<h2>Claims</h2>
${claims.length || unasserted.length
    ? `<div class="claims">${claims.map((c) => claimRow(c, false)).join('')}` +
      `${unasserted.map((c, i) => claimRow(c, true, i, located[c.resource])).join('')}</div>`
    : `<p class="dim">This case asserts nothing${page.expect === 'valid'
      ? ' beyond being valid.' : '. A bad case that asserts nothing is an unfinished test.'}</p>`}

<h2>Data</h2>
${files.map((file) => `<div class="file"><div class="head">
  ${chip(file.role === 'case' ? 'this case' : 'included')}
  ${open(file.relative, file.path, 1)}
  ${file.sharedBy.length ? `<span class="dim" title="${escape(file.sharedBy.join('\n'))}">· shared with ` +
    `${file.sharedBy.length} other case(s) — an edit here changes them too</span>` : ''}
</div><div class="cards">${file.cards.map(card).join('')}</div></div>`).join('')}

<script nonce="${nonce}">
  const vscode = acquireVsCodeApi();
  document.addEventListener('click', (event) => {
    const target = event.target.closest('[data-open],[data-type],[data-refresh],[data-assert]');
    if (!target) { return; }
    event.preventDefault();
    if (target.dataset.assert !== undefined) {
      vscode.postMessage({ command: 'assert', index: Number(target.dataset.assert) });
    }
    else if (target.dataset.open) { vscode.postMessage({ command: 'open', at: target.dataset.open }); }
    else if (target.dataset.type) { vscode.postMessage({ command: 'type', name: target.dataset.type }); }
    else { vscode.postMessage({ command: 'refresh' }); }
  });
</script>
</body></html>`;
}

class CasePages {
  constructor(clientHolder) {
    this.clientHolder = clientHolder;
    this.panel = undefined;
    this.current = undefined;
  }

  async show(packageUri, caseFile) {
    if (!this.clientHolder.client || !packageUri || !caseFile) {
      vscode.window.showWarningMessage(
        'SemForge: no package is open, or the language server is not running.');
      return;
    }
    this.current = { packageUri, caseFile };
    if (!this.panel) {
      this.panel = vscode.window.createWebviewPanel(
        'semforgeCasePage', 'Test case', vscode.ViewColumn.Active,
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
    let page;
    try {
      page = await this.clientHolder.client.sendRequest('semforge/casePage',
        { uri: this.current.packageUri, case: this.current.caseFile });
    } catch (error) {
      page = { ok: false, error: error.message || String(error) };
    }
    if (!this.panel) {
      return;
    }
    if (!page.ok) {
      this.panel.title = 'Test case';
      this.panel.webview.html = `<!DOCTYPE html><html><head><meta charset="utf-8">` +
        `<meta http-equiv="Content-Security-Policy" content="default-src 'none';"></head>` +
        `<body style="font-family:var(--vscode-font-family);color:var(--vscode-foreground);` +
        `padding:20px"><p>SemForge: ${escape(page.error)}</p></body></html>`;
      return;
    }
    this.page = page;
    this.panel.title = `⚑ ${page.name}`;
    this.panel.webview.html = renderCasePage(page,
      { nonce: crypto.randomBytes(16).toString('base64') });
  }

  async receive(message) {
    if (!message || !this.current) {
      return;
    }
    if (message.command === 'assert') {
      await this.assert(message.index);
    } else if (message.command === 'open' && message.at) {
      await showLocation(message.at, true);
    } else if (message.command === 'type' && message.name) {
      await vscode.commands.executeCommand('semforge.openTypePage',
        { raw: { targetClass: message.name }, packageUri: this.current.packageUri });
    } else if (message.command === 'refresh') {
      await this.render();
    }
  }

  /** "Assert it": the firing becomes a claim, written into the case's
   *  expectations.yaml, and the page re-renders with it under holds. */
  async assert(index) {
    const firing = this.page && (this.page.unasserted || [])[index];
    if (!firing) {
      return;
    }
    const result = await this.clientHolder.client.sendRequest('semforge/addAssert', {
      uri: this.current.packageUri, case: this.page.case,
      constraint: firing.constraint, resource: firing.resource });
    if (!result.ok) {
      vscode.window.showErrorMessage(`SemForge: ${result.error}`);
      return;
    }
    vscode.window.setStatusBarMessage(
      `SemForge: ${this.page.name} now asserts ` +
        `${firing.constraint.split('/').slice(1, 2).join('')} on ${firing.resource}`, 5000);
    if (result.note) {
      vscode.window.showWarningMessage(`SemForge: ${result.note}`);
    }
    await this.render();
    vscode.commands.executeCommand('semforge.refreshModel');
  }

  refresh() {
    if (this.panel && this.panel.visible) {
      this.render();
    }
  }
}

/** Every declared case, from the Model tree's payload, for the palette. */
async function pickCase(client, packageUri) {
  const answer = await client.sendRequest('semforge/model', { uri: packageUri, detail: 'summary' });
  const cases = [];
  const walk = (nodes) => (nodes || []).forEach((node) => {
    if (node.kind === 'example' && node.file) {
      cases.push({ label: node.label, description: node.detail, file: node.file });
    }
    walk(node.children);
  });
  walk(answer.roots);
  if (!cases.length) {
    vscode.window.showInformationMessage(
      'SemForge: this package declares no test cases. Cases live in an ' +
        'expectations.yaml under examples/.');
    return undefined;
  }
  const picked = await vscode.window.showQuickPick(cases,
    { title: 'Open the page of a test case', matchOnDescription: true });
  return picked ? picked.file : undefined;
}

function register(context, clientHolder, session) {
  const pages = new CasePages(clientHolder);
  context.subscriptions.push(
    vscode.commands.registerCommand('semforge.openCasePage', async (node) => {
      const client = clientHolder.client;
      const packageUri = (node && node.packageUri) || session.uri;
      if (!client || !packageUri) {
        vscode.window.showWarningMessage(
          'SemForge: no package is open, or the language server is not running.');
        return;
      }
      if (node && node.raw && !node.raw.file) {
        // The model scratchpad sits in the same tree as the cases but is not
        // one: it has no claims to check.
        vscode.window.showInformationMessage(
          `SemForge: ${node.raw.label} is the model, not a test case. Its ` +
            'violations are in the Problems panel; open a case under Tests.');
        return;
      }
      const caseFile = node && node.raw ? node.raw.file : await pickCase(client, packageUri);
      if (caseFile) {
        await pages.show(packageUri, caseFile);
      }
    }),
    vscode.workspace.onDidSaveTextDocument(() => pages.refresh())
  );
  return pages;
}

module.exports = { register, renderCasePage, CasePages };
