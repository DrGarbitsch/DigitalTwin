"""semforge command line.

Exit codes are the CI contract:
  0 conformant   1 violations   2 package invalid   3 internal
"""

import sys

import click

from .. import __version__
from ..errors import CapabilityError, PackageError
from ..package import load
from ..validate import validate_package


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
                   f'{result.component}({result.attribute})  [{result.shape}]')

    count = len(report.violations)
    click.echo(f'\n{count} violation{"" if count == 1 else "s"}')
    if not report.complete:
        # V1: a report that cannot account for every applicable constraint must
        # say so. Silence is never success.
        click.echo('note: conformant/not-applicable statuses are not yet '
                   'established (applicable-set enumerator is M2); this run '
                   'reports violations only.')
    sys.exit(1 if count else 0)
