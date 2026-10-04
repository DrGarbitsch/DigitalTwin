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
const { pickValue } = require('./attribute');

const REFRESH_VIEWS = ['semforge.refreshTree', 'semforge.refreshKnowledge',
  'semforge.refreshModel'];

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

function action(name, index, text, title) {
  return `<a href="#" class="act" data-action="${name}" data-row="${index}"` +
    `${title ? ` title="${escape(title)}"` : ''}>${escape(text)}</a>`;
}

/**
 * Which attribute row a tree click meant. The Constraints tree knows the path
 * (its deepest row on the page is the longest prefix: a full-mode constraint
 * row sits below its attribute); the Knowledge tree knows only the attribute.
 */
function focusIndex(attributes, focus) {
  if (!focus) {
    return -1;
  }
  let best = -1;
  let length = 0;
  const wanted = focus.path || [];
  attributes.forEach((row, index) => {
    const path = row.path || [];
    if (path.length > length && path.length <= wanted.length &&
        path.every((step, at) => step === wanted[at])) {
      best = index;
      length = path.length;
    }
  });
  if (best < 0 && focus.attribute) {
    best = attributes.findIndex((row) => row.attribute === focus.attribute);
  }
  return best;
}

function attributeRows(attributes, focused, options) {
  // The shape page shows one shape's rows: a "Declared in" column would say
  // the same name on every row.
  const shapeColumn = !(options && options.shapeColumn === false);
  return attributes.map((row, index) => {
    const classes = [row.inherited ? 'inh' : '', row.violations.length ? 'flag' : '',
      index === focused ? 'focus' : ''].filter(Boolean).join(' ');
    // A class, not a style attribute: the page's CSP admits only its own
    // nonce'd stylesheet, so an inline style would be silently dropped.
    const indent = row.depth ? ` class="depth${Math.min(row.depth, 4)}"` : '';
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
    return `<tr class="${classes}"${index === focused ? ' id="focus"' : ''}>` +
      `<td${indent}>${openable(row.label, row.definedAt, ` title="${escape(row.term)}"`)}</td>` +
      `<td><span class="kind">${escape(row.kind)}</span></td>` +
      `<td>${row.inherited ? escape(row.presence)
        : action('presence', index, row.presence, 'Change: optional or required')}</td>` +
      `<td>${row.inherited ? escape(row.value)
        : row.valueEditable ? action('value', index, row.value, 'Change what the value must be')
          : `<span title="${escape(row.valueLocked || '')}">${escape(row.value)}</span>`}` +
      `${verbatim}` +
      `${(row.notes || []).map((n) => `<div>${chip(n, 'bad')}</div>`).join('')}</td>` +
      (shapeColumn ? `<td>${row.contributions
        ? `${row.contributions.length} shapes <span class="dim">· all apply</span>`
        : shapeLink(row.shapeName, row.shape) +
        `${row.inheritedFrom ? ` <span class="dim">· from ${escape(row.inheritedFrom)}</span>` : ''}` +
        `${row.condition ? ` <span class="cond">· ${escape(row.condition)}</span>` : ''}`}</td>`
        : '') +
      `<td><a href="#" class="act" data-action="test" data-row="${index}" ` +
      `title="New test for ${escape(row.label)}: valid, or one of its constraints firing">` +
      `${tested || 'New test…'}</a></td><td>${model}</td>` +
      `<td class="acts">${actions(row, index)}</td></tr>` +
      (row.contributions && shapeColumn
        ? contributionRows(row, index, row.depth || 0) : '');
  }).join('');
}

function actions(row, index, contrib) {
  const at = `data-row="${index}"${contrib === undefined ? '' : ` data-contrib="${contrib}"`}`;
  if (row.via) {
    // A shape that reaches the type by another target: edited there.
    return `<button data-shape="${escape(row.shape)}" title="Edit it on its shape page">` +
      'Open shape</button>';
  }
  if (row.inherited && !row.contributions) {
    return `<button data-action="override" ${at} title="Declare a stricter ` +
      'constraint on this type\'s own shape">Override…</button>';
  }
  return `<button data-action="menu" ${at} title="More actions">⋯</button>`;
}

/** Beneath an attribute several shapes constrain: what each one says, and
 *  which of it the others already outdo. All of them apply (SHACL
 *  conjoins); the row above is what holds when they do. */
