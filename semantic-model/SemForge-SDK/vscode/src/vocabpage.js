/*
 * The vocabulary page: one value list -- MachineState, Wasteclass -- and its
 * care.
 *
 * A vocabulary value is used in the data, in SPARQL queries, in the shapes and
 * in the knowledge itself, so the page lists every value with where it is
 * used, and the constraints that draw their values from the class. Managing
 * it happens here, with visible buttons: + Value, Label…, Delete… (which
 * shows the uses first and refuses quietly to break them).
 *
 * `renderVocabularyPage` is a pure function from the payload
 * `semforge/vocabularyPage` returns; everything shown is escaped, and script
 * and style run only with the per-render nonce.
 */

const crypto = require('crypto');
const vscode = require('vscode');

const { showLocation } = require('./reveal');
const { escape } = require('./typepage');

const REFRESH_VIEWS = ['semforge.refreshKnowledge', 'semforge.refreshTree',
  'semforge.refreshShapes'];

function chip(text, tone, title) {
  return `<span class="chip ${tone || ''}"${title ? ` title="${escape(title)}"` : ''}>` +
    `${escape(text)}</span>`;
}

function openable(text, at, title) {
  return at
    ? `<a href="#" data-open="${escape(at)}"${title ? ` title="${escape(title)}"` : ''}>${escape(text)}</a>`
    : escape(text);
}

function usedChips(uses) {
  if (!uses.total) {
    return chip('unused', 'warn', 'No data, shape, query or knowledge statement names it.');
  }
  const where = uses.places.map((p) =>
    `${p.kind}: ${p.file}:${p.line}${p.owner ? ` (${p.owner})` : ''}`).join('\n');
  return [['data', 'in data'], ['queries', 'in queries'], ['shapes', 'in shapes'],
    ['knowledge', 'in knowledge']]
    .filter(([key]) => uses[key])
    .map(([key, words]) => chip(`${uses[key]} ${words}`, key === 'data' ? 'ok' : '', where))
    .join(' ');
}

function valueRows(values, focus) {
  return values.map((row, index) => {
    const focused = focus && row.iri === focus;
    const properties = row.properties.map((p) =>
      `<div><span class="dim">${escape(p.property)}</span> ` +
      (p.link ? `<a href="#" data-vocab="${escape(p.link)}">${escape(p.value)}</a>`
        : escape(p.value)) + '</div>').join('');
    return `<tr${focused ? ' class="focus" id="focus"' : ''}>` +
      `<td>${openable(row.name, row.definedAt, row.iri)}</td>` +
      `<td><a href="#" class="act" data-action="label" data-row="${index}" ` +
      `title="Change the label">${row.label ? escape(row.label) : '<span class="dim">add…</span>'}</a></td>` +
      `<td>${properties}</td>` +
      `<td>${usedChips(row.uses)}</td>` +
      `<td class="acts"><button data-action="delete" data-row="${index}" ` +
      `title="Delete this value; its uses are shown first">Delete…</button></td></tr>`;
  }).join('');
}

