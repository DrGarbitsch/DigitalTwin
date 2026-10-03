/*
 * New test case…: add a test file to a suite.
 *
 * The general way in, beside New test… (one attribute) and New case… (one
 * SPARQL rule): a suite -- existing, or new for a shape -- good or bad, and a
 * start: a copy of a case, an entity from the model, a fresh entity of a
 * type, an empty file, or a .jsonld already under examples/ that nothing
 * declares. The SDK writes and declares it and runs it once; the case page
 * opens, where a bad case's firings become asserts with "Assert it".
 */

const vscode = require('vscode');

const { showLocation } = require('./reveal');

const SEPARATOR = vscode.QuickPickItemKind
  ? vscode.QuickPickItemKind.Separator : -1;

function base(path) {
  return String(path).split('/').pop().replace(/\.jsonld$/, '');
}

async function pickSuite(options, preset) {
  if (preset) {
    return { suite: preset };
  }
  const existing = new Set(options.suites);
  const items = options.suites.map((suite) => ({ label: `$(beaker) ${suite}`, suite }));
  const fresh = options.shapes.filter((s) => !existing.has(`test_${s.label}`));
  if (fresh.length) {
    items.push({ label: 'A new suite for a shape', kind: SEPARATOR });
    items.push(...fresh.map((s) => ({ label: `$(add) test_${s.label}`,
      description: `for ${s.name}`, suite: `test_${s.label}` })));
  }
  if (options.undeclared.length) {
    items.push({ label: 'Already written', kind: SEPARATOR });
    items.push({ label: '$(file-add) Declare a file under examples/ that nothing runs',
      description: `${options.undeclared.length} file(s)`, declare: true });
  }
  return vscode.window.showQuickPick(items, { title: 'New test case: in which suite?' });
}

async function pickExpect() {
  const picked = await vscode.window.showQuickPick([
    { label: '$(pass) Should conform', description: 'good/ · expect: valid', expect: 'valid' },
    { label: '$(error) Should violate', description: 'bad/ · expect: invalid — assert what ' +
      'fires on its case page', expect: 'invalid' }
  ], { title: 'New test case: what should it show?' });
  return picked && picked.expect;
}

async function pickStart(options) {
  const items = [];
  if (options.cases.length) {
    items.push({ label: '$(copy) A copy of a case', start: 'copy',
      description: 'its includes written into the new file' });
  }
  if (options.entities.length) {
    items.push({ label: '$(symbol-object) An entity from the model', start: 'model' });
  }
  if (options.types.length) {
    items.push({ label: '$(symbol-class) A new entity of a type', start: 'type',
      description: 'its required attributes given valid values' });
  }
  items.push({ label: '$(file) An empty file', start: 'empty' });
  const picked = await vscode.window.showQuickPick(items,
    { title: 'New test case: start from?' });
  if (!picked) {
    return undefined;
  }
  if (picked.start === 'copy') {
    const chosen = await vscode.window.showQuickPick(options.cases.map((c) => ({
      label: c.path, description: c.expect, detail: c.description, source: c.path })),
    { title: 'Copy which case?', matchOnDescription: true });
    return chosen && { start: 'copy', source: chosen.source, name: `${base(chosen.source)}-copy` };
  }
  if (picked.start === 'model') {
    const chosen = await vscode.window.showQuickPick(
      options.entities.map((id) => ({ label: id, source: id })),
      { title: 'Which entity from the model?' });
    return chosen && { start: 'model', source: chosen.source,
      name: chosen.source.split(/[:/#]/).filter(Boolean).slice(-2).join('-') };
  }
  if (picked.start === 'type') {
    const chosen = await vscode.window.showQuickPick(options.types.map((t) => ({
      label: t.label, description: t.term, source: t.iri })),
    { title: 'A new entity of which type?', matchOnDescription: true });
    return chosen && { start: 'type', source: chosen.source,
      name: `${chosen.label.toLowerCase()}-case` };
  }
  return { start: 'empty', source: '', name: 'new-case' };
}

async function newTestCase(clientHolder, session, node) {
  const client = clientHolder.client;
  const packageUri = (node && node.packageUri) || session.uri;
  if (!client || !packageUri) {
    vscode.window.showWarningMessage(
      'SemForge: no package is open, or the language server is not running.');
    return false;
  }
  const options = await client.sendRequest('semforge/testCaseOptions', { uri: packageUri });
  if (!options.ok) {
    vscode.window.showErrorMessage(`SemForge: ${options.error}`);
    return false;
  }
  const raw = (node && node.raw) || {};
  const preset = raw.kind === 'suite' ? (raw.term || raw.label) : '';
  const where = await pickSuite(options, preset);
  if (!where) {
    return false;
  }
  let request;
  if (where.declare) {
    const file = await vscode.window.showQuickPick(
      options.undeclared.map((path) => ({ label: path, path })),
      { title: 'Declare which file?' });
    if (!file) {
      return false;
    }
    const expect = await pickExpect();
    if (!expect) {
      return false;
    }
    request = { suite: '', expect, start: 'existing', source: file.path, name: '' };
  } else {
    const expect = await pickExpect();
    if (!expect) {
      return false;
    }
    const start = await pickStart(options);
    if (!start) {
      return false;
    }
    const name = await vscode.window.showInputBox({
      title: `New test case in ${where.suite}`,
      prompt: 'A name for the file (letters, digits, dashes)',
      value: start.name,
      validateInput: (text) => (/[A-Za-z0-9]/.test(text) ? undefined : 'a name is required')
    });
    if (!name) {
      return false;
    }
    request = { suite: where.suite, expect, start: start.start, source: start.source, name };
  }
  const made = await client.sendRequest('semforge/addTestCase',
    Object.assign({ uri: packageUri }, request));
  if (!made.ok) {
    vscode.window.showErrorMessage(`SemForge: ${made.error}`);
    return false;
  }
  vscode.commands.executeCommand('semforge.refreshModel');
  await vscode.commands.executeCommand('semforge.openCasePage',
    { raw: { kind: 'example', file: made.file }, packageUri });
  const said = made.passes
    ? `SemForge: ${made.case} written, and it passes.`
    : made.expect === 'invalid' && made.violations === 0
      ? `SemForge: ${made.case} written. Nothing fires yet: edit its data until it ` +
        'violates, then assert what fires on its case page.'
      : `SemForge: ${made.case} written; it does not pass yet: ${made.failures.join('; ')}`;
  const open = await (made.passes ? vscode.window.showInformationMessage(said, 'Open .jsonld')
    : vscode.window.showWarningMessage(said, 'Open .jsonld'));
  if (open) {
    await showLocation(`${made.file}:1`, true);
  }
  return made;
}

function register(context, clientHolder, session) {
  context.subscriptions.push(
    vscode.commands.registerCommand('semforge.newTestCase',
      (node) => newTestCase(clientHolder, session, node)));
}

module.exports = { register, newTestCase };
