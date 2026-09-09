/*
 * Moving the editor to a node's location.
 *
 * Shared by both trees so selection behaves the same in each: the Examples tree
 * had no such wiring at all, which is why selecting an entity moved nothing.
 */

const vscode = require('vscode');

/** `file:line` -> { file, line }, tolerating a Windows drive letter. */
function splitLocation(at) {
  const split = (at || '').lastIndexOf(':');
  if (split < 0) {
    return undefined;
  }
  const line = parseInt(at.slice(split + 1), 10);
  if (Number.isNaN(line)) {
    return undefined;
  }
  return { file: at.slice(0, split), line: Math.max(line - 1, 0) };
}

/** Put the cursor on a file:line. Keeps focus in the tree unless asked. */
async function showLocation(at, focus) {
  const where = splitLocation(at);
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

module.exports = { splitLocation, showLocation };
