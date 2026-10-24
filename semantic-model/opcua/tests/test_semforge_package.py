#
# Copyright (c) 2026 Intel Corporation
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
import os

import pytest

from lib.semforge_package import build_package, import_closure

HEADER = '@prefix owl: <http://www.w3.org/2002/07/owl#> .\n'


def _ontology(path, *imports):
    lines = [HEADER, f'<urn:{os.path.basename(path)}> a owl:Ontology']
    if imports:
        lines.append(' ; owl:imports ' + ', '.join(f'<{i}>' for i in imports))
    path.write_text(''.join(lines) + ' .\n')
    return str(path)


def test_the_closure_follows_file_imports_and_puts_imports_first(tmp_path):
    core = _ontology(tmp_path / 'core.owl.ttl')
    di = _ontology(tmp_path / 'di.owl.ttl', f'file://{tmp_path}/core.owl.ttl')
    pumps = _ontology(tmp_path / 'pumps.owl.ttl', f'file://{tmp_path}/di.owl.ttl',
                      f'file://{tmp_path}/core.owl.ttl')
    instance = _ontology(tmp_path / 'instance.owl.ttl', f'file://{tmp_path}/pumps.owl.ttl')

    order = list(import_closure([instance]))
    assert order == [core, di, pumps, instance]


def test_a_url_import_is_kept_as_a_url_and_a_cycle_ends(tmp_path):
    seen = {}

    def resolve(source):
        seen[source] = True
        return {'/a.ttl': ['https://example.org/base.ttl', '/b.ttl'],
                '/b.ttl': ['/a.ttl'],
                'https://example.org/base.ttl': []}[source]

    closure = import_closure(['/a.ttl'], resolve)
    assert list(closure) == ['https://example.org/base.ttl', '/b.ttl', '/a.ttl']


def test_standard_vocabularies_are_neither_copied_nor_followed():
    graph = {'/i.ttl': ['https://example.org/base.ttl'],
             'https://example.org/base.ttl': ['http://www.w3.org/2000/01/rdf-schema#',
                                              'https://example.org/v0/ngsild.ttl'],
             'http://www.w3.org/2000/01/rdf-schema#': ['/never.ttl'],
             'https://example.org/v0/ngsild.ttl': ['/never.ttl']}
    assert list(import_closure(['/i.ttl'], graph.__getitem__)) == \
        ['https://example.org/base.ttl', '/i.ttl']


def test_the_package_holds_the_closure_and_names_its_sources(tmp_path):
    src = tmp_path / 'src'
    src.mkdir()
    core = _ontology(src / 'core.owl.ttl')
    instance = _ontology(src / 'instance.owl.ttl', f'file://{core}')
    for name in ('shacl.ttl', 'instances.jsonld', 'context.jsonld'):
        (src / name).write_text('{}' if name.endswith('.jsonld') else HEADER)

    out = tmp_path / 'pkg'
    build_package(str(out), [instance], str(src / 'shacl.ttl'), str(src / 'instances.jsonld'),
                  str(src / 'context.jsonld'), 'https://example.org/context.jsonld',
                  name='pumps', ngsild='../ontology/ngsild.ttl')

    assert sorted(os.listdir(out / 'knowledge')) == ['core.owl.ttl', 'instance.owl.ttl']
    assert (out / 'knowledge' / 'core.owl.ttl').read_text() == (src / 'core.owl.ttl').read_text()
    assert sorted(os.listdir(out)) == ['context.jsonld', 'knowledge', 'model-instance.jsonld',
                                       'semforge.yaml', 'shacl.ttl']
    config = (out / 'semforge.yaml').read_text()
    assert 'name: pumps' in config
    assert 'published: https://example.org/context.jsonld' in config
    assert 'source: ../ontology/ngsild.ttl' in config
    assert f'knowledge/core.owl.ttl <- {core}' in config


def test_two_sources_with_one_file_name_do_not_collide(tmp_path):
    (tmp_path / 'a').mkdir()
    (tmp_path / 'b').mkdir()
    first = _ontology(tmp_path / 'a' / 'base.ttl')
    second = _ontology(tmp_path / 'b' / 'base.ttl', f'file://{first}')
    for name in ('shacl.ttl', 'm.jsonld', 'c.jsonld'):
        (tmp_path / name).write_text('{}')
    out = tmp_path / 'pkg'
    build_package(str(out), [second], str(tmp_path / 'shacl.ttl'), str(tmp_path / 'm.jsonld'),
                  str(tmp_path / 'c.jsonld'), 'https://example.org/c.jsonld')
    assert sorted(os.listdir(out / 'knowledge')) == ['base-2.ttl', 'base.ttl']


def test_it_refuses_a_directory_that_holds_something(tmp_path):
    (tmp_path / 'pkg').mkdir()
    (tmp_path / 'pkg' / 'x').write_text('')
    with pytest.raises(ValueError):
        build_package(str(tmp_path / 'pkg'), [], '', '', '', '')