function contributionRows(row, index, depth) {
  const indent = `depth${Math.min(depth + 1, 4)}`;
  return row.contributions.map((c, j) => {
    const weaker = (c.noEffect || []).length
      ? ' ' + c.noEffect.map((n) => chip(`${n}: no effect`, '', 'Another shape on this ' +
        'attribute says something stricter, so this part never decides anything.')).join(' ')
      : '';
    // The shape's name goes where every row says where it is declared; the
    // attribute column stays empty -- these lines are about the same one.
    return `<tr class="contrib">` +
      `<td class="${indent}"></td>` +
      '<td></td>' +
      `<td>${escape(c.presence)}</td><td>${escape(c.value)}${weaker}</td>` +
      `<td>${shapeLink(c.shapeName, c.shape)}` +
      `${c.inheritedFrom ? ` <span class="dim">· from ${escape(c.inheritedFrom)}</span>` : ''}` +
      `${c.condition ? ` <span class="cond">· ${escape(c.condition)}</span>` : ''}</td>` +
      '<td></td><td></td>' +
      `<td class="acts">${actions(c, index, j)}</td></tr>`;
  }).join('');
}

/** A shape's name, opening its page: the shape is where the constraint lives. */
function shapeLink(name, iri) {
  const short = String(name || '').split(':').pop();
  return iri
    ? `<a href="#" class="mono" data-shape="${escape(iri)}" title="${escape(name)}">${escape(short)}</a>`
    : `<span class="mono">${escape(short)}</span>`;
}

