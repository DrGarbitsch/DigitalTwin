
-- ============================================================
-- THE QUERY -- paste this unchanged on BOTH versions.
-- "For every Cutter: 'critical' while it has a state that is not ON,
--  'ok' otherwise."  The LEFT JOIN keeps the entity in the result even
--  when it has no violating attribute, so the verdict can go back to 'ok'.
-- ============================================================
INSERT INTO verdict
SELECT u.`id` AS resource,
       CASE WHEN MAX(CASE WHEN v.this IS NOT NULL THEN 1 ELSE 0 END) = 1
            THEN 'critical' ELSE 'ok' END AS severity
FROM (SELECT `id` FROM entities_view WHERE `type` = 'Cutter') AS u
LEFT JOIN (
    SELECT `entityId` AS this FROM attributes_view WHERE `attributeValue` <> 'ON'
  ) AS v ON u.`id` = v.this
GROUP BY u.`id`;
