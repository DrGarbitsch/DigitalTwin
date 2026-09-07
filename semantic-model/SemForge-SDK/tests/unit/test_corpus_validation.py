"""Validating the real KMS.

Every violation the corpus produces is a KNOWN one, documented elsewhere in the
repo. Pinning them here means a new violation is a finding rather than noise,
and it is the check that the pipeline reproduces what the platform's own
harnesses already established.
"""

from semforge.validate import Status, validate_package

# Documented in shacl2flink/tests/pyshacl-compare/expected-divergences.txt and
# in kms-constraints/kms/README.md. See test docstrings for each.
BASE = 'https://industryfusion.github.io/contexts/example/v0/base_shacl/'
FILTER = 'https://industryfusion.github.io/contexts/example/v0/filter_shacl/'

# Shape identity is the full IRI, not the short name: the corpus carries two
# distinct CartridgeShape IRIs and merging them would corrupt coverage.
EXPECTED = {
    # filter_shacl, not base_shacl -- the two share a local name and only the
    # IRI says which one required hasWasteclass [1,1].
    ('urn:cartridge:1', 'hasWasteclass', 'MaxCountConstraintComponent', FILTER + 'CartridgeShape'),
    ('urn:cutter:1', 'hasXXXWorkpiece', 'MinCountConstraintComponent', BASE + 'MachineShape'),
    ('urn:filter:1', 'hasXXXWorkpiece', 'MinCountConstraintComponent', BASE + 'MachineShape'),
}


def test_corpus_violations_are_exactly_the_known_ones(corpus):
    report = validate_package(corpus)
    assert set(report.keys()) == EXPECTED


def test_the_wasteclass_violation_is_the_rule_writeback_divergence(corpus):
    """A sh:rule constructs a second hasWasteclass.

    In RDF that is an added triple, so the attribute now has two values and
    maxCount 1 fires. As an NGSI-LD update it would REPLACE the value that was
    there. Applying update semantics between rule iterations is the `rule_output`
    transform, which lands with the fixpoint in M3 -- so this violation is
    expected today and is the test that will invert when M3 arrives.
    """
    report = validate_package(corpus)
    hits = [r for r in report.violations if r.attribute == 'hasWasteclass']
    assert len(hits) == 1
    assert hits[0].resource == 'urn:cartridge:1'


def test_the_workpiece_violations_are_the_documented_sub_attribute_ones(corpus):
    """MachineShape requires hasState -> hasXXXWorkpiece [1,1].

    Only urn:plasmacutter:1 carries it, so cutter:1 and filter:1 correctly
    report. kms-constraints/kms/README.md documents the same two.
    """
    report = validate_package(corpus)
    hits = {r.resource for r in report.violations if r.attribute == 'hasXXXWorkpiece'}
    assert hits == {'urn:cutter:1', 'urn:filter:1'}


def test_no_result_is_unattributable(corpus):
    """Every result maps to an entity.

    A result that cannot be attributed is reported NOT_EVALUATED rather than
    dropped, so this asserts the normaliser handled every shape in the corpus.
    """
    report = validate_package(corpus)
    assert [r for r in report.results if r.status is Status.NOT_EVALUATED] == []


def test_report_accounts_for_every_applicable_constraint(corpus):
    """V1, now established rather than deferred.

    Was `complete is False` while the applicable-set enumerator was M2 work.
    It exists now, so the report states conformance instead of leaving it to be
    inferred from silence -- and `complete` is the claim that every reported
    result mapped onto an enumerated pair.
    """
    report = validate_package(corpus)
    assert report.complete is True
    assert len(report.conformant) > len(report.violations)
    assert len(report.evaluated) == len(report.conformant) + len(report.violations)


def test_shape_names_are_stable_not_blank_node_labels(corpus):
    """Result identity must not contain a blank node label (H4).

    pyshacl reports sh:sourceShape, which for a nested property shape is an
    anonymous node whose label changes between runs. Identity resolves to the
    enclosing named shape instead.
    """
    first = validate_package(corpus).keys()
    second = validate_package(corpus).keys()
    assert first == second
    for _, _, _, shape in first:
        assert shape.startswith('http'), 'shape identity must be an IRI, not a blank node label'
        assert shape.endswith('Shape')


def test_the_two_cartridge_shapes_stay_distinct(corpus):
    """base_shacl:CartridgeShape and filter_shacl:CartridgeShape are different.

    They share a local name. Identity is the IRI precisely so their verdicts
    are never merged.
    """
    from semforge.validate.shapes import node_shapes
    names = [str(s) for s in node_shapes(corpus.shapes) if str(s).endswith('CartridgeShape')]
    assert len(names) == 2
    assert len({n.rsplit('/', 1)[-1] for n in names}) == 1
