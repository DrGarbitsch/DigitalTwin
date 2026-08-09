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
        self.shape = spec.root / entry['shape'] if entry.get('shape') else None
        self.testcases = spec.root / 'testcases' / self.id

    @property
    def implemented(self):
        return self.shape is not None

    def fixtures(self):
        if not self.testcases.is_dir():
            return []
        return sorted(self.testcases.glob('*.NodeSet2.xml'))

    def check_fixture_counts(self):
        """Enforce the suite's contract: two passing and two failing nodesets."""
        names = [path.name for path in self.fixtures()]
        passes = [name for name in names if name.startswith(PASS_PREFIX)]
        fails = [name for name in names if name.startswith(FAIL_PREFIX)]
        problems = []
        if len(passes) < 2:
            problems.append(f'{self.id}: expected at least 2 "{PASS_PREFIX}" nodesets, found {len(passes)}')
        if len(fails) < 2:
            problems.append(f'{self.id}: expected at least 2 "{FAIL_PREFIX}" nodesets, found {len(fails)}')
        for name in names:
            if not name.startswith((PASS_PREFIX, FAIL_PREFIX)):
                problems.append(f'{self.id}: fixture "{name}" must start with "{PASS_PREFIX}" or "{FAIL_PREFIX}"')
        return problems


class Spec:
    """A specification directory: manifest, shapes, shared NS0 nodeset, rules."""

    def __init__(self, root):
        self.root = root
        self.manifest = json.loads((root / 'spec.json').read_text())
        self.id = self.manifest['id']
        self.title = self.manifest.get('title', self.id)
        self.common_nodeset = root / self.manifest['commonNodeset']
        self.rules = [Rule(self, entry) for entry in self.manifest['rules']]
        self.build = BUILD_DIR / self.id

    @property
    def implemented_rules(self):
        return [rule for rule in self.rules if rule.implemented]

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
            f'  expected:\n    ' + '\n    '.join(expected) +
            f'\n  actual:\n    ' + '\n    '.join(report))


def check_cross(spec, rule, fixture, all_shapes):
    """Assert a passing fixture conforms to the whole specification's shape set."""
    data = spec.case_data(rule, fixture)
    conforms, report = validate(data, all_shapes)
    if not conforms:
        raise TestFailure(
            f'{rule.id}/{fixture.name}: conforms to its own shape but VIOLATES another rule in {spec.id}. '
            f'A shape is over-firing, or this "passing" nodeset is not actually spec-compliant:\n  '
            + '\n  '.join(report))


def collect_specs(only_spec):
    specs = []
    for path in sorted(SPECS_DIR.iterdir()):
        if not (path / 'spec.json').is_file():
            continue
        if only_spec and path.name != only_spec:
            continue
        specs.append(Spec(path))
    return specs


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('-s', '--spec', help='Only run this specification directory, e.g. core-part3')
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

    failures = []
    checks = 0
    for spec in specs:
        rules = [rule for rule in spec.rules if rule.implemented]
        if args.rule:
            rules = [rule for rule in rules if rule.id == args.rule]
            if not rules:
                print(f'No implemented rule {args.rule} in {spec.id}')
                return 1

        print(f'=== {spec.title} ({spec.id}) ===')
        for rule in rules:
            failures.extend(rule.check_fixture_counts())

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
            rule_failures = [
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
    """Print how much of a specification's catalog is enforced by a shape."""
    print(f'=== {spec.title} ({spec.id}) ===')
    by_status = {}
    for rule in spec.rules:
        by_status.setdefault(rule.status, []).append(rule)
    implemented = spec.implemented_rules
    print(f'  rules in manifest : {len(spec.rules)}')
    print(f'  enforced by shape : {len(implemented)}')
    for status, rules in sorted(by_status.items()):
        print(f'    {status:<24} {len(rules):>3}  {", ".join(rule.id for rule in rules)}')
    fixtures = sum(len(rule.fixtures()) for rule in implemented)
    print(f'  nodeset fixtures  : {fixtures}')
    print()


if __name__ == '__main__':
    sys.exit(main())
