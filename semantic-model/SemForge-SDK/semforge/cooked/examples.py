"""The example instances, as a tree, with what validation says about them.

The constraint tree shows the shapes. This shows the data they judge, which is
the other half of the loop the manifest describes: pick an entity, walk its
nested attributes, see which constraint fired on which one, change a value and
watch the verdict move.

A viewer alone would be a JSON outline VS Code already gives you. What makes it
worth its own tree is the verdicts hanging off the nodes -- an entity says how
many violations it carries, and the attribute that caused one says so on the
line you are looking at.

Editing goes through a JSON round-trip rather than a text-span index, unlike
the shapes. That is not laziness: `json.dumps(..., indent=2)` reproduces this
model byte for byte, so a value change really does produce a one-line diff.
JSON has no comments to lose either, which is what forced the span approach on
Turtle.
"""

import json
from collections import OrderedDict
from dataclasses import dataclass, field

from ..errors import PackageError

RESERVED = {'@context', 'id', '@id', 'type', '@type'}
DEFAULT_DATASET = '@none'
VALUE_KEYS = ('value', 'object', 'valueList', 'json')
META_KEYS = ('observedAt', 'unitCode', 'datasetId')


@dataclass
class ExampleNode:
    # kind: example | entity | attribute | dataset | instance | meta
    kind: str
    label: str
    detail: str = ''
    entity: str = ''           # the entity IRI this sits under
    path: list = field(default_factory=list)   # attribute names, then index
    value: str = ''
    editable: bool = False
    severity: str = ''         # violation | warning | '' -- from the report
    messages: list = field(default_factory=list)
    children: list = field(default_factory=list)
    file: str = ''             # the JSON file this node was read from
    dataset_id: str = ''       # the datasetId this row stands for
    observations: int = 0      # how many, when it is a series
    attribute_path: list = field(default_factory=list)  # where to append one

    @property
    def is_series(self):
        return self.observations > 1


def _entities(path):
    with open(path, encoding='utf-8') as handle:
        document = json.load(handle, object_pairs_hook=OrderedDict)
    return document if isinstance(document, list) else [document]


def _render(value):
    if isinstance(value, dict) and '@id' in value:
        return str(value['@id'])
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)[:60]
    return json.dumps(value, ensure_ascii=False) if isinstance(value, str) \
        else str(value)


def _instance_node(instance, entity, path, findings):
    """One attribute instance: its value, its metadata, its sub-attributes."""
    node = ExampleNode(kind='instance', label='', entity=entity,
                       path=list(path))
    if not isinstance(instance, dict):
        node.label = _render(instance)
        node.value = _render(instance)
        return node

    kind = instance.get('type', '')
    for key in VALUE_KEYS:
        if key in instance:
            node.label = _render(instance[key])
            node.value = _render(instance[key])
            node.detail = kind
            node.editable = key in ('value', 'object')
            node.path = list(path) + [key]
            break
    else:
        node.label = kind or '(no value)'
        node.detail = 'attribute with no value'

    for key in META_KEYS:
        if key in instance:
            node.children.append(ExampleNode(
                kind='meta', label=key, detail=_render(instance[key]),
                entity=entity, path=list(path) + [key],
                value=_render(instance[key]), editable=True))

    for key, value in instance.items():
        if key in RESERVED or key in VALUE_KEYS or key in META_KEYS:
            continue
        node.children.append(
            _attribute_node(key, value, entity, list(path) + [key], findings))
    return node


def _dataset_of(instance):
    if isinstance(instance, dict):
        return str(instance.get('datasetId', DEFAULT_DATASET))
    return DEFAULT_DATASET


def _group_by_dataset(instances):
    """{datasetId: [(index, instance)]}, in first-seen order.

    An NGSI-LD attribute is identified by (entity, name, datasetId). Several
    instances sharing a datasetId are ONE attribute observed repeatedly;
    different datasetIds are DIFFERENT attributes that happen to share a name.
    A flat list conflates the two, and they behave differently -- the dedup
    resolves within a datasetId and never across.
    """
    groups = OrderedDict()
    for index, instance in enumerate(instances):
        groups.setdefault(_dataset_of(instance), []).append((index, instance))
    return groups


