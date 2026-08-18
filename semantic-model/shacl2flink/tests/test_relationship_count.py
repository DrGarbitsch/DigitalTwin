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
A relationship is counted once per datasetId, not once per row.

Reported from a running cluster: urn:plasmacutter:1 was reported as

    Model validation for relationship ...hasFilter failed for urn:plasmacutter:1.
    Found 2 relationships instead of [1, 1]!

while Scorpio held exactly one hasFilter, datasetId absent, linking to
urn:filter:1. Two rows for that one relationship had reached the aggregate, and
the count was `SUM(CASE WHEN ... THEN 1 ELSE 0 END)` -- one per ROW -- so it
reported two.

Rows can duplicate for reasons the aggregate cannot see. attributes_view
deduplicates on (id, datasetId) under a state TTL, and a relationship that has
been deleted stops being republished by the periodic snapshot, because it no
longer exists to snapshot; its key is therefore the one key guaranteed to
expire. Recreating it later arrives as an INSERT rather than an update, the -U
withdrawing the previous row is never emitted, and both rows are counted. The
same cluster has also reported "Found 2" and "Found 3" for attributes existing
exactly once with the TTL disabled entirely, so row duplication is not solely a
TTL effect and the aggregate should not depend on rows being unique.

datasetId is what distinguishes instances of a multi-attribute in NGSI-LD, so
counting distinct datasetIds is both the correct cardinality and immune to a
duplicate row. sql_check_property_count already counts that way; this pins the
relationship count to the same rule, and pins the two to each other so the
asymmetry cannot come back.

