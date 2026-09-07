"""The Turtle block index (H3): spans, line numbers, and what can hide a '.'"""

from semforge.rdfio.turtle_index import TurtleIndex, index_file

PREFIXES = '@prefix ex: <https://example.org/> .\n@prefix sh: <http://www.w3.org/ns/shacl#> .\n'


def test_a_hash_inside_an_iri_is_not_a_comment():
    """The bug the corpus caught.

    Reading <http://www.w3.org/ns/shacl#> as a comment start swallowed the
    statement terminator and merged three prefix directives with the shape that
    followed them -- so the first shape in the file was simply absent.
    """
    index = TurtleIndex(PREFIXES + 'ex:A a sh:NodeShape .\nex:B a sh:NodeShape .\n')
    assert [b.raw_subject for b in index.blocks] == ['ex:A', 'ex:B']


def test_a_comment_can_hide_a_terminator():
    index = TurtleIndex(PREFIXES + 'ex:A a sh:NodeShape ;\n  # a . inside a comment\n  sh:name "x" .\n')
    assert len(index.blocks) == 1


def test_a_dot_inside_a_string_is_not_a_terminator():
    index = TurtleIndex(PREFIXES + 'ex:A sh:name "one . two" ; sh:order 1 .\n')
    assert len(index.blocks) == 1


def test_a_triple_quoted_sparql_body_survives():
    body = 'SELECT ?x WHERE { ?x a ex:C . FILTER(?x != ex:y) }'
    index = TurtleIndex(
        PREFIXES + 'ex:A sh:sparql [ sh:select """' + body + '""" ] .\nex:B a sh:NodeShape .\n')
    assert [b.raw_subject for b in index.blocks] == ['ex:A', 'ex:B']


def test_nested_brackets_do_not_terminate_early():
    index = TurtleIndex(
        PREFIXES + 'ex:A sh:property [ sh:path ex:p ; sh:node [ sh:minCount 1 ] ] .\n')
    assert len(index.blocks) == 1


def test_line_numbers_are_reported(tmp_path):
    source = PREFIXES + '\nex:A a sh:NodeShape .\n\nex:B a sh:NodeShape .\n'
    path = tmp_path / 'shapes.ttl'
    path.write_text(source)
    index = index_file(str(path))
    assert index.locator('https://example.org/A').endswith(':4')
    assert index.locator('https://example.org/B').endswith(':6')
    assert index.locator('https://example.org/missing') == ''


def test_every_corpus_shape_is_located(corpus):
    from semforge.validate.shapes import node_shapes
    index = index_file(corpus.sources['shapes'])
    for shape in node_shapes(corpus.shapes):
        assert index.locator(shape), f'{shape} has no locator'