def _current_index(members):
    """Which member validation reads: the latest observedAt, else the last.

    Returns the index into the WHOLE attribute, not a position within the
    group -- an edit path has to address the JSON array, and the two coincide
    only when there is a single datasetId.
    """
    stamped = [(str(instance.get('observedAt', '')), index)
               for index, instance in members
               if isinstance(instance, dict) and 'observedAt' in instance]
    return max(stamped)[1] if stamped else members[-1][0]


def _member_at(members, index):
    return next(instance for position, instance in members if position == index)


def _series_children(members, current, entity, path, findings):
    """One row per observation, newest marked current.

    Editing any other one changes the file and nothing else, which without the
    marker reads as the editor being broken.
    """
    out = []
    for index, instance in members:
        child = _instance_node(instance, entity, list(path) + [index], findings)
        stamp = instance.get('observedAt') if isinstance(instance, dict) else None
        marks = [child.detail] if child.detail else []
        if stamp:
            marks.append(str(stamp))
        marks.append('current' if index == current else 'superseded')
        child.detail = ' · '.join(marks)
        child.children = [c for c in child.children
                          if not (c.kind == 'meta' and c.label == 'observedAt')]
        out.append(child)
    return out


def _dataset_node(dataset, members, entity, path, findings):
    current = _current_index(members)
    head = _instance_node(_member_at(members, current), entity,
                          list(path) + [current], findings)
    node = ExampleNode(
        kind='dataset', label=head.label or dataset, entity=entity,
        dataset_id=dataset, observations=len(members),
        attribute_path=list(path), path=head.path, value=head.value,
        editable=head.editable,
        detail=' · '.join(p for p in (
            dataset, head.detail,
            f'{len(members)} observations' if len(members) > 1 else '') if p))
    node.children = (_series_children(members, current, entity, path, findings)
                     if len(members) > 1 else list(head.children))
    return node


def _attribute_node(name, value, entity, path, findings):
    instances = value if isinstance(value, list) else [value]
    short = name.rsplit('/', 1)[-1].rsplit('#', 1)[-1].split(':')[-1]

    node = ExampleNode(kind='attribute', label=short, entity=entity,
                       path=list(path), attribute_path=list(path))
    hit = findings.get((entity, short))
    if hit:
        node.severity = hit[0]
        node.messages = hit[1]
        node.detail = f'{len(hit[1])} violation(s)'

    groups = _group_by_dataset(instances)

    if len(groups) > 1:
        node.detail = ' · '.join(
            p for p in (node.detail, f'{len(groups)} datasets') if p)
        for dataset, members in groups.items():
            node.children.append(
                _dataset_node(dataset, members, entity, path, findings))
        return node

    dataset, members = next(iter(groups.items()))
    current = _current_index(members)
    node.dataset_id = dataset
    node.observations = len(members)
    if dataset != DEFAULT_DATASET:
        node.detail = ' · '.join(p for p in (node.detail, dataset) if p)

    head = _instance_node(_member_at(members, current), entity,
                          list(path) + [current], findings)

    if len(members) > 1:
        # One dataset observed repeatedly: the row shows the value validation
        # reads, and expanding gives the series.
        node.value, node.editable, node.path = head.value, head.editable, head.path
        node.detail = ' · '.join(p for p in (
            head.label, head.detail, f'{len(members)} observations',
            node.detail) if p)
        node.children = _series_children(members, current, entity, path,
                                         findings)
        return node

    if not head.children:
        node.value, node.editable, node.path = head.value, head.editable, head.path
        node.detail = ' · '.join(p for p in (head.label, head.detail,
                                             node.detail) if p)
    else:
        node.children = [head]
        node.detail = node.detail or head.label
    return node


