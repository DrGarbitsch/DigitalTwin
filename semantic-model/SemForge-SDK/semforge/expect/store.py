"""The expectation file.

ruamel.yaml in round-trip mode on purpose: expectation files are human-edited
and `semforge accept` rewrites them in place, so comments and key order have to
survive. pyyaml would destroy every comment in the file on the first accept.
"""

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
            conformance=entry.get('conformance', '')))
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
