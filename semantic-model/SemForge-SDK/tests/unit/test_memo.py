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

"""What is derived from a loaded graph is kept on it -- and only while it holds."""

from rdflib import Graph, Literal, URIRef

from semforge.rdfio.memo import on_graph

EX = 'https://example.org/'


def _graph(*names):
    graph = Graph()
    for name in names:
        graph.add((URIRef(EX + name), URIRef(EX + 'p'), Literal(1)))
    return graph


def test_kept_while_the_graph_and_its_key_are_the_same():
    knowledge, shapes = _graph('a'), _graph('s')
    calls = []

    def compute():
        calls.append(1)
        return len(calls)

    assert on_graph(knowledge, 'x', (shapes,), compute) == 1
    assert on_graph(knowledge, 'x', (shapes,), compute) == 1
    # Another shapes graph, even an equal one, is another key.
    assert on_graph(knowledge, 'x', (_graph('s'),), compute) == 2
    # The graph itself grew.
    knowledge.add((URIRef(EX + 'b'), URIRef(EX + 'p'), Literal(2)))
    assert on_graph(knowledge, 'x', (shapes,), compute) == 3
    # Another name is another value.
    assert on_graph(knowledge, 'y', (shapes,), compute) == 4


def test_a_case_edit_does_not_recompute_the_declared_attributes(tmp_path, corpus):
    """The editor's analysis after a case edit reuses what the knowledge says."""
    import shutil

    from semforge.cooked import choices
    from semforge.package import load

    root = tmp_path / 'pkg'
    shutil.copytree(corpus.path, root, ignore=shutil.ignore_patterns('.semforge'))
    first = load(str(root))
    terms = choices.attribute_terms(first)
    again = load(str(root), reuse={role: (first.files(role), getattr(first, role))
                                   for role in ('knowledge', 'shapes')})
    computed = []
    real = choices._attribute_terms
    choices._attribute_terms = lambda package: computed.append(1) or real(package)
    try:
        assert choices.attribute_terms(again) == terms
    finally:
        choices._attribute_terms = real
    assert computed == []
