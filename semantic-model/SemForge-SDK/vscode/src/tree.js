/*
 * The cooked view: a TreeDataProvider over the SDK's constraint tree.
 *
 * It renders what `semforge/tree` returns and sends edits back through
 * `semforge/setConstraint`. It computes nothing itself -- the tree, which
 * parameters are editable, and what an edit does to the file are all decided in
 * the SDK, so the tree and the CLI cannot disagree about what a shape says.
 */

const fs = require('fs');
const path = require('path');
const vscode = require('vscode');

// Candidate values come from the server, never from a list in here. Which
// classes may be offered is an ontology question -- entity types on one side of
// the NGSI-LD encoding, vocabulary classes on the other -- and a list hard-coded
// in JavaScript would drift from the model the moment somebody adds a class.
const CUSTOM = Symbol('custom');

class ConstraintNode {
  constructor(raw, packageUri) {
    this.raw = raw;
    this.packageUri = packageUri;
  }
}

/** file:line -> { file, line }, tolerating a Windows drive letter. */
function splitLocation(at) {
  const split = at.lastIndexOf(':');
  if (split < 0) {
    return undefined;
  }
  const line = parseInt(at.slice(split + 1), 10);
  if (Number.isNaN(line)) {
    return undefined;
  }
  return { file: at.slice(0, split), line: Math.max(line - 1, 0) };
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

  /**
   * Index the whole tree in one pass.
   *
   * The server returns every node in a single reply, so the wrappers can be
   * built once and kept. That identity is what TreeView.reveal needs: a fresh
   * wrapper per getChildren call would make every element unrecognisable to
   * the view, and reveal a no-op.
   */
  _index(roots) {
    this.nodes = new Map();
    this.parents = new Map();
    this.owners = new Map();

    const walk = (raw, parentRaw, owner) => {
      this.nodes.set(raw, new ConstraintNode(raw, this.uri));
      this.parents.set(raw, parentRaw);
      this.owners.set(raw, owner);
      (raw.children || []).forEach((child) => walk(child, raw, owner));
    };

    roots.forEach((root) => {
      const owner = {
        label: root.label,
        // The type's OWN shape -- an override is added there, never to the
        // inherited shape the constraint came from.
        shape: (root.children.find((c) => !c.inheritedFrom) || {}).shape
      };
      walk(root, null, owner);
    });
    this.rawRoots = roots;
  }

  wrap(raw) {
    return raw ? this.nodes.get(raw) : undefined;
  }

  getParent(node) {
    return this.wrap(this.parents.get(node.raw));
  }

  /** The non-inherited node declaring the same thing, if the tree has one. */
  findCanonical(raw) {
    for (const candidate of this.nodes.keys()) {
      if (
        !candidate.inheritedFrom &&
        candidate.shape === raw.shape &&
        candidate.parameter === (raw.parameter || '') &&
        JSON.stringify(candidate.path) === JSON.stringify(raw.path || [])
      ) {
        return this.nodes.get(candidate);
      }
    }
    return undefined;
  }

  /**
   * The type node a tree node sits under.
   *
   * An override is added to the shape of the type being VIEWED, not the shape
   * the constraint came from -- that is the whole point of pulling it down.
   */
  ownerOf(node) {
    return this.owners ? this.owners.get(node.raw) : undefined;
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
    item.contextValue = raw.inheritedFrom
      ? 'inherited'
      : raw.editable
      ? 'editable'
      : raw.kind;

    if (raw.kind === 'type') {
      item.iconPath = new vscode.ThemeIcon('symbol-class');
    } else if (raw.kind === 'shape') {
      item.iconPath = new vscode.ThemeIcon('symbol-interface');
    } else if (raw.kind === 'attribute') {
      item.iconPath = new vscode.ThemeIcon('symbol-field');
    } else if (raw.kind === 'slot') {
      item.iconPath = new vscode.ThemeIcon('symbol-property');
    } else if (raw.inheritedFrom) {
      // Shown because it APPLIES here: sh:targetClass reaches subclasses, so a
      // shape on Machine validates every Filter. Not editable in place --
      // SHACL conjoins, so a constraint added on the subtype is evaluated
      // alongside this one rather than instead of it.
      item.iconPath = new vscode.ThemeIcon('type-hierarchy-super');
      item.tooltip =
        `Inherited from ${raw.inheritedClass.split('/').pop()}\n` +
        `Declared at ${raw.definedAt}\n\n` +
        'Right-click to jump there, or to declare it on this type.';
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
      return (node.raw.children || []).map((child) => this.wrap(child));
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
    this._index(result.roots || []);
    return this.rawRoots.map((raw) => this.wrap(raw));
  }
}

function freeText(raw) {
  return vscode.window.showInputBox({
    title: raw.parameter,
    prompt: `New value for ${raw.parameter}`,
    value: raw.value,
    validateInput: (text) =>
      text.trim().length ? undefined : 'a value is required'
  });
}

function toItems(choices) {
  const items = choices.map((choice) => ({
    label: choice.label,
    description: choice.value,
    detail: choice.detail,
    value: choice.value
  }));
  items.push({
    label: '$(edit) Enter a different value…',
    description: '',
    detail: 'anything valid in the shapes file',
    value: CUSTOM
  });
  return items;
}

async function fetchChoices(client, node, search) {
  try {
    const result = await client.sendRequest('semforge/choices', {
      uri: node.packageUri,
      path: node.raw.path,
      parameter: node.raw.parameter,
      search: search || null
    });
    return {
      choices: result.choices || [],
      note: result.note || '',
      total: result.total || 0
    };
  } catch (error) {
    return { choices: [], note: `suggestions unavailable: ${error.message}`, total: 0 };
  }
}

/**
 * Ask for the new value, offering what the model allows.
 *
 * When the candidate set fits, VS Code filters it locally as you type. When it
 * does not -- the server caps what it sends -- typing goes back to the server
 * instead, so an ontology of any size stays navigable rather than arriving as a
 * truncated list with no way to reach the rest.
 *
 * Either way the picker keeps a way out to a typed value. The suggestions are a
 * convenience, not a restriction: a list that cannot be escaped would make the
 * cooked view less capable than the file it edits.
 */
async function promptForValue(client, node) {
  const raw = node.raw;
  const first = await fetchChoices(client, node, '');

  if (!first.choices.length) {
    if (first.note) {
      vscode.window.setStatusBarMessage(`SemForge: ${first.note}`, 5000);
    }
    return freeText(raw);
  }

  const truncated = first.total > first.choices.length;
  if (!truncated) {
    const picked = await vscode.window.showQuickPick(toItems(first.choices), {
      title: `${raw.parameter} (currently ${raw.value})`,
      placeHolder: first.note || 'pick a value, or enter your own',
      matchOnDescription: true,
      matchOnDetail: true
    });
    if (!picked) {
      return undefined;
    }
    return picked.value === CUSTOM ? freeText(raw) : picked.value;
  }

  return new Promise((resolve) => {
    const quickPick = vscode.window.createQuickPick();
    quickPick.title = `${raw.parameter} (currently ${raw.value})`;
    quickPick.placeholder = first.note || 'type to search';
    quickPick.matchOnDescription = true;
    quickPick.matchOnDetail = true;
    // The server has already ranked and filtered; re-filtering locally would
    // hide entries it deliberately included.
    quickPick.items = toItems(first.choices);

    let pending;
    let generation = 0;
    quickPick.onDidChangeValue((text) => {
      clearTimeout(pending);
      const mine = ++generation;
      pending = setTimeout(async () => {
        quickPick.busy = true;
        const next = await fetchChoices(client, node, text);
        if (mine === generation) {
          quickPick.items = toItems(next.choices);
          quickPick.placeholder = next.note || 'pick a value, or enter your own';
        }
        quickPick.busy = false;
      }, 150);
    });

    let accepted = false;
    quickPick.onDidAccept(async () => {
      const picked = quickPick.selectedItems[0];
      accepted = true;
      quickPick.hide();
      if (!picked) {
        resolve(undefined);
      } else {
        resolve(picked.value === CUSTOM ? await freeText(raw) : picked.value);
      }
    });
    quickPick.onDidHide(() => {
      quickPick.dispose();
      if (!accepted) {
        resolve(undefined);
      }
    });
    quickPick.show();
  });
}

/** Put the cursor on a file:line, without stealing focus from the tree. */
async function showLocation(at, focus) {
  const where = splitLocation(at || '');
  if (!where) {
    return;
  }
  const document = await vscode.workspace.openTextDocument(where.file);
  const editor = await vscode.window.showTextDocument(document, {
    preserveFocus: !focus,
    preview: true
  });
  const position = new vscode.Position(where.line, 0);
  editor.selection = new vscode.Selection(position, position);
  editor.revealRange(
    new vscode.Range(position, position),
    vscode.TextEditorRevealType.InCenter
  );
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

function register(context, clientHolder) {
  const provider = new CookedTreeProvider(clientHolder);
  const view = vscode.window.createTreeView('semforgeConstraints', {
    treeDataProvider: provider
  });
  context.subscriptions.push(view);
  if (!defaultUri() && !vscode.window.activeTextEditor) {
    view.message =
      'Open a folder holding knowledge.ttl, shacl.ttl and ' +
      'model-instance.jsonld — or run "SemForge: Doctor".';
  }

  // Selecting anything moves the .ttl to it. Every node carries its own
  // file:line -- an attribute, a single parameter, not just the shape -- so
  // this lands on the line you picked rather than the top of the block.
  context.subscriptions.push(
    view.onDidChangeSelection(async (event) => {
      const selected = event.selection && event.selection[0];
      if (selected && selected.raw.definedAt) {
        await showLocation(selected.raw.definedAt, false);
      }
    })
  );

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
    vscode.commands.registerCommand('semforge.editConstraint', async (node) => {
      const raw = node && node.raw;
      if (!raw || !raw.editable) {
        return;
      }
      const value = await promptForValue(clientHolder.client, node);
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
    ),

    vscode.commands.registerCommand('semforge.goToDefinition', async (node) => {
      const raw = node && node.raw;
      if (!raw) {
        return;
      }
      // Navigate BOTH views. The tree is where the reader is looking, so
      // jumping only the editor leaves them to find the declaring shape by
      // hand -- which is the work this command exists to remove.
      const canonical = provider.findCanonical(raw);
      if (canonical) {
        try {
          await view.reveal(canonical, {
            select: true,
            focus: true,
            expand: 3
          });
        } catch (error) {
          // reveal can refuse for a node the view has not realised yet; the
          // editor jump below still happens.
        }
      }
      await showLocation(raw.definedAt, true);
    }),

    vscode.commands.registerCommand('semforge.overrideHere', async (node) => {
      const raw = node && node.raw;
      if (!raw || !raw.inheritedFrom || !raw.parameter) {
        vscode.window.showInformationMessage(
          'SemForge: pick an inherited constraint to declare on this type.'
        );
        return;
      }
      // The type node this constraint is being pulled down onto.
      const owner = provider.ownerOf(node);
      if (!owner) {
        vscode.window.showErrorMessage(
          'SemForge: could not tell which shape to add it to.'
        );
        return;
      }

      const value = await vscode.window.showInputBox({
        title: `${raw.parameter} on ${owner.label}`,
        prompt:
          `Inherited value is ${raw.value}. SHACL conjoins, so this can only ` +
          'make the constraint stricter.',
        value: raw.value
      });
      if (value === undefined) {
        return;
      }

      const send = (force) =>
        clientHolder.client.sendRequest('semforge/override', {
          uri: node.packageUri,
          targetShape: owner.shape,
          path: raw.path,
          parameter: raw.parameter,
          inheritedValue: raw.value,
          value,
          force
        });

      let result = await send(false);
      if (!result.ok && (result.effect === 'weaker' || result.effect === 'same')) {
        const choice = await vscode.window.showWarningMessage(
          `${raw.parameter} ${raw.value} → ${value} is ${result.effect}. ` +
            result.error,
          { modal: true },
          'Open the inherited shape',
          'Add it anyway'
        );
        if (choice === 'Open the inherited shape') {
          return vscode.commands.executeCommand('semforge.goToDefinition', node);
        }
        if (choice !== 'Add it anyway') {
          return;
        }
        result = await send(true);
      }

      if (result.ok) {
        vscode.window.setStatusBarMessage(
          `SemForge: ${raw.parameter} declared on ${owner.label} (${result.effect})`,
          5000
        );
        provider.refresh();
      } else {
        vscode.window.showErrorMessage(`SemForge: ${result.error}`);
      }
    })
  );

  return provider;
}

module.exports = { register, CookedTreeProvider };
