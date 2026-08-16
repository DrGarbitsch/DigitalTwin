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
Deleting an entity must retract the alerts raised against it.

Reported from a running cluster: deleting an object left its alerts standing
and produced new ones reading

    Model validation for relationship ...hasCartridge failed for urn:filter:1 .
    Found -1 relationships instead of [1, 1]!

-1 is the diagnosis. The count is `SUM(CASE WHEN ... THEN 1 ELSE 0 END)`, whose
every term is 0 or 1, so in batch it cannot go below zero -- which is exactly
why the SQLite oracle and the pyshacl comparison agreed throughout while Flink
was wrong. On Flink the same expression is an incremental aggregate over a
changelog, and it reads -1 when it has applied one more retraction than it has
accumulations for that group.

Two things let that happen, and this file pins both. They are asserted on the
GENERATED artefacts rather than end to end because the failure needs an hour of
wall clock to appear -- a test that had to wait out a TTL would never run in
CI, and the e2e that covers the same ground
(tests/bats/test-shacl-flink-e2e) runs minutes after a deploy, when nothing
has expired yet.

The behaviour these settings produce is covered by
tests/sql-tests/sql-cases/deleted-entities (batch semantics) and by the
deletion tests in the Flink e2e (the changelog path).
"""

import pathlib
import re

import ruamel.yaml

import create_ngsild_tables
import lib.configs as configs
import lib.shacl_properties_to_sql as props


def _entities_view_statement(tmp_path):
    """
    The entities_view as actually GENERATED -- create_ngsild_tables.py is run
    and its output read back.

    Rebuilding the view here by calling create_yaml_view with a ttl of our own
    would assert nothing about the call site: the hint would be present because
    the test put it there, and dropping it from the generator would still pass.
    """
    create_ngsild_tables.main(output_folder=str(tmp_path))
    document = (tmp_path / 'ngsild.yaml').read_text()
    for section in ruamel.yaml.YAML(typ='safe').load_all(document):
        if section and section.get('spec', {}).get('name') == 'entities_view':
            return section['spec']['sqlstatement']
    raise AssertionError('create_ngsild_tables.py emitted no entities_view')


def test_entity_dedup_state_never_expires(tmp_path):
    """
    The view keeping the latest row per entity id had no STATE_TTL hint at all,
    so it inherited table.exec.state.ttl -- an hour. Entities are written once
    at deploy time and never touched, so an hour in, every entity's dedup state
    is gone and a DELETE arriving after that is not an update to a known key
    but the first row of an unknown one: Flink emits +I(deleted=true) instead
    of -U(old)/+U(new). Nothing retracts what the entity contributed and its
    alerts outlive it.
    """
    statement = _entities_view_statement(tmp_path)
    assert 'STATE_TTL' in statement, \
        'entities_view has no STATE_TTL hint and will inherit the job TTL'
    assert configs.view_state_ttl in statement, \
        'entities_view is not bound to the dedicated view TTL setting'
    assert configs.flink_ttl not in statement, \
        'entities_view dedup is back on the hourly job TTL'


def test_view_and_job_ttl_are_separate_settings():
    """
    The dedup views must not be tied to the job TTL: raising the one to bound
    memory would silently reintroduce the stale-alert behaviour.
    """
    assert configs.view_state_ttl != configs.flink_ttl
    assert configs.shacl_state_ttl != configs.flink_ttl


def _helm_value(name):
    """The default of a flink.* key in the umbrella values file."""
    values = pathlib.Path(__file__).parents[3] / 'helm' / 'values.yaml.gotmpl'
    match = re.search(rf'^\s+{name}:\s*"([^"]*)"', values.read_text(),
                      re.MULTILINE)
    assert match, f'{name} is not defined in {values}'
    return match.group(1)


def test_deployed_defaults_do_not_expire_validation_state():
    """
    The unit tests above pin which SETTING each operator reads; this pins what
    that setting is actually shipped as. Both halves matter -- wiring the views
    to their own knob achieves nothing if the knob defaults to an hour.

    A zero-valued Flink TTL means "never expire", written either as 0d or 0 ms.
    """
    assert _helm_value('viewTtl').startswith('0'), \
        'flink.viewTtl expires the dedup views; deletes will stop clearing alerts'
    assert _helm_value('shaclTtl').startswith('0'), \
        'flink.shaclTtl expires validation state; alerts will outlive their entity'


def _generated_checks():
    """The relationship and property checks, exactly as generated."""
    flink_relationship, _ = props.create_relationship_sql()
    flink_property, _ = props.create_property_sql()
    return {'relationship': flink_relationship, 'property': flink_property}


def test_count_checks_do_not_group_by_edeleted():
    """
    `edeleted` as a grouping key means a deleted entity MIGRATES its rows from
    group (id, false) to group (id, true) instead of emptying the first, and
    the `NOT edeleted` in the HAVING then mutes only the new group. The old one
    is retracted only if every row it holds is retracted -- which is what stops
    happening once state expires. A retraction landing in a group whose
    accumulator was rebuilt from fewer rows is what produced "-1".
    """
    for name, sql in _generated_checks().items():
        clauses = re.findall(r'GROUP\s+BY\s(.*?)\sHAVING', sql,
                             re.IGNORECASE | re.DOTALL)
        assert clauses, f'{name}: no GROUP BY ... HAVING found to check'
        for group_by in clauses:
            assert 'edeleted' not in group_by.lower(), \
                f'{name}: edeleted is a grouping key again in {group_by.strip()}'


def test_deleted_entities_never_reach_the_checks():
    """
    Deleted entities are filtered out of A1, so deleting one EMPTIES its groups
    and Flink retracts their alerts the way it does for any group that ceases
    to exist. This is what replaces the muting the GROUP BY used to do.
    """
    for name, sql in _generated_checks().items():
        assert 'COALESCE(A.`deleted`, false) = false' in sql, \
            f'{name}: A1 admits deleted entities, so their alerts are never retracted'
