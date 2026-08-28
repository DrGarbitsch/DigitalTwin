-- Same four rows as the filesystem reproducer, but the sources are
-- upsert-kafka with a PRIMARY KEY, so Flink puts a ChangelogNormalize in
-- front of each -- exactly the shape of the production pipeline, where the
-- retraction originates in the normalizer rather than in a Rank.
--
-- topic_a: three successive values for the SAME key (k=a, d=0)
-- topic_b: one row for the same key
--
-- The upsert source must yield exactly ONE row per key, so every query below
-- must end with exactly ONE row:  a | v3 | w1

SET 'execution.runtime-mode' = 'streaming';
SET 'sql-client.execution.result-mode' = 'tableau';
SET 'parallelism.default' = '1';
SET 'table.exec.state.ttl' = '0';

CREATE TABLE a (
  k STRING, d STRING, v STRING, ts TIMESTAMP(3),
  PRIMARY KEY (k, d) NOT ENFORCED
) WITH (
  'connector' = 'upsert-kafka',
  'topic' = 'topic_a',
  'properties.bootstrap.servers' = 'repro-kafka:9092',
  'key.format' = 'json',
  'value.format' = 'json',
  'scan.bounded.mode' = 'latest-offset'
);

CREATE TABLE b (
  k STRING, d STRING, v STRING, ts TIMESTAMP(3),
  PRIMARY KEY (k, d) NOT ENFORCED
) WITH (
  'connector' = 'upsert-kafka',
  'topic' = 'topic_b',
  'properties.bootstrap.servers' = 'repro-kafka:9092',
  'key.format' = 'json',
  'value.format' = 'json',
  'scan.bounded.mode' = 'latest-offset'
);

-- K1: straight from the upsert source, projected to (k, v) so the (k, d)
-- key is no longer provable -> NoUniqueKey join
CREATE TEMPORARY VIEW pa AS SELECT k, v FROM a;
CREATE TEMPORARY VIEW pb AS SELECT k, v FROM b;

-- K2: the production shape -- upsert source, then a Rank on (k, d), then the
-- same projection
CREATE TEMPORARY VIEW ra AS SELECT k, v FROM (
  SELECT *, ROW_NUMBER() OVER (PARTITION BY k, d ORDER BY ts DESC) AS rn FROM a) WHERE rn = 1;
CREATE TEMPORARY VIEW rb AS SELECT k, v FROM (
  SELECT *, ROW_NUMBER() OVER (PARTITION BY k, d ORDER BY ts DESC) AS rn FROM b) WHERE rn = 1;

SELECT 'K1-inner' AS tag, pa.k, pa.v, pb.v FROM pa JOIN pb ON pa.k = pb.k;
SELECT 'K1-outer' AS tag, pa.k, pa.v, pb.v FROM pa LEFT JOIN pb ON pa.k = pb.k;
SELECT 'K2-inner' AS tag, ra.k, ra.v, rb.v FROM ra JOIN rb ON ra.k = rb.k;
SELECT 'K2-outer' AS tag, ra.k, ra.v, rb.v FROM ra LEFT JOIN rb ON ra.k = rb.k;
