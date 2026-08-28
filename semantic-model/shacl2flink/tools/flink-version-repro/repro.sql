-- Minimal reproducer: does a stream-stream join REMOVE a row when the
-- retraction for it arrives?
--
-- Input: 4 rows total. Table a carries three successive values for the SAME
-- logical row (k='a', d='0'); table b carries one row for the same k.
-- The dedup keeps the latest per (k, d), so `la` must hold exactly ONE row
-- (a, v3) and the join must produce exactly ONE row.
--
-- V1 deduplicates on (k, d) and then projects only k, so the unique key is
-- not provable downstream and the join compiles as
-- leftInputSpec=[NoUniqueKey], rightInputSpec=[NoUniqueKey] -- a join that
-- keeps every row per key and drops one only when a matching retraction
-- arrives.
--
-- Expected on any version: 1 row.  a | v3 | w1

SET 'execution.runtime-mode' = 'streaming';
SET 'sql-client.execution.result-mode' = 'tableau';
SET 'parallelism.default' = '1';
SET 'table.exec.state.ttl' = '0';

CREATE TABLE a (
  k STRING, d STRING, v STRING, ts TIMESTAMP(3)
) WITH ('connector' = 'filesystem', 'path' = 'file:///data/a.csv', 'format' = 'csv');

CREATE TABLE b (
  k STRING, d STRING, v STRING, ts TIMESTAMP(3)
) WITH ('connector' = 'filesystem', 'path' = 'file:///data/b.csv', 'format' = 'csv');

-- V1: dedup key is (k, d); the projection keeps only k
CREATE TEMPORARY VIEW la AS
  SELECT k, v FROM (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY k, d ORDER BY ts DESC) AS rn FROM a)
  WHERE rn = 1;

CREATE TEMPORARY VIEW lb AS
  SELECT k, v FROM (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY k, d ORDER BY ts DESC) AS rn FROM b)
  WHERE rn = 1;

-- V2: dedup key is (k) alone; it survives the projection
CREATE TEMPORARY VIEW ka AS
  SELECT k, v FROM (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY k ORDER BY ts DESC) AS rn FROM a)
  WHERE rn = 1;

CREATE TEMPORARY VIEW kb AS
  SELECT k, v FROM (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY k ORDER BY ts DESC) AS rn FROM b)
  WHERE rn = 1;

-- ---------- V1 inner
SELECT 'V1-inner' AS tag, la.k, la.v, lb.v FROM la JOIN lb ON la.k = lb.k;

-- ---------- V1 left outer
SELECT 'V1-outer' AS tag, la.k, la.v, lb.v FROM la LEFT JOIN lb ON la.k = lb.k;

-- ---------- V2 inner (the control: key survives the projection)
SELECT 'V2-inner' AS tag, ka.k, ka.v, kb.v FROM ka JOIN kb ON ka.k = kb.k;

-- ---------- V2 left outer
SELECT 'V2-outer' AS tag, ka.k, ka.v, kb.v FROM ka LEFT JOIN kb ON ka.k = kb.k;
