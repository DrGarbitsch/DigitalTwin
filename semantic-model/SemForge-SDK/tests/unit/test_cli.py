"""The CLI. Exit codes are the CI contract: 0 clean, 1 violations, 2 bad package."""

from click.testing import CliRunner

from semforge.cli import cli


def test_validate_reports_violations_and_exits_1(corpus_path):
    result = CliRunner().invoke(cli, ['validate', corpus_path])
    assert result.exit_code == 1
    assert 'CartridgeShape' in result.output
    assert '3 violations' in result.output


def test_validate_reports_the_view_and_what_it_removed(corpus_path):
    """The view builder removes data, so every run says what it removed."""
    result = CliRunner().invoke(cli, ['validate', corpus_path])
    assert 'view=current' in result.output
    assert 'collapsed=3' in result.output


def test_validate_warns_that_conformance_is_not_yet_established(corpus_path):
    result = CliRunner().invoke(cli, ['validate', corpus_path])
    assert 'violations only' in result.output


def test_bad_package_exits_2(tmp_path):
    result = CliRunner().invoke(cli, ['validate', str(tmp_path)])
    assert result.exit_code == 2
    assert 'package error' in result.output


def test_missing_path_is_rejected_by_the_parser():
    result = CliRunner().invoke(cli, ['validate', '/nonexistent/path'])
    assert result.exit_code == 2
