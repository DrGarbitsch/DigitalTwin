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

"""Verdicts: validation once per package version, in the background.

A click on a class used to validate the whole package inside the request --
15 s on the OPC UA pump package, again for every class. A page now shows its
structure at once and the verdicts when they are in.
"""

import shutil
import threading

import pytest

from semforge.editor.verdicts import (VerdictService, Verdicts, compute, from_json,
                                      in_process, to_json)
from semforge.package import load


@pytest.fixture
def package(tmp_path, corpus_path):
    copy = tmp_path / 'pkg'
    shutil.copytree(corpus_path, copy, ignore=shutil.ignore_patterns('.semforge'))
    return load(str(copy))


def test_the_main_model_and_every_case_are_validated(package):
    from semforge.expect.store import load_expectations

    verdicts = compute(package, 'v1')
    assert verdicts.stamp == 'v1'
    assert len(verdicts.model.violations) == 3          # the kms's known three
    assert set(verdicts.cases) == {e.path for e in load_expectations(package.path).examples}


def test_they_survive_json(package):
    verdicts = compute(package, 'v1')
    again = from_json(to_json(verdicts))
    assert again.model.keys() == verdicts.model.keys()
    assert again.model.results == verdicts.model.results
    assert {p: r.keys() for p, r in again.cases.items()} == \
        {p: r.keys() for p, r in verdicts.cases.items()}


class Fake:
    """A package whose version and validation the test controls."""

    def __init__(self):
        self.stamp = 'v1'
        self.runs = []
        self.gate = threading.Event()
        self.gate.set()
        self.fail = None

    def fingerprint(self, root):
        return self.stamp

    def run(self, root, stamp):
        self.gate.wait(10)
        self.runs.append(stamp)
        if self.fail:
            raise RuntimeError(self.fail)
        from semforge.validate.results import Report
        return Verdicts(stamp=stamp, model=Report())


def _service(fake, notified=None):
    return VerdictService(fake.fingerprint, fake.run,
                          notify=lambda root, state: (notified if notified is not None
                                                      else []).append(state.state),
                          use_disk=False)


def test_a_page_never_waits_and_hears_when_they_are_in():
    fake, notified = Fake(), []
    fake.gate.clear()
    service = _service(fake, notified)

    verdicts, state = service.get('/pkg')
    assert verdicts is None and state.state == 'evaluating'
    fake.gate.set()
    service.wait('/pkg', timeout=10)
    assert notified == ['ready']
    verdicts, state = service.get('/pkg')
    assert state.state == 'ready' and verdicts.stamp == 'v1'


def test_one_version_is_validated_once():
    fake = Fake()
    service = _service(fake)
    service.get('/pkg')
    service.wait('/pkg', timeout=10)
    for _ in range(20):
        assert service.get('/pkg')[1].state == 'ready'
    assert fake.runs == ['v1']


def test_after_a_change_the_last_verdicts_come_back_stale():
    fake = Fake()
    service = _service(fake)
    service.get('/pkg')
    service.wait('/pkg', timeout=10)

    fake.stamp = 'v2'
    fake.gate.clear()
    verdicts, state = service.get('/pkg')
    assert state.state == 'evaluating' and state.stale and verdicts.stamp == 'v1'
    fake.gate.set()
    service.wait('/pkg', timeout=10)
    assert service.get('/pkg')[0].stamp == 'v2'


def test_a_change_during_a_run_is_validated_too():
    fake = Fake()
    fake.gate.clear()
    service = _service(fake)
    service.get('/pkg')
    fake.stamp = 'v2'                    # edited while v1 is being validated
    fake.gate.set()
    service.wait('/pkg', timeout=10)
    assert fake.runs == ['v1', 'v2']
    assert service.get('/pkg')[0].stamp == 'v2'


def test_a_failure_is_reported_not_retried_for_the_same_version():
    fake = Fake()
    fake.fail = 'boom'
    service = _service(fake)
    service.get('/pkg')
    service.wait('/pkg', timeout=10)
    verdicts, state = service.get('/pkg')
    assert state.state == 'failed' and 'boom' in state.error
    assert fake.runs == ['v1']


def test_a_restart_on_an_unchanged_package_validates_nothing(package):
    from semforge.editor.cache import fingerprint

    first = VerdictService(fingerprint, in_process(load))
    first.get(package.path)
    first.wait(package.path, timeout=120)
    assert first.get(package.path)[1].state == 'ready'

    runs = []
    second = VerdictService(fingerprint, lambda root, stamp: runs.append(stamp))
    verdicts, state = second.get(package.path)
    assert state.state == 'ready' and not runs
    assert len(verdicts.model.violations) == 3


def test_pages_without_verdicts_never_validate(package, monkeypatch):
    """The property that keeps a click fast at any size."""
    from semforge.cooked.casepage import build_case_page, build_model_page
    from semforge.cooked.examples import build_suite
    from semforge.cooked.shapepage import build_shape_page
    from semforge.cooked.typepage import PENDING, build_type_page
    from semforge.editor.analysis import analyse
    from semforge.expect.store import load_expectations
    from semforge.validate import orchestrator

    def forbidden(*args, **kwargs):
        raise AssertionError('validated while building a page')

    monkeypatch.setattr(orchestrator, 'validate_graphs', forbidden)
    monkeypatch.setattr(orchestrator, 'validate_package', forbidden)
    import semforge.validate as validate
    monkeypatch.setattr(validate, 'validate_package', forbidden)

    page = build_type_page(package, 'iffBaseEntities:Filter', PENDING)
    assert page['attributes'] and page['summary']['instancesViolating'] is None
    assert {a['tested'] for a in page['attributes']} == {'evaluating'}
    assert all(i['violations'] is None for i in page['instances'])

    shape = build_shape_page(package, 'iffBaseShacl:FilterShape', PENDING)
    assert shape['summary']['violations'] is None

    model = build_model_page(package, PENDING)
    assert model['summary']['violations'] is None and model['summary']['entities']

    example = load_expectations(package.path).examples[0]
    case = build_case_page(package, example.path, PENDING)
    assert case['passed'] is None and all(c['holds'] is None for c in case['claims'])

    def nodes(level):
        for node in level:
            yield node
            yield from nodes(node.children)

    cases = [n for n in nodes(build_suite(package, verdicts=PENDING)) if n.kind == 'example']
    declared = [n for n in cases if n.detail == 'evaluating…']
    assert declared and not any(n.severity for n in declared)

    findings, _ = analyse(package.path, package=package, verdicts=PENDING)
    kinds = {f.kind for items in findings.values() for f in items}
    assert not kinds & {'fires', 'unexercised'}


def test_pages_with_verdicts_show_what_validation_shows(package):
    """Built from verdicts, a page says what it said when it validated itself."""
    from semforge.cooked.typepage import build_type_page

    verdicts = compute(package, 'v1')
    from_verdicts = build_type_page(package, 'iffBaseEntities:Filter', verdicts)
    validated_here = build_type_page(package, 'iffBaseEntities:Filter')
    assert from_verdicts == validated_here
