# Top-1 ROW_NUMBER on a non-time-attribute order key is wrongly declared insert-only (Flink 2.1+)

**Affects** Flink 2.1.0 and 2.3.0 (measured); 2.2 and `master` carry the same
code. **Not** 1.20.4 (measured), nor 1.19/1.20/2.0 by source inspection.
**Component** Table SQL / Planner.
**Impact** Silent wrong results: a `ROW_NUMBER() = 1` deduplication stops
retracting the row it supersedes, so every downstream operator keeps stale rows
forever. No error, no warning, no failed job.
**Fix** Two lines, verified — `flink-fix.patch` next to this file. See
[The fix](#the-fix).

---

## The short version

Flink 2.1 added a shortcut that declares a top-1 `ROW_NUMBER()` insert-only.
It is sound for a genuine *keep-first deduplication on a time attribute*, where
the first row to arrive wins and can never be displaced. But the shortcut is
guarded only by `RankUtil.isDeduplication(rank)`, which checks nothing but
"`ROW_NUMBER`, top-1, no rank column" — it never checks that the sort is on a
time attribute. So it is applied to plain `Rank` operators too, and their
retractions are dropped.

On an ordinary (non-time-attribute) column, the only form that survives is

```sql
ROW_NUMBER() OVER (PARTITION BY id ORDER BY ts DESC)          -- correct, by luck
```

because that is the one case where `keepLastDeduplicateRow` returns `true`.
Both of these are silently broken:

```sql
ROW_NUMBER() OVER (PARTITION BY id ORDER BY ts DESC, seq DESC) -- multi-column
ROW_NUMBER() OVER (PARTITION BY id ORDER BY ts ASC)            -- ascending
```

---

## Reproducing it

Two containers: one Kafka, one Flink. Everything below is submitted through
`sql-client.sh` (equivalently, pasted into the SQL gateway). **The DDL and the
query are byte-identical on both versions** — only the Flink image changes.

Scripts: `../tools/flink-version-repro/` (`kafka_setup.sh`, then
`run-minimal.sh <image> <label> <connector-jar-url>`).

### Step A — paste the DDL

Two append-only Kafka logs and one keyed sink. In both logs the newest row per
`id` is the current truth, so each is wrapped in a `ROW_NUMBER() = 1` view.

```sql
SET 'execution.runtime-mode' = 'streaming';
SET 'parallelism.default' = '1';

CREATE TABLE entities (
  `id` STRING,
  `type` STRING,
  `ts` TIMESTAMP(3)
) WITH (
  'connector' = 'kafka', 'topic' = 'r_entities',
  'properties.bootstrap.servers' = 'repro-kafka:9092',
  'scan.startup.mode' = 'earliest-offset',
  'value.format' = 'json'
);

CREATE TABLE attributes (
  `id` STRING,
  `entityId` STRING,
  `attributeValue` STRING,
  `ts` TIMESTAMP(3),
  `seq` BIGINT
) WITH (
  'connector' = 'kafka', 'topic' = 'r_attributes',
  'properties.bootstrap.servers' = 'repro-kafka:9092',
  'scan.startup.mode' = 'earliest-offset',
  'value.format' = 'json'
);

CREATE TABLE verdict (
  `resource` STRING,
  `severity` STRING,
  PRIMARY KEY (`resource`) NOT ENFORCED
) WITH (
  'connector' = 'upsert-kafka', 'topic' = 'r_verdict',
  'properties.bootstrap.servers' = 'repro-kafka:9092',
  'key.format' = 'json', 'value.format' = 'json'
);

CREATE TEMPORARY VIEW entities_view AS
  SELECT `id`, `type` FROM (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY `id` ORDER BY `ts` DESC) AS rn
    FROM entities) WHERE rn = 1;

-- the operator this report is about: TWO sort columns, `seq` breaking ties
CREATE TEMPORARY VIEW attributes_view AS
  SELECT `id`, `entityId`, `attributeValue` FROM (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY `id`
             ORDER BY `ts` DESC, `seq` DESC) AS rn
    FROM attributes) WHERE rn = 1;
```

### Step B — paste the query

For every entity of type `Cutter`: `critical` while it currently has an
attribute whose value is not `ON`, `ok` otherwise. The `LEFT JOIN` keeps the
entity in the result when it has no such attribute, so the verdict is able to
return to `ok`.

```sql
INSERT INTO verdict
SELECT u.`id` AS resource,
       CASE WHEN MAX(CASE WHEN v.this IS NOT NULL THEN 1 ELSE 0 END) = 1
            THEN 'critical' ELSE 'ok' END AS severity
FROM (SELECT `id` FROM entities_view WHERE `type` = 'Cutter') AS u
LEFT JOIN (
    SELECT `entityId` AS this FROM attributes_view WHERE `attributeValue` <> 'ON'
  ) AS v ON u.`id` = v.this
GROUP BY u.`id`;
```

### Step C — insert three rows, one at a time

Wait for each to be processed before sending the next (the reproducer sleeps
35 s, 60 s, 60 s).

```sql
-- 1. the entity appears; it has no attributes yet
INSERT INTO entities   VALUES ('c1', 'Cutter', TIMESTAMP '2026-01-01 00:00:00');

-- 2. a violating attribute appears (state OFF)
INSERT INTO attributes VALUES ('a1', 'c1', 'OFF', TIMESTAMP '2026-01-01 00:00:01', 1);

-- 3. the SAME attribute (`id` = 'a1') is superseded by a good value (ON)
INSERT INTO attributes VALUES ('a1', 'c1', 'ON',  TIMESTAMP '2026-01-01 00:00:02', 2);
```

### Step D — read the sink

```
kafka-console-consumer.sh --bootstrap-server ... --topic r_verdict --from-beginning
```

---

## What should happen, and what does

After insert 3, `attributes_view` must contain exactly one row for `a1`, the
one with the larger `(ts, seq)` — value `ON`. `ON <> 'ON'` is false, so `v` is
empty, so the verdict must go back to `ok`.

| after | expected | Flink 1.20.4 | Flink 2.3.0 |
|---|---|---|---|
| insert 1 | `{"resource":"c1","severity":"ok"}` | `ok` | `ok` |
| insert 2 | `critical` (preceded by a tombstone) | `null`, `critical` | `null`, `critical` |
| insert 3 | `ok` again (preceded by a tombstone) | `null`, `ok` | **nothing at all** |

Full topic contents, verbatim:

```
1.20.4:  {"resource":"c1","severity":"ok"}
         null
         {"resource":"c1","severity":"critical"}
         null
         {"resource":"c1","severity":"ok"}          <-- clears

2.3.0:   {"resource":"c1","severity":"ok"}
         null
         {"resource":"c1","severity":"critical"}
                                                    <-- never clears
```

On 2.3 the alert is stuck at `critical` forever, although the condition that
raised it is gone. Nothing fails; the job stays healthy.

Across releases:

| Flink | result | how established |
|---|---|---|
| 1.20.4 | correct — clears | run |
| 2.1.0 | stuck at `critical` | run |
| 2.3.0 | stuck at `critical` | run |
| 2.3.0 + patch | correct — clears | run |
| 2.0.0 | not testable | run — this query cannot be planned at all on 2.0.0: `java.lang.AssertionError: Relational expression rel#743:LogicalProject … belongs to a different planner than is currently being used`, an unrelated defect |
| 1.19, 1.20, 2.0 | expected correct | source: the insert-only branch does not exist |
| 2.1, 2.2, 2.3, master | expected broken | source: the insert-only branch is present |

---

## Which operator loses the retraction

Tap the deduplication's own output into a `debezium-json` Kafka sink, so the
changelog op codes become visible:

```sql
CREATE TABLE probe (
  `id` STRING, `entityId` STRING, `attributeValue` STRING
) WITH (
  'connector' = 'kafka', 'topic' = 'r_probe1',
  'properties.bootstrap.servers' = 'repro-kafka:9092',
  'value.format' = 'debezium-json'
);
INSERT INTO probe SELECT `id`, `entityId`, `attributeValue` FROM attributes_view;
```

```
1.20.4:  {"before":null,                          "after":{"id":"a1",...,"attributeValue":"OFF"},"op":"c"}
         {"before":{"id":"a1",...,"OFF"},         "after":null,                                  "op":"d"}
         {"before":null,                          "after":{"id":"a1",...,"attributeValue":"ON"}, "op":"c"}

2.3.0:   {"before":null,                          "after":{"id":"a1",...,"attributeValue":"OFF"},"op":"c"}
         {"before":null,                          "after":{"id":"a1",...,"attributeValue":"ON"}, "op":"c"}
```

(`debezium-json` writes `c` for both `INSERT` and `UPDATE_AFTER`, and `d` for
both `UPDATE_BEFORE` and `DELETE`, so this shows whether a withdrawal was
emitted, not which of the two kinds it was.)

The deduplication itself is the faulty operator: on 2.3 it announces `ON` as
the new top-1 without ever withdrawing `OFF`. Two rows are therefore live at
rank 1 for the same partition key — which an insert-only stream cannot express.

Downstream this is unrecoverable: between the deduplication and the join sits
the filter `attributeValue <> 'ON'`. A withdrawal of `OFF` passes that filter
(and would evict the row from the join state); the un-withdrawn `ON` does not.
So the stale `OFF` row stays in the join's state for the lifetime of the job.

---

## Why 1.20 is right

`ROW_NUMBER() OVER (PARTITION BY id ORDER BY ts DESC, seq DESC) = 1` is a
*keep-last* deduplication: the winner is whichever row currently has the
greatest `(ts, seq)`, and any later row with a greater key replaces it. The
result is by definition an updating relation — for one partition key the output
row changes over time — so its changelog must contain retractions. 1.20 emits
the `OFF` row, then withdraws it, then emits the `ON` row, and every downstream
operator sees a relation that always holds exactly one row per `id`. That is
what SQL semantics require; its declared changelog mode `[I,UB,UA,D]` says so.

The only deduplication that is genuinely insert-only is *keep-first on a time
attribute*, where sort order equals arrival order, so the winner is decided by
the first record and nothing can ever displace it.

---

## Root cause

`EXPLAIN CHANGELOG_MODE` shows the defect without running anything. Same script,
same optimized plan on both versions — the operators, strategies and join input
specs are byte-identical — but the declared changelog mode differs:

```
1.20.4  Rank(... partitionBy=[id], orderBy=[ts DESC, seq DESC], changelogMode=[I,UB,UA,D])
2.3.0   Rank(... partitionBy=[id], orderBy=[ts DESC, seq DESC], changelogMode=[I])
```

The single-column deduplication in the very same plan
(`orderBy=[ts DESC]`, on `entities`) is `[I,UB,UA,D]` on both versions. Note
that both are planned as `Rank`, never as `Deduplicate` — neither sorts on a
time attribute — yet 2.3 applies deduplicate reasoning to one of them.

`FlinkChangelogModeInferenceProgram.scala` (2.1+, absent in 2.0 and earlier):

```scala
case rank: StreamPhysicalRank if RankUtil.isDeduplication(rank) =>
  val insertOnly = children.forall(ChangelogPlanUtils.isInsertOnly)
  val providedTrait =
    if (insertOnly && RankUtil.outputInsertOnlyInDeduplicate(
          tableConfig, RankUtil.keepLastDeduplicateRow(rank.orderKey))) {
      // Deduplicate outputs append only if first row is kept and mini batching is disabled
      ModifyKindSetTrait.INSERT_ONLY
    } else ModifyKindSetTrait.ALL_CHANGES
```

`RankUtil.scala`:

```scala
/** Whether the given rank is logically a deduplication. */
def isDeduplication(rank: Rank): Boolean =
  !rank.outputRankNumber && rank.rankType == RankType.ROW_NUMBER && isTop1(rank.rankRange)

def keepLastDeduplicateRow(orderKey: RelCollation): Boolean = {
  // order by timeIndicator desc ==> lastRow, otherwise is firstRow
  if (orderKey.getFieldCollations.size() != 1) {
    return false                                  // multi-column: gives up
  }
  orderKey.getFieldCollations.get(0).direction.isDescending
}

def outputInsertOnlyInDeduplicate(config: ReadableConfig, keepLastRow: Boolean): Boolean =
  !keepLastRow && !config.get(ExecutionConfigOptions.TABLE_EXEC_MINIBATCH_ENABLED)
```

Two things go wrong together:

1. `isDeduplication` is not the right guard. Whether a rank is really executed
   as a `StreamExecDeduplicate` is decided by `canConvertToDeduplicate`, which
   additionally requires `sortOnTimeAttributeOnly` — a *single* sort field that
   is a proctime or rowtime indicator. The changelog branch skips that check, so
   plain `Rank` operators take the deduplicate shortcut.
2. `keepLastDeduplicateRow` answers "no" both when it means "keep-first" and
   when it means "I can't tell" (multi-column). `outputInsertOnlyInDeduplicate`
   reads that `!keepLastRow` as the positive claim "this is keep-first", which
   genuinely is insert-only. A "don't know" is consumed as a "no".

So on a plain column the shortcut fires for `ORDER BY x ASC` (keepLast = false
because the direction is ascending) and for any multi-column order key
(keepLast = false because it gave up). Only single-column `DESC` escapes, and
only by accident. Note also that `outputInsertOnlyInDeduplicate` returns false
whenever mini-batch is enabled, so **turning mini-batch on hides the bug
entirely** — which makes the failure look mini-batch-dependent when it is not.

---

## The fix

`flink-fix.patch`, against the `release-2.3.0` tag. It restores the invariant
that only a rank which is really executed as a `StreamExecDeduplicate` may claim
to be insert-only, by reusing the predicate `canConvertToDeduplicate` already
relies on:

```scala
// FlinkChangelogModeInferenceProgram.scala
val sortOnTimeAttributeOnly =
  RankUtil.sortOnTimeAttributeOnly(rank.orderKey, rank.getInput.getRowType)

if (insertOnly && sortOnTimeAttributeOnly && RankUtil.outputInsertOnlyInDeduplicate(
      tableConfig, RankUtil.keepLastDeduplicateRow(rank.orderKey)))
```

plus making that existing helper visible (it was `private`). Since
`sortOnTimeAttributeOnly` already demands a single proctime/rowtime sort field,
this closes the ascending case and the multi-column case at once.

`canConvertToDeduplicate` itself is deliberately *not* called here: it consults
`ChangelogPlanUtils.inputInsertOnly`, and Flink's own
`FlinkRelMdModifiedMonotonicity` notes that this is unreliable while the
modifyKindSet trait is still being computed. The `insertOnly` value already
derived from the visited children serves that purpose instead.

Verified by building `flink-table-planner` from the patched 2.3.0 tag and
swapping the jar into `flink:2.3.0` (drop `lib/flink-table-planner-loader-*.jar`,
put the planner jar in `lib/`):

| check | result |
|---|---|
| multi-column case (`ORDER BY ts DESC, seq DESC`) | `ok → critical → ok` — fixed |
| ascending case (`ORDER BY ts ASC`) | `ok → critical → ok` — fixed |
| genuine keep-first dedup on `PROCTIME()` | plan unchanged: `Deduplicate(keep=[FirstRow], key=[id], order=[PROCTIME], outputInsertOnly=[true])`, byte-identical to stock |
| `DeduplicateTest`, `ChangelogModeInferenceTest`, `RankTest` (stream + batch) | 93 tests, 0 failures |
| `DeduplicateITCase` (runtime behaviour) | 50 tests, 0 failures, 6 skipped |

The third row is the one that matters for not regressing the 2.1 optimisation:
the case it was written for still produces exactly the same plan.

---

## Bisect log

Each line is a full run of the reproducer; only the named change differs from
the minimal case.

| variant | 1.20.4 | 2.3.0 |
|---|---|---|
| full platform rule (4 joins, real DDL) | clears | stuck |
| one join, `hasState` only | clears | stuck |
| **`ORDER BY ts DESC, seq DESC`** (minimal, above) | clears | **stuck** |
| **`ORDER BY ts ASC`**, later row has a smaller `ts` | clears | **stuck** |
| `ORDER BY ts DESC` — second sort column deleted | clears | clears |
| plus `SET 'table.exec.state.ttl' = '3600 s'` | clears | clears |
| `PARTITION BY id, datasetId` (two-column *partition* key) | clears | clears |
| no `LEFT JOIN` (dedup → `GROUP BY` → sink) | clears | clears |
| no dedup on the left/universe side of the join | clears | clears |

Only the order key matters. The state TTL, the partition key width and the join
shape do not — they merely determine whether the lost retraction is observable.

---

## What this means for us

Two separate defects were found while chasing "alerts never clear on 2.3", and
only one of them is Flink's.

1. **Ours, fixed** (`Give every SPARQL verdict an upsert key that matches its
   sink`). Rule statements wrote into `alerts_bulk`, whose primary key is
   `(resource, event, environment)`, from a `LEFT JOIN` that can produce several
   violation rows per resource — so the query had no provable upsert key. 1.20
   papered over this with a `SinkUpsertMaterializer`; 2.3 refuses to plan it
   (FLIP-558). Fixed by grouping the verdict per resource
   (`GROUP BY this_left` with `MAX(...)`), which gives the query the upsert key
   its sink declares. The plan now shows
   `GroupAggregate(groupBy=[resource], MAX_RETRACT)` and no materializer.

2. **Flink's** — this report, with a verified fix in `flink-fix.patch`. Our
   `attributes` view deduplicates with
   `ORDER BY COALESCE(observedAt, ts) DESC, offset DESC`, where the Kafka offset
   breaks ties between records sharing a timestamp. That is a multi-column order
   key, so on 2.1+ it is planned insert-only and alerts never clear.

Until the fix is upstream, 1.20.4 remains the only stock platform on which the
use case is proven. On 2.1+ the workarounds are to enable mini-batch, or to
collapse the deduplication order key to a single **descending** column — and
note that the single-column form is correct only by accident, so it is a
workaround, not a design to rely on.
