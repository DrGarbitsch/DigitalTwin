-- The one structural feature the earlier reproducers lack: a FEEDBACK CYCLE.
--
-- Our pipeline writes constraint_trigger_table and reads it back in the same
-- job, so a verdict re-enters the operators that produced it. Four records
-- cannot loop, which is why the previous reproducers could not show anything.
--
-- Shape here, mirroring production:
--   a, b            upsert-kafka sources (the attributes)
--   trigger         upsert-kafka, WRITTEN by statement 1 and READ by statement 2
--   alerts          upsert-kafka, the final verdict
--
-- Statement 1 joins a and b with the key projected away (bag join) and writes
-- a verdict per key into `trigger`.
-- Statement 2 reads `trigger` back, joins it against `b` again and aggregates
-- into `alerts` -- closing the loop through Kafka exactly as the real job does.
--
-- Expectation: for N updates of ONE key, both statements emit O(N) records.
-- Amplification shows up as records-in-topic growing far beyond N.

SET 'execution.runtime-mode' = 'streaming';
SET 'parallelism.default' = '1';
SET 'table.exec.state.ttl' = '0';
SET 'pipeline.name' = 'cycle-B-keyed';

CREATE TABLE a (
  k STRING, d STRING, v STRING, ts TIMESTAMP(3),
  PRIMARY KEY (k) NOT ENFORCED
) WITH ('connector'='upsert-kafka','topic'='topic_a',
        'properties.bootstrap.servers'='repro-kafka:9092',
        'key.format'='json','value.format'='json');

CREATE TABLE b (
  k STRING, d STRING, v STRING, ts TIMESTAMP(3),
  PRIMARY KEY (k) NOT ENFORCED
) WITH ('connector'='upsert-kafka','topic'='topic_b',
        'properties.bootstrap.servers'='repro-kafka:9092',
        'key.format'='json','value.format'='json');

CREATE TABLE trigger_t (
  k STRING, verdict STRING,
  PRIMARY KEY (k) NOT ENFORCED
) WITH ('connector'='upsert-kafka','topic'='topic_trigger',
        'properties.bootstrap.servers'='repro-kafka:9092',
        'key.format'='json','value.format'='json');

CREATE TABLE alerts (
  k STRING, n BIGINT,
  PRIMARY KEY (k) NOT ENFORCED
) WITH ('connector'='upsert-kafka','topic'='topic_alerts',
        'properties.bootstrap.servers'='repro-kafka:9092',
        'key.format'='json','value.format'='json');

-- the projection drops d, so both join inputs are NoUniqueKey (as in production)
CREATE TEMPORARY VIEW pa AS SELECT k, v FROM a;
CREATE TEMPORARY VIEW pb AS SELECT k, v FROM b;
-- reading the trigger table back is what closes the cycle
CREATE TEMPORARY VIEW pt AS SELECT k, verdict FROM trigger_t;

EXECUTE STATEMENT SET
BEGIN
  INSERT INTO trigger_t
    SELECT pa.k, pa.v FROM pa JOIN pb ON pa.k = pb.k;
  INSERT INTO alerts
    SELECT pt.k, COUNT(*) FROM pt JOIN pb ON pt.k = pb.k GROUP BY pt.k;
END;
