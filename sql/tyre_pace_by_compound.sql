-- Average pace per tyre compound in one race (Bahrain 2024 = race_id 202401).
--
-- Laps are joined to the stint that covers them to get the compound and tyre age;
-- lap 1, out-laps, in-laps (laps with a pit stop) and laps without a time are dropped.
-- Safety Car laps are still included: filtering them is part of stage 3.
WITH tyre_laps AS (
    SELECT
        l.driver_id,
        l.lap,
        l.lap_time_s,
        s.compound,
        l.lap - s.lap_start + COALESCE(s.tyre_age_at_start, 0) AS tyre_age
    FROM laps AS l
    JOIN stints AS s
        ON s.race_id = l.race_id
       AND s.driver_id = l.driver_id
       AND l.lap BETWEEN s.lap_start AND s.lap_end
    WHERE l.race_id = 202401
      AND l.lap > 1
      AND l.lap_time_s IS NOT NULL
      AND NOT l.is_pit_out_lap
      AND NOT EXISTS (
          SELECT 1 FROM pit_stops AS p
          WHERE p.race_id = l.race_id AND p.driver_id = l.driver_id AND p.lap = l.lap
      )
)
SELECT
    compound,
    COUNT(*) AS laps,
    COUNT(DISTINCT driver_id) AS drivers,
    ROUND(AVG(lap_time_s), 3) AS avg_lap_s,
    MAX(tyre_age) AS max_tyre_age
FROM tyre_laps
GROUP BY compound
ORDER BY avg_lap_s;
