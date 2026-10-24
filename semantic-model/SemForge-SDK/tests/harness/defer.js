/**
 * The pages' refresh deferral, driven directly: results that arrive while an
 * edit is open wait for it. Prints one JSON line of what happened.
 *
 *   node defer.js <vscode/src directory>
 */
const Module = require('module');
const path = require('path');

const original = Module._load;
Module._load = function (request, parent, isMain) {
  if (request === 'vscode') {
    return new Proxy({}, { get: () => new Proxy(function () {}, { get: () => () => ({}) }) });
  }
  return original(request, parent, isMain);
};

const src = process.argv[2];
const out = {};

async function check(name, Pages) {
  const pages = new Pages({ client: undefined }, undefined);
  let renders = 0;
  pages.render = async () => { renders += 1; pages.editing = false; };
  pages.panel = { visible: true };
  pages.page = { verdicts: { state: 'evaluating' } };

  // 1. An edit of the extension's (a picker) is under way: the refresh waits.
  let finish;
  pages.handle = () => new Promise((resolve) => { finish = resolve; });
  const editing = pages.receive({ command: 'presence' });
  pages.verdictsArrived();
  const duringPicker = renders;
  finish();
  await editing;
  const afterPicker = renders;

  // 2. The page's own editor is open: the refresh waits until it closes.
  pages.page = { verdicts: { state: 'evaluating' } };
  await pages.receive({ command: 'editing', open: true });
  pages.verdictsArrived();
  const duringEditor = renders;
  await pages.receive({ command: 'editing', open: false });
  const afterEditor = renders;

  // 3. Nothing open: at once. 4. A page already final is not redrawn.
  pages.page = { verdicts: { state: 'evaluating' } };
  pages.verdictsArrived();
  const idle = renders;
  pages.page = { verdicts: { state: 'ready' } };
  pages.verdictsArrived();
  out[name] = { duringPicker, afterPicker, duringEditor, afterEditor, idle, final: renders };
}

(async () => {
  await check('type', require(path.join(src, 'typepage.js')).TypePages);
  await check('shape', require(path.join(src, 'shapepage.js')).ShapePages);
  await check('case', require(path.join(src, 'casepage.js')).CasePages);
  console.log(JSON.stringify(out));
})().catch((error) => { console.error(error); process.exit(1); });
