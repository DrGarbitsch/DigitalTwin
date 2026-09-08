"""The expectation file.

ruamel.yaml in round-trip mode on purpose: expectation files are human-edited
and `semforge accept` rewrites them in place, so comments and key order have to
survive. pyyaml would destroy every comment in the file on the first accept.
"""

import json
import os
from dataclasses import dataclass, field

from ruamel.yaml import YAML

from ..errors import PackageError

FILENAME = os.path.join('expectations', 'validation.yaml')


def _yaml():
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.indent(mapping=2, sequence=4, offset=2)
    return yaml


@dataclass
class Example:
    path: str
    expect: str = 'valid'            # valid | invalid
    asserts: list = field(default_factory=list)
    residue: str = ''
    conformance: str = ''            # 'full' requires empty residue
    include: list = field(default_factory=list)
    description: str = ''

    @property
    def group(self):
        """The directory an example sits in -- good/, bad/, anything.

        Folder names are for selection and grouping only. What an example is
        FOR comes from `expect` and `asserts`; a file under bad/ that asserts
        nothing is an unfinished test, not a passing one.
        """
        parts = self.path.replace('\\', '/').split('/')
        return parts[-2] if len(parts) > 1 else ''

    @property
    def requires_full_conformance(self):
        return self.conformance == 'full'

    def asserted_keys(self):
        """The (resource, constraint reference) pairs this example is about."""
        return {(a.get('resource', ''), a['constraint']) for a in self.asserts}


@dataclass
class Expectations:
    path: str
    examples: list = field(default_factory=list)
    raw: object = None

    def for_path(self, example_path):
        for example in self.examples:
            if example.path == example_path:
                return example
        return None


def load_expectations(package_path):
    location = os.path.join(package_path, FILENAME)
    if not os.path.exists(location):
        return Expectations(path=location, raw={'examples': []})

    with open(location) as handle:
        raw = _yaml().load(handle) or {}
    examples = []
    for entry in raw.get('examples', []) or []:
        if 'path' not in entry:
            raise PackageError(f'{location}: an example entry has no "path"')
        examples.append(Example(
            path=entry['path'],
            expect=entry.get('expect', 'valid'),
            asserts=list(entry.get('asserts', []) or []),
            residue=entry.get('residue', ''),
            conformance=entry.get('conformance', ''),
            include=list(entry.get('include', []) or []),
            description=entry.get('description', '')))
    return Expectations(path=location, examples=examples, raw=raw)


def save_expectations(expectations):
    """Write back, preserving comments and ordering where the file existed."""
    os.makedirs(os.path.dirname(expectations.path), exist_ok=True)
    raw = expectations.raw if expectations.raw is not None else {'examples': []}
    by_path = {e.path: e for e in expectations.examples}

    entries = raw.get('examples') or []
    for entry in entries:
        example = by_path.get(entry.get('path'))
        if example is not None and example.residue:
            entry['residue'] = example.residue
    if not entries:
        raw['examples'] = [
            {'path': e.path, 'expect': e.expect, 'residue': e.residue}
            for e in expectations.examples]

    with open(expectations.path, 'w') as handle:
        _yaml().dump(raw, handle)


def compose(package, example):
    """The data graph for one example: its own file plus what it includes.

    Subobjects exist so a case can say what it is about. "A cutter running
    while its filter is off" needs a filter, a cartridge and a workpiece to be
    a well-formed entity at all, and repeating them in every case makes the
    difference between two cases hard to see and easy to get wrong.

    Includes are composed BEFORE the example, so the example wins where both
    describe the same entity -- that is what lets bad/filter-off replace the
    filter the good case includes.
    """
    import os

    from rdflib import Graph

    from ..package.context import context_config, resolve_model_document

    config = context_config(package.path)
    graph = Graph()
    for relative in list(example.include) + [example.path]:
        path = os.path.join(package.path, 'examples', relative) \
            if not os.path.isabs(relative) else relative
        if not os.path.exists(path):
            path = os.path.join(package.path, relative)
        if not os.path.exists(path):
            raise PackageError(
                f'{example.path}: cannot find {relative}')
        document, _ = resolve_model_document(package.path, path, config)
        graph.parse(data=json.dumps(document), format='json-ld')
    return graph


def discover(package_path, folder='examples'):
    """Every .jsonld under examples/, as relative paths.

    Used to notice a file nobody declared -- an example that exists and is
    never run is worse than no example, because the directory listing suggests
    coverage that the suite does not have.
    """
    import os

    root = os.path.join(package_path, folder)
    found = []
    for current, _, names in os.walk(root):
        for name in sorted(names):
            if name.endswith(('.jsonld', '.json')):
                found.append(os.path.relpath(os.path.join(current, name), root))
    return sorted(found)
