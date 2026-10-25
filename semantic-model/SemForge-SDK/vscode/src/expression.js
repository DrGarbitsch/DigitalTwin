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
 * The expression editor: a value that is more than one set of conditions.
 *
 * Opened only when the value already is an expression (sh:or, sh:and,
 * sh:xone, sh:not on its value layer) or when asked for with "Combine with
 * another condition…" in the value picker. One plain value -- what nearly
 * every attribute needs -- never sees it.
 *
 * The expression is shown as a tree, one line per part; picking a part offers
 * what can be done to it. Every change is one request to the server, which
 * rewrites the value layer and reads it back before keeping it
 * (cooked/expression.py).
 */
const vscode = require('vscode');

const CONNECTIVE_WORDS = { or: 'any of', and: 'all of', xone: 'exactly one of', not: 'not' };

// What a condition may be, in the order a reader thinks of them.
const CONDITIONS = [
  { parameter: 'sh:datatype', label: 'A datatype', detail: 'number, text, date, …', ask: 'choice' },
  { parameter: 'sh:class', label: 'A class', detail: 'a vocabulary term, or an entity type', ask: 'choice' },
  { parameter: 'sh:hasValue', label: 'Exactly this value', detail: 'a number, "text", or a prefixed name', ask: 'text' },
  { parameter: 'sh:in', label: 'One of a list', detail: 'separated by commas', ask: 'text' },
  { parameter: 'sh:minInclusive', label: 'At least (≥)', ask: 'number' },
  { parameter: 'sh:minExclusive', label: 'More than (>)', ask: 'number' },
  { parameter: 'sh:maxInclusive', label: 'At most (≤)', ask: 'number' },
  { parameter: 'sh:maxExclusive', label: 'Less than (<)', ask: 'number' },
  { parameter: 'sh:minLength', label: 'At least this many characters', ask: 'integer' },
  { parameter: 'sh:maxLength', label: 'At most this many characters', ask: 'integer' },
  { parameter: 'sh:pattern', label: 'Matching a pattern', detail: 'a regular expression', ask: 'text' }
];

async function send(pages, method, params) {
  const client = pages.clientHolder.client;
  if (!client) {
    return undefined;
  }
  const answer = await client.sendRequest(method, Object.assign({ uri: pages.current.packageUri }, params));
  if (!answer || !answer.ok) {
    vscode.window.showErrorMessage(`SemForge: ${(answer && answer.error) || 'no answer'}`);
    return undefined;
  }
  return answer;
}

/** {parameter, value} for one condition, or undefined when cancelled. */
async function askCondition(pages, row, title, only) {
  const offered = only ? CONDITIONS.filter((c) => c.parameter === only) : CONDITIONS;
  const spec = offered.length === 1 ? offered[0]
    : await vscode.window.showQuickPick(offered, { title });
  if (!spec) {
    return undefined;
  }
  if (spec.ask === 'choice') {
    const slot = row.kind === 'Relationship' ? 'ngsild:hasObject' : 'ngsild:hasValue';
    let choices = [];
    try {
      const answer = await pages.clientHolder.client.sendRequest('semforge/choices', {
        uri: pages.current.packageUri, path: [row.term, slot], parameter: spec.parameter });
      choices = answer.choices || [];
    } catch (error) {
      choices = [];
    }
    const items = choices.map((c) => ({ label: c.label || c.value, description: c.value,
      detail: c.detail, value: c.value }))
      .concat([{ label: '$(edit) Enter another…', value: undefined }]);
    const picked = await vscode.window.showQuickPick(items,
      { title: `${title} · ${spec.label}`, matchOnDescription: true });
    if (!picked) {
      return undefined;
    }
    if (picked.value !== undefined) {
      return { parameter: spec.parameter, value: picked.value };
    }
  }
  const value = await vscode.window.showInputBox({
    title: `${title} · ${spec.label}`,
    prompt: spec.detail || '',
    validateInput: (text) => {
      const raw = text.trim();
      if (!raw) {
        return 'a value is needed';
      }
      if (spec.ask === 'number' && Number.isNaN(Number(raw))) {
        return 'a number';
      }
      if (spec.ask === 'integer' && !/^\d+$/.test(raw)) {
        return 'a whole number, 0 or more';
      }
      return undefined;
    }
  });
  return value === undefined ? undefined : { parameter: spec.parameter, value: value.trim() };
}

/** The tree as quick pick items, one per part, indented by depth. */
function lines(node, address, depth, out) {
  const indent = ' '.repeat(depth);
  if (node.kind === 'op') {
    if (address.length) {
      out.push({ label: `${indent}$(symbol-operator) ${node.words}`, node, address });
    }
    node.children.forEach((child, index) =>
      lines(child, address.concat([index]), depth + (address.length ? 1 : 0), out));
  } else if (node.kind === 'leaf') {
    const own = address.length === 1 && address[0] === 0;
    if (own && !node.conditions.length) {
      return;          // the layer's own conditions, when there are none
    }
    out.push({ label: `${indent}$(symbol-field) ${node.words}`,
      description: own ? 'and always' : '', node, address });
  } else {
    out.push({ label: `${indent}$(code) ${node.words}`, description: 'kept as written — edit in the .ttl',
      node, address });
  }
  return out;
}

