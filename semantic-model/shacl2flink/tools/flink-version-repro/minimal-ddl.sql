-- ============================================================
-- DDL -- paste unchanged into BOTH versions.
-- ============================================================
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

-- the dedup sorts on TWO plain columns: `ts`, then `seq` as tie-breaker
CREATE TEMPORARY VIEW attributes_view AS
  SELECT `id`, `entityId`, `attributeValue` FROM (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY `id`
             ORDER BY `ts` DESC, `seq` DESC) AS rn
    FROM attributes) WHERE rn = 1;
