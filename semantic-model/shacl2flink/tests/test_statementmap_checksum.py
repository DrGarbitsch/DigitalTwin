#
# Copyright (c) 2026 Intel Corporation
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

"""
A model change must reach the running Flink job.

A BeamSqlStatementSet names its SQL by ConfigMap reference, and the operator
reconciles on changes to the statement set: ConfigMaps are registered with
kopf.index, a lookup table rather than a watch, and updateStrategy is only
consulted from the statement set's own update handler. Regenerating the model
therefore rewrites the ConfigMap and leaves the statement set byte-identical,
so Kubernetes records no diff, no event fires, and the job keeps executing the
SQL it was submitted with.

Nothing reports this. A job running last week's model and a job running this
week's look identical from the outside - same name, same status, same absence
of errors - so the divergence is only discoverable by reading the submitted SQL
back off the running job and comparing it by hand.

Stamping a checksum of the statements onto the statement set makes it a
function of the content it references, so the diff exists and the operator has
something to react to.
"""

import os
import sys

import pytest

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
import lib.utils as utils  # noqa: E402


STATEMENTS = [
    'INSERT INTO alerts SELECT * FROM a;',
    'INSERT INTO alerts SELECT * FROM b;',
]

# The operator carries its own copy of this hash - it cannot import from here -
# and compares what it computes against what we stamp. The two implementations
# are pinned to each other by asserting this same literal on both sides; see
# FlinkSqlServicesOperator/test/test_beamsqlstatementsetoperator.py. If you
# change the algorithm, both tests must be updated together, and every deployed
# statement set will redeploy once.
GOLDEN_CHECKSUM = \
    'dfba9700ee3500fb876db8e5b09d3b62d416ba61e5e0c39869ac5ee1d486ad89'


def test_checksum_matches_the_operator_implementation():
    assert utils.statementmap_checksum(STATEMENTS) == GOLDEN_CHECKSUM


def test_checksum_changes_when_a_statement_changes():
    """The whole point: a model edit has to move the checksum."""
    changed = [STATEMENTS[0], 'INSERT INTO alerts SELECT * FROM c;']
    assert utils.statementmap_checksum(STATEMENTS) != \
        utils.statementmap_checksum(changed)


def test_checksum_changes_when_a_statement_is_added():
    added = STATEMENTS + ['INSERT INTO alerts SELECT * FROM c;']
    assert utils.statementmap_checksum(STATEMENTS) != \
        utils.statementmap_checksum(added)


def test_checksum_is_stable_across_rebuilds():
    """A rebuild of an unchanged model must not redeploy the job.

    The checksum is the redeployment trigger, so instability here would cancel
    and restart the Flink job on every `make helm`, discarding its state.
    """
    assert utils.statementmap_checksum(STATEMENTS) == \
        utils.statementmap_checksum(list(STATEMENTS))


def test_checksum_does_not_collide_on_statement_boundaries():
    assert utils.statementmap_checksum(['ab', 'c']) != \
        utils.statementmap_checksum(['a', 'bc'])


def test_checksum_survives_configmap_key_collation():
    """ConfigMap keys are strings, so the API server collates them as strings.

    The operator reads '0', '1', '10', '11', '2', ... and reassembles the
    statements in that order, which is not the order they were generated in.
    A checksum sensitive to that ordering would mismatch on every statement set
    with more than ten statements.
    """
    statements = [f'INSERT INTO alerts SELECT {i};' for i in range(12)]
    configmap = utils.create_configmap('cm', statements)

    as_operator_reads_them = [configmap['data'][key]
                              for key in sorted(configmap['data'],
                                                key=str)]
    assert as_operator_reads_them != statements, \
        'collation must actually differ, or this test proves nothing'
    assert utils.statementmap_checksum(as_operator_reads_them) == \
        utils.statementmap_checksum(statements)


def test_statementmap_carries_the_checksum_as_an_annotation():
    checksum = utils.statementmap_checksum(STATEMENTS)
    result = utils.create_statementmap('object', ['table'], ['view'], None,
                                       ['ns/cm'], checksum=checksum)
    annotations = result['metadata']['annotations']
    assert annotations[utils.STATEMENTMAP_CHECKSUM_ANNOTATION] == checksum


def test_configmap_carries_the_checksum_outside_data():
    """The operator submits every value under `data` to Flink as SQL.

    A checksum stored there would be executed as a statement.
    """
    checksum = utils.statementmap_checksum(STATEMENTS)
    result = utils.create_configmap('cm', STATEMENTS, checksum=checksum)
    assert result['metadata']['annotations'][
        utils.STATEMENTMAP_CHECKSUM_ANNOTATION] == checksum
    assert list(result['data'].values()) == STATEMENTS


def test_objects_stay_unannotated_without_a_checksum():
    """Callers that pass no checksum must render exactly as before."""
    assert 'annotations' not in utils.create_configmap('cm', STATEMENTS)['metadata']
    assert 'annotations' not in utils.create_statementmap(
        'object', ['table'], ['view'], None, ['ns/cm'])['metadata']


@pytest.mark.parametrize('name,statementmap_name', [
    ('shacl-validation', 'shacl-validation-configmap1'),
    ('shacl-constraints', 'shacl-constraints-configmap1'),
])
def test_statementset_and_its_configmaps_agree(name, statementmap_name):
    """Both sides of the comparison the operator makes must line up.

    The operator recomputes the checksum from the ConfigMap contents and
    refuses to deploy if it disagrees with the statement set's annotation, so a
    generator that stamps the two inconsistently would block deployment
    entirely.
    """
    checksum = utils.statementmap_checksum(STATEMENTS)
    configmap = utils.create_configmap(statementmap_name, STATEMENTS,
                                       checksum=checksum)
    statementset = utils.create_statementmap(name, ['table'], ['view'], None,
                                             [f'iff/{statementmap_name}'],
                                             checksum=checksum)

    reassembled = list(configmap['data'].values())
    assert utils.statementmap_checksum(reassembled) == \
        statementset['metadata']['annotations'][
            utils.STATEMENTMAP_CHECKSUM_ANNOTATION]
