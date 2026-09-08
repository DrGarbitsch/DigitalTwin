/*
 * The example instances, as a tree.
 *
 * The constraint view shows the shapes; this shows the data they judge. What
 * makes it worth a view of its own rather than the JSON outline VS Code
 * already gives you is the verdicts: an entity says how many violations it
 * carries, and editing a value re-validates, so the effect of a change is
 * visible where the change was made.
 */

const vscode = require('vscode');

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
        ? raw.kind === 'entity'
          ? vscode.TreeItemCollapsibleState.Collapsed
          : vscode.TreeItemCollapsibleState.Collapsed
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

    if (raw.kind === 'example') {
      item.iconPath = new vscode.ThemeIcon('database');
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
    if (raw.editable) {
      item.command = {
        command: 'semforge.editValue',
        title: 'Edit value',
        arguments: [node]
      };
    }
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

function register(context, clientHolder, onChanged) {
  const provider = new ExampleTreeProvider(clientHolder);
  const view = vscode.window.createTreeView('semforgeExamples', {
    treeDataProvider: provider
  });
  context.subscriptions.push(view);

  const track = (editor) => {
    if (editor && /\.(ttl|jsonld)$/.test(editor.document.uri.fsPath)) {
      provider.refresh(editor.document.uri.toString());
    }
  };
  track(vscode.window.activeTextEditor);
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
