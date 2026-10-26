/**
* Copyright (c) 2026 IndustryFusion Foundation
*
* Licensed under the Apache License, Version 2.0 (the "License");
* you may not use this file except in compliance with the License.
* You may obtain a copy of the License at
*
*    http://www.apache.org/licenses/LICENSE-2.0
*
* Unless required by applicable law or agreed to in writing, software
* distributed under the License is distributed on an "AS IS" BASIS,
* WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
* See the License for the specific language governing permissions and
* limitations under the License.
*/

// Validation in the background: after an edit a page answers at once, and
// the verdicts follow when the worker has them -- here, a maximum lowered
// below what Main's workpiece says makes it violate, and raising it back
// clears that. And the Main page's tools for many entities: the filter, the
// graph, the type link that opens THAT type.

const assert = require('assert');
const vscode = require('vscode');
const { semforge, until, request } = require('./helpers');

const ENT = 'https://industryfusion.github.io/contexts/example/v0/base_entities/';

async function workpiecePage(api) {
  const page = await request(api, 'semforge/typePage', { entityType: `${ENT}Workpiece` });
  assert.ok(page.ok, page.error);
  return page;
}

function width(page) {
  return page.attributes.find((a) => a.label === 'hasWidth');
}

async function setMaximum(api, value) {
  const row = width(await workpiecePage(api));
  const done = await request(api, 'semforge/editValueForms', { shape: row.shape, path: row.path,
    action: { op: 'set', form: 0, node: [0], parameter: 'sh:maxInclusive', value } });
  assert.ok(done.ok, done.error);
}

describe('Validation in the background', () => {
  it('a page answers at once after an edit, and the verdicts follow', async () => {
    const api = await semforge();
    const before = await until(async () => {
      const page = await workpiecePage(api);
      return page.verdicts.state === 'ready' && page;
    }, 'the first verdicts');
    // What violates hasWidth already -- an earlier suite adds a workpiece
    // without one -- stays the baseline: the edit adds the one at 100.
    const already = width(before).violations.slice().sort();

    await setMaximum(api, '50');
    const started = Date.now();
    const asked = await workpiecePage(api);
    const seconds = (Date.now() - started) / 1000;
    assert.ok(seconds < 5, `the page took ${seconds}s: it waited for the validation`);
    assert.ok(['ready', 'evaluating'].includes(asked.verdicts.state), JSON.stringify(asked.verdicts));
    assert.match(width(asked).value, /50/, 'the structure is new at once');

    const judged = await until(async () => {
      const page = await workpiecePage(api);
      return page.verdicts.state === 'ready' &&
        width(page).violations.some((id) => !already.includes(id)) && page;
    }, 'the verdicts: Main’s workpiece at 100 now violates hasWidth');
    assert.ok(width(judged).violations.some((id) => /workpiece/i.test(id) && !already.includes(id)),
      width(judged).violations);

    await setMaximum(api, '100');
    await until(async () => {
      const page = await workpiecePage(api);
      return page.verdicts.state === 'ready' &&
        JSON.stringify(width(page).violations.slice().sort()) === JSON.stringify(already);
    }, 'the violation to clear');
  });
});

describe('The Main page with many entities', () => {
  it('offers Cards and Graph, and a filter by type, attribute and id from the data', async () => {
    const api = await semforge();
    await vscode.commands.executeCommand('semforge.openModelPage');
    const page = await until(() => api.pages.case.page && api.pages.case.page.kind === 'model' &&
      api.pages.case.page, 'the Main page');
    const html = api.pages.case.panel.webview.html;
    assert.ok(html.includes('data-view="cards"') && html.includes('data-view="graph"'));
    const cards = page.files.flatMap((f) => f.cards);
    for (const type of new Set(cards.map((c) => c.type).filter(Boolean))) {
      assert.ok(html.includes(`<option value="${type}">`), `the filter offers ${type}`);
    }
    // What the graph is drawn from: every entity, its type and its relationships.
    const index = JSON.parse(html.split('<script type="application/json" id="entities">')[1]
      .split('</script>')[0].replace(/\\u003c/g, '<'));
    assert.deepStrictEqual(index.map((e) => e.id).sort(), cards.map((c) => c.id || '').sort());
    const drawn = index.flatMap((e) => e.rels.map((r) => `${e.id} ${r.name} ${r.target}`));
    const said = cards.flatMap((c) => (c.attributes || [])
      .filter((a) => a.kind === 'Relationship' && a.value && !a.superseded)
      .map((a) => `${c.id || ''} ${a.name} ${a.value}`));
    assert.ok(said.length, 'Main has relationships');
    for (const edge of said) {
      assert.ok(drawn.includes(edge), `the graph draws ${edge}`);
    }
  });

  it('a type link opens that type’s page, a card does not', async () => {
    const api = await semforge();
    const html = api.pages.case.panel.webview.html;
    // The regression: the whole card carried data-type, so a click anywhere on
    // it -- on a relationship to another type too -- opened the card's type.
    assert.ok(!/class="card[^"]*"[^>]*data-type=/.test(html), 'a card carries no data-type');
    assert.ok(/class="card[^"]*"[^>]*data-ftype=/.test(html), 'the filter reads data-ftype');
    const card = api.pages.case.page.files.flatMap((f) => f.cards).find((c) => c.type);
    await api.pages.case.receive({ command: 'type', name: card.type });
    await until(() => api.pages.type.panel &&
      api.pages.type.panel.title === `Entity type: ${card.type.split(':').pop()}`, 'its type page');
    await vscode.commands.executeCommand('workbench.action.closeAllEditors');
  });
});
