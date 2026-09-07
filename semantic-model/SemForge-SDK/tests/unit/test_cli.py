"""The CLI. Exit codes are the CI contract: 0 clean, 1 violations, 2 bad package."""

from click.testing import CliRunner

from semforge.cli import cli


def test_validate_reports_violations_and_exits_1(corpus_path):
    result = CliRunner().invoke(cli, ['validate', corpus_path])
    assert result.exit_code == 1
    assert 'MachineShape' in result.output
    assert '2 violations' in result.output


def test_validate_reports_the_view_and_what_it_removed(corpus_path):
    """The view builder removes data, so every run says what it removed."""
    result = CliRunner().invoke(cli, ['validate', corpus_path])
    assert 'view=current' in result.output
    assert 'collapsed=3' in result.output


def test_validate_states_conformance_rather_than_implying_it(corpus_path):
    """Was a warning that conformance was not established; M2 established it."""
    result = CliRunner().invoke(cli, ['validate', corpus_path])
    assert 'constraints evaluated' in result.output
    assert 'INCOMPLETE' not in result.output


def test_bad_package_exits_2(tmp_path):
    result = CliRunner().invoke(cli, ['validate', str(tmp_path)])
    assert result.exit_code == 2
    assert 'package error' in result.output


def test_missing_path_is_rejected_by_the_parser():
    result = CliRunner().invoke(cli, ['validate', '/nonexistent/path'])
    assert result.exit_code == 2


def test_test_command_runs_and_reports_coverage(corpus_path):
    result = CliRunner().invoke(cli, ['test', corpus_path, '--coverage'])
    assert 'Coverage' in result.output
    assert 'no-firing-example' in result.output


def test_test_command_fail_on_turns_coverage_into_a_failure(corpus_path):
    clean = CliRunner().invoke(cli, ['test', corpus_path])
    gated = CliRunner().invoke(cli, [
        'test', corpus_path, '--coverage', '--fail-on', 'no-firing-example'])
    assert gated.exit_code == 1
    assert 'no-firing-example' in gated.output
    assert clean.exit_code in (0, 1)


def test_validate_reports_how_many_constraints_were_evaluated(corpus_path):
    """V1 surfaced: the count is stated, not left as silence."""
    result = CliRunner().invoke(cli, ['validate', corpus_path])
    assert 'constraints evaluated' in result.output


def test_accept_writes_the_residue(tmp_path, corpus_path):
    import os
    import shutil
    package = tmp_path / 'pkg'
    package.mkdir()
    for name in ('knowledge.ttl', 'shacl.ttl', 'model-instance.jsonld'):
        shutil.copy(os.path.join(corpus_path, name), package / name)

    result = CliRunner().invoke(cli, ['accept', str(package)])
    assert result.exit_code == 0
    written = (package / 'expectations' / 'validation.yaml').read_text()
    assert 'sha256:' in written

    # Second accept is a no-op: nothing changed, so nothing to accept.
    again = CliRunner().invoke(cli, ['accept', str(package)])
    assert 'accepted residue for 0 example(s)' in again.output