def build_suite(package, expectations=None):
    """Every declared example as its own root, with what it is for and how it did.

    The package's own model-instance is included as a root too. It is not a
    declared example -- it is the model as shipped -- and leaving it out of the
    tree would hide the thing most of the toolchain actually compiles.

    Entities that arrive through `include` are shown read-only under the file
    that declares them. Editing a subobject in place would change every case
    that includes it, which is a decision to take deliberately in that file
    rather than a side effect of editing one example.
    """
    from ..expect.store import compose, load_expectations
    from ..validate.orchestrator import validate_graphs

    expectations = expectations or load_expectations(package.path)
    by_suite = OrderedDict()
    loose = []

    for example in expectations.examples:
        try:
            graph = compose(package, example)
            report = validate_graphs(graph, package.shapes, package.knowledge,
                                     strict=False)
        except Exception as exc:                   # noqa: BLE001
            node = ExampleNode(kind='example', label=example.path,
                               detail=f'error: {exc}', severity='violation')
        else:
            node = _example_root(package, example, report)

        target = by_suite.setdefault(example.suite, []) if example.suite \
            else loose
        target.append(node)

    roots = []
    for suite, nodes in by_suite.items():
        failing = [n for n in nodes if n.severity]
        node = ExampleNode(
            kind='suite', label=suite,
            detail=' · '.join(p for p in (
                f'{len(nodes)} case(s)',
                f'{len(failing)} failing' if failing else 'all ok') if p),
            severity='violation' if failing else '')
        node.children = nodes
        roots.append(node)

    roots.extend(loose)
    roots.append(_model_root(package))
    return roots


def _expected_shape(example, report):
    """Did it do what it says? -- the label the tree hangs on the example."""
    violations = len(report.violations)
    if example.expect == 'invalid':
        return ('ok' if violations else 'FAILED: expected a violation',
                '' if violations else 'violation')
    if example.conformance == 'full' and violations:
        return (f'FAILED: {violations} violation(s), conformance is full',
                'violation')
    return ('ok', '')


def _example_root(package, example, report):
    import os

    status, severity = _expected_shape(example, report)
    detail = ' · '.join(p for p in (
        example.group, example.expect, status,
        f'{len(example.include)} include(s)' if example.include else '') if p)
    node = ExampleNode(kind='example', label=os.path.basename(example.path),
                       detail=detail, severity=severity,
                       messages=[example.description] if example.description
                       else [])

    own = os.path.join(package.path, 'examples', example.path)
    node.children.extend(_entity_nodes(own, report))

    for included in example.include:
        path = os.path.join(package.path, 'examples', included)
        folder = ExampleNode(kind='include', label=os.path.basename(included),
                             detail='included — edit it where it is declared')
        folder.children.extend(_entity_nodes(path, report, editable=False))
        node.children.append(folder)
    return node


def _model_root(package):
    from ..validate import validate_package

    node = ExampleNode(
        kind='example', label=package.sources['model'].rsplit('/', 1)[-1],
        detail='the model as shipped — not a declared example')
    node.children.extend(
        _entity_nodes(package.sources['model'], validate_package(
            package, strict=False)))
    return node


def _stamp_file(node, path):
    node.file = path
    for child in node.children:
        _stamp_file(child, path)


def _entity_nodes(path, report=None, editable=True):
    findings = {}
    counts = {}
    for result in (report.violations if report is not None else []):
        findings.setdefault((result.resource, result.attribute),
                            ['violation', []])[1].append(
            f'{result.component}: {result.message or ""}'.strip())
        counts[result.resource] = counts.get(result.resource, 0) + 1

    out = []
    for entity in _entities(path):
        if not isinstance(entity, dict):
            continue
        identifier = str(entity.get('id') or entity.get('@id') or '(no id)')
        node = ExampleNode(
            kind='entity', label=identifier, entity=identifier,
            detail=str(entity.get('type') or entity.get('@type') or ''))
        if counts.get(identifier):
            node.severity = 'violation'
            node.detail += f' · {counts[identifier]} violation(s)'
            node.messages = [m for (resource, _), (_, msgs) in findings.items()
                             if resource == identifier for m in msgs]
        for key, value in entity.items():
            if key in RESERVED:
                continue
            child = _attribute_node(key, value, identifier, [key], findings)
            if not editable:
                _read_only(child)
            node.children.append(child)
        _stamp_file(node, path)
        out.append(node)
    return out


def _read_only(node):
    node.editable = False
    for child in node.children:
        _read_only(child)


