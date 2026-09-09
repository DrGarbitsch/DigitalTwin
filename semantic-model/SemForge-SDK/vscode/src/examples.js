/*
 * The example instances, as a tree.
 *
 * The constraint view shows the shapes; this shows the data they judge. What
 * makes it worth a view of its own rather than the JSON outline VS Code
 * already gives you is the verdicts: an entity says how many violations it
 * carries, and editing a value re-validates, so the effect of a change is
 * visible where the change was made.
 */

const fs = require('fs');
const path = require('path');
const vscode = require('vscode');

const { showLocation } = require('./reveal');

class ExampleTreeNode {
  constructor(raw, packageUri) {
    this.raw = raw;
    this.packageUri = packageUri;
  }
}

class ExampleTreeProvider {
  constructor(clientHolder) {
    this.clientHolder = clientHolder;
    this._onDidChangeTreeData = new vscode.EventEmitter();
    this.onDidChangeTreeData = this._onDidChangeTreeData.event;
    this.nodes = new Map();
  }

  refresh(uri) {
    if (uri) {
      this.uri = uri;
    }
    this._onDidChangeTreeData.fire();
  }

  wrap(raw) {
    if (!this.nodes.has(raw)) {
      this.nodes.set(raw, new ExampleTreeNode(raw, this.uri));
    }
    return this.nodes.get(raw);
  }

  getTreeItem(node) {
    const raw = node.raw;
    const hasChildren = (raw.children || []).length > 0;
    const item = new vscode.TreeItem(
      raw.label || raw.kind,
      hasChildren
        ? raw.kind === 'example' && !raw.severity
          ? vscode.TreeItemCollapsibleState.Collapsed
          : vscode.TreeItemCollapsibleState.Expanded
        : vscode.TreeItemCollapsibleState.None
    );
    item.description = raw.detail || '';
    // A row that stands for a datasetId can take a new observation, whether or
    // not there is already a series under it.
    const series = raw.observations > 1;
    item.contextValue = raw.datasetId
      ? series
        ? 'exampleSeries'
        : 'exampleDataset'
      : raw.editable
      ? 'exampleEditable'
      : raw.kind;

    if (raw.kind === 'suite') {
      // One test_<Shape> directory: its cases pass or they do not.
      item.iconPath = new vscode.ThemeIcon(
        raw.severity ? 'testing-failed-icon' : 'folder-library'
      );
    } else if (raw.kind === 'example') {
      // A declared case: green when it did what it says, red when it did not.
      item.iconPath = new vscode.ThemeIcon(
        raw.severity ? 'testing-failed-icon' : 'beaker'
      );
    } else if (raw.kind === 'include') {
      // A subobject. Editing it here would change every case that includes it,
      // so it is shown read-only and edited where it is declared.
      item.iconPath = new vscode.ThemeIcon('references');
    } else if (raw.kind === 'entity') {
      item.iconPath = new vscode.ThemeIcon(
        raw.severity ? 'error' : 'symbol-object'
      );
    } else if (raw.kind === 'meta') {
      item.iconPath = new vscode.ThemeIcon('watch');
    } else if (series) {
      // A time series: the row shows the value validation reads, the children
      // are the observations behind it.
      item.iconPath = new vscode.ThemeIcon('graph-line');
      item.tooltip =
        `${raw.observations} observations for datasetId ${raw.datasetId}\n` +
        'The row shows the one validation reads (latest observedAt).\n' +
        'Right-click to add another.';
    } else if (raw.severity) {
      item.iconPath = new vscode.ThemeIcon('warning');
    } else if (raw.editable) {
      item.iconPath = new vscode.ThemeIcon('edit');
    } else {
      item.iconPath = new vscode.ThemeIcon('symbol-field');
    }

    if (raw.messages && raw.messages.length) {
      item.tooltip = raw.messages.join('\n');
    }
    if (raw.messages && raw.messages.length) {
      item.tooltip = raw.messages.join('\n');
    }
    // No command on click. Clicking used to open the edit box, which is a
    // surprising thing for a single click to do -- and it replaced the one
    // thing a click should do, which is show you the row in the file. Editing
    // is the inline pencil and the context menu.
    return item;
  }

