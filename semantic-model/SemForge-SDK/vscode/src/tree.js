/*
 * The cooked view: a TreeDataProvider over the SDK's constraint tree.
 *
 * It renders what `semforge/tree` returns and sends edits back through
 * `semforge/setConstraint`. It computes nothing itself -- the tree, which
 * parameters are editable, and what an edit does to the file are all decided in
 * the SDK, so the tree and the CLI cannot disagree about what a shape says.
 */

const vscode = require('vscode');

// Values that are an enumeration rather than free text. Offering a picker for
// these is the whole ergonomic difference between a form and a text box.
const CHOICES = {
  'sh:nodeKind': ['sh:IRI', 'sh:BlankNode', 'sh:Literal',
                  'sh:BlankNodeOrIRI', 'sh:IRIOrLiteral'],
  'sh:datatype': ['xsd:string', 'xsd:integer', 'xsd:double', 'xsd:decimal',
                  'xsd:boolean', 'xsd:dateTime', 'xsd:anyURI']
};

class ConstraintNode {
  constructor(raw, packageUri) {
    this.raw = raw;
    this.packageUri = packageUri;
  }

  get children() {
    return (this.raw.children || []).map(
      (child) => new ConstraintNode(child, this.packageUri)
    );
  }
}

class CookedTreeProvider {
  constructor(clientHolder) {
    this.clientHolder = clientHolder;
    this._onDidChangeTreeData = new vscode.EventEmitter();
    this.onDidChangeTreeData = this._onDidChangeTreeData.event;
    this.uri = undefined;
  }

  refresh(uri) {
    if (uri) {
      this.uri = uri;
    }
    this._onDidChangeTreeData.fire();
  }

  getTreeItem(node) {
    const raw = node.raw;
    const hasChildren = (raw.children || []).length > 0;
    const item = new vscode.TreeItem(
      raw.label,
      hasChildren
        ? vscode.TreeItemCollapsibleState.Collapsed
        : vscode.TreeItemCollapsibleState.None
    );
    item.description = raw.detail || raw.value || '';
    item.contextValue = raw.editable ? 'editable' : raw.kind;

    if (raw.kind === 'type') {
      item.iconPath = new vscode.ThemeIcon('symbol-class');
    } else if (raw.kind === 'shape') {
      item.iconPath = new vscode.ThemeIcon('symbol-interface');
    } else if (raw.kind === 'attribute') {
      item.iconPath = new vscode.ThemeIcon('symbol-field');
    } else if (raw.kind === 'slot') {
      item.iconPath = new vscode.ThemeIcon('symbol-property');
    } else if (raw.editable) {
      item.iconPath = new vscode.ThemeIcon('edit');
      item.tooltip = `${raw.parameter} = ${raw.value}\nClick to change.`;
      item.command = {
        command: 'semforge.editConstraint',
        title: 'Edit',
        arguments: [node]
      };
    } else {
      // Shown, not offered. A tree that hid what it cannot edit would be
      // lying about what the shape contains.
      item.iconPath = new vscode.ThemeIcon('lock-small');
      item.tooltip = raw.detail || 'raw only — edit in the .ttl file';
    }
    return item;
  }

  async getChildren(node) {
    if (node) {
      return node.children;
    }
    const client = this.clientHolder.client;
    if (!client || !this.uri) {
      return [];
    }
    const result = await client.sendRequest('semforge/tree', { uri: this.uri });
    if (result.error) {
      this.lastError = result.error;
      return [];
    }
    this.lastError = undefined;
    return (result.roots || []).map(
      (raw) => new ConstraintNode(raw, this.uri)
    );
  }
}

/** Ask for the new value, using a picker where the value is an enumeration. */
async function promptForValue(raw) {
  const choices = CHOICES[raw.parameter];
  if (choices) {
    return vscode.window.showQuickPick(choices, {
      title: `${raw.parameter} (currently ${raw.value})`,
      placeHolder: 'pick a value'
    });
  }
  return vscode.window.showInputBox({
    title: `${raw.parameter}`,
    prompt: `New value for ${raw.parameter}`,
    value: raw.value,
    validateInput: (text) =>
      text.trim().length ? undefined : 'a value is required'
  });
}

function register(context, clientHolder) {
  const provider = new CookedTreeProvider(clientHolder);
  const view = vscode.window.createTreeView('semforgeConstraints', {
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
    vscode.commands.registerCommand('semforge.editConstraint', async (node) => {
      const raw = node && node.raw;
      if (!raw || !raw.editable) {
        return;
      }
      const value = await promptForValue(raw);
      if (value === undefined) {
        return;
      }
      const result = await clientHolder.client.sendRequest(
        'semforge/setConstraint',
        {
          uri: node.packageUri,
          shape: raw.shape,
          path: raw.path,
          parameter: raw.parameter,
          value
        }
      );
      if (result.ok) {
        vscode.window.setStatusBarMessage(
          `SemForge: ${raw.parameter} = ${value} (${result.bytesChanged} byte(s) changed)`,
          4000
        );
        provider.refresh();
      } else {
        vscode.window.showErrorMessage(`SemForge: ${result.error}`);
      }
    }),

    vscode.commands.registerCommand('semforge.removeConstraint', async (node) => {
      const raw = node && node.raw;
      if (!raw || !raw.editable) {
        return;
      }
      const confirm = await vscode.window.showWarningMessage(
        `Remove ${raw.parameter} from ${raw.path[raw.path.length - 1]}?`,
        { modal: true },
        'Remove'
      );
      if (confirm !== 'Remove') {
        return;
      }
      const result = await clientHolder.client.sendRequest(
        'semforge/setConstraint',
        {
          uri: node.packageUri,
          shape: raw.shape,
          path: raw.path,
          parameter: raw.parameter,
          remove: true
        }
      );
      if (result.ok) {
        provider.refresh();
      } else {
        vscode.window.showErrorMessage(`SemForge: ${result.error}`);
      }
    }),

    vscode.commands.registerCommand('semforge.refreshTree', () =>
      provider.refresh()
    )
  );

  return provider;
}

module.exports = { register, CookedTreeProvider, CHOICES };
