"""The SPARQL workbench page, driven through the extension with the harness,
on the payloads the real server builds (so page and server cannot drift).

Apply, Cancel and Save are the page's own buttons; what reaches the
extension is a message, and what it sends back -- a result, a save -- is
posted INTO the page rather than re-rendering it, so the editor keeps what
was typed.
"""

import json
import os
import shutil
import subprocess
from unittest import mock

import pytest

from semforge.cooked import sparqlbench as sb

HERE = os.path.dirname(os.path.abspath(__file__))
SDK = os.path.dirname(os.path.dirname(HERE))
DRIVE = os.path.join(SDK, 'tests', 'harness', 'drive.js')
SRC = os.path.join(SDK, 'vscode', 'src')
BASE = 'https://industryfusion.github.io/contexts/example/v0/base_shacl/'
CUTTER = BASE + 'StateOnCutterShape'
PACKAGE = 'file:///pkg/shacl.ttl'
OFF = 'test_StateOnCutterShape/bad/filter-off.jsonld'


@pytest.fixture(scope='module')
def page(corpus):
    return dict(sb.bench_page(corpus, CUTTER, 0, sb.MAIN), ok=True)


@pytest.fixture(scope='module')
def run(corpus, page):
    return sb.run_query(corpus, CUTTER, 0, sb.MAIN, page['holder']['query'])


