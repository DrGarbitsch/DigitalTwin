/*
 * Finding the package in the opened folder.
 *
 * Each tree used to carry its own copy of this, looking only for the three
 * artifacts directly inside a workspace folder root. Open `semantic-model/`
 * rather than `semantic-model/kms/` and that finds nothing, so the trees
 * started empty and waited for an editor to be opened — which the Constraints
 * and Examples trees then did silently, and the Knowledge tree never did at
 * all, because it had no editor tracking.
 *
 * So: look in the folder, then one level down, and say what was looked for when
 * nothing turns up.
 */

const fs = require('fs');
const path = require('path');
const vscode = require('vscode');

const ARTIFACTS = ['shacl.ttl', 'knowledge.ttl', 'model-instance.jsonld'];

/** True when this directory holds all three artifacts. */
function isPackage(directory) {
  return ARTIFACTS.every((name) => fs.existsSync(path.join(directory, name)));
}

function firstArtifact(directory) {
  for (const name of ARTIFACTS) {
    const candidate = path.join(directory, name);
    if (fs.existsSync(candidate)) {
      return vscode.Uri.file(candidate).toString();
    }
  }
  return undefined;
}

/**
 * A URI inside a package in the opened folders, or undefined.
 *
 * The URI is a file rather than the directory because that is what the server
 * resolves a package from: it walks up from a file, which is what an editor
 * hands you.
 */
function findPackageUri() {
  const folders = vscode.workspace.workspaceFolders || [];
  const roots = [];
  for (const folder of folders) {
    roots.push(folder.uri.fsPath);
  }
  // The folder itself wins over anything beneath it.
  for (const root of roots) {
    if (isPackage(root)) {
      return firstArtifact(root);
    }
  }
  for (const root of roots) {
    let names = [];
    try {
      names = fs.readdirSync(root, { withFileTypes: true })
        .filter((entry) => entry.isDirectory() && !entry.name.startsWith('.'))
        .map((entry) => entry.name)
        .sort();
    } catch (error) {
      continue;                       // unreadable folder; nothing to find
    }
    for (const name of names) {
      const candidate = path.join(root, name);
      if (isPackage(candidate)) {
        return firstArtifact(candidate);
      }
    }
  }
  return undefined;
}

/** What to tell someone whose tree is empty. */
function noPackageMessage() {
  const folders = (vscode.workspace.workspaceFolders || [])
    .map((folder) => folder.uri.fsPath)
    .join(', ');
  return (
    'No SemForge package found in ' + (folders || 'this window') +
    ' or one level below it. A package is a directory holding ' +
    ARTIFACTS.join(', ') + '. Open one, or run "SemForge: Doctor".'
  );
}

module.exports = { ARTIFACTS, isPackage, findPackageUri, noPackageMessage };
