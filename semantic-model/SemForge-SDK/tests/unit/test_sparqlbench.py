"""The SPARQL workbench: a shape's query, the data validation gives it, and
what it returns -- edited, run, saved.

The first test is the contract the page rests on: for every SPARQL
constraint in the corpus and every data source, the nodes the workbench says
violate are exactly those `validate_graphs` reports. A workbench that runs a
query over a slightly different graph would be worse than none.
"""

import shutil

import pytest
from rdflib import Graph, URIRef
from rdflib.namespace import SH

from semforge.cooked import sparqlbench as sb
from semforge.errors import PackageError
from semforge.package import load

BASE = 'https://industryfusion.github.io/contexts/example/v0/base_shacl/'
CUTTER = BASE + 'StateOnCutterShape'
UNTIL = BASE + 'TimestampCartridgeUntilRulesShape'


@pytest.fixture
def kms(tmp_path, corpus_path):
    # Followed: the corpus files are symlinks into semantic-model/kms.
    target = tmp_path / 'kms'
    shutil.copytree(corpus_path, target, symlinks=False,
                    ignore=shutil.ignore_patterns('.semforge'))
    return str(target)


def _sparql_shapes(package):
    return sorted({str(s) for s in package.shapes.subjects(SH.sparql, None)})


# --- the contract: what it says violates is what validation reports ---------------------

def test_the_workbench_agrees_with_validation_everywhere(corpus):
    from semforge.cooked.casepage import _find_case
    from semforge.expect.store import compose
    from semforge.validate.orchestrator import validate_graphs

    shapes = _sparql_shapes(corpus)
    assert len(shapes) >= 4
    checked = 0
    for source in [s['id'] for s in sb.sources(corpus, CUTTER)]:
        data = corpus.model if source == sb.MAIN else compose(corpus, _find_case(corpus, source))
        report = validate_graphs(data, corpus.shapes, corpus.knowledge, strict=False)
        for shape in shapes:
            fired = {r.resource for r in report.violations
                     if str(r.shape) == shape and 'SPARQL' in str(r.component)}
            for holder in sb.holders(corpus, shape):
                if holder['kind'] != 'constraint':
                    continue
                result = sb.run_query(corpus, shape, holder['index'], source, holder['query'])
                assert result['ok'], result
                said = {str(URIRef(n)) if ':' in n else n for n in result['violating']}
                expanded = {_expand(corpus, n) for n in said}
                assert expanded == fired, (shape, source, expanded, fired)
                checked += 1
    assert checked >= 20


def _expand(package, term):
    prefix, _, name = term.partition(':')
    for bound, namespace in package.shapes.namespaces():
        if bound == prefix:
            return str(namespace) + name
    return term


def test_some_source_makes_a_constraint_fire(corpus):
    """The contract above would hold vacuously if nothing ever fired."""
    fired = sb.run_query(corpus, CUTTER, 0, 'test_StateOnCutterShape/bad/filter-off.jsonld',
                         sb.holders(corpus, CUTTER)[0]['query'])
    assert fired['violating'] == ['urn:plasmacutter:1']
    assert fired['focus'][0]['messages'] == ['Cutter running without running filter']


# --- where the queries are, and which data ------------------------------------------------

def test_holders_are_read_from_the_file(corpus):
    found = sb.holders(corpus, CUTTER)
    assert len(found) == 1
    holder = found[0]
    assert holder['kind'] == 'constraint' and holder['severity'] == 'base:severityCritical'
    assert holder['message'] == 'Cutter running without running filter'
    assert 'FILTER(?v1 = base:state_PROCESSING' in holder['query']
    lines = open(holder['file']).read().splitlines()
    assert 'sh:select' in lines[holder['line'] - 1]
    assert [h['kind'] for h in sb.holders(corpus, UNTIL)] == ['rule']


def test_a_holder_is_picked_by_text_then_kind_then_position(corpus):
    found = sb.holders(corpus, CUTTER) + sb.holders(corpus, UNTIL)
    assert sb.pick(found, query=found[1]['query'] + '\n') is found[1]
    assert sb.pick(found, kind='rule') is found[1]
    assert sb.pick(found, index=0) is found[0]
    assert sb.pick(found, index=99) is found[-1]


def test_sources_are_main_then_the_cases_it_reaches(corpus):
    found = sb.sources(corpus, CUTTER)
    assert found[0]['id'] == sb.MAIN and found[0]['focus'] == 2
    reached = [s for s in found[1:] if s['focus']]
    assert {s['id'] for s in reached} == {
        'test_StateOnCutterShape/bad/filter-off.jsonld',
        'test_StateOnCutterShape/good/filter-on.jsonld'}
    assert found[1:len(reached) + 1] == reached, 'reaching cases come first'


def test_the_page_shows_the_data_the_query_sees(corpus):
    page = sb.bench_page(corpus, CUTTER, 0, 'test_StateOnCutterShape/bad/filter-off.jsonld')
    assert page['focus'] == ['urn:plasmacutter:1']
    assert 'urn:plasmacutter:1' in page['data']['turtle']
    assert 'rdfs:subClassOf' not in page['data']['turtle'], 'knowledge is counted, not shown'
    assert page['stats']['view'] == 'current' and 'current view' in page['stats']['graph']


