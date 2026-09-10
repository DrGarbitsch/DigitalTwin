/*
 * Drive one command handler, or one tree provider, against a stub `vscode`.
 *
 * The activation harness proves the extension LOADS and registers its commands.
 * It could not see what a command DOES -- and that is where the failures have
 * been: an icon that sent the parent attribute's name, a tree that turned a
 * server error into an empty panel, a reveal that could not resolve its own
 * node after a refresh. None of those throw, and none of them log.
 *
 * Usage: node drive.js <workspace folder> <extension.js|src dir> <scenario.json>
 * Prints one JSON line describing what happened.
 */
const Module = require('module');
const path = require('path');
const original = Module._load;

const scenario = require(path.resolve(process.argv[4]));
const seen = {
  commands: [],
  requests: [],
  shown: [],
  quickPicks: [],
  inputs: [],
  info: [],
  warnings: [],
  errors: [],
  revealed: [],
  messages: []
};

const noop = () => undefined;
const registry = new Map();
const selections = [];

const stub = {
  workspace: {
    getConfiguration: () => ({ get: () => '' }),
    workspaceFolders: [{ uri: { fsPath: process.argv[2] } }],
    createFileSystemWatcher: () => ({ dispose: noop }),
    onDidChangeConfiguration: noop,
    onDidSaveTextDocument: noop,
    openTextDocument: (file) =>
      Promise.resolve({ uri: { fsPath: file }, lineCount: 10000 })
  },
  window: {
    createTreeView: (id) => ({
      dispose: noop,
      reveal: (node, options) =>
        Promise.resolve(seen.revealed.push({ view: id, key: node.key,
                                             options: options || {} })),
      onDidChangeSelection: (handler) => {
        selections.push({ view: id, handler });
        return { dispose: noop };
      }
    }),
    onDidChangeActiveTextEditor: noop,
    activeTextEditor: undefined,
    showTextDocument: (document, options) => {
      const editor = {
        document,
        selection: undefined,
        revealRange: (range) =>
          seen.shown.push({ file: document.uri.fsPath,
                            line: range && range.start && range.start.line,
                            preserveFocus: !!(options || {}).preserveFocus })
      };
      return Promise.resolve(editor);
    },
    showQuickPick: (items, options) => {
      const offered = (items || []).map((item) => ({
        label: item.label, description: item.description, value: item.value
      }));
      seen.quickPicks.push({ items: offered,
                             placeHolder: (options || {}).placeHolder });
      if (scenario.pick === undefined) {
        return Promise.resolve(undefined);
      }
      const chosen = typeof scenario.pick === 'number'
        ? items[scenario.pick]
        : items.find((item) => item.label === scenario.pick);
      return Promise.resolve(chosen);
    },
    showInputBox: (options) => {
      seen.inputs.push({ title: (options || {}).title,
                         value: (options || {}).value });
      return Promise.resolve(scenario.input);
    },
    showInformationMessage: (message, ...rest) => {
      seen.info.push(message);
      return Promise.resolve(scenario.answer);
    },
    showWarningMessage: (message) => {
      seen.warnings.push(message);
      return Promise.resolve(undefined);
    },
    showErrorMessage: (message) => {
      seen.errors.push(message);
      return Promise.resolve(undefined);
    },
    createOutputChannel: () => ({ appendLine: noop, show: noop }),
    setStatusBarMessage: (message) => seen.messages.push(message)
  },
  commands: {
    registerCommand: (id, handler) => {
      seen.commands.push(id);
      registry.set(id, handler);
      return { dispose: noop };
    },
    executeCommand: noop
  },
  EventEmitter: class { constructor() { this.event = noop; } fire() {} },
  ThemeIcon: class { constructor(i) { this.id = i; } },
  TreeItem: class { constructor(l, c) { this.label = l; this.collapsibleState = c; } },
  TreeItemCollapsibleState: { None: 0, Collapsed: 1, Expanded: 2 },
  Position: class { constructor(line, character) { this.line = line; this.character = character; } },
  Selection: class { constructor(a) { this.start = a; } },
  Range: class { constructor(a, b) { this.start = a; this.end = b; } },
  TextEditorRevealType: { InCenter: 2 }, SymbolKind: { Class: 4 },
  MarkupKind: { Markdown: 'markdown' },
  Uri: { file: (p) => ({ fsPath: p, toString: () => 'file://' + p }) }
};

