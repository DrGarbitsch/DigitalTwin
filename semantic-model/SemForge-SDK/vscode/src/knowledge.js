/*
 * The knowledge, as a tree: the third ingredient beside shapes and examples.
 *
 * Entity types nest by rdfs:subClassOf; vocabulary classes list their members.
 * What makes it more than an outline of knowledge.ttl is the joins it shows --
 * which shape judges a class, how many examples instantiate it, which terms the
 * data actually uses -- and the two jumps that follow those joins: one to the
 * class in knowledge.ttl, one to the shape in shacl.ttl.
 */

const fs = require('fs');
const path = require('path');
const vscode = require('vscode');

const { showLocation } = require('./reveal');

class KnowledgeTreeNode {
  constructor(raw, packageUri) {
    this.raw = raw;
    this.packageUri = packageUri;
  }
}

class KnowledgeTreeProvider {
  constructor(clientHolder) {
    this.clientHolder = clientHolder;
    this._onDidChangeTreeData = new vscode.EventEmitter();
    this.onDidChangeTreeData = this._onDidChangeTreeData.event;
    this.nodes = new Map();
    this.parents = new Map();
  }

  refresh(uri) {
    if (uri) {
      this.uri = uri;
    }
    this._onDidChangeTreeData.fire();
  }

  wrap(raw) {
    if (!this.nodes.has(raw)) {
      this.nodes.set(raw, new KnowledgeTreeNode(raw, this.uri));
    }
    return this.nodes.get(raw);
  }

  getParent(node) {
    return this.parents.get(node.raw);
  }

  getTreeItem(node) {
    const raw = node.raw;
    const children = raw.children || [];
    const item = new vscode.TreeItem(
      raw.label || raw.kind,
      children.length
        ? // Groups open; a class with a long member list does not, or the
          // vocabularies bury the hierarchy.
          raw.kind === 'group'
          ? vscode.TreeItemCollapsibleState.Expanded
          : vscode.TreeItemCollapsibleState.Collapsed
        : vscode.TreeItemCollapsibleState.None
    );
    item.description = raw.detail || '';
    // Spelled out, because `when: viewItem == x` matches a string and a row
    // whose contextValue drifts from package.json silently loses its icons.
    item.contextValue =
      raw.kind === 'class'
        ? raw.shapeAt
          ? 'classWithShape'
          : 'class'
        : raw.kind;

    if (raw.kind === 'group') {
      item.iconPath = new vscode.ThemeIcon('library');
    } else if (raw.kind === 'class') {
      item.iconPath = new vscode.ThemeIcon(
        raw.severity ? 'warning' : 'symbol-class'
      );
    } else if (raw.kind === 'individual') {
      item.iconPath = new vscode.ThemeIcon(
        raw.severity ? 'warning' : 'symbol-enum-member'
      );
    } else if (raw.kind === 'instance') {
      item.iconPath = new vscode.ThemeIcon('symbol-object');
    } else {
      item.iconPath = new vscode.ThemeIcon('references');
    }

    const lines = (raw.messages || []).slice();
    if (raw.iri) {
      lines.push(raw.iri);
    }
    if (raw.shapeName) {
      lines.push(`judged by ${raw.shapeName}`);
    }
    if (lines.length) {
      item.tooltip = lines.join('\n');
    }
    return item;
  }

  async getChildren(node) {
    if (node) {
      return (node.raw.children || []).map((child) => {
        this.parents.set(child, node);
        return this.wrap(child);
      });
    }
    const client = this.clientHolder.client;
    if (!client || !this.uri) {
      return [];
    }
    const result = await client.sendRequest('semforge/knowledge', {
      uri: this.uri
    });
    if (result.error) {
      return [];
    }
    this.nodes = new Map();
    this.parents = new Map();
    return (result.roots || []).map((raw) => this.wrap(raw));
  }
}

function defaultUri() {
  const folders = vscode.workspace.workspaceFolders || [];
  for (const folder of folders) {
    const root = folder.uri.fsPath;
    for (const name of ['knowledge.ttl', 'shacl.ttl', 'model-instance.jsonld']) {
      const candidate = path.join(root, name);
      if (fs.existsSync(candidate)) {
        return vscode.Uri.file(candidate).toString();
      }
    }
  }
  return undefined;
}

function register(context, clientHolder, onShape) {
  const provider = new KnowledgeTreeProvider(clientHolder);
  const view = vscode.window.createTreeView('semforgeKnowledge', {
    treeDataProvider: provider
  });
  context.subscriptions.push(view);

  // Selecting a class moves knowledge.ttl to its declaration; selecting an
  // instance moves the .jsonld to the entity. Same rule as the other two views,
  // and as there the row also unfolds rather than toggling shut.
  context.subscriptions.push(
    view.onDidChangeSelection(async (event) => {
      const selected = event.selection && event.selection[0];
      if (!selected) {
        return;
      }
      if (selected.raw.definedAt) {
        await showLocation(selected.raw.definedAt, false);
      }
      if ((selected.raw.children || []).length) {
        try {
          await view.reveal(selected, { expand: true, select: false, focus: false });
        } catch (error) {
          // Gone after a refresh; nothing to reveal.
        }
      }
    })
  );

  provider.refresh(defaultUri());
  context.subscriptions.push(
    vscode.workspace.onDidSaveTextDocument(() => provider.refresh())
  );

  context.subscriptions.push(
    vscode.commands.registerCommand('semforge.refreshKnowledge', () =>
      provider.refresh()
    ),

    vscode.commands.registerCommand('semforge.showShapeForClass', async (node) => {
      const raw = node && node.raw;
      if (!raw) {
        return;
      }
      if (raw.shapeAt) {
        await showLocation(raw.shapeAt, true);
        if (onShape) {
          onShape(raw.shape);
        }
        return;
      }
      // No shape of its own. Saying which ancestor checks it is more useful
      // than an empty jump -- and the detail already says whether anything
      // does.
      vscode.window.showInformationMessage(
        `SemForge: no shape targets ${raw.label} directly. ` +
          (raw.detail && raw.detail.includes('inherited')
            ? 'It is checked by a shape further up the hierarchy.'
            : 'Nothing checks it.')
      );
    })
  );

  return provider;
}

module.exports = { register, KnowledgeTreeProvider };
