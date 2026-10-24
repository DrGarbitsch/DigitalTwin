/**
 * Render a case/model page payload to HTML, with a stub `vscode`, for a
 * browser to run: node render_casepage.js <vscode/src> <page.json> <out.html> [after.js]
 *
 * The page's own script needs acquireVsCodeApi, which only a webview has: a
 * stub is put in front of it. `after.js`, if given, runs once the page is up.
 */
const Module = require('module');
const fs = require('fs');
const path = require('path');

const original = Module._load;
Module._load = function (request, parent, isMain) {
  if (request === 'vscode') {
    return new Proxy({}, { get: () => new Proxy(function () {}, { get: () => () => ({}) }) });
  }
  return original(request, parent, isMain);
};

const { renderCasePage } = require(path.join(process.argv[2], 'casepage.js'));
const page = JSON.parse(fs.readFileSync(process.argv[3], 'utf-8'));
let html = renderCasePage(page, { nonce: 'n' });
const stub = '<script nonce="n">function acquireVsCodeApi() { return { postMessage() {}, ' +
  'getState() { return null; }, setState() {} }; }</script>';
html = html.replace('<script nonce="n">', stub + '<script nonce="n">');
if (process.argv[5]) {
  html = html.replace('</body>', '<script nonce="n">' + fs.readFileSync(process.argv[5], 'utf-8') +
    '</script></body>');
}
fs.writeFileSync(process.argv[4], html);
