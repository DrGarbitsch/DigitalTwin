"""The test case page: claims, outcome, and the data as entity cards.

The payload is checked against the corpus cases -- it must agree with
`semforge test` about whether a case passes, attach every violation to the
attribute it is about (a missing sub-attribute to its parent), and keep values
intact. The renderer and the command are driven through the Node harness.
"""

import json
import os
import shutil
import subprocess

import pytest

from semforge.cooked.casepage import build_case_page
from semforge.errors import PackageError

HERE = os.path.dirname(os.path.abspath(__file__))
SDK = os.path.dirname(os.path.dirname(HERE))
DRIVE = os.path.join(SDK, 'tests', 'harness', 'drive.js')
SRC = os.path.join(SDK, 'vscode', 'src')
WITHOUT = 'test_FilterShape/bad/without-cartridge.jsonld'
SHARED = 'test_CartridgeShape/bad/shared-by-two-filters.jsonld'


@pytest.fixture(scope='module')
def without(corpus):
    return build_case_page(corpus, WITHOUT)


@pytest.fixture(scope='module')
def shared(corpus):
    return build_case_page(corpus, SHARED)


def _cards(page):
    return {card['id']: card for file in page['files'] for card in file['cards']}


def _rows(card):
    return {row['name']: row for row in card['attributes']}


# --- claims and outcome ------------------------------------------------------------

def test_the_claim_holds_and_the_case_passes(without):
    assert without['expect'] == 'invalid' and without['passed']
    assert without['failures'] == []
    claim = without['claims'][0]
    assert claim['holds'] and claim['resource'] == 'urn:filter:9'
    assert claim['explained']['text'] == 'hasCartridge is required but missing'


def test_what_fired_unasserted_is_listed_separately(without):
    assert [u['constraint'] for u in without['unasserted']] == [
        'iffBaseShacl:MachineShape/hasXXXWorkpiece/MinCountConstraintComponent']


def test_the_page_agrees_with_semforge_test(corpus):
    from semforge.cli.main import _examples_and_reports
    from semforge.expect import run_tests
    from semforge.expect.store import load_expectations
    from semforge.sanity import known_constraints

    outcomes = {o.example: o.passed for o in run_tests(
        _examples_and_reports(corpus, load_expectations(corpus.path)),
        known_constraints(corpus))}
    for case, passed in outcomes.items():
        assert build_case_page(corpus, case)['passed'] == passed, case


def test_an_undeclared_case_is_refused(corpus):
    with pytest.raises(PackageError, match='not a declared test case'):
        build_case_page(corpus, 'test_Nothing/bad/nope.jsonld')


# --- the data ------------------------------------------------------------------------

def test_a_missing_attribute_lands_on_the_entity(without):
    card = _cards(without)['urn:filter:9']
    assert [v['text'] for v in card['violations']] == ['hasCartridge is required but missing']


def test_a_missing_sub_attribute_lands_on_its_parent(without):
    rows = _rows(_cards(without)['urn:filter:9'])
    assert [v['text'] for v in rows['hasState']['violations']] == [
        'hasXXXWorkpiece is required but missing']
    assert rows['hasState']['violations'][0]['shape'] == 'MachineShape'
    assert rows['hasState']['violations'][0]['detail'], 'the raw message stays as the tooltip'


def test_includes_are_their_own_sections_with_who_shares_them(shared):
    roles = [(f['role'], f['relative']) for f in shared['files']]
    assert roles[0] == ('case', SHARED)
    assert ('include', 'subobjects/cartridge-fresh.jsonld') in roles
    cartridge = next(f for f in shared['files'] if f['relative'].endswith('cartridge-fresh.jsonld'))
    assert len(cartridge['sharedBy']) == 2


def test_values_are_kept_whole(shared):
    rows = _rows(_cards(shared)['urn:cartridge:1'])
    assert rows['isUsedFrom']['value'] == '2024-02-27T13:54:55.400Z', 'a timestamp has colons'
    assert rows['hasWasteclass']['value'] == 'WC1', 'a prefixed name loses its prefix'
    assert _rows(_cards(shared)['urn:filter:1'])['hasCartridge']['value'] == 'urn:cartridge:1'