def build_examples(package, report=None):
    """Entities -> attributes -> instances, annotated with the verdicts."""
    findings = {}
    if report is not None:
        for result in report.violations:
            key = (result.resource, result.attribute)
            entry = findings.setdefault(key, ['violation', []])
            entry[1].append(f'{result.component}: {result.message or ""}'.strip())

    by_entity = {}
    for result in (report.violations if report is not None else []):
        by_entity.setdefault(result.resource, 0)
        by_entity[result.resource] += 1

    root = ExampleNode(
        kind='example',
        label=package.sources['model'].rsplit('/', 1)[-1],
        detail=f'{len(_entities(package.sources["model"]))} entities')

    for entity in _entities(package.sources['model']):
        if not isinstance(entity, dict):
            continue
        identifier = str(entity.get('id') or entity.get('@id') or '(no id)')
        node = ExampleNode(
            kind='entity', label=identifier, entity=identifier,
            detail=str(entity.get('type') or entity.get('@type') or ''))
        count = by_entity.get(identifier, 0)
        if count:
            node.severity = 'violation'
            node.detail += f' · {count} violation(s)'
            # A minCount violation is about an attribute that is NOT there, so
            # there is no node to hang it on. The entity carries the message or
            # it is lost.
            node.messages = [m for (resource, _), (_, msgs) in findings.items()
                             if resource == identifier for m in msgs]

        for key, value in entity.items():
            if key in RESERVED:
                continue
            node.children.append(
                _attribute_node(key, value, identifier, [key], findings))
        root.children.append(node)
    return [root]


# --- editing -----------------------------------------------------------------

def _locate(document, entity_id, path):
    for entity in document:
        if not isinstance(entity, dict):
            continue
        if str(entity.get('id') or entity.get('@id')) != entity_id:
            continue
        cursor = entity
        for step in path[:-1]:
            cursor = cursor[step]
        return cursor, path[-1]
    raise PackageError(f'no entity {entity_id} in this example')


def _target_file(package, file=None):
    """Which JSON an edit lands in.

    Defaults to the package model, but the suite view shows entities from
    example files too -- editing one of those has to write where it came from,
    not into model-instance.jsonld.
    """
    import os

    if not file:
        return package.sources['model']
    if os.path.isabs(file):
        return file
    for base in (package.path, os.path.join(package.path, 'examples')):
        candidate = os.path.join(base, file)
        if os.path.exists(candidate):
            return candidate
    raise PackageError(f'no such example file: {file}')


def set_value(package, entity_id, path, value, file=None):
    """Change one value in an example. Returns (path, old, new).

    The new value is parsed as JSON when it can be, so `42` becomes a number
    and `{"@id": "..."}` becomes a node reference -- typing an IRI into a
    Property that expects one should not quietly produce the string form,
    which is the difference between a constraint passing and failing.
    """
    source = _target_file(package, file)
    with open(source, encoding='utf-8') as handle:
        text = handle.read()
    document = json.loads(text, object_pairs_hook=OrderedDict)
    if not isinstance(document, list):
        document = [document]

    container, key = _locate(document, entity_id, list(path))
    try:
        parsed = json.loads(value) if isinstance(value, str) else value
    except (TypeError, ValueError):
        parsed = value

    try:
        old = container[key]
    except (KeyError, IndexError, TypeError):
        raise PackageError(f'{entity_id}: no value at {"/".join(map(str, path))}')
    container[key] = parsed

    rendered = json.dumps(document, indent=2, ensure_ascii=False)
    if text.endswith('\n'):
        rendered += '\n'
    json.loads(rendered)                       # never write what will not parse
    with open(source, 'w', encoding='utf-8') as handle:
        handle.write(rendered)
    return source, _render(old), _render(parsed)