Batch cannot reproduce the duplicate -- the SQLite view collapses it before the
aggregate ever sees it, which is why the oracle agreed with Flink throughout --
so the expression is asserted directly instead.
"""

import re
import sqlite3

import pytest

import lib.shacl_properties_to_sql as props


def _instance_count(template):
    """The aggregate the template actually uses, lifted out of the Jinja set."""
    match = re.search(r'{%-?\s*set instance_count\s*%}(.*?){%-?\s*endset\s*%}',
                      template, re.S)
    assert match is not None, 'template defines no instance_count'
    return ' '.join(match.group(1).split())


RELATIONSHIP_COUNT = _instance_count(props.sql_check_relationship_property_count)
PROPERTY_COUNT = _instance_count(props.sql_check_property_count)


# (adeleted, link, index) -- one relationship present twice under the same
# datasetId, a second under its own, plus rows that must not be counted.
ROWS = [
    (0, 'urn:filter:1', '@none'),   # the relationship
    (0, 'urn:filter:1', '@none'),   # ... duplicated, the bug this survives
    (0, 'urn:other:1', 'ds1'),      # a genuine second instance
    (1, 'urn:gone:1', 'ds2'),       # deleted, must not count
    (0, None, 'ds3'),               # no link, must not count
]


def _evaluate(expression, rows=ROWS):
    con = sqlite3.connect(':memory:')
    con.execute('CREATE TABLE a (adeleted INTEGER, link TEXT, `index` TEXT)')
    con.executemany('INSERT INTO a VALUES (?, ?, ?)', rows)
    # FALSE is spelled 0 in the SQLite dialect the generator targets elsewhere.
    sql = expression.replace('FALSE', '0')
    return con.execute(f'SELECT {sql} FROM a').fetchone()[0]


def test_relationship_count_ignores_a_duplicate_row():
    """The regression: two rows for one relationship must count once.

    The previous expression, SUM(CASE WHEN ... THEN 1 ELSE 0 END), returns 3
    for these rows and is what produced "Found 2 relationships instead of
    [1, 1]!" on a cluster holding exactly one.
    """
    assert _evaluate(RELATIONSHIP_COUNT) == 2


def test_a_matched_row_without_a_datasetid_still_counts():
    """COUNT(DISTINCT ...) skips NULLs, and a skipped row means "Found 0".

    Counting distinct datasetIds must not turn a satisfied constraint into a
    violation just because the instance carries no datasetId. NULL means the
    default instance, exactly as '@none' does. No fixture produces such a row --
    the bridge always writes '@none' -- so nothing else would catch this.
    """
    assert _evaluate(RELATIONSHIP_COUNT, [(0, 'urn:filter:1', None)]) == 1


def test_a_missing_datasetid_is_the_same_instance_as_none():
    rows = [(0, 'urn:filter:1', None), (0, 'urn:filter:1', '@none')]
    assert _evaluate(RELATIONSHIP_COUNT, rows) == 1


def test_relationship_count_excludes_deleted_and_unlinked():
    rows = [(1, 'urn:gone:1', 'ds1'), (0, None, 'ds2')]
    assert _evaluate(RELATIONSHIP_COUNT, rows) == 0


def test_relationship_count_counts_each_datasetid_once():
    rows = [(0, 'urn:a:1', '@none'), (0, 'urn:b:1', 'ds1'), (0, 'urn:c:1', 'ds2')]
    assert _evaluate(RELATIONSHIP_COUNT, rows) == 3


def test_relationship_count_is_distinct_over_datasetid():
    assert 'COUNT(DISTINCT' in RELATIONSHIP_COUNT
    assert '`index`' in RELATIONSHIP_COUNT


def test_relationship_count_does_not_sum_rows():
    """Guards the specific shape that was wrong, not just the result."""
    assert 'THEN 1 ELSE 0' not in RELATIONSHIP_COUNT
    assert not RELATIONSHIP_COUNT.startswith('SUM(')


def test_relationship_and_property_counts_agree():
    """Neither may drift from the other again.

    They differ only in the column that decides whether the row is an instance
    of the constrained path -- `link` for a relationship, `attr_typ` for a
    property.
    """
    normalise = lambda s: s.replace('link', 'X').replace('attr_typ', 'X').lower()  # noqa: E731
    assert normalise(RELATIONSHIP_COUNT) == normalise(PROPERTY_COUNT)


@pytest.mark.parametrize('template_name', [
    'sql_check_relationship_property_count',
    'sql_check_property_count',
])
def test_a_verdict_is_emitted_even_when_the_constraint_holds(template_name):
    """"Not violated" must be a row, not the absence of one.

    These statements used to filter with HAVING, so a constraint that stopped
    being violated simply stopped producing a row and the only signal was a
    retraction. Measured on a cluster: after a redeploy the job wrote nothing at
    all for two constraints it had evaluated as satisfied, and the alerts they
    had raised stayed open in Alerta indefinitely, because nothing ever said
    they had cleared.

    Emitting `triggered` as the condition means a satisfied constraint states so
    explicitly, which survives state expiry in a way a missing row cannot. The
    cost is a row per (entity, constraint) rather than per violation.
    """
    template = getattr(props, template_name)
    assert '{{ constraint_cond }} as triggered' in template
    assert 'true as triggered' not in template
    assert 'HAVING' not in template, \
        'filtering with HAVING makes "not violated" indistinguishable from silence'


@pytest.mark.parametrize('template_name', [
    'sql_check_relationship_property_count',
    'sql_check_property_count',
])
def test_the_count_aggregate_state_never_expires(template_name):
    """The accumulator must not be allowed to drift.

    A count over a changelog is maintained incrementally across several state
    structures; state TTL expires those independently, and once they disagree
    nothing reconciles them -- republishing a value increments a counter that is
    already inconsistent. Measured on a cluster: one row published for
    urn:plasmacutter:1 hasFilter, datasetId '@none', counted as 2.

    Pinned per operator rather than job-wide: this state is one accumulator per
    (entity, constraint) and bounded by the model, while the dedup views grow
    with churn and keep their TTL.
    """
    template = getattr(props, template_name)
    assert "STATE_TTL('A1' = '0d')" in template


@pytest.mark.parametrize('template_name', [
    'sql_check_relationship_property_count',
    'sql_check_property_count',
])
def test_count_is_used_everywhere_in_the_template(template_name):
    """Message and both HAVING comparisons must use the same expression.

    A literal aggregate left inline in any of the three would report a number
    the constraint did not test against, or test against one it did not report.
    """
    template = getattr(props, template_name)
    assert 'THEN 1 ELSE 0' not in template, \
        'a row-counting aggregate is still inlined in the template'
    assert template.count('{{ instance_count }}') >= 3
