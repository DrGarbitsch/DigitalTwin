"""The server driven over real stdio.

Every other editor test calls the analysis layer directly, which is what keeps
that layer honest. This one is the opposite check: that the wiring actually
speaks LSP, so "the extension works" is verified rather than assumed. It is the
only test here that starts a process.
"""

import json
import os
import subprocess
import sys
import threading
import time

import pytest

SDK = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
INTERPRETER = os.path.join(SDK, 'venv', 'bin', 'python')


def _framed(message):
    body = json.dumps(message).encode()
    return b'Content-Length: %d\r\n\r\n' % len(body) + body


class Session:
    def __init__(self, document):
        self.messages = []
        # NOT cwd=SDK. The server is launched by an editor with the folder the
        # USER opened as its working directory, and running it from the SDK
        # directory hid a real failure: `semforge` was importable only because
        # the package happened to sit in the current directory, so the server
        # died instantly for every actual user while this test passed.
        self.process = subprocess.Popen(
            [INTERPRETER if os.path.exists(INTERPRETER) else sys.executable,
             '-m', 'semforge.editor.server'],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, cwd=os.path.dirname(SDK))
        threading.Thread(target=self._read, daemon=True).start()
        self.document = document

    def send(self, message):
        self.process.stdin.write(_framed(message))
        self.process.stdin.flush()

    def _read(self):
        stream = self.process.stdout
        while True:
            header = b''
            while b'\r\n\r\n' not in header:
                byte = stream.read(1)
                if not byte:
                    return
                header += byte
            length = int(next(line for line in header.decode().split('\r\n')
                              if 'Content-Length' in line).split(':')[1])
            self.messages.append(json.loads(stream.read(length)))

    def wait_for(self, predicate, seconds=45):
        deadline = time.time() + seconds
        while time.time() < deadline:
            found = [m for m in self.messages if predicate(m)]
            if found:
                return found
            time.sleep(0.2)
        return []

    def close(self):
        self.process.terminate()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()


@pytest.fixture(scope='module')
def session(request):
    document = os.path.join(SDK, 'tests', 'corpus', 'kms', 'shacl.ttl')
    session = Session(document)
    request.addfinalizer(session.close)

    session.send({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize',
                  'params': {'processId': os.getpid(),
                             'rootUri': 'file://' + SDK, 'capabilities': {}}})
    assert session.wait_for(lambda m: m.get('id') == 1), 'server did not initialize'
    session.send({'jsonrpc': '2.0', 'method': 'initialized', 'params': {}})
    with open(document) as handle:
        text = handle.read()
    session.send({'jsonrpc': '2.0', 'method': 'textDocument/didOpen',
                  'params': {'textDocument': {
                      'uri': 'file://' + document, 'languageId': 'turtle',
                      'version': 1, 'text': text}}})
    return session


def test_the_server_advertises_what_the_extension_relies_on(session):
    reply = [m for m in session.messages if m.get('id') == 1][0]
    capabilities = reply['result']['capabilities']
    for capability in ('hoverProvider', 'definitionProvider',
                       'documentSymbolProvider', 'textDocumentSync'):
        assert capabilities.get(capability), f'{capability} not advertised'


def test_opening_a_shapes_file_publishes_diagnostics(session):
    published = session.wait_for(
        lambda m: m.get('method') == 'textDocument/publishDiagnostics')
    assert published, 'no diagnostics arrived'
    diagnostics = published[0]['params']['diagnostics']
    assert diagnostics
    assert all(d['range']['start']['line'] >= 0 for d in diagnostics)


def test_the_server_starts_from_a_directory_that_is_not_the_sdk(session):
    """The regression guard for the failure this test used to hide.

    An editor starts the server wherever the user's folder is. If `semforge` is
    not installed, the process exits before saying anything -- and a language
    server that exits immediately is indistinguishable from one that found
    nothing to report.
    """
    assert session.process.poll() is None, (
        'the server exited: '
        + session.process.stderr.read().decode()[-400:])


def test_the_diagnostics_carry_the_semforge_source_and_a_kind(session):
    published = session.wait_for(
        lambda m: m.get('method') == 'textDocument/publishDiagnostics')
    sources = {d['source'] for d in published[0]['params']['diagnostics']}
    assert sources
    assert all(s.startswith('semforge (') for s in sources)
    assert any('unexercised' in s for s in sources), \
        'the dead-shape warning should reach the editor'


def test_the_cooked_tree_arrives_over_the_protocol(session):
    """semforge/tree is what the VS Code TreeView renders."""
    session.send({'jsonrpc': '2.0', 'id': 10, 'method': 'semforge/tree',
                  'params': {'uri': 'file://' + session.document}})
    replies = session.wait_for(lambda m: m.get('id') == 10)
    assert replies, 'no reply to semforge/tree'
    result = replies[0]['result']
    assert not result.get('error'), result.get('error')

    labels = {root['label'] for root in result['roots']}
    assert {'Filter', 'Cutter'} <= labels

    def walk(nodes):
        for node in nodes:
            yield node
            yield from walk(node['children'])

    editable = [n for n in walk(result['roots']) if n['editable']]
    assert editable, 'nothing is editable, so the tree is read-only'
    for node in editable:
        assert node['shape'] and node['path'] and node['parameter']