def test_a_rule_runs_over_the_rules_graph_not_the_view(corpus):
    page = sb.bench_page(corpus, UNTIL, 0, sb.MAIN)
    assert page['stats']['view'] == 'rules'
    # A CONSTRUCT is shown with what it builds, per focus node.
    query = ('PREFIX ex: <urn:ex:>\nCONSTRUCT { $this ex:seen true } WHERE { $this a ?t }')
    result = sb.run_query(corpus, UNTIL, 0, sb.MAIN, query)
    assert result['ok'] and result['triples'] == len(page['focus']) == 2
    assert 'ex:seen true' in result['constructed']


# --- a run --------------------------------------------------------------------------------

def test_an_edit_is_compared_with_the_saved_query(corpus):
    saved = sb.holders(corpus, CUTTER)[0]['query']
    edited = saved.replace('?v2 != base:state_ON', 'true')
    result = sb.run_query(corpus, CUTTER, 0, sb.MAIN, edited)
    assert result['violating'] == ['urn:plasmacutter:1', 'urn:plasmacutter:2']
    assert result['saved'] == {'violating': [], 'ok': True}
    assert result['columns'] == ['this', 'v1', 'f', 'v2']
    assert 'saved' not in sb.run_query(corpus, CUTTER, 0, sb.MAIN, saved)


@pytest.mark.parametrize('query, says', [
    ('SELECT $this WHERE { $this ?p }', 'does not parse'),
    ('CONSTRUCT { $this a <urn:x> } WHERE { $this ?p ?o }', 'must be a SELECT'),
])
def test_what_cannot_run_says_why(corpus, query, says):
    result = sb.run_query(corpus, CUTTER, 0, sb.MAIN, query)
    assert not result['ok'] and says in result['error']


def test_a_parse_error_says_where(corpus):
    result = sb.run_query(corpus, CUTTER, 0, sb.MAIN, 'SELECT $this\nWHERE {\n  $this ?p }')
    assert 'line:' in result['error']


@pytest.mark.parametrize('query, warned', [
    ('SELECT $this WHERE { $this ?p ?o MINUS { $this a <urn:x> } }', 'MINUS'),
    ('SELECT ?x WHERE { ?x ?p ?o }', 'never mentions $this'),
    ('SELECT $this (COUNT(?o) AS ?n) WHERE { $this ?p ?o } GROUP BY $this', 'aggregate'),
])
def test_what_validation_would_read_differently_is_warned(corpus, query, warned):
    result = sb.run_query(corpus, CUTTER, 0, sb.MAIN, query)
    assert any(warned in w for w in result['warnings']), result['warnings']


def test_the_message_is_filled_from_each_row(corpus):
    found = [{'v': 'hot', 'this': 'urn:a'}]
    assert sb._message('{?v} on {$this}, {?missing}', found[0], 'urn:a') == \
        'hot on urn:a, {?missing}'


# --- saving -------------------------------------------------------------------------------

def test_save_replaces_only_the_literal(kms):
    package = load(kms)
    holder = sb.holders(package, CUTTER)[0]
    before = open(holder['file']).read()
    edited = holder['query'].replace('?v2 != base:state_ON', '?v2 != base:state_OFF')
    done = sb.save_query(package, CUTTER, 0, edited, holder['query'])
    after = open(holder['file']).read()
    assert done['line'] == holder['line']
    assert before.replace('?v2 != base:state_ON', '?v2 != base:state_OFF') == after
    assert sb.holders(load(kms), CUTTER)[0]['query'] == edited


def test_quotes_and_backslashes_survive_a_save(kms):
    package = load(kms)
    holder = sb.holders(package, CUTTER)[0]
    tricky = holder['query'] + '\n# a "quoted" """triple""" and a \\ backslash"'
    sb.save_query(package, CUTTER, 0, tricky, holder['query'])
    assert sb.holders(load(kms), CUTTER)[0]['query'] == tricky
    Graph().parse(holder['file'], format='turtle')


def test_a_save_over_a_changed_file_is_refused(kms):
    package = load(kms)
    holder = sb.holders(package, CUTTER)[0]
    sb.save_query(package, CUTTER, 0, holder['query'] + '\n', holder['query'])
    with pytest.raises(PackageError, match='changed in the file'):
        sb.save_query(load(kms), CUTTER, 0, 'SELECT $this WHERE { }', holder['query'])
    with pytest.raises(PackageError, match='empty query'):
        sb.save_query(load(kms), CUTTER, 0, '  ', holder['query'] + '\n')


# --- a new constraint ----------------------------------------------------------------------

