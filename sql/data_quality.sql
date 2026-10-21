-- Data quality checks for the f1lab database.
--
-- Every check is a query returning the offending rows; an empty result means OK.
-- A check starts with "-- name: <id>", followed by comment lines describing it.
-- Run them with:  python -m f1lab.db.quality
-- (the ingest CLI also runs them after loading).

-- name: race_without_openf1_session
-- Races that could not be linked to an OpenF1 race session.
SELECT race_id, season, round, race_name
FROM races
WHERE openf1_session_key IS NULL;

-- name: laps_without_result
-- Laps of drivers who are missing from the race classification.
SELECT l.race_id, l.driver_id, COUNT(*) AS laps
FROM laps AS l
LEFT JOIN results AS r
    ON r.race_id = l.race_id AND r.driver_id = l.driver_id
WHERE r.driver_id IS NULL
GROUP BY l.race_id, l.driver_id;

-- name: lap_beyond_race_distance
-- Timed laps numbered above the race distance (the winner's lap count).
-- Per-driver lap counts are not used: a DSQ has laps = 0, a retirement may
-- have one extra, incomplete lap in OpenF1. Untimed laps are ignored: OpenF1
-- opens an untimed lap after the chequered flag (2023-2025: 38 such rows).
WITH distance AS (
    SELECT race_id, MAX(laps) AS race_laps
    FROM results
    GROUP BY race_id
)
SELECT l.race_id, l.driver_id, l.lap, d.race_laps
FROM laps AS l
JOIN distance AS d ON d.race_id = l.race_id
WHERE l.lap > d.race_laps
  AND l.lap_time_s IS NOT NULL;

-- name: classified_without_laps
-- Finished or lapped drivers (numeric position) without any lap in OpenF1.
SELECT r.race_id, r.driver_id, r.position_text, r.laps
FROM results AS r
WHERE r.laps > 0
  AND r.position_text GLOB '[0-9]*'
  AND NOT EXISTS (
      SELECT 1 FROM laps AS l
      WHERE l.race_id = r.race_id AND l.driver_id = r.driver_id
  );

-- name: incomplete_lap_coverage
-- Finished or lapped drivers with some, but clearly not all, of their laps in
-- OpenF1 (one missing lap is tolerated). OpenF1 itself has such gaps: Miami 2025
-- has 559 of ~1,100 laps (laps 2-24 missing for most drivers).
WITH have AS (
    SELECT race_id, driver_id, COUNT(*) AS laps_rows
    FROM laps
    GROUP BY race_id, driver_id
)
SELECT r.race_id, r.driver_id, r.laps AS classified_laps, h.laps_rows
FROM results AS r
JOIN have AS h ON h.race_id = r.race_id AND h.driver_id = r.driver_id
WHERE r.position_text GLOB '[0-9]*'
  AND h.laps_rows < r.laps - 1;

-- name: stint_inverted_range
-- Stints that end before they start. lap_end = lap_start - 1 is a valid
-- zero-lap stint (tyres changed before completing a lap: pit-lane starts in
-- Monaco 2025, a red flag in Australia 2023), so only larger gaps are flagged.
SELECT race_id, driver_id, stint, lap_start, lap_end
FROM stints
WHERE lap_start > lap_end + 1;

-- name: stint_overlap
-- Consecutive stints of a driver that overlap by more than the boundary lap.
SELECT cur.race_id, cur.driver_id, cur.stint, cur.lap_end, nxt.lap_start
FROM stints AS cur
JOIN stints AS nxt
    ON nxt.race_id = cur.race_id
   AND nxt.driver_id = cur.driver_id
   AND nxt.stint = cur.stint + 1
WHERE nxt.lap_start < cur.lap_end;

-- name: shared_stint_lap_without_pit_stop
-- OpenF1 sometimes puts the lap of a pit stop (the in-lap) into both stints
-- (2023-2025: 305 of ~2600 transitions). That is only valid if the driver
-- really pitted on the shared lap.
SELECT cur.race_id, cur.driver_id, cur.stint, cur.lap_end AS shared_lap
FROM stints AS cur
JOIN stints AS nxt
    ON nxt.race_id = cur.race_id
   AND nxt.driver_id = cur.driver_id
   AND nxt.stint = cur.stint + 1
WHERE nxt.lap_start = cur.lap_end
  AND NOT EXISTS (
      SELECT 1 FROM pit_stops AS p
      WHERE p.race_id = cur.race_id AND p.driver_id = cur.driver_id AND p.lap = cur.lap_end
  );

-- name: timed_lap_without_stint
-- Timed laps not covered by any stint: their tyre compound is unknown.
SELECT l.race_id, l.driver_id, l.lap
FROM laps AS l
WHERE l.lap_time_s IS NOT NULL
  AND NOT EXISTS (
      SELECT 1 FROM stints AS s
      WHERE s.race_id = l.race_id
        AND s.driver_id = l.driver_id
        AND l.lap BETWEEN s.lap_start AND s.lap_end
  );

-- name: pit_stop_without_result
-- Pit stops of drivers who are missing from the race classification.
SELECT p.race_id, p.driver_id, p.stop
FROM pit_stops AS p
LEFT JOIN results AS r
    ON r.race_id = p.race_id AND r.driver_id = p.driver_id
WHERE r.driver_id IS NULL;