  async getChildren(node) {
    if (node) {
      return (node.raw.children || []).map((child) => this.wrap(child));
    }
    const client = this.clientHolder.client;
    if (!client || !this.uri) {
      return [];
    }
    const result = await client.sendRequest('semforge/examples', {
      uri: this.uri
    });
    if (result.error) {
      return [];
    }
    this.nodes = new Map();
    return (result.roots || []).map((raw) => this.wrap(raw));
  }
}

/**
 * A package artifact inside the opened folder, as a URI string.
 *
 * The common flow is "open the folder, click the icon" with no editor open at
 * all. Anchoring only to the active editor left the tree empty in exactly that
 * case, with nothing to say why.
 */
function defaultUri() {
  const folders = vscode.workspace.workspaceFolders || [];
  for (const folder of folders) {
    const root = folder.uri.fsPath;
    for (const name of ['shacl.ttl', 'knowledge.ttl', 'model-instance.jsonld']) {
      const candidate = path.join(root, name);
      if (fs.existsSync(candidate)) {
        return vscode.Uri.file(candidate).toString();
      }
    }
  }
  return undefined;
}

function register(context, clientHolder, onChanged) {
  const provider = new ExampleTreeProvider(clientHolder);
  const view = vscode.window.createTreeView('semforgeExamples', {
    treeDataProvider: provider
  });
  context.subscriptions.push(view);

  // Selecting a row moves the .jsonld to it. Every node carries its own
  // file:line now, so this lands on the entity, the attribute or the single
  // observation you picked.
  context.subscriptions.push(
    view.onDidChangeSelection(async (event) => {
      const selected = event.selection && event.selection[0];
      if (selected && selected.raw.definedAt) {
        await showLocation(selected.raw.definedAt, false);
      }
    })
  );

  if (!defaultUri() && !vscode.window.activeTextEditor) {
    view.message =
      'Open a folder holding knowledge.ttl, shacl.ttl and ' +
      'model-instance.jsonld — or run "SemForge: Doctor".';
  }

  const track = (editor) => {
    if (editor && /\.(ttl|jsonld)$/.test(editor.document.uri.fsPath)) {
      provider.refresh(editor.document.uri.toString());
    }
  };
  track(vscode.window.activeTextEditor);
  if (!provider.uri) {
    provider.refresh(defaultUri());
  }
  context.subscriptions.push(
    vscode.window.onDidChangeActiveTextEditor(track),
    vscode.workspace.onDidSaveTextDocument(() => provider.refresh())
  );

  context.subscriptions.push(
    vscode.commands.registerCommand('semforge.editValue', async (node) => {
      const raw = node && node.raw;
      if (!raw || !raw.editable) {
        return;
      }
      const value = await vscode.window.showInputBox({
        title: `${raw.label} on ${raw.entity}`,
        prompt:
          'JSON is parsed, so 42 is a number and {"@id": "..."} a node ' +
          'reference. Anything else is taken as a string.',
        value: raw.value
      });
      if (value === undefined) {
        return;
      }
      const result = await clientHolder.client.sendRequest('semforge/setValue', {
        uri: node.packageUri,
        entity: raw.entity,
        path: raw.path,
        file: raw.file,
        value
      });
      if (result.ok) {
        vscode.window.setStatusBarMessage(
          `SemForge: ${raw.label} ${result.old} → ${result.new}`,
          5000
        );
        provider.refresh();
        if (onChanged) {
          onChanged();
        }
      } else {
        vscode.window.showErrorMessage(`SemForge: ${result.error}`);
      }
    }),

    vscode.commands.registerCommand('semforge.refreshExamples', () =>
      provider.refresh()
    ),

    vscode.commands.registerCommand('semforge.addAttribute', async (node) => {
      const raw = node && node.raw;
      if (!raw || raw.kind !== 'entity') {
        return;
      }
      const name = await vscode.window.showInputBox({
        title: `New attribute on ${raw.entity}`,
        prompt: 'Prefixed name, e.g. iffBaseEntities:hasStrength'
      });
      if (!name) {
        return;
      }
      // Blank lets the server read the kind off the shapes, which is better
      // than asking the person the model is supposed to be helping.
      const { kinds } = await clientHolder.client.sendRequest('semforge/kinds', {});
      const picked = await vscode.window.showQuickPick(
        [{ label: 'From the shapes', description: 'let the model decide', value: '' }].concat(
          kinds.map((k) => ({ label: k, value: k }))
        ),
        { title: 'Attribute type' }
      );
      if (picked === undefined) {
        return;
      }
      const value = await vscode.window.showInputBox({
        title: `Value for ${name}`,
        prompt:
          'JSON is parsed. A Relationship takes an entity IRI; a Property ' +
          'takes a literal or {"@id": "…"}.'
      });
      if (value === undefined) {
        return;
      }
      const result = await clientHolder.client.sendRequest(
        'semforge/addAttribute',
        {
          uri: node.packageUri,
          entity: raw.entity,
          file: raw.file,
          name,
          kind: picked.value,
          value
        }
      );
      if (result.ok) {
        vscode.window.setStatusBarMessage(
          `SemForge: ${name} added as ${result.kind}`,
          5000
        );
        provider.refresh();
        if (onChanged) {
          onChanged();
        }
      } else {
        vscode.window.showErrorMessage(`SemForge: ${result.error}`);
      }
    }),

    vscode.commands.registerCommand('semforge.addEntity', async (node) => {
      const raw = node && node.raw;
      const file = raw && (raw.file || (raw.children || []).map((c) => c.file)[0]);
      if (!file) {
        return;
      }
      const id = await vscode.window.showInputBox({
        title: 'New entity',
        prompt: 'id, e.g. urn:filter:9',
        value: 'urn:'
      });
      if (!id) {
        return;
      }
      const entityType = await vscode.window.showInputBox({
        title: `Type of ${id}`,
        prompt: 'e.g. iffBaseEntities:Filter'
      });
      if (!entityType) {
        return;
      }
      const result = await clientHolder.client.sendRequest('semforge/addEntity', {
        uri: node.packageUri,
        file,
        id,
        entityType
      });
      if (result.ok) {
        provider.refresh();
        if (onChanged) {
          onChanged();
        }
      } else {
        vscode.window.showErrorMessage(`SemForge: ${result.error}`);
      }
    }),

    vscode.commands.registerCommand('semforge.addObservation', async (node) => {
      const raw = node && node.raw;
      if (!raw || !raw.attributePath || !raw.attributePath.length) {
        return;
      }
      const value = await vscode.window.showInputBox({
        title: `New observation of ${raw.label}`,
        prompt: `datasetId ${raw.datasetId || '@none'} — JSON is parsed`,
        value: raw.value
      });
      if (value === undefined) {
        return;
      }
      const observedAt = await vscode.window.showInputBox({
        title: 'observedAt',
        prompt:
          'ISO 8601 UTC with milliseconds. Later than the current one, or it ' +
          'will not become the value validation reads.',
        value: new Date().toISOString().replace(/\.\d{3}Z$/, '.000Z')
      });
      if (observedAt === undefined) {
        return;
      }
      const result = await clientHolder.client.sendRequest(
        'semforge/addObservation',
        {
          uri: node.packageUri,
          entity: raw.entity,
          attributePath: raw.attributePath,
          datasetId: raw.datasetId,
          file: raw.file,
          value,
          observedAt
        }
      );
      if (result.ok) {
        vscode.window.setStatusBarMessage(
          `SemForge: ${raw.label} now has ${result.count} observation(s)`,
          5000
        );
        provider.refresh();
        if (onChanged) {
          onChanged();
        }
      } else {
        vscode.window.showErrorMessage(`SemForge: ${result.error}`);
      }
    })
  );

  return provider;
}

module.exports = { register, ExampleTreeProvider };
