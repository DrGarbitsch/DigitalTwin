#
# Copyright (c) 2026 IndustryFusion Foundation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
"""Assemble the output of nodeset2owl/owl2instances into a SemForge package.

A SemForge package is a directory: knowledge, shapes, model, a local context and
semforge.yaml. The knowledge is the hard part. nodeset2owl writes the type
system into separate ontologies (core, di, machinery, pumps, ...) and points at
them with owl:imports -- absolute file:/// paths on the machine that built
them, or urls. Protege follows owl:imports; SemForge does not, so a package
holding only the instance ontology has no type system: every sh:targetClass
names a class nothing declares.

So the knowledge becomes a directory holding the whole import closure, one
file per ontology, copied byte for byte. Nothing in the package points outside
it, and the package means the same thing on every machine.
"""

import os
import shutil
import urllib.parse
import urllib.request
from collections import OrderedDict

from rdflib import Graph, OWL

KNOWLEDGE_DIR = 'knowledge'

# Not copied, and not followed: the W3C vocabularies SemForge knows, and the
# NGSI-LD vocabulary, which a package declares in semforge.yaml (ngsild:).
EXCLUDED = ('http://www.w3.org/', 'https://www.w3.org/', '*/ngsild.ttl')


def excluded(source, patterns=EXCLUDED):
    for pattern in patterns:
        if pattern.startswith('*'):
            if source.endswith(pattern[1:]):
                return True
        elif source.startswith(pattern):
            return True
    return False


def _location(iri, base_dir):
    """A local path for a file:/// iri or a relative name, else the url itself."""
    if iri.startswith('file://'):
        return urllib.parse.unquote(urllib.parse.urlparse(iri).path)
    if iri.startswith(('http://', 'https://')):
        return iri
    return os.path.normpath(os.path.join(base_dir, iri))


def _imports(path_or_url):
    graph = Graph()
    graph.parse(path_or_url, format='turtle')
    return [str(o) for o in graph.objects(None, OWL.imports)]


def import_closure(roots, resolve=_imports, exclude=EXCLUDED):
    """Every file reachable from `roots` through owl:imports, imports first.

    Returns an OrderedDict {source: [sources it imports]}; a source is a local
    path or a url. `resolve` reads the owl:imports of one source; a source
    matching `exclude` is neither copied nor followed.
    """
    found = OrderedDict()

    def visit(source, trail):
        if source in found or source in trail or excluded(source, exclude):
            return
        base_dir = os.path.dirname(source) if not source.startswith(('http://', 'https://')) \
            else ''
        imported = [_location(iri, base_dir) for iri in resolve(source)]
        for child in imported:
            visit(child, trail | {source})
        found[source] = imported

    for root in roots:
        visit(os.path.abspath(root), frozenset())
    return found


def _file_name(source, taken):
    """A file name for a source in knowledge/, unique within the package."""
    name = os.path.basename(urllib.parse.urlparse(source).path if
                            source.startswith(('http://', 'https://')) else source) or 'ontology.ttl'
    if not name.endswith('.ttl'):
        name += '.ttl'
    stem, suffix = name[:-4], '.ttl'
    candidate, n = name, 1
    while candidate in taken:
        n += 1
        candidate = f'{stem}-{n}{suffix}'
    taken.add(candidate)
    return candidate


def _copy(source, target):
    if source.startswith(('http://', 'https://')):
        with urllib.request.urlopen(source, timeout=60) as response:   # noqa: S310
            data = response.read()
        with open(target, 'wb') as handle:
            handle.write(data)
    else:
        shutil.copyfile(source, target)


def _config(name, published, ngsild, sources):
    lines = [
        f'# {name}',
        '#',
        '# Written by owl2semforge.py from the output of nodeset2owl.py and',
        '# owl2instances.py.',
        '',
        f'name: {name}',
        '',
        '# The entities name the PUBLISHED context; SemForge answers it from the',
        '# local copy, so nothing here depends on the network.',
        'context:',
        '  local: context.jsonld',
        f'  published: {published}',
    ]
    if ngsild:
        lines += ['', 'ngsild:', f'  source: {ngsild}']
    lines += ['', '# knowledge/ is the owl:imports closure, one file per ontology:']
    lines += [f'#   {target} <- {source}' for target, source in sources]
    return '\n'.join(lines) + '\n'


def build_package(out_dir, knowledge, shacl, instances, context, published,
                  name=None, ngsild=None, resolve=_imports, copy=_copy, exclude=EXCLUDED):
    """Write a SemForge package into `out_dir`. Returns the files written."""
    if os.path.exists(out_dir) and os.listdir(out_dir):
        raise ValueError(f'{out_dir} exists and is not empty')
    os.makedirs(os.path.join(out_dir, KNOWLEDGE_DIR))

    written, taken, sources = [], set(), []
    for source in import_closure(knowledge, resolve, exclude):
        target = _file_name(source, taken)
        copy(source, os.path.join(out_dir, KNOWLEDGE_DIR, target))
        sources.append((f'{KNOWLEDGE_DIR}/{target}', source))
        written.append(os.path.join(out_dir, KNOWLEDGE_DIR, target))

    for source, target in ((shacl, 'shacl.ttl'), (instances, 'model-instance.jsonld'),
                           (context, 'context.jsonld')):
        shutil.copyfile(source, os.path.join(out_dir, target))
        written.append(os.path.join(out_dir, target))

    config = os.path.join(out_dir, 'semforge.yaml')
    with open(config, 'w', encoding='utf-8') as handle:
        handle.write(_config(name or os.path.basename(os.path.abspath(out_dir)),
                             published, ngsild, sources))
    written.append(config)
    return written