function ruleRows(rules) {
  return rules.map((rule) => `<div class="rule">` +
    `<span class="kind">${escape(rule.kind)}</span>` +
    `<span class="what">${shapeLink(rule.shapeName, rule.shape)}` +
    `${rule.text ? ` <span class="dim">· ${escape(rule.text)}</span>` : ''}` +
    `${rule.inheritedFrom ? ` <span class="dim">· from ${escape(rule.inheritedFrom)}</span>` : ''}` +
    `${rule.condition ? ` <span class="cond">· ${escape(rule.condition)}</span>` : ''}</span>` +
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
  const also = page.alsoCheckedBy || [];

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
  .cond { color: var(--vscode-descriptionForeground); font-style: italic; }
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
  tr.contrib td { color: var(--vscode-descriptionForeground); font-size: 0.94em; border-top: 0;
                  padding-top: 2px; padding-bottom: 2px; }
  tr.flag td:first-child { box-shadow: inset 3px 0 0 var(--vscode-errorForeground, #f14c4c); }
  tr.focus td { background: var(--vscode-editor-selectionHighlightBackground, rgba(128,128,128,.2)); }
  tr.focus td:first-child { box-shadow: inset 3px 0 0 var(--vscode-focusBorder, #0078d4); }
  td.depth1 { padding-left: 30px; } td.depth2 { padding-left: 48px; }
  td.depth3 { padding-left: 66px; } td.depth4 { padding-left: 84px; }
  .kind { font-size: 0.84em; padding: 0 6px; border-radius: 3px;
          background: var(--vscode-badge-background); color: var(--vscode-badge-foreground); }
  .mono, .verbatim { font-family: var(--vscode-editor-font-family); font-size: 0.92em; }
  .verbatim { color: var(--vscode-descriptionForeground); white-space: normal; margin-top: 2px; }
  .rules { display: grid; gap: 6px; }
  .rule { display: grid; grid-template-columns: auto 1fr auto; gap: 10px; align-items: baseline;
          padding: 6px 10px; border: 1px solid var(--vscode-panel-border, rgba(128,128,128,.35)); }
  .empty { color: var(--vscode-descriptionForeground); font-style: italic; }
  a.act { color: inherit; border-bottom: 1px dashed var(--vscode-descriptionForeground); }
  a.act:hover, a.act:focus-visible { color: var(--vscode-textLink-foreground); text-decoration: none; }
  td.acts { text-align: right; }
  td.acts button { padding: 0 8px; }
  button.primary { background: var(--vscode-button-background); color: var(--vscode-button-foreground);
                   border-color: var(--vscode-button-background); }
  button.primary:hover { background: var(--vscode-button-hoverBackground); }
  ul { margin: 0; padding-left: 1.1em; }
  li { margin: 2px 0; }
</style></head><body>
<div class="crumbs">${crumbs}<b>${escape(page.label)}</b> · <span class="mono">${escape(page.term)}</span></div>
<h1>${escape(page.label)}</h1>
<div class="chips">${chips}</div>
<div class="bar">
  <button class="primary" data-action="addAttribute" title="${page.ownShape
    ? `Add an attribute to ${escape(page.ownShapeName)}`
    : `${escape(page.label)} has no shape of its own yet: one is created for it first`}">+ Attribute</button>
  ${page.ownShape ? '' : '<button data-action="createShape" title="Write an empty shape targeting this type, e.g. for a SPARQL rule">Create its shape</button>'}
  ${page.shapeAt ? `<button data-open="${escape(page.shapeAt)}">Open the shape in .ttl</button>` : ''}
  <button data-action="newSubtype" title="Declare a new entity type that is a kind of ${escape(page.label)}">New subtype…</button>
  <button data-refresh="1">Refresh</button>
</div>

<h2>Attributes · own and inherited</h2>
${attributes.length ? `<div class="table"><table>
<thead><tr><th>Attribute</th><th>Kind</th><th>Presence</th><th>Value</th><th>Declared in</th><th>Tested</th><th>Model</th><th></th></tr></thead>
<tbody>${attributeRows(attributes, focusIndex(attributes, options && options.focus))}</tbody></table></div>`
    : '<p class="empty">No shape constrains an attribute of this type.</p>'}

<h2>Rules on the whole entity</h2>
<p class="dim">SPARQL constraints and rules read the entity as a whole, not one attribute.</p>
${rules.length ? `<div class="rules">${ruleRows(rules)}</div>`
    : '<p class="empty">No SPARQL constraint or rule applies to this type.</p>'}

${also.length ? `<h2>Shapes that apply under a condition</h2>
<p class="dim">They do not target ${escape(page.label)} by class; their constraints are in the
tables above, marked with the condition.</p>
<div class="rules">${also.map((a) => `<div class="rule"><span class="kind">shape</span>` +
    `<span class="what">${shapeLink(a.shapeName, a.shape)} <span class="cond">· ${escape(a.condition || a.target)}</span></span>` +
    `${a.reached ? chip(`reaches ${a.reached}`) : chip('none in the data yet')}</div>`).join('')}</div>` : ''}

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
  const focused = document.getElementById('focus');
  if (focused) { focused.scrollIntoView({ block: 'center' }); }
  document.addEventListener('click', (event) => {
    const target = event.target.closest('[data-open],[data-type],[data-shape],[data-refresh],[data-action]');
    if (!target) { return; }
    event.preventDefault();
    if (target.dataset.action) {
      vscode.postMessage({ command: target.dataset.action,
                           row: target.dataset.row === undefined ? -1 : Number(target.dataset.row),
                           contrib: target.dataset.contrib === undefined ? undefined
                             : Number(target.dataset.contrib) });
    }
    else if (target.dataset.open) { vscode.postMessage({ command: 'open', at: target.dataset.open }); }
    else if (target.dataset.type) { vscode.postMessage({ command: 'type', name: target.dataset.type }); }
    else if (target.dataset.shape) { vscode.postMessage({ command: 'shape', name: target.dataset.shape }); }
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

  /**
   * `focus` marks one attribute row ({path} from the Constraints tree,
   * {attribute} from the Knowledge tree). `preserveFocus` leaves the keyboard
   * where it was: a click in a tree opens the page beside the reader's
   * browsing, and the next arrow key should move in the tree, not the page.
   */
  async show(packageUri, entityType, focus, preserveFocus) {
    const client = this.clientHolder.client;
    if (!client || !packageUri || !entityType) {
      vscode.window.showWarningMessage(
        'SemForge: no package is open, or the language server is not running.');
      return;
    }
    const same = this.panel && this.current && this.current.packageUri === packageUri &&
      this.current.entityType === entityType &&
      JSON.stringify(this.current.focus) === JSON.stringify(focus);
    this.current = { packageUri, entityType, focus };
    if (!this.panel) {
      this.panel = vscode.window.createWebviewPanel(
        'semforgeTypePage', 'Entity type',
        { viewColumn: vscode.ViewColumn.Active, preserveFocus: !!preserveFocus },
        { enableScripts: true, localResourceRoots: [] });
      this.panel.onDidDispose(() => { this.panel = undefined; });
      this.panel.webview.onDidReceiveMessage((message) => this.receive(message));
    } else {
      this.panel.reveal(undefined, !!preserveFocus);
      if (same) {
        return;                        // clicked again: already showing it
      }
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
    this.page = page;
    this.panel.title = `${page.label} · type`;
    this.panel.webview.html = renderTypePage(page,
      { nonce: crypto.randomBytes(16).toString('base64'), focus: this.current.focus });
  }

  async receive(message) {
    if (!message || !this.current) {
      return;
    }
    const edit = EDITS[message.command];
    if (edit) {
      let row = this.page && this.page.attributes
        ? this.page.attributes[message.row] : undefined;
      if (row && row.contributions) {
        row = message.contrib !== undefined ? row.contributions[message.contrib]
          : message.command === 'test' ? row : await whichShape(row, message.command);
        if (!row) {
          return;
        }
      }
      const changed = await edit(this, row);
      if (changed) {
        await this.render();
        for (const command of REFRESH_VIEWS) {
          vscode.commands.executeCommand(command);
        }
      }
      return;
    }
    if (message.command === 'open' && message.at) {
      await showLocation(message.at, true);
    } else if (message.command === 'shape' && message.name) {
      await vscode.commands.executeCommand('semforge.openShapePage',
        { raw: { shape: message.name }, packageUri: this.current.packageUri });
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

// --- editing: each answers one click, and says whether anything changed --------------

async function request(pages, method, params) {
  const result = await pages.clientHolder.client.sendRequest(method,
    Object.assign({ uri: pages.current.packageUri }, params));
  if (!result.ok) {
    vscode.window.showErrorMessage(`SemForge: ${result.error}`);
    return false;
  }
  return result;
}

async function editPresence(pages, row) {
  if (!row) {
    return false;
  }
  const picked = await vscode.window.showQuickPick([
    { label: 'Required', description: 'sh:minCount 1', value: 'required' },
    { label: 'Optional', description: 'sh:minCount 0', value: 'optional' }
  ], { title: `${row.label}: present on every ${pages.page.subject || pages.page.label}?` });
  if (!picked) {
    return false;
  }
  return Boolean(await request(pages, 'semforge/editAttribute',
    { shape: row.shape, path: row.path, presence: picked.value }));
}

async function editValue(pages, row) {
  if (!row || !row.valueEditable) {
    if (row && row.valueLocked) {
      vscode.window.showInformationMessage(`SemForge: ${row.label}'s value is ${row.valueLocked}.`);
    }
    return false;
  }
  const value = await pickValue(pages.clientHolder.client, pages.current.packageUri,
    { kind: row.kind, term: row.term, label: row.label });
  if (value === undefined) {
    return false;
  }
  return Boolean(await request(pages, 'semforge/editAttribute', {
    shape: row.shape, path: row.path,
    value: value.datatype || value.valueClass ? value : { kind: 'any' }
  }));
}

function describeParameter(parameter) {
  return { label: `${parameter.parameter} ${parameter.value}`,
    description: parameter.layer === 'value' ? 'on the value' : 'on the attribute',
    parameter };
}

// Every constraint the editor writes, in words, with where it goes and what
// its value is. A count goes on the attribute (how many instances) or on the
// value; everything else only on the value.
const CONSTRAINTS = [
  { parameter: 'sh:minInclusive', words: 'at least (≥)', kind: 'number' },
  { parameter: 'sh:maxInclusive', words: 'at most (≤)', kind: 'number' },
  { parameter: 'sh:minExclusive', words: 'more than (>)', kind: 'number' },
  { parameter: 'sh:maxExclusive', words: 'less than (<)', kind: 'number' },
  { parameter: 'sh:datatype', words: 'the value\'s datatype', kind: 'choice' },
  { parameter: 'sh:class', words: 'the value is one of a class', kind: 'choice' },
  { parameter: 'sh:nodeKind', words: 'IRI, literal or blank node', kind: 'choice' },
  { parameter: 'sh:minLength', words: 'text at least this long', kind: 'integer' },
  { parameter: 'sh:maxLength', words: 'text at most this long', kind: 'integer' },
  { parameter: 'sh:pattern', words: 'text matching a regular expression', kind: 'text' },
  { parameter: 'sh:in', words: 'the value is one of a list', kind: 'list' },
  { parameter: 'sh:minCount', words: 'at least this many instances', kind: 'integer',
    layer: 'attribute' },
  { parameter: 'sh:maxCount', words: 'at most this many instances', kind: 'integer',
    layer: 'attribute' }
];

const KIND_PROMPT = {
  number: ['A number, e.g. 0 or 12.5', (t) => (/^[-+]?\d+(\.\d+)?([eE][-+]?\d+)?$/.test(t.trim())
    ? undefined : 'a number')],
  integer: ['A whole number, 0 or more', (t) => (/^\d+$/.test(t.trim()) ? undefined
    : 'a whole number')],
  text: ['A regular expression, e.g. ^[A-Z]{2}[0-9]+$', (t) => (t ? undefined : 'required')]
};

/**
 * An sh:in list. Where the value is drawn from a vocabulary class
 * (sh:class MachineState), its values are offered to tick -- the current
 * ones ticked; otherwise the items are typed, separated by commas: numbers,
 * "quoted text", prefixed names. Returns a list, a text, or undefined.
 */
async function askList(pages, row, current) {
  const cls = row.parameters.find((p) => p.layer === 'value' && p.parameter === 'sh:class');
  if (cls) {
    let page;
    try {
      page = await pages.clientHolder.client.sendRequest('semforge/vocabularyPage',
        { uri: pages.current.packageUri, cls: cls.value });
    } catch (error) {
      page = undefined;
    }
    if (page && page.ok && page.values.length) {
      const short = (term) => String(term).split(':').pop();
      const ticked = new Set((current || []).map(short));
      const picked = await vscode.window.showQuickPick(page.values.map((v) => ({
        label: v.name, description: v.label, value: v.term, picked: ticked.has(v.name) })),
      { title: `${row.label} · sh:in: which ${page.label} values are allowed?`,
        canPickMany: true });
      if (!picked) {
        return undefined;
      }
      if (!picked.length) {
        vscode.window.showWarningMessage('SemForge: an empty list admits no value; ' +
          'remove sh:in instead.');
        return undefined;
      }
      return picked.map((item) => item.value);
    }
  }
  const value = await vscode.window.showInputBox({
    title: `${row.label} · sh:in: the value is one of`,
    value: (current || []).join(', '),
    prompt: 'Separated by commas: numbers, "quoted text", prefixed names (ex:ON)',
    validateInput: (t) => (t.trim() ? undefined : 'at least one value; or remove sh:in') });
  return value === undefined ? undefined : value.trim();
}

async function askValue(pages, row, spec, current) {
  if (spec.kind === 'list') {
    return askList(pages, row, current);
  }
  if (spec.kind === 'choice') {
    const slot = row.kind === 'Relationship' ? 'ngsild:hasObject' : 'ngsild:hasValue';
    let offered = [];
    try {
      const answer = await pages.clientHolder.client.sendRequest('semforge/choices', {
        uri: pages.current.packageUri, path: row.path.concat([slot]),
        parameter: spec.parameter });
      offered = answer.choices || [];
    } catch (error) {
      offered = [];
    }
    const items = offered.map((c) => ({ label: c.label || c.value, description: c.detail,
      value: c.value }));
    items.push({ label: '$(edit) Enter a different value…', value: undefined });
    const picked = await vscode.window.showQuickPick(items,
      { title: `${row.label} · ${spec.parameter}`, matchOnDescription: true });
    if (!picked) {
      return undefined;
    }
    if (picked.value !== undefined) {
      return picked.value;
    }
  }
  const [prompt, validate] = KIND_PROMPT[spec.kind] ||
    ['A prefixed name, e.g. xsd:double', (t) => (t.trim() ? undefined : 'required')];
  const value = await vscode.window.showInputBox({
    title: `${row.label} · ${spec.parameter}: ${spec.words}`,
    value: current, prompt, validateInput: validate });
  return value === undefined ? undefined : value.trim();
}

async function editParameter(pages, row) {
  const have = row.parameters.map((p) => ({
    label: `${p.parameter} ${p.value}`,
    description: p.layer === 'value' ? 'on the value' : 'on the attribute',
    detail: 'change it, or remove it', existing: p }));
  const present = new Set(row.parameters.map((p) => `${p.layer}:${p.parameter}`));
  if (row.inList) {
    // A list is structure, not a plain parameter: listed here item by item.
    have.push({ label: `sh:in ${row.inList.value}`, description: 'on the value',
      detail: 'edit the list, or remove it',
      existing: { parameter: 'sh:in', value: row.inList.value, path: row.inList.path,
        layer: 'value', items: row.inList.items } });
    present.add('value:sh:in');
  }
  const add = [];
  for (const spec of CONSTRAINTS) {
    const layers = spec.layer === 'attribute' ? ['attribute', 'value'] : ['value'];
    for (const layer of layers) {
      if (!present.has(`${layer}:${spec.parameter}`)) {
        add.push({ label: `$(add) ${spec.parameter}`,
          description: `${spec.words}${layer === 'attribute' ? '' : ' · on the value'}`,
          spec, layer });
      }
    }
  }
  const picked = await vscode.window.showQuickPick([
    { label: 'On this attribute', kind: vscode.QuickPickItemKind.Separator },
    ...have,
    { label: 'Add a constraint', kind: vscode.QuickPickItemKind.Separator },
    ...add
  ], { title: `${row.label}: which constraint?`, matchOnDescription: true });
  if (!picked) {
    return false;
  }
  if (picked.existing) {
    const parameter = picked.existing;
    const spec = CONSTRAINTS.find((c) => c.parameter === parameter.parameter) ||
      { parameter: parameter.parameter, words: '', kind: 'term' };
    const how = await vscode.window.showQuickPick([
      { label: parameter.items ? '$(edit) Edit the list…' : '$(edit) Change the value…',
        action: 'change' },
      { label: `$(trash) Remove ${parameter.parameter}`, action: 'remove' }
    ], { title: `${row.label} · ${parameter.parameter} ${parameter.value}` });
    if (!how) {
      return false;
    }
    if (how.action === 'remove') {
      return Boolean(await request(pages, 'semforge/setConstraint', {
        shape: row.shape, path: parameter.path, parameter: parameter.parameter,
        remove: true }));
    }
    if (parameter.items) {
      // Written anew in place: the list as a whole is the value.
      const items = await askList(pages, row, parameter.items);
      if (items === undefined) {
        return false;
      }
      return Boolean(await request(pages, 'semforge/setConstraint', {
        shape: row.shape, path: row.path, parameter: 'sh:in', value: items,
        add: true, layer: 'value' }));
    }
    const value = await askValue(pages, row, spec, parameter.value);
    if (value === undefined || value === parameter.value) {
      return false;
    }
    return Boolean(await request(pages, 'semforge/setConstraint', {
      shape: row.shape, path: parameter.path, parameter: parameter.parameter, value }));
  }
  const value = await askValue(pages, row, picked.spec, picked.spec.kind === 'list' ? [] : '');
  if (value === undefined || value === '') {
    return false;
  }
  const done = await request(pages, 'semforge/setConstraint', {
    shape: row.shape, path: row.path, parameter: picked.spec.parameter, value,
    add: true, layer: picked.layer });
  if (done && done.note) {
    vscode.window.showWarningMessage(`SemForge: ${done.note}`);
  }
  return Boolean(done);
}

async function rowMenu(pages, row) {
  if (!row) {
    return false;
  }
  const shapeName = row.shapeName.split(':').pop();
  const choices = [
    { label: '$(beaker) New test…', description: 'valid, or one of its constraints firing',
      run: newTest },
    { label: '$(edit) Constraints…', description: 'add, change or remove: ranges, datatype, class, length, pattern, counts',
      run: editParameter },
    { label: '$(add) Add a sub-attribute…', description: `nested inside ${row.label}`,
      run: async () => {
        await vscode.commands.executeCommand('semforge.addAttributeConstraint', {
          raw: { kind: 'attribute', shape: row.shape, path: row.path,
            label: row.term, inheritedFrom: '' },
          packageUri: pages.current.packageUri });
        return true;
      } },
    { label: `$(remove) Remove from ${shapeName}…`,
      description: 'the attribute stays declared', run: removeFromShape },
    { label: '$(trash) Delete the attribute everywhere…',
      description: 'shows every dependent first',
      run: async () => {
        await vscode.commands.executeCommand('semforge.deleteAttribute', {
          raw: { iri: row.attribute }, packageUri: pages.current.packageUri });
        return true;
      } },
    { label: `$(merge) Merge ${shapeName} into…`,
      description: 'another shape selecting the same nodes; nothing checked changes',
      run: async () => Boolean(await vscode.commands.executeCommand('semforge.mergeShape', {
        raw: { shape: row.shape }, packageUri: pages.current.packageUri })) },
    { label: '$(go-to-file) Open in .ttl',
      run: async () => { await showLocation(row.definedAt, true); return false; } }
  ];
  const picked = await vscode.window.showQuickPick(choices, { title: row.label });
  return picked ? picked.run(pages, row) : false;
}

/** An attribute several shapes constrain is changed in ONE of them: which?
 *  Only this type's own shapes can be edited here; an inherited one is
 *  tightened with Override, and a conditional one on its shape page. */
async function whichShape(row, command) {
  const own = row.contributions.filter((c) => !c.inherited);
  const candidates = command === 'override'
    ? row.contributions.filter((c) => c.inherited && !c.via) : own;
  if (!candidates.length) {
    vscode.window.showInformationMessage(
      `SemForge: ${row.label} is constrained here by shapes this type does not own; ` +
        'open one of them to change it.');
    return undefined;
  }
  if (candidates.length === 1) {
    return candidates[0];
  }
  const picked = await vscode.window.showQuickPick(candidates.map((c) => ({
    label: c.shapeName.split(':').pop(), description: `${c.presence} · ${c.value}`,
    detail: (c.noEffect || []).length ? `no effect here: ${c.noEffect.join(', ')}` : undefined,
    contribution: c })),
  { title: `${row.label} is constrained by ${row.contributions.length} shapes: change which?` });
  return picked && picked.contribution;
}

/** The type has no shape of its own: write one targeting it. The type page
 *  re-renders after it, now with + Attribute. */
async function createShape(pages) {
  const made = await vscode.commands.executeCommand('semforge.newShape', {
    raw: { kind: 'type', targetClass: pages.page.iri, label: pages.page.label },
    packageUri: pages.current.packageUri }, { stay: true });
  return Boolean(made);
}

/** New subtype…: the shared command, with this type as the parent. The page
 *  itself does not change -- a subtype is not part of its parent's page. */
async function newSubtype(pages) {
  await vscode.commands.executeCommand('semforge.newSubtype', {
    raw: { targetClass: pages.page.iri }, packageUri: pages.current.packageUri });
  return false;
}

/** A test for this attribute: the shared command, aimed at this row. */
async function newTest(pages, row) {
  if (!row) {
    return false;
  }
  // On a type page the type is the page's; on a shape page it is the class
  // the shape targets -- and a shape targeting no class has no type to test.
  const type = 'testType' in pages.page ? pages.page.testType : pages.page.iri;
  if (!type) {
    vscode.window.showInformationMessage(
      `SemForge: ${pages.page.label} targets no entity type, so a test cannot pick ` +
        'an entity for it here. Open the attribute on the type page of an entity it reaches.');
    return false;
  }
  return vscode.commands.executeCommand('semforge.newAttributeTest', {
    raw: { kind: 'attribute', label: row.label, path: row.path, typeClass: type },
    packageUri: pages.current.packageUri });
}

async function removeFromShape(pages, row) {
  const shapeName = row.shapeName.split(':').pop();
  const answer = await vscode.window.showWarningMessage(
    `Remove ${row.label} from ${shapeName}?`,
    { modal: true, detail: `Its property shape — every constraint on it, and ` +
      `any sub-attribute nested in it — is taken out of ${shapeName}. The ` +
      'attribute stays declared in the knowledge, and stays constrained wherever ' +
      'else it is. The data is not touched.' },
    'Remove');
  if (answer !== 'Remove') {
    return false;
  }
  return Boolean(await request(pages, 'semforge/removeProperty',
    { shape: row.shape, path: row.path }));
}

async function override(pages, row) {
  if (!row) {
    return false;
  }
  if (!pages.page.ownShape) {
    vscode.window.showInformationMessage(
      `SemForge: ${pages.page.label} has no shape of its own to declare it on.`);
    return false;
  }
  const picked = await vscode.window.showQuickPick(row.parameters.map(describeParameter),
    { title: `${row.label}: which inherited constraint to tighten on ${pages.page.label}?` });
  if (!picked) {
    return false;
  }
  const { parameter } = picked;
  const value = await vscode.window.showInputBox({
    title: `${parameter.parameter} on ${pages.page.label}`, value: parameter.value,
    prompt: `Inherited from ${row.inheritedFrom}: ${parameter.value}. SHACL conjoins, ` +
      'so this can only make the constraint stricter.'
  });
  if (value === undefined) {
    return false;
  }
  const send = (force) => pages.clientHolder.client.sendRequest('semforge/override', {
    uri: pages.current.packageUri, targetShape: pages.page.ownShape,
    path: parameter.path, parameter: parameter.parameter,
    inheritedValue: parameter.value, value, force });
  let result = await send(false);
  if (!result.ok && (result.effect === 'weaker' || result.effect === 'same')) {
    const choice = await vscode.window.showWarningMessage(
      `${parameter.parameter} ${parameter.value} → ${value} is ${result.effect}. ${result.error}`,
      { modal: true }, 'Add it anyway');
    if (choice !== 'Add it anyway') {
      return false;
    }
    result = await send(true);
  }
  if (!result.ok) {
    vscode.window.showErrorMessage(`SemForge: ${result.error}`);
    return false;
  }
  return true;
}

async function addAttribute(pages) {
  return addAttributeToType(pages.current.packageUri, {
    iri: pages.page.iri, label: pages.page.label,
    shapes: pages.page.ownShape
      ? [{ shape: pages.page.ownShape, label: pages.page.ownShapeName }] : [] });
}

/**
 * + Attribute on a type: the attribute goes into one of the type's OWN shapes.
 * A type with none yet -- a new subtype, judged only by what it inherits --
 * gets one first (its name is asked, prefilled), so adding an attribute never
 * stops at "create a shape first".
 */
async function addAttributeToType(packageUri, type) {
  let target = type.shapes[0];
  if (type.shapes.length > 1) {
    const picked = await vscode.window.showQuickPick(
      type.shapes.map((s) => ({ label: s.label, shape: s })),
      { title: `+ Attribute on ${type.label}: into which of its shapes?` });
    if (!picked) {
      return false;
    }
    target = picked.shape;
  }
  if (!target) {
    const made = await vscode.commands.executeCommand('semforge.newShape', {
      raw: { kind: 'type', targetClass: type.iri, label: type.label }, packageUri },
    { stay: true, quiet: true });
    if (!made) {
      return false;
    }
    target = { shape: made.iri, label: made.name };
  }
  await vscode.commands.executeCommand('semforge.addAttributeConstraint', {
    raw: { kind: 'shape', shape: target.shape, label: target.label, inheritedFrom: '' },
    packageUri });
  return true;
}

const EDITS = { presence: editPresence, value: editValue, menu: rowMenu, test: newTest,
  createShape, newSubtype,
  override, addAttribute };

/** The entity type a tree row stands for, whichever tree it is in. */
function typeOf(node) {
  const raw = node && node.raw;
  if (!raw) {
    return undefined;
  }
  return raw.targetClass || raw.typeClass || (raw.kind === 'class' && raw.iri) ||
    raw.entityType || raw.iri || undefined;
}

/** The attribute row a tree row points at on its type's page, if any. */
function focusOf(node) {
  const raw = node && node.raw;
  if (!raw || raw.kind === 'type' || raw.kind === 'class' || raw.kind === 'carrier') {
    return undefined;
  }
  const path = Array.isArray(raw.path) && raw.path.length ? raw.path : undefined;
  const attribute = raw.kind === 'attribute' && raw.iri ? raw.iri : undefined;
  return path || attribute ? { path, attribute } : undefined;
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
    vscode.commands.registerCommand('semforge.openTypePage', async (node, options) => {
      const client = clientHolder.client;
      const packageUri = (node && node.packageUri) || session.uri;
      if (!client || !packageUri) {
        vscode.window.showWarningMessage(
          'SemForge: no package is open, or the language server is not running.');
        return;
      }
      const entityType = node && node.raw ? typeOf(node) : await pickType(client, packageUri);
      if (entityType) {
        await pages.show(packageUri, entityType, focusOf(node),
          !!(options && options.preserveFocus));
      }
    }),
    // + Attribute on a type row in the Types view: its own shapes are the
    // children not marked inherited.
    vscode.commands.registerCommand('semforge.addTypeAttribute', async (node) => {
      const raw = node && node.raw;
      const packageUri = (node && node.packageUri) || session.uri;
      if (!raw || !packageUri || !clientHolder.client) {
        return false;
      }
      const shapes = (raw.children || [])
        .filter((c) => c.kind === 'shape' && !c.inheritedFrom && c.shape)
        .map((c) => ({ shape: c.shape, label: c.label }));
      const changed = await addAttributeToType(packageUri,
        { iri: typeOf(node), label: raw.label, shapes });
      if (changed) {
        for (const command of REFRESH_VIEWS) {
          vscode.commands.executeCommand(command);
        }
        pages.refresh();
      }
      return changed;
    }),
    vscode.workspace.onDidSaveTextDocument(() => pages.refresh())
  );
  return pages;
}

module.exports = { register, renderTypePage, TypePages, typeOf, focusOf, focusIndex, escape,
  attributeRows, EDITS };
