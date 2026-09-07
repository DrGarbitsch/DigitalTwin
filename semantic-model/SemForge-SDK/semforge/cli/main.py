"""semforge command line.

Exit codes are the CI contract:
  0 conformant   1 violations   2 package invalid   3 internal
"""

import os
import sys

import click
from rdflib import Graph

from .. import __version__
from ..errors import CapabilityError, PackageError
from ..expect import (coverage, load_expectations, run_tests,
                      save_expectations)
from ..expect.store import Example
from ..package import load
from ..validate import validate_package
from ..validate.orchestrator import validate_graphs


@click.group()
@click.version_option(__version__)
def cli():
    """SemForge: offline authoring and validation of semantic packages."""


@cli.command()
@click.argument('path', type=click.Path(exists=True), default='.')
@click.option('--no-strict', is_flag=True,
              help='report view-declaration problems instead of failing on them')
def validate(path, no_strict):
    """Validate a package's examples against its shapes."""
    try:
        package = load(path)
        report = validate_package(package, strict=not no_strict)
    except PackageError as exc:
        click.echo(f'package error: {exc}', err=True)
        sys.exit(2)
    except CapabilityError as exc:
        click.echo(str(exc), err=True)
        sys.exit(2)

    for stats in report.view_stats:
        detail = [f'view={stats.view.value}']
        if stats.collapsed:
            detail.append(f'collapsed={stats.collapsed} attribute instances')
        if stats.empty_lists:
            detail.append(f'empty-lists={stats.empty_lists}')
        click.echo('  '.join(detail))

    for result in sorted(report.violations, key=lambda r: r.key()):
        click.echo(f'{result.severity:>9}  {result.resource}  '
                   f'{result.component}({result.attribute})  [{result.shape_name}]')

    count = len(report.violations)
    click.echo(f'\n{len(report.evaluated)} constraints evaluated, '
               f'{count} violation{"" if count == 1 else "s"}')
    if not report.complete:
        # V1: a report that cannot account for every applicable constraint must
        # say so. Silence is never success.
        for diagnostic in report.diagnostics:
            click.echo(f'  {diagnostic}', err=True)
        click.echo('note: this report is INCOMPLETE -- conformance cannot be '
                   'trusted for the shapes above.', err=True)
    sys.exit(1 if count else 0)


def _examples_and_reports(package, expectations):
    """Every declared example paired with its report.

    A package with no expectation file is still testable: its own model is the
    single example, so `semforge test` works before anything is declared.
    """
    if not expectations.examples:
        default = Example(path=os.path.relpath(package.sources['model'], package.path))
        return [(default, validate_package(package))]

    paired = []
    for example in expectations.examples:
        graph = Graph()
        graph.parse(os.path.join(package.path, example.path), format='json-ld')
        paired.append((example, validate_graphs(
            graph, package.shapes, package.knowledge)))
    return paired


@cli.command()
@click.argument('path', type=click.Path(exists=True), default='.')
@click.option('--coverage', 'want_coverage', is_flag=True,
              help='report which constraints are exercised, and on which side')
@click.option('--fail-on', type=click.Choice(['no-firing-example',
                                              'no-conforming-example']),
              help='treat that coverage status as a failure')
def test(path, want_coverage, fail_on):
    """Run a package's examples against its declared expectations."""
    try:
        package = load(path)
        expectations = load_expectations(path)
        paired = _examples_and_reports(package, expectations)
    except (PackageError, CapabilityError) as exc:
        click.echo(str(exc), err=True)
        sys.exit(2)

    failed = 0
    for outcome in run_tests(paired):
        if outcome.passed:
            click.echo(f'ok    {outcome.example}')
            continue
        failed += 1
        click.echo(f'FAIL  {outcome.example}')
        for failure in outcome.failures:
            click.echo(f'        {failure}')

    if want_coverage:
        click.echo('\nCoverage')
        for entry in coverage(paired):
            marker = {'two-sided': '  ok  ', 'no-firing-example': '  !!  ',
                      'no-conforming-example': '  ..  '}[entry.status]
            click.echo(f'{marker}{entry.constraint}  [{entry.status}]')
        if fail_on:
            offenders = [e for e in coverage(paired) if e.status == fail_on]
            if offenders:
                click.echo(f'\n{len(offenders)} constraint(s) are {fail_on}', err=True)
                failed += len(offenders)

    sys.exit(1 if failed else 0)


@cli.command()
@click.argument('path', type=click.Path(exists=True), default='.')
def accept(path):
    """Record the current residue of every example as expected."""
    try:
        package = load(path)
        expectations = load_expectations(path)
        paired = _examples_and_reports(package, expectations)
    except (PackageError, CapabilityError) as exc:
        click.echo(str(exc), err=True)
        sys.exit(2)

    changed = 0
    outcomes = {o.example: o for o in run_tests(paired)}
    for example, _ in paired:
        outcome = outcomes[example.path]
        if example.residue != outcome.residue:
            example.residue = outcome.residue
            changed += 1
    if not expectations.examples:
        expectations.examples = [example for example, _ in paired]
    save_expectations(expectations)
    click.echo(f'accepted residue for {changed} example(s) -> {expectations.path}')
