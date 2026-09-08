/*
 * SemForge VS Code extension.
 *
 * This file starts a language server and gets out of the way. Every semantic
 * decision -- what is a violation, which constraint no example exercises, where
 * a property is declared -- is made by the SDK and reaches here as an ordinary
 * LSP message. That is deliberate: the VS Code layer must not become the
 * semantic engine, or the CLI and CI stop agreeing with the editor.
 */

const fs = require('fs');
const path = require('path');
const vscode = require('vscode');
const { LanguageClient, TransportKind } = require('vscode-languageclient/node');

const cookedTree = require('./tree');
const exampleTree = require('./examples');

// Shared so the tree provider always talks to the CURRENT client: restarting
// the server must not leave the view wired to a dead one.
const clientHolder = { client: undefined };
let client;

/**
 * Find a Python that has semforge importable.
 *
 * Order: the configured interpreter, then the SDK's own venv (which is what
 * `make setup` builds), then whatever python3 is on PATH.
 */
function resolvePython(workspaceFolder) {
  const configured = vscode.workspace
    .getConfiguration('semforge')
    .get('pythonPath');
  if (configured) {
    return configured;
  }
  if (workspaceFolder) {
    const candidates = [
      path.join(workspaceFolder, 'venv', 'bin', 'python'),
      path.join(workspaceFolder, 'semantic-model', 'SemForge-SDK', 'venv', 'bin', 'python'),
      path.join(workspaceFolder, 'SemForge-SDK', 'venv', 'bin', 'python')
    ];
    for (const candidate of candidates) {
      if (fs.existsSync(candidate)) {
        return candidate;
      }
    }
  }
  return 'python3';
}

/**
 * The SDK directory for an interpreter at <sdk>/venv/bin/python, or undefined.
 *
 * Used as the server's working directory and PYTHONPATH so that an SDK which
 * has not been `pip install -e .`'d still starts. Without it the server is
 * launched in the folder the user opened, where `semforge` is not importable --
 * which fails silently, because a language server that exits immediately looks
 * exactly like one that found nothing to report.
 */
function sdkDirectory(python) {
  const parts = python.split(path.sep);
  const index = parts.lastIndexOf('venv');
  if (index <= 0) {
    return undefined;
  }
  const candidate = parts.slice(0, index).join(path.sep);
  return fs.existsSync(path.join(candidate, 'semforge')) ? candidate : undefined;
}

function startClient(context) {
  const folders = vscode.workspace.workspaceFolders;
  const root = folders && folders.length ? folders[0].uri.fsPath : undefined;
  const python = resolvePython(root);
  const sdk = sdkDirectory(python);

  const environment = Object.assign({}, process.env);
  if (sdk) {
    environment.PYTHONPATH = environment.PYTHONPATH
      ? `${sdk}${path.delimiter}${environment.PYTHONPATH}`
      : sdk;
  }

  const serverOptions = {
    command: python,
    args: ['-m', 'semforge.editor.server'],
    transport: TransportKind.stdio,
    options: { cwd: sdk || root, env: environment }
  };

  const clientOptions = {
    // Turtle carries the shapes and the ontology; the model instance is
    // JSON-LD. Opening any of them should activate the package.
    documentSelector: [
      { scheme: 'file', language: 'turtle' },
      { scheme: 'file', pattern: '**/*.ttl' },
      { scheme: 'file', pattern: '**/*.jsonld' }
    ],
    synchronize: {
      fileEvents: vscode.workspace.createFileSystemWatcher(
        '**/*.{ttl,jsonld,yaml}'
      )
    },
    outputChannelName: 'SemForge'
  };

  client = new LanguageClient(
    'semforge',
    'SemForge Language Server',
    serverOptions,
    clientOptions
  );
  client.start();
  clientHolder.client = client;
  context.subscriptions.push(client);
}

function activate(context) {
  startClient(context);
  // The constraint view and the example view are two halves of one loop:
  // editing data should refresh the shapes' verdicts and vice versa.
  const constraints = cookedTree.register(context, clientHolder);
  exampleTree.register(context, clientHolder, () => constraints.refresh());

  context.subscriptions.push(
    vscode.commands.registerCommand('semforge.restart', async () => {
      if (client) {
        await client.stop();
      }
      startClient(context);
      vscode.window.showInformationMessage('SemForge language server restarted');
    })
  );

  // Revalidation is a save in disguise: the server analyses the whole package
  // on save, so this just re-triggers it for the active file.
  context.subscriptions.push(
    vscode.commands.registerCommand('semforge.revalidate', async () => {
      const editor = vscode.window.activeTextEditor;
      if (editor) {
        await editor.document.save();
      }
    })
  );
}

function deactivate() {
  return client ? client.stop() : undefined;
}

module.exports = { activate, deactivate };
