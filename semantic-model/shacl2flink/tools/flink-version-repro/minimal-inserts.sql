
-- ===== STEP 1 -- the entity appears, it has no attributes yet =====
INSERT INTO entities VALUES ('c1', 'Cutter', TIMESTAMP '2026-01-01 00:00:00');

-- ===== STEP 2 -- a violating attribute appears (state OFF) =====
INSERT INTO attributes VALUES ('a1', 'c1', 'OFF', TIMESTAMP '2026-01-01 00:00:01', 1);

-- ===== STEP 3 -- the same attribute is superseded by a good value (ON) =====
INSERT INTO attributes VALUES ('a1', 'c1', 'ON', TIMESTAMP '2026-01-01 00:00:02', 2);
