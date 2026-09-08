"""The LSP server: a thin translation of analysis.py into protocol objects.

Nothing here decides anything semantic. That is architecture.md section 8.4 --
the editor layer must not become the semantic engine -- and it is why every
behaviour this exposes is testable without starting a server.

LSP is used where the operation IS an LSP operation: diagnostics, hover,
go-to-definition, document symbols. Operations with no natural LSP shape would
go on a dedicated channel instead; none are needed yet.
"""

import os
import re

from lsprotocol import types
from pygls.lsp.server import LanguageServer

from .. import __version__
from .analysis import analyse, definition_at, hover_at, package_root

SEVERITY = {
    'error': types.DiagnosticSeverity.Error,
    'warning': types.DiagnosticSeverity.Warning,
    'information': types.DiagnosticSeverity.Information,
    'hint': types.DiagnosticSeverity.Hint,
}
WORD = re.compile(r'[A-Za-z_][\w.-]*:?[\w.-]*')

server = LanguageServer('semforge', __version__)
_packages = {}


def _uri_to_path(uri):
    from urllib.parse import unquote, urlparse
    return unquote(urlparse(uri).path)


def _path_to_uri(path):
    from urllib.request import pathname2url
    return 'file://' + pathname2url(os.path.abspath(path))


def _word_at(document, position):
    try:
        line = document.lines[position.line]
    except IndexError:
        return ''
    for match in WORD.finditer(line):
        if match.start() <= position.character <= match.end():
            return match.group(0).rstrip(':').split(':')[-1] or match.group(0)
    return ''


def _publish(ls, uri):
    """Analyse the package this file belongs to and publish its diagnostics."""
    path = _uri_to_path(uri)
    root = package_root(path)
    if root is None:
        ls.text_document_publish_diagnostics(
            types.PublishDiagnosticsParams(uri=uri, diagnostics=[]))
        return
    try:
        findings, package = analyse(root)
    except Exception as exc:                       # noqa: BLE001
        # A broken package must not silence the server: report the failure as a
        # diagnostic rather than leaving the editor showing a clean file.
        ls.text_document_publish_diagnostics(types.PublishDiagnosticsParams(
            uri=uri, diagnostics=[types.Diagnostic(
                range=types.Range(types.Position(0, 0), types.Position(0, 1)),
                message=f'semforge could not analyse this package: {exc}',
                severity=types.DiagnosticSeverity.Error, source='semforge')]))
        return

    _packages[root] = package
    for file_path, items in findings.items():
        diagnostics = []
        for finding in items:
            line = max(finding.line - 1, 0)
            diagnostics.append(types.Diagnostic(
                range=types.Range(types.Position(line, 0),
                                  types.Position(line, 200)),
                message=finding.message,
                severity=SEVERITY.get(finding.severity,
                                      types.DiagnosticSeverity.Information),
                source=f'semforge ({finding.kind})'))
        ls.text_document_publish_diagnostics(types.PublishDiagnosticsParams(
            uri=_path_to_uri(file_path), diagnostics=diagnostics))


@server.feature(types.TEXT_DOCUMENT_DID_OPEN)
def did_open(ls, params):
    _publish(ls, params.text_document.uri)


@server.feature(types.TEXT_DOCUMENT_DID_SAVE)
def did_save(ls, params):
    _publish(ls, params.text_document.uri)


@server.feature(types.TEXT_DOCUMENT_HOVER)
def hover(ls, params):
    root = package_root(_uri_to_path(params.text_document.uri))
    package = _packages.get(root)
    if package is None:
        return None
    document = ls.workspace.get_text_document(params.text_document.uri)
    markdown = hover_at(package, _word_at(document, params.position))
    if not markdown:
        return None
    return types.Hover(contents=types.MarkupContent(
        kind=types.MarkupKind.Markdown, value=markdown))


@server.feature(types.TEXT_DOCUMENT_DEFINITION)
def definition(ls, params):
    root = package_root(_uri_to_path(params.text_document.uri))
    package = _packages.get(root)
    if package is None:
        return None
    document = ls.workspace.get_text_document(params.text_document.uri)
    found = definition_at(package, _word_at(document, params.position))
    if found is None:
        return None
    path, line = found
    return types.Location(
        uri=_path_to_uri(path),
        range=types.Range(types.Position(line - 1, 0),
                          types.Position(line - 1, 0)))


