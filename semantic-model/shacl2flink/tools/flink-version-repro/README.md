# Flink version reproducer

Runs the same tiny query on two Flink versions, entirely off the cluster, in
about 90 s per version. Built while investigating why the validation pipeline
works on 1.20.4 and misbehaves on 2.3.0.

    ./run.sh <image> <label> [sqlfile]                 # filesystem sources
    ./kafka_setup.sh && ./produce.sh                   # one KRaft broker, 4 records
    ./run_kafka.sh <image> <label> <connector-jar-url> # upsert-kafka sources
    KEYS=200 ./run_cycle.sh <image> <label> <jar> <updates> cycle_A.sql

Images used: `ibn40/flink-sql-gateway:v0.7.0-flink120` (1.20.4) and
`:v0.7.0-flink23` (2.3.0) -- the exact builds the cluster runs. Connector jars
come from Maven Central: `flink-sql-connector-kafka:3.3.0-1.20` and
`:5.0.0-2.2` (note `5.0.0-2.0` does not exist; a failed download is a 554-byte
HTML page and the connector then simply is not on the classpath).

## What each script tests

| file | chain | input | expected |
|---|---|---|---|
| `repro.sql` | filesystem -> `Rank` -> project -> join, V1 keyed `(k,d)` / V2 keyed `(k)`, inner + outer | 4 rows | 1 final row |
| `kafka_repro.sql` | `upsert-kafka` -> `ChangelogNormalize` (+`Rank` for K2) -> project -> join | 4 rows | 1 final row |
| `cycle_repro.sql` / `cycle_A.sql` | as above plus a FEEDBACK CYCLE: statement 1 writes an upsert-kafka topic that statement 2 reads back (`cycle_A` adds `ON CONFLICT DO DEDUPLICATE`) | N updates | 2N-1 records per key |
| `cycle_B.sql` | same cycle with single-column primary keys, so the upsert key survives the projection and matches the sink PK -- no `ON CONFLICT` needed | N updates | 2N-1 records per key |

## Results (2026-08-28)

**Every case behaves IDENTICALLY on 1.20.4 and 2.3.0.**

| chain | 1.20.4 | 2.3.0 |
|---|---|---|
| filesystem, bag join (`NoUniqueKey/NoUniqueKey`, verified by EXPLAIN), inner + outer | 1 row | 1 row |
| filesystem, keyed join, inner + outer | 1 row | 1 row |
| upsert-kafka + ChangelogNormalize (+Rank), inner + outer | 1 row | 1 row |
| cycle + `ON CONFLICT DO DEDUPLICATE`, 20 updates of 1 key | 39 | 39 |
| cycle, 200 keys x 5 updates | -- | 1800 (= 200 x 9, exact) |

So none of these reproduce the pipeline-level failure: bag joins, outer joins,
`ChangelogNormalize`, the feedback cycle and the `ON CONFLICT` clause are all
exonerated in isolation. On the full pipeline the difference is stark and
repeatable (1.20 flat at 12 in / 12 out per write; 2.3 climbing to >1.4 M
records from a single write) -- see the memory note `flink23-join-accumulation`
and `tools/job_analysis.py`.

## Gotchas found the hard way

* `variant` is a reserved word in 2.3 (VARIANT type) -- name the column
  something else.
* Kafka sources are unbounded, so `sql-client -f` never returns; add
  `'scan.bounded.mode' = 'latest-offset'` for terminating queries.
* The Strimzi Kafka image needs `LOG_DIR` pointed somewhere writable and
  `listeners` bound to a routable hostname (not `0.0.0.0`).
