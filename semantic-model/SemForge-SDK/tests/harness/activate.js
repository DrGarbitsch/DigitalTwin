/*
 * Activate the extension against a stub `vscode`.
 *
 * node --check only parses: it cannot see a function that is CALLED and never
 * DEFINED, which is how `sdkDirectory` went missing and left the extension
 * throwing ReferenceError at activation -- broken in exactly the way that looks
 * like "it finds nothing".
 */
const Module = require('module');
const path = require('path');
const original = Module._load;
const registered = [];

const noop = () => undefined;
const stub = {
  workspace: {
    getConfiguration: () => ({ get: () => '' }),
    workspaceFolders: [{ uri: { fsPath: process.argv[2] } }],
    createFileSystemWatcher: () => ({ dispose: noop }),
    onDidChangeConfiguration: noop,
    onDidSaveTextDocument: noop,
    openTextDocument: noop
  },
  window: {
    createTreeView: () => ({ dispose: noop, reveal: noop, onDidChangeSelection: noop }),
    onDidChangeActiveTextEditor: noop,
    activeTextEditor: undefined,
    showErrorMessage: (m) => { registered.push('ERROR: ' + m); return Promise.resolve(); },
    showInformationMessage: noop,
    createOutputChannel: () => ({ appendLine: noop, show: noop }),
    setStatusBarMessage: noop
  },
  commands: { registerCommand: (id) => { registered.push(id); return { dispose: noop }; },
              executeCommand: noop },
  EventEmitter: class { constructor() { this.event = noop; } fire() {} },
  ThemeIcon: class { constructor(i) { this.id = i; } },
  TreeItem: class { constructor(l) { this.label = l; } },
  TreeItemCollapsibleState: { None: 0, Collapsed: 1, Expanded: 2 },
  Position: class {}, Selection: class {}, Range: class {},
  TextEditorRevealType: { InCenter: 2 }, SymbolKind: { Class: 4 },
  MarkupKind: { Markdown: 'markdown' },
  Uri: { file: (p) => ({ fsPath: p, toString: () => 'file://' + p }) }
};

Module._load = function (request, parent, isMain) {
  if (request === 'vscode') return stub;
  if (request === 'vscode-languageclient/node') {
    // Stubbed, because the real library wants a far fuller vscode API than a
    // stub can provide. Whether it SHIPS is a separate question, and stubbing
    // it here is what hid the extension being packaged without it -- so
    // test_extension_packaging.py checks that every bare require resolves
    // inside the package. The two tests cover different failures.
    return { LanguageClient: class { start() {} stop() { return Promise.resolve(); } },
             TransportKind: { stdio: 0 } };
  }
  return original(request, parent, isMain);
};

const extension = require(path.resolve(process.argv[3]));
const context = { subscriptions: [] };
extension.activate(context);
console.log(JSON.stringify({ commands: registered.filter((r) => !r.startsWith('ERROR')),
                             errors: registered.filter((r) => r.startsWith('ERROR')) }));
