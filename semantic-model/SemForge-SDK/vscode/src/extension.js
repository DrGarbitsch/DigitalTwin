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

function startClient(context) {
  const folders = vscode.workspace.workspaceFolders;
  const root = folders && folders.length ? folders[0].uri.fsPath : undefined;
  const python = resolvePython(root);

  const serverOptions = {
    command: python,
    args: ['-m', 'semforge.editor.server'],
    transport: TransportKind.stdio,
    options: { cwd: root }
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
  context.subscriptions.push(client);
}

function activate(context) {
  startClient(context);

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
