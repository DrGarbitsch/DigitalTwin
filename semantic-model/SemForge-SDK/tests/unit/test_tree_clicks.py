"""A click on a tree row opens its page; the source is a right-click away.

Driven through the real extension wiring with the Node harness: a selection
in a view, and what it asked VS Code to do. `semforge.trees.click: source`
keeps the old behaviour -- the .ttl/.jsonld editor moves to the row.

Also the symbol set: one icon per kind, status as the icon's colour, and no
hover buttons on rows in summary mode.
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
PACKAGE_JSON = os.path.join(SDK, 'vscode', 'package.json')
TREES = ('semforgeConstraints', 'semforgeModel', 'semforgeKnowledge')


def _drive(tmp_path, scenario, target='extension.js'):
    node = shutil.which('node')
    if node is None:
        pytest.skip('node is not installed')
    for name in ('shacl.ttl', 'knowledge.ttl', 'model-instance.jsonld'):
        (tmp_path / name).write_text('')
    path = tmp_path / 'scenario.json'
    path.write_text(json.dumps(scenario))
    result = subprocess.run([node, DRIVE, str(tmp_path), os.path.join(SRC, target),
                             str(path)], capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stderr[-1500:]
    return json.loads(result.stdout.strip().splitlines()[-1])


def _click(tmp_path, view, raw, config=None, key='root/0'):
    return _drive(tmp_path, {
        'mode': 'select', 'view': view, 'config': config or {},
        'node': {'key': key, 'raw': dict({'children': []}, **raw),
                 'packageUri': 'file:///pkg/shacl.ttl'},
        'replies': {'semforge/tree': {'roots': []}, 'semforge/model': {'roots': []},
                    'semforge/knowledge': {'roots': []}}})


def _opened(seen, command):
    return [e['args'] for e in seen['executed'] if e['command'] == command]


ATTRIBUTE = {'kind': 'attribute', 'label': 'hasStrength',
             'path': ['https://x/hasStrength'], 'typeClass': 'https://x/Filter',
             'definedAt': '/pkg/shacl.ttl:105'}


# --- step A: a click opens the page ------------------------------------------------

def test_an_attribute_click_opens_its_type_page_and_keeps_the_keyboard(tmp_path):
    seen = _click(tmp_path, 'semforgeConstraints', ATTRIBUTE)
    opened = _opened(seen, 'semforge.openTypePage')
    assert len(opened) == 1
    node, options = opened[0]
    assert node['raw']['typeClass'] == 'https://x/Filter'
    assert options == {'preserveFocus': True}
    assert seen['shown'] == [], 'the .ttl stays where it was'


def test_the_source_setting_keeps_the_old_click(tmp_path):
    seen = _click(tmp_path, 'semforgeConstraints', ATTRIBUTE,
                  config={'trees.click': 'source'})
    assert _opened(seen, 'semforge.openTypePage') == []
    assert seen['shown'] == [{'file': '/pkg/shacl.ttl', 'line': 104,
                              'preserveFocus': True}]


def test_a_case_click_opens_the_case_page(tmp_path):
    seen = _click(tmp_path, 'semforgeModel',
                  {'kind': 'example', 'label': 'without-cartridge',
                   'file': '/pkg/examples/test_x/without-cartridge.jsonld',
                   'definedAt': '/pkg/examples/test_x/expectations.yaml:3'})
    opened = _opened(seen, 'semforge.openCasePage')
    assert len(opened) == 1
    assert opened[0][0]['raw']['file'].endswith('without-cartridge.jsonld')
    assert opened[0][1] == {'preserveFocus': True}


def test_the_model_scratchpad_has_no_page_and_opens_its_source(tmp_path):
    seen = _click(tmp_path, 'semforgeModel',
                  {'kind': 'entity', 'label': 'urn:filter:1', 'entity': 'urn:filter:1',
                   'definedAt': '/pkg/model-instance.jsonld:7'})
    assert _opened(seen, 'semforge.openCasePage') == []
    assert seen['shown'][0]['file'] == '/pkg/model-instance.jsonld'


def test_an_entity_type_in_the_knowledge_opens_its_page(tmp_path):
    seen = _click(tmp_path, 'semforgeKnowledge',
                  {'kind': 'class', 'role': 'entityType', 'label': 'Filter',
                   'iri': 'https://x/Filter', 'definedAt': '/pkg/knowledge.ttl:40'})
    assert len(_opened(seen, 'semforge.openTypePage')) == 1
    assert seen['shown'] == []


def test_a_knowledge_attribute_opens_its_carrier_s_page(tmp_path):
    seen = _click(tmp_path, 'semforgeKnowledge',
                  {'kind': 'attribute', 'label': 'hasStrength', 'iri': 'https://x/hasStrength',
                   'entityType': 'https://x/Filter', 'definedAt': '/pkg/knowledge.ttl:80'})
    assert len(_opened(seen, 'semforge.openTypePage')) == 1


def test_a_vocabulary_class_has_no_page_yet(tmp_path):
    seen = _click(tmp_path, 'semforgeKnowledge',
                  {'kind': 'class', 'role': 'vocabulary', 'label': 'MachineState',
                   'iri': 'https://x/MachineState', 'definedAt': '/pkg/knowledge.ttl:625'})
    assert _opened(seen, 'semforge.openTypePage') == []
    assert seen['shown'][0]['line'] == 624


def test_open_source_goes_to_the_row_s_declaration(tmp_path):
    seen = _drive(tmp_path, {
        'command': 'semforge.openSource',
        'node': {'raw': ATTRIBUTE, 'packageUri': 'file:///pkg/shacl.ttl'},
        'replies': {}})
    assert seen['shown'] == [{'file': '/pkg/shacl.ttl', 'line': 104,
                              'preserveFocus': False}]


def test_the_page_opens_on_the_clicked_attribute(tmp_path):
    seen = _drive(tmp_path, {
        'command': 'semforge.openTypePage',
        'node': {'raw': ATTRIBUTE, 'packageUri': 'file:///pkg/shacl.ttl'},
        'replies': {'semforge/typePage': {
            'ok': True, 'label': 'Filter', 'crumbs': [], 'summary': {},
            'attributes': [
                {'label': 'hasCartridge', 'attribute': 'https://x/hasCartridge',
                 'path': ['https://x/hasCartridge'], 'term': 'x:hasCartridge', 'kind': 'Relationship',
                 'presence': 'required · one', 'value': '→ FilterCartridge', 'verbatim': [],
                 'shapeName': 'x:FilterShape', 'depth': 0, 'violations': []},
                {'label': 'hasStrength', 'attribute': 'https://x/hasStrength',
                 'path': ['https://x/hasStrength'], 'term': 'x:hasStrength', 'kind': 'Property',
                 'presence': 'optional', 'value': 'number', 'verbatim': [],
                 'shapeName': 'x:FilterShape', 'depth': 0, 'violations': []}],
            'rules': [], 'exercisedBy': [], 'instances': [], 'subtypes': []}}})
    assert seen['errors'] == [], seen['errors']
    html = seen['webviews'][0]['html'][-1]
    assert html.count('id="focus"') == 1
    assert '>hasStrength<' in html.split('id="focus"', 1)[1].split('</tr>', 1)[0]


# --- step B: the symbol set ---------------------------------------------------------

PROVIDERS = {'semforgeModel': ('ModelTreeProvider', 'model.js', 'semforge/model'),
             'semforgeKnowledge': ('KnowledgeTreeProvider', 'knowledge.js',
                                   'semforge/knowledge')}


def _items(tmp_path, view, roots):
    provider, target, method = PROVIDERS[view]
    return {'items': _drive(tmp_path, {
        'mode': 'items', 'provider': provider, 'uri': 'file:///pkg/shacl.ttl',
        'replies': {method: {'roots': roots}}}, target=target)['rows']}


def test_a_failing_case_keeps_its_beaker_and_turns_red(tmp_path):
    seen = _items(tmp_path, 'semforgeModel', [
        {'kind': 'group', 'label': 'Tests', 'children': [
            {'kind': 'example', 'label': 'good', 'file': '/pkg/a.jsonld', 'children': []},
            {'kind': 'example', 'label': 'bad', 'file': '/pkg/b.jsonld',
             'severity': 'violation', 'children': []}]}])
    rows = {row['label']: row for row in seen['items']}
    assert rows['good']['icon'] == rows['bad']['icon'] == 'beaker'
    assert rows['bad']['color'] == 'list.errorForeground'
    assert rows['good']['color'] == 'testing.iconPassed'


def test_knowledge_tells_entity_types_from_vocabulary_by_icon(tmp_path):
    seen = _items(tmp_path, 'semforgeKnowledge', [
        {'kind': 'group', 'label': 'Entity types', 'children': [
            {'kind': 'class', 'role': 'entityType', 'label': 'Filter', 'children': []}]},
        {'kind': 'group', 'label': 'Vocabulary classes', 'children': [
            {'kind': 'class', 'role': 'vocabulary', 'label': 'MachineState', 'children': [
                {'kind': 'individual', 'label': 'state_ON', 'severity': 'warning',
                 'children': []}]}]}])
    rows = {row['label']: row for row in seen['items']}
    assert rows['Filter']['icon'] == 'symbol-class'
    assert rows['MachineState']['icon'] == 'symbol-enum'
    assert rows['state_ON']['icon'] == 'symbol-enum-member'
    assert rows['state_ON']['color'] == 'list.warningForeground'


def test_only_the_kind_icons_are_used():
    """The review's set; a status icon (warning, error, pencil, lock) on a row
    would say status by shape, which is what the colour is for."""
    allowed = {'symbol-class', 'symbol-interface', 'symbol-field', 'symbol-property',
               'symbol-event', 'symbol-constant', 'beaker', 'symbol-object', 'symbol-enum',
               'symbol-enum-member', 'symbol-namespace', 'project', 'database',
               'settings-gear', 'info'}
    import re
    for name in ('tree.js', 'model.js', 'knowledge.js', 'project.js'):
        with open(os.path.join(SRC, name)) as handle:
            source = handle.read()
        assert 'new vscode.ThemeIcon(' not in source, f'{name} bypasses icon()'
        # The first argument of every icon(...) call, ternaries included.
        firsts = re.findall(r"\bicon\(([^,()]*(?:\([^()]*\)[^,()]*)*)[,)]", source)
        used = {name for first in firsts
                for name in re.findall(r"(?<!=== )(?<!== )'([\w-]+)'", first)}
        assert len(firsts) >= 3, name
        assert used <= allowed, f'{name}: {used - allowed}'


def test_summary_rows_carry_no_hover_buttons_but_keep_every_action():
    with open(PACKAGE_JSON) as handle:
        menus = json.load(handle)['contributes']['menus']['view/item/context']
    for entry in menus:
        if not entry.get('group', '').startswith('inline'):
            continue
        if not any(f'view == {view}' in entry['when'] for view in TREES):
            continue
        assert entry['when'].endswith(' && config.semforge.trees.detail == full'), entry
        bare = entry['when'][:-len(' && config.semforge.trees.detail == full')]
        assert any(other['command'] == entry['command'] and other['when'] == bare and
                   not other.get('group', '').startswith('inline') for other in menus), \
            f'{entry["command"]} would be unreachable in summary mode'


def test_one_plus_per_view_title():
    with open(PACKAGE_JSON) as handle:
        contributes = json.load(handle)['contributes']
    icons = {c['command']: c.get('icon') for c in contributes['commands']}
    for view in ('semforgeConstraints', 'semforgeModel', 'semforgeKnowledge',
                 'semforgeProject'):
        plus = [e for e in contributes['menus']['view/title']
                if e.get('when') == f'view == {view}' and icons.get(e.get('command')) == '$(add)']
        assert len(plus) <= 1, view


def test_the_click_setting_defaults_to_the_page():
    with open(PACKAGE_JSON) as handle:
        props = json.load(handle)['contributes']['configuration']['properties']
    assert props['semforge.trees.click']['default'] == 'page'
    assert props['semforge.trees.click']['enum'] == ['page', 'source']
