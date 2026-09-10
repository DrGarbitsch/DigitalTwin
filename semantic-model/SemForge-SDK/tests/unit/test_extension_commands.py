"""What the commands and the trees actually DO.

`test_extension_activates.py` proves the extension loads and registers its
commands. It cannot see what a handler does with the row it is given -- and that
is where every recent failure has been:

  * the shape icon sent `attributePath[0]`, the PARENT attribute's name, so a
    sub-attribute jumped to the wrong shape;
  * a tree turned the server's "not a SemForge package" into an empty panel with
    no message, which reads as the extension being broken;
  * `reveal()` could not resolve its own node after a refresh, because identity
    was the raw object and a refetch replaces it.

None of those throw and none of them log. So the handlers are driven here
against a stub `vscode` and a canned server.
"""

import json
import os
import shutil
import subprocess

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
SDK = os.path.dirname(os.path.dirname(HERE))
DRIVE = os.path.join(SDK, 'tests', 'harness', 'drive.js')
SRC = os.path.join(SDK, 'vscode', 'src')

SHAPE_REPLY = {
    'ok': True, 'how': 'found', 'shape': 'http://example.com/FilterShape',
    'shapeName': 'iffBaseShacl:FilterShape', 'file': '/pkg/shacl.ttl',
    'line': 105, 'inherited': False, 'slot': 'ngsild:hasValue', 'exists': True,
}