def test_a_new_constraint_fires_on_nothing_until_written(kms):
    from semforge.validate import validate_package

    shape = BASE + 'WorkpieceShape'
    before = {(r.resource, str(r.component)) for r in validate_package(load(kms)).violations}
    made = sb.add_constraint(load(kms), shape, 'Workpiece "too" hot')
    package = load(kms)
    holder = sb.holders(package, shape)[made['index']]
    assert holder['message'] == 'Workpiece "too" hot' and holder['kind'] == 'constraint'
    assert 'SELECT $this' in holder['query'] and 'PREFIX ngsild:' in holder['query']
    run = sb.run_query(package, shape, made['index'], sb.MAIN, holder['query'])
    assert run['ok'] and run['violating'] == [] and run['focusCount'] >= 1
    after = {(r.resource, str(r.component)) for r in validate_package(package).violations}
    assert after == before, 'a skeleton changes no verdict'


def test_a_constraint_needs_its_message(kms):
    with pytest.raises(PackageError, match='needs its message'):
        sb.add_constraint(load(kms), BASE + 'WorkpieceShape', '  ')


# --- removing ------------------------------------------------------------------------------

def _statement(kms, shape):
    package = load(kms)
    index = package.index('shapes')
    path, block = index.block_for(URIRef(shape))
    return index.source_of(path)[block.start:block.end]


def test_removing_a_query_followed_by_more_of_the_shape(kms):
    query = sb.holders(load(kms), CUTTER)[0]['query']
    done = sb.remove_holder(load(kms), CUTTER, 0, query)
    assert _statement(kms, CUTTER) == ('iffBaseShacl:StateOnCutterShape a sh:NodeShape ;\n'
                                       '    sh:targetClass iffBaseEntities:Cutter .')
    assert sb.holders(load(kms), CUTTER) == [] and done['asserts'] == 0


def test_removing_a_rule(kms):
    query = sb.holders(load(kms), UNTIL)[0]['query']
    sb.remove_holder(load(kms), UNTIL, 0, query)
    assert _statement(kms, UNTIL) == ('iffBaseShacl:TimestampCartridgeUntilRulesShape a '
                                      'sh:NodeShape ;\n    sh:targetClass '
                                      'iffBaseEntities:FilterCartridge .')


def test_removing_the_last_part_of_a_statement_restores_it_exactly(kms):
    shape = BASE + 'WorkpieceShape'
    before = _statement(kms, shape)
    made = sb.add_constraint(load(kms), shape, 'temporary')
    query = sb.holders(load(kms), shape)[made['index']]['query']
    sb.remove_holder(load(kms), shape, made['index'], query)
    assert _statement(kms, shape) == before


def test_every_other_triple_survives(kms):
    before = load(kms).shapes
    query = sb.holders(load(kms), CUTTER)[0]['query']
    sb.remove_holder(load(kms), CUTTER, 0, query)
    after = load(kms).shapes
    assert len(before) - len(after) == len(before.cbd(next(
        before.objects(URIRef(CUTTER), SH.sparql)))) + 1


def test_the_plan_names_the_cases_that_assert_it(kms):
    plan = sb.removal_plan(load(kms), CUTTER, 0)
    assert plan['last'] and plan['others'] == 0
    assert [(a['case'], a['resource']) for a in plan['asserts']] == \
        [('filter-off.jsonld', 'urn:plasmacutter:1')]
    assert sb.removal_plan(load(kms), UNTIL, 0)['asserts'] == [], 'a rule is not asserted'


def test_removing_the_last_constraint_can_take_its_asserts(kms):
    from semforge.expect.store import load_expectations

    query = sb.holders(load(kms), CUTTER)[0]['query']
    done = sb.remove_holder(load(kms), CUTTER, 0, query, drop_asserts=True)
    assert done['asserts'] == 1
    left = [a for e in load_expectations(kms).examples for a in e.asserts
            if 'StateOnCutterShape' in str(a)]
    assert left == []


def test_asserts_stay_while_another_constraint_can_satisfy_them(kms):
    sb.add_constraint(load(kms), CUTTER, 'a second one')
    plan = sb.removal_plan(load(kms), CUTTER, 1)
    assert not plan['last'] and plan['others'] == 1 and plan['asserts']
    query = sb.holders(load(kms), CUTTER)[1]['query']
    done = sb.remove_holder(load(kms), CUTTER, 1, query, drop_asserts=True)
    assert done['asserts'] == 0, 'the first constraint still answers for them'
    assert sb._asserting(load(kms), CUTTER)


def test_a_removal_over_a_changed_file_is_refused(kms):
    with pytest.raises(PackageError, match='changed in the file'):
        sb.remove_holder(load(kms), CUTTER, 0, 'SELECT $this WHERE { }')
    assert sb.holders(load(kms), CUTTER), 'nothing was removed'


def test_a_query_that_is_the_whole_statement_is_not_cut_out(kms):
    path = sb.holders(load(kms), CUTTER)[0]['file']
    with open(path, 'a', encoding='utf-8') as handle:
        handle.write('\niffBaseShacl:Lone sh:sparql [ sh:select """SELECT $this WHERE { }""" ] .\n')
    lone = BASE + 'Lone'
    query = sb.holders(load(kms), lone)[0]['query']
    with pytest.raises(PackageError, match='remove the shape instead'):
        sb.remove_holder(load(kms), lone, 0, query)