def test_rows_point_at_their_lines(shared):
    card = _cards(shared)['urn:filter:8']
    with open(card['file'], encoding='utf-8') as handle:
        lines = handle.read().split('\n')
    assert 'urn:filter:8' in lines[card['line'] - 1] or 'urn:filter:8' in lines[card['line']]
    row = _rows(card)['hasStrength']
    assert 'hasStrength' in lines[row['line'] - 1]


# --- the renderer and the command ------------------------------------------------------

def _node(tmp_path, scenario, target):
    node = shutil.which('node')
    if node is None:
        pytest.skip('node is not installed')
    path = tmp_path / 'scenario.json'
    path.write_text(json.dumps(scenario))
    out = subprocess.run([node, DRIVE, str(tmp_path), os.path.join(SRC, target), str(path)],
                         capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr[-1500:]
    return json.loads(out.stdout.strip().splitlines()[-1])


def _render(tmp_path, page):
    return _node(tmp_path, {'mode': 'render', 'function': 'renderCasePage',
                            'payload': page, 'options': {'nonce': 'n1'}},
                 'casepage.js')['html']


def test_the_page_shows_claims_and_cards(tmp_path, without):
    html = _render(tmp_path, without)
    for text in ('expects invalid', 'passes', 'holds', 'also fired',
                 'hasCartridge is required but missing',
                 'hasXXXWorkpiece is required but missing', 'urn:filter:9'):
        assert text in html, text
    assert "script-src 'nonce-n1'" in html


def test_nothing_reaches_the_page_unescaped(tmp_path, without):
    hostile = json.loads(json.dumps(without))
    hostile['description'] = '<script>alert(1)</script>'
    hostile['files'][0]['cards'][0]['attributes'][0]['value'] = '"><img src=x onerror=alert(2)>'
    html = _render(tmp_path, hostile)
    assert '<script>alert' not in html and '<img src=x' not in html


def test_a_case_row_opens_its_page_and_a_type_link_opens_the_type_page(tmp_path, without):
    seen = _node(tmp_path, {
        'command': 'semforge.openCasePage',
        'node': {'raw': {'kind': 'example', 'label': 'without-cartridge.jsonld',
                         'file': without['file'], 'children': []},
                 'packageUri': 'file:///pkg/shacl.ttl'},
        'webviewMessages': [{'command': 'type', 'name': 'Filter'},
                            {'command': 'open', 'at': f"{without['file']}:2"}],
        'replies': {'semforge/casePage': dict(without, ok=True)}}, 'extension.js')
    assert seen['errors'] == [], seen['errors']
    asked = [r['params'] for r in seen['requests'] if r['method'] == 'semforge/casePage']
    assert asked[0]['case'] == without['file']
    assert seen['webviews'][0]['title'] == '⚑ without-cartridge.jsonld'
    typed = [e for e in seen['executed'] if e['command'] == 'semforge.openTypePage']
    assert typed[0]['args'][0]['raw']['targetClass'] == 'Filter'
    assert seen['shown'][0]['file'] == without['file']


def test_the_case_row_carries_its_file(corpus):
    from semforge.cooked.examples import build_suite

    def walk(nodes):
        for node in nodes:
            yield node
            yield from walk(node.children)

    from semforge.expect.store import load_expectations

    declared = {os.path.basename(e.path) for e in load_expectations(corpus.path).examples}
    rows = [n for n in walk(build_suite(corpus)) if n.kind == 'example']
    cases = [n for n in rows if n.label in declared]
    assert len(cases) == len(declared)
    assert all(os.path.isfile(n.file) for n in cases)
    # The model scratchpad shares the row kind but is not a case: no case file.
    assert all(not n.file for n in rows if n.label not in declared)


def test_the_model_row_says_it_is_not_a_case(tmp_path):
    seen = _node(tmp_path, {
        'command': 'semforge.openCasePage',
        'node': {'raw': {'kind': 'example', 'label': 'model-instance.jsonld',
                         'file': '', 'children': []},
                 'packageUri': 'file:///pkg/shacl.ttl'},
        'replies': {}}, 'extension.js')
    assert seen['requests'] == [] and seen['webviews'] == []
    assert any('not a test case' in m for m in seen['info'])
