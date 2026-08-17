#!/usr/bin/env python3
#
# Copyright (c) 2025 Intel Corporation
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
"""Regression runner for the OPC UA validation-rule suites under validation/specs/.

Each specification (OPC UA Part 3 today, companion specifications later) owns a
directory holding a machine-readable rule manifest, one SHACL shape per rule,
and -- for every implemented rule -- four NodeSet2 XML fixtures: two that must
pass and two that must fail. This script turns that tree into a test run.

Per test case it does what a user would do by hand:

    nodeset2owl.py <case>.NodeSet2.xml -i <ns0-subset>.ttl -o <case>.owl.ttl
    validate.py -m ontology -ni -s <rule>.shacl.ttl <case+ns0 merged>.ttl

so the suite exercises the real translation and the real CLI, not a
reimplementation of either. Nothing is downloaded except the OPC UA Types XSD
that nodeset2owl.py already fetches for value parsing.

Two checks run over the fixtures
--------------------------------
**Targeted** -- every ``fail-*`` fixture is validated against its own rule's
shape and must produce exactly the violations recorded in the neighbouring
``.expected`` file (focus nodes and messages). Every ``pass-*`` fixture is
validated against the same shape and must conform. This is what proves a rule
detects what it claims to detect.

**Cross** -- every ``pass-*`` fixture of *every* rule is additionally validated
against the merged shape set of the whole specification, and must still
conform. This is the part that compounds: each new passing nodeset added for
one rule immediately becomes a false-positive guard for every rule already in
the suite, so the corpus gets better at catching regressions as it grows. Skip
it with --no-cross when iterating on a single rule.

The data graph under validation is the NS0 subset *plus* the fixture, because
almost every Part 3 rule is phrased in terms of NS0 nodes. That means the real
(if pruned) Namespace 0 content is held to the same shapes as the fixtures --
a shape that false-positives on the spec's own nodes fails the suite.
"""

import argparse
import json
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
OPCUA_DIR = HERE.parent
NODESET2OWL = OPCUA_DIR / 'nodeset2owl.py'
VALIDATE = OPCUA_DIR / 'validate.py'
SPECS_DIR = HERE / 'specs'
BUILD_DIR = HERE / '.build'

# The manifest is a JSON-LD document. It is the single source for both readers:
# this runner loads it as JSON, and rdflib loads the same bytes as RDF, so
# there is no generated copy of the catalog to fall out of date.
MANIFEST_NAME = 'spec.jsonld'

# Translated forms a shape can be written against. A shape declares its own with
# opcv:representation; see validation/vocabulary.ttl.
#
# Only OpcUaOwl has a pipeline here. NgsiLd fixtures would go through
# owl2instances.py and be validated with `validate.py -m instance` against
# NGSI-LD entities, whose Properties and ListParameters carry values instead of
# the Node-and-Reference structure the OWL form keeps -- so a shape written for
# one form shares nothing with a shape written for the other, not even its
# target class. owl2instances.py is not on this branch, which is the immediate
# reason the pipeline is declared rather than built.
KNOWN_REPRESENTATIONS = {
    'opcv:OpcUaOwl': 'nodeset2owl.py output, validated with validate.py -m ontology',
    'opcv:NgsiLd': 'owl2instances.py output, validated with validate.py -m instance',
    'opcv:NgsiLdTemporal': 'NGSI-LD carrying per-instance ngsild:observedAt -- time as ordinary data',
}
RUNNABLE_REPRESENTATIONS = {'opcv:OpcUaOwl'}

# Fixture filenames declare their own expectation, so a case can never be
# silently mis-filed: the prefix is the assertion.
PASS_PREFIX = 'pass-'
FAIL_PREFIX = 'fail-'

# Every fixture is translated on its own and is only ever merged with the NS0
# subset (which uses "opcua"), so a single fixed prefix cannot collide, and it
# keeps the build artefacts readable when a shape has to be debugged by hand.
FIXTURE_PREFIX = 'fixture'

