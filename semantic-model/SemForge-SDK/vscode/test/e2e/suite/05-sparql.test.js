// The SPARQL workbench in a real VS Code: its page script runs (it asks for
// the saved query's result by itself on load), Apply runs an edit over a
// case's data, Save writes shacl.ttl, + SPARQL constraint starts a new one.

const assert = require('assert');
const vscode = require('vscode');
const { PACKAGE_URI, semforge, until, answering, read } = require('./helpers');

const BASE = 'https://industryfusion.github.io/contexts/example/v0/base_shacl/';
const CUTTER = `${BASE}StateOnCutterShape`;
const OFF = 'test_StateOnCutterShape/bad/filter-off.jsonld';

/** Everything the extension posts into the page, recorded. */
function recording(bench) {
  const posted = [];
  const post = bench.post.bind(bench);
  bench.post = (message) => {
    posted.push(message);
    post(message);
  };
  return posted;
}

async function open(api, shape, options) {
  await vscode.commands.executeCommand('semforge.openSparqlBench',
    { raw: { shape }, packageUri: PACKAGE_URI }, options || {});
  try {
    return await until(() => api.pages.sparql.panel && api.pages.sparql.page &&
      api.pages.sparql.page.shape === shape && api.pages.sparql.page, 'the workbench');
  } catch (error) {
    const panel = api.pages.sparql.panel;
    throw new Error(`${error.message}; the panel shows: ${panel
      ? panel.webview.html.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').slice(0, 400)
      : '(no panel)'}`);
  }
}

describe('the SPARQL workbench', () => {
  it('opens on a query, and its page runs the saved query by itself', async () => {
    const api = await semforge();
    const posted = recording(api.pages.sparql);
    const page = await open(api, CUTTER);
    assert.strictEqual(api.pages.sparql.panel.title, 'StateOnCutterShape · SPARQL');
    assert.strictEqual(page.holder.kind, 'constraint');
    const result = await until(() => posted.find((m) => m.type === 'result'),
      'the page script to ask for a run (it runs on load)');
    assert.ok(result.result.ok, JSON.stringify(result.result));
    assert.deepStrictEqual(result.result.violating, [], 'Main conforms to the saved query');
  });

  it('Apply runs an edit over a case and compares it with the saved query', async () => {
    const api = await semforge();
    await open(api, CUTTER);
    await api.pages.sparql.receive({ command: 'source', source: OFF,
      query: api.pages.sparql.page.holder.query });
    await until(() => api.pages.sparql.page.source === OFF, 'the case as data');
    assert.deepStrictEqual(api.pages.sparql.page.focus, ['urn:plasmacutter:1']);
    const saved = api.pages.sparql.page.holder.query;
    const edited = saved.replace('?v2 != base:state_ON', '?v2 = base:state_ON');
    const result = await api.pages.sparql.receive({ command: 'run', query: edited });
    assert.ok(result.ok, JSON.stringify(result));
    assert.deepStrictEqual(result.violating, []);
    assert.deepStrictEqual(result.saved.violating, ['urn:plasmacutter:1'],
      'the filter is off in this case: the saved query fires');
  });

  it('Save writes the edit into shacl.ttl, and Cancel needs no server', async () => {
    const api = await semforge();
    await open(api, CUTTER);
    const saved = api.pages.sparql.page.holder.query;
    const edited = saved.replace('FILTER(', '# checked in the workbench\n        FILTER(');
    await api.pages.sparql.receive({ command: 'draft', query: edited, dirty: true });
    const done = await api.pages.sparql.receive({ command: 'save', query: edited });
    assert.ok(done.ok, JSON.stringify(done));
    assert.match(read('shacl.ttl'), /# checked in the workbench/);
    assert.strictEqual(api.pages.sparql.dirty, false);
    assert.strictEqual(api.pages.sparql.page.holder.query, edited, 'the new baseline');
  });

  it('+ SPARQL constraint writes one that fires on nothing and opens it', async () => {
    const api = await semforge();
    // The save test above edited by message, not in the page's text box, so
    // the page still reports its old text as unsaved: switching shape asks.
    const session = answering([{ kind: 'input', value: 'Workpiece checked in the workbench' },
      { kind: 'warning', button: 'Discard them' }]);
    try {
      await vscode.commands.executeCommand('semforge.addSparqlConstraint',
        { raw: { shape: `${BASE}WorkpieceShape`, label: 'WorkpieceShape' },
          packageUri: PACKAGE_URI });
    } finally {
      session.restore();
    }
    const page = await until(() => api.pages.sparql.page &&
      api.pages.sparql.page.shape === `${BASE}WorkpieceShape` && api.pages.sparql.page,
    'the workbench on the new constraint');
    assert.strictEqual(page.holder.message, 'Workpiece checked in the workbench');
    assert.match(read('shacl.ttl'), /Workpiece checked in the workbench/);
    const result = await api.pages.sparql.receive({ command: 'run', query: page.holder.query });
    assert.ok(result.ok && result.focusCount >= 1, JSON.stringify(result));
    assert.deepStrictEqual(result.violating, [], 'a skeleton fires on nothing');
  });
});
