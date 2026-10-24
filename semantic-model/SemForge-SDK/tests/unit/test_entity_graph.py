"""The entity views of the model and case pages: the card filter and the graph.

The page script runs in a browser, so the checks that need one run in headless
Chromium when it is there (Playwright's, or SEMFORGE_CHROME) and are skipped
otherwise. What the page is drawn from -- the entities and their
relationships -- is checked everywhere.
"""

import glob
import json
import os
import re
import shutil
import subprocess

import pytest

SDK = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
SRC = os.path.join(SDK, 'vscode', 'src')
RENDER = os.path.join(SDK, 'tests', 'harness', 'render_casepage.js')


def _row(name, kind='Property', value='1', children=()):
    return {'name': name, 'term': 'ex:' + name, 'kind': kind, 'value': value, 'dataset': '',
            'unitCode': '', 'observedAt': '', 'stamp': {}, 'latestAt': '', 'superseded': False,
            'instances': 1, 'line': 1, 'violations': [], 'children': list(children),
            'display': name}


def _card(id_, type_, rows):
    return {'id': id_, 'type': type_, 'file': '/pkg/model.jsonld', 'line': 1,
            'violations': [], 'attributes': rows}


# A -> B -> A (a cycle), A -> C through a sub-attribute, B -> a target not here.
PAGE = {
    'kind': 'model', 'name': 'Main', 'case': '', 'expect': '', 'group': '', 'suite': '',
    'description': '', 'passed': True, 'failures': [], 'claims': [], 'unasserted': [],
    'residuePinned': False, 'file': '/pkg/model.jsonld', 'expectations': '',
    'verdicts': {'state': 'ready'},
    'summary': {'entities': 3, 'violations': 0, 'includes': 0},
    'files': [{'role': 'model', 'path': '/pkg/model.jsonld', 'relative': 'model.jsonld',
               'sharedBy': [], 'cards': [
                   _card('urn:a', 'ex:Pump', [
                       _row('hasPort', 'Relationship', 'urn:b'),
                       _row('hasState', children=[_row('hasDriver', 'Relationship', 'urn:c')])]),
                   _card('urn:b', 'ex:Port', [
                       _row('hasOwner', 'Relationship', 'urn:a'),
                       _row('hasElsewhere', 'Relationship', 'urn:gone')]),
                   _card('urn:c', 'ex:Drive', [_row('hasSpeed')])]}],
}


def _node():
    node = shutil.which('node')
    if node is None:
        pytest.skip('node is not installed')
    return node


def _render(tmp_path, after=None):
    page = tmp_path / 'page.json'
    page.write_text(json.dumps(PAGE))
    out = tmp_path / 'page.html'
    args = [_node(), RENDER, SRC, str(page), str(out)]
    if after:
        script = tmp_path / 'after.js'
        script.write_text(after)
        args.append(str(script))
    run = subprocess.run(args, capture_output=True, text=True, timeout=60)
    assert run.returncode == 0, run.stderr[-1500:]
    return out


def test_the_page_carries_its_entities_and_their_relationships(tmp_path):
    html = _render(tmp_path).read_text()
    data = re.search(r'<script type="application/json" id="entities">(.*?)</script>', html, re.S)
    entities = {e['id']: e for e in json.loads(data.group(1))}
    assert entities['urn:a']['rels'] == [{'name': 'hasPort', 'target': 'urn:b'},
                                         {'name': 'hasState.hasDriver', 'target': 'urn:c'}]
    assert entities['urn:a']['attrs'] == ['hasPort', 'hasState']
    assert 'data-type="ex:Port"' in html and 'data-id="urn:b"' in html
    assert 'data-view="graph"' in html and '<details class="filter" id="filter">' in html


def _chrome():
    candidates = [os.environ.get('SEMFORGE_CHROME', '')] + sorted(glob.glob(os.path.expanduser(
        '~/.cache/ms-playwright/chromium-*/chrome-linux*/chrome')))
    found = next((c for c in candidates if c and os.path.exists(c)), None)
    if found is None:
        pytest.skip('no headless Chromium (set SEMFORGE_CHROME)')
    return found


def _dom(tmp_path, after):
    out = _render(tmp_path, after)
    run = subprocess.run([_chrome(), '--headless=new', '--no-sandbox', '--disable-gpu',
                          '--virtual-time-budget=3000', '--dump-dom', 'file://' + str(out)],
                         capture_output=True, text=True, timeout=120)
    return run.stdout


OPEN_ALL = '''
document.querySelector('[data-view=graph]').click();
function openAll() {
  document.querySelectorAll('#graph details.gnode').forEach(function (d) { d.open = true; });
}
openAll(); setTimeout(openAll, 50); setTimeout(openAll, 100); setTimeout(openAll, 150);
'''


def test_the_graph_starts_where_nothing_points_and_ends_a_cycle_with_a_jump(tmp_path):
    dom = _dom(tmp_path, OPEN_ALL)
    graph = dom[dom.index('id="graph"'):dom.index('id="cardview"')]
    # urn:a and urn:b point at each other, urn:a at urn:c: everything is pointed
    # at, so the cycle is entered at its first entity -- one root, not three.
    assert '0 root(s): the entities nothing points at · 1 more where a cycle has no way in' \
        in graph
    assert graph.index('data-id="urn:a"') < graph.index('data-id="urn:b"')
    # urn:b points back at urn:a, which is open above: a jump, not another urn:a.
    assert 'data-jump="urn:a"' in graph
    assert graph.count('data-id="urn:a"') == 1
    assert 'urn:gone (not in this page)' in graph
    assert 'hasState.hasDriver →' in graph


def test_a_filter_hides_the_cards_and_roots_the_graph(tmp_path):
    dom = _dom(tmp_path, '''
var t = document.getElementById('ftype'); t.value = 'ex:Port'; t.dispatchEvent(new Event('change'));
''')
    cards = re.findall(r'<div class="card[^"]*"[^>]*data-id="([^"]+)"[^>]*?( hidden="")?>', dom)
    assert {card for card, hidden in cards if not hidden} == {'urn:b'}
    assert '1 of 3 shown' in dom

    graph = _dom(tmp_path, '''
var t = document.getElementById('ftype'); t.value = 'ex:Port'; t.dispatchEvent(new Event('change'));
document.querySelector('[data-view=graph]').click();
''')
    assert '1 matching entity as roots' in graph