def test_an_edit_over_the_protocol_rewrites_the_file(tmp_path, corpus):
    """The full cooked path: request the tree, edit a node, see the bytes move."""
    import shutil

    package = tmp_path / 'pkg'
    package.mkdir()
    for role, name in (('knowledge', 'knowledge.ttl'), ('shapes', 'shacl.ttl'),
                       ('model', 'model-instance.jsonld')):
        shutil.copy(corpus.sources[role], package / name)
    document = str(package / 'shacl.ttl')

    live = Session(document)
    try:
        live.send({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize',
                   'params': {'processId': os.getpid(),
                              'rootUri': 'file://' + str(package),
                              'capabilities': {}}})
        assert live.wait_for(lambda m: m.get('id') == 1)
        live.send({'jsonrpc': '2.0', 'method': 'initialized', 'params': {}})

        before = open(document).read()
        live.send({'jsonrpc': '2.0', 'id': 11, 'method': 'semforge/setConstraint',
                   'params': {
                       'uri': 'file://' + document,
                       'shape': ('https://industryfusion.github.io/contexts/'
                                 'example/v0/base_shacl/FilterShape'),
                       'path': ['iffBaseEntities:hasStrength'],
                       'parameter': 'sh:minCount', 'value': '0'}})
        replies = live.wait_for(lambda m: m.get('id') == 11)
        assert replies, 'no reply to semforge/setConstraint'
        result = replies[0]['result']
        assert result['ok'], result.get('error')
        assert result['bytesChanged'] == 1

        after = open(document).read()
        assert len(after) == len(before)
        assert sum(1 for a, b in zip(before, after) if a != b) == 1
    finally:
        live.close()


def test_a_refused_edit_reports_instead_of_corrupting(tmp_path, corpus):
    """Structure is not editable through the cooked channel."""
    import shutil

    package = tmp_path / 'pkg'
    package.mkdir()
    for role, name in (('knowledge', 'knowledge.ttl'), ('shapes', 'shacl.ttl'),
                       ('model', 'model-instance.jsonld')):
        shutil.copy(corpus.sources[role], package / name)
    document = str(package / 'shacl.ttl')

    live = Session(document)
    try:
        live.send({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize',
                   'params': {'processId': os.getpid(),
                              'rootUri': 'file://' + str(package),
                              'capabilities': {}}})
        assert live.wait_for(lambda m: m.get('id') == 1)
        before = open(document).read()

        live.send({'jsonrpc': '2.0', 'id': 12, 'method': 'semforge/setConstraint',
                   'params': {
                       'uri': 'file://' + document,
                       'shape': ('https://industryfusion.github.io/contexts/'
                                 'example/v0/base_shacl/FilterShape'),
                       'path': ['iffBaseEntities:hasStrength'],
                       'parameter': 'sh:or', 'value': 'nonsense'}})
        replies = live.wait_for(lambda m: m.get('id') == 12)
        assert replies and replies[0]['result']['ok'] is False
        assert 'not editable' in replies[0]['result']['error']
        assert open(document).read() == before
    finally:
        live.close()


def test_class_choices_arrive_over_the_protocol_and_respect_the_slot(session):
    """What the picker shows: entity types for a relationship, vocabulary for a value."""
    session.send({'jsonrpc': '2.0', 'id': 20, 'method': 'semforge/choices',
                  'params': {'uri': 'file://' + session.document,
                             'path': ['iffBaseEntities:hasFilter',
                                      'ngsild:hasObject'],
                             'parameter': 'sh:class'}})
    entity = session.wait_for(lambda m: m.get('id') == 20)[0]['result']
    entity_labels = {c['label'] for c in entity['choices']}
    assert 'Filter' in entity_labels and 'MachineState' not in entity_labels

    session.send({'jsonrpc': '2.0', 'id': 21, 'method': 'semforge/choices',
                  'params': {'uri': 'file://' + session.document,
                             'path': ['iffBaseEntities:hasState',
                                      'ngsild:hasValue'],
                             'parameter': 'sh:class'}})
    vocabulary = session.wait_for(lambda m: m.get('id') == 21)[0]['result']
    labels = {c['label'] for c in vocabulary['choices']}
    assert 'MachineState' in labels and 'Filter' not in labels

    # Spelled for the shapes file, not the knowledge file: `default1:` is what
    # knowledge.ttl calls that namespace and shacl.ttl would not resolve it.
    values = {c['value'] for c in vocabulary['choices']}
    assert 'base:MachineState' in values
    assert not any(v.startswith('default') for v in values)
