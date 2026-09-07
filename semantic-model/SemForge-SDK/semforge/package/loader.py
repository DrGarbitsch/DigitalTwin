"""Load a package from disk.

M1 reads the KMS triple layout directly -- knowledge.ttl, shacl.ttl and a
model-instance -- which is what the corpus is and what `semforge export` will
have to reproduce byte-for-byte. The modular layout of architecture.md section
6.1, with semforge.yaml, is read when present and otherwise defaulted from
these names.

Loading is read-only and executes no code from the package.
"""

import os
from dataclasses import dataclass, field

from rdflib import Graph

from ..errors import PackageError

DEFAULTS = {
    'knowledge': ['knowledge.ttl'],
    'shapes': ['shacl.ttl'],
    'model': ['model-instance.jsonld', 'model.jsonld'],
}


@dataclass
class Package:
    path: str
    knowledge: Graph = field(default_factory=Graph)
    shapes: Graph = field(default_factory=Graph)
    model: Graph = field(default_factory=Graph)
    sources: dict = field(default_factory=dict)

    def artifact(self, role):
        return self.sources.get(role)


def _first_present(path, names):
    for name in names:
        candidate = os.path.join(path, name)
        if os.path.exists(candidate):
            return candidate
    return None


def load(path):
    """Load a package directory. Raises PackageError naming what is missing."""
    if not os.path.isdir(path):
        raise PackageError(f'not a package directory: {path}')

    sources = {}
    missing = []
    for role, names in DEFAULTS.items():
        found = _first_present(path, names)
        if found is None:
            missing.append(f'{role} (looked for {", ".join(names)})')
        else:
            sources[role] = found
    if missing:
        raise PackageError(
            f'{path} is missing:\n' + '\n'.join(f'  - {m}' for m in missing))

    package = Package(path=path, sources=sources)
    package.knowledge.parse(sources['knowledge'], format='turtle')
    package.shapes.parse(sources['shapes'], format='turtle')
    package.model.parse(sources['model'], format='json-ld')
    return package
