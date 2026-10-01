/*
 * "SemForge: New attribute…" -- declare an attribute in the knowledge and,
 * in the same gesture, constrain it on its type's shape.
 *
 * The order is the model's own: an attribute has to be DECLARED before a shape
 * may name it, because a sh:path the ontology has never heard of is how a
 * constraint ends up checking nothing. Making that two trips through two views
 * was the friction; this is one flow that does both steps in that order.
 *
 * VS Code has no extension-owned top-level menu, so the flow is reachable from
 * everywhere an extension IS allowed to put it: the Command Palette, the
 * SemForge submenu (Explorer and editor right-click, the Project view title),
 * the status bar menu, and the + picker in the Constraints view.
 */

const vscode = require('vscode');

const { declareAttribute } = require('./model');
const { showLocation } = require('./reveal');

async function valueChoices(client, packageUri, path, parameter) {
  try {
    const result = await client.sendRequest('semforge/choices', {
      uri: packageUri, path, parameter, search: null
    });
    return result.choices || [];
  } catch (error) {
    return [];
  }
}

/**
 * What the value must be. Asked, not read: the knowledge says which KIND an
 * attribute is, and deliberately leaves what its value may be to the shapes.
 * Returns {datatype, valueClass}, or undefined when cancelled.
 */
async function pickValue(client, packageUri, option) {
  const anything = { label: 'Any value', detail: 'constrain only that a value is there', value: {} };
  let items;
  if (option.kind === 'Relationship') {
    const entities = await valueChoices(
      client, packageUri, [option.term, 'ngsild:hasObject'], 'sh:class');
    items = [{ ...anything, label: 'Any entity' }].concat(entities.map((c) => ({
      label: c.label, description: c.value, detail: c.detail,
      value: { valueClass: c.value }
    })));
  } else if (option.kind === 'Property') {
    const [datatypes, classes] = await Promise.all([
      valueChoices(client, packageUri, [option.term, 'ngsild:hasValue'], 'sh:datatype'),
      valueChoices(client, packageUri, [option.term, 'ngsild:hasValue'], 'sh:class')
    ]);
    items = [anything,
      { label: 'A literal', kind: vscode.QuickPickItemKind.Separator }]
      .concat(datatypes.map((c) => ({
        label: c.label, description: 'datatype', value: { datatype: c.value }
      })))
      .concat([{ label: 'A vocabulary term', kind: vscode.QuickPickItemKind.Separator }])
      .concat(classes.map((c) => ({
        label: c.label, description: c.value, detail: c.detail,
        value: { valueClass: c.value }
      })));
  } else {
    return {};      // a JSON, list or geo payload has no class or datatype to ask
  }
  const picked = await vscode.window.showQuickPick(items, {
    title: `${option.label}: what must its value be?`,
    matchOnDescription: true,
    matchOnDetail: true
  });
  return picked ? picked.value : undefined;
}

const OPTIONAL = { label: 'Optional', description: 'sh:minCount 0',
  detail: 'checked when present, fine when absent', required: false };
const REQUIRED = { label: 'Required', description: 'sh:minCount 1',
  detail: 'every entity of this type must carry it', required: true };
const NOT_NOW = { label: 'Not now', description: 'declared only',
  detail: 'no shape names it yet — add it later with the + on the shape',
  skip: true };

/**
 * Constrain one declared attribute on a shape: presence, value, write.
 *
 * `target` is {shape} for a tree row, or {entityType} when the flow started
 * from a type -- the server then picks that type's OWN shape. With `optional`
 * set the first question also offers to stop at the declaration.
 * Returns the server's result, or undefined when cancelled or declined.
 */
async function constrainAttribute(client, packageUri, option, target, optional) {
  const presence = await vscode.window.showQuickPick(
    optional ? [OPTIONAL, REQUIRED, NOT_NOW] : [OPTIONAL, REQUIRED],
    { title: `${option.label} on ${target.label}` });
  if (!presence || presence.skip) {
    return undefined;
  }
  const value = await pickValue(client, packageUri, option);
  if (value === undefined) {
    return undefined;
  }
  const result = await client.sendRequest('semforge/addAttributeConstraint', {
    uri: packageUri,
    shape: target.shape || null,
    entityType: target.entityType || null,
    attribute: option.iri || option.term,
    required: presence.required,
    datatype: value.datatype || null,
    valueClass: value.valueClass || null
  });
  if (!result.ok) {
    vscode.window.showErrorMessage(`SemForge: ${result.error}`);
    return undefined;
  }
  vscode.window.setStatusBarMessage(
    `SemForge: ${option.label} added to ${target.label}`, 5000);
  if (result.line) {
    await showLocation(`${result.file}:${result.line}`, false);
  }
  return result;
}

/** The entity type the new attribute belongs to, picked from the knowledge. */
async function pickEntityType(client, packageUri) {
  let answer;
  try {
    answer = await client.sendRequest('semforge/entityTypes', { uri: packageUri });
  } catch (error) {
    answer = { error: error.message || String(error) };
  }
  if (!answer || answer.error) {
    vscode.window.showErrorMessage(
      `SemForge: ${(answer && answer.error) || 'the entity types could not be read'}`);
    return undefined;
  }
  const items = (answer.types || []).map((type) => ({
    label: type.label,
    description: type.term,
    detail: [type.parent ? `under ${type.parent}` : 'the root',
             type.ownShape ? 'has its own shape' : 'no shape of its own yet']
      .join(' · '),
    type
  }));
  const picked = await vscode.window.showQuickPick(items, {
    title: 'New attribute — which entity type carries it?',
    placeHolder: 'it is inherited by every type below the one you pick',
    matchOnDescription: true
  });
  return picked ? picked.type : undefined;
}

/**
 * The whole flow. `preset` may already name the type ({entityType, shape,
 * label}) -- the Constraints view's + knows which shape it was clicked on.
 */
async function newAttribute(client, packageUri, preset) {
  if (!client) {
    vscode.window.showErrorMessage(
      'SemForge: the language server is not running — run "SemForge: Doctor".');
    return undefined;
  }
  if (!packageUri) {
    vscode.window.showWarningMessage(
      'SemForge: no package is open. Open a file in one, or run ' +
      '"SemForge: New project…".');
    return undefined;
  }
  let target = preset;
  if (!target) {
    const type = await pickEntityType(client, packageUri);
    if (!type) {
      return undefined;
    }
    target = { entityType: type.term, label: type.label,
               hasShape: Boolean(type.ownShape) };
  }

  const made = await declareAttribute(client, packageUri, target.entityType);
  if (!made) {
    return undefined;
  }
  if (!target.shape && !target.hasShape) {
    vscode.window.showInformationMessage(
      `SemForge: ${made.label} is declared. No shape targets ${target.label} ` +
        'itself yet, so nothing constrains it — that needs a shape first.');
    return made;
  }
  // From a shape's + the author has already said they want a constraint; from
  // anywhere else declaring alone is a legitimate place to stop.
  await constrainAttribute(client, packageUri, made, target, !target.shape);
  return made;
}

function register(context, clientHolder, session, refresh) {
  context.subscriptions.push(
    vscode.commands.registerCommand('semforge.newAttribute', async () => {
      const made = await newAttribute(clientHolder.client, session.uri);
      if (made && refresh) {
        refresh();
      }
    })
  );
}

module.exports = { register, newAttribute, constrainAttribute, pickValue };
