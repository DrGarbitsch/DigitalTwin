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
