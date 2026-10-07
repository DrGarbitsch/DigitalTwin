/*
 * Rename… for a shape, a test case and a suite.
 *
 * A shape's name is written in more places than its declaration -- other
 * shapes' `sh:node`, a SPARQL body, every assert naming one of its
 * constraints, the digest of every residue it is part of -- so the SDK plans
 * the rename and this file says the plan before anything is written. A case
 * is its file and a suite its folder: those are moves, with the entries that
 * point at them following.
 *
 * Editors showing a moved file are closed and the file reopened where it went;
 * the SPARQL workbench of a renamed shape is closed (its query document is
 * named by the shape).
 */

const path = require('path');
const vscode = require('vscode');

const REFRESH_VIEWS = ['semforge.refreshShapes', 'semforge.refreshTree',
  'semforge.refreshModel'];

const NAME = /^[A-Za-z_][A-Za-z0-9_-]*(\.[A-Za-z0-9_-]+)*$/;

function validName(text) {
  return NAME.test(String(text || '').trim()) ? undefined
    : 'a letter or "_" first, then letters, digits, "_", "-" and "." (not at the end)';
}

function refreshViews() {
  for (const command of REFRESH_VIEWS) {
    vscode.commands.executeCommand(command);
  }
}

async function ask(client, method, params) {
  const answer = await client.sendRequest(method, params);
  if (!answer.ok) {
    vscode.window.showErrorMessage(`SemForge: ${answer.error}`);
    return undefined;
  }
  return answer;
}

/** Tabs showing a file at or under `where`, closed; the files they showed. */
async function closeTabs(where, scheme) {
  const groups = vscode.window.tabGroups;
  if (!groups) {
    return [];
  }
  const tabs = groups.all.flatMap((g) => g.tabs).filter((t) => t.input && t.input.uri &&
    (scheme ? t.input.uri.scheme === scheme && t.input.uri.path === where
      : t.input.uri.scheme === 'file' && (t.input.uri.fsPath === where ||
        t.input.uri.fsPath.startsWith(where + path.sep))));
  const files = tabs.map((t) => t.input.uri.fsPath);
  if (tabs.length) {
    await groups.close(tabs);
  }
  return files;
}

async function reopen(files, from, to) {
  for (const file of files) {
    const moved = to + file.slice(from.length);
    await vscode.window.showTextDocument(vscode.Uri.file(moved), { preview: false });
  }
}

/** What renaming says before it writes. */
function planned(plan) {
  const lines = [];
  for (const file of plan.files) {
    lines.push(`${path.basename(file.file)}: ${file.references} reference(s)` +
      (file.inQueries ? `, ${file.inQueries} of them in a SPARQL query` : ''));
  }
  const asserts = plan.asserts.reduce((sum, a) => sum + a.count, 0);
  if (asserts) {
    lines.push(`${asserts} assert(s) in ${plan.asserts.length} test case(s) name it: renamed with it.`);
  }
  if (plan.residues.length) {
    lines.push(`${plan.residues.length} case(s) pin a residue: each that holds now is pinned ` +
      'again, since a rename changes no verdict.');
  }
  return lines.join('\n');
}