def add_observation(package, entity_id, attribute_path, dataset_id=None,
                    value=None, observed_at=None, file=None):
    """Append an observation to one attribute of one entity.

    An attribute is identified by (entity, name, datasetId), so a new
    observation joins the series for ITS datasetId and starts a new one for a
    datasetId not seen before. The type is copied from what is already there --
    a Property whose new instance arrives as a Relationship is not a new
    observation of the same attribute, it is a different attribute.
    """
    source = _target_file(package, file)
    with open(source, encoding='utf-8') as handle:
        text = handle.read()
    document = json.loads(text, object_pairs_hook=OrderedDict)
    if not isinstance(document, list):
        document = [document]

    entity = next((e for e in document if isinstance(e, dict)
                   and str(e.get('id') or e.get('@id')) == entity_id), None)
    if entity is None:
        raise PackageError(f'no entity {entity_id} in this example')

    cursor = entity
    for step in list(attribute_path)[:-1]:
        cursor = cursor[step]
    key = list(attribute_path)[-1]
    if key not in cursor:
        raise PackageError(f'{entity_id} has no attribute {key}')

    existing = cursor[key]
    instances = existing if isinstance(existing, list) else [existing]
    template = next((i for i in instances if isinstance(i, dict)), {})

    fresh = OrderedDict()
    if template.get('type'):
        fresh['type'] = template['type']
    try:
        fresh['value'] = json.loads(value) if isinstance(value, str) else value
    except (TypeError, ValueError):
        fresh['value'] = value
    if observed_at:
        fresh['observedAt'] = observed_at
    if dataset_id and dataset_id != DEFAULT_DATASET:
        fresh['datasetId'] = dataset_id

    cursor[key] = instances + [fresh]

    rendered = json.dumps(document, indent=2, ensure_ascii=False)
    if text.endswith('\n'):
        rendered += '\n'
    json.loads(rendered)
    with open(source, 'w', encoding='utf-8') as handle:
        handle.write(rendered)
    return source, len(cursor[key])


def _write(source, document, text):
    rendered = json.dumps(document, indent=2, ensure_ascii=False)
    if text.endswith('\n'):
        rendered += '\n'
    json.loads(rendered)
    with open(source, 'w', encoding='utf-8') as handle:
        handle.write(rendered)
    return rendered


def add_attribute(package, entity_id, name, kind=None, value=None,
                  file=None, **metadata):
    """Add a legal NGSI-LD attribute to an entity.

    The kind decides which key carries the payload, and the shapes are asked
    first: a value shape on ngsild:hasObject means Relationship, one on
    hasValue means Property. Reading it from the model beats asking the author,
    who is the person the model exists to help -- and getting the pairing wrong
    produces something that parses, looks plausible and means nothing.
    """
    from ..ngsild.build import attribute, kind_for_shape

    source = _target_file(package, file)
    with open(source, encoding='utf-8') as handle:
        text = handle.read()
    document = json.loads(text, object_pairs_hook=OrderedDict)
    if not isinstance(document, list):
        document = [document]

    entity = next((e for e in document if isinstance(e, dict)
                   and str(e.get('id') or e.get('@id')) == entity_id), None)
    if entity is None:
        raise PackageError(f'no entity {entity_id} in {source}')
    if name in entity:
        raise PackageError(
            f'{entity_id} already has {name}; add an observation to it instead')

    if not kind:
        kind = kind_for_shape(package, str(entity.get('type', '')), name) \
            or 'Property'
    try:
        parsed = json.loads(value) if isinstance(value, str) else value
    except (TypeError, ValueError):
        parsed = value

    entity[name] = attribute(kind, parsed, **metadata)
    _write(source, document, text)
    return source, kind


def add_entity(package, identifier, entity_type, file=None, context=None):
    """Append a legal NGSI-LD entity to an example file."""
    from ..ngsild.build import entity as build_entity
    from ..package.context import context_config

    source = _target_file(package, file)
    with open(source, encoding='utf-8') as handle:
        text = handle.read()
    document = json.loads(text, object_pairs_hook=OrderedDict)
    if not isinstance(document, list):
        document = [document]

    if any(isinstance(e, dict) and str(e.get('id') or e.get('@id')) == identifier
           for e in document):
        raise PackageError(f'{source} already declares {identifier}')

    if context is None:
        existing = next((e.get('@context') for e in document
                         if isinstance(e, dict) and e.get('@context')), None)
        context = existing or context_config(package.path).published

    document.append(build_entity(identifier, entity_type, context=context))
    _write(source, document, text)
    return source, len(document)


def flatten(nodes, depth=0):
    for node in nodes:
        yield depth, node
        yield from flatten(node.children, depth + 1)
