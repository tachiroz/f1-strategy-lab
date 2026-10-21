-- Laps prepared for the tyre model: one row per lap with its tyre and context.
--
-- The tyre of a lap comes from the stint that covers it. When OpenF1 lists the
-- pit in-lap in two stints, the lap belongs to the older stint: it was driven
-- on the old tyres. Tyre age = age at the start of the stint + laps into it.
-- The "seasons" bind parameter is a list, expanded by SQLAlchemy. (No colon-prefixed
-- names in comments: text() would treat them as extra bind parameters.)
WITH lap_stint AS (
    SELECT
        l.race_id,
        l.driver_id,
        l.lap,
        s.stint,
        s.compound,
        s.tyre_age_at_start + (l.lap - s.lap_start) AS tyre_age,
        ROW_NUMBER() OVER (
            PARTITION BY l.race_id, l.driver_id, l.lap
            ORDER BY s.stint
        ) AS stint_rank
    FROM laps AS l
    JOIN stints AS s
        ON s.race_id = l.race_id
       AND s.driver_id = l.driver_id
       AND l.lap BETWEEN s.lap_start AND s.lap_end
)
SELECT
    r.race_id,
    r.season,
    r.round,
    r.circuit_id,
    r.race_name,
    l.driver_id,
    l.lap,
    l.start_time_utc,
    l.lap_time_s,
    l.is_pit_out_lap,
    EXISTS (
        SELECT 1 FROM pit_stops AS p
        WHERE p.race_id = l.race_id AND p.driver_id = l.driver_id AND p.lap = l.lap
    ) AS is_pit_in_lap,
    ls.stint,
    ls.compound,
    ls.tyre_age
FROM laps AS l
JOIN races AS r ON r.race_id = l.race_id
LEFT JOIN lap_stint AS ls
    ON ls.race_id = l.race_id
   AND ls.driver_id = l.driver_id
   AND ls.lap = l.lap
   AND ls.stint_rank = 1
WHERE r.season IN :seasons
ORDER BY l.race_id, l.driver_id, l.lap;
