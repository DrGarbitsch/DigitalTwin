
-- ===== STEP 1 -- the entity appears =====
INSERT INTO entities VALUES ('c1', 'Cutter', TIMESTAMP '2026-01-01 00:00:00');

-- ===== STEP 2 -- violating attribute, LARGE ts =====
INSERT INTO attributes VALUES ('a1', 'c1', 'OFF', TIMESTAMP '2026-01-01 00:00:02', 1);

-- ===== STEP 3 -- good value with a SMALLER ts: under ORDER BY ts ASC this
--                 becomes the new top-1, so the verdict must clear =====
INSERT INTO attributes VALUES ('a1', 'c1', 'ON', TIMESTAMP '2026-01-01 00:00:01', 2);