// The server, canned: method -> result. Anything not listed rejects, which is
// itself a case worth driving.
const client = {
  sendRequest: (method, params) => {
    seen.requests.push({ method, params });
    const replies = scenario.replies || {};
    if (!(method in replies)) {
      return Promise.reject(new Error(`Unhandled method ${method}`));
    }
    const reply = replies[method];
    if (reply && reply.__reject) {
      return Promise.reject(new Error(reply.__reject));
    }
    return Promise.resolve(reply);
  },
  start: noop,
  stop: () => Promise.resolve()
};

Module._load = function (request, parent, isMain) {
  if (request === 'vscode') return stub;
  if (request === 'vscode-languageclient/node') {
    return {
      LanguageClient: class {
        constructor() { Object.assign(this, client); }
      },
      TransportKind: { stdio: 0 }
    };
  }
  return original(request, parent, isMain);
};

async function runCommand() {
  const extension = require(path.resolve(process.argv[3]));
  extension.activate({ subscriptions: [] });
  const handler = registry.get(scenario.command);
  if (!handler) {
    seen.errors.push(`command ${scenario.command} is not registered`);
    return;
  }
  await handler(scenario.node);
}

async function runTree() {
  const module = require(path.resolve(process.argv[3]));
  const Provider = module[scenario.provider];
  const provider = new Provider({ client });
  provider.view = {};
  provider.uri = scenario.uri;
  const first = await provider.getChildren();
  const firstKeys = first.map((node) => node.key);
  // Again, as happens whenever the tree follows the editor: the server sends
  // fresh objects, and the wrappers must stay the same ones the view holds.
  const second = await provider.getChildren();
  seen.tree = {
    roots: firstKeys,
    labels: first.map((node) => node.raw.label),
    message: provider.view.message,
    identityKept: first.length > 0 &&
      first.every((node, at) => node === second[at]),
    childIdentityKept: await (async () => {
      if (!first.length) {
        return null;
      }
      const kids = await provider.getChildren(first[0]);
      if (!kids.length) {
        return null;
      }
      await provider.getChildren();          // a refresh in between
      const again = await provider.getChildren(first[0]);
      return kids[0] === again[0] && provider.getParent(kids[0]) === first[0];
    })()
  };
}

async function runLocate() {
  const locate = require(path.resolve(process.argv[3]));
  seen.locate = {
    uri: locate.findPackageUri() || null,
    message: locate.noPackageMessage()
  };
}

/**
 * Drive a click: select a row in one view and see what happens.
 *
 * This goes through the real wiring -- the extension's own providers and
 * callbacks -- because the interesting part is the other view reacting, which no
 * handler test in isolation can show.
 */
async function runSelect() {
  const extension = require(path.resolve(process.argv[3]));
  extension.activate({ subscriptions: [] });
  const found = selections.filter((entry) => entry.view === scenario.view);
  if (!found.length) {
    seen.errors.push(`${scenario.view} registered no selection handler`);
    return;
  }
  for (const entry of found) {
    await entry.handler({ selection: [scenario.node] });
  }
}

const modes = { tree: runTree, locate: runLocate, select: runSelect };
((modes[scenario.mode] || runCommand)())
  .then(() => console.log(JSON.stringify(seen)))
  .catch((error) => {
    seen.errors.push(`threw: ${error && error.message}`);
    console.log(JSON.stringify(seen));
    process.exitCode = 0;
  });