# validate.py reports violations as "Focus Node:"/"Message:" lines (both the
# direct-SPARQL path in lib/shacl.py and pySHACL's own report use them). Those
# two facts -- which node, and why -- are what the .expected files pin down;
# everything else in the report is formatting that would make the fixtures
# brittle for no gain.
REPORT_LINE = re.compile(r'^\s*(Focus Node|Message):\s*(.*)$')


class TestFailure(Exception):
    """A fixture did not behave as its filename and .expected file require."""


def run(cmd, cwd=None):
    """Run `cmd`, returning (returncode, combined output)."""
    proc = subprocess.run(
        [str(part) for part in cmd],
        cwd=str(cwd) if cwd else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return proc.returncode, proc.stdout


def python_exe():
    """Interpreter used for the child tools -- the one running this script."""
    return sys.executable


def is_stale(target, *sources):
    """True if `target` is missing or older than any of `sources`.

    Conversions dominate the suite's runtime, so results are reused across runs
    unless an input actually changed.
    """
    if not target.exists():
        return True
    target_mtime = target.stat().st_mtime
    return any(source.stat().st_mtime > target_mtime for source in sources)


def convert(nodeset, output, prefix, inputs=()):
    """Translate a NodeSet2 XML fixture to OWL Turtle via nodeset2owl.py."""
    output.parent.mkdir(parents=True, exist_ok=True)
    cmd = [python_exe(), NODESET2OWL, nodeset, '-p', prefix, '-o', output]
    for item in inputs:
        cmd += ['-i', str(item)]
    code, out = run(cmd, cwd=OPCUA_DIR)
    if code != 0:
        raise TestFailure(f'nodeset2owl.py failed for {nodeset.name}:\n{out}')
    return output


def merge_turtle(output, *sources):
    """Concatenate Turtle `sources` into `output` as one graph.

    Turtle is append-safe: each source carries its own @prefix directives and
    re-declaring a prefix is legal, so concatenating the raw text yields the
    union of the graphs without needing to parse and re-serialise them. Doing
    it textually keeps this a fast file operation rather than an rdflib
    round-trip per test case.
    """
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text('\n'.join(source.read_text() for source in sources))
    return output


def validate(data, shapes):
    """Run validate.py in ontology mode; return (conforms, report lines).

    ``-ni`` suppresses owl:imports resolution: the fixture's imports point at
    the NS0 subset (already merged into `data`) and at the remote base
    ontology, which the shapes deliberately do not depend on. Keeping imports
    off is what makes a suite run hermetic and fast.
    """
    code, out = run([python_exe(), VALIDATE, '-s', shapes, '-m', 'ontology', '-ni', data], cwd=OPCUA_DIR)
    match = re.search(r'^Validation Conforms:\s*(True|False)\s*$', out, re.MULTILINE)
    if match is None:
        raise TestFailure(f'validate.py produced no verdict for {Path(data).name}:\n{out}')
    conforms = match.group(1) == 'True'
    # Exit code 1 is validate.py's way of signalling non-conformance; any other
    # non-zero code means the tool itself broke and must not read as a finding.
    if code not in (0, 1):
        raise TestFailure(f'validate.py errored for {Path(data).name}:\n{out}')
    return conforms, extract_report(out)


def extract_report(output):
    """Reduce a validate.py report to a sorted, de-duplicated finding list."""
    lines = set()
    for line in output.splitlines():
        match = REPORT_LINE.match(line)
        if match:
            lines.add(f'{match.group(1)}: {match.group(2).strip()}')
    return sorted(lines)


class Rule:
    """One catalog rule: its shape, its fixtures, and its expectations."""

    def __init__(self, spec, entry):
        self.spec = spec
        self.id = entry['id']
        self.section = entry.get('section', '')
        self.summary = entry.get('summary', '')
        self.status = entry.get('status', 'implemented')
        # Compact IRI as written in the manifest, e.g. "rule:AS-039". Kept so
        # check_identity can confirm it agrees with the id beside it -- the one
        # place the JSON-LD form repeats itself.
        self.iri = entry.get('@id')
        self.shape = spec.root / entry['shape'] if entry.get('shape') else None
        self.testcases = spec.root / 'testcases' / self.id
        # Which model kind(s) the rule constrains: the specification's own type
        # definitions, a model that instantiates them, or both. Empty means
        # unclassified, which the fixture layout then treats as "one set".
        self.applies_to = entry.get('appliesTo') or []
        # Representations in which the rule is answerable at all. Stated only
        # where that is representation-dependent -- a rule about change over
        # time is unanswerable against a NodeSet2 and routine against NGSI-LD
        # with observedAt. Absent means the status holds everywhere.
        self.checkable_in = entry.get('checkableIn') or []

    @property
    def implemented(self):
        return self.shape is not None

    def fixture_sets(self):
        """Fixtures grouped by the model kind they exercise.

        A rule constraining both kinds needs two fixture sets, because the two
        are different graphs: a TypeModel fixture defines ObjectTypes and
        InstanceDeclarations, an InstanceModel fixture instantiates them. They
        cannot share a nodeset and they cannot share a shape either -- one
        targets InstanceDeclarations, the other has to exclude them.

        So such a rule lays its fixtures out per kind:

            testcases/PU-001/TypeModel/pass-1-....NodeSet2.xml
            testcases/PU-001/InstanceModel/fail-1-....NodeSet2.xml

        A rule constraining one kind keeps the flat layout, which is every rule
        in the suite today.
        """
        if not self.testcases.is_dir():
            return {}
        subdirectories = [path for path in sorted(self.testcases.iterdir()) if path.is_dir()]
        if subdirectories:
            return {path.name: sorted(path.glob('*.NodeSet2.xml')) for path in subdirectories}
        flat = sorted(self.testcases.glob('*.NodeSet2.xml'))
        return {'': flat} if flat else {}

    def fixtures(self):
        return [path for paths in self.fixture_sets().values() for path in paths]

    def check_identity(self):
        """Enforce the URN scheme: a shape names itself, and names its rule.

        Shape files are edited by hand while the manifest is edited separately,
        so the two drift unless something compares them. Checked textually
        rather than by parsing RDF, because the runner otherwise needs no graph
        library and shells out for everything that does.

        See validation/vocabulary.ttl for the scheme.
        """
        if self.spec.document is None:
            return [f'{self.id}: {MANIFEST_NAME} has no documentNumber, so IRIs cannot be checked']

        problems = []
        # "rule:AS-039" against the id "AS-039" beside it. JSON-LD cannot build
        # an @id from two sibling fields, and relative IRIs do not resolve
        # against a urn: base, so the rule ID is written twice in one object.
        # Cheap to write, cheap to check, and this is the check.
        if self.iri != f'rule:{self.id}':
            problems.append(
                f'{self.id}: manifest @id is "{self.iri}", expected "rule:{self.id}"')

        # checkableIn names representations, and a typo here would quietly claim
        # a rule is answerable somewhere that does not exist.
        for representation in self.checkable_in:
            if f'opcv:{representation}' not in KNOWN_REPRESENTATIONS:
                problems.append(
                    f'{self.id}: checkableIn names unknown representation "{representation}"; '
                    f'known: {", ".join(sorted(k.split(":")[1] for k in KNOWN_REPRESENTATIONS))}')

        if self.shape is None or not self.shape.is_file():
            return problems

        text = self.shape.read_text()
        expected_prefix = f'urn:opcua:validation:shape:{self.spec.document}:{self.id}'
        expected_rule = f'<urn:opcua:validation:rule:{self.spec.document}:{self.id}>'

        subjects = re.findall(r'^<([^>]+)>\s+a\s+sh:NodeShape', text, re.MULTILINE)
        if not subjects:
            problems.append(
                f'{self.id}: {self.shape.name} declares no sh:NodeShape with an absolute IRI '
                f'subject. Shapes used to mint names in the base: vocabulary namespace; they '
                f'now carry their own URN.')
        for subject in subjects:
            # A rule needing several target classes is split across node shapes,
            # so a ":<part>" suffix is expected -- anything else is a typo or a
            # shape filed under the wrong rule.
            if subject != expected_prefix and not subject.startswith(expected_prefix + ':'):
                problems.append(
                    f'{self.id}: shape IRI <{subject}> does not match '
                    f'<{expected_prefix}> or <{expected_prefix}:PART>')
        if expected_rule not in text:
            problems.append(
                f'{self.id}: {self.shape.name} never links itself to its rule with '
                f'opcv:implementsRule {expected_rule}')

        # Every node shape says which translated form it matches, and there is
        # one declaration per shape. A shape without one would be run against
        # whatever the runner happens to build, which is the mistake this whole
        # facet exists to prevent.
        declared = re.findall(r'opcv:representation\s+(\S+?)\s*[;.]', text)
        if len(declared) != len(subjects):
            problems.append(
                f'{self.id}: {self.shape.name} declares {len(subjects)} node shape(s) but '
                f'{len(declared)} opcv:representation -- one is needed per shape')
        for representation in set(declared):
            if representation not in KNOWN_REPRESENTATIONS:
                problems.append(
                    f'{self.id}: unknown opcv:representation {representation}; '
                    f'known: {", ".join(sorted(KNOWN_REPRESENTATIONS))}')
            elif representation not in RUNNABLE_REPRESENTATIONS:
                problems.append(
                    f'{self.id}: {self.shape.name} is written for {representation} '
                    f'({KNOWN_REPRESENTATIONS[representation]}), which this runner cannot build. '
                    f'Refusing to validate it against an {"/".join(sorted(RUNNABLE_REPRESENTATIONS))} '
                    f'graph, which is what running it anyway would do.')
        return problems

    def check_fixture_counts(self):
        """Enforce the suite's contract: two passing and two failing nodesets.

        Per model kind, not in total. A rule constraining both kinds with four
        fixtures between them has covered neither properly, and totalling them
        would hide that.
        """
        problems = []
        sets = self.fixture_sets()

        declared = set(self.applies_to)
        if declared and len(declared) > 1:
            missing = declared - set(sets)
            if missing:
                problems.append(
                    f'{self.id}: appliesTo names {", ".join(sorted(declared))} but there is no '
                    f'testcases/{self.id}/{"/, ".join(sorted(missing))}/ directory')
        for kind in sets:
            if kind and declared and kind not in declared:
                problems.append(
                    f'{self.id}: fixture directory "{kind}" is not in appliesTo '
                    f'({", ".join(sorted(declared)) or "unset"})')

        for kind, paths in sorted(sets.items()):
            where = f'{self.id}/{kind}' if kind else self.id
            names = [path.name for path in paths]
            passes = [name for name in names if name.startswith(PASS_PREFIX)]
            fails = [name for name in names if name.startswith(FAIL_PREFIX)]
            if len(passes) < 2:
                problems.append(f'{where}: expected at least 2 "{PASS_PREFIX}" nodesets, found {len(passes)}')
            if len(fails) < 2:
                problems.append(f'{where}: expected at least 2 "{FAIL_PREFIX}" nodesets, found {len(fails)}')
            for name in names:
                if not name.startswith((PASS_PREFIX, FAIL_PREFIX)):
                    problems.append(
                        f'{where}: fixture "{name}" must start with "{PASS_PREFIX}" or "{FAIL_PREFIX}"')
        return problems


class Spec:
    """A specification directory: manifest, shapes, shared NS0 nodeset, rules."""

    def __init__(self, root):
        self.root = root
        # A JSON-LD document, and plain JSON at the same time: this reads it as
        # a dict and never resolves the @context, while rdflib reads the same
        # file as a graph. Terms the context does not map -- commonNodeset,
        # catalogCoverage and the rest -- are build inputs and are invisible to
        # the RDF reader by design.
        self.manifest = json.loads((root / MANIFEST_NAME).read_text())
        # The directory name is the id; the manifest no longer repeats it,
        # because "id" in this document means opcv:ruleId.
        self.id = root.name
        self.title = self.manifest.get('title', self.id)
        # OPC document number: the stable half of a specification's identity,
        # and what every rule and shape IRI is built from. Directory names and
        # titles in this tree have both changed once; 10000-3 has not.
        self.document = self.manifest.get('documentNumber')
        self.common_nodeset = root / self.manifest['commonNodeset']
        self.rules = [Rule(self, entry) for entry in self.manifest['rules']]
        self.build = BUILD_DIR / self.id

    @property
    def implemented_rules(self):
        return [rule for rule in self.rules if rule.implemented]

    def check_identity(self):
        """Check this specification's own IRI, and every rule's -- implemented
        or not.

        A catalogued rule has no shape to disagree with, but its @id can still
        be wrong, and it would then be wrong for however long it takes someone
        to implement it. Three of four specifications here are entirely
        catalogued, so checking only implemented rules would check almost
        nothing.
        """
        problems = []
        expected = f'spec:{self.document}'
        if self.document is None:
            problems.append(f'{self.id}: {MANIFEST_NAME} has no documentNumber')
        elif self.manifest.get('@id') != expected:
            problems.append(
                f'{self.id}: manifest @id is "{self.manifest.get("@id")}", expected "{expected}"')
        for rule in self.rules:
            problems.extend(rule.check_identity())
        return problems

    def common_ttl(self):
        """Translate (once) the shared NS0 subset every fixture is layered on."""
        target = self.build / 'common' / 'ns0-subset.ttl'
        if is_stale(target, self.common_nodeset):
            convert(self.common_nodeset, target, prefix='opcua')
        return target

    def merged_shapes(self):
        """Concatenate every implemented rule's shape into one shapes graph.

        Used by the cross check. SHACL node shapes are additive -- each targets
        its own classes -- so merging cannot create constraints that none of the
        individual files impose.
        """
        target = self.build / 'common' / 'all-shapes.shacl.ttl'
        shapes = [rule.shape for rule in self.implemented_rules]
        if not shapes:
            return None
        if is_stale(target, *shapes):
            merge_turtle(target, *shapes)
        return target

    def case_data(self, rule, fixture):
        """Build the data graph for one fixture: NS0 subset + the fixture itself."""
        common = self.common_ttl()
        case_ttl = self.build / rule.id / f'{fixture.stem}.owl.ttl'
        if is_stale(case_ttl, fixture, common):
            convert(fixture, case_ttl, prefix=FIXTURE_PREFIX, inputs=[common])
        merged = self.build / rule.id / f'{fixture.stem}.merged.ttl'
        if is_stale(merged, case_ttl, common):
            merge_turtle(merged, common, case_ttl)
        return merged


def expectation_path(fixture):
    """Path of the recorded findings for a failing fixture."""
    return fixture.with_suffix('.expected')


def check_targeted(spec, rule, fixture, update):
    """Assert one fixture behaves as its prefix (and .expected file) require."""
    data = spec.case_data(rule, fixture)
    conforms, report = validate(data, rule.shape)

    if fixture.name.startswith(PASS_PREFIX):
        if not conforms:
            raise TestFailure(
                f'{rule.id}/{fixture.name}: expected the nodeset to CONFORM to {rule.shape.name}, '
                f'but it reported:\n  ' + '\n  '.join(report))
        return

    if conforms:
        raise TestFailure(
            f'{rule.id}/{fixture.name}: expected the nodeset to VIOLATE {rule.shape.name}, but it conformed. '
            f'Either the fixture no longer plants the defect, or the shape stopped detecting it.')

    expected_file = expectation_path(fixture)
    if update:
        expected_file.write_text('\n'.join(report) + '\n')
        return
    if not expected_file.exists():
        raise TestFailure(
            f'{rule.id}/{fixture.name}: no {expected_file.name}. Re-run with --update-expectations '
            f'and review the recorded findings.')
    expected = [line for line in expected_file.read_text().splitlines() if line.strip()]
    if report != expected:
        raise TestFailure(
            f'{rule.id}/{fixture.name}: findings changed.\n'
            '  expected:\n    ' + '\n    '.join(expected) +
            '\n  actual:\n    ' + '\n    '.join(report))


def check_cross(spec, rule, fixture, all_shapes):
    """Assert a passing fixture conforms to the whole specification's shape set."""
    data = spec.case_data(rule, fixture)
    conforms, report = validate(data, all_shapes)
    if not conforms:
        raise TestFailure(
            f'{rule.id}/{fixture.name}: conforms to its own shape but VIOLATES another rule in {spec.id}. '
            'A shape is over-firing, or this "passing" nodeset is not actually spec-compliant:\n  ' +
            '\n  '.join(report))


def collect_specs(only_spec):
    specs = []
    for path in sorted(SPECS_DIR.iterdir()):
        if not (path / MANIFEST_NAME).is_file():
            continue
        if only_spec and path.name != only_spec:
            continue
        specs.append(Spec(path))
    return dependency_order(specs)


def dependency_order(specs):
    """Sort so a specification is always listed after the ones it builds on.

    Directory names sort alphabetically, which puts opc-10000-100-devices ahead
    of the opc-10000-3-address-space it depends on -- readable output would then
    contradict the dependency chain it is reporting. Ties keep alphabetical
    order so a run is reproducible.

    A dependency cycle, or a dependsOn naming a specification that is not
    present (a --spec filter is enough to cause that), leaves the remaining
    specs in alphabetical order rather than raising: ordering is presentational,
    and refusing to run over it would be a worse failure than printing it oddly.
    """
    # dependsOn holds compact spec IRIs ("spec:10000-3"), not directory names,
    # so that the same field is a real RDF link. Resolve through the document
    # number rather than the directory, which is exactly what changed last time.
    def iri_of(spec):
        return f'spec:{spec.document}'

    remaining = list(specs)
    ordered = []
    placed = set()
    while remaining:
        ready = [spec for spec in remaining
                 if all(dep in placed or dep not in {iri_of(s) for s in remaining}
                        for dep in spec.manifest.get('dependsOn') or [])]
        if not ready:
            ordered.extend(remaining)
            break
        ordered.extend(ready)
        placed.update(iri_of(spec) for spec in ready)
        remaining = [spec for spec in remaining if spec not in ready]
    return ordered


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('-s', '--spec', help='Only run this specification directory, e.g. opc-10000-3-address-space')
    parser.add_argument('-r', '--rule', help='Only run this rule, e.g. AS-008')
    parser.add_argument('-j', '--jobs', type=int, default=min(8, (os.cpu_count() or 2)),
                        help='Parallel test cases (default: one per core, capped at 8)')
    parser.add_argument('--no-cross', action='store_true',
                        help='Skip the cross check that validates every passing nodeset '
                             'against the whole specification shape set')
    parser.add_argument('--update-expectations', action='store_true',
                        help='Rewrite the .expected file of every failing fixture from the current '
                             'findings. Review the diff -- this is how a shape change is blessed.')
    parser.add_argument('--coverage', action='store_true',
                        help='Print rule coverage for each specification and exit')
    args = parser.parse_args()

    specs = collect_specs(args.spec)
    if not specs:
        print(f'No specification found under {SPECS_DIR}' + (f' named {args.spec}' if args.spec else ''))
        return 1

    if args.coverage:
        for spec in specs:
            report_coverage(spec)
        return 0

    # Asked for one rule: it lives in exactly one specification, so "absent from
    # this spec" is the normal case and only "absent from all of them" is an
    # error. Checking up front keeps the per-spec loop below free of it.
    if args.rule and not any(rule.id == args.rule
                             for spec in specs for rule in spec.implemented_rules):
        print(f'No implemented rule {args.rule} in ' + ', '.join(spec.id for spec in specs))
        return 1

    failures = []
    checks = 0
    for spec in specs:
        rules = spec.implemented_rules
        if args.rule:
            rules = [rule for rule in rules if rule.id == args.rule]

        print(f'=== {spec.title} ({spec.id}) ===')

        # Identity is checked for the whole specification, before the shapes
        # and independently of them: three of the four specifications here have
        # no implemented rule at all, and their IRIs still have to be right.
        identity_problems = spec.check_identity()
        if identity_problems:
            print(f'  FAIL  identity: {len(identity_problems)} problem(s)')
            failures.extend(identity_problems)

        # A specification whose rules are all catalogued but unimplemented is a
        # first-class state, not a broken directory: the prose catalog and the
        # manifest exist, no shape does yet. Stop before common_ttl(), which
        # would otherwise demand a baseline nodeset that phase 1 has not
        # materialised.
        if not rules:
            print(f'  --    {len(spec.rules)} rule(s) catalogued, none implemented yet\n')
            continue

        # Kept per rule rather than thrown straight onto `failures`, so a rule
        # missing a fixture is shown as FAIL on its own line instead of only in
        # the summary, where it reads as a failure of some other rule.
        # Identity was already checked for every rule above, implemented or not.
        count_problems = {rule.id: rule.check_fixture_counts() for rule in rules}

        # Warm the shared artefacts before fanning out, so parallel workers
        # never race to build the same NS0 translation.
        spec.common_ttl()
        all_shapes = spec.merged_shapes()

        jobs = []
        for rule in rules:
            for fixture in rule.fixtures():
                jobs.append(('targeted', rule, fixture))
                if not args.no_cross and fixture.name.startswith(PASS_PREFIX) and all_shapes:
                    jobs.append(('cross', rule, fixture))

        # The conversions are the expensive part and each writes to its own
        # path, so a thread pool over subprocess calls is enough here.
        def execute(job):
            kind, rule, fixture = job
            try:
                if kind == 'targeted':
                    check_targeted(spec, rule, fixture, args.update_expectations)
                else:
                    check_cross(spec, rule, fixture, all_shapes)
            except TestFailure as err:
                return f'[{kind}] {err}'
            return None

        with ThreadPoolExecutor(max_workers=max(1, args.jobs)) as pool:
            results = list(pool.map(execute, jobs))

        checks += len(jobs)
        for rule in rules:
            rule_failures = count_problems[rule.id] + [
                result for result, job in zip(results, jobs)
                if result and job[1].id == rule.id
            ]
            status = 'FAIL' if rule_failures else 'ok'
            print(f'  {status:>4}  {rule.id}  {rule.summary}')
            failures.extend(rule_failures)

    print()
    if failures:
        print(f'{len(failures)} failure(s) out of {checks} check(s):\n')
        for failure in failures:
            print(f'- {failure}\n')
        return 1
    print(f'All {checks} check(s) passed.')
    return 0


def report_coverage(spec):
    """Print how much of a specification's rule catalog this suite enforces.

    The manifest lists the rules that have a shape; the rules that do not are
    left in the prose catalog it points at, together with the reason each one
    is still open (checkable but unwritten, blocked on an Attribute the
    translation drops, or a cross-consistency check too large for a shape).
    Duplicating that backlog here would only let the two copies drift, so the
    denominator is a count taken from the catalog and the gap list stays in it.
    """
    implemented = spec.implemented_rules
    total = spec.manifest.get('catalogRuleCount')
    fixtures = sum(len(rule.fixtures()) for rule in implemented)

    print(f'=== {spec.title} ({spec.id}) ===')
    print(f'  catalog           : {spec.manifest.get("catalog", "(none)")}')
    depends = spec.manifest.get('dependsOn') or []
    print(f'  builds on         : {", ".join(depends) if depends else "(nothing)"}')
    if total:
        print(f'  rules enforced    : {len(implemented)} of {total}')
    else:
        print(f'  rules enforced    : {len(implemented)}')
    print(f'  nodeset fixtures  : {fixtures}')
    print()
    for rule in implemented:
        names = [path.name for path in rule.fixtures()]
        passes = sum(1 for name in names if name.startswith(PASS_PREFIX))
        fails = sum(1 for name in names if name.startswith(FAIL_PREFIX))
        print(f'  {rule.id}  {passes} pass / {fails} fail   {rule.section:<18} {rule.summary}')
    print()


if __name__ == '__main__':
    sys.exit(main())
