"""The first click: what it needs is done before it, and it is never blank.

On the OPC UA pump package the first class click took 2.2 s with the package
already loaded -- the text index of 12.8 MB of ontology -- and paid the package
load (2.6 s) too when the views came from their cache. Now the index is kept
per file content, the editor warms the package as soon as anything asks about
it, and a page that is still waiting says so instead of staying blank.
"""

import json
import os
import shutil
import subprocess
import time

import pytest

from semforge.rdfio import turtle_index
from semforge.rdfio.derived import cache_dir
from semforge.rdfio.turtle_index import index_file

SDK = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
DRIVE = os.path.join(SDK, 'tests', 'harness', 'drive.js')
SRC = os.path.join(SDK, 'vscode', 'src')

TURTLE = '@prefix ex: <https://example.org/> .\n' + ''.join(
    f'ex:S{n} a ex:Thing ;\n    ex:p "{n}" .\n\n' for n in range(30))


@pytest.fixture
def ttl(tmp_path):
    path = tmp_path / 'pkg' / 'k.ttl'
    path.parent.mkdir()
    path.write_text(TURTLE)
    turtle_index._PARSED.clear()
    return path


def _blocks(index):
    return [(b.subject, b.raw_subject, b.start, b.end, b.start_line, b.end_line)
            for b in index.blocks]


def test_the_index_is_kept_and_read_back_the_same(ttl, monkeypatch):
    root = str(ttl.parent)
    cold = index_file(str(ttl), root)
    assert os.listdir(cache_dir(root, 'index'))

    turtle_index._PARSED.clear()

    def no_parse(source):
        raise AssertionError('indexed again although kept')

    monkeypatch.setattr(turtle_index, '_parse', no_parse)
    warm = index_file(str(ttl), root)
    assert _blocks(warm) == _blocks(cold)
    line = TURTLE[:TURTLE.index('ex:S7 ')].count('\n') + 1
    assert warm.block_for('https://example.org/S7').start_line == line


def test_an_edit_indexes_again_and_keeps_one_version(ttl):
    root = str(ttl.parent)
    index_file(str(ttl), root)
    ttl.write_text(TURTLE.replace('ex:S7 ', 'ex:T7 '))
    turtle_index._PARSED.clear()
    assert index_file(str(ttl), root).block_for('https://example.org/T7') is not None
    entries = [n for n in os.listdir(cache_dir(root, 'index')) if n.endswith('.json')]
    assert len(entries) == 1


def test_without_a_package_nothing_is_kept(ttl):
    index_file(str(ttl))
    assert not os.path.exists(cache_dir(str(ttl.parent), 'index'))


def test_the_package_is_warmed_when_anything_asks(tmp_path, corpus_path):
    from semforge.editor import server

    root = str(tmp_path / 'pkg')
    shutil.copytree(corpus_path, root, ignore=shutil.ignore_patterns('.semforge'))
    server._warm(root)
    deadline = time.time() + 120
    while time.time() < deadline:
        package = server._packages.get(root)
        if package is not None and hasattr(package, '_index_knowledge') \
                and hasattr(package, '_index_shapes'):
            break
        time.sleep(0.1)
    else:
        pytest.fail('the package was not warmed')
    assert os.listdir(cache_dir(root, 'index'))
    server._service().wait(root, timeout=120)
    assert server._service().get(root)[1].state == 'ready'

    before = server._packages[root]
    server._warm(root)                              # once per version
    assert server._packages[root] is before


def _open(tmp_path, page):
    node = shutil.which('node')
    if node is None:
        pytest.skip('node is not installed')
    scenario = tmp_path / 'scenario.json'
    scenario.write_text(json.dumps({
        'command': 'semforge.openTypePage',
        'node': {'raw': {'kind': 'type', 'targetClass': 'https://example.org/Pump',
                         'children': []},
                 'packageUri': 'file:///pkg/shacl.ttl'},
        'replies': {'semforge/typePage': page}}))
    out = subprocess.run([node, DRIVE, str(tmp_path), os.path.join(SRC, 'extension.js'),
                          str(scenario)], capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr[-1500:]
    return json.loads(out.stdout.strip().splitlines()[-1])


PAGE = {'ok': True, 'iri': 'https://example.org/Pump', 'label': 'Pump', 'term': 'ex:Pump',
        'crumbs': [], 'subtypes': [], 'ownShapes': [], 'ownShape': '', 'ownShapeName': '',
        'shapeAt': '', 'attributes': [], 'rules': [], 'alsoCheckedBy': [],
        'exercisedBy': [], 'instances': [],
        'summary': {'cases': 0, 'casesFailing': 0, 'instances': 0,
                    'instancesViolating': None, 'neverFired': 0},
        'verdicts': {'state': 'evaluating', 'stale': False, 'error': '', 'seconds': 0}}


def test_a_slow_page_says_it_is_loading(tmp_path):
    seen = _open(tmp_path, {'__delay': 600, 'reply': PAGE})
    html = seen['webviews'][0]['html']
    assert 'Loading Pump' in html[0]
    assert 'evaluating' in html[-1] and 'Loading' not in html[-1]


def test_a_quick_page_does_not_flicker(tmp_path):
    seen = _open(tmp_path, PAGE)
    assert not any('Loading' in h for h in seen['webviews'][0]['html'])