def _drive(tmp_path, scenario, target='extension.js', workspace=None):
    node = shutil.which('node')
    if node is None:
        pytest.skip('node is not installed')
    path = tmp_path / 'scenario.json'
    path.write_text(json.dumps(scenario))
    result = subprocess.run(
        [node, DRIVE, str(workspace or tmp_path),
         os.path.join(SRC, target), str(path)],
        capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stderr[-1500:]
    return json.loads(result.stdout.strip().splitlines()[-1])


def _row(**overrides):
    raw = {
        'kind': 'attribute', 'label': 'hasStrength', 'entity': 'urn:filter:1',
        'entityType': 'iffBaseEntities:Filter', 'editable': True,
        'attributePath': ['iffBaseEntities:hasStrength'],
        'path': ['iffBaseEntities:hasStrength', 0, 'value'],
        'value': '0.6', 'children': [],
    }
    raw.update(overrides)
    return {'raw': raw, 'packageUri': 'file:///pkg/shacl.ttl'}


# --- the shape jump ----------------------------------------------------------

def test_the_shape_icon_asks_for_the_attribute_and_opens_the_line(tmp_path):
    seen = _drive(tmp_path, {
        'command': 'semforge.goToShape', 'node': _row(),
        'replies': {'semforge/shapeFor': SHAPE_REPLY},
    })
    asked = [r for r in seen['requests'] if r['method'] == 'semforge/shapeFor']
    assert len(asked) == 1
    assert asked[0]['params']['attribute'] == 'iffBaseEntities:hasStrength'
    assert asked[0]['params']['entityType'] == 'iffBaseEntities:Filter'
    assert asked[0]['params']['create'] is False
    # Line 105 of the file, zero-based in the editor.
    assert seen['shown'] == [{'file': '/pkg/shacl.ttl', 'line': 104,
                              'preserveFocus': False}]
    assert seen['warnings'] == [] and seen['errors'] == []


def test_a_sub_attribute_jumps_to_its_own_shape_not_its_parents(tmp_path):
    """`attributePath[0]` is the TOP attribute.

    hasXXXWorkpiece sits under hasState, and sending `hasState` would open the
    wrong shape while looking like it worked.
    """
    seen = _drive(tmp_path, {
        'command': 'semforge.goToShape',
        'node': _row(label='hasXXXWorkpiece',
                     attributePath=['iffBaseEntities:hasState', 0,
                                    'iffBaseEntities:hasXXXWorkpiece'],
                     path=['iffBaseEntities:hasState', 0,
                           'iffBaseEntities:hasXXXWorkpiece', 0, 'object']),
        'replies': {'semforge/shapeFor': SHAPE_REPLY},
    })
    asked = [r for r in seen['requests'] if r['method'] == 'semforge/shapeFor']
    assert asked[0]['params']['attribute'] == 'iffBaseEntities:hasXXXWorkpiece'


def test_a_missing_shape_is_offered_and_then_created(tmp_path):
    seen = _drive(tmp_path, {
        'command': 'semforge.goToShape', 'node': _row(),
        'answer': 'Create an empty one',
        'replies': {'semforge/shapeFor': {'ok': False, 'exists': False,
                                          'error': 'no shape constrains it'}},
    })
    # Asked before writing: this edits shacl.ttl.
    assert any('No shape constrains' in m for m in seen['info'])
    asked = [r for r in seen['requests'] if r['method'] == 'semforge/shapeFor']
    assert [r['params']['create'] for r in asked] == [False, True]


def test_declining_the_offer_writes_nothing(tmp_path):
    seen = _drive(tmp_path, {
        'command': 'semforge.goToShape', 'node': _row(),
        'replies': {'semforge/shapeFor': {'ok': False, 'exists': False,
                                          'error': 'no shape constrains it'}},
    })
    asked = [r for r in seen['requests'] if r['method'] == 'semforge/shapeFor']
    assert [r['params']['create'] for r in asked] == [False]
    assert seen['shown'] == []


def test_a_server_that_does_not_know_the_method_says_so(tmp_path):
    """An older server than the extension is exactly what happened.

    The request rejected, the rejection was never caught, and the click did
    nothing at all -- no jump, no message, nothing in the log.
    """
    seen = _drive(tmp_path, {
        'command': 'semforge.goToShape', 'node': _row(), 'replies': {},
    })
    assert seen['errors'], 'a rejected request produced no message'
    assert 'Unhandled method semforge/shapeFor' in seen['errors'][0]


def test_a_row_without_a_type_says_which_half_is_missing(tmp_path):
    seen = _drive(tmp_path, {
        'command': 'semforge.goToShape',
        'node': _row(entityType=''), 'replies': {},
    })
    assert seen['warnings'] and 'entity type' in seen['warnings'][0]
    assert seen['requests'] == []


# --- the value picker --------------------------------------------------------

def test_editing_a_value_offers_the_classes_the_shape_allows(tmp_path):
    seen = _drive(tmp_path, {
        'command': 'semforge.editValue',
        'node': _row(label='hasState',
                     attributePath=['iffBaseEntities:hasState'],
                     path=['iffBaseEntities:hasState', 0, 'value'],
                     value='{"@id": "base:state_ON"}'),
        'pick': 'state_OFF',
        'replies': {
            'semforge/valueChoices': {'choices': [
                {'value': '{"@id": "base:state_ON"}', 'label': 'state_ON',
                 'detail': 'MachineState'},
                {'value': '{"@id": "base:state_OFF"}', 'label': 'state_OFF',
                 'detail': 'MachineState'}], 'note': ''},
            'semforge/setValue': {'ok': True, 'old': 'state_ON',
                                  'new': 'state_OFF'},
        },
    })
    assert seen['quickPicks'], 'no picker was offered'
    labels = [i['label'] for i in seen['quickPicks'][0]['items']]
    assert 'state_ON' in labels and 'state_OFF' in labels
    # And an escape hatch, because the list is a convenience not a restriction.
    assert any('Type a value' in label for label in labels)
    assert seen['inputs'] == [], 'asked for free text despite having options'
    written = [r for r in seen['requests'] if r['method'] == 'semforge/setValue']
    assert written[0]['params']['value'] == '{"@id": "base:state_OFF"}'


def test_a_value_with_no_class_constraint_still_gets_an_input_box(tmp_path):
    seen = _drive(tmp_path, {
        'command': 'semforge.editValue', 'node': _row(),
        'input': '0.8',
        'replies': {
            'semforge/valueChoices': {'choices': [],
                                      'note': 'no sh:class for hasStrength'},
            'semforge/setValue': {'ok': True, 'old': '0.6', 'new': '0.8'},
        },
    })
    assert seen['quickPicks'] == []
    assert seen['inputs'], 'no way to enter a value'
    written = [r for r in seen['requests'] if r['method'] == 'semforge/setValue']
    assert written[0]['params']['value'] == '0.8'


def test_editing_survives_a_server_without_the_choices_method(tmp_path):
    """The picker is an addition; losing it must not cost the edit."""
    seen = _drive(tmp_path, {
        'command': 'semforge.editValue', 'node': _row(), 'input': '0.8',
        'replies': {'semforge/setValue': {'ok': True, 'old': '0.6',
                                          'new': '0.8'}},
    })
    assert seen['inputs'], 'the edit was lost with the picker'
    written = [r for r in seen['requests'] if r['method'] == 'semforge/setValue']
    assert written and written[0]['params']['value'] == '0.8'


# --- the trees ---------------------------------------------------------------

@pytest.mark.parametrize('target,provider,method', [
    ('examples.js', 'ExampleTreeProvider', 'semforge/examples'),
    ('knowledge.js', 'KnowledgeTreeProvider', 'semforge/knowledge'),
    ('tree.js', 'CookedTreeProvider', 'semforge/tree'),
])
def test_a_server_error_reaches_the_panel(tmp_path, target, provider, method):
    """An empty tree with no message is the failure this project keeps meeting.

    The knowledge tree did exactly that: the server said "not a SemForge
    package" and the panel said nothing.
    """
    seen = _drive(tmp_path, {
        'mode': 'tree', 'provider': provider, 'uri': 'file:///pkg/shacl.ttl',
        'replies': {method: {'roots': [], 'error': 'not a SemForge package'}},
    }, target=target)
    assert seen['tree']['roots'] == []
    assert 'not a SemForge package' in (seen['tree']['message'] or '')


@pytest.mark.parametrize('target,provider,method', [
    ('examples.js', 'ExampleTreeProvider', 'semforge/examples'),
    ('knowledge.js', 'KnowledgeTreeProvider', 'semforge/knowledge'),
])
def test_a_node_keeps_its_identity_across_a_refetch(tmp_path, target, provider,
                                                    method):
    """reveal() needs the node the view already holds.

    The tree follows the active editor, so opening the file a click selected
    refreshes it -- and with identity tied to the raw object, the node being
    revealed was already a stranger: "Failed to resolve tree node".
    """
    roots = [{'kind': 'group', 'label': 'a root', 'entity': 'urn:x', 'iri': 'i',
              'children': [{'kind': 'class', 'label': 'a child', 'iri': 'c',
                            'entity': 'urn:y', 'children': []}]}]
    seen = _drive(tmp_path, {
        'mode': 'tree', 'provider': provider, 'uri': 'file:///pkg/shacl.ttl',
        'replies': {method: {'roots': roots}},
    }, target=target)
    assert seen['tree']['identityKept'] is True
    assert seen['tree']['childIdentityKept'] is True, \
        'a child node lost its identity, so reveal cannot resolve it'


def test_a_tree_with_no_package_says_what_it_looked_for(tmp_path):
    seen = _drive(tmp_path, {
        'mode': 'tree', 'provider': 'KnowledgeTreeProvider', 'uri': None,
        'replies': {},
    }, target='knowledge.js')
    assert 'No SemForge package found' in (seen['tree']['message'] or '')
    assert 'knowledge.ttl' in seen['tree']['message']


# --- finding the package -----------------------------------------------------

def _package_at(directory):
    os.makedirs(directory, exist_ok=True)
    for name in ('shacl.ttl', 'knowledge.ttl', 'model-instance.jsonld'):
        with open(os.path.join(directory, name), 'w') as handle:
            handle.write('')


def test_a_package_in_the_opened_folder_is_found(tmp_path):
    _package_at(str(tmp_path))
    seen = _drive(tmp_path, {'mode': 'locate'}, target='locate.js')
    assert seen['locate']['uri'].endswith('shacl.ttl')


def test_a_package_one_level_below_the_opened_folder_is_found(tmp_path):
    """Opening `semantic-model/` rather than `semantic-model/kms/`.

    This is what made the knowledge tree empty: the search looked only IN the
    folder, and the other two trees hid it by waiting for an editor instead.
    """
    _package_at(str(tmp_path / 'kms'))
    os.makedirs(str(tmp_path / 'other'), exist_ok=True)
    seen = _drive(tmp_path, {'mode': 'locate'}, target='locate.js')
    assert seen['locate']['uri'].endswith('kms/shacl.ttl'), seen['locate']


def test_the_folder_itself_wins_over_a_subdirectory(tmp_path):
    _package_at(str(tmp_path))
    _package_at(str(tmp_path / 'kms'))
    seen = _drive(tmp_path, {'mode': 'locate'}, target='locate.js')
    assert not seen['locate']['uri'].endswith('kms/shacl.ttl')


def test_no_package_gives_a_message_naming_what_was_looked_for(tmp_path):
    seen = _drive(tmp_path, {'mode': 'locate'}, target='locate.js')
    assert seen['locate']['uri'] is None
    for expected in ('shacl.ttl', 'knowledge.ttl', 'model-instance.jsonld',
                     'one level below', str(tmp_path)):
        assert expected in seen['locate']['message']