def _drive(tmp_path, scenario, target='extension.js'):
    node = shutil.which('node')
    if node is None:
        pytest.skip('node is not installed')
    path = tmp_path / 'scenario.json'
    path.write_text(json.dumps(scenario))
    result = subprocess.run([node, DRIVE, str(tmp_path), os.path.join(SRC, target), str(path)],
                            capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stderr[-1500:]
    return json.loads(result.stdout.strip().splitlines()[-1])


def _render(tmp_path, page, draft=None):
    return _drive(tmp_path, {'mode': 'render', 'function': 'renderSparqlBench', 'payload': page,
                             'options': {'nonce': 'n1', 'draft': draft}}, 'sparqlpage.js')['html']


def _open(tmp_path, page, messages, **scenario):
    replies = {'semforge/sparqlBench': page, 'semforge/sparqlRun': {'ok': True}}
    replies.update(scenario.pop('replies', {}))
    return _drive(tmp_path, dict({
        'command': 'semforge.openSparqlBench',
        'node': {'raw': {'shape': CUTTER}, 'packageUri': PACKAGE},
        'webviewMessages': messages, 'replies': replies}, **scenario))


def _asked(seen, method):
    return [r['params'] for r in seen['requests'] if r['method'] == method]


# --- the page ---------------------------------------------------------------------------

def test_it_shows_the_query_the_data_and_the_three_buttons(tmp_path, page):
    html = _render(tmp_path, page)
    for text in ('id="query"', 'id="apply"', 'id="cancel"', 'id="save"', 'id="source"',
                 'Cutter running without running filter', 'severity: base:severityCritical',
                 'Instance data (Turtle)', 'urn:plasmacutter:1', '2 focus node(s)'):
        assert text in html, text
    # The query is handed to the page as data and put into the editor by its
    # script: markup would lose the query's leading newline.
    assert html.split('id="query"', 1)[1].split('</textarea>', 1)[0].endswith('>')
    state = json.loads(html.split('const state = ', 1)[1].split(';\n', 1)[0])
    assert state['draft'] == state['baseline'] == page['holder']['query']
    assert state['draft'].startswith('\n')
    assert "script-src 'nonce-n1'" in html
    assert html.count('<option') == len(page['sources'])


def test_the_page_script_parses(tmp_path, page):
    """The script is generated inside a template string, where `\\n` in a regex
    turns into a real line break -- a page whose script does not parse shows
    everything and does nothing. Checked here, not only in a real VS Code."""
    html = _render(tmp_path, page)
    script = html.split('<script nonce="n1">', 1)[1].split('</script>', 1)[0]
    path = tmp_path / 'page-script.js'
    path.write_text('function acquireVsCodeApi() {}\n' + script)
    node = shutil.which('node')
    checked = subprocess.run([node, '--check', str(path)], capture_output=True, text=True)
    assert checked.returncode == 0, checked.stderr[-800:]


def test_a_draft_is_shown_instead_of_the_saved_text(tmp_path, page):
    html = _render(tmp_path, page, draft='SELECT $this WHERE { $this ?p ?o }')
    state = json.loads(html.split('const state = ', 1)[1].split(';\n', 1)[0])
    assert state['draft'] == 'SELECT $this WHERE { $this ?p ?o }'
    # The saved text stays the baseline Cancel returns to.
    assert state['baseline'] == page['holder']['query']


def test_nothing_reaches_the_page_unescaped(tmp_path, page):
    hostile = json.loads(json.dumps(page))
    hostile['holder']['query'] = '</textarea><script>alert(1)</script>'
    hostile['holder']['message'] = '<img src=x onerror=alert(2)>'
    html = _render(tmp_path, hostile)
    assert '<script>alert' not in html and '<img src=x' not in html
    assert '</textarea><script>' not in html


# --- what the buttons do -----------------------------------------------------------------

def test_apply_runs_the_edited_text_and_posts_the_result_back(tmp_path, page, run):
    seen = _open(tmp_path, page, [{'command': 'run', 'query': 'SELECT $this WHERE {}'}],
                 replies={'semforge/sparqlRun': run})
    assert seen['errors'] == [], seen['errors']
    assert seen['webviews'][0]['title'] == 'StateOnCutterShape · SPARQL'
    assert _asked(seen, 'semforge/sparqlRun') == [{
        'uri': PACKAGE, 'shape': CUTTER, 'index': 0, 'source': '@main',
        'query': 'SELECT $this WHERE {}'}]
    posted = seen['webviews'][0]['posted']
    assert posted == [{'type': 'result', 'result': run}]
    assert len(seen['webviews'][0]['html']) == 1, 'a run never re-renders the editor away'


def test_save_writes_over_the_query_it_opened(tmp_path, page):
    edited = page['holder']['query'] + '\n'
    seen = _open(tmp_path, page, [{'command': 'draft', 'query': edited, 'dirty': True},
                                  {'command': 'save', 'query': edited}],
                 replies={'semforge/sparqlSave': {'ok': True, 'file': '/pkg/shacl.ttl',
                                                  'line': 187}})
    assert _asked(seen, 'semforge/sparqlSave') == [{
        'uri': PACKAGE, 'shape': CUTTER, 'index': 0, 'query': edited,
        'expected': page['holder']['query']}]
    assert seen['webviews'][0]['posted'][-1] == {
        'type': 'saved', 'query': edited, 'where': 'shacl.ttl:187'}
    assert any(e['command'] == 'semforge.refreshShapes' for e in seen['executed'])


def test_a_refused_save_says_why_and_keeps_the_edit(tmp_path, page):
    seen = _open(tmp_path, page, [{'command': 'save', 'query': 'x'}],
                 replies={'semforge/sparqlSave': {'ok': False, 'error': 'changed in the file'}})
    assert any('changed in the file' in e for e in seen['errors'])
    assert seen['webviews'][0]['posted'][-1] == {'type': 'error', 'text': 'not saved'}


def test_another_source_rerenders_with_the_draft_kept(tmp_path, page):
    seen = _open(tmp_path, page, [{'command': 'source', 'source': OFF,
                                   'query': 'SELECT $this WHERE { $this ?p ?o }'}])
    asked = _asked(seen, 'semforge/sparqlBench')
    assert [a['source'] for a in asked] == ['@main', OFF]
    html = seen['webviews'][0]['html'][-1]
    assert 'SELECT $this WHERE { $this ?p ?o }' in html.split('id="query"', 1)[1]


def test_switching_query_with_unsaved_edits_asks_first(tmp_path, page):
    two = dict(page, holders=page['holders'] + [dict(page['holder'], index=1, query='SELECT 2')])
    for answer, renders in ((None, 1), ('Discard them', 2)):
        scenario = {'replies': {'semforge/sparqlBench': two}}
        if answer:
            scenario['answer'] = answer
        seen = _open(tmp_path, two, [{'command': 'holder', 'index': 1, 'dirty': True}], **scenario)
        assert any('unsaved edits' in w for w in seen['warnings'])
        assert len(_asked(seen, 'semforge/sparqlBench')) == renders


# --- the way in ------------------------------------------------------------------------

def test_the_shape_page_opens_the_workbench_on_the_clicked_query(tmp_path, corpus):
    from semforge.cooked.shapepage import build_shape_page

    shape_page = dict(build_shape_page(corpus, CUTTER), ok=True)
    seen = _drive(tmp_path, {
        'command': 'semforge.openShapePage',
        'node': {'raw': {'shape': CUTTER}, 'packageUri': PACKAGE},
        'webviewMessages': [{'command': 'bench', 'row': 0}],
        'replies': {'semforge/shapePage': shape_page}})
    html = seen['webviews'][0]['html'][0]
    assert 'data-action="bench" data-row="0"' in html and 'data-action="addSparql"' in html
    opened = [e['args'] for e in seen['executed'] if e['command'] == 'semforge.openSparqlBench']
    assert opened[0][0]['raw']['shape'] == CUTTER
    assert opened[0][1] == {'query': shape_page['checks'][0]['query'], 'kind': 'constraint'}


def test_add_sparql_constraint_asks_the_message_and_opens_it(tmp_path, page):
    seen = _drive(tmp_path, {
        'command': 'semforge.addSparqlConstraint',
        'node': {'raw': {'shape': CUTTER, 'label': 'StateOnCutterShape'}, 'packageUri': PACKAGE},
        'inputs': ['Cutter too hot'],
        'replies': {'semforge/addSparqlConstraint': {'ok': True, 'file': '/pkg/shacl.ttl',
                                                     'index': 1, 'line': 210},
                    'semforge/sparqlBench': page}})
    assert _asked(seen, 'semforge/addSparqlConstraint') == [
        {'uri': PACKAGE, 'shape': CUTTER, 'message': 'Cutter too hot'}]
    assert _asked(seen, 'semforge/sparqlBench')[0]['index'] == 1
    assert any('fires on nothing yet' in m for m in seen['info'])


def test_the_type_page_s_rule_rows_open_it(tmp_path, corpus):
    from semforge.cooked.typepage import build_type_page

    type_page = dict(build_type_page(corpus, 'iffBaseEntities:Cutter'), ok=True)
    rule = next(r for r in type_page['rules'] if r['shape'] == CUTTER)
    seen = _drive(tmp_path, {
        'command': 'semforge.openTypePage',
        'node': {'raw': {'kind': 'type', 'targetClass': type_page['iri'], 'children': []},
                 'packageUri': PACKAGE},
        'webviewMessages': [{'command': 'bench', 'shape': rule['shape'], 'kind': rule['kind']}],
        'replies': {'semforge/typePage': type_page}})
    assert f'data-bench="{CUTTER}"' in seen['webviews'][0]['html'][0]
    opened = [e['args'] for e in seen['executed'] if e['command'] == 'semforge.openSparqlBench']
    assert opened == [[{'raw': {'shape': CUTTER}, 'packageUri': PACKAGE}, {'kind': 'constraint'}]]


# --- the server --------------------------------------------------------------------------

def test_the_server_answers_all_four(corpus_path, tmp_path):
    from semforge.editor import server

    copy = tmp_path / 'kms'
    shutil.copytree(corpus_path, copy, symlinks=False, ignore=shutil.ignore_patterns('.semforge'))
    uri = f'file://{copy}/shacl.ttl'
    ls = mock.MagicMock()
    with mock.patch.object(server, '_publish'):
        opened = server.sparql_bench_feature(ls, {'uri': uri, 'shape': CUTTER, 'source': OFF})
        assert opened['ok'] and opened['focus'] == ['urn:plasmacutter:1']
        ran = server.sparql_run_feature(ls, {'uri': uri, 'shape': CUTTER, 'index': 0,
                                             'source': OFF, 'query': opened['holder']['query']})
        assert ran['violating'] == ['urn:plasmacutter:1']
        saved = server.sparql_save_feature(ls, {
            'uri': uri, 'shape': CUTTER, 'index': 0,
            'query': opened['holder']['query'] + '\n', 'expected': opened['holder']['query']})
        assert saved['ok'], saved
        added = server.add_sparql_constraint_feature(ls, {'uri': uri, 'shape': CUTTER,
                                                          'message': 'second'})
        assert added['ok'] and added['index'] == 1
        refused = server.sparql_bench_feature(ls, {'uri': uri, 'shape': BASE + 'WorkpieceShape'})
        assert not refused['ok'] and 'no SPARQL query' in refused['error']


def test_a_parameter_the_client_left_out_is_missing_not_a_tuple_method():
    """pygls hands custom params over as a namedtuple: without this, an omitted
    `index` was tuple.index, and the workbench failed only in a real VS Code."""
    from collections import namedtuple

    from semforge.editor.server import _field

    Sent = namedtuple('Object', ['uri', 'shape'])
    assert _field(Sent('u', 's'), 'index') is None
    assert _field(Sent('u', 's'), 'count', 7) == 7
    assert _field(Sent('u', 's'), 'shape') == 's'
    WithIndex = namedtuple('Object', ['uri', 'index'])
    assert _field(WithIndex('u', 2), 'index') == 2


# --- Remove… ----------------------------------------------------------------------------

def _plan(page, asserts, last=True, others=0):
    return {'ok': True, 'holder': page['holder'], 'last': last, 'others': others,
            'asserts': [{'file': '/pkg/examples/x/expectations.yaml', 'case': case,
                         'resource': 'urn:plasmacutter:1'} for case in asserts]}


def _remove(tmp_path, page, plan, answer, dirty=False, after=None):
    replies = {'semforge/sparqlRemovalPlan': plan,
               'semforge/sparqlRemove': {'ok': True, 'file': '/pkg/shacl.ttl', 'line': 185,
                                         'asserts': 1 if answer and 'asserts' in answer else 0}}
    if after is not None:
        replies['semforge/sparqlBench'] = after
    scenario = {'replies': replies}
    if answer:
        scenario['answer'] = answer
    return _open(tmp_path, page, [{'command': 'remove', 'dirty': dirty}], **scenario)


def test_remove_says_which_cases_assert_it_and_can_take_them(tmp_path, page):
    seen = _remove(tmp_path, page, _plan(page, ['filter-off.jsonld']),
                   'Remove it and its asserts')
    warning = next(w for w in seen['warnings'] if w.startswith('Remove the SPARQL constraint'))
    assert '"Cutter running without running filter"' in warning
    assert 'filter-off.jsonld (on urn:plasmacutter:1)' in warning
    assert 'no other SPARQL constraint of this shape is left' in warning
    sent = _asked(seen, 'semforge/sparqlRemove')
    assert sent == [{'uri': PACKAGE, 'shape': CUTTER, 'query': page['holder']['query'],
                     'kind': 'constraint', 'expected': page['holder']['query'],
                     'dropAsserts': True}]
    assert any(e['command'] == 'semforge.refreshShapes' for e in seen['executed'])


def test_remove_it_only_keeps_the_asserts(tmp_path, page):
    seen = _remove(tmp_path, page, _plan(page, ['filter-off.jsonld']), 'Remove it only')
    assert _asked(seen, 'semforge/sparqlRemove')[0]['dropAsserts'] is False


def test_asserts_another_constraint_answers_for_are_only_mentioned(tmp_path, page):
    seen = _remove(tmp_path, page, _plan(page, ['filter-off.jsonld'], last=False, others=1),
                   'Remove')
    warning = next(w for w in seen['warnings'] if w.startswith('Remove the'))
    assert '1 other(s) remain, so the asserts are kept' in warning
    assert _asked(seen, 'semforge/sparqlRemove')[0]['dropAsserts'] is False


def test_unsaved_edits_are_mentioned_and_a_dismissal_removes_nothing(tmp_path, page):
    seen = _remove(tmp_path, page, _plan(page, []), None, dirty=True)
    assert any('unsaved edits in the workbench go with it' in w for w in seen['warnings'])
    assert _asked(seen, 'semforge/sparqlRemove') == []


def test_after_the_last_query_the_page_closes(tmp_path, page):
    gone = {'ok': False, 'error': 'iffBaseShacl:StateOnCutterShape has no SPARQL query'}
    seen = _remove(tmp_path, page, _plan(page, []), 'Remove', after=gone)
    assert len(seen['webviews'][0]['html']) == 1, 'not re-rendered into an error page'


def test_the_shape_page_s_remove_names_the_query_by_its_text(tmp_path, corpus):
    from semforge.cooked.shapepage import build_shape_page

    shape_page = dict(build_shape_page(corpus, CUTTER), ok=True)
    seen = _drive(tmp_path, {
        'command': 'semforge.openShapePage',
        'node': {'raw': {'shape': CUTTER}, 'packageUri': PACKAGE},
        'webviewMessages': [{'command': 'removeSparql', 'row': 0}],
        'replies': {'semforge/shapePage': shape_page}})
    assert 'data-action="removeSparql" data-row="0"' in seen['webviews'][0]['html'][0]
    asked = [e['args'] for e in seen['executed'] if e['command'] == 'semforge.removeSparqlQuery']
    check = shape_page['checks'][0]
    assert asked[0][1] == {'query': check['query'], 'kind': 'constraint',
                           'message': check['message']}


def test_the_server_finds_the_query_by_its_text(corpus_path, tmp_path):
    from semforge.editor import server
    from semforge.package import load

    copy = tmp_path / 'kms'
    shutil.copytree(corpus_path, copy, symlinks=False, ignore=shutil.ignore_patterns('.semforge'))
    uri = f'file://{copy}/shacl.ttl'
    query = sb.holders(load(str(copy)), CUTTER)[0]['query']
    with mock.patch.object(server, '_publish'):
        plan = server.sparql_removal_plan_feature(mock.MagicMock(), {
            'uri': uri, 'shape': CUTTER, 'query': query})
        assert plan['ok'] and plan['last'] and len(plan['asserts']) == 1
        done = server.sparql_remove_feature(mock.MagicMock(), {
            'uri': uri, 'shape': CUTTER, 'query': query, 'expected': query,
            'dropAsserts': True})
        assert done['ok'] and done['asserts'] == 1


# --- the selector, Inspect, snapshots ----------------------------------------------------------

def test_the_page_says_how_this_is_bound(tmp_path, page):
    html = _render(tmp_path, page)
    assert '<b>Selects</b>' in html
    assert '$this = each of every Cutter, and every subclass of it → 2 node(s)' in html
    assert 'Show as SPARQL — what the engine adds' in html
    assert 'VALUES $this { &lt;urn:plasmacutter:1&gt; &lt;urn:plasmacutter:2&gt; }' in html


def test_inspect_asks_with_the_text_as_it_is_and_posts_the_answer(tmp_path, page, corpus):
    inspected = sb.inspect(corpus, CUTTER, 0, sb.MAIN, page['holder']['query'])
    seen = _open(tmp_path, page, [{'command': 'inspect', 'query': 'SELECT $this WHERE {}'}],
                 replies={'semforge/sparqlInspect': inspected})
    assert _asked(seen, 'semforge/sparqlInspect') == [{
        'uri': PACKAGE, 'shape': CUTTER, 'index': 0, 'source': '@main',
        'query': 'SELECT $this WHERE {}'}]
    assert seen['webviews'][0]['posted'] == [{'type': 'inspect', 'result': inspected}]
    assert len(seen['webviews'][0]['html']) == 1, 'the editor is not re-rendered away'
    html = seen['webviews'][0]['html'][0]
    assert 'id="inspect"' in html and 'id="inspected"' in html


def _snap(tmp_path, page, messages, **scenario):
    ran = {'ok': True, 'kind': 'constraint', 'violating': ['urn:plasmacutter:1']}
    return _open(tmp_path, page, messages, replies={'semforge/sparqlRun': ran}, **scenario)


def test_a_snapshot_keeps_the_text_with_what_it_did(tmp_path, page):
    seen = _snap(tmp_path, page, [{'command': 'snapshot', 'query': 'SELECT 1'}],
                 inputs=['works on filter-off'])
    assert seen['inputs'][0]['title'] == 'Snapshot'
    assert 'closing VS Code forgets it' in seen['inputs'][0]['prompt']
    (posted,) = seen['webviews'][0]['posted']
    (entry,) = posted['list']
    assert posted['type'] == 'snapshots'
    assert entry['name'] == 'works on filter-off' and entry['query'] == 'SELECT 1'
    assert entry['verdict'] == '1 violating on Main'


def test_snapshots_outlive_a_rerender_and_can_be_deleted(tmp_path, page):
    seen = _snap(tmp_path, page, [{'command': 'snapshot', 'query': 'SELECT 1'},
                                  {'command': 'snapshot', 'query': 'SELECT 2'},
                                  {'command': 'source', 'source': OFF, 'query': 'SELECT 2'},
                                  {'command': 'deleteSnapshot', 'id': 1}],
                 inputs=['first', 'second'])
    html = seen['webviews'][0]['html'][-1]
    state = json.loads(html.split('const state = ', 1)[1].split(';\n', 1)[0])
    assert [s['name'] for s in state['snapshots']] == ['first', 'second'], 'kept across data'
    assert [s['name'] for s in seen['webviews'][0]['posted'][-1]['list']] == ['second']


def test_a_dismissed_name_takes_no_snapshot(tmp_path, page):
    seen = _snap(tmp_path, page, [{'command': 'snapshot', 'query': 'SELECT 1'}])
    assert seen['webviews'][0]['posted'] == [] and _asked(seen, 'semforge/sparqlRun') == []


def test_nothing_of_the_workbench_is_stored_anywhere():
    """Agreed: only Save persists. Snapshots and drafts live in memory and go
    with VS Code."""
    source = open(os.path.join(SRC, 'sparqlpage.js')).read()
    for storage in ('workspaceState', 'globalState', 'storageUri', 'writeFile', 'setState('):
        assert storage not in source, storage