/** What can be done to one part; the server's action, or undefined. */
async function actionFor(pages, row, item) {
  const { node, address } = item;
  const title = `${row.label}: ${node.words}`;
  let choices;
  if (node.kind === 'leaf') {
    choices = [
      { label: '$(add) Add a condition…', op: 'set' },
      ...(node.conditions.length ? [
        { label: '$(edit) Change a condition…', op: 'change' },
        { label: '$(remove) Remove a condition…', op: 'unset' }] : []),
      { label: '$(symbol-operator) Or else…', description: 'any of: this, or another', op: 'wrap', connective: 'or' },
      { label: '$(symbol-operator) Exactly one of this and…', op: 'wrap', connective: 'xone' },
      { label: '$(circle-slash) Not this', op: 'wrap', connective: 'not' },
      ...(address.length > 1 || address[0] !== 0 ? [{ label: '$(trash) Remove this branch', op: 'remove' }] : [])
    ];
  } else if (node.kind === 'op') {
    choices = [
      ...(node.op !== 'not' ? [{ label: '$(add) Add a branch…', op: 'add' }] : []),
      ...(node.op !== 'not' ? ['or', 'and', 'xone'].filter((op) => op !== node.op).map((op) => ({
        label: `$(arrow-swap) Change to "${CONNECTIVE_WORDS[op]}"`, op: 'retype', connective: op })) : []),
      { label: '$(circle-slash) Not this', op: 'wrap', connective: 'not' },
      ...(node.op === 'not' || node.op === 'and' || node.children.length === 1
        ? [{ label: node.op === 'not' ? '$(debug-step-out) Drop the "not"' : '$(debug-step-out) Unwrap',
          op: 'unwrap' }] : []),
      { label: '$(trash) Remove', op: 'remove' }
    ];
  } else {
    choices = [{ label: '$(trash) Remove', op: 'remove' },
      { label: '$(go-to-file) Open in .ttl', op: 'open' }];
  }
  const picked = await vscode.window.showQuickPick(choices, { title });
  if (!picked) {
    return undefined;
  }
  if (picked.op === 'open') {
    await require('./reveal').showLocation(row.definedAt, true);
    return undefined;
  }
  const action = { op: picked.op, node: address, connective: picked.connective };
  if (picked.op === 'change') {
    const which = await vscode.window.showQuickPick(node.conditions.map((c) => ({
      label: `${c.parameter} ${c.value}`, parameter: c.parameter })), { title });
    if (!which) {
      return undefined;
    }
    const condition = await askCondition(pages, row, title, which.parameter);
    return condition && Object.assign(action, { op: 'set' }, condition);
  }
  if (picked.op === 'unset') {
    const which = await vscode.window.showQuickPick(node.conditions.map((c) => ({
      label: `${c.parameter} ${c.value}`, parameter: c.parameter })), { title });
    return which && Object.assign(action, { parameter: which.parameter });
  }
  if (['set', 'add'].includes(picked.op) ||
      (picked.op === 'wrap' && picked.connective !== 'not')) {
    const condition = await askCondition(pages, row, title);
    return condition && Object.assign(action, condition);
  }
  return action;
}

/**
 * Edit the value of `row` as an expression, until Done. Returns true when
 * something was written (the page then refreshes).
 */
async function openExpression(pages, row) {
  const where = { shape: row.shape, path: row.path };
  let changed = false;
  for (;;) {
    const read = await send(pages, 'semforge/expression', where);
    if (!read) {
      return changed;
    }
    if (!read.editable) {
      const open = await vscode.window.showInformationMessage(
        `SemForge: ${row.label}'s value is edited in the .ttl: ${read.reason}.`, 'Open in .ttl');
      if (open) {
        await require('./reveal').showLocation(row.definedAt, true);
      }
      return changed;
    }
    const items = [{ label: '$(check) Done', done: true },
      { label: read.said || 'any value', kind: vscode.QuickPickItemKind.Separator }]
      .concat(lines(read.expression, [], 0, []));
    const picked = await vscode.window.showQuickPick(items, {
      title: `${row.label}: what its value must be`,
      placeHolder: 'Pick a part to change it'
    });
    if (!picked || picked.done) {
      return changed;
    }
    const action = await actionFor(pages, row, picked);
    if (!action) {
      continue;
    }
    if (await send(pages, 'semforge/editExpression', Object.assign({ action }, where))) {
      changed = true;
    }
  }
}

/** "Combine with another condition…": one plain value becomes an expression. */
async function combine(pages, row) {
  const how = await vscode.window.showQuickPick([
    { label: 'Or else…', description: 'any of: what it is now, or another', connective: 'or' },
    { label: 'Exactly one of…', description: 'what it is now, or another, not both', connective: 'xone' },
    { label: 'But not…', description: 'what it is now, except', connective: 'not' }
  ], { title: `${row.label}: combine its value with another condition` });
  if (!how) {
    return false;
  }
  const condition = await askCondition(pages, row, `${row.label} · ${how.label}`);
  if (!condition) {
    return false;
  }
  const done = await send(pages, 'semforge/editExpression', {
    shape: row.shape, path: row.path,
    action: Object.assign({ op: 'combine', connective: how.connective }, condition) });
  if (!done) {
    return false;
  }
  await openExpression(pages, row);
  return true;
}

module.exports = { openExpression, combine, lines, CONDITIONS };