@server.feature(types.TEXT_DOCUMENT_DOCUMENT_SYMBOL)
def document_symbol(ls, params):
    from ..rdfio import index_file

    path = _uri_to_path(params.text_document.uri)
    if not path.endswith('.ttl') or not os.path.exists(path):
        return None
    symbols = []
    for block in index_file(path).blocks:
        symbols.append(types.DocumentSymbol(
            name=block.raw_subject,
            kind=types.SymbolKind.Class,
            range=types.Range(types.Position(block.start_line - 1, 0),
                              types.Position(block.end_line - 1, 0)),
            selection_range=types.Range(types.Position(block.start_line - 1, 0),
                                        types.Position(block.start_line - 1, 1))))
    return symbols


# --- the SemForge channel ---------------------------------------------------
#
# Architecture section 8.3: LSP is used where the operation IS an LSP
# operation. A constraint tree and an edit-by-address are not, and forcing them
# through workspace/executeCommand would make them opaque to any other client.
# They get named methods instead.

def _field(params, name, default=None):
    """Read a parameter whichever way pygls handed it over.

    Custom methods have no registered type, so pygls deserialises their params
    into a namedtuple-like object rather than a dict -- and a handler written
    for one shape fails on the other with a TypeError the client never sees.
    """
    if isinstance(params, dict):
        return params.get(name, default)
    return getattr(params, name, default)


def _serialise(node):
    return {
        'kind': node.kind, 'label': node.label, 'detail': node.detail,
        'shape': node.shape, 'path': list(node.path_chain),
        'parameter': node.parameter, 'value': node.value,
        'editable': node.editable,
        'children': [_serialise(child) for child in node.children],
    }


def _package_for(root):
    from ..package import load

    if root not in _packages:
        _packages[root] = load(root)
    return _packages[root]


@server.feature('semforge/tree')
def cooked_tree(ls, params):
    """The cooked constraint tree for a package."""
    from ..cooked import build_tree

    root = package_root(_uri_to_path(_field(params, 'uri', '')))
    if root is None:
        return {'roots': [], 'error': 'not a SemForge package'}
    try:
        package = _package_for(root)
        return {'root': root,
                'roots': [_serialise(node) for node in build_tree(package)]}
    except Exception as exc:                       # noqa: BLE001
        return {'roots': [], 'error': str(exc)}


@server.feature('semforge/choices')
def constraint_choices(ls, params):
    """Candidate values for a parameter at one address.

    Computed here rather than in the extension because which classes are
    offerable is an ontology question -- entity types on one side of the
    NGSI-LD encoding, vocabulary classes on the other -- and a hard-coded list
    in JavaScript would drift from the model the moment somebody adds a class.
    """
    from ..cooked.choices import choices_for

    root = package_root(_uri_to_path(_field(params, 'uri', '')))
    if root is None:
        return {'choices': [], 'note': 'not a SemForge package'}
    try:
        package = _package_for(root)
        found, note = choices_for(package, list(_field(params, 'path') or []),
                                  _field(params, 'parameter'))
        return {'choices': found, 'note': note}
    except Exception as exc:                       # noqa: BLE001
        return {'choices': [], 'note': str(exc)}


@server.feature('semforge/setConstraint')
def set_constraint(ls, params):
    """Apply one cooked edit, then re-analyse so diagnostics follow it."""
    from ..cooked import apply_edit, remove_constraint

    root = package_root(_uri_to_path(_field(params, 'uri', '')))
    if root is None:
        return {'ok': False, 'error': 'not a SemForge package'}
    try:
        package = _package_for(root)
        shape = _field(params, 'shape')
        chain = list(_field(params, 'path') or [])
        parameter = _field(params, 'parameter')
        if _field(params, 'remove'):
            path, changed = remove_constraint(package, shape, chain, parameter)
        else:
            path, changed = apply_edit(package, shape, chain, parameter,
                                       str(_field(params, 'value')))
        _packages.pop(root, None)                  # the file changed underneath
        _publish(ls, _path_to_uri(path))
        return {'ok': True, 'file': path, 'bytesChanged': changed}
    except Exception as exc:                       # noqa: BLE001
        return {'ok': False, 'error': str(exc)}


def main():
    server.start_io()


if __name__ == '__main__':
    main()
