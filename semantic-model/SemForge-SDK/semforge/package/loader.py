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
from .context import context_config, model_context, resolve_model_document

DEFAULTS = {
    'knowledge': ['knowledge.ttl'],
    'shapes': ['shacl.ttl'],
    'model': ['model-instance.jsonld', 'model.jsonld'],
}


@dataclass
class Package:
    path: str
    context_url: str = ''      # what the model names on disk
    context_resolved_locally: bool = False
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

    # The model names the PUBLISHED context on disk; loading answers it from the
    # local copy. Editing the file to point at a local path would make the
    # package unusable to everyone who resolves the url themselves, and fetching
    # the url would make every load depend on the network and on whatever it
    # serves today.
    import json as _json

    config = context_config(path)
    package.context_url = str(model_context(sources['model']) or '')
    document, swapped = resolve_model_document(path, sources['model'], config)
    package.context_resolved_locally = swapped
    if swapped:
        package.model.parse(data=_json.dumps(document), format='json-ld')
    else:
        package.model.parse(sources['model'], format='json-ld')
    return package
