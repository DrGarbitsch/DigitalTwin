/*
 * Every shape, whatever it targets.
 *
 * The Types view reads constraints by entity type. But a SHACL shape is not
 * tied to one: it selects focus nodes by class, by named node, by the subjects
 * or objects of a predicate, by a SPARQL query -- or it has no target and is
 * reached from another shape through sh:node. A shape of that second kind
 * belongs to no type, and in a tree organised by type it was nowhere.
 *
 * So each shape is a row here, its description saying in words what it
 * targets ("targets subjects of hasValve"), and a click opens its page.
 */

const vscode = require('vscode');

const { noPackageMessage } = require('./locate');
const { showLocation, treeDetail, treeClick, icon } = require('./reveal');

class ShapeNode {
  constructor(raw, packageUri) {
    this.raw = raw;
    this.packageUri = packageUri;
  }
}

class ShapesTreeProvider {
  constructor(clientHolder) {
    this.clientHolder = clientHolder;
    this._onDidChangeTreeData = new vscode.EventEmitter();
    this.onDidChangeTreeData = this._onDidChangeTreeData.event;
  }

  refresh(uri) {
    if (uri) {
      this.uri = uri;
    }
    this._onDidChangeTreeData.fire();
  }

  setPackage(uri) {
    this.uri = uri || undefined;
    this._onDidChangeTreeData.fire();
  }

  message(text) {
    if (this.view) {
      this.view.message = text;
    }
  }

  getParent() {
    return undefined;                  // a flat list
  }

  getTreeItem(node) {
    const raw = node.raw;
    const item = new vscode.TreeItem(raw.label, vscode.TreeItemCollapsibleState.None);
    item.description = raw.detail || '';
    item.contextValue = raw.rule ? 'rule' : 'shape';
    item.iconPath = icon(raw.rule ? 'symbol-event' : 'symbol-interface',
      raw.severity ? 'error' : '');
    item.tooltip = [raw.term || raw.label, raw.detail, raw.definedAt]
      .filter(Boolean).join('\n');
    return item;
  }

  async getChildren(node) {
    if (node) {
      return [];
    }
    const client = this.clientHolder.client;
    if (!client) {
      this.message('The language server is not running — run "SemForge: Doctor".');
      return [];
    }
    if (!this.uri) {
      this.message(noPackageMessage());
      return [];
    }
    let result;
    try {
      result = await client.sendRequest('semforge/shapes',
        { uri: this.uri, detail: treeDetail() });
    } catch (error) {
      this.message(`SemForge: ${error.message || error}`);
      return [];
    }
    if (result.error) {
      this.message(`SemForge: ${result.error}`);
      return [];
    }
    const roots = result.roots || [];
    this.message(roots.length ? undefined : 'This package declares no shapes.');
    return roots.map((raw) => new ShapeNode(raw, this.uri));
  }
}

function register(context, clientHolder, session) {
  const provider = new ShapesTreeProvider(clientHolder);
  const view = vscode.window.createTreeView('semforgeShapes', {
    treeDataProvider: provider
  });
  provider.view = view;
  context.subscriptions.push(view);

  context.subscriptions.push(
    view.onDidChangeSelection(async (event) => {
      const selected = event.selection && event.selection[0];
      if (!selected) {
        return;
      }
      if (treeClick() === 'page') {
        await vscode.commands.executeCommand('semforge.openShapePage', selected,
          { preserveFocus: true });
      } else if (selected.raw.definedAt) {
        await showLocation(selected.raw.definedAt, false);
      }
    })
  );

  provider.refresh(session.uri);
  context.subscriptions.push(
    session.onDidChange((uri) => provider.setPackage(uri)),
    vscode.workspace.onDidSaveTextDocument(() => provider.refresh()),
    vscode.commands.registerCommand('semforge.refreshShapes', () => provider.refresh())
  );
  return provider;
}

module.exports = { register, ShapesTreeProvider };