async function renameShape(clientHolder, session, node, bench) {
  const client = clientHolder.client;
  const packageUri = (node && node.packageUri) || session.uri;
  const shape = node && node.raw && node.raw.shape;
  if (!client || !packageUri || !shape) {
    vscode.window.showWarningMessage('SemForge: Rename… works on a shape.');
    return undefined;
  }
  const old = shape.split(/[/#]/).pop();
  const name = await vscode.window.showInputBox({
    title: `Rename ${old}`, value: old, valueSelection: [0, old.length],
    prompt: 'Its new name, in the same namespace. Every reference, assert and residue follows.',
    validateInput: (text) => text.trim() === old ? 'that is its name' : validName(text)
  });
  if (!name) {
    return undefined;
  }
  const plan = await ask(client, 'semforge/renameShapePlan',
    { uri: packageUri, shape, name: name.trim() });
  if (!plan) {
    return undefined;
  }
  const buttons = ['Rename'];
  if (plan.suite && plan.suite.free) {
    buttons.unshift(`Rename it and ${plan.suite.from}`);
  }
  const detail = planned(plan) + (plan.suite ? '\n\n' + (plan.suite.free
    ? `The suite folder ${plan.suite.from} can be renamed to ${plan.suite.to} too.`
    : `${plan.suite.to} already exists, so ${plan.suite.from} keeps its name.`) : '');
  const answer = await vscode.window.showWarningMessage(
    `Rename ${plan.name} to ${plan.newCurie}?`, { modal: true, detail }, ...buttons);
  if (!answer) {
    return undefined;
  }
  // The workbench's query document is named by the shape: it goes.
  if (bench && bench.current && bench.current.shape === shape && bench.panel) {
    if (bench.uri) {
      await bench.close(bench.uri);
    }
    bench.panel.dispose();
  }
  const suite = answer !== 'Rename';
  const done = await ask(client, 'semforge/renameShape',
    { uri: packageUri, shape, name: name.trim(), suite });
  if (!done) {
    return undefined;
  }
  refreshViews();
  await vscode.commands.executeCommand('semforge.openShapePage',
    { raw: { shape: done.newIri }, packageUri });
  vscode.window.showInformationMessage(`SemForge: ${done.oldName} is now ${done.newName}` +
    (done.asserts ? `, with ${done.asserts} assert(s)` : '') +
    (done.repinned.length ? `; ${done.repinned.length} residue(s) pinned again` : '') +
    (done.suiteMoved ? `; its suite is ${done.suiteMoved}` : '') + '.');
  return done;
}

async function renameCase(clientHolder, session, node) {
  const client = clientHolder.client;
  const packageUri = (node && node.packageUri) || session.uri;
  const file = node && node.raw && node.raw.file;
  if (!client || !packageUri || !file) {
    vscode.window.showWarningMessage('SemForge: Rename… works on a test case.');
    return undefined;
  }
  const old = path.basename(file).replace(/\.jsonld$/, '');
  const name = await vscode.window.showInputBox({
    title: `Rename the case ${old}`, value: old, valueSelection: [0, old.length],
    prompt: 'Its new file name (.jsonld is kept). Its expectations entry follows.',
    validateInput: (text) => text.trim().replace(/\.jsonld$/, '') === old ? 'that is its name'
      : validName(text.trim().replace(/\.jsonld$/, ''))
  });
  if (!name) {
    return undefined;
  }
  const open = await closeTabs(file);
  const done = await ask(client, 'semforge/renameCase',
    { uri: packageUri, case: file, name: name.trim() });
  if (!done) {
    await reopen(open, file, file);
    return undefined;
  }
  await reopen(open, file, done.file);
  refreshViews();
  await vscode.commands.executeCommand('semforge.openCasePage',
    { raw: { kind: 'example', file: done.file }, packageUri });
  return done;
}

async function renameSuite(clientHolder, session, node) {
  const client = clientHolder.client;
  const packageUri = (node && node.packageUri) || session.uri;
  const raw = node && node.raw;
  const folder = raw && (raw.term || raw.label);
  if (!client || !packageUri || !raw || raw.kind !== 'suite' || !folder) {
    vscode.window.showWarningMessage('SemForge: Rename… works on a suite.');
    return undefined;
  }
  const old = folder.split('/').pop();
  const name = await vscode.window.showInputBox({
    title: `Rename the suite ${old}`, value: old, valueSelection: [0, old.length],
    prompt: 'Its new folder name. Nothing inside it changes.',
    validateInput: (text) => text.trim() === old ? 'that is its name' : validName(text)
  });
  if (!name) {
    return undefined;
  }
  const done = await ask(client, 'semforge/renameSuite',
    { uri: packageUri, suite: folder, name: name.trim() });
  if (!done) {
    return undefined;
  }
  // Editors of files in the folder now show a path that is gone.
  await reopen(await closeTabs(done.source), done.source, done.folder);
  refreshViews();
  return done;
}

function register(context, clientHolder, session, bench) {
  context.subscriptions.push(
    vscode.commands.registerCommand('semforge.renameShape',
      (node) => renameShape(clientHolder, session, node, bench)),
    vscode.commands.registerCommand('semforge.renameTestCase',
      (node) => renameCase(clientHolder, session, node)),
    vscode.commands.registerCommand('semforge.renameSuite',
      (node) => renameSuite(clientHolder, session, node))
  );
}

module.exports = { register, renameShape, renameCase, renameSuite, validName };