function renderVocabularyPage(page, options) {
  const nonce = (options && options.nonce) || '';
  const focus = options && options.focus;
  const csp = `default-src 'none'; style-src 'nonce-${nonce}'; script-src 'nonce-${nonce}';`;
  const summary = page.summary || {};
  const values = page.values || [];
  const drawn = page.constrainedBy || [];
  const relations = page.relations || [];
  const subclasses = page.subclasses || [];
  const parents = page.parents || [];
  const chips = [
    chip(`${summary.values} value(s)`),
    summary.unused ? chip(`${summary.unused} unused`, 'warn',
      'Named nowhere: no data, shape, query or knowledge statement uses them.') : '',
    summary.constraints
      ? chip(`${summary.constraints} constraint(s) draw from it`, 'ok')
      : chip('no constraint draws from it', 'warn',
        'No sh:class or sh:in names this class or its values, so nothing checks ' +
        'that an attribute holds one of them.')
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
  h1 { font-size: 1.6em; font-weight: 600; margin: 4px 0 2px; }
  h2 { font-size: 0.78em; font-weight: 600; letter-spacing: .08em; text-transform: uppercase;
       color: var(--vscode-descriptionForeground); margin: 26px 0 8px; }
  .mono { font-family: var(--vscode-editor-font-family); font-size: 0.92em; }
  .chips { display: flex; flex-wrap: wrap; gap: 6px; }
  .chips.top { margin-top: 10px; }
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
       vertical-align: top; }
  tr:hover td { background: var(--vscode-list-hoverBackground); }
  tr.focus td { background: var(--vscode-editor-selectionHighlightBackground, rgba(128,128,128,.2)); }
  tr.focus td:first-child { box-shadow: inset 3px 0 0 var(--vscode-focusBorder, #0078d4); }
  td.acts { text-align: right; white-space: nowrap; }
  td.acts button { padding: 0 8px; }
  a.act { color: inherit; border-bottom: 1px dashed var(--vscode-descriptionForeground); }
  ul { margin: 0; padding-left: 1.2em; display: grid; gap: 4px; }
</style></head><body>
<div class="crumbs">Vocabulary${parents.map((p) => ' › ' + (p.page
    ? `<a href="#" data-vocab="${escape(p.iri)}">${escape(p.label)}</a>` : escape(p.label))).join('')}</div>
<h1>${escape(page.label)}</h1>
<div class="dim mono">${escape(page.term)}</div>
${page.comment ? `<p>${escape(page.comment)}</p>` : ''}
<div class="chips top">${chips}</div>
<div class="bar"><button class="primary" data-action="addValue">+ Value</button>
${page.definedAt ? `<button data-open="${escape(page.definedAt)}">Open in .ttl</button>` : ''}
<button data-refresh="1">Refresh</button></div>

<h2>Values</h2>
${values.length ? `<div class="table"><table>
<thead><tr><th>Value</th><th>Label</th><th>Properties</th><th>Used</th><th></th></tr></thead>
<tbody>${valueRows(values, focus)}</tbody></table></div>`
    : '<p class="empty">No values yet. + Value adds the first.</p>'}

<h2>Drawn from by</h2>
${drawn.length ? `<ul>${drawn.map((d) => `<li><a href="#" class="mono" data-shape="${escape(d.shape)}">` +
    `${escape(d.shapeName.split(':').pop())}</a>${d.attribute ? ` · ${escape(d.attribute)}` : ''}` +
    ` <span class="dim">· ${escape(d.how)}</span></li>`).join('')}</ul>`
    : '<p class="empty">No constraint draws its values from this class.</p>'}

${relations.length ? `<h2>Relations</h2><ul>${relations.map((r) =>
    `<li>${openable(r.name, r.definedAt)} <span class="dim">· ${escape(r.domain || '?')} → ` +
    `${escape(r.range || '?')}</span></li>`).join('')}</ul>` : ''}

${subclasses.length ? `<h2>Subclasses</h2><div class="chips">${subclasses.map((c) => c.page
    ? `<a href="#" data-vocab="${escape(c.iri)}">${chip(c.label)}</a>` : chip(c.label)).join('')}</div>` : ''}

<script nonce="${nonce}">
  const vscode = acquireVsCodeApi();
  const focused = document.getElementById('focus');
  if (focused) { focused.scrollIntoView({ block: 'center' }); }
  document.addEventListener('click', (event) => {
    const target = event.target.closest('[data-open],[data-vocab],[data-shape],[data-action],[data-refresh]');
    if (!target) { return; }
    event.preventDefault();
    if (target.dataset.action) {
      vscode.postMessage({ command: target.dataset.action,
                           row: target.dataset.row === undefined ? -1 : Number(target.dataset.row) });
    }
    else if (target.dataset.open) { vscode.postMessage({ command: 'open', at: target.dataset.open }); }
    else if (target.dataset.vocab) { vscode.postMessage({ command: 'vocab', cls: target.dataset.vocab }); }
    else if (target.dataset.shape) { vscode.postMessage({ command: 'shape', name: target.dataset.shape }); }
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

/** One reused panel, like the type and shape pages. */
class VocabularyPages {
  constructor(clientHolder) {
    this.clientHolder = clientHolder;
    this.panel = undefined;
    this.current = undefined;
  }

  async show(packageUri, cls, focus, preserveFocus) {
    if (!this.clientHolder.client || !packageUri || !cls) {
      vscode.window.showWarningMessage(
        'SemForge: no package is open, or the language server is not running.');
      return;
    }
    const same = this.panel && this.current && this.current.packageUri === packageUri &&
      this.current.cls === cls && this.current.focus === focus;
    this.current = { packageUri, cls, focus };
    if (!this.panel) {
      this.panel = vscode.window.createWebviewPanel(
        'semforgeVocabularyPage', 'Vocabulary',
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
      page = await this.clientHolder.client.sendRequest('semforge/vocabularyPage',
        { uri: this.current.packageUri, cls: this.current.cls });
    } catch (error) {
      page = { ok: false, error: error.message || String(error) };
    }
    if (!this.panel) {
      return;
    }
    if (!page.ok) {
      this.panel.title = 'Vocabulary';
      this.panel.webview.html = renderMessage(`SemForge: ${page.error}`);
      return;
    }
    this.page = page;
    this.panel.title = `${page.label} · vocabulary`;
    this.panel.webview.html = renderVocabularyPage(page,
      { nonce: crypto.randomBytes(16).toString('base64'), focus: this.current.focus });
  }

  async receive(message) {
    if (!message || !this.current) {
      return;
    }
    const { packageUri } = this.current;
    const row = this.page && this.page.values ? this.page.values[message.row] : undefined;
    if (message.command === 'open' && message.at) {
      await showLocation(message.at, true);
    } else if (message.command === 'vocab' && message.cls) {
      await this.show(packageUri, message.cls);
    } else if (message.command === 'shape' && message.name) {
      await vscode.commands.executeCommand('semforge.openShapePage',
        { raw: { shape: message.name }, packageUri });
    } else if (message.command === 'addValue') {
      await this.changed(await this.addValue());
    } else if (message.command === 'label' && row) {
      await this.changed(await this.editLabel(row));
    } else if (message.command === 'delete' && row) {
      await this.changed(await this.deleteValue(row));
    } else if (message.command === 'refresh') {
      await this.render();
    }
  }

  async changed(result) {
    if (!result) {
      return;
    }
    if (!result.ok) {
      vscode.window.showErrorMessage(`SemForge: ${result.error}`);
      return;
    }
    if (result.iri) {
      this.current.focus = result.iri;
    }
    await this.render();
    for (const command of REFRESH_VIEWS) {
      vscode.commands.executeCommand(command);
    }
  }

  async addValue() {
    const page = this.page;
    const name = await vscode.window.showInputBox({
      title: `New value of ${page.label}`,
      prompt: `The value's name, in ${page.namespace}`,
      validateInput: (text) => /^[A-Za-z_][A-Za-z0-9_.-]*$/.test(text.trim())
        ? undefined : 'letters, digits, "_", "-" and ".", starting with a letter'
    });
    if (!name) {
      return undefined;
    }
    const label = await vscode.window.showInputBox({
      title: `${name.trim()}: label (optional)`,
      prompt: 'What a person reads, e.g. "ON". Leave empty for none.'
    });
    if (label === undefined) {
      return undefined;
    }
    return this.clientHolder.client.sendRequest('semforge/addVocabularyValue',
      { uri: this.current.packageUri, cls: page.iri, name: name.trim(), label: label.trim() });
  }

  async editLabel(row) {
    const label = await vscode.window.showInputBox({
      title: `${row.name}: label`, value: row.label,
      prompt: 'Empty removes the label.'
    });
    if (label === undefined || label === row.label) {
      return undefined;
    }
    return this.clientHolder.client.sendRequest('semforge/setValueLabel',
      { uri: this.current.packageUri, value: row.iri, label: label.trim() });
  }

  async deleteValue(row) {
    const uses = row.uses;
    let force = false;
    if (uses.total) {
      const where = uses.places.slice(0, 8).map((p) =>
        `${p.kind}: ${p.file}:${p.line}${p.owner ? ` (${p.owner})` : ''}`).join('\n');
      const answer = await vscode.window.showWarningMessage(
        `${row.name} is used in ${uses.total} place(s). Deleting the declaration ` +
          'leaves each of them naming an undeclared value.',
        { modal: true, detail: where + (uses.places.length > 8 ? '\n…' : '') },
        'Delete anyway');
      if (answer !== 'Delete anyway') {
        return undefined;
      }
      force = true;
    } else {
      const answer = await vscode.window.showWarningMessage(
        `Delete ${row.name}? Nothing uses it.`, { modal: true }, 'Delete');
      if (answer !== 'Delete') {
        return undefined;
      }
    }
    return this.clientHolder.client.sendRequest('semforge/removeVocabularyValue',
      { uri: this.current.packageUri, value: row.iri, force });
  }

  refresh() {
    if (this.panel && this.panel.visible) {
      this.render();
    }
  }
}

async function pickClass(client, packageUri, title, extra) {
  const answer = await client.sendRequest('semforge/vocabularyClasses', { uri: packageUri });
  const items = (extra || []).concat((answer.classes || []).map((c) =>
    ({ label: c.label, description: c.term, iri: c.iri })));
  const picked = await vscode.window.showQuickPick(items, { title, matchOnDescription: true });
  return picked;
}

function register(context, clientHolder, session) {
  const pages = new VocabularyPages(clientHolder);
  context.subscriptions.push(
    vscode.commands.registerCommand('semforge.openVocabularyPage', async (node, options) => {
      const client = clientHolder.client;
      const packageUri = (node && node.packageUri) || session.uri;
      if (!client || !packageUri) {
        vscode.window.showWarningMessage(
          'SemForge: no package is open, or the language server is not running.');
        return;
      }
      let cls = options && options.cls;
      if (!cls && node && node.raw) {
        cls = node.raw.kind === 'class' ? node.raw.iri : node.raw.cls;
      }
      if (!cls) {
        const picked = await pickClass(client, packageUri, 'Open a vocabulary class');
        cls = picked && picked.iri;
      }
      if (cls) {
        await pages.show(packageUri, cls, options && options.focus,
          !!(options && options.preserveFocus));
      }
    }),

    vscode.commands.registerCommand('semforge.newVocabularyClass', async (node) => {
      const client = clientHolder.client;
      const packageUri = (node && node.packageUri) || session.uri;
      if (!client || !packageUri) {
        vscode.window.showWarningMessage(
          'SemForge: no package is open, or the language server is not running.');
        return;
      }
      const parent = await pickClass(client, packageUri,
        'New vocabulary class: under which class?',
        [{ label: '(none)', description: 'a class of its own', iri: '' }]);
      if (!parent) {
        return;
      }
      const name = await vscode.window.showInputBox({
        title: 'New vocabulary class',
        prompt: parent.iri ? `Its name; it goes under ${parent.label}, in the same namespace`
          : 'Its name; it goes in the namespace the other vocabularies use',
        validateInput: (text) => /^[A-Za-z_][A-Za-z0-9_.-]*$/.test(text.trim())
          ? undefined : 'letters, digits, "_", "-" and ".", starting with a letter'
      });
      if (!name) {
        return;
      }
      const made = await client.sendRequest('semforge/addVocabularyClass',
        { uri: packageUri, name: name.trim(), parent: parent.iri || null });
      if (!made.ok) {
        vscode.window.showErrorMessage(`SemForge: ${made.error}`);
        return;
      }
      for (const command of REFRESH_VIEWS) {
        vscode.commands.executeCommand(command);
      }
      await pages.show(packageUri, made.iri);
    }),
    vscode.workspace.onDidSaveTextDocument(() => pages.refresh())
  );
  return pages;
}

module.exports = { register, renderVocabularyPage, VocabularyPages };
