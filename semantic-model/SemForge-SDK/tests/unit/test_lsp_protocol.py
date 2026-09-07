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
        self.process = subprocess.Popen(
            [INTERPRETER if os.path.exists(INTERPRETER) else sys.executable,
             '-m', 'semforge.editor.server'],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, cwd=SDK)
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


def test_the_diagnostics_carry_the_semforge_source_and_a_kind(session):
    published = session.wait_for(
        lambda m: m.get('method') == 'textDocument/publishDiagnostics')
    sources = {d['source'] for d in published[0]['params']['diagnostics']}
    assert sources
    assert all(s.startswith('semforge (') for s in sources)
    assert any('unexercised' in s for s in sources), \
        'the dead-shape warning should reach the editor'
