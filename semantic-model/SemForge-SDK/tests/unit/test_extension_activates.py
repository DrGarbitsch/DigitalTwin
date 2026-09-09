"""Actually activate the extension.

`node --check` parses; it cannot see a function that is CALLED and never
DEFINED. That is how `sdkDirectory` went missing in an edit and left the
extension throwing ReferenceError the moment VS Code activated it -- broken in
precisely the way that looks like "it finds nothing", which is the failure mode
this project keeps meeting.

So this runs `activate()` against a stub `vscode` and asserts the commands get
registered. It is the only test here that needs node; it skips if node is
absent rather than pretending to pass.
"""

import json
import os
import shutil
import subprocess

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
SDK = os.path.dirname(os.path.dirname(HERE))
HARNESS = os.path.join(SDK, 'tests', 'harness', 'activate.js')
EXTENSION = os.path.join(SDK, 'vscode', 'src', 'extension.js')

EXPECTED = {
    'semforge.restart', 'semforge.revalidate', 'semforge.doctor',
    'semforge.editConstraint', 'semforge.removeConstraint',
    'semforge.refreshTree', 'semforge.goToDefinition', 'semforge.overrideHere',
    'semforge.editValue', 'semforge.refreshExamples', 'semforge.addAttribute',
    'semforge.addEntity', 'semforge.addObservation',
}


def _activate(corpus_path):
    node = shutil.which('node')
    if node is None:
        pytest.skip('node is not installed')
    result = subprocess.run(
        [node, HARNESS, os.path.abspath(corpus_path), EXTENSION],
        capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, (
        'activate() threw -- the extension would not load:\n'
        + result.stderr[-1500:])
    return json.loads(result.stdout.strip().splitlines()[-1])


def test_activation_does_not_throw(corpus_path):
    _activate(corpus_path)


def test_every_command_is_registered(corpus_path):
    registered = set(_activate(corpus_path)['commands'])
    assert registered == EXPECTED, (
        f'missing: {sorted(EXPECTED - registered)}; '
        f'unexpected: {sorted(registered - EXPECTED)}')


def test_the_manifest_and_the_code_agree(corpus_path):
    """A command in one and not the other is dead either way."""
    with open(os.path.join(SDK, 'vscode', 'package.json')) as handle:
        declared = {c['command']
                    for c in json.load(handle)['contributes']['commands']}
    registered = set(_activate(corpus_path)['commands'])
    assert declared == registered, (
        f'declared not registered: {sorted(declared - registered)}; '
        f'registered not declared: {sorted(registered - declared)}')


def test_a_usable_package_activates_without_an_error_popup(corpus_path):
    """The corpus has a working venv beside it, so nothing should be reported."""
    assert _activate(corpus_path)['errors'] == []


def test_every_view_has_an_onview_activation_event():
    """Clicking a contributed view has to activate the extension.

    Without `onView:`, VS Code renders the view with nothing behind it and says
    "There is no data provider registered that can provide view data" -- which
    reads as the extension being broken rather than asleep, and leaves no log
    entry at all because it never ran.
    """
    with open(os.path.join(SDK, 'vscode', 'package.json')) as handle:
        manifest = json.load(handle)

    views = {view['id']
             for group in manifest['contributes']['views'].values()
             for view in group}
    events = set(manifest['activationEvents'])
    for view in views:
        assert f'onView:{view}' in events, \
            f'{view} can be shown without activating the extension'


def test_the_trees_anchor_to_the_folder_not_only_the_editor(corpus_path):
    """The common flow is "open the folder, click the icon" with no file open.

    Anchoring only to the active editor left the tree empty in exactly that
    case, with nothing to say why.
    """
    for name in ('tree.js', 'examples.js'):
        source = open(os.path.join(SDK, 'vscode', 'src', name)).read()
        assert 'function defaultUri(' in source, f'{name} has no folder fallback'
        assert 'workspaceFolders' in source
